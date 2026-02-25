"""Excel data extraction and normalization for admission files."""

from agentic_admission.extraction.pipeline import parse_file, run_pipeline

__all__ = ["parse_file", "run_pipeline"]
