"""Demo: curriculum matching on a small cohort.

Tests the LLM-powered course matching against EPFL bachelors
for 3 candidates with diverse backgrounds.

Usage:
    uv run python scripts/demo_curriculum_match.py
    uv run python scripts/demo_curriculum_match.py --model <model> --base-url <url>
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from loguru import logger

from agentic_admission.agents.dossier_loader import (
    enrich_with_parquet,
    load_all_anonymized_dossiers,
)
from agentic_admission.config import settings
from agentic_admission.curriculum.matcher import format_match_report, match_curriculum
from agentic_admission.curriculum.storage import load_curriculum

# Pick 3 diverse candidates (different universities/countries)
_DEMO_CANDIDATES: list[str] = [
    "2020-21-fall_banasevic",  # UC San Diego, USA
    "2020-21-fall_atamny",  # TU München, Germany
    "2020-21-fall_fukuno",  # Kyoto University, Japan
]


def _load_dossiers(anonymized_root: Path, parquet_path: Path) -> list:
    """Load and filter to demo candidates."""
    all_dossiers = load_all_anonymized_dossiers(anonymized_root, limit=200)
    all_dossiers = enrich_with_parquet(all_dossiers, parquet_path)
    selected = [d for d in all_dossiers if d.candidate_id in _DEMO_CANDIDATES]

    found = {d.candidate_id for d in selected}
    missing = set(_DEMO_CANDIDATES) - found
    if missing:
        logger.warning("Could not find dossiers for: {}", missing)

    return selected


async def _run(
    *, model: str, base_url: str, api_key: str, anonymized_root: Path, parquet_path: Path
) -> None:
    """Run curriculum matching on demo candidates."""
    # Pre-load curriculum once
    try:
        curriculum = load_curriculum()
    except FileNotFoundError:
        logger.error("No curriculum data found. Run 'uv run poe scrape-curriculum' first.")
        return

    bachelor_count = sum(1 for p in curriculum.programs if p.level.value == "bachelor")
    minor_count = sum(1 for p in curriculum.programs if p.level.value == "minor")
    print(
        f"Curriculum loaded: {len(curriculum.programs)} programs "
        f"({bachelor_count} bachelors, {minor_count} minors), "
        f"{len(curriculum.courses)} courses"
    )

    if bachelor_count == 0:
        logger.error("No bachelor programs in curriculum — re-run scraper with bachelors enabled.")
        return

    dossiers = _load_dossiers(anonymized_root, parquet_path)
    if not dossiers:
        logger.error("No demo candidates found. Check data paths.")
        return

    print(f"\nMatching {len(dossiers)} candidates against EPFL curriculum...\n")

    for dossier in dossiers:
        print("=" * 70)
        print(f"  {dossier.candidate_id}")
        print(f"  School: {dossier.school_name} ({dossier.school_country})")
        print("=" * 70)

        if not dossier.transcript_text:
            print("  ⚠ No transcript text — skipping\n")
            continue

        try:
            report = await match_curriculum(
                candidate_id=dossier.candidate_id,
                transcript_text=dossier.transcript_text,
                model=model,
                base_url=base_url,
                api_key=api_key,
                curriculum=curriculum,
            )

            print(format_match_report(report))
            print()

        except Exception:
            logger.exception("Failed to match {}", dossier.candidate_id)
            print()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Demo: curriculum matching on 3 candidates")
    parser.add_argument("--anonymized-root", type=Path, default=Path("data/processed/anonymized"))
    parser.add_argument(
        "--parquet", type=Path, default=Path("data/processed/all_candidates.parquet")
    )
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--base-url", type=str, default=None)
    parser.add_argument("--api-key", type=str, default=None)
    args = parser.parse_args()

    model = args.model or settings.openrouter_model
    base_url = args.base_url or settings.openrouter_base_url
    api_key = args.api_key or settings.openrouter_api_key

    print("=" * 70)
    print("  EPFL Curriculum Matching Demo")
    print(f"  Model:    {model}")
    print(f"  Endpoint: {base_url}")
    print("=" * 70)
    print()

    asyncio.run(
        _run(
            model=model,
            base_url=base_url,
            api_key=api_key,
            anonymized_root=args.anonymized_root,
            parquet_path=args.parquet,
        )
    )


if __name__ == "__main__":
    main()
