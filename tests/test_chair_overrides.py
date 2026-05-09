"""Tests for the deterministic chair override helpers.

These cover the post-synthesis hard-reject and the academic-strength clamp
that fire when the GPA gate verdict is BELOW. The full ``synthesize`` is
not exercised here (that needs an LLM mock — see ``test_chair.py``); we
test the deterministic primitives directly.
"""

from __future__ import annotations

import pytest

from agentic_admission.agents.chair import (
    ACCEPT_COMPOSITE_FLOOR,
    WAITLIST_COMPOSITE_FLOOR,
    apply_gate_overrides,
    clamp_academic_strength_below_threshold,
    decision_from_composite,
)
from agentic_admission.agents.gpa_gate import GradingSystem, ThresholdDirection, ThresholdVerdict
from agentic_admission.models.evaluation import (
    AgentRole,
    AgentScorecard,
    Decision,
    DimensionJustification,
)


def _verdict(
    direction: ThresholdDirection,
    *,
    extracted: float = 3.5,
    threshold: float = 4.0,
    gap: float = -0.5,
) -> ThresholdVerdict:
    return ThresholdVerdict(
        direction=direction,
        gap=gap,
        confidence=0.9,
        system=GradingSystem.US_4,
        extracted_value=extracted,
        threshold_value=threshold,
    )


def _academic(score: int) -> AgentScorecard:
    return AgentScorecard(
        role=AgentRole.ACADEMIC,
        scores={"academic_strength": score, "institution_quality": 7},
        justifications={
            "academic_strength": DimensionJustification(pros=("strong",), cons=()),
            "institution_quality": DimensionJustification(pros=("priority",), cons=()),
        },
    )


@pytest.mark.unit
class TestApplyGateOverrides:
    def test_below_threshold_forces_reject(self) -> None:
        decision, pros, cons = apply_gate_overrides(
            decision=Decision.ACCEPT,
            pros=("strong transcript",),
            cons=(),
            threshold_verdict=_verdict(ThresholdDirection.BELOW),
            gpa_confidence=0.9,
        )
        assert decision is Decision.REJECT
        assert any("below SPE threshold" in c for c in cons)
        assert pros == ("strong transcript",)

    def test_above_threshold_keeps_decision(self) -> None:
        decision, _, cons = apply_gate_overrides(
            decision=Decision.ACCEPT,
            pros=(),
            cons=(),
            threshold_verdict=_verdict(ThresholdDirection.ABOVE, gap=+0.7),
            gpa_confidence=0.9,
        )
        assert decision is Decision.ACCEPT
        assert cons == ()

    def test_near_threshold_keeps_decision(self) -> None:
        decision, _, _ = apply_gate_overrides(
            decision=Decision.WAITLIST,
            pros=(),
            cons=(),
            threshold_verdict=_verdict(ThresholdDirection.NEAR, gap=+0.05),
            gpa_confidence=0.9,
        )
        assert decision is Decision.WAITLIST

    def test_low_confidence_routes_to_waitlist(self) -> None:
        decision, _, cons = apply_gate_overrides(
            decision=Decision.ACCEPT,
            pros=(),
            cons=(),
            threshold_verdict=_verdict(ThresholdDirection.ABOVE, gap=+0.7),
            gpa_confidence=0.3,
        )
        assert decision is Decision.WAITLIST
        assert any("confidence too low" in c for c in cons)

    def test_low_confidence_overrides_below_threshold(self) -> None:
        # When the extractor itself is unsure, we cannot trust the BELOW
        # verdict either — waitlist for human review.
        decision, _, cons = apply_gate_overrides(
            decision=Decision.ACCEPT,
            pros=(),
            cons=(),
            threshold_verdict=_verdict(ThresholdDirection.BELOW),
            gpa_confidence=0.3,
        )
        assert decision is Decision.WAITLIST
        assert any("confidence too low" in c for c in cons)

    def test_no_verdict_keeps_decision(self) -> None:
        decision, _, cons = apply_gate_overrides(
            decision=Decision.ACCEPT,
            pros=(),
            cons=(),
            threshold_verdict=None,
            gpa_confidence=1.0,
        )
        assert decision is Decision.ACCEPT
        assert cons == ()

    def test_unknown_verdict_keeps_decision(self) -> None:
        decision, _, _ = apply_gate_overrides(
            decision=Decision.ACCEPT,
            pros=(),
            cons=(),
            threshold_verdict=ThresholdVerdict(
                direction=ThresholdDirection.UNKNOWN,
                gap=0.0,
                confidence=0.0,
                system=GradingSystem.UNKNOWN,
            ),
            gpa_confidence=0.9,
        )
        assert decision is Decision.ACCEPT


