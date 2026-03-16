"""Tests for the deliberation orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from agentic_admission.agents.orchestrator import evaluate_candidate
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


def _make_scorecard(role: AgentRole) -> AgentScorecard:
    """Build a deterministic scorecard for the given role."""
    scores = {
        AgentRole.ACADEMIC: {"academic_strength": 8, "institution_quality": 7},
        AgentRole.REFERENCE: {"reference_quality": 7, "calibration_confidence": 6},
        AgentRole.MOTIVATION: {"motivation_clarity": 8, "program_fit": 7},
        AgentRole.DEVILS_ADVOCATE: {"risk_flags": 9, "consistency": 8},
    }
    return AgentScorecard(
        role=role, scores=scores[role], justifications=dict.fromkeys(scores[role], "test")
    )


_DEFAULT_FINAL_SCORES = {
    "academic_strength": 8,
    "institution_quality": 7,
    "reference_quality": 7,
    "calibration_confidence": 6,
    "motivation_clarity": 8,
    "program_fit": 7,
    "risk_flags": 9,
    "consistency": 8,
}

_DEFAULT_CALL_KWARGS: dict[str, str] = {
    "candidate_id": "2024-25_round1_42",
    "transcript_text": "GPA: 3.8/4.0",
    "letters_text": "Dear committee...",
    "calibration_context": "US avg: 0.85",
    "historical_letters": "[Letter 1]...",
    "motivation_text": "I want to join MTE...",
    "cv_text": "Experience: Google...",
    "full_dossier_text": "[All documents]...",
    "model": "test",
    "base_url": "http://test",
}


@pytest.fixture
def _mock_agents_no_conflicts(mocker: MockerFixture) -> None:
    """Patch all agent functions -- no disagreements detected."""
    for fn_name in (
        "evaluate_academic",
        "evaluate_reference",
        "evaluate_motivation",
        "evaluate_devils_advocate",
    ):
        role = {
            "evaluate_academic": AgentRole.ACADEMIC,
            "evaluate_reference": AgentRole.REFERENCE,
            "evaluate_motivation": AgentRole.MOTIVATION,
            "evaluate_devils_advocate": AgentRole.DEVILS_ADVOCATE,
        }[fn_name]

        async def _fake(*, _role: AgentRole = role, **kwargs: Any) -> AgentScorecard:
            return _make_scorecard(_role)

        mocker.patch(f"agentic_admission.agents.orchestrator.{fn_name}", side_effect=_fake)

    async def _fake_detect(**kwargs: Any) -> tuple[()]:
        return ()

    mocker.patch(
        "agentic_admission.agents.orchestrator.detect_disagreements", side_effect=_fake_detect
    )

    async def _fake_synthesize(
        *, candidate_id: str, scorecards: Any, debates: Any, model: str, base_url: str
    ) -> PanelVerdict:
        return PanelVerdict(
            candidate_id=candidate_id,
            scorecards=scorecards,
            debates=debates,
            final_scores=_DEFAULT_FINAL_SCORES,
            composite_score=7.5,
            decision=Decision.ACCEPT,
            justification="Strong candidate.",
        )

    mocker.patch("agentic_admission.agents.orchestrator.synthesize", side_effect=_fake_synthesize)


@pytest.fixture
def _mock_agents_with_conflicts(mocker: MockerFixture) -> None:
    """Patch all agent functions -- one conflict triggers a debate."""
    for fn_name in (
        "evaluate_academic",
        "evaluate_reference",
        "evaluate_motivation",
        "evaluate_devils_advocate",
    ):
        role = {
            "evaluate_academic": AgentRole.ACADEMIC,
            "evaluate_reference": AgentRole.REFERENCE,
            "evaluate_motivation": AgentRole.MOTIVATION,
            "evaluate_devils_advocate": AgentRole.DEVILS_ADVOCATE,
        }[fn_name]

        async def _fake(*, _role: AgentRole = role, **kwargs: Any) -> AgentScorecard:
            return _make_scorecard(_role)

        mocker.patch(f"agentic_admission.agents.orchestrator.{fn_name}", side_effect=_fake)

    conflict = Conflict(
        dimension="reference_quality",
        agents_involved=(AgentRole.REFERENCE, AgentRole.DEVILS_ADVOCATE),
        nature="Conflicting interpretation of letter quality.",
        debate_question="Is this letter genuinely strong?",
    )

    async def _fake_detect(**kwargs: Any) -> tuple[Conflict, ...]:
        return (conflict,)

    mocker.patch(
        "agentic_admission.agents.orchestrator.detect_disagreements", side_effect=_fake_detect
    )

    debate_transcript = DebateTranscript(conflict_dimension="reference_quality", entries=())

    async def _fake_moderate(**kwargs: Any) -> DebateTranscript:
        return debate_transcript

    mocker.patch(
        "agentic_admission.agents.orchestrator.moderate_debate", side_effect=_fake_moderate
    )

    async def _fake_synthesize(
        *, candidate_id: str, scorecards: Any, debates: Any, model: str, base_url: str
    ) -> PanelVerdict:
        return PanelVerdict(
            candidate_id=candidate_id,
            scorecards=scorecards,
            debates=debates,
            final_scores=_DEFAULT_FINAL_SCORES,
            composite_score=7.5,
            decision=Decision.WAITLIST,
            justification="Borderline after debate.",
        )

    mocker.patch("agentic_admission.agents.orchestrator.synthesize", side_effect=_fake_synthesize)


@pytest.mark.usefixtures("_mock_agents_no_conflicts")
class TestEvaluateCandidateNoConflicts:
    async def test_returns_panel_verdict(self):
        verdict = await evaluate_candidate(**_DEFAULT_CALL_KWARGS)
        assert isinstance(verdict, PanelVerdict)
        assert verdict.candidate_id == "2024-25_round1_42"
        assert verdict.decision == Decision.ACCEPT

    async def test_all_four_scorecards_present(self):
        verdict = await evaluate_candidate(**_DEFAULT_CALL_KWARGS)
        roles = {card.role for card in verdict.scorecards}
        assert roles == {
            AgentRole.ACADEMIC,
            AgentRole.REFERENCE,
            AgentRole.MOTIVATION,
            AgentRole.DEVILS_ADVOCATE,
        }

    async def test_no_debates_when_no_conflicts(self):
        verdict = await evaluate_candidate(**_DEFAULT_CALL_KWARGS)
        assert verdict.debates == ()

    async def test_composite_score_is_float(self):
        verdict = await evaluate_candidate(**_DEFAULT_CALL_KWARGS)
        assert isinstance(verdict.composite_score, float)

    async def test_final_scores_has_eight_dimensions(self):
        verdict = await evaluate_candidate(**_DEFAULT_CALL_KWARGS)
        assert len(verdict.final_scores) == 8


@pytest.mark.usefixtures("_mock_agents_with_conflicts")
class TestEvaluateCandidateWithConflicts:
    async def test_returns_panel_verdict_after_debate(self):
        verdict = await evaluate_candidate(**_DEFAULT_CALL_KWARGS)
        assert isinstance(verdict, PanelVerdict)
        assert verdict.decision == Decision.WAITLIST

    async def test_debates_present_when_conflicts_detected(self):
        verdict = await evaluate_candidate(**_DEFAULT_CALL_KWARGS)
        assert len(verdict.debates) == 1
        assert verdict.debates[0].conflict_dimension == "reference_quality"

    async def test_scorecards_still_present_with_conflicts(self):
        verdict = await evaluate_candidate(**_DEFAULT_CALL_KWARGS)
        assert len(verdict.scorecards) == 4
