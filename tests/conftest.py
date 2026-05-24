"""Shared test fixtures and helpers for the agentic_admission test suite."""

from __future__ import annotations

from agentic_admission.models.evaluation import (
    AgentRole,
    AgentScorecard,
    Decision,
    DimensionJustification,
    PanelVerdict,
    VerdictSummary,
)


def make_justification(
    pros: tuple[str, ...] = ("ok",), cons: tuple[str, ...] = ()
) -> DimensionJustification:
    """Build a DimensionJustification with sensible defaults for tests."""
    return DimensionJustification(pros=pros, cons=cons)


def make_scorecard(
    role: AgentRole,
    scores: dict[str, int],
    *,
    pros: tuple[str, ...] = ("ok",),
    cons: tuple[str, ...] = (),
) -> AgentScorecard:
    """Build an AgentScorecard whose justifications carry the same pros/cons.

    Used by tests that don't care about per-dimension justification content
    and just need a valid scorecard.
    """
    justifications = {dim: make_justification(pros=pros, cons=cons) for dim in scores}
    return AgentScorecard(role=role, scores=scores, justifications=justifications)


def make_verdict_summary(
    pros: tuple[str, ...] = ("strong overall",), cons: tuple[str, ...] = ()
) -> VerdictSummary:
    """Build a VerdictSummary with sensible defaults."""
    return VerdictSummary(pros=pros, cons=cons)


def make_panel_verdict(
    *,
    candidate_id: str = "test_candidate",
    scorecards: tuple[AgentScorecard, ...] = (),
    final_scores: dict[str, int] | None = None,
    composite_score: float = 7.5,
    decision: Decision = Decision.ACCEPT,
) -> PanelVerdict:
    """Build a PanelVerdict with sensible defaults for tests."""
    if final_scores is None:
        final_scores = {
            "academic_strength": 8,
            "institution_quality": 7,
            "reference_quality": 7,
            "calibration_confidence": 6,
            "motivation_clarity": 8,
            "program_fit": 7,
            "risk_flags": 9,
            "consistency": 8,
        }
    return PanelVerdict(
        candidate_id=candidate_id,
        scorecards=scorecards,
        debates=(),
        final_scores=final_scores,
        composite_score=composite_score,
        decision=decision,
        justification=make_verdict_summary(),
    )
