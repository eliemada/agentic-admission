"""Output models for LLM-powered curriculum matching.

Concise models capturing the decision-relevant output of mapping a
candidate's courses to EPFL equivalents.
"""

from __future__ import annotations

from pydantic import BaseModel


class CourseMatch(BaseModel, frozen=True):
    """A single mapping: candidate course → EPFL equivalent(s).

    Attributes
    ----------
    candidate_course : str
        Name of the course from the candidate's transcript.
    epfl_codes : tuple[str, ...]
        EPFL course codes that cover similar content.
    confidence : float
        Match confidence (0.0-1.0).
    """

    candidate_course: str
    epfl_codes: tuple[str, ...] = ()
    confidence: float = 0.0


class CoverageArea(BaseModel, frozen=True):
    """Coverage score for a knowledge area.

    Attributes
    ----------
    area : str
        Knowledge area name (e.g. "Mathematics", "CS Core").
    coverage : float
        Fraction covered (0.0-1.0).
    gap_courses : tuple[str, ...]
        EPFL course codes the candidate is missing.
    """

    area: str
    coverage: float = 0.0
    gap_courses: tuple[str, ...] = ()


class MinorFit(BaseModel, frozen=True):
    """How well the candidate's background aligns with a specific minor.

    Attributes
    ----------
    minor_slug : str
        Minor program slug.
    minor_name : str
        Minor display name.
    fit_score : int
        Overall fit (1-10).
    prerequisite_coverage : float
        Fraction of prerequisite knowledge covered (0.0-1.0).
    strengths : tuple[str, ...]
        Short phrases: candidate strengths for this minor.
    gaps : tuple[str, ...]
        Short phrases: knowledge gaps.
    reasoning : str
        One sentence justification.
    """

    minor_slug: str
    minor_name: str
    fit_score: int = 5
    prerequisite_coverage: float = 0.0
    strengths: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()
    reasoning: str = ""


class CurriculumMatchReport(BaseModel, frozen=True):
    """Complete matching report for one candidate.

    Attributes
    ----------
    candidate_id : str
        Candidate identifier.
    course_matches : tuple[CourseMatch, ...]
        Top course mappings to EPFL equivalents.
    coverage_by_area : tuple[CoverageArea, ...]
        Coverage scores by knowledge area.
    overall_coverage : float
        Aggregate coverage (0.0-1.0).
    closest_epfl_bachelor : str
        Which EPFL bachelor the candidate most resembles.
    minor_fits : tuple[MinorFit, ...]
        Top-3 recommended minors.
    summary : str
        One sentence executive summary.
    """

    candidate_id: str
    course_matches: tuple[CourseMatch, ...] = ()
    coverage_by_area: tuple[CoverageArea, ...] = ()
    overall_coverage: float = 0.0
    closest_epfl_bachelor: str = ""
    minor_fits: tuple[MinorFit, ...] = ()
    summary: str = ""
