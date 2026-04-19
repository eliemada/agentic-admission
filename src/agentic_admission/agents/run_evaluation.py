"""CLI runner: evaluate candidates E2E and compare with committee decisions."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx
from loguru import logger

from agentic_admission.agents.dossier_loader import (
    DossierContent,
    enrich_with_parquet,
    load_all_anonymized_dossiers,
)
from agentic_admission.agents.gpa_extractor import GpaExtraction, extract_gpa
from agentic_admission.agents.orchestrator import evaluate_candidate
from agentic_admission.calibration.retriever import get_calibration_context
from agentic_admission.config import settings
from agentic_admission.models.evaluation import PanelVerdict

# Mapping from committee decision strings to normalized values
_COMMITTEE_DECISION_MAP: dict[str, str] = {
    "ok": "accept",
    "oui": "accept",
    "yes": "accept",
    "admis": "accept",
    "admitted": "accept",
    "accept": "accept",
    "accepté": "accept",
    "accepté / bourse": "accept",
    "yes - bourse": "accept",
    "no": "reject",
    "non": "reject",
    "refusé": "reject",
    "refused": "reject",
    "reject": "reject",
    "a discuter": "waitlist",
    "discuss": "waitlist",
    "waitlist": "waitlist",
    "liste d'attente": "waitlist",
}


def _normalize_committee_decision(raw: str) -> str:
    """Normalize a committee decision string to accept/reject/waitlist/unknown.

    Parameters
    ----------
    raw
        Raw decision from the Parquet (e.g. "OK", "NO", "A discuter").

    Returns
    -------
    str
        One of ``"accept"``, ``"reject"``, ``"waitlist"``, or ``"unknown"``.
    """
    cleaned = raw.strip().lower()
    return _COMMITTEE_DECISION_MAP.get(cleaned, "unknown")


async def evaluate_single(
    dossier: DossierContent, *, model: str, base_url: str, api_key: str = ""
) -> tuple[PanelVerdict, GpaExtraction]:
    """Evaluate one candidate through the full pipeline.

    Steps:

    1. Extract GPA from transcript text.
    2. Get calibration context (profile + historical letters from zsearch).
    3. Call the 4-phase agent orchestrator.
    4. Return the ``PanelVerdict`` and ``GpaExtraction``.

    Parameters
    ----------
    dossier
        Loaded and enriched dossier content.
    model
        LLM model identifier.
    base_url
        LLM endpoint base URL.
    api_key
        Optional API key for cloud endpoints (OpenRouter, etc.).

    Returns
    -------
    tuple[PanelVerdict, GpaExtraction]
        The agent panel's verdict and GPA extraction for this candidate.
    """
    # --- Phase 0: GPA extraction (non-fatal) ---
    _fallback_gpa = GpaExtraction(
        gpa_value="N/A",
        gpa_scale="N/A",
        gpa_normalized=0.0,
        grading_system="unknown",
        institution_name="unknown",
        degree_name="unknown",
        notable_courses="GPA extraction failed.",
        trajectory="stable",
        confidence=0.0,
    )

    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient(timeout=120.0, headers=headers) as client:
            gpa = await extract_gpa(
                dossier.transcript_text, model=model, base_url=base_url, client=client
            )
    except Exception:
        logger.warning("GPA extraction failed for {}, continuing without GPA", dossier.candidate_id)
        gpa = _fallback_gpa

    logger.info(
        "GPA for {}: {}/{} (normalized: {:.1f}, confidence: {:.2f})",
        dossier.candidate_id,
        gpa.gpa_value,
        gpa.gpa_scale,
        gpa.gpa_normalized,
        gpa.confidence,
    )

    # Enrich dossier with GPA data
    dossier = dossier.model_copy(
        update={
            "gpa_value": gpa.gpa_value,
            "gpa_scale": gpa.gpa_scale,
            "gpa_normalized": gpa.gpa_normalized,
            "gpa_grading_system": gpa.grading_system,
            "gpa_institution": gpa.institution_name,
            "gpa_confidence": gpa.confidence,
        }
    )

    # Prepend SPE metadata and GPA summary to transcript text
    enriched_transcript = dossier.transcript_text

    # SPE institutional context (set by EPFL before any evaluation)
    spe_header_parts: list[str] = []
    if dossier.school_quality or dossier.gpa_threshold:
        spe_header_parts.append("## EPFL SPE Institutional Assessment\n")
        if dossier.school_quality:
            spe_header_parts.append(
                f"- Institution category: **{dossier.school_quality}**\n"
            )
        if dossier.gpa_threshold:
            spe_header_parts.append(
                f"- GPA admission threshold for this institution: "
                f"**{dossier.gpa_threshold}**\n"
            )
        if dossier.spe_remarks:
            spe_header_parts.append(f"- SPE remarks: {dossier.spe_remarks}\n")
        spe_header_parts.append(
            "\nCandidates below the GPA threshold are normally rejected "
            "unless exceptional circumstances justify an exception.\n"
        )
        spe_header_parts.append("\n---\n\n")

    if gpa.gpa_value != "N/A":
        gpa_summary = (
            f"## Extracted GPA Summary\n\n"
            f"- GPA: {gpa.gpa_value}/{gpa.gpa_scale} ({gpa.grading_system})\n"
            f"- Normalized: {gpa.gpa_normalized:.1f}/100\n"
            f"- Institution: {gpa.institution_name}\n"
            f"- Degree: {gpa.degree_name}\n"
            f"- Trajectory: {gpa.trajectory}\n"
            f"- Notable courses: {gpa.notable_courses}\n"
            f"- Extraction confidence: {gpa.confidence:.0%}\n\n---\n\n"
        )
        spe_header_parts.append(gpa_summary)

    if spe_header_parts:
        enriched_transcript = "".join(spe_header_parts) + dossier.transcript_text

    calibration_context, historical_letters = get_calibration_context(
        candidate_letters=dossier.letters_text,
        school_name=dossier.school_name,
        school_country=dossier.school_country,
        school_quality=dossier.school_quality,
    )

    verdict = await evaluate_candidate(
        candidate_id=dossier.candidate_id,
        transcript_text=enriched_transcript,
        letters_text=dossier.letters_text,
        calibration_context=calibration_context,
        historical_letters=historical_letters,
        motivation_text=dossier.motivation_text,
        cv_text=dossier.cv_text,
        full_dossier_text=dossier.full_dossier_text,
        model=model,
        base_url=base_url,
        api_key=api_key,
    )

    return verdict, gpa


async def run_batch(
    dossiers: list[DossierContent],
    *,
    model: str,
    base_url: str,
    api_key: str = "",
    output_dir: Path,
    concurrency: int = 4,
) -> list[tuple[DossierContent, PanelVerdict]]:
    """Evaluate a batch of candidates with bounded concurrency.

    Uses ``asyncio.Semaphore`` to limit parallel LLM calls.
    Saves each verdict (with GPA data) as JSON immediately after completion.

    Parameters
    ----------
    dossiers
        List of dossier contents to evaluate.
    model
        LLM model identifier.
    base_url
        LLM endpoint base URL.
    output_dir
        Directory to save verdict JSON files.
    concurrency
        Maximum number of parallel evaluations.

    Returns
    -------
    list[tuple[DossierContent, PanelVerdict]]
        Pairs of (dossier, verdict) for all successfully evaluated candidates.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _evaluate_with_semaphore(
        dossier: DossierContent,
    ) -> tuple[DossierContent, PanelVerdict] | None:
        async with semaphore:
            try:
                logger.info("Evaluating {} ...", dossier.candidate_id)
                verdict, gpa = await evaluate_single(
                    dossier, model=model, base_url=base_url, api_key=api_key
                )

                # Merge verdict and GPA into a single JSON output
                verdict_data = json.loads(verdict.model_dump_json())
                verdict_data["gpa"] = json.loads(gpa.model_dump_json())

                verdict_path = output_dir / f"{dossier.candidate_id}.json"
                verdict_path.write_text(json.dumps(verdict_data, indent=2), encoding="utf-8")
                logger.info(
                    "Verdict for {}: {} (composite: {:.1f}, GPA: {}/{})",
                    dossier.candidate_id,
                    verdict.decision.value,
                    verdict.composite_score,
                    gpa.gpa_value,
                    gpa.gpa_scale,
                )
                return (dossier, verdict)
            except Exception:
                logger.exception("Failed to evaluate {}", dossier.candidate_id)
                return None

    tasks = [_evaluate_with_semaphore(d) for d in dossiers]
    raw_results = await asyncio.gather(*tasks)
    results = [r for r in raw_results if r is not None]

    logger.info("Evaluated {}/{} candidates successfully", len(results), len(dossiers))
    return results


