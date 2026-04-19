"""Minor Advisor agent: recommends EPFL minors based on transcript and CV."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from pydantic import BaseModel

from agentic_admission.agents.llm_client import ChatMessage, complete
from agentic_admission.models.evaluation import MinorRecommendation, MinorScore
from agentic_admission.models.minor import format_minor_list

if TYPE_CHECKING:
    import httpx


_MINOR_ADVISOR_PROMPT = (
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

    Returns
    -------
    MinorRecommendation
        Ranked list of 3 recommended minors with scores and reasoning.
    """
    minor_list = format_minor_list()

    messages = [
        ChatMessage(role="system", content=_MINOR_ADVISOR_PROMPT),
        ChatMessage(
            role="user",
            content=(
                "Recommend the 3 best-fitting EPFL minors for this candidate.\n\n"
                "## Available Minors\n\n"
                f"{minor_list}\n\n"
                "## Candidate Transcript\n\n"
                f"{transcript_text}\n\n"
                "## Candidate CV\n\n"
                f"{cv_text}"
            ),
        ),
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
