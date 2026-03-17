"""Convert dossier PDFs to structured Markdown using Docling.

Supports two VLM backends controlled by ``--backend``:

- ``local`` (default): Granite-Docling-258M via HuggingFace Transformers (CPU, no setup).
- ``api``: Remote VLM (e.g. Qwen3-VL) via an OpenAI-compatible API such as vLLM.
  Configured through ``VLM_BASE_URL`` and ``VLM_MODEL_NAME`` in ``.env``.

Run standalone
--------------
.. code-block:: bash

    uv run python -m agentic_admission.preprocessing.text_extraction                    # local
    uv run python -m agentic_admission.preprocessing.text_extraction --backend api      # vLLM
    uv run python -m agentic_admission.preprocessing.text_extraction --dry-run           # preview
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

# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------


@dataclass
class ExtractionReport:
    """Counts produced by :func:`extract_texts`."""

    total: int = 0
    converted: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Converter factories
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _should_skip(pdf_path: Path, md_path: Path) -> bool:
    """Return True if *md_path* exists and is newer than *pdf_path*."""
    if not md_path.exists():
        return False
    return md_path.stat().st_mtime >= pdf_path.stat().st_mtime


def convert_pdf_to_markdown(pdf_path: Path, output_path: Path, converter: object) -> bool:
    """Convert a single PDF to Markdown using the given Docling converter.

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

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md_text, encoding="utf-8")
        return True
    except Exception:
        logger.exception("Failed to convert {}", pdf_path)
        return False


def extract_texts(
    src: Path, dst: Path, *, backend: str = "local", dry_run: bool = False, force: bool = False
) -> ExtractionReport:
    """Walk *src*, convert each PDF to Markdown, and write to *dst*.

    Parameters
    ----------
    src
        Root of the dossier PDF tree (``data/processed/dossiers``).
    dst
        Root of the output Markdown tree (``data/processed/texts``).
    backend
        ``"local"`` for Granite-Docling-258M or ``"api"`` for remote VLM.
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

    converter = None
    if not dry_run:
        logger.info("Building Docling converter (backend={})", backend)
        converter = _build_api_converter() if backend == "api" else _build_local_converter()
        logger.info("Converter ready")

    semester_dirs = sorted(d for d in src.iterdir() if d.is_dir())
    for semester_dir in semester_dirs:
        candidate_dirs = sorted(d for d in semester_dir.iterdir() if d.is_dir())
        for cand_dir in candidate_dirs:
            for pdf_path in sorted(cand_dir.rglob("*.pdf")):
                report.total += 1
                relative = pdf_path.relative_to(src)
                md_path = dst / relative.with_suffix(".md")

                if not force and _should_skip(pdf_path, md_path):
                    report.skipped += 1
                    continue

                if dry_run:
                    logger.info("[DRY-RUN] CONVERT {} -> {}", pdf_path, md_path)
                    report.converted += 1
                    continue

                t0 = time.perf_counter()
                ok = convert_pdf_to_markdown(pdf_path, md_path, converter)
                elapsed = time.perf_counter() - t0

                if ok:
                    report.converted += 1
                    logger.debug("Converted {} ({:.1f}s)", relative, elapsed)
                else:
                    report.errors.append(str(pdf_path))

                if report.total % 100 == 0:
                    logger.info(
                        "Progress: {}/{} files processed ({} errors)",
                        report.converted + len(report.errors),
                        report.total,
                        len(report.errors),
                    )

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the text extraction pipeline."""
    parser = argparse.ArgumentParser(description="Convert dossier PDFs to Markdown using Docling.")
    parser.add_argument(
        "--input", type=Path, default=_INPUT_ROOT, help="Root directory of normalized dossier PDFs."
    )
    parser.add_argument(
        "--output", type=Path, default=_OUTPUT_ROOT, help="Output directory for Markdown files."
    )
    parser.add_argument(
        "--backend",
        choices=["local", "api"],
        default="local",
        help="VLM backend: 'local' (Granite-Docling-258M) or 'api' (remote vLLM).",
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
        "Done: {} total, {} converted, {} skipped, {} errors",
        report.total,
        report.converted,
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
