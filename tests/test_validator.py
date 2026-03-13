"""Tests for dossier pre-screening / triage validation."""

from __future__ import annotations

from pathlib import PurePosixPath

from agentic_admission.intake.validator import TriageVerdict, triage_batch, triage_dossier
from agentic_admission.models.document import DocumentType, DossierDocument
from agentic_admission.models.dossier import Dossier


def _doc(doc_type: DocumentType, number: int | None = None) -> DossierDocument:
    return DossierDocument(
        path=PurePosixPath(f"sem/cand/{number or 0}"),
        document_type=doc_type,
        number=number,
    )


def _full_dossier(folder: str = "akiki") -> Dossier:
    """A dossier with all critical + expected documents."""
    return Dossier(
        folder_name=folder,
        semester="2024-25-fall",
        documents=[
            _doc(DocumentType.APPLICATION_SUMMARY, 1),
            _doc(DocumentType.MOTIVATION_LETTER, 2),
            _doc(DocumentType.RECOMMENDATION_LETTER, 3),
            _doc(DocumentType.TRANSCRIPT, 9),
            _doc(DocumentType.CV, 11),
        ],
    )


# ---------------------------------------------------------------------------
# COMPLETE — all critical docs present
# ---------------------------------------------------------------------------


class TestTriageComplete:
    def test_full_dossier_is_complete(self) -> None:
        result = triage_dossier(_full_dossier())
        assert result.verdict == TriageVerdict.COMPLETE
        assert result.missing_critical == ()
        assert result.missing_expected == ()

    def test_critical_only_is_complete(self) -> None:
        """Having all critical docs but missing optional ones → still COMPLETE."""
        dossier = Dossier(
            folder_name="akiki",
            semester="2024-25-fall",
            documents=[
                _doc(DocumentType.MOTIVATION_LETTER, 2),
                _doc(DocumentType.TRANSCRIPT, 9),
                _doc(DocumentType.CV, 11),
            ],
        )
        result = triage_dossier(dossier)
        assert result.verdict == TriageVerdict.COMPLETE


# ---------------------------------------------------------------------------
# INCOMPLETE — missing critical docs → auto-reject recommendation
# ---------------------------------------------------------------------------


class TestTriageIncomplete:
    def test_missing_cv_is_incomplete(self) -> None:
        dossier = Dossier(
            folder_name="akiki",
            semester="2024-25-fall",
            documents=[
                _doc(DocumentType.MOTIVATION_LETTER, 2),
                _doc(DocumentType.TRANSCRIPT, 9),
            ],
        )
        result = triage_dossier(dossier)
        assert result.verdict == TriageVerdict.INCOMPLETE
        assert DocumentType.CV in result.missing_critical

    def test_missing_transcript_is_incomplete(self) -> None:
        dossier = Dossier(
            folder_name="akiki",
            semester="2024-25-fall",
            documents=[
                _doc(DocumentType.MOTIVATION_LETTER, 2),
                _doc(DocumentType.CV, 11),
            ],
        )
        result = triage_dossier(dossier)
        assert result.verdict == TriageVerdict.INCOMPLETE
        assert DocumentType.TRANSCRIPT in result.missing_critical

    def test_missing_motivation_is_incomplete(self) -> None:
        dossier = Dossier(
            folder_name="akiki",
            semester="2024-25-fall",
            documents=[
                _doc(DocumentType.CV, 11),
                _doc(DocumentType.TRANSCRIPT, 9),
            ],
        )
        result = triage_dossier(dossier)
        assert result.verdict == TriageVerdict.INCOMPLETE
        assert DocumentType.MOTIVATION_LETTER in result.missing_critical

    def test_missing_multiple_critical(self) -> None:
        dossier = Dossier(
            folder_name="akiki",
            semester="2024-25-fall",
            documents=[_doc(DocumentType.APPLICATION_SUMMARY, 1)],
        )
        result = triage_dossier(dossier)
        assert result.verdict == TriageVerdict.INCOMPLETE
        assert len(result.missing_critical) == 3

    def test_auto_reject_reason_present(self) -> None:
        dossier = Dossier(
            folder_name="akiki",
            semester="2024-25-fall",
            documents=[_doc(DocumentType.TRANSCRIPT, 9)],
        )
        result = triage_dossier(dossier)
        assert result.auto_reject
        assert "missing" in result.reason.lower()


# ---------------------------------------------------------------------------
# EMPTY — no documents at all
# ---------------------------------------------------------------------------


class TestTriageEmpty:
    def test_no_documents(self) -> None:
        dossier = Dossier(folder_name="akiki", semester="2024-25-fall", documents=[])
        result = triage_dossier(dossier)
        assert result.verdict == TriageVerdict.EMPTY
        assert result.auto_reject

    def test_only_unknown_docs(self) -> None:
        dossier = Dossier(
            folder_name="akiki",
            semester="2024-25-fall",
            documents=[_doc(DocumentType.UNKNOWN, 99)],
        )
        result = triage_dossier(dossier)
        assert result.verdict == TriageVerdict.INCOMPLETE
        assert result.auto_reject


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestTriageMetadata:
    def test_result_carries_identity(self) -> None:
        result = triage_dossier(_full_dossier("benchetrite"))
        assert result.folder_name == "benchetrite"
        assert result.semester == "2024-25-fall"

    def test_completeness_score(self) -> None:
        result = triage_dossier(_full_dossier())
        assert result.completeness == 1.0

    def test_partial_completeness(self) -> None:
        dossier = Dossier(
            folder_name="akiki",
            semester="2024-25-fall",
            documents=[_doc(DocumentType.CV, 11)],
        )
        result = triage_dossier(dossier)
        assert 0.0 < result.completeness < 1.0


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------


class TestTriageBatch:
    def test_batch_returns_one_per_dossier(self) -> None:
        dossiers = [_full_dossier("a"), Dossier(folder_name="b", semester="s", documents=[])]
        results = triage_batch(dossiers)
        assert len(results) == 2
        assert results[0].verdict == TriageVerdict.COMPLETE
        assert results[1].verdict == TriageVerdict.EMPTY

    def test_batch_counts(self) -> None:
        dossiers = [
            _full_dossier("a"),
            _full_dossier("b"),
            Dossier(folder_name="c", semester="s", documents=[]),
            Dossier(
                folder_name="d",
                semester="s",
                documents=[_doc(DocumentType.CV, 11)],
            ),
        ]
        results = triage_batch(dossiers)
        complete = sum(1 for r in results if r.verdict == TriageVerdict.COMPLETE)
        rejected = sum(1 for r in results if r.auto_reject)
        assert complete == 2
        assert rejected == 2
