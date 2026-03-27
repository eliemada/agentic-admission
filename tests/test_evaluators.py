"""Tests for specialist evaluator agent functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from agentic_admission.agents.evaluators import (
    evaluate_academic,
    evaluate_devils_advocate,
    evaluate_motivation,
    evaluate_reference,
)
from agentic_admission.models.evaluation import AgentRole, AgentScorecard

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def _mock_llm(mocker: MockerFixture) -> None:
    """Patch ``complete`` to return a valid AgentScorecard without hitting an LLM."""
    scorecard = AgentScorecard(
        role=AgentRole.ACADEMIC,
        scores={"academic_strength": 7, "institution_quality": 6},
        justifications={
            "academic_strength": "Solid GPA.",
            "institution_quality": "Mid-tier institution.",
        },
    )

    async def fake_complete(
        *, messages: Any, response_model: Any, model: Any, base_url: Any, **kwargs: Any
    ) -> AgentScorecard:
        return response_model.model_validate(scorecard.model_dump())

    mocker.patch("agentic_admission.agents.evaluators.complete", side_effect=fake_complete)


@pytest.mark.usefixtures("_mock_llm")
class TestEvaluateAcademic:
    async def test_returns_scorecard(self):
        result = await evaluate_academic(
            transcript_text="GPA: 3.8/4.0, BS Computer Science",
            model="test",
            base_url="http://test",
        )
        assert isinstance(result, AgentScorecard)
        assert result.role == AgentRole.ACADEMIC

    async def test_scorecard_has_required_dimensions(self):
        result = await evaluate_academic(
            transcript_text="GPA: 3.8/4.0", model="test", base_url="http://test"
        )
        assert "academic_strength" in result.scores
        assert "institution_quality" in result.scores


@pytest.mark.usefixtures("_mock_llm")
class TestEvaluateReference:
    async def test_returns_scorecard(self):
        result = await evaluate_reference(
            letters_text="Dear committee, this student is exceptional...",
            calibration_context="US university avg sentiment: 0.85",
            historical_letters="[Letter 1] ...",
            model="test",
            base_url="http://test",
        )
        assert isinstance(result, AgentScorecard)


@pytest.mark.usefixtures("_mock_llm")
class TestEvaluateMotivation:
    async def test_returns_scorecard(self):
        result = await evaluate_motivation(
            motivation_text="I want to join MTE because...",
            cv_text="Experience: 2 years at Google...",
            model="test",
            base_url="http://test",
        )
        assert isinstance(result, AgentScorecard)


@pytest.mark.usefixtures("_mock_llm")
class TestEvaluateDevilsAdvocate:
    async def test_returns_scorecard(self):
        result = await evaluate_devils_advocate(
            full_dossier_text="[Transcript] ... [Letters] ... [CV] ...",
            model="test",
            base_url="http://test",
        )
        assert isinstance(result, AgentScorecard)
