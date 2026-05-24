"""Tests for specialist evaluator agent functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from agentic_admission.agents.evaluators import (
    AcademicResponse,
    DevilsAdvocateResponse,
    MotivationResponse,
    ReferenceResponse,
    evaluate_academic,
    evaluate_devils_advocate,
    evaluate_motivation,
    evaluate_reference,
)
from agentic_admission.models.evaluation import AgentRole, AgentScorecard

if TYPE_CHECKING:
    from pydantic import BaseModel
    from pytest_mock import MockerFixture


_RESPONSE_PAYLOADS: dict[type, dict[str, Any]] = {
    AcademicResponse: {
        "academic_strength": 7,
        "academic_strength_justification": {"pros": ["solid GPA"], "cons": []},
        "institution_quality": 6,
        "institution_quality_justification": {"pros": ["mid-tier"], "cons": []},
    },
    ReferenceResponse: {
        "reference_quality": 7,
        "reference_quality_justification": {"pros": ["specific letter"], "cons": []},
        "calibration_confidence": 6,
        "calibration_confidence_justification": {"pros": ["clear region"], "cons": []},
    },
    MotivationResponse: {
        "motivation_clarity": 8,
        "motivation_clarity_justification": {"pros": ["clear goals"], "cons": []},
        "program_fit": 7,
        "program_fit_justification": {"pros": ["aligned background"], "cons": []},
    },
    DevilsAdvocateResponse: {
        "risk_flags": 9,
        "risk_flags_justification": {"pros": ["no fraud signals"], "cons": []},
        "consistency": 8,
        "consistency_justification": {"pros": ["narrative aligns"], "cons": []},
    },
}


@pytest.fixture
def _mock_llm(mocker: MockerFixture) -> None:
    """Patch ``complete`` to return a per-evaluator response model."""

    async def fake_complete(
        *, messages: Any, response_model: type[BaseModel], model: Any, base_url: Any, **kwargs: Any
    ) -> BaseModel:
        payload = _RESPONSE_PAYLOADS.get(response_model)
        if payload is None:
            msg = f"No fixture payload for {response_model.__name__}"
            raise AssertionError(msg)
        return response_model.model_validate(payload)

    mocker.patch("agentic_admission.agents.evaluators.complete", side_effect=fake_complete)


@pytest.mark.usefixtures("_mock_llm")
class TestEvaluateAcademic:
    async def test_returns_scorecard(self) -> None:
        result = await evaluate_academic(
            transcript_text="GPA: 3.8/4.0, BS Computer Science",
            model="test",
            base_url="http://test",
        )
        assert isinstance(result, AgentScorecard)
        assert result.role == AgentRole.ACADEMIC

    async def test_scorecard_has_required_dimensions(self) -> None:
        result = await evaluate_academic(
            transcript_text="GPA: 3.8/4.0", model="test", base_url="http://test"
        )
        assert "academic_strength" in result.scores
        assert "institution_quality" in result.scores


@pytest.mark.usefixtures("_mock_llm")
class TestEvaluateReference:
    async def test_returns_scorecard(self) -> None:
        result = await evaluate_reference(
            letters_text="Dear committee, this student is exceptional...",
            calibration_context="US university avg sentiment: 0.85",
            historical_letters="[Letter 1] ...",
            model="test",
            base_url="http://test",
        )
        assert isinstance(result, AgentScorecard)
        assert result.role == AgentRole.REFERENCE


@pytest.mark.usefixtures("_mock_llm")
class TestEvaluateMotivation:
    async def test_returns_scorecard(self) -> None:
        result = await evaluate_motivation(
            motivation_text="I want to join MTE because...",
            cv_text="Experience: 2 years at Google...",
            model="test",
            base_url="http://test",
        )
        assert isinstance(result, AgentScorecard)
        assert result.role == AgentRole.MOTIVATION


@pytest.mark.usefixtures("_mock_llm")
class TestEvaluateDevilsAdvocate:
    async def test_returns_scorecard(self) -> None:
        result = await evaluate_devils_advocate(
            full_dossier_text="[Transcript] ... [Letters] ... [CV] ...",
            model="test",
            base_url="http://test",
        )
        assert isinstance(result, AgentScorecard)
        assert result.role == AgentRole.DEVILS_ADVOCATE

    async def test_epfl_internal_context_prepended(self, mocker: MockerFixture) -> None:
        captured: dict[str, Any] = {}

        async def fake_complete(
            *,
            messages: Any,
            response_model: type[BaseModel],
            model: Any,
            base_url: Any,
            **kwargs: Any,
        ) -> BaseModel:
            captured["system"] = messages[0].content
            return response_model.model_validate(_RESPONSE_PAYLOADS[DevilsAdvocateResponse])

        mocker.patch("agentic_admission.agents.evaluators.complete", side_effect=fake_complete)
        await evaluate_devils_advocate(
            full_dossier_text="...", model="test", base_url="http://test", is_epfl_internal=True
        )
        assert "EPFL-internal candidate context" in captured["system"]
