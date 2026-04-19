"""Load anonymized dossier texts and prepare inputs for the agent orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyarrow.parquet as pq

if TYPE_CHECKING:
    from pathlib import Path
from loguru import logger
from pydantic import BaseModel

from agentic_admission.intake.matcher import match_dossiers_to_candidates
from agentic_admission.models.candidate import CandidateRecord
from agentic_admission.models.document import DocumentType, classify_document
from agentic_admission.models.dossier import Dossier


class DossierContent(BaseModel, frozen=True):
    """Aggregated text content from one candidate's anonymized dossier.

    Each field maps to an input parameter of ``evaluate_candidate()``.

    Attributes
    ----------
    candidate_id
        Identifier in ``"{semester}_{folder_name}"`` format.
    semester
        Semester directory name.
    folder_name
        Candidate folder name.
    transcript_text
        Concatenated text from all TRANSCRIPT documents.
    letters_text
        Concatenated text from all RECOMMENDATION_LETTER documents.
    motivation_text
        Text from the MOTIVATION_LETTER document.
    cv_text
        Text from the CV document.
    full_dossier_text
        All documents concatenated with type headers.
    school_country
        From matched CandidateRecord (empty if unmatched).
    school_name
        From matched CandidateRecord (empty if unmatched).
    school_quality
        From matched CandidateRecord (empty if unmatched).
    decision_final
        Committee's actual decision (for comparison).
    """

    candidate_id: str
    semester: str
    folder_name: str
    transcript_text: str = ""
    letters_text: str = ""
    motivation_text: str = ""
    cv_text: str = ""
    full_dossier_text: str = ""
    school_country: str = ""
    school_name: str = ""
    school_quality: str = ""
    gpa_threshold: str = ""
    spe_remarks: str = ""
    decision_final: str = ""
    gpa_value: str = ""
    gpa_scale: str = ""
    gpa_normalized: float = 0.0
    gpa_grading_system: str = ""
    gpa_institution: str = ""
    gpa_confidence: float = 0.0


_SECTION_SEPARATOR = "\n\n---\n\n"


def load_anonymized_dossier(candidate_dir: Path, semester: str) -> DossierContent:
    """Read anonymized markdown files from a candidate directory.

    Expected layout::

        candidate_dir/
        ├── 1 - Synthese .../text.md
        ├── 2 - Lettre de motivation .../text.md
        └── ...

    Walks each numbered sub-directory, classifies by name, reads ``text.md``,
    and groups content by ``DocumentType``.

    Parameters
    ----------
    candidate_dir
        Absolute path to a candidate's anonymized folder.
    semester
        The semester name (e.g. ``"2024-25-fall"``).

    Returns
    -------
    DossierContent
        Aggregated text content grouped by document type.
    """
    texts_by_type: dict[DocumentType, list[str]] = {}
    all_sections: list[str] = []

    for entry in sorted(candidate_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        md_files = list(entry.glob("*.md"))
        if not md_files:
            continue

        text_file = md_files[0]
        content = text_file.read_text(encoding="utf-8").strip()
        if not content:
            continue

        doc_type = classify_document(entry.name)
        texts_by_type.setdefault(doc_type, []).append(content)
        all_sections.append(f"## {doc_type.value}\n\n{content}")

    return DossierContent(
        candidate_id=f"{semester}_{candidate_dir.name}",
        semester=semester,
        folder_name=candidate_dir.name,
        transcript_text=_SECTION_SEPARATOR.join(texts_by_type.get(DocumentType.TRANSCRIPT, [])),
        letters_text=_SECTION_SEPARATOR.join(
            texts_by_type.get(DocumentType.RECOMMENDATION_LETTER, []),
        ),
        motivation_text=next(iter(texts_by_type.get(DocumentType.MOTIVATION_LETTER, [])), ""),
        cv_text=next(iter(texts_by_type.get(DocumentType.CV, [])), ""),
        full_dossier_text=_SECTION_SEPARATOR.join(all_sections),
    )


def load_all_anonymized_dossiers(
    anonymized_root: Path, *, limit: int | None = None,
) -> list[DossierContent]:
    """Scan the anonymized root and load all candidate dossiers.

    Parameters
    ----------
    anonymized_root
        Root of anonymized dossier tree (e.g. ``data/processed/anonymized/``).
    limit
        If set, only load the first *limit* candidates (for testing).

    Returns
    -------
    list[DossierContent]
        One entry per candidate with aggregated text content.
    """
    if not anonymized_root.is_dir():
        logger.warning("Anonymized root does not exist: {}", anonymized_root)
        return []

    dossiers: list[DossierContent] = []
    semester_dirs = sorted(d for d in anonymized_root.iterdir() if d.is_dir())

    for semester_dir in semester_dirs:
        semester = semester_dir.name
        candidate_dirs = sorted(d for d in semester_dir.iterdir() if d.is_dir())

        for cand_dir in candidate_dirs:
            if limit is not None and len(dossiers) >= limit:
                logger.info("Reached limit of {} dossiers", limit)
                return dossiers

            dossier = load_anonymized_dossier(cand_dir, semester)
            dossiers.append(dossier)

        logger.debug("Loaded {}: {} candidates", semester, len(candidate_dirs))

    logger.info("Loaded {} anonymized dossiers from {}", len(dossiers), anonymized_root)
    return dossiers


def _load_candidates_from_parquet(parquet_path: Path) -> list[CandidateRecord]:
    """Read candidate records from the Parquet file.

    Parameters
    ----------
    parquet_path
        Path to ``all_candidates.parquet``.

    Returns
    -------
    list[CandidateRecord]
        All candidate records.
    """
    table = pq.read_table(parquet_path)
    rows = table.to_pydict()
    n_rows = table.num_rows

    candidates: list[CandidateRecord] = []
    for i in range(n_rows):
        row = {col: rows[col][i] for col in rows}
        candidates.append(CandidateRecord.model_validate(row))

    logger.info("Loaded {} candidates from {}", len(candidates), parquet_path)
    return candidates


def enrich_with_parquet(dossiers: list[DossierContent], parquet_path: Path) -> list[DossierContent]:
    """Match dossier contents to CandidateRecords and fill in metadata.

    Uses the existing ``intake.matcher`` module to match by name/semester.
    Populates ``school_country``, ``school_name``, ``school_quality``,
    and ``decision_final`` from the matched ``CandidateRecord``.

    Parameters
    ----------
    dossiers
        Loaded dossier contents (from :func:`load_all_anonymized_dossiers`).
    parquet_path
        Path to ``all_candidates.parquet``.

    Returns
    -------
    list[DossierContent]
        Enriched dossiers with metadata from the Parquet.
    """
    candidates = _load_candidates_from_parquet(parquet_path)

    # Build lightweight Dossier objects for the matcher (it only needs
    # semester + folder_name for the index lookup).
    stub_dossiers = [
        Dossier(folder_name=d.folder_name, semester=d.semester, documents=[]) for d in dossiers
    ]

    matched, _unmatched_dossiers, _unmatched_candidates = match_dossiers_to_candidates(
        stub_dossiers, candidates,
    )

    # Build a lookup from (semester, folder_name) → matched CandidateRecord
    match_index: dict[tuple[str, str], CandidateRecord] = {}
    for m in matched:
        if m.candidate is not None:
            match_index[(m.semester, m.folder_name)] = m.candidate

    enriched: list[DossierContent] = []
    matched_count = 0
    for dossier in dossiers:
        candidate = match_index.get((dossier.semester, dossier.folder_name))
        if candidate is not None:
            matched_count += 1
            # Use decision_final if available, otherwise fall back to decision_section
            decision = candidate.decision_final or candidate.decision_section
            enriched.append(
                dossier.model_copy(
                    update={
                        "school_country": candidate.school_country,
                        "school_name": candidate.school_name,
                        "school_quality": candidate.school_quality,
                        "gpa_threshold": candidate.gpa_scale,
                        "spe_remarks": candidate.spe_remarks,
                        "decision_final": decision,
                    },
                ),
            )
        else:
            enriched.append(dossier)

    logger.info("Enriched {}/{} dossiers with Parquet metadata", matched_count, len(dossiers))
    return enriched
