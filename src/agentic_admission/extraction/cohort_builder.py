"""Batch-parse all Synthese PDFs in a dossier semester and produce a cohort JSON.

Usage::

    python -m agentic_admission.extraction.cohort_builder [--semester 2025-26-fall]

Output is written to ``data/processed/cohort_{semester}.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from loguru import logger

from agentic_admission.extraction.synthese_parser import (
    SyntheseRecord,
    find_synthese_pdf,
    parse_synthese,
)

_PROJECT = Path(__file__).resolve().parent.parent.parent.parent
_DOSSIER_ROOT = _PROJECT / "data" / "raw" / "applications" / "dossiers"
_OUTPUT_ROOT = _PROJECT / "data" / "processed"


def build_cohort(semester: str) -> list[SyntheseRecord]:
    """Parse every dossier folder in *semester* and return records.

    Parameters
    ----------
    semester
        Subdirectory name under ``data/raw/applications/dossiers/``,
        e.g. ``"2025-26-fall"``.

    Returns
    -------
    list[SyntheseRecord]
        Successfully parsed records.
    """
    semester_dir = _DOSSIER_ROOT / semester
    if not semester_dir.is_dir():
        logger.error("Semester directory not found: {}", semester_dir)
        return []

    folders = sorted(f for f in semester_dir.iterdir() if f.is_dir())
    logger.info("Found {} dossier folders in {}", len(folders), semester)

    records: list[SyntheseRecord] = []
    failures: list[tuple[str, str]] = []

    for folder in folders:
        pdf_path = find_synthese_pdf(folder)
        if pdf_path is None:
            failures.append((folder.name, "No Synthese PDF found"))
            continue
        try:
            record = parse_synthese(pdf_path, folder.name)
            records.append(record)
        except Exception as exc:
            failures.append((folder.name, str(exc)))

    logger.info("Parsed {}/{} candidates successfully", len(records), len(folders))
    if failures:
        logger.warning("{} failures:", len(failures))
        for name, reason in failures:
            logger.warning("  {} — {}", name, reason)

    return records


def _records_to_dicts(records: list[SyntheseRecord]) -> list[dict[str, str]]:
    """Convert records to JSON-serializable dicts."""
    return [
        {
            "folder_name": r.folder_name,
            "application_id": r.application_id,
            "last_name": r.last_name,
            "first_names": r.first_names,
            "full_name": r.full_name,
            "gender": r.gender,
            "nationality": r.nationality,
            "institution_name": r.institution_name,
            "institution_country": r.institution_country,
            "field_of_study": r.field_of_study,
            "study_level": r.study_level,
            "gpa": r.gpa,
            "gpa_max": r.gpa_max,
        }
        for r in records
    ]


def save_cohort(semester: str) -> Path:
    """Build and save cohort JSON, returning the output path."""
    records = build_cohort(semester)
    if not records:
        logger.error("No records to save")
        return Path()

    _OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output_path = _OUTPUT_ROOT / f"cohort_{semester}.json"
    data = _records_to_dicts(records)
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved {} records to {}", len(data), output_path)
    return output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    semester_arg = "2025-26-fall"
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv[1:]):
            if arg == "--semester" and i + 2 < len(sys.argv):
                semester_arg = sys.argv[i + 2]
                break
            if not arg.startswith("--"):
                semester_arg = arg
                break

    save_cohort(semester_arg)
