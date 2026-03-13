"""Document type classification and dossier document model."""

from __future__ import annotations

import re
from enum import Enum
from pathlib import PurePosixPath  # noqa: TC003 — Pydantic needs this at runtime

from pydantic import BaseModel


class DocumentType(Enum):
    """Known document types within a candidate dossier.

    Numbers in comments refer to the typical ordering prefix in folder names.
    """

    APPLICATION_SUMMARY = "application_summary"  # 1 - Synthese de la candidature
    MOTIVATION_LETTER = "motivation_letter"  # 2 - Lettre de motivation
    RECOMMENDATION_LETTER = "recommendation_letter"  # 3,5,7 - Referent Lettre de recommandation
    REFERENT_SUMMARY = "referent_summary"  # 4,6,8 - Referent Synthese
    TRANSCRIPT = "transcript"  # 9,10 - Releve de notes
    DIPLOMA = "diploma"  # 8,9 - Diplome institution
    CV = "cv"  # 11 - CV
    LANGUAGE_CERTIFICATE = "language_certificate"  # 12 - Certificat linguistique (TOEFL)
    GRE_RESULTS = "gre_results"  # 13 - Resultats GRE
    OTHER = "other"  # 13 - Autres documents
    UNKNOWN = "unknown"  # Unrecognized filename


# Ordered rules: first match wins.  Patterns are matched case-insensitively
# against the folder/file name (the numbered prefix line).
_CLASSIFICATION_RULES: list[tuple[re.Pattern[str], DocumentType]] = [
    (
        re.compile(r"synth(?:e|è)se de la candidature", re.IGNORECASE),
        DocumentType.APPLICATION_SUMMARY,
    ),
    (re.compile(r"lettre de motivation", re.IGNORECASE), DocumentType.MOTIVATION_LETTER),
    (
        re.compile(r"referent.*lettre de recommandation", re.IGNORECASE),
        DocumentType.RECOMMENDATION_LETTER,
    ),
    (re.compile(r"referent.*synth(?:e|è)se", re.IGNORECASE), DocumentType.REFERENT_SUMMARY),
    (re.compile(r"relev(?:e|é) de notes", re.IGNORECASE), DocumentType.TRANSCRIPT),
    (re.compile(r"dipl(?:o|ô)me", re.IGNORECASE), DocumentType.DIPLOMA),
    (re.compile(r"\bCV[\b_]|^CV$", re.IGNORECASE), DocumentType.CV),
    (
        re.compile(r"certificat linguistique|toefl", re.IGNORECASE),
        DocumentType.LANGUAGE_CERTIFICATE,
    ),
    (re.compile(r"r(?:e|é)sultats?\s*GRE", re.IGNORECASE), DocumentType.GRE_RESULTS),
    (re.compile(r"autres documents", re.IGNORECASE), DocumentType.OTHER),
]

_NUMBER_PREFIX = re.compile(r"^(\d+)\s*-\s*")


def classify_document(name: str) -> DocumentType:
    """Classify a document folder/file name into a ``DocumentType``.

    Parameters
    ----------
    name
        The folder or file name (e.g.
        ``"3 - Cand. Master Referent #1 Lettre de recommandation_F909725189"``).

    Returns
    -------
    DocumentType
        The detected type, or ``UNKNOWN`` if no rule matched.
    """
    for pattern, doc_type in _CLASSIFICATION_RULES:
        if pattern.search(name):
            return doc_type
    return DocumentType.UNKNOWN


def parse_document_number(name: str) -> int | None:
    """Extract the leading number from a document folder name.

    Parameters
    ----------
    name
        Folder/file name, e.g. ``"3 - Cand. Master ..."``

    Returns
    -------
    int | None
        The number prefix, or None if not present.
    """
    m = _NUMBER_PREFIX.match(name)
    return int(m.group(1)) if m else None


class DossierDocument(BaseModel, frozen=True):
    """A single document within a candidate dossier.

    Attributes
    ----------
    path
        Relative path from the dossier root to this document's folder or file.
    document_type
        Classified type of the document.
    number
        The ordering number from the folder prefix (e.g. 3 for recommendation #1).
    """

    path: PurePosixPath
    document_type: DocumentType
    number: int | None = None
