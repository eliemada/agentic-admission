"""Two-phase dossier PDF → Markdown extraction.

Phase 1 (fast, CPU-only): extract embedded text via PyMuPDF.
Phase 2 (slow, GPU): OCR scanned/image PDFs via RolmOCR on vLLM.

Run standalone
--------------
.. code-block:: bash

    # Phase 1 only — fast text extraction, no GPU needed
    uv run python -m agentic_admission.preprocessing.text_extraction

    # Phase 1 + Phase 2 — also OCR scanned pages via remote VLM
    uv run python -m agentic_admission.preprocessing.text_extraction --backend api

    # Preview what would happen
    uv run python -m agentic_admission.preprocessing.text_extraction --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from agentic_admission.config import settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_INPUT_ROOT = Path("data/processed/dossiers")
_OUTPUT_ROOT = Path("data/processed/texts")

_PROMPT_MARKDOWN = (
    "Convert this page to markdown. Preserve headings, tables, lists, and reading order."
)

# Minimum characters per page to consider a PDF as "text-based".
# Below this threshold, the page is likely scanned/image-only.
_MIN_CHARS_PER_PAGE = 50

# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------


@dataclass
class ExtractionReport:
    """Counts produced by :func:`extract_texts`."""

    total: int = 0
    text_extracted: int = 0
    ocr_extracted: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def converted(self) -> int:
        """Total successfully converted files."""
        return self.text_extracted + self.ocr_extracted


# ---------------------------------------------------------------------------
# Phase 1: Direct text extraction (PyMuPDF)
# ---------------------------------------------------------------------------


def _extract_text_pymupdf(pdf_path: Path) -> str | None:
    """Extract embedded text from a PDF using PyMuPDF.

    Parameters
    ----------
    pdf_path
        Path to the PDF file.

    Returns
    -------
    str | None
        Extracted text if the PDF has enough embedded text, else None
        (indicating the PDF is scanned/image-based and needs OCR).
    """
    import fitz

    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        logger.warning("PyMuPDF failed to open {}", pdf_path)
        return None

    pages_text: list[str] = []
    scanned_pages = 0

    for page in doc:
        text = page.get_text("text").strip()
        if len(text) < _MIN_CHARS_PER_PAGE:
            scanned_pages += 1
        pages_text.append(text)

    doc.close()

    total_pages = len(pages_text)
    if total_pages == 0:
        return None

    # If more than half the pages are scanned, treat the whole PDF as needing OCR
    if scanned_pages > total_pages / 2:
        return None

    full_text = "\n\n---\n\n".join(pages_text)

    # Final sanity check: if the total text is very short, it's probably scanned
    if len(full_text.strip()) < _MIN_CHARS_PER_PAGE:
        return None

    return full_text


def _write_markdown(text: str, output_path: Path) -> None:
    """Write text to a markdown file, creating parent directories."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Phase 2: VLM-based OCR (Docling + RolmOCR)
# ---------------------------------------------------------------------------


def _build_api_converter() -> object:
    """Build a Docling converter using a remote VLM via OpenAI-compatible API.

    Reads ``VLM_BASE_URL`` and ``VLM_MODEL_NAME`` from application settings.

    Returns
    -------
    DocumentConverter
        Configured with VlmPipeline and ApiVlmOptions for remote inference.
    """
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import ApiVlmOptions, ResponseFormat, VlmPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.vlm_pipeline import VlmPipeline
    from pydantic import AnyUrl

    url = settings.vlm_base_url.rstrip("/") + "/chat/completions"
    vlm_options = ApiVlmOptions(
        url=AnyUrl(url),
        params={"model": settings.vlm_model_name, "max_tokens": 2048},
        prompt=_PROMPT_MARKDOWN,
        response_format=ResponseFormat.MARKDOWN,
        timeout=300.0,
    )
    pipeline_options = VlmPipelineOptions(vlm_options=vlm_options, enable_remote_services=True)
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_cls=VlmPipeline, pipeline_options=pipeline_options
            )
        }
    )


