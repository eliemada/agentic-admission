"""Tests for the updated evaluation models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_admission.models.evaluation import (
    AgentRole,
    AgentScorecard,
    Conflict,
    DebateEntry,
    DebateTranscript,
    Decision,
    PanelVerdict,
)


class TestAgentRole:
    def test_all_five_roles_exist(self) -> None:
        roles = {r.value for r in AgentRole}
        assert roles == {"academic", "reference", "motivation", "devils_advocate", "chair"}


class TestDecision:
    def test_all_decisions_exist(self) -> None:
        decisions = {d.value for d in Decision}
        assert decisions == {"accept", "reject", "waitlist"}


class TestAgentScorecard:
    def test_frozen(self) -> None:
        card = AgentScorecard(
            role=AgentRole.ACADEMIC,
            scores={"academic_strength": 8, "institution_quality": 7},
            justifications={"academic_strength": "Strong GPA from top-tier school."},
        )
        assert card.role == AgentRole.ACADEMIC
        assert card.scores["academic_strength"] == 8

    def test_immutable(self) -> None:
        card = AgentScorecard(
            role=AgentRole.ACADEMIC,
            scores={"academic_strength": 8},
            justifications={"academic_strength": "Solid."},
        )
        try:
            card.role = AgentRole.CHAIR  # type: ignore[misc]
        except Exception:
            pass
        else:
            msg = "AgentScorecard should be frozen"
            raise AssertionError(msg)

    def test_score_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError, match="must be 1-10"):
            AgentScorecard(
                role=AgentRole.ACADEMIC,
                scores={"academic_strength": 0},
                justifications={"academic_strength": "Too low."},
            )

    def test_score_above_range_raises(self) -> None:
        with pytest.raises(ValidationError, match="must be 1-10"):
            AgentScorecard(
                role=AgentRole.ACADEMIC,
                scores={"academic_strength": 11},
                justifications={"academic_strength": "Too high."},
            )

    def test_scores_dict_is_immutable(self) -> None:
        card = AgentScorecard(
            role=AgentRole.ACADEMIC,
            scores={"academic_strength": 8},
            justifications={"academic_strength": "Good."},
        )
        with pytest.raises(TypeError):
            card.scores["academic_strength"] = 5  # type: ignore[index]

    def test_justifications_dict_is_immutable(self) -> None:
        card = AgentScorecard(
            role=AgentRole.ACADEMIC,
            scores={"academic_strength": 8},
            justifications={"academic_strength": "Good."},
        )
        with pytest.raises(TypeError):
            card.justifications["academic_strength"] = "Changed."  # type: ignore[index]


class TestConflict:
    def test_conflict_fields(self) -> None:
        conflict = Conflict(
            dimension="reference_quality",
            agents_involved=(AgentRole.REFERENCE, AgentRole.DEVILS_ADVOCATE),
            nature="Agent 2 sees strong calibrated letter; Agent 4 flags inconsistency.",
            debate_question="Is the reference letter genuinely strong after cultural adjustment?",
        )
        assert conflict.dimension == "reference_quality"
        assert len(conflict.agents_involved) == 2


class TestDebateTranscript:
    def test_entries(self) -> None:
        entry = DebateEntry(
            role=AgentRole.REFERENCE,
            round_number=1,
            argument="The letter is strong after US calibration.",
        )
        transcript = DebateTranscript(conflict_dimension="reference_quality", entries=(entry,))
        assert len(transcript.entries) == 1


class TestPanelVerdict:
    def test_verdict_fields(self) -> None:
        verdict = PanelVerdict(
            candidate_id="2024-25_round1_42",
            scorecards=(),
            debates=(),
            final_scores={
                "academic_strength": 8,
                "institution_quality": 7,
                "reference_quality": 6,
                "calibration_confidence": 7,
                "motivation_clarity": 8,
                "program_fit": 7,
                "risk_flags": 9,
                "consistency": 8,
            },
            composite_score=7.5,
            decision=Decision.ACCEPT,
            justification="Strong academic profile with well-calibrated references.",
        )
        assert verdict.decision == Decision.ACCEPT
        assert len(verdict.final_scores) == 8

    def test_verdict_final_scores_validated(self) -> None:
        with pytest.raises(ValidationError, match="must be 1-10"):
            PanelVerdict(
                candidate_id="2024-25_round1_42",
                scorecards=(),
                debates=(),
                final_scores={"academic_strength": 0},
                composite_score=5.0,
                decision=Decision.REJECT,
                justification="Score out of range.",
            )

    def test_verdict_composite_score_range(self) -> None:
        with pytest.raises(ValidationError, match="composite_score must be 1\\.0-10\\.0"):
            PanelVerdict(
                candidate_id="2024-25_round1_42",
                scorecards=(),
                debates=(),
                final_scores={"academic_strength": 5},
                composite_score=0.5,
                decision=Decision.REJECT,
                justification="Composite out of range.",
            )

    def test_verdict_final_scores_immutable(self) -> None:
        verdict = PanelVerdict(
            candidate_id="2024-25_round1_42",
            scorecards=(),
            debates=(),
            final_scores={"academic_strength": 8},
            composite_score=8.0,
            decision=Decision.ACCEPT,
            justification="Strong.",
        )
        with pytest.raises(TypeError):
            verdict.final_scores["academic_strength"] = 5  # type: ignore[index]
