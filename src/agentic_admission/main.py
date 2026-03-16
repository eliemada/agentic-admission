"""Entry point for the agentic-admission system."""

from __future__ import annotations

import sys

from loguru import logger

from agentic_admission.config import settings


def run() -> None:
    """Launch the admission agent pipeline."""
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)
    logger.info("agentic-admission starting (model={})", settings.model_name)
    logger.info("Agent deliberation system ready. Use evaluate_candidate() to evaluate dossiers.")


if __name__ == "__main__":
    run()