def _build_local_converter() -> object:
    """Build a Docling converter using Granite-Docling-258M locally.

    Returns
    -------
    DocumentConverter
        Configured with VlmPipeline and Granite-Docling Transformers preset.
    """
    from docling.datamodel import vlm_model_specs
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import VlmPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.vlm_pipeline import VlmPipeline

    pipeline_options = VlmPipelineOptions(vlm_options=vlm_model_specs.GRANITEDOCLING_TRANSFORMERS)
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_cls=VlmPipeline, pipeline_options=pipeline_options
            )
        }
    )


def _convert_pdf_with_ocr(pdf_path: Path, output_path: Path, converter: object) -> bool:
    """Convert a single PDF to Markdown using a Docling VLM converter.

    Parameters
    ----------
    pdf_path
        Path to the source PDF file.
    output_path
        Path where the Markdown file will be written.
    converter
        A ``DocumentConverter`` instance (local or API-backed).

    Returns
    -------
    bool
        True on success, False on failure.
    """
    try:
        result = converter.convert(str(pdf_path))  # type: ignore[union-attr]
        md_text = result.document.export_to_markdown()
        _write_markdown(md_text, output_path)
        return True
    except Exception:
        logger.exception("OCR failed for {}", pdf_path)
        return False


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _should_skip(pdf_path: Path, md_path: Path) -> bool:
    """Return True if *md_path* exists and is newer than *pdf_path*."""
    if not md_path.exists():
        return False
    return md_path.stat().st_mtime >= pdf_path.stat().st_mtime


def _iter_pdf_paths(src: Path) -> list[Path]:
    """Collect all PDF paths under *src* in sorted order."""
    pdf_paths: list[Path] = []
    for semester_dir in sorted(d for d in src.iterdir() if d.is_dir()):
        for cand_dir in sorted(d for d in semester_dir.iterdir() if d.is_dir()):
            pdf_paths.extend(sorted(cand_dir.rglob("*.pdf")))
    return pdf_paths


def _run_phase1(
    pdf_paths: list[Path],
    src: Path,
    dst: Path,
    *,
    dry_run: bool,
    force: bool,
    report: ExtractionReport,
) -> list[tuple[Path, Path]]:
    """Phase 1: extract embedded text, return list of PDFs needing OCR."""
    ocr_queue: list[tuple[Path, Path]] = []
    logger.info("Phase 1: extracting embedded text with PyMuPDF ...")

    for pdf_path in pdf_paths:
        report.total += 1
        relative = pdf_path.relative_to(src)
        md_path = dst / relative.with_suffix(".md")

        if not force and _should_skip(pdf_path, md_path):
            report.skipped += 1
            continue

        if dry_run:
            report.text_extracted += 1
            continue

        text = _extract_text_pymupdf(pdf_path)
        if text is not None:
            _write_markdown(text, md_path)
            report.text_extracted += 1
        else:
            ocr_queue.append((pdf_path, md_path))

        if report.total % 500 == 0:
            logger.info(
                "Phase 1 progress: {} / {} (text: {}, queued for OCR: {})",
                report.total - report.skipped,
                report.total,
                report.text_extracted,
                len(ocr_queue),
            )

    logger.info(
        "Phase 1 complete: {} text-extracted, {} need OCR, {} skipped (of {} total)",
        report.text_extracted,
        len(ocr_queue),
        report.skipped,
        report.total,
    )
    return ocr_queue


