"""PII detection and anonymization using Presidio with GLiNER NER backend.

Uses GLiNER (``knowledgator/gliner-multitask-large-v0.5``) for zero-shot multilingual NER
instead of heavy spaCy NER models. Only ``en_core_web_sm`` (~12 MB) is needed
for tokenization; GLiNER handles all entity recognition across 40+ languages.

Run standalone
--------------
.. code-block:: bash

    uv run python -m agentic_admission.anonymizer.presidio_pipeline              # full run
    uv run python -m agentic_admission.anonymizer.presidio_pipeline --dry-run    # preview
    uv run python -m agentic_admission.anonymizer.presidio_pipeline --sample 5   # test on 5 files
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from agentic_admission.config import settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_INPUT_ROOT = Path("data/processed/texts")
_OUTPUT_ROOT = Path("data/processed/anonymized")

_ENTITY_PLACEHOLDER_MAP: dict[str, str] = {
    "PERSON": "<PERSON>",
    "EMAIL_ADDRESS": "<EMAIL>",
    "PHONE_NUMBER": "<PHONE>",
    "LOCATION": "<LOCATION>",
    "DATE_TIME": "<DATE>",
    "IBAN_CODE": "<IBAN>",
    "CREDIT_CARD": "<PII>",
    "CH_AHV": "<AVS>",
    "EPFL_SCIPER": "<SCIPER>",
    "NRP": "<PII>",
    "URL": "<URL>",
    "IP_ADDRESS": "<PII>",
    "date of birth": "<DOB>",
    "person": "<PERSON>",
    "name": "<PERSON>",
    "address": "<ADDRESS>",
    "email": "<EMAIL>",
    "phone number": "<PHONE>",
    "passport number": "<PII>",
    "PASSPORT": "<PII>",
    "social security number": "<PII>",
    "credit card number": "<PII>",
    "mobile phone number": "<PHONE>",
    "organization": "<ORG>",
}
# Map from Presidio/GLiNER entity types to placeholder strings.

_DEFAULT_PLACEHOLDER = "<PII>"

# Entity types handled by DobYearOperator (preserves birth year).
_DOB_ENTITY_TYPES: frozenset[str] = frozenset({"date of birth"})

# GLiNER entity labels to request (zero-shot — tell it what to find).
_GLINER_ENTITIES = [
    "person",
    "name",
    "organization",
    "phone number",
    "address",
    "email",
    "date of birth",
    "passport number",
    "social security number",
    "credit card number",
    "mobile phone number",
]


# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------


@dataclass
class AnonymizationReport:
    """Counts produced by :func:`anonymize_dossiers`."""

    total_files: int = 0
    anonymized: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    total_pii_found: int = 0
    pii_by_type: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine factories
# ---------------------------------------------------------------------------


def build_analyzer() -> Any:
    """Build a Presidio AnalyzerEngine with GLiNER NER + custom recognizers.

    Returns
    -------
    AnalyzerEngine
        Configured with GLiNER for multilingual zero-shot NER and
        custom recognizers for Swiss AVS/AHV and EPFL SCIPER.
    """
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    from agentic_admission.anonymizer.recognizers import build_custom_recognizers

    # Minimal spaCy model for tokenization only (GLiNER does the NER).
    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
    }
    nlp_engine = NlpEngineProvider(nlp_configuration=nlp_config).create_engine()

    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])

    # Remove default SpacyRecognizer (GLiNER replaces it).
    spacy_recognizer = None
    for rec in analyzer.registry.recognizers:
        if type(rec).__name__ == "SpacyRecognizer":
            spacy_recognizer = rec
            break
    if spacy_recognizer is not None:
        analyzer.registry.remove_recognizer(spacy_recognizer.name)

    # Add GLiNER recognizer.
    try:
        from presidio_analyzer.predefined_recognizers import GLiNERRecognizer

        gliner_recognizer = GLiNERRecognizer(
            model_name=settings.gliner_model,
            supported_entities=_GLINER_ENTITIES,
            supported_language="en",
        )
        analyzer.registry.add_recognizer(gliner_recognizer)
        logger.info("GLiNER recognizer loaded (model={})", settings.gliner_model)
    except ImportError:
        logger.warning("GLiNERRecognizer not available; falling back to built-in recognizers only")

    # Add custom Swiss/EPFL recognizers.
    for recognizer in build_custom_recognizers():
        analyzer.registry.add_recognizer(recognizer)

    return analyzer


def build_anonymizer() -> Any:
    """Build a Presidio AnonymizerEngine with custom operators.

    Registers :class:`~agentic_admission.anonymizer.dob_operator.DobYearOperator`
    so that ``"date of birth"`` entities preserve the birth year.

    Returns
    -------
    AnonymizerEngine
        Ready to anonymize text with operator configs.
    """
    from presidio_anonymizer import AnonymizerEngine

    from agentic_admission.anonymizer.dob_operator import DobYearOperator

    engine = AnonymizerEngine()
    engine.add_anonymizer(DobYearOperator)
    return engine


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _build_operators(entity_types: list[str]) -> dict[str, Any]:
    """Build Presidio operator configs for the detected entity types.

    Parameters
    ----------
    entity_types
        List of entity type strings detected by the analyzer.

    Returns
    -------
    dict[str, OperatorConfig]
        Mapping from entity type to its replacement operator.
    """
    from presidio_anonymizer.entities import OperatorConfig

    operators: dict[str, Any] = {}
    for entity_type in entity_types:
        if entity_type in _DOB_ENTITY_TYPES:
            operators[entity_type] = OperatorConfig("dob_year", {})
        else:
            placeholder = _ENTITY_PLACEHOLDER_MAP.get(entity_type, _DEFAULT_PLACEHOLDER)
            operators[entity_type] = OperatorConfig("replace", {"new_value": placeholder})
    return operators


def _propagate_detected_names(text: str, results: list[Any]) -> list[Any]:
    """Find additional occurrences of already-detected names in *text*.

    When the analyzer detects "Rolla Abi Antoun" at one position, this function
    scans for all other occurrences of "Rolla", "Abi Antoun", and the full name
    elsewhere in the text and creates synthetic results for them.

    Parameters
    ----------
    text
        Full document text.
    results
        Presidio analyzer results from the initial analysis pass.

    Returns
    -------
    list
        Original results plus any new synthetic results for propagated names.
    """
    from agentic_admission.anonymizer.allow_lists import build_allow_list

    _NAME_ENTITY_TYPES = frozenset({"PERSON", "person", "name"})
    _MIN_PROPAGATION_LEN = 3
    _PROPAGATED_SCORE = 0.85

    allow_set = frozenset(w.lower() for w in build_allow_list())

    # Collect existing spans to avoid duplicates.
    existing_spans: set[tuple[int, int]] = {(r.start, r.end) for r in results}

    # Collect unique name parts from detected PERSON/name entities.
    name_parts: set[str] = set()
    for r in results:
        if r.entity_type not in _NAME_ENTITY_TYPES:
            continue
        detected_text = text[r.start : r.end].strip()
        # Add the full name.
        if len(detected_text) >= _MIN_PROPAGATION_LEN:
            name_parts.add(detected_text)
        # Add individual words (e.g., "Rolla", "Antoun" from "Rolla Abi Antoun").
        for word in detected_text.split():
            if len(word) >= _MIN_PROPAGATION_LEN and word.lower() not in allow_set:
                name_parts.add(word)

    if not name_parts:
        return results

    # Scan text for all occurrences of each name part.
    new_results = list(results)
    for part in name_parts:
        pattern = re.compile(re.escape(part), re.IGNORECASE)
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            if (start, end) in existing_spans:
                continue
            # Check word boundary (don't match inside longer words).
            if start > 0 and text[start - 1].isalnum():
                continue
            # Allow possessive 's after the match.
            check_end = end
            if check_end < len(text) and text[check_end] in ("'", "\u2019"):
                # Skip past 's
                if check_end + 1 < len(text) and text[check_end + 1].lower() == "s":
                    check_end += 2
            if check_end < len(text) and text[check_end].isalnum():
                continue

            try:
                from presidio_analyzer import RecognizerResult

                new_result = RecognizerResult(
                    entity_type="PERSON",
                    start=start,
                    end=end,
                    score=_PROPAGATED_SCORE,
                )
            except ImportError:
                # Fallback for test environments without presidio.
                from unittest.mock import MagicMock

                new_result = MagicMock()
                new_result.entity_type = "PERSON"
                new_result.start = start
                new_result.end = end
                new_result.score = _PROPAGATED_SCORE

            new_results.append(new_result)
            existing_spans.add((start, end))

    return new_results


def _inject_candidate_name(
    text: str, candidate_name: str, existing_results: list[Any]
) -> list[Any]:
    """Inject the candidate name from folder metadata as PII to redact.

    Extracts name parts from the folder name (e.g. ``jaramillo_velez`` →
    ``["jaramillo", "velez"]``), generates casing variants, and creates
    synthetic ``RecognizerResult`` objects for every occurrence in *text*.

    Parameters
    ----------
    text
        Full document text.
    candidate_name
        Candidate folder name (underscore-separated, e.g. ``jaramillo_velez``).
    existing_results
        Results from the analyzer pass (used to avoid duplicate spans).

    Returns
    -------
    list
        Original results plus synthetic results for the candidate name.
    """
    from agentic_admission.anonymizer.allow_lists import build_allow_list

    _INJECTED_SCORE = 0.95
    _MIN_NAME_LEN = 3

    allow_set = frozenset(w.lower() for w in build_allow_list())
    existing_spans: set[tuple[int, int]] = {(r.start, r.end) for r in existing_results}
    new_results = list(existing_results)

    # Split folder name into name parts: "garcia_de_la_fuente" → ["garcia", "fuente"]
    raw_parts = candidate_name.replace("-", "_").split("_")
    name_parts: set[str] = set()
    for part in raw_parts:
        if len(part) >= _MIN_NAME_LEN and part.lower() not in allow_set:
            name_parts.add(part)

    # Also try the full name joined with spaces for multi-word matches.
    full_name = " ".join(raw_parts)
    if len(full_name) >= _MIN_NAME_LEN:
        name_parts.add(full_name)

    for part in name_parts:
        pattern = re.compile(re.escape(part), re.IGNORECASE)
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            if (start, end) in existing_spans:
                continue
            # Word boundary checks.
            if start > 0 and text[start - 1].isalnum():
                continue
            if end < len(text) and text[end].isalnum():
                continue

            try:
                from presidio_analyzer import RecognizerResult

                result = RecognizerResult(
                    entity_type="PERSON",
                    start=start,
                    end=end,
                    score=_INJECTED_SCORE,
                )
            except ImportError:
                from unittest.mock import MagicMock

                result = MagicMock()
                result.entity_type = "PERSON"
                result.start = start
                result.end = end
                result.score = _INJECTED_SCORE

            new_results.append(result)
            existing_spans.add((start, end))

    return new_results


def anonymize_text(
    text: str,
    analyzer: Any,
    anonymizer: Any,
    *,
    candidate_name: str | None = None,
    score_threshold: float | None = None,
    allow_list: list[str] | None = None,
    filter_pipeline: list[Any] | None = None,
) -> tuple[str, dict[str, int]]:
    """Detect and replace PII in *text*.

    Parameters
    ----------
    text
        Raw text to anonymize.
    analyzer
        A ``PresidioAnalyzerEngine`` instance.
    anonymizer
        A ``PresidioAnonymizerEngine`` instance.
    candidate_name
        Candidate folder name (e.g. ``jaramillo_velez``).  When provided,
        all occurrences of name parts are forcibly redacted regardless of
        NER confidence.
    score_threshold
        Minimum confidence for PII detection. Defaults to settings value.
    allow_list
        Terms to never flag as PII. Defaults to domain allow-list
        from :func:`~agentic_admission.anonymizer.allow_lists.build_allow_list`.
    filter_pipeline
        Post-analysis filter functions. Defaults to the standard pipeline
        from :func:`~agentic_admission.anonymizer.post_filters.build_filter_pipeline`.

    Returns
    -------
    tuple[str, dict[str, int]]
        (anonymized_text, entity_counts) where entity_counts maps
        entity type names to the number of occurrences found.
    """
    from agentic_admission.anonymizer.allow_lists import build_allow_list
    from agentic_admission.anonymizer.post_filters import apply_filters, build_filter_pipeline

    threshold = (
        score_threshold if score_threshold is not None else settings.presidio_score_threshold
    )

    effective_allow_list = allow_list if allow_list is not None else build_allow_list()

    results = analyzer.analyze(
        text=text, language="en", score_threshold=threshold, allow_list=effective_allow_list
    )

    # Inject candidate name from folder metadata BEFORE propagation.
    if candidate_name:
        results = _inject_candidate_name(text, candidate_name, results)

    if not results:
        return text, {}

    # Propagate detected names to catch all occurrences in the document.
    results = _propagate_detected_names(text, results)

    # Apply post-analysis filters to reduce false positives.
    effective_filters = filter_pipeline if filter_pipeline is not None else build_filter_pipeline()
    results = apply_filters(text, results, effective_filters)

    if not results:
        return text, {}

    entity_types = list({r.entity_type for r in results})
    operators = _build_operators(entity_types)

    anonymized = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)

    counts: dict[str, int] = {}
    for r in results:
        counts[r.entity_type] = counts.get(r.entity_type, 0) + 1

    return anonymized.text, counts


def _extract_candidate_name(file_path: Path) -> str | None:
    """Extract the candidate folder name from a dossier file path.

    Expects paths like ``texts/2024-25-spring/jaramillo_velez/9 - .../file.md``.
    The candidate name is the directory two levels above the file.
    """
    # parts: [..., semester, candidate, doc_folder, filename]
    parts = file_path.parts
    if len(parts) >= 4:  # noqa: PLR2004
        return parts[-3]
    return None


def anonymize_file(
    input_path: Path, output_path: Path, analyzer: Any, anonymizer: Any
) -> dict[str, int]:
    """Read a Markdown file, anonymize it, and write the result.

    Parameters
    ----------
    input_path
        Path to the source Markdown file.
    output_path
        Path where the anonymized file will be written.
    analyzer
        A ``PresidioAnalyzerEngine`` instance.
    anonymizer
        A ``PresidioAnonymizerEngine`` instance.

    Returns
    -------
    dict[str, int]
        Entity type counts found in this file.
    """
    text = input_path.read_text(encoding="utf-8")

    if not text.strip():
        return {}

    candidate_name = _extract_candidate_name(input_path)
    anon_text, counts = anonymize_text(text, analyzer, anonymizer, candidate_name=candidate_name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(anon_text, encoding="utf-8")

    return counts


def _hash_name(name: str) -> str:
    """Return a short deterministic hash for a name string."""
    return hashlib.sha256(name.encode()).hexdigest()[:12]


def _anonymize_path(relative: Path) -> Path:
    """Replace candidate name and filename PII with hashes.

    Input:  ``2024-25-spring/jaramillo_velez/9 - Doc_F123/CV_Simon.md``
    Output: ``2024-25-spring/a1b2c3d4e5f6/9 - Doc_F123/a1b2c3d4e5f6.md``

    The semester is kept as-is.  The candidate folder is hashed.
    The document subfolder is kept (contains no PII --- only doc type + hash).
    The filename is hashed (often contains the candidate name).
    """
    parts = list(relative.parts)
    if len(parts) >= 2:  # noqa: PLR2004
        # parts[0] = semester, parts[1] = candidate folder
        parts[1] = _hash_name(parts[1])
    if len(parts) >= 1:
        # Hash the filename (preserve .md extension)
        stem = Path(parts[-1]).stem
        parts[-1] = _hash_name(stem) + ".md"
    return Path(*parts)


def _should_skip(src_path: Path, dst_path: Path) -> bool:
    """Return True if *dst_path* exists and is newer than *src_path*."""
    if not dst_path.exists():
        return False
    return dst_path.stat().st_mtime >= src_path.stat().st_mtime


def _collect_md_files(src: Path) -> list[Path]:
    """Walk *src* and return all ``.md`` files in semester/candidate order."""
    files: list[Path] = []
    semester_dirs = sorted(d for d in src.iterdir() if d.is_dir())
    for semester_dir in semester_dirs:
        candidate_dirs = sorted(d for d in semester_dir.iterdir() if d.is_dir())
        for cand_dir in candidate_dirs:
            files.extend(sorted(cand_dir.rglob("*.md")))
    return files


def _process_single_file(
    md_path: Path, out_path: Path, analyzer: Any, anonymizer: Any, report: AnonymizationReport
) -> None:
    """Anonymize one file and update *report* in place."""
    try:
        counts = anonymize_file(md_path, out_path, analyzer, anonymizer)
        report.anonymized += 1
        for entity_type, count in counts.items():
            report.pii_by_type[entity_type] = report.pii_by_type.get(entity_type, 0) + count
            report.total_pii_found += count
        logger.debug("Anonymized {} (PII: {})", md_path.name, counts)
    except Exception:
        logger.exception("Failed to anonymize {}", md_path)
        report.errors.append(str(md_path))


def anonymize_dossiers(
    src: Path, dst: Path, *, dry_run: bool = False, force: bool = False, sample: int | None = None
) -> AnonymizationReport:
    """Walk *src*, anonymize each Markdown file, and write to *dst*.

    Parameters
    ----------
    src
        Root of the extracted text tree (``data/processed/texts``).
    dst
        Root of the output tree (``data/processed/anonymized``).
    dry_run
        If True, log what would happen without writing anything.
    force
        If True, re-anonymize even if output already exists.
    sample
        If set, process only this many files (for testing).

    Returns
    -------
    AnonymizationReport
        Summary counts of the anonymization run.
    """
    report = AnonymizationReport()

    analyzer = None
    anonymizer = None
    if not dry_run:
        logger.info("Building Presidio engines (GLiNER + custom recognizers)")
        analyzer = build_analyzer()
        anonymizer = build_anonymizer()
        logger.info("Engines ready")

    md_files = _collect_md_files(src)
    if sample is not None:
        md_files = md_files[:sample]

    # Mapping from hashed paths to original paths (for traceability).
    path_mapping: dict[str, str] = {}

    for md_path in md_files:
        report.total_files += 1
        relative = md_path.relative_to(src)
        anon_relative = _anonymize_path(relative)
        out_path = dst / anon_relative

        path_mapping[str(anon_relative)] = str(relative)

        if not force and _should_skip(md_path, out_path):
            report.skipped += 1
            continue

        if dry_run:
            logger.info("[DRY-RUN] ANONYMIZE {} -> {}", md_path, out_path)
            report.anonymized += 1
            continue

        _process_single_file(md_path, out_path, analyzer, anonymizer, report)

        if report.total_files % 100 == 0:
            logger.info(
                "Progress: {}/{} files ({} PII found, {} errors)",
                report.anonymized,
                report.total_files,
                report.total_pii_found,
                len(report.errors),
            )

    # Write path mapping as Parquet (gitignored — contains original names).
    import pyarrow as pa
    import pyarrow.parquet as pq

    mapping_table = pa.table({
        "anonymized_path": list(path_mapping.keys()),
        "original_path": list(path_mapping.values()),
    })
    mapping_path = dst / "path_mapping.parquet"
    pq.write_table(mapping_table, mapping_path)
    logger.info("Path mapping written to {} ({} entries)", mapping_path, len(path_mapping))

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the PII anonymization pipeline."""
    parser = argparse.ArgumentParser(
        description="Detect and redact PII from extracted Markdown files."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=_INPUT_ROOT,
        help="Root directory of extracted Markdown files.",
    )
    parser.add_argument(
        "--output", type=Path, default=_OUTPUT_ROOT, help="Output directory for anonymized files."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Log what would happen without writing anything."
    )
    parser.add_argument(
        "--force", action="store_true", help="Re-anonymize even if output already exists."
    )
    parser.add_argument(
        "--sample", type=int, default=None, help="Process only this many files (for testing)."
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=None,
        help="Minimum confidence threshold (default: from .env).",
    )
    args = parser.parse_args()

    if not args.input.exists():
        logger.error("Input root not found: {}", args.input)
        sys.exit(1)

    if args.confidence is not None:
        settings.presidio_score_threshold = args.confidence

    logger.info("Anonymizing PII from {} -> {}", args.input, args.output)
    if args.dry_run:
        logger.info("DRY-RUN mode — no files will be written.")

    report = anonymize_dossiers(
        args.input, args.output, dry_run=args.dry_run, force=args.force, sample=args.sample
    )

    logger.info(
        "Done: {} total, {} anonymized, {} skipped, {} errors, {} PII entities found",
        report.total_files,
        report.anonymized,
        report.skipped,
        len(report.errors),
        report.total_pii_found,
    )
    if report.pii_by_type:
        logger.info("PII breakdown:")
        for entity_type, count in sorted(report.pii_by_type.items(), key=lambda x: -x[1]):
            logger.info("  {}: {}", entity_type, count)
    if report.errors:
        for err in report.errors:
            logger.warning("  Error: {}", err)


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    main()
