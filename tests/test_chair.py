"""Tests for the Chair agent functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from agentic_admission.agents.chair import detect_disagreements, moderate_debate, synthesize
from agentic_admission.models.evaluation import (
    AgentRole,
    AgentScorecard,
    Conflict,
    DebateTranscript,
    Decision,
    PanelVerdict,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def _make_scorecard(role: AgentRole, scores: dict[str, int]) -> AgentScorecard:
    return AgentScorecard(
        role=role, scores=scores, justifications=dict.fromkeys(scores, "test justification")
    )


SAMPLE_SCORECARDS = (
    _make_scorecard(AgentRole.ACADEMIC, {"academic_strength": 8, "institution_quality": 7}),
    _make_scorecard(AgentRole.REFERENCE, {"reference_quality": 7, "calibration_confidence": 6}),
    _make_scorecard(AgentRole.MOTIVATION, {"motivation_clarity": 8, "program_fit": 7}),
    _make_scorecard(AgentRole.DEVILS_ADVOCATE, {"risk_flags": 9, "consistency": 8}),
)


class TestDetectDisagreements:
    @pytest.fixture
    def _mock_llm_conflicts(self, mocker: MockerFixture) -> None:
        conflict = Conflict(
            dimension="reference_quality",
            agents_involved=(AgentRole.REFERENCE, AgentRole.DEVILS_ADVOCATE),
            nature="Conflicting interpretation of letter quality.",
            debate_question="Is this letter genuinely strong?",
        )

        async def fake_complete(
            *, messages: Any, response_model: Any, model: Any, base_url: Any, **kwargs: Any
        ) -> Any:
            from agentic_admission.agents.chair import DisagreementReport

            return DisagreementReport(conflicts=(conflict,))

        mocker.patch("agentic_admission.agents.chair.complete", side_effect=fake_complete)

    @pytest.mark.usefixtures("_mock_llm_conflicts")
    async def test_returns_conflict_list(self):
        conflicts = await detect_disagreements(
            scorecards=SAMPLE_SCORECARDS, model="test", base_url="http://test"
        )
        assert len(conflicts) == 1
        assert conflicts[0].dimension == "reference_quality"


class TestModerateDebate:
    @pytest.fixture
    def _mock_llm_debate(self, mocker: MockerFixture) -> None:
        async def fake_complete(
            *, messages: Any, response_model: Any, model: Any, base_url: Any, **kwargs: Any
        ) -> AgentScorecard:
            return AgentScorecard(
                role=AgentRole.REFERENCE,
                scores={"reference_quality": 7},
                justifications={"reference_quality": "After debate, I maintain my position."},
            )

        mocker.patch("agentic_admission.agents.chair.complete", side_effect=fake_complete)

    @pytest.mark.usefixtures("_mock_llm_debate")
    async def test_returns_debate_transcript(self):
        conflict = Conflict(
            dimension="reference_quality",
            agents_involved=(AgentRole.REFERENCE, AgentRole.DEVILS_ADVOCATE),
            nature="test conflict",
            debate_question="Is this letter strong?",
        )
        transcript = await moderate_debate(
            conflict=conflict, scorecards=SAMPLE_SCORECARDS, model="test", base_url="http://test"
        )
        assert isinstance(transcript, DebateTranscript)
        assert transcript.conflict_dimension == "reference_quality"


class TestSynthesize:
    @pytest.fixture
    def _mock_llm_verdict(self, mocker: MockerFixture) -> None:
        verdict = PanelVerdict(
            candidate_id="test_candidate",
            scorecards=(),
            debates=(),
            final_scores={
                "academic_strength": 8,
                "institution_quality": 7,
                "reference_quality": 7,
                "calibration_confidence": 6,
                "motivation_clarity": 8,
                "program_fit": 7,
                "risk_flags": 9,
                "consistency": 8,
            },
            composite_score=7.5,
            decision=Decision.ACCEPT,
            justification="Strong candidate overall.",
        )

        async def fake_complete(
            *, messages: Any, response_model: Any, model: Any, base_url: Any, **kwargs: Any
        ) -> PanelVerdict:
            return verdict

        mocker.patch("agentic_admission.agents.chair.complete", side_effect=fake_complete)

    @pytest.mark.usefixtures("_mock_llm_verdict")
    async def test_returns_panel_verdict(self):
        verdict = await synthesize(
            candidate_id="test_candidate",
            scorecards=SAMPLE_SCORECARDS,
            debates=(),
            model="test",
            base_url="http://test",
        )
        assert isinstance(verdict, PanelVerdict)
        assert verdict.decision == Decision.ACCEPT
        assert len(verdict.final_scores) == 8
