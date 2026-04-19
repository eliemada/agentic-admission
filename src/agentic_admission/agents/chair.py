"""Chair agent: disagreement detection, debate moderation, and final synthesis."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    Decision,
    PanelVerdict,
    VerdictSummary,
)

if TYPE_CHECKING:
    import httpx

_MAX_DEBATE_ROUNDS = 2


SCORING_WEIGHTS: dict[str, float] = {
    "academic_strength": 0.20,
    "institution_quality": 0.15,
    "reference_quality": 0.15,
    "calibration_confidence": 0.10,
    "motivation_clarity": 0.10,
    "program_fit": 0.10,
    "risk_flags": 0.10,
    "consistency": 0.10,
}
"""Explicit scoring weights for the composite score.

Academic credentials and reference quality dominate (50% combined).
Motivation and devil's-advocate dimensions are secondary signals — a weak
motivation letter should not sink an academically strong candidate.
"""


def compute_composite(final_scores: dict[str, int]) -> float:
    """Compute deterministic weighted composite from dimension scores.

    Parameters
    ----------
    final_scores
        Dimension name to integer score (1-10).

    Returns
    -------
    float
        Weighted average clamped to 1.0-10.0.
    """
    total = sum(
        final_scores.get(dim, 5) * weight for dim, weight in SCORING_WEIGHTS.items()
    )
    return max(1.0, min(10.0, round(total, 2)))


class ChairSynthesis(BaseModel, frozen=True):
    """Lightweight response model for the Chair's final synthesis.

    The composite_score is computed deterministically in Python — the LLM
    only provides dimension scores and the decision.

    Attributes
    ----------
    academic_strength
        Final score for academic strength (1-10).
    institution_quality
        Final score for institution quality (1-10).
    reference_quality
        Final score for reference quality (1-10).
    calibration_confidence
        Final score for calibration confidence (1-10).
    motivation_clarity
        Final score for motivation clarity (1-10).
    program_fit
        Final score for program fit (1-10).
    risk_flags
        Final score for risk flags (1-10, inverse: 10 = no concerns).
    consistency
        Final score for dossier consistency (1-10).
    decision
        Accept, reject, or waitlist.
    justification
        2-3 sentence justification.
    """

    academic_strength: int
    institution_quality: int
    reference_quality: int
    calibration_confidence: int
    motivation_clarity: int
    program_fit: int
    risk_flags: int
    consistency: int
    decision: Decision
    pros: tuple[str, ...]
    cons: tuple[str, ...]


class DebateArgument(BaseModel, frozen=True):
    """A single agent's argument in a debate round."""

    argument: str


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
        lines: list[str] = [f"### {card.role.value.upper()}"]
        for dim, score in card.scores.items():
            lines.append(f"- {dim}: {score}/10")
            justification = card.justifications.get(dim)
            if justification is not None:
                for pro in justification.pros:
                    lines.append(f"  + {pro}")
                for con in justification.cons:
                    lines.append(f"  - {con}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _format_debate_entries(entries: tuple[DebateEntry, ...]) -> str:
    """Render debate entries as readable text.

    Parameters
    ----------
    entries
        Ordered debate entries to format.

    Returns
    -------
    str
        Newline-joined formatted entries, or ``"(none yet)"`` if empty.
    """
    if not entries:
        return "(none yet)"
    return "\n".join(f"[{e.role.value}, Round {e.round_number}]: {e.argument}" for e in entries)


async def detect_disagreements(
    *,
    scorecards: tuple[AgentScorecard, ...],
    model: str,
    base_url: str,
    client: httpx.AsyncClient | None = None,
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
    client
        Optional shared ``httpx.AsyncClient``.

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
        messages=messages,
        response_model=DisagreementReport,
        model=model,
        base_url=base_url,
        client=client,
    )
    logger.info("Chair detected {} conflict(s)", len(report.conflicts))
    return report.conflicts


async def moderate_debate(
    *,
    conflict: Conflict,
    scorecards: tuple[AgentScorecard, ...],
    model: str,
    base_url: str,
    client: httpx.AsyncClient | None = None,
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
    client
        Optional shared ``httpx.AsyncClient``.

    Returns
    -------
    DebateTranscript
        Full transcript of the debate.
    """
    entries: list[DebateEntry] = []
    context = _format_scorecards(scorecards)

    for round_num in range(1, _MAX_DEBATE_ROUNDS + 1):
        for role in conflict.agents_involved:
            prior_args = _format_debate_entries(tuple(entries))
            messages = [
                ChatMessage(role="system", content=AGENT_PROMPTS[role]),
                ChatMessage(
                    role="user",
                    content=(
                        f"DEBATE — Round {round_num}\n\n"
                        f"Question: {conflict.debate_question}\n\n"
                        f"Context:\n{context}\n\n"
                        f"Prior arguments:\n{prior_args}\n\n"
                        "Defend or adjust your position on this dimension. "
                        "Provide a concise argument (2-4 sentences)."
                    ),
                ),
            ]
            response = await complete(
                messages=messages,
                response_model=DebateArgument,
                model=model,
                base_url=base_url,
                client=client,
            )
            entries.append(
                DebateEntry(role=role, round_number=round_num, argument=response.argument)
            )

    logger.info("Debate on '{}' completed: {} entries", conflict.dimension, len(entries))
    return DebateTranscript(conflict_dimension=conflict.dimension, entries=tuple(entries))


async def synthesize(
    *,
    candidate_id: str,
    scorecards: tuple[AgentScorecard, ...],
    debates: tuple[DebateTranscript, ...],
    model: str,
    base_url: str,
    client: httpx.AsyncClient | None = None,
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
    client
        Optional shared ``httpx.AsyncClient``.

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
            header = f"### Debate: {transcript.conflict_dimension}"
            body = _format_debate_entries(transcript.entries)
            sections.append(f"{header}\n{body}")
        debate_text = "\n\n".join(sections)

    weight_description = ", ".join(
        f"{dim} ({w:.0%})" for dim, w in SCORING_WEIGHTS.items()
    )

    messages = [
        ChatMessage(role="system", content=AGENT_PROMPTS[AgentRole.CHAIR]),
        ChatMessage(
            role="user",
            content=(
                "Produce the FINAL VERDICT for this candidate.\n\n"
                "Return a JSON with:\n"
                "- 8 dimension scores (integer 1-10): academic_strength, "
                "institution_quality, reference_quality, calibration_confidence, "
                "motivation_clarity, program_fit, risk_flags, consistency\n"
                "- decision: one of 'accept', 'reject', or 'waitlist'\n"
                "- pros: array of 2-5 bullet points summarising key strengths\n"
                "- cons: array of 0-5 bullet points summarising concerns\n\n"
                "NOTE: The composite score is computed automatically using these "
                f"weights: {weight_description}. Academic credentials and "
                "reference quality carry the most weight. A strong transcript "
                "should not be penalised by a weak motivation letter.\n\n"
                f"## Specialist Scorecards\n\n{formatted_cards}\n\n"
                f"## Debate Transcripts\n\n{debate_text or '(no debates needed)'}"
            ),
        ),
    ]
    synthesis = await complete(
        messages=messages,
        response_model=ChairSynthesis,
        model=model,
        base_url=base_url,
        client=client,
    )

    final_scores = {
        "academic_strength": synthesis.academic_strength,
        "institution_quality": synthesis.institution_quality,
        "reference_quality": synthesis.reference_quality,
        "calibration_confidence": synthesis.calibration_confidence,
        "motivation_clarity": synthesis.motivation_clarity,
        "program_fit": synthesis.program_fit,
        "risk_flags": synthesis.risk_flags,
        "consistency": synthesis.consistency,
    }

    composite = compute_composite(final_scores)
    logger.info("Composite score for {}: {:.2f}", candidate_id, composite)

    return PanelVerdict(
        candidate_id=candidate_id,
        scorecards=scorecards,
        debates=debates,
        final_scores=final_scores,
        composite_score=composite,
        decision=synthesis.decision,
        justification=VerdictSummary(pros=synthesis.pros, cons=synthesis.cons),
    )
