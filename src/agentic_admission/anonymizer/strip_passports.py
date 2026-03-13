"""Record passport/ID presence per candidate and optionally delete the files.

Scans all candidate dossier folders, records which candidates submitted a
passport or identity document, writes an inventory parquet, and optionally
removes the passport/ID folders to eliminate sensitive PII.

Run standalone
--------------
.. code-block:: bash

    uv run python -m agentic_admission.anonymizer.strip_passports          # dry-run
    uv run python -m agentic_admission.anonymizer.strip_passports --delete # delete
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DOSSIER_ROOT = Path("data/raw/applications/dossiers")
_OUTPUT_PATH = Path("data/processed/dossier_inventory.parquet")

_PASSPORT_KEYWORDS = ("passeport", "identite", "identité")
"""Substrings matched case-insensitively against subdirectory names."""


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _is_passport_dir(name: str) -> bool:
    """Return True if *name* looks like a passport/ID folder."""
    lower = name.lower()
    return any(kw in lower for kw in _PASSPORT_KEYWORDS)


def _folder_stats(folder: Path) -> tuple[int, int]:
    """Return (file_count, total_size_bytes) for all files under *folder*."""
    count = 0
    size = 0
    for f in folder.rglob("*"):
        if f.is_file():
            count += 1
            size += f.stat().st_size
    return count, size


def scan_dossiers(root: Path) -> list[dict[str, Any]]:
    """Scan *root* for candidate dossier folders and record passport presence.

    Parameters
    ----------
    root
        Path to the dossiers directory (e.g. ``data/raw/applications/dossiers``).

    Returns
    -------
    list[dict[str, Any]]
        One row per candidate with keys: ``semester``, ``candidate_folder``,
        ``has_passport_id``, ``passport_file_count``, ``passport_size_kb``,
        ``passport_dir`` (the resolved path, for deletion).
    """
    rows: list[dict[str, Any]] = []

    semester_dirs = sorted(d for d in root.iterdir() if d.is_dir())
    for semester_dir in semester_dirs:
        semester = semester_dir.name
        candidate_dirs = sorted(d for d in semester_dir.iterdir() if d.is_dir())
        for cand_dir in candidate_dirs:
            passport_dirs = [
                d for d in cand_dir.iterdir() if d.is_dir() and _is_passport_dir(d.name)
            ]

            if passport_dirs:
                for pdir in passport_dirs:
                    fcount, fsize = _folder_stats(pdir)
                    rows.append(
                        {
                            "semester": semester,
                            "candidate_folder": cand_dir.name,
                            "has_passport_id": True,
                            "passport_file_count": fcount,
                            "passport_size_kb": round(fsize / 1024, 1),
                            "passport_dir": str(pdir),
                        }
                    )
            else:
                rows.append(
                    {
                        "semester": semester,
                        "candidate_folder": cand_dir.name,
                        "has_passport_id": False,
                        "passport_file_count": 0,
                        "passport_size_kb": 0.0,
                        "passport_dir": "",
                    }
                )

    return rows


def write_inventory(rows: list[dict[str, Any]], output: Path) -> None:
    """Write inventory rows to a Parquet file."""
    schema = pa.schema(
        [
            ("semester", pa.string()),
            ("candidate_folder", pa.string()),
            ("has_passport_id", pa.bool_()),
            ("passport_file_count", pa.int32()),
            ("passport_size_kb", pa.float64()),
        ]
    )
    columns: dict[str, list[object]] = {
        "semester": [r["semester"] for r in rows],
        "candidate_folder": [r["candidate_folder"] for r in rows],
        "has_passport_id": [r["has_passport_id"] for r in rows],
        "passport_file_count": [r["passport_file_count"] for r in rows],
        "passport_size_kb": [r["passport_size_kb"] for r in rows],
    }
    table = pa.table(columns, schema=schema)
    output.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, output)
    logger.info("Wrote {} rows to {}", len(rows), output)


def delete_passport_dirs(rows: list[dict[str, Any]]) -> tuple[int, float]:
    """Delete all passport/ID directories recorded in *rows*.

    Returns
    -------
    tuple[int, float]
        (folders_deleted, megabytes_freed)
    """
    deleted = 0
    freed_kb = 0.0
    for row in rows:
        pdir = row["passport_dir"]
        if not pdir or not row["has_passport_id"]:
            continue
        path = Path(str(pdir))
        if path.exists():
            freed_kb += float(row["passport_size_kb"])
            shutil.rmtree(path)
            logger.debug("Deleted {}", path)
            deleted += 1
    return deleted, freed_kb / 1024


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the passport stripping pipeline."""
    parser = argparse.ArgumentParser(
        description="Record passport/ID presence and optionally delete the files."
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete passport/ID folders (default is dry-run).",
    )
    parser.add_argument(
        "--dossier-root", type=Path, default=_DOSSIER_ROOT, help="Root directory of dossier data."
    )
    parser.add_argument(
        "--output", type=Path, default=_OUTPUT_PATH, help="Output parquet file path."
    )
    args = parser.parse_args()

    if not args.dossier_root.exists():
        logger.error("Dossier root not found: {}", args.dossier_root)
        sys.exit(1)

    logger.info("Scanning dossiers in {}", args.dossier_root)
    rows = scan_dossiers(args.dossier_root)

    has_passport = sum(1 for r in rows if r["has_passport_id"])
    total_size_mb = sum(float(r["passport_size_kb"]) for r in rows) / 1024
    logger.info(
        "Found {} candidates: {} with passport/ID ({:.1f} MB)",
        len(rows),
        has_passport,
        total_size_mb,
    )

    write_inventory(rows, args.output)

    if args.delete:
        deleted, freed_mb = delete_passport_dirs(rows)
        logger.info("Deleted {} passport/ID folders, freed {:.1f} MB", deleted, freed_mb)
    else:
        logger.info("Dry-run mode — no files deleted. Pass --delete to remove passport folders.")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    main()