@pytest.mark.unit
class TestDecisionFromComposite:
    """Composite-score → Decision mapping (calibrated against committee history)."""

    def test_high_composite_accepts(self) -> None:
        assert decision_from_composite(8.5) is Decision.ACCEPT
        assert decision_from_composite(8.0) is Decision.ACCEPT
        assert decision_from_composite(10.0) is Decision.ACCEPT

    def test_borderline_waitlists(self) -> None:
        assert decision_from_composite(7.99) is Decision.WAITLIST
        assert decision_from_composite(7.5) is Decision.WAITLIST

    def test_low_composite_rejects(self) -> None:
        assert decision_from_composite(7.49) is Decision.REJECT
        assert decision_from_composite(5.0) is Decision.REJECT
        assert decision_from_composite(1.0) is Decision.REJECT

    def test_thresholds_are_documented_constants(self) -> None:
        # Lock the calibration so a future change has to be intentional.
        assert ACCEPT_COMPOSITE_FLOOR == 8.0
        assert WAITLIST_COMPOSITE_FLOOR == 7.5

    def test_gate_override_can_override_composite_decision(self) -> None:
        # Composite says accept, but BELOW threshold forces reject.
        decision, _, cons = apply_gate_overrides(
            decision=Decision.ACCEPT,
            pros=(),
            cons=(),
            threshold_verdict=_verdict(ThresholdDirection.BELOW),
            gpa_confidence=0.9,
        )
        assert decision is Decision.REJECT
        assert any("below SPE threshold" in c for c in cons)


@pytest.mark.unit
class TestClampAcademicStrength:
    def test_clamps_above_cap(self) -> None:
        cards = (_academic(8),)
        out = clamp_academic_strength_below_threshold(
            cards,
            threshold_verdict=_verdict(ThresholdDirection.BELOW),
            gpa_confidence=0.9,
        )
        assert out[0].scores["academic_strength"] == 4

    def test_does_not_raise_below_cap(self) -> None:
        cards = (_academic(2),)
        out = clamp_academic_strength_below_threshold(
            cards,
            threshold_verdict=_verdict(ThresholdDirection.BELOW),
            gpa_confidence=0.9,
        )
        assert out[0].scores["academic_strength"] == 2

    def test_no_op_when_above_threshold(self) -> None:
        cards = (_academic(8),)
        out = clamp_academic_strength_below_threshold(
            cards,
            threshold_verdict=_verdict(ThresholdDirection.ABOVE, gap=+0.7),
            gpa_confidence=0.9,
        )
        assert out is cards
        assert out[0].scores["academic_strength"] == 8

    def test_no_op_when_low_confidence(self) -> None:
        # Low confidence: don't trust the gate, leave the score alone
        # (apply_gate_overrides will route to waitlist instead).
        cards = (_academic(8),)
        out = clamp_academic_strength_below_threshold(
            cards,
            threshold_verdict=_verdict(ThresholdDirection.BELOW),
            gpa_confidence=0.3,
        )
        assert out is cards
        assert out[0].scores["academic_strength"] == 8

    def test_no_op_when_no_verdict(self) -> None:
        cards = (_academic(8),)
        out = clamp_academic_strength_below_threshold(
            cards,
            threshold_verdict=None,
            gpa_confidence=1.0,
        )
        assert out is cards

    def test_only_academic_card_modified(self) -> None:
        from agentic_admission.models.evaluation import AgentRole, AgentScorecard

        ref = AgentScorecard(
            role=AgentRole.REFERENCE,
            scores={"reference_quality": 9, "calibration_confidence": 8},
            justifications={
                "reference_quality": DimensionJustification(pros=(), cons=()),
                "calibration_confidence": DimensionJustification(pros=(), cons=()),
            },
        )
        cards = (_academic(8), ref)
        out = clamp_academic_strength_below_threshold(
            cards,
            threshold_verdict=_verdict(ThresholdDirection.BELOW),
            gpa_confidence=0.9,
        )
        assert out[0].scores["academic_strength"] == 4
        assert out[1] is ref  # unchanged
        assert out[1].scores["reference_quality"] == 9
