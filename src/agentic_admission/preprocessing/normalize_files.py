"""Copy dossier files to processed/ with corrected extensions and docx-to-pdf conversion.

Walks ``data/raw/applications/dossiers/``, detects each file's real type via magic
bytes, and copies it to ``data/processed/dossiers/`` with the correct ``.pdf``
extension.  Non-PDF files (e.g. ``.docx``) are converted to PDF via LibreOffice.

Run standalone
--------------
.. code-block:: bash

    uv run python -m agentic_admission.preprocessing.normalize_files            # full run
    uv run python -m agentic_admission.preprocessing.normalize_files --dry-run  # preview only
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DOSSIER_ROOT = Path("data/raw/applications/dossiers")
_OUTPUT_ROOT = Path("data/processed/dossiers")

_MAGIC_TABLE: list[tuple[bytes, str]] = [(b"%PDF", ".pdf"), (b"PK\x03\x04", ".docx")]
# Magic-byte prefixes mapped to file extensions.
# ``PK\x03\x04`` is the ZIP local-file header used by OOXML formats (docx, xlsx, pptx).
# For this dataset only ``.docx`` has been observed.

_MAGIC_READ_SIZE = 8
# Number of bytes to read for magic-byte detection.


# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------


@dataclass
class NormalizationReport:
    """Counts produced by :func:`normalize_dossiers`."""

    total: int = 0
    copied: int = 0
    renamed: int = 0
    converted: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_type(path: Path) -> str:
    """Return the detected extension for *path* based on magic bytes.

    Parameters
    ----------
    path
        File to inspect.

    Returns
    -------
    str
        Detected extension (e.g. ``".pdf"``), or ``""`` if unknown.
    """
    try:
        header = path.read_bytes()[:_MAGIC_READ_SIZE]
    except OSError:
        return ""
    for magic, ext in _MAGIC_TABLE:
        if header.startswith(magic):
            return ext
    return ""


def _fix_filename(original: str, detected_ext: str) -> str:
    """Return *original* with the correct extension based on *detected_ext*.

    Parameters
    ----------
    original
        Original filename (possibly truncated or with a wrong extension).
    detected_ext
        Extension detected from magic bytes (e.g. ``".pdf"``).

    Returns
    -------
    str
        Filename with the correct extension.
    """
    stem = Path(original).stem
    suffix = Path(original).suffix.lower()

    if suffix == detected_ext:
        return original

    # Strip broken/partial suffix and append the correct one.
    return stem + detected_ext


def _convert_to_pdf(src_path: Path, dst_path: Path) -> None:
    """Convert *src_path* to PDF and write the result to *dst_path*.

    Parameters
    ----------
    src_path
        Source file (e.g. a ``.docx``).
    dst_path
        Desired output path (must end in ``.pdf``).

    Raises
    ------
    RuntimeError
        If LibreOffice exits with a non-zero return code.
    """
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "libreoffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(dst_path.parent),
            str(src_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"LibreOffice conversion failed for {src_path}: {result.stderr.strip()}"
        raise RuntimeError(msg)

    # LibreOffice writes <stem>.pdf in outdir — rename if our target name differs.
    lo_output = dst_path.parent / (src_path.stem + ".pdf")
    if lo_output != dst_path and lo_output.exists():
        lo_output.rename(dst_path)


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def _copy_pdf(
    file_path: Path,
    out_path: Path,
    *,
    was_renamed: bool,
    dry_run: bool,
    report: NormalizationReport,
) -> None:
    """Copy a PDF file, optionally fixing its filename."""
    if dry_run:
        action = "RENAME+COPY" if was_renamed else "COPY"
        logger.info("[DRY-RUN] {} {} → {}", action, file_path, out_path)
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, out_path)
    report.copied += 1
    if was_renamed:
        report.renamed += 1


def _convert_non_pdf(
    file_path: Path, out_path: Path, *, dry_run: bool, report: NormalizationReport
) -> None:
    """Convert a non-PDF file to PDF via LibreOffice."""
    if dry_run:
        logger.info("[DRY-RUN] CONVERT {} → {}", file_path, out_path)
    else:
        try:
            _convert_to_pdf(file_path, out_path)
        except RuntimeError:
            logger.exception("Conversion failed: {}", file_path)
            report.errors.append(str(file_path))
            return
    report.converted += 1


def _process_file(
    file_path: Path,
    src: Path,
    dst: Path,
    *,
    convert: bool,
    dry_run: bool,
    report: NormalizationReport,
) -> None:
    """Detect, rename, and copy/convert a single dossier file."""
    report.total += 1
    relative = file_path.relative_to(src)
    detected_ext = _detect_type(file_path)

    if not detected_ext:
        logger.warning("Unknown file type: {}", file_path)
        report.errors.append(str(file_path))
        return

    fixed_name = _fix_filename(file_path.name, detected_ext)
    was_renamed = fixed_name != file_path.name

    if detected_ext == ".pdf":
        out_path = dst / relative.parent / fixed_name
        _copy_pdf(file_path, out_path, was_renamed=was_renamed, dry_run=dry_run, report=report)
    elif convert:
        pdf_name = Path(fixed_name).stem + ".pdf"
        out_path = dst / relative.parent / pdf_name
        _convert_non_pdf(file_path, out_path, dry_run=dry_run, report=report)
    else:
        logger.debug("Skipping non-PDF (convert=False): {}", file_path)
        report.skipped += 1


def normalize_dossiers(
    src: Path, dst: Path, *, convert: bool = True, dry_run: bool = False
) -> NormalizationReport:
    """Walk *src*, detect file types, and copy/convert files to *dst*.

    Parameters
    ----------
    src
        Root of the raw dossier tree (``data/raw/applications/dossiers``).
    dst
        Root of the output tree (``data/processed/dossiers``).
    convert
        If ``True``, convert non-PDF files (e.g. docx) to PDF via LibreOffice.
        If ``False``, skip non-PDF files.
    dry_run
        If ``True``, log what would happen without writing anything.

    Returns
    -------
    NormalizationReport
        Summary counts of the normalization run.
    """
    report = NormalizationReport()

    semester_dirs = sorted(d for d in src.iterdir() if d.is_dir())
    for semester_dir in semester_dirs:
        candidate_dirs = sorted(d for d in semester_dir.iterdir() if d.is_dir())
        for cand_dir in candidate_dirs:
            for file_path in sorted(cand_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                if file_path.suffix.lower() == ".zip":
                    logger.debug("Skipping ZIP: {}", file_path)
                    report.skipped += 1
                    continue
                _process_file(file_path, src, dst, convert=convert, dry_run=dry_run, report=report)

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the dossier normalization pipeline."""
    parser = argparse.ArgumentParser(
        description="Copy dossiers to processed/ with fixed filenames and docx→pdf conversion."
    )
    parser.add_argument(
        "--dossier-root",
        type=Path,
        default=_DOSSIER_ROOT,
        help="Root directory of raw dossier data.",
    )
    parser.add_argument(
        "--output", type=Path, default=_OUTPUT_ROOT, help="Output directory for normalized files."
    )
    parser.add_argument(
        "--no-convert", action="store_true", help="Skip docx→pdf conversion (just copy PDFs)."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Log what would happen without writing anything."
    )
    args = parser.parse_args()

    if not args.dossier_root.exists():
        logger.error("Dossier root not found: {}", args.dossier_root)
        sys.exit(1)

    logger.info("Normalizing dossiers from {} → {}", args.dossier_root, args.output)
    if args.dry_run:
        logger.info("DRY-RUN mode — no files will be written.")

    report = normalize_dossiers(
        args.dossier_root, args.output, convert=not args.no_convert, dry_run=args.dry_run
    )

    logger.info(
        "Done: {} total files, {} copied, {} renamed, {} converted, {} skipped, {} errors",
        report.total,
        report.copied,
        report.renamed,
        report.converted,
        report.skipped,
        len(report.errors),
    )
    if report.errors:
        for err in report.errors:
            logger.warning("  Error: {}", err)


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")
    main()
