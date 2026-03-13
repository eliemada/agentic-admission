"""Dossier model linking a candidate's structured record to their document files."""

from __future__ import annotations

from enum import IntEnum

from pydantic import BaseModel

from agentic_admission.models.candidate import CandidateRecord
from agentic_admission.models.document import DocumentType, DossierDocument


class ProcessingStage(IntEnum):
    """Processing stages a dossier progresses through.

    Integer values encode ordering so that ``stage_a < stage_b`` reflects
    the pipeline sequence.
    """

    RAW = 0
    NORMALIZED = 1
    EXTRACTED = 2
    ANONYMIZED = 3
    EVALUATED = 4


class Dossier(BaseModel):
    """A candidate dossier: the folder of documents plus optional structured record.

    Attributes
    ----------
    folder_name
        Name of the candidate's folder on disk (e.g. ``"akiki"``).
    semester
        Semester directory name (e.g. ``"2024-25-fall"``).
    documents
        Classified documents found in the folder.
    candidate
        Matched ``CandidateRecord`` from the Parquet, or ``None`` if unmatched.
    stage
        Current processing stage of this dossier.
    """

    folder_name: str
    semester: str
    documents: list[DossierDocument]
    candidate: CandidateRecord | None = None
    stage: ProcessingStage = ProcessingStage.RAW

    def has_document(self, doc_type: DocumentType) -> bool:
        """Return ``True`` if the dossier contains at least one document of *doc_type*."""
        return any(d.document_type == doc_type for d in self.documents)

    def documents_by_type(self, doc_type: DocumentType) -> list[DossierDocument]:
        """Return all documents matching *doc_type*."""
        return [d for d in self.documents if d.document_type == doc_type]