def print_comparison_table(results: list[tuple[DossierContent, PanelVerdict]]) -> None:
    """Print a table comparing agent decisions vs committee decisions.

    Parameters
    ----------
    results
        Pairs of (dossier, verdict) from the evaluation batch.
    """
    if not results:
        logger.warning("No results to display")
        return

    # Header
    header = f"{'Candidate':<35} {'Agent':<10} {'Committee':<10} {'Composite':>9} {'Match':>5}"
    separator = "-" * len(header)

    print()  # noqa: T201
    print(separator)  # noqa: T201
    print(header)  # noqa: T201
    print(separator)  # noqa: T201

    match_count = 0
    total = len(results)

    for dossier, verdict in results:
        agent_decision = verdict.decision.value
        committee_raw = dossier.decision_final
        committee_normalized = _normalize_committee_decision(committee_raw)

        is_match = agent_decision == committee_normalized
        if is_match:
            match_count += 1

        match_str = "Y" if is_match else "N"
        if committee_normalized == "unknown":
            match_str = "?"

        print(  # noqa: T201
            f"{dossier.candidate_id:<35} "
            f"{agent_decision:<10} "
            f"{committee_normalized:<10} "
            f"{verdict.composite_score:>9.1f} "
            f"{match_str:>5}"
        )

    print(separator)  # noqa: T201

    # Exclude unknowns from agreement calculation
    known = [
        (d, v) for d, v in results if _normalize_committee_decision(d.decision_final) != "unknown"
    ]
    known_matches = sum(
        1 for d, v in known if v.decision.value == _normalize_committee_decision(d.decision_final)
    )
    known_total = len(known)

    if known_total > 0:
        pct = known_matches / known_total * 100
        print(f"Agreement: {known_matches}/{known_total} ({pct:.0f}%)")  # noqa: T201
    else:
        print(f"Total evaluated: {total} (no committee decisions available for comparison)")  # noqa: T201
    print()  # noqa: T201


