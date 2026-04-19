"""Demo evaluation: run the pipeline on 5 candidates and compare with committee.

Picks 2 admitted + 3 rejected candidates with complete dossiers.
Prints a comparison table showing agent vs. committee agreement.

Usage:
    uv run python scripts/demo_eval.py --model <model> --base-url <url>
    uv run python scripts/demo_eval.py  # uses .env defaults
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from loguru import logger

from agentic_admission.agents.dossier_loader import (
    enrich_with_parquet,
    load_all_anonymized_dossiers,
)
from agentic_admission.agents.run_evaluation import evaluate_single, print_comparison_table
from agentic_admission.config import settings
from agentic_admission.models.evaluation import PanelVerdict

# ---------------------------------------------------------------------------
# Target candidates: 2 admitted, 3 rejected (diverse backgrounds, complete dossiers)
# ---------------------------------------------------------------------------

_DEMO_CANDIDATES: dict[str, str] = {
    # --- Admitted ---
    "2020-21-fall_banasevic": "accept",  # UC San Diego, USA
    "2020-21-fall_polydorou": "accept",  # NTU Athens, Greece
    # --- Rejected ---
    "2020-21-fall_atamny": "reject",  # TU München, Germany
    "2020-21-fall_boukhabrine": "reject",  # McGill, Canada
    "2020-21-fall_fukuno": "reject",  # Kyoto University, Japan
}


def _select_demo_dossiers(anonymized_root: Path, parquet_path: Path) -> list:
    """Load and filter to only the demo candidates."""
    all_dossiers = load_all_anonymized_dossiers(anonymized_root, limit=200)
    all_dossiers = enrich_with_parquet(all_dossiers, parquet_path)

    selected = [d for d in all_dossiers if d.candidate_id in _DEMO_CANDIDATES]

    found = {d.candidate_id for d in selected}
    missing = set(_DEMO_CANDIDATES) - found
    if missing:
        logger.warning("Could not find dossiers for: {}", missing)

    logger.info(
        "Selected {} demo candidates: {}", len(selected), [d.candidate_id for d in selected]
    )
    return selected


async def _run_demo(
    *,
    model: str,
    base_url: str,
    api_key: str,
    output_dir: Path,
    anonymized_root: Path,
    parquet_path: Path,
) -> None:
    """Run evaluation on demo candidates and print results."""
    dossiers = _select_demo_dossiers(anonymized_root, parquet_path)
    if not dossiers:
        logger.error("No demo candidates found. Check data paths.")
        return

    results = []

    for dossier in dossiers:
        logger.info("Evaluating {} ({}) ...", dossier.candidate_id, dossier.school_name)
        try:
            verdict, gpa = await evaluate_single(
                dossier, model=model, base_url=base_url, api_key=api_key
            )

            # Save verdict JSON
            verdict_data = json.loads(verdict.model_dump_json())
            verdict_data["gpa"] = json.loads(gpa.model_dump_json())
            verdict_path = output_dir / f"{dossier.candidate_id}.json"
            verdict_path.write_text(
                json.dumps(verdict_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            results.append((dossier, verdict))

            _print_single_result(dossier, verdict, gpa)

        except Exception:
            logger.exception("Failed to evaluate {}", dossier.candidate_id)

    # Final comparison table
    print_comparison_table(results)
    logger.info("Verdicts saved to {}", output_dir)


def _print_single_result(dossier: object, verdict: PanelVerdict, gpa: object) -> None:
    """Print a brief summary for one candidate right after evaluation."""
    committee = (dossier.decision_final or "unknown").strip()
    match = "MATCH" if verdict.decision.value == committee.lower() else "MISMATCH"

    minor_str = ""
    if verdict.minor_recommendation is not None:
        minor_str = f" | minor: {verdict.minor_recommendation.primary_minor}"

    print()  # noqa: T201
    print(f"  {dossier.candidate_id}")  # noqa: T201
    print(f"    School:    {dossier.school_name} ({dossier.school_country})")  # noqa: T201
    print(f"    GPA:       {gpa.gpa_value}/{gpa.gpa_scale} (norm: {gpa.gpa_normalized:.0f}/100)")  # noqa: T201
    print(f"    Agent:     {verdict.decision.value} (composite: {verdict.composite_score:.1f})")  # noqa: T201
    print(f"    Committee: {committee}")  # noqa: T201
    print(f"    Result:    {match}{minor_str}")  # noqa: T201

    # Print pros/cons
    justification = verdict.justification
    if hasattr(justification, "pros"):
        if justification.pros:
            print("    Pros:")  # noqa: T201
            for pro in justification.pros:
                print(f"      + {pro}")  # noqa: T201
        if justification.cons:
            print("    Cons:")  # noqa: T201
            for con in justification.cons:
                print(f"      - {con}")  # noqa: T201
    else:
        print(f"    Summary:   {justification}")  # noqa: T201
    print()  # noqa: T201


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Demo evaluation: 5 candidates (2 admitted, 3 rejected)"
    )
    parser.add_argument("--anonymized-root", type=Path, default=Path("data/processed/anonymized"))
    parser.add_argument(
        "--parquet", type=Path, default=Path("data/processed/all_candidates.parquet")
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output dir for verdict JSONs (default: from .env)",
    )
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--base-url", type=str, default=None)
    parser.add_argument("--api-key", type=str, default=None)
    args = parser.parse_args()

    model = args.model or settings.model_name
    base_url = args.base_url or settings.model_base_url
    api_key = args.api_key or settings.openrouter_api_key
    output_dir = args.output_dir or Path(settings.evaluation_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)  # noqa: T201
    print("  MTE Admission Demo Evaluation")  # noqa: T201
    print(f"  Model:    {model}")  # noqa: T201
    print(f"  Endpoint: {base_url}")  # noqa: T201
    print(f"  Output:   {output_dir}")  # noqa: T201
    print("=" * 60)  # noqa: T201
    print()  # noqa: T201
    print("  Candidates:")  # noqa: T201
    for cid, expected in _DEMO_CANDIDATES.items():
        print(f"    {cid} (expected: {expected})")  # noqa: T201
    print()  # noqa: T201

    asyncio.run(
        _run_demo(
            model=model,
            base_url=base_url,
            api_key=api_key,
            output_dir=output_dir,
            anonymized_root=args.anonymized_root,
            parquet_path=args.parquet,
        )
    )


if __name__ == "__main__":
    main()
