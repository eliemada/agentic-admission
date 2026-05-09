"""Chair agent: disagreement detection, debate moderation, and final synthesis."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from pydantic import BaseModel

from agentic_admission.agents.evaluation_profile import EXTERNAL_PROFILE, EvaluationProfile
from agentic_admission.agents.gpa_gate import ThresholdDirection, ThresholdVerdict
from agentic_admission.agents.llm_client import ChatMessage, complete
from agentic_admission.agents.prompts import AGENT_PROMPTS
from agentic_admission.models.evaluation import (
    AgentRole,
    AgentScorecard,
    Conflict,
    DebateEntry,
    DebateTranscript,
    Decision,
    DimensionJustification,
    PanelVerdict,
    VerdictSummary,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx

_MAX_DEBATE_ROUNDS = 2
_DEFAULT_DIMENSION_SCORE: int = 5

# Composite-score cutoffs for the deterministic decision rule. Calibrated
# against the 2025-26-spring cohort (128 candidates) so the accept rate
# (~37%) matches the committee's historical band of 40-50/128.
ACCEPT_COMPOSITE_FLOOR: float = 8.0
WAITLIST_COMPOSITE_FLOOR: float = 7.5
"""Composite-score thresholds applied AFTER the LLM produces dimension scores.

The LLM's own ``decision`` field is advisory: in the 2025-26-spring
backtest the LLM returned 79/128 accepts under a stated rule that should
have produced 57. We derive the decision deterministically from the
composite to keep accept rates calibrated and reproducible.
"""


def decision_from_composite(composite: float) -> Decision:
    """Map a composite score to ``accept`` / ``waitlist`` / ``reject``.

    Parameters
    ----------
    composite
        Weighted dimension-score average, in [1.0, 10.0].

    Returns
    -------
    Decision
        ``ACCEPT`` if ``composite >= 8.0``, ``WAITLIST`` if
        ``>= 7.5``, ``REJECT`` otherwise.

    Notes
    -----
    Gate overrides (below-threshold reject, low-confidence waitlist) are
    applied AFTER this rule via :func:`apply_gate_overrides` and take
    precedence.
    """
    if composite >= ACCEPT_COMPOSITE_FLOOR:
        return Decision.ACCEPT
    if composite >= WAITLIST_COMPOSITE_FLOOR:
        return Decision.WAITLIST
    return Decision.REJECT


def compute_composite(
    final_scores: dict[str, int],
    *,
    weights: Mapping[str, float] | None = None,
) -> float:
    """Compute deterministic weighted composite from dimension scores.

    Parameters
    ----------
    final_scores
        Dimension name to integer score (1-10).
    weights
        Per-dimension weights. Defaults to :data:`EXTERNAL_PROFILE.weights`.
        The caller is expected to supply weights that sum to 1.0; the
        :class:`~agentic_admission.agents.evaluation_profile.EvaluationProfile`
        constructor enforces this.

    Returns
    -------
    float
        Weighted average clamped to 1.0-10.0.
    """
    weights = weights or EXTERNAL_PROFILE.weights
    total = sum(
        final_scores.get(dim, _DEFAULT_DIMENSION_SCORE) * weight
        for dim, weight in weights.items()
    )
    return max(1.0, min(10.0, round(total, 2)))


_LOW_GPA_CONFIDENCE: float = 0.5
"""GPA-extraction confidence below which we route to WAITLIST instead of trusting the score."""

_BELOW_THRESHOLD_ACADEMIC_CAP: int = 4
"""Maximum allowed ``academic_strength`` when the GPA is below the SPE threshold."""


def apply_gate_overrides(
    *,
    decision: Decision,
    pros: tuple[str, ...],
    cons: tuple[str, ...],
    threshold_verdict: ThresholdVerdict | None,
    gpa_confidence: float,
) -> tuple[Decision, tuple[str, ...], tuple[str, ...]]:
    """Apply deterministic gates AFTER the Chair has produced a synthesis.

    Two policies, applied in order:

    1. **Confidence gate.** When the GPA extractor is unsure
       (``gpa_confidence < 0.5``), the LLM's accept/reject is unsafe;
       route to ``WAITLIST`` for committee review.
    2. **Below-threshold hard reject.** When the gate verdict is BELOW
       and confidence is sufficient, force ``REJECT`` regardless of what
       the Chair said. The committee's policy ("below the bar = refused")
       is mechanical and we encode it deterministically.

    Returns
    -------
    tuple[Decision, tuple[str, ...], tuple[str, ...]]
        Possibly-modified ``(decision, pros, cons)``. ``cons`` is appended
        with a one-line audit trail when an override fires.
    """
    if gpa_confidence < _LOW_GPA_CONFIDENCE:
        new_cons = (
            *cons,
            f"GPA extraction confidence too low ({gpa_confidence:.0%}) — "
            "routed to waitlist for manual review.",
        )
        return Decision.WAITLIST, pros, new_cons

    if (
        threshold_verdict is not None
        and threshold_verdict.direction is ThresholdDirection.BELOW
    ):
        new_cons = (
            *cons,
            f"GPA below SPE threshold (extracted {threshold_verdict.extracted_value} "
            f"vs threshold {threshold_verdict.threshold_value}, "
            f"gap {threshold_verdict.gap:+.2f}, system={threshold_verdict.system.value}) "
            "— hard-reject by gate.",
        )
        return Decision.REJECT, pros, new_cons

    return decision, pros, cons


def clamp_academic_strength_below_threshold(
    scorecards: tuple[AgentScorecard, ...],
    *,
    threshold_verdict: ThresholdVerdict | None,
    gpa_confidence: float,
) -> tuple[AgentScorecard, ...]:
    """Clamp Academic Evaluator's ``academic_strength`` when GPA is below threshold.

    Mirrors the post-synthesis hard-reject: if the gate says BELOW with
    sufficient confidence, the Academic scorecard's ``academic_strength``
    is capped at :data:`_BELOW_THRESHOLD_ACADEMIC_CAP`. The Chair sees the
    capped value during synthesis, so it is unlikely to argue for an
    accept that the gate would then override anyway. This mostly serves
    to keep the Chair's reasoning consistent with the final decision.

    Parameters
    ----------
    scorecards
        Specialist scorecards from Phase 1.
    threshold_verdict
        Output of :func:`agentic_admission.agents.gpa_gate.compare_to_threshold`.
    gpa_confidence
        :attr:`GpaExtraction.confidence` from the extractor.

    Returns
    -------
    tuple[AgentScorecard, ...]
        New tuple of scorecards (the input is not mutated).
    """
    if threshold_verdict is None or threshold_verdict.direction is not ThresholdDirection.BELOW:
        return scorecards
    if gpa_confidence < _LOW_GPA_CONFIDENCE:
        return scorecards

    out: list[AgentScorecard] = []
    for card in scorecards:
        if card.role is AgentRole.ACADEMIC and "academic_strength" in card.scores:
            new_scores = dict(card.scores)
            current = new_scores["academic_strength"]
            if current > _BELOW_THRESHOLD_ACADEMIC_CAP:
                new_scores["academic_strength"] = _BELOW_THRESHOLD_ACADEMIC_CAP
                out.append(card.model_copy(update={"scores": new_scores}))
                continue
        out.append(card)
    return tuple(out)


def make_skipped_reference_scorecard(reason: str) -> AgentScorecard:
    """Build a sentinel scorecard for cases where the Reference evaluator was skipped.

    The scorecard uses minimum-valid scores (1) so the
    :class:`~agentic_admission.models.evaluation.AgentScorecard` validator
    accepts it. The justifications carry an explicit ``reason`` so any
    downstream consumer (UI, audit log, Chair prompt) can distinguish a
    skipped evaluation from a genuinely weak letter.

    Parameters
    ----------
    reason
        Human-readable explanation (e.g. ``"EPFL-internal: letters not required"``).

    Returns
    -------
    AgentScorecard
        Sentinel scorecard for the Reference role.
    """
    cons = (f"Skipped: {reason}",)
    return AgentScorecard(
        role=AgentRole.REFERENCE,
        scores={"reference_quality": 1, "calibration_confidence": 1},
        justifications={
            "reference_quality": DimensionJustification(pros=(), cons=cons),
            "calibration_confidence": DimensionJustification(pros=(), cons=cons),
        },
    )


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
                lines.extend(f"  + {pro}" for pro in justification.pros)
                lines.extend(f"  - {con}" for con in justification.cons)
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
        max_tokens=4096,
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
    profile: EvaluationProfile = EXTERNAL_PROFILE,
    threshold_verdict: ThresholdVerdict | None = None,
    gpa_confidence: float = 1.0,
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
    profile
        Scoring profile applied to the composite. Also surfaces in the
        Chair's user prompt so the LLM understands which dimensions
        carry weight (e.g. reference is zero-weighted for EPFL-internal
        candidates and the prompt warns the Chair not to penalise a
        sentinel reference scorecard).
    threshold_verdict
        Result of comparing the candidate's GPA to the SPE threshold. When
        ``direction == BELOW`` (with sufficient ``gpa_confidence``), the
        decision is forced to ``REJECT`` after the LLM synthesis runs.
    gpa_confidence
        Extractor confidence in [0, 1]. Below 0.5 routes the verdict to
        ``WAITLIST`` regardless of what the LLM said.

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
        f"{dim} ({w:.0%})" for dim, w in profile.weights.items()
    )
    profile_note = (
        f"NOTE: This candidate is being scored under the {profile.name!r} profile. "
        "The composite score is computed automatically using these "
        f"weights: {weight_description}. Academic credentials carry the most "
        "weight. A strong transcript should not be penalised by a weak motivation "
        "letter."
    )
    if profile.skip_reference:
        profile_note += (
            "\n\nIMPORTANT: This candidate's reference dimensions are "
            "zero-weighted (no/insufficient recommendation letters submitted). "
            "Do NOT lower the recommendation because reference scores are 1 — "
            "the Reference scorecard is a sentinel placeholder."
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
                f"{profile_note}\n\n"
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
        max_tokens=4096,
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

    composite = compute_composite(final_scores, weights=profile.weights)
    logger.info(
        "Composite score for {} ({}): {:.2f}", candidate_id, profile.name, composite
    )

    # Derive the decision deterministically from the composite. The LLM's
    # own decision field is advisory only — in the 2025-26-spring backtest
    # it was ~40% more lenient than its own stated accept rule. The
    # composite-based rule keeps accept rates calibrated to the committee's
    # historical band.
    composite_decision = decision_from_composite(composite)
    if composite_decision is not synthesis.decision:
        logger.info(
            "Composite rule for {}: {} -> {} (composite={:.2f})",
            candidate_id,
            synthesis.decision.value,
            composite_decision.value,
            composite,
        )

    # Then layer gate overrides on top: BELOW threshold forces reject,
    # low GPA confidence forces waitlist. These take precedence over the
    # composite rule.
    final_decision, final_pros, final_cons = apply_gate_overrides(
        decision=composite_decision,
        pros=synthesis.pros,
        cons=synthesis.cons,
        threshold_verdict=threshold_verdict,
        gpa_confidence=gpa_confidence,
    )
    if final_decision is not composite_decision:
        logger.info(
            "Gate override for {}: {} -> {} (threshold={}, gpa_confidence={:.2f})",
            candidate_id,
            composite_decision.value,
            final_decision.value,
            threshold_verdict.direction.value if threshold_verdict else "n/a",
            gpa_confidence,
        )

    return PanelVerdict(
        candidate_id=candidate_id,
        scorecards=scorecards,
        debates=debates,
        final_scores=final_scores,
        composite_score=composite,
        decision=final_decision,
        justification=VerdictSummary(pros=final_pros, cons=final_cons),
    )
