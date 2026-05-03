"""LLM-powered curriculum matcher.

Maps a candidate's transcript courses to EPFL equivalents and produces
a concise match report for minor assignment decisions.
"""

from __future__ import annotations

import httpx
from loguru import logger
from pydantic import BaseModel

from agentic_admission.agents.llm_client import ChatMessage, complete
from agentic_admission.curriculum.match_models import (
    CourseMatch,
    CoverageArea,
    CurriculumMatchReport,
    MinorFit,
)
from agentic_admission.curriculum.models import Curriculum, ProgramLevel
from agentic_admission.curriculum.storage import load_curriculum

# ---------------------------------------------------------------------------
# LLM response schema
# ---------------------------------------------------------------------------


class _MatchedCourse(BaseModel, frozen=True):
    """Single course match in LLM response."""

    candidate_course: str
    epfl_codes: list[str]
    confidence: float


class _CoverageAreaResponse(BaseModel, frozen=True):
    """Coverage area in LLM response."""

    area: str
    coverage: float
    gap_courses: list[str]


class _MinorFitResponse(BaseModel, frozen=True):
    """Minor fit in LLM response."""

    minor_slug: str
    minor_name: str
    fit_score: int
    prerequisite_coverage: float
    strengths: list[str]
    gaps: list[str]
    reasoning: str


class _MatcherResponse(BaseModel, frozen=True):
    """Full LLM response for curriculum matching."""

    course_matches: list[_MatchedCourse]
    coverage_areas: list[_CoverageAreaResponse]
    overall_coverage: float
    closest_epfl_bachelor: str
    minor_fits: list[_MinorFitResponse]
    summary: str


# ---------------------------------------------------------------------------
# Context builders — compact, code+name only, no descriptions
# ---------------------------------------------------------------------------


def _build_bachelor_context(curriculum: Curriculum) -> str:
    """Build a compact reference: code + name per course, grouped by program."""
    bachelor_programs = [p for p in curriculum.programs if p.level == ProgramLevel.BACHELOR]
    lines: list[str] = []

    for program in bachelor_programs:
        courses = curriculum.courses_for_program(program.slug)
        if not courses:
            continue
        course_list = ", ".join(f"{c.code} {c.name}" for c in courses)
        lines.append(f"**{program.name}**: {course_list}")

    return "\n".join(lines)


def _build_minor_context(curriculum: Curriculum) -> str:
    """Build a compact reference of minors: slug + course codes."""
    minor_programs = [p for p in curriculum.programs if p.level == ProgramLevel.MINOR]
    lines: list[str] = []

    for minor in minor_programs:
        courses = curriculum.courses_for_program(minor.slug)
        if not courses:
            continue
        course_list = ", ".join(c.code for c in courses)
        lines.append(f"**{minor.name}** [{minor.slug}]: {course_list}")

    return "\n".join(lines)


_SYSTEM_PROMPT = """\
You are an academic curriculum analyst at EPFL. Compare a candidate's bachelor \
courses against EPFL programs and recommend 3 minors.

Be CONCISE. No prose — structured data only.

INSTRUCTIONS:
1. Match candidate courses to EPFL codes (top 10 matches, confidence 0-1).
2. Coverage areas: 4-6 areas, fraction covered (0-1), list gap course codes only.
3. Closest EPFL bachelor: one program name.
4. Top 3 minor fits: score 1-10, prerequisite_coverage 0-1, \
3 strengths, 3 gaps (short phrases), reasoning (1 sentence max).
5. Summary: 1 sentence.

Return JSON matching the schema exactly.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def match_curriculum(
    *,
    candidate_id: str,
    transcript_text: str,
    model: str,
    base_url: str,
    api_key: str = "",
    client: httpx.AsyncClient | None = None,
    curriculum: Curriculum | None = None,
) -> CurriculumMatchReport:
    """Match a candidate's transcript against the EPFL curriculum.

    Parameters
    ----------
    candidate_id
        Candidate identifier.
    transcript_text
        Markdown text of the candidate's academic transcript.
    model
        LLM model identifier.
    base_url
        LLM endpoint base URL.
    api_key
        Optional API key for cloud endpoints (OpenRouter, etc.).
    client
        Optional shared ``httpx.AsyncClient``.
    curriculum
        Pre-loaded curriculum. Loaded from disk if not provided.

    Returns
    -------
    CurriculumMatchReport
        Structured report with course matches, coverage, and minor fit.
    """
    if curriculum is None:
        curriculum = load_curriculum()

    bachelor_ctx = _build_bachelor_context(curriculum)
    minor_ctx = _build_minor_context(curriculum)

    messages = [
        ChatMessage(role="system", content=_SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=(
                f"## EPFL Bachelors\n{bachelor_ctx}\n\n"
                f"## EPFL Minors\n{minor_ctx}\n\n"
                f"## Candidate Transcript\n{transcript_text}"
            ),
        ),
    ]

    logger.info("Matching curriculum for candidate {}", candidate_id)

    managed_client: httpx.AsyncClient | None = None
    effective_client = client
    if client is None and api_key:
        managed_client = httpx.AsyncClient(
            timeout=120.0, headers={"Authorization": f"Bearer {api_key}"}
        )
        effective_client = managed_client

    try:
        response = await complete(
            messages=messages,
            response_model=_MatcherResponse,
            model=model,
            base_url=base_url,
            client=effective_client,
            max_tokens=8192,
        )
    finally:
        if managed_client is not None:
            await managed_client.aclose()

    return _to_report(candidate_id, response)


def _to_report(candidate_id: str, response: _MatcherResponse) -> CurriculumMatchReport:
    """Convert the flat LLM response to the immutable domain model."""
    return CurriculumMatchReport(
        candidate_id=candidate_id,
        course_matches=tuple(
            CourseMatch(
                candidate_course=m.candidate_course,
                epfl_codes=tuple(m.epfl_codes),
                confidence=m.confidence,
            )
            for m in response.course_matches
        ),
        coverage_by_area=tuple(
            CoverageArea(area=a.area, coverage=a.coverage, gap_courses=tuple(a.gap_courses))
            for a in response.coverage_areas
        ),
        overall_coverage=response.overall_coverage,
        closest_epfl_bachelor=response.closest_epfl_bachelor,
        minor_fits=tuple(
            MinorFit(
                minor_slug=mf.minor_slug,
                minor_name=mf.minor_name,
                fit_score=mf.fit_score,
                prerequisite_coverage=mf.prerequisite_coverage,
                strengths=tuple(mf.strengths),
                gaps=tuple(mf.gaps),
                reasoning=mf.reasoning,
            )
            for mf in response.minor_fits
        ),
        summary=response.summary,
    )


def format_match_report(report: CurriculumMatchReport) -> str:
    """Format a match report as concise markdown for downstream agents."""
    lines: list[str] = [
        f"**Coverage**: {report.overall_coverage:.0%} "
        f"| **Closest bachelor**: {report.closest_epfl_bachelor}"
    ]

    for area in report.coverage_by_area:
        gaps = f" (gaps: {', '.join(area.gap_courses[:3])})" if area.gap_courses else ""
        lines.append(f"- {area.area}: {area.coverage:.0%}{gaps}")

    for i, mf in enumerate(report.minor_fits, 1):
        strengths = ", ".join(mf.strengths[:3])
        gaps = ", ".join(mf.gaps[:3])
        lines.append(
            f"{i}. **{mf.minor_name}** {mf.fit_score}/10 "
            f"(prereq: {mf.prerequisite_coverage:.0%}) "
            f"+{strengths} -{gaps}"
        )

    lines.append(report.summary)

    return "\n".join(lines)
