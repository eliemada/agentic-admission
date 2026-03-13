"""Pre-screening triage: flag incomplete dossiers for auto-rejection.

Dossiers missing critical documents (CV, motivation letter, transcript) are
recommended for automatic rejection.  The downstream agent panel *may*
override this if the available documents show exceptional quality, but the
default is reject-first.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agentic_admission.models.document import DocumentType
from agentic_admission.models.dossier import Dossier

# ---------------------------------------------------------------------------
# Document importance tiers
# ---------------------------------------------------------------------------

# Missing any of these → auto-reject recommendation.
CRITICAL_DOCUMENTS: frozenset[DocumentType] = frozenset(
    {DocumentType.CV, DocumentType.MOTIVATION_LETTER, DocumentType.TRANSCRIPT}
)

# Nice to have; missing ones are noted but don't trigger rejection.
EXPECTED_DOCUMENTS: frozenset[DocumentType] = frozenset(
    {DocumentType.APPLICATION_SUMMARY, DocumentType.RECOMMENDATION_LETTER}
)

_ALL_SCORED = CRITICAL_DOCUMENTS | EXPECTED_DOCUMENTS


# ---------------------------------------------------------------------------
# Triage result
# ---------------------------------------------------------------------------


class TriageVerdict(Enum):
    """Pre-screening outcome for a dossier."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    EMPTY = "empty"


@dataclass(frozen=True)
class TriageResult:
    """Triage outcome for a single dossier.

    Attributes
    ----------
    folder_name
        Candidate folder name.
    semester
        Semester directory name.
    verdict
        Overall triage verdict.
    auto_reject
        ``True`` if the dossier should be auto-rejected (missing critical
        documents or empty).  The agent panel may override this.
    reason
        Human-readable explanation of the verdict.
    missing_critical
        Critical document types that are absent.
    missing_expected
        Expected (but non-critical) document types that are absent.
    completeness
        Fraction of scored documents present (0.0-1.0).
    """

    folder_name: str
    semester: str
    verdict: TriageVerdict
    auto_reject: bool
    reason: str
    missing_critical: tuple[DocumentType, ...] = ()
    missing_expected: tuple[DocumentType, ...] = ()
    completeness: float = 0.0


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def triage_dossier(dossier: Dossier) -> TriageResult:
    """Screen a dossier for completeness and return a triage decision.

    Parameters
    ----------
    dossier
        The dossier to screen.

    Returns
    -------
    TriageResult
        Triage outcome with auto-reject recommendation.
    """
    present_types = frozenset(d.document_type for d in dossier.documents)

    if not dossier.documents:
        return TriageResult(
            folder_name=dossier.folder_name,
            semester=dossier.semester,
            verdict=TriageVerdict.EMPTY,
            auto_reject=True,
            reason="No documents found — auto-reject",
            completeness=0.0,
        )

    missing_crit = tuple(
        sorted((dt for dt in CRITICAL_DOCUMENTS if dt not in present_types), key=lambda d: d.value)
    )
    missing_exp = tuple(
        sorted((dt for dt in EXPECTED_DOCUMENTS if dt not in present_types), key=lambda d: d.value)
    )

    scored_present = sum(1 for dt in _ALL_SCORED if dt in present_types)
    completeness = scored_present / len(_ALL_SCORED)

    if missing_crit:
        names = ", ".join(dt.value for dt in missing_crit)
        return TriageResult(
            folder_name=dossier.folder_name,
            semester=dossier.semester,
            verdict=TriageVerdict.INCOMPLETE,
            auto_reject=True,
            reason=f"Missing critical documents: {names} — auto-reject unless overridden",
            missing_critical=missing_crit,
            missing_expected=missing_exp,
            completeness=completeness,
        )

    return TriageResult(
        folder_name=dossier.folder_name,
        semester=dossier.semester,
        verdict=TriageVerdict.COMPLETE,
        auto_reject=False,
        reason="All critical documents present",
        missing_critical=(),
        missing_expected=missing_exp,
        completeness=completeness,
    )


def triage_batch(dossiers: list[Dossier]) -> list[TriageResult]:
    """Screen a list of dossiers.

    Parameters
    ----------
    dossiers
        Dossiers to screen.

    Returns
    -------
    list[TriageResult]
        One result per dossier.
    """
    return [triage_dossier(d) for d in dossiers]
