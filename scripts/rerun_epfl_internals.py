"""Re-run only the 28 EPFL-internal candidates from Spring 2025-26, N times.

Used to validate the prompt fix (MTE EPFL-internal threshold 4.0 instead
of 4.5) without burning credits on the 100 external candidates the fix
doesn't touch.

Run::

    uv run python scripts/rerun_epfl_internals.py --n-runs 5 \\
        --output-prefix data/processed/runs_postfix/run
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
from agentic_admission.curriculum.university_profiles import detect_epfl_internal

# Hashes of the 28 EPFL-internals detected in the prior 5x run.
_EPFL_HASHES: frozenset[str] = frozenset(
    {
        "03f04df5270c",
        "04db248bd130",
        "16e8bbe0c623",
        "197a4a37be28",
        "395d50e5cc7d",
        "3e6f13cc2a98",
        "40e9ebcdde2c",
        "4d85b1bfa647",
        "5145dbcf0585",
        "5a65cc3ccc13",
        "6509240fe849",
        "6b91633db1da",
        "7573473ad40c",
        "800d73d4404c",
        "82ddf06044ac",
        "8655be1be89d",
        "8b296c88c36a",
        "8f5f3cc44828",
        "914281699b49",
        "99827b87624a",
        "ab7146ae20e9",
        "b932dc01c73a",
        "c8a8e2176664",
        "ceeedf663cd8",
        "d18ab8318eef",
        "d8a8b2b00d0b",
        "e3966f748a69",
        "f4c248134fc9",
    }
)


async def _run_one(dossier, model: str, base_url: str, api_key: str, output_dir: Path) -> None:
    """Evaluate one candidate and persist verdict JSON."""
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-runs", type=int, default=5)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()

    model = settings.model_name
    base_url = settings.model_base_url
    api_key = settings.openrouter_api_key

    # Load all Spring 2025-26 dossiers, filter to EPFL-internals.
    all_dossiers = load_all_anonymized_dossiers(
        Path("data/processed/anonymized"), semester="2025-26-spring"
    )
    enriched = enrich_with_parquet(all_dossiers, Path("data/processed/all_candidates.parquet"))

    epfl_dossiers = []
    for d in enriched:
        # Spring 2025-26 doesn't match parquet, so enrich didn't set is_epfl_internal.
        # Use the prior-detected hash list as the source of truth, and force the flag.
        if d.folder_name in _EPFL_HASHES:
            forced = d.model_copy(
                update={
                    "school_name": "Ecole polytechnique fédérale de Lausanne EPFL",
                    "is_epfl_internal": True,
                    "gpa_threshold": "4.0/6",
                }
            )
            epfl_dossiers.append(forced)

    logger.info("Loaded {} EPFL-internal dossiers", len(epfl_dossiers))

    for i in range(1, args.n_runs + 1):
        out_dir = Path(f"{args.output_prefix}{i:02d}")
        logger.info("=== RUN {}/{} → {} ===", i, args.n_runs, out_dir)
        asyncio.run(_run_batch(epfl_dossiers, model, base_url, api_key, out_dir, args.concurrency))

    logger.info("All {} runs complete", args.n_runs)


# Silence unused-import warning for detect_epfl_internal (kept for future use).
_ = detect_epfl_internal


if __name__ == "__main__":
    main()
