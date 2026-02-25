"""Pydantic model for a normalized candidate application record."""

from __future__ import annotations

from pydantic import BaseModel


class CandidateRecord(BaseModel):
    """A single MTE admission candidate, normalized across all source files.

    Each record represents one candidate with their academic profile,
    committee evaluations (merged from multiple reviewers), and aggregate
    decisions.

    Attributes
    ----------
    source_file : str
        Original filename (e.g. ``mte_applications_2023-24_round1.xlsx``).
    academic_year : str
        Academic year extracted from filename (e.g. ``2023-24``).
    admission_round : str
        Round identifier (e.g. ``round1``, ``round2``).
    candidate_number : int | None
        Row number in the original Excel sheet.
    name : str
        Full name (Nom Prénom).  Will be anonymized downstream.
    school_country : str
        Country of the applicant's institution.
    school_name : str
        Name of the institution of origin.
    school_quality : str
        Quality rating (A=priority, B=good, C=low interest, X=unknown).
    spe_remarks : str
        SPE cross-reference remarks.
    gpa_scale : str
        GPA scale string (e.g. ``1.7/1``, ``80%``).
    study_level : str
        Study level (Bachelor, Master, Autre).  Empty when not available.
    gpa_candidate : str
        Raw GPA value of the candidate.
    gpa_max : str
        Maximum possible GPA on the grading scale.
    gender : str
        Gender (M/F) when available.
    committee_evaluations : str
        Merged text from all committee members, formatted as
        ``[INITIALS] Decision — Comment | [INITIALS] Decision — Comment``.
    decision_section : str
        Section aggregate decision (OK, NO, A discuter, etc.).
    decision_permanent_member : str
        Permanent committee member decision.  Empty for early years.
    decision_final : str
        Final aggregate decision.  Empty for early years.
    """

    source_file: str
    academic_year: str
    admission_round: str

    candidate_number: int | None = None
    name: str = ""
    school_country: str = ""
    school_name: str = ""
    school_quality: str = ""
    spe_remarks: str = ""
    gpa_scale: str = ""
    study_level: str = ""
    gpa_candidate: str = ""
    gpa_max: str = ""
    gender: str = ""

    committee_evaluations: str = ""

    decision_section: str = ""
    decision_permanent_member: str = ""
    decision_final: str = ""
