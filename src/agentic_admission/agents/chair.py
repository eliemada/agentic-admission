"""Chair agent: disagreement detection, debate moderation, and final synthesis."""

from __future__ import annotations

from loguru import logger
from pydantic import BaseModel

from agentic_admission.agents.llm_client import ChatMessage, complete
from agentic_admission.agents.prompts import AGENT_PROMPTS
from agentic_admission.models.evaluation import (
    AgentRole,
    AgentScorecard,
    Conflict,
    DebateEntry,
    DebateTranscript,
    PanelVerdict,
)

_MAX_DEBATE_ROUNDS = 2


class DisagreementReport(BaseModel, frozen=True):
    """Chair's assessment of conflicts across scorecards.

    Attributes
    ----------
    conflicts
        Detected semantic conflicts (empty tuple if none).
    """

    conflicts: tuple[Conflict, ...]


def _format_scorecards(scorecards: tuple[AgentScorecard, ...]) -> str:
    """Render scorecards as readable text for the Chair's context.

    Parameters
    ----------
    scorecards
        Specialist scorecards to format.

    Returns
    -------
    str
        Markdown-formatted scorecard summary.
    """
    sections: list[str] = []
    for card in scorecards:
        lines = [f"### {card.role.value.upper()}"]
        for dim, score in card.scores.items():
            justification = card.justifications.get(dim, "")
            lines.append(f"- {dim}: {score}/10 — {justification}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


async def detect_disagreements(
    *, scorecards: tuple[AgentScorecard, ...], model: str, base_url: str
) -> tuple[Conflict, ...]:
    """Have the Chair identify semantic conflicts across specialist scorecards.

    Parameters
    ----------
    scorecards
        The 4 specialist scorecards.
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.

    Returns
    -------
    tuple[Conflict, ...]
        Detected conflicts, empty if agents agree.
    """
    formatted = _format_scorecards(scorecards)
    messages = [
        ChatMessage(role="system", content=AGENT_PROMPTS[AgentRole.CHAIR]),
        ChatMessage(
            role="user",
            content=(
                "Review these 4 specialist scorecards and identify any meaningful "
                "semantic disagreements. Return a DisagreementReport.\n\n"
                f"{formatted}"
            ),
        ),
    ]
    report = await complete(
        messages=messages, response_model=DisagreementReport, model=model, base_url=base_url
    )
    logger.info("Chair detected {} conflict(s)", len(report.conflicts))
    return report.conflicts


async def moderate_debate(
    *, conflict: Conflict, scorecards: tuple[AgentScorecard, ...], model: str, base_url: str
) -> DebateTranscript:
    """Run a 2-round targeted debate between disagreeing agents.

    Parameters
    ----------
    conflict
        The specific disagreement to debate.
    scorecards
        All specialist scorecards (for context).
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.

    Returns
    -------
    DebateTranscript
        Full transcript of the debate.
    """
    entries: list[DebateEntry] = []
    context = _format_scorecards(scorecards)

    for round_num in range(1, _MAX_DEBATE_ROUNDS + 1):
        for role in conflict.agents_involved:
            prior_args = "\n".join(
                f"[{e.role.value}, Round {e.round_number}]: {e.argument}" for e in entries
            )
            messages = [
                ChatMessage(role="system", content=AGENT_PROMPTS[role]),
                ChatMessage(
                    role="user",
                    content=(
                        f"DEBATE — Round {round_num}\n\n"
                        f"Question: {conflict.debate_question}\n\n"
                        f"Context:\n{context}\n\n"
                        f"Prior arguments:\n{prior_args or '(none yet)'}\n\n"
                        "Defend or adjust your position. Respond with an AgentScorecard."
                    ),
                ),
            ]
            response = await complete(
                messages=messages, response_model=AgentScorecard, model=model, base_url=base_url
            )
            justification = response.justifications.get(
                conflict.dimension, next(iter(response.justifications.values()), "")
            )
            entries.append(DebateEntry(role=role, round_number=round_num, argument=justification))

    logger.info("Debate on '{}' completed: {} entries", conflict.dimension, len(entries))
    return DebateTranscript(conflict_dimension=conflict.dimension, entries=tuple(entries))


async def synthesize(
    *,
    candidate_id: str,
    scorecards: tuple[AgentScorecard, ...],
    debates: tuple[DebateTranscript, ...],
    model: str,
    base_url: str,
) -> PanelVerdict:
    """Produce the final panel verdict.

    Parameters
    ----------
    candidate_id
        Unique candidate identifier.
    scorecards
        All specialist scorecards.
    debates
        All debate transcripts (empty if no conflicts).
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.

    Returns
    -------
    PanelVerdict
        The final scorecard, recommendation, and justification.
    """
    formatted_cards = _format_scorecards(scorecards)
    debate_text = ""
    if debates:
        sections: list[str] = []
        for transcript in debates:
            lines = [
                f"### Debate: {transcript.conflict_dimension}",
                *[
                    f"[{entry.role.value}, Round {entry.round_number}]: {entry.argument}"
                    for entry in transcript.entries
                ],
            ]
            sections.append("\n".join(lines))
        debate_text = "\n\n".join(sections)

    messages = [
        ChatMessage(role="system", content=AGENT_PROMPTS[AgentRole.CHAIR]),
        ChatMessage(
            role="user",
            content=(
                "Produce the FINAL VERDICT for this candidate. Return a PanelVerdict with "
                "all 8 dimension scores, composite_score, decision, and justification.\n\n"
                f"## Specialist Scorecards\n\n{formatted_cards}\n\n"
                f"## Debate Transcripts\n\n{debate_text or '(no debates needed)'}"
            ),
        ),
    ]
    verdict = await complete(
        messages=messages, response_model=PanelVerdict, model=model, base_url=base_url
    )
    return PanelVerdict(
        candidate_id=candidate_id,
        scorecards=scorecards,
        debates=debates,
        final_scores=verdict.final_scores,
        composite_score=verdict.composite_score,
        decision=verdict.decision,
        justification=verdict.justification,
    )
