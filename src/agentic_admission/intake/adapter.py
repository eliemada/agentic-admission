"""Intake adapter: detect format, unpack archives, and scan dossier trees.

Supports three input formats:

- A plain directory (passthrough to scanner)
- A single ZIP or TAR/TAR.GZ archive
- A directory of per-candidate ZIP files

Run standalone
--------------
.. code-block:: bash

    uv run python -m agentic_admission.intake.adapter path/to/source --output data/staging/
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import zipfile
from enum import Enum
from pathlib import Path

from loguru import logger

from agentic_admission.intake.scanner import scan_dossier_tree
from agentic_admission.models.dossier import Dossier

# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_ZIP_MAGIC = b"PK\x03\x04"
_GZIP_MAGIC = b"\x1f\x8b"
_MAGIC_READ_SIZE = 8


class ArchiveFormat(Enum):
    """Detected input format."""

    ZIP = "zip"
    TAR = "tar"
    DIRECTORY = "directory"
    ZIP_DIRECTORY = "zip_directory"


def detect_format(source: Path) -> ArchiveFormat:
    """Detect the format of *source*.

    Parameters
    ----------
    source
        Path to a file or directory.

    Returns
    -------
    ArchiveFormat
        The detected format.

    Raises
    ------
    FileNotFoundError
        If *source* does not exist.
    ValueError
        If the format cannot be determined.
    """
    if not source.exists():
        msg = f"Source not found: {source}"
        raise FileNotFoundError(msg)

    if source.is_dir():
        # Check if it's a directory of ZIPs
        children = list(source.iterdir())
        zips = [c for c in children if c.suffix.lower() == ".zip" and c.is_file()]
        if zips and len(zips) == len([c for c in children if c.is_file()]):
            return ArchiveFormat.ZIP_DIRECTORY
        return ArchiveFormat.DIRECTORY

    # File — check magic bytes
    header = source.read_bytes()[:_MAGIC_READ_SIZE]

    if header.startswith(_ZIP_MAGIC):
        return ArchiveFormat.ZIP

    if header.startswith(_GZIP_MAGIC) or source.suffix in {".tar", ".tgz"}:
        return ArchiveFormat.TAR

    msg = f"Unsupported format for: {source}"
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def _is_safe_path(member_path: str, destination: Path) -> bool:
    """Return True if *member_path* resolves inside *destination*."""
    resolved = (destination / member_path).resolve()
    return str(resolved).startswith(str(destination.resolve()))


def _extract_zip(archive: Path, destination: Path) -> None:
    """Extract a ZIP archive to *destination*, skipping unsafe paths."""
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "r") as zf:
        for member in zf.infolist():
            if not _is_safe_path(member.filename, destination):
                logger.warning("Skipping unsafe path in ZIP: {}", member.filename)
                continue
            zf.extract(member, destination)


def _extract_tar(archive: Path, destination: Path) -> None:
    """Extract a TAR archive to *destination*, skipping unsafe paths."""
    destination.mkdir(parents=True, exist_ok=True)
    mode = "r:gz" if archive.suffix in {".gz", ".tgz"} else "r:"
    with tarfile.open(archive, mode) as tf:
        safe_members = []
        for member in tf.getmembers():
            if not _is_safe_path(member.name, destination):
                logger.warning("Skipping unsafe path in TAR: {}", member.name)
                continue
            safe_members.append(member)
        tf.extractall(destination, members=safe_members)  # noqa: S202


def _extract_zip_directory(source: Path, destination: Path) -> None:
    """Extract each ZIP in *source* to *destination*."""
    destination.mkdir(parents=True, exist_ok=True)
    for zip_path in sorted(source.glob("*.zip")):
        logger.debug("Extracting {}", zip_path.name)
        _extract_zip(zip_path, destination)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ingest(source: Path, destination: Path) -> list[Dossier]:
    """Detect format, unpack if needed, scan, and return dossiers.

    Parameters
    ----------
    source
        Path to a ZIP, TAR, directory, or directory of ZIPs.
    destination
        Staging directory where archives are unpacked.  For plain directories
        the scanner reads *source* directly and *destination* is created but
        not used for extraction.

    Returns
    -------
    list[Dossier]
        Scanned dossiers from the unpacked tree.
    """
    fmt = detect_format(source)
    destination.mkdir(parents=True, exist_ok=True)

    scan_root: Path

    if fmt == ArchiveFormat.DIRECTORY:
        logger.info("Source is a directory, scanning directly: {}", source)
        scan_root = source

    elif fmt == ArchiveFormat.ZIP:
        logger.info("Extracting ZIP: {} → {}", source, destination)
        _extract_zip(source, destination)
        scan_root = destination

    elif fmt == ArchiveFormat.TAR:
        logger.info("Extracting TAR: {} → {}", source, destination)
        _extract_tar(source, destination)
        scan_root = destination

    elif fmt == ArchiveFormat.ZIP_DIRECTORY:
        logger.info("Extracting per-candidate ZIPs from: {} → {}", source, destination)
        _extract_zip_directory(source, destination)
        scan_root = destination

    else:
        msg = f"Unhandled format: {fmt}"
        raise ValueError(msg)

    return scan_dossier_tree(scan_root)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the intake adapter from the command line."""
    parser = argparse.ArgumentParser(description="Ingest dossiers from ZIP/TAR/directory.")
    parser.add_argument(
        "source", type=Path, help="Path to ZIP, TAR, directory, or directory of per-candidate ZIPs."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/staging"),
        help="Staging directory for unpacked archives.",
    )
    args = parser.parse_args()

    if not args.source.exists():
        logger.error("Source not found: {}", args.source)
        sys.exit(1)

    dossiers = ingest(args.source, args.output)
    logger.info("Ingested {} dossiers", len(dossiers))

    valid = sum(1 for d in dossiers if d.documents)
    empty = len(dossiers) - valid
    if empty:
        logger.warning("{} dossiers have no documents", empty)


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    main()