def _run_phase2(
    ocr_queue: list[tuple[Path, Path]],
    *,
    backend: str,
    dry_run: bool,
    report: ExtractionReport,
) -> None:
    """Phase 2: OCR scanned PDFs via Docling VLM backend."""
    if not ocr_queue:
        logger.info("No scanned PDFs found — skipping Phase 2.")
        return

    if backend == "none":
        logger.info("OCR backend is 'none' — skipping {} scanned PDFs.", len(ocr_queue))
        for pdf_path, _ in ocr_queue:
            report.errors.append(f"SKIPPED_OCR: {pdf_path}")
        return

    if dry_run:
        logger.info("[DRY-RUN] Would OCR {} scanned PDFs.", len(ocr_queue))
        return

    logger.info("Phase 2: OCR-ing {} scanned PDFs (backend={}) ...", len(ocr_queue), backend)
    converter = _build_api_converter() if backend == "api" else _build_local_converter()
    logger.info("Converter ready")

    for i, (pdf_path, md_path) in enumerate(ocr_queue, 1):
        t0 = time.perf_counter()
        ok = _convert_pdf_with_ocr(pdf_path, md_path, converter)
        elapsed = time.perf_counter() - t0

        if ok:
            report.ocr_extracted += 1
            logger.debug("OCR converted: {} ({:.1f}s)", pdf_path.name, elapsed)
        else:
            report.errors.append(str(pdf_path))

        if i % 50 == 0:
            logger.info(
                "Phase 2 progress: {}/{} OCR'd ({} errors)",
                i,
                len(ocr_queue),
                len(report.errors),
            )


def extract_texts(
    src: Path,
    dst: Path,
    *,
    backend: str = "local",
    dry_run: bool = False,
    force: bool = False,
) -> ExtractionReport:
    """Two-phase extraction: direct text first, then OCR for scanned PDFs.

    Parameters
    ----------
    src
        Root of the dossier PDF tree (``data/processed/dossiers``).
    dst
        Root of the output Markdown tree (``data/processed/texts``).
    backend
        ``"local"`` for Granite-Docling-258M, ``"api"`` for remote VLM,
        or ``"none"`` to skip OCR entirely (text extraction only).
    dry_run
        If True, log what would happen without writing anything.
    force
        If True, re-extract even if output already exists.

    Returns
    -------
    ExtractionReport
        Summary counts of the extraction run.
    """
    report = ExtractionReport()
    pdf_paths = _iter_pdf_paths(src)
    ocr_queue = _run_phase1(pdf_paths, src, dst, dry_run=dry_run, force=force, report=report)
    _run_phase2(ocr_queue, backend=backend, dry_run=dry_run, report=report)
    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the two-phase text extraction pipeline."""
    parser = argparse.ArgumentParser(
        description="Two-phase PDF text extraction: direct text + OCR for scanned pages."
    )
    parser.add_argument(
        "--input", type=Path, default=_INPUT_ROOT, help="Root directory of normalized dossier PDFs."
    )
    parser.add_argument(
        "--output", type=Path, default=_OUTPUT_ROOT, help="Output directory for Markdown files."
    )
    parser.add_argument(
        "--backend",
        choices=["local", "api", "none"],
        default="none",
        help=(
            "OCR backend for scanned PDFs: 'local' (Granite-Docling-258M), "
            "'api' (remote vLLM), or 'none' (skip OCR, text-only)."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Log what would happen without writing anything."
    )
    parser.add_argument(
        "--force", action="store_true", help="Re-extract even if output already exists."
    )
    args = parser.parse_args()

    if not args.input.exists():
        logger.error("Input root not found: {}", args.input)
        sys.exit(1)

    logger.info("Extracting text from {} -> {} (backend={})", args.input, args.output, args.backend)
    if args.dry_run:
        logger.info("DRY-RUN mode — no files will be written.")

    report = extract_texts(
        args.input, args.output, backend=args.backend, dry_run=args.dry_run, force=args.force
    )

    logger.info(
        "Done: {} total, {} text, {} OCR, {} skipped, {} errors",
        report.total,
        report.text_extracted,
        report.ocr_extracted,
        report.skipped,
        len(report.errors),
    )
    if report.errors:
        for err in report.errors:
            logger.warning("  Error: {}", err)


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    main()
