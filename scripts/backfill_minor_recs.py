"""Backfill ``minor_recommendation`` for verdicts where it is missing.

Some verdicts under ``data/processed/evaluations/`` were written without a
``minor_recommendation`` because the original ``recommend_minor`` coroutine
raised during the batch run (LLM JSON parsing failure, schema validation
failure, or the MTE-master safety-net ``RuntimeError``). The orchestrator
catches those exceptions via ``return_exceptions=True`` and proceeds with
``minor_recommendation=None`` so the candidate is not lost — but the
verdict file ends up incomplete.

This script re-runs ``recommend_minor`` for those candidates only, using
the same anonymized dossier inputs the orchestrator would have seen, and
patches the verdict JSON file in place.

Usage::

    uv run python scripts/backfill_minor_recs.py
    uv run python scripts/backfill_minor_recs.py --semester 2025-26-spring
    uv run python scripts/backfill_minor_recs.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
from loguru import logger

from agentic_admission.agents.dossier_loader import detect_epfl_internal, load_anonymized_dossier
from agentic_admission.agents.minor_advisor import recommend_minor
from agentic_admission.config import settings
from agentic_admission.models.evaluation import MinorRecommendation

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_EVAL_DIR = _PROJECT_ROOT / "data" / "processed" / "evaluations"
_ANON_ROOT = _PROJECT_ROOT / "data" / "processed" / "anonymized"


def _missing_minor_paths(eval_dir: Path, semester: str | None) -> list[Path]:
    """Return verdict files where ``minor_recommendation`` is null."""
    paths: list[Path] = []
    for path in sorted(eval_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Could not read {} — skipping", path.name)
            continue
        if data.get("minor_recommendation") is not None:
            continue
        if semester is not None and not path.stem.startswith(semester):
            continue
        paths.append(path)
    return paths


def _split_candidate_id(stem: str) -> tuple[str, str] | None:
    """``"2025-26-spring_abc123"`` → ``("2025-26-spring", "abc123")``.

    Splits on the *last* underscore so semester names that contain
    hyphens stay intact.
    """
    idx = stem.rfind("_")
    if idx <= 0 or idx == len(stem) - 1:
        return None
    return stem[:idx], stem[idx + 1 :]


async def _backfill_one(
    *,
    verdict_path: Path,
    model: str,
    base_url: str,
    api_key: str,
    dry_run: bool,
) -> bool:
    """Re-run ``recommend_minor`` for one verdict and patch the file.

    Returns ``True`` on success (or dry-run preview), ``False`` if the
    advisor still cannot produce a recommendation.
    """
    parts = _split_candidate_id(verdict_path.stem)
    if parts is None:
        logger.warning("Could not parse semester/folder from {}", verdict_path.stem)
        return False
    semester, folder = parts

    candidate_dir = _ANON_ROOT / semester / folder
    if not candidate_dir.is_dir():
        logger.warning("No anonymized dossier for {} (looked in {})", verdict_path.stem, candidate_dir)
        return False

    dossier = load_anonymized_dossier(candidate_dir, semester)

    # We do not know the original parquet-resolved school name here, so
    # detect EPFL-internal status from the dossier text directly. The
    # deterministic mapping in ``recommend_minor`` will pick this up via
    # ``full_dossier_text``.
    full_text = dossier.full_dossier_text
    is_epfl_internal = detect_epfl_internal(full_text)

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=120.0, headers=headers) as client:
        try:
            recommendation: MinorRecommendation = await recommend_minor(
                transcript_text=dossier.transcript_text,
                cv_text=dossier.cv_text,
                model=model,
                base_url=base_url,
                client=client,
                candidate_id=verdict_path.stem,
                is_epfl_internal=is_epfl_internal,
                full_dossier_text=full_text,
            )
        except Exception as exc:
            logger.opt(exception=True).warning(
                "recommend_minor still fails for {}: {}", verdict_path.stem, exc
            )
            return False

    payload = json.loads(recommendation.model_dump_json())
    logger.info(
        "{} -> {} (top score {})",
        verdict_path.stem,
        payload["primary_minor"],
        payload["recommended"][0]["fit_score"],
    )

    if dry_run:
        return True

    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    verdict["minor_recommendation"] = payload
    verdict_path.write_text(
        json.dumps(verdict, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return True


async def _run(
    *,
    eval_dir: Path,
    semester: str | None,
    model: str,
    base_url: str,
    api_key: str,
    concurrency: int,
    dry_run: bool,
) -> tuple[int, int]:
    """Backfill every missing-minor verdict. Returns (succeeded, attempted)."""
    targets = _missing_minor_paths(eval_dir, semester)
    if not targets:
        logger.info("No verdicts need backfill (semester filter: {})", semester)
        return (0, 0)

    logger.info("Backfilling {} verdicts (dry_run={}, concurrency={})", len(targets), dry_run, concurrency)

    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded(path: Path) -> bool:
        async with semaphore:
            return await _backfill_one(
                verdict_path=path,
                model=model,
                base_url=base_url,
                api_key=api_key,
                dry_run=dry_run,
            )

    results = await asyncio.gather(*(_bounded(p) for p in targets))
    return (sum(1 for r in results if r), len(targets))


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-dir", type=Path, default=_EVAL_DIR)
    parser.add_argument("--semester", type=str, default=None, help="Limit to one semester")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--base-url", type=str, default=None)
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true", help="Print recommendations without writing files")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)

    if settings.openrouter_api_key:
        model = args.model or settings.openrouter_model
        base_url = args.base_url or settings.openrouter_base_url
        api_key = args.api_key or settings.openrouter_api_key
    else:
        model = args.model or settings.model_name
        base_url = args.base_url or settings.model_base_url
        api_key = args.api_key or ""

    succeeded, attempted = asyncio.run(
        _run(
            eval_dir=args.eval_dir,
            semester=args.semester,
            model=model,
            base_url=base_url,
            api_key=api_key,
            concurrency=args.concurrency,
            dry_run=args.dry_run,
        )
    )
    logger.info("Backfill complete: {}/{} verdicts patched", succeeded, attempted)


if __name__ == "__main__":
    main()
