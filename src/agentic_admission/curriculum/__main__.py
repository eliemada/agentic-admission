"""CLI entry point: ``python -m agentic_admission.curriculum``."""

from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger

from agentic_admission.curriculum.models import ProgramLevel
from agentic_admission.curriculum.scraper import scrape_curriculum
from agentic_admission.curriculum.storage import save_curriculum

_DEFAULT_OUTPUT = Path("data/reference/epfl_curriculum")


async def _main() -> None:
    logger.info("Starting EPFL curriculum scrape …")
    curriculum = await scrape_curriculum(
        levels=(ProgramLevel.BACHELOR, ProgramLevel.MASTER, ProgramLevel.MINOR)
    )
    save_curriculum(curriculum, _DEFAULT_OUTPUT)
    logger.info(
        "Done — {} programs, {} courses, {} entries written to {}",
        len(curriculum.programs),
        len(curriculum.courses),
        len(curriculum.entries),
        _DEFAULT_OUTPUT,
    )


if __name__ == "__main__":
    asyncio.run(_main())
