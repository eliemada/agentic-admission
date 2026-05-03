"""Specialist evaluator agent functions for the deliberation panel."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import BaseModel

from agentic_admission.agents.llm_client import ChatMessage, complete
from agentic_admission.agents.prompts import AGENT_PROMPTS
from agentic_admission.models.evaluation import AgentRole, AgentScorecard, DimensionJustification

if TYPE_CHECKING:
    import httpx


# ---------------------------------------------------------------------------
# Typed response models — explicit fields so the LLM knows what to produce
# ---------------------------------------------------------------------------


class AcademicResponse(BaseModel, frozen=True):
    """Response schema for the Academic Evaluator."""

    academic_strength: int
    academic_strength_justification: str
    institution_quality: int
    institution_quality_justification: str


class ReferenceResponse(BaseModel, frozen=True):
    """Response schema for the Reference Letter Specialist."""

    reference_quality: int
    reference_quality_justification: str
    calibration_confidence: int
    calibration_confidence_justification: str


class MotivationResponse(BaseModel, frozen=True):
    """Response schema for the Motivation & Fit Evaluator."""

    motivation_clarity: int
    motivation_clarity_justification: str
    program_fit: int
    program_fit_justification: str


class DevilsAdvocateResponse(BaseModel, frozen=True):
    """Response schema for the Devil's Advocate."""

    risk_flags: int
    risk_flags_justification: str
    consistency: int
    consistency_justification: str


def _response_to_scorecard(role: AgentRole, response: BaseModel) -> AgentScorecard:
    """Convert a typed response to an AgentScorecard.

    Extracts fields ending in ``_justification`` as justifications and
    the corresponding integer fields as scores.

    Parameters
    ----------
    role
        The agent role.
    response
        The typed response model.

    Returns
    -------
    AgentScorecard
        A scorecard with scores and justifications dicts.
    """
    data = response.model_dump()
    scores: dict[str, int] = {}
    justifications: dict[str, DimensionJustification] = {}

    for key, value in data.items():
        if key.endswith("_justification"):
            dim = key.removesuffix("_justification")
            justifications[dim] = _parse_justification(str(value))
        else:
            scores[key] = max(1, min(10, int(value)))

    return AgentScorecard(role=role, scores=scores, justifications=justifications)


def _parse_justification(raw: str) -> DimensionJustification:
    """Parse a justification string into structured pros/cons.

    The LLM may return either a JSON object with pros/cons arrays
    or a plain text string. Handles both formats.
    """
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and ("pros" in parsed or "cons" in parsed):
                return DimensionJustification(
                    pros=tuple(parsed.get("pros", ())),
                    cons=tuple(parsed.get("cons", ())),
                )
        except json.JSONDecodeError:
            pass
    # Fallback: treat entire string as a single pro
    return DimensionJustification(pros=(raw,) if raw else (), cons=())


async def evaluate_academic(
    *, transcript_text: str, model: str, base_url: str, client: httpx.AsyncClient | None = None
) -> AgentScorecard:
    """Run the Academic Evaluator agent.

    Parameters
    ----------
    transcript_text
        Markdown text of transcripts, GPA info, and GRE scores.
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.
    client
        Optional shared ``httpx.AsyncClient``.

    Returns
    -------
    AgentScorecard
        Scorecard with ``academic_strength`` and ``institution_quality``.
    """
    messages = [
        ChatMessage(role="system", content=AGENT_PROMPTS[AgentRole.ACADEMIC]),
        ChatMessage(role="user", content=f"Evaluate this candidate:\n\n{transcript_text}"),
    ]
    response = await complete(
        messages=messages,
        response_model=AcademicResponse,
        model=model,
        base_url=base_url,
        client=client,
    )
    return _response_to_scorecard(AgentRole.ACADEMIC, response)


async def evaluate_reference(
    *,
    letters_text: str,
    calibration_context: str,
    historical_letters: str,
    model: str,
    base_url: str,
    client: httpx.AsyncClient | None = None,
) -> AgentScorecard:
    """Run the Reference Letter Specialist agent.

    Parameters
    ----------
    letters_text
        Markdown text of all recommendation letters.
    calibration_context
        Calibration profile for the candidate's region/institution.
    historical_letters
        3-5 retrieved historical letters with outcomes.
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.
    client
        Optional shared ``httpx.AsyncClient``.

    Returns
    -------
    AgentScorecard
        Scorecard with ``reference_quality`` and ``calibration_confidence``.
    """
    user_content = (
        f"## Candidate's Reference Letters\n\n{letters_text}\n\n"
        f"## Calibration Profile\n\n{calibration_context or '(not available)'}\n\n"
        f"## Historical Letters for Comparison\n\n{historical_letters or '(not available)'}"
    )
    messages = [
        ChatMessage(role="system", content=AGENT_PROMPTS[AgentRole.REFERENCE]),
        ChatMessage(role="user", content=user_content),
    ]
    response = await complete(
        messages=messages,
        response_model=ReferenceResponse,
        model=model,
        base_url=base_url,
        client=client,
    )
    return _response_to_scorecard(AgentRole.REFERENCE, response)


async def evaluate_motivation(
    *,
    motivation_text: str,
    cv_text: str,
    model: str,
    base_url: str,
    client: httpx.AsyncClient | None = None,
) -> AgentScorecard:
    """Run the Motivation & Fit Evaluator agent.

    Parameters
    ----------
    motivation_text
        Markdown text of the motivation letter.
    cv_text
        Markdown text of the CV.
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.
    client
        Optional shared ``httpx.AsyncClient``.

    Returns
    -------
    AgentScorecard
        Scorecard with ``motivation_clarity`` and ``program_fit``.
    """
    user_content = f"## Motivation Letter\n\n{motivation_text}\n\n## CV\n\n{cv_text}"
    messages = [
        ChatMessage(role="system", content=AGENT_PROMPTS[AgentRole.MOTIVATION]),
        ChatMessage(role="user", content=user_content),
    ]
    response = await complete(
        messages=messages,
        response_model=MotivationResponse,
        model=model,
        base_url=base_url,
        client=client,
    )
    return _response_to_scorecard(AgentRole.MOTIVATION, response)


async def evaluate_devils_advocate(
    *, full_dossier_text: str, model: str, base_url: str, client: httpx.AsyncClient | None = None
) -> AgentScorecard:
    """Run the Devil's Advocate agent.

    Parameters
    ----------
    full_dossier_text
        Markdown text of the entire dossier (all documents concatenated).
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.
    client
        Optional shared ``httpx.AsyncClient``.

    Returns
    -------
    AgentScorecard
        Scorecard with ``risk_flags`` and ``consistency``.
    """
    messages = [
        ChatMessage(role="system", content=AGENT_PROMPTS[AgentRole.DEVILS_ADVOCATE]),
        ChatMessage(role="user", content=f"Review this complete dossier:\n\n{full_dossier_text}"),
    ]
    response = await complete(
        messages=messages,
        response_model=DevilsAdvocateResponse,
        model=model,
        base_url=base_url,
        client=client,
    )
    return _response_to_scorecard(AgentRole.DEVILS_ADVOCATE, response)
