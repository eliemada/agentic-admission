"""Re-run a semester batch on only the dossiers that match the parquet.

Useful for validation runs where unmatched dossiers add cost but no
ground-truth comparison is possible.

Usage::

    uv run python scripts/rerun_matched_only.py \\
        --semester 2024-25-fall \\
        --output-dir data/processed/runs/run_v3_fall_matched
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
from agentic_admission.agents.run_evaluation import evaluate_single
from agentic_admission.config import settings


async def _run_one(dossier, model, base_url, api_key, output_dir: Path) -> None:
    try:
        verdict, gpa = await evaluate_single(
            dossier, model=model, base_url=base_url, api_key=api_key
        )
        verdict_data = json.loads(verdict.model_dump_json())
        verdict_data["gpa"] = json.loads(gpa.model_dump_json())
        out = output_dir / f"{dossier.candidate_id}.json"
        out.write_text(json.dumps(verdict_data, indent=2), encoding="utf-8")
        logger.info(
            "Saved {} → {} (composite={:.2f})",
            dossier.candidate_id,
            verdict.decision.value,
            verdict.composite_score,
        )
    except Exception:
        logger.exception("Failed {}", dossier.candidate_id)


async def _run_batch(dossiers, model, base_url, api_key, output_dir, concurrency):
    output_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(d):
        async with sem:
            await _run_one(d, model, base_url, api_key, output_dir)

    await asyncio.gather(*(_bounded(d) for d in dossiers))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--semester", type=str, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--concurrency", type=int, default=4)
    args = p.parse_args()

    all_dossiers = load_all_anonymized_dossiers(
        Path("data/processed/anonymized"), semester=args.semester
    )
    enriched = enrich_with_parquet(all_dossiers, Path("data/processed/all_candidates.parquet"))

    matched = [d for d in enriched if (d.decision_final or "").strip()]
    logger.info(
        "Filtered: {} matched dossiers (with committee decision) out of {}",
        len(matched),
        len(enriched),
    )

    asyncio.run(
        _run_batch(
            matched,
            settings.model_name,
            settings.model_base_url,
            settings.openrouter_api_key,
            args.output_dir,
            args.concurrency,
        )
    )
    logger.info("Done. Verdicts saved to {}", args.output_dir)


if __name__ == "__main__":
    main()
