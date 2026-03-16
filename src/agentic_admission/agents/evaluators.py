"""Specialist evaluator agent functions for the deliberation panel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentic_admission.agents.llm_client import ChatMessage, complete
from agentic_admission.agents.prompts import AGENT_PROMPTS
from agentic_admission.models.evaluation import AgentRole, AgentScorecard

if TYPE_CHECKING:
    import httpx


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
    scorecard = await complete(
        messages=messages,
        response_model=AgentScorecard,
        model=model,
        base_url=base_url,
        client=client,
    )
    return AgentScorecard(
        role=AgentRole.ACADEMIC, scores=scorecard.scores, justifications=scorecard.justifications
    )


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
        f"## Calibration Profile\n\n{calibration_context}\n\n"
        f"## Historical Letters for Comparison\n\n{historical_letters}"
    )
    messages = [
        ChatMessage(role="system", content=AGENT_PROMPTS[AgentRole.REFERENCE]),
        ChatMessage(role="user", content=user_content),
    ]
    scorecard = await complete(
        messages=messages,
        response_model=AgentScorecard,
        model=model,
        base_url=base_url,
        client=client,
    )
    return AgentScorecard(
        role=AgentRole.REFERENCE, scores=scorecard.scores, justifications=scorecard.justifications
    )


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
    scorecard = await complete(
        messages=messages,
        response_model=AgentScorecard,
        model=model,
        base_url=base_url,
        client=client,
    )
    return AgentScorecard(
        role=AgentRole.MOTIVATION, scores=scorecard.scores, justifications=scorecard.justifications
    )


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
    scorecard = await complete(
        messages=messages,
        response_model=AgentScorecard,
        model=model,
        base_url=base_url,
        client=client,
    )
    return AgentScorecard(
        role=AgentRole.DEVILS_ADVOCATE,
        scores=scorecard.scores,
        justifications=scorecard.justifications,
    )