def main() -> None:
    """CLI entrypoint for E2E admission evaluation."""
    parser = argparse.ArgumentParser(description="Run E2E admission evaluation")
    parser.add_argument(
        "--anonymized-root",
        type=Path,
        default=Path("data/processed/anonymized"),
        help="Root of anonymized dossier tree",
    )
    parser.add_argument(
        "--parquet",
        type=Path,
        default=Path("data/processed/all_candidates.parquet"),
        help="Path to candidates Parquet file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for verdict JSON files (default: from .env)",
    )
    parser.add_argument(
        "--limit", type=int, default=5, help="Number of candidates to evaluate (default: 5)"
    )
    parser.add_argument(
        "--model", type=str, default=None, help="LLM model identifier (default: from .env)"
    )
    parser.add_argument(
        "--base-url", type=str, default=None, help="LLM endpoint base URL (default: from .env)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key for cloud LLM endpoints (default: OPENROUTER_API_KEY from .env)",
    )
    parser.add_argument(
        "--concurrency", type=int, default=4, help="Max parallel evaluations (default: 4)"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=False,
        help="Skip candidates that already have a verdict JSON in the output dir",
    )
    args = parser.parse_args()

    model = args.model or settings.model_name
    base_url = args.base_url or settings.model_base_url
    api_key = args.api_key or settings.openrouter_api_key
    output_dir = args.output_dir or Path(settings.evaluation_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading anonymized dossiers (limit={}) ...", args.limit)
    dossiers = load_all_anonymized_dossiers(args.anonymized_root, limit=args.limit)

    if not dossiers:
        logger.error("No dossiers found at {}", args.anonymized_root)
        return

    logger.info("Enriching with Parquet metadata ...")
    dossiers = enrich_with_parquet(dossiers, args.parquet)

    if args.skip_existing:
        before = len(dossiers)
        dossiers = [d for d in dossiers if not (output_dir / f"{d.candidate_id}.json").exists()]
        skipped = before - len(dossiers)
        if skipped:
            logger.info("Skipped {} already-evaluated candidates", skipped)
        if not dossiers:
            logger.info("All candidates already evaluated, nothing to do")
            return

    logger.info(
        "Starting evaluation: {} candidates, model={}, base_url={}", len(dossiers), model, base_url
    )

    results = asyncio.run(
        run_batch(
            dossiers,
            model=model,
            base_url=base_url,
            api_key=api_key,
            output_dir=output_dir,
            concurrency=args.concurrency,
        )
    )

    print_comparison_table(results)

    logger.info("Verdicts saved to {}", output_dir)


if __name__ == "__main__":
    main()
