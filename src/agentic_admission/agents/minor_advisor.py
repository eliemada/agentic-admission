"""Minor Advisor agent: recommends EPFL minors based on transcript and CV.

When EPFL curriculum data is available, the advisor first matches the
candidate's courses against EPFL bachelor equivalents, then uses that
structured overlap to ground its minor recommendations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from pydantic import BaseModel

from agentic_admission.agents.llm_client import ChatMessage, complete
from agentic_admission.curriculum.match_models import CurriculumMatchReport
from agentic_admission.models.evaluation import MinorRecommendation, MinorScore
from agentic_admission.models.minor import format_minor_list

if TYPE_CHECKING:
    import httpx

    from agentic_admission.curriculum.models import Curriculum


_MINOR_ADVISOR_PROMPT = """\
You are the Minor Advisor on an MTE admissions panel at EPFL.

Your task: given a candidate's transcript, CV, and a curriculum match report
that maps their courses to EPFL equivalents, recommend which EPFL disciplinary
minor best fits their academic background.

RULES:
- Recommend exactly 3 minors, ranked by fit (best first).
- Use the curriculum match report as your PRIMARY evidence — it shows which
  EPFL courses the candidate's background covers and where the gaps are.
- A good minor fit means the candidate already has the prerequisite knowledge
  to succeed in that minor's courses.
- The CV provides secondary context (work experience, projects, interests).
- If the candidate studied Industrial Engineering and you are uncertain,
  default to Systems Engineering (section MTE).
- Each recommendation needs a fit_score (1-10) and reasoning that cites
  specific matched courses or coverage areas from the report.
- Return a JSON matching the MinorAdvisorResponse schema.
"""

_MINOR_ADVISOR_PROMPT_BASIC = (
    "You are the Minor Advisor on an MTE admissions panel at EPFL.\n\n"
    "Your task: given a candidate's transcript and CV, recommend which EPFL "
    "disciplinary minor best fits their academic background and coursework.\n\n"
    "RULES:\n"
    "- Recommend exactly 3 minors, ranked by fit (best first).\n"
    "- Base your recommendation primarily on courses taken and skills "
    "demonstrated in the transcript.\n"
    "- The CV provides secondary context (work experience, projects, interests).\n"
    "- If the candidate studied Industrial Engineering and you are uncertain, "
    "default to Systems Engineering (section MTE).\n"
    "- Each recommendation needs a fit_score (1-10) and a one-sentence "
    "reasoning citing specific courses or experience.\n"
    "- Return a JSON matching the MinorAdvisorResponse schema.\n"
)


class MinorAdvisorResponse(BaseModel, frozen=True):
    """LLM response schema for minor recommendation."""

    minor_1_name: str
    minor_1_section: str
    minor_1_score: int
    minor_1_reason: str
    minor_2_name: str
    minor_2_section: str
    minor_2_score: int
    minor_2_reason: str
    minor_3_name: str
    minor_3_section: str
    minor_3_score: int
    minor_3_reason: str


async def recommend_minor(
    *,
    transcript_text: str,
    cv_text: str,
    model: str,
    base_url: str,
    client: httpx.AsyncClient | None = None,
    candidate_id: str = "",
    use_curriculum: bool = True,
) -> MinorRecommendation:
    """Recommend top-3 EPFL minors for a candidate.

    Parameters
    ----------
    transcript_text
        Markdown text of the candidate's academic transcript.
    cv_text
        Markdown text of the candidate's CV.
    model
        LLM model identifier.
    base_url
        LLM endpoint base URL.
    client
        Optional shared ``httpx.AsyncClient``.
    candidate_id
        Candidate identifier (used for curriculum matching).
    use_curriculum
        If True and curriculum data exists, first match courses against
        EPFL and use the match report to ground recommendations.

    Returns
    -------
    MinorRecommendation
        Ranked list of 3 recommended minors with scores and reasoning.
    """
    match_context = ""

    if use_curriculum:
        report = await _try_curriculum_match(
            candidate_id=candidate_id,
            transcript_text=transcript_text,
            model=model,
            base_url=base_url,
            client=client,
        )
        if report is not None:
            from agentic_admission.curriculum.matcher import format_match_report

            match_context = format_match_report(report)

    system_prompt = _MINOR_ADVISOR_PROMPT if match_context else _MINOR_ADVISOR_PROMPT_BASIC
    minor_list = format_minor_list()

    user_content_parts = [
        "Recommend the 3 best-fitting EPFL minors for this candidate.\n\n"
        "## Available Minors\n\n"
        f"{minor_list}\n\n"
    ]

    if match_context:
        user_content_parts.append(
            f"## Curriculum Match Report (course-level EPFL comparison)\n\n{match_context}\n\n"
        )

    user_content_parts.extend(
        [f"## Candidate Transcript\n\n{transcript_text}\n\n## Candidate CV\n\n{cv_text}"]
    )

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content="".join(user_content_parts)),
    ]

    response = await complete(
        messages=messages,
        response_model=MinorAdvisorResponse,
        model=model,
        base_url=base_url,
        client=client,
    )

    recommended = (
        MinorScore(
            minor_name=response.minor_1_name,
            section_code=response.minor_1_section,
            fit_score=response.minor_1_score,
            reasoning=response.minor_1_reason,
        ),
        MinorScore(
            minor_name=response.minor_2_name,
            section_code=response.minor_2_section,
            fit_score=response.minor_2_score,
            reasoning=response.minor_2_reason,
        ),
        MinorScore(
            minor_name=response.minor_3_name,
            section_code=response.minor_3_section,
            fit_score=response.minor_3_score,
            reasoning=response.minor_3_reason,
        ),
    )

    primary = recommended[0].minor_name
    logger.info("Minor recommendation: {} (score {})", primary, recommended[0].fit_score)

    return MinorRecommendation(recommended=recommended, primary_minor=primary)


async def _try_curriculum_match(
    *,
    candidate_id: str,
    transcript_text: str,
    model: str,
    base_url: str,
    client: httpx.AsyncClient | None,
) -> CurriculumMatchReport | None:
    """Attempt curriculum matching, returning None on any failure."""
    from agentic_admission.curriculum.storage import load_curriculum

    try:
        curriculum: Curriculum = load_curriculum()
    except FileNotFoundError:
        logger.debug("No curriculum data found — skipping curriculum match")
        return None

    # Only match if we have bachelor programs to compare against
    has_bachelors = any(p.level.value == "bachelor" for p in curriculum.programs)
    if not has_bachelors:
        logger.debug("No bachelor programs in curriculum — skipping match")
        return None

    try:
        from agentic_admission.curriculum.matcher import match_curriculum

        return await match_curriculum(
            candidate_id=candidate_id,
            transcript_text=transcript_text,
            model=model,
            base_url=base_url,
            client=client,
            curriculum=curriculum,
        )
    except Exception:
        logger.opt(exception=True).warning("Curriculum match failed — falling back to basic mode")
        return None
