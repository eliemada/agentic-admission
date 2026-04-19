"""Tests for the GPA extraction agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from agentic_admission.agents.gpa_extractor import GpaExtraction, extract_gpa

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


# ---------------------------------------------------------------------------
# GpaExtraction model tests
# ---------------------------------------------------------------------------


class TestGpaExtractionModel:
    """Unit tests for the GpaExtraction Pydantic model."""

    def test_valid_construction(self):
        gpa = GpaExtraction(
            gpa_value="3.7",
            gpa_scale="4.0",
            gpa_normalized=92.5,
            grading_system="US 4.0",
            institution_name="MIT",
            degree_name="BSc Computer Science",
            notable_courses="Strong in algorithms, weaker in databases.",
            trajectory="improving",
            confidence=0.9,
        )
        assert gpa.gpa_value == "3.7"
        assert gpa.gpa_normalized == 92.5
        assert gpa.confidence == 0.9

    def test_frozen_immutability(self):
        gpa = GpaExtraction(
            gpa_value="14.5",
            gpa_scale="20",
            gpa_normalized=72.5,
            grading_system="French /20",
            institution_name="Ecole Polytechnique",
            degree_name="BSc Mathematics",
            notable_courses="Excellent in analysis.",
            trajectory="stable",
            confidence=0.85,
        )
        with pytest.raises(Exception):  # noqa: B017, PT011
            gpa.gpa_value = "15.0"  # type: ignore[misc]

    def test_normalized_bounds_lower(self):
        with pytest.raises(Exception):  # noqa: B017, PT011
            GpaExtraction(
                gpa_value="1.0",
                gpa_scale="4.0",
                gpa_normalized=-5.0,
                grading_system="US 4.0",
                institution_name="Test",
                degree_name="BSc",
                notable_courses="",
                trajectory="stable",
                confidence=0.5,
            )

    def test_normalized_bounds_upper(self):
        with pytest.raises(Exception):  # noqa: B017, PT011
            GpaExtraction(
                gpa_value="4.0",
                gpa_scale="4.0",
                gpa_normalized=105.0,
                grading_system="US 4.0",
                institution_name="Test",
                degree_name="BSc",
                notable_courses="",
                trajectory="stable",
                confidence=0.5,
            )

    def test_confidence_bounds(self):
        with pytest.raises(Exception):  # noqa: B017, PT011
            GpaExtraction(
                gpa_value="3.0",
                gpa_scale="4.0",
                gpa_normalized=75.0,
                grading_system="US 4.0",
                institution_name="Test",
                degree_name="BSc",
                notable_courses="",
                trajectory="stable",
                confidence=1.5,
            )


# ---------------------------------------------------------------------------
# extract_gpa function tests
# ---------------------------------------------------------------------------

_SAMPLE_GPA = GpaExtraction(
    gpa_value="3.7",
    gpa_scale="4.0",
    gpa_normalized=92.5,
    grading_system="US 4.0",
    institution_name="MIT",
    degree_name="BSc Computer Science",
    notable_courses="Strong across the board.",
    trajectory="stable",
    confidence=0.9,
)


@pytest.fixture
def _mock_gpa_llm(mocker: MockerFixture) -> None:
    """Patch ``complete`` to return a valid GpaExtraction without hitting an LLM."""

    async def fake_complete(
        *, messages: Any, response_model: Any, model: Any, base_url: Any, **kwargs: Any,
    ) -> GpaExtraction:
        return response_model.model_validate(_SAMPLE_GPA.model_dump())

    mocker.patch("agentic_admission.agents.gpa_extractor.complete", side_effect=fake_complete)


class TestExtractGpaEmptyInput:
    """Test extract_gpa with empty transcript text (no LLM call needed)."""

    async def test_empty_string_returns_na(self):
        result = await extract_gpa("", model="test", base_url="http://test")
        assert result.gpa_value == "N/A"
        assert result.gpa_normalized == 0.0
        assert result.confidence == 0.0

    async def test_whitespace_only_returns_na(self):
        result = await extract_gpa("   \n  ", model="test", base_url="http://test")
        assert result.gpa_value == "N/A"
        assert result.gpa_scale == "N/A"
        assert result.grading_system == "unknown"


@pytest.mark.usefixtures("_mock_gpa_llm")
class TestExtractGpaWithLLM:
    """Test extract_gpa with mocked LLM responses."""

    async def test_returns_gpa_extraction(self):
        result = await extract_gpa(
            "GPA: 3.7/4.0 at MIT, BSc Computer Science", model="test", base_url="http://test",
        )
        assert isinstance(result, GpaExtraction)
        assert result.gpa_value == "3.7"
        assert result.gpa_scale == "4.0"

    async def test_normalized_score(self):
        result = await extract_gpa(
            "Transcript from MIT with 3.7/4.0", model="test", base_url="http://test",
        )
        assert result.gpa_normalized == 92.5

    async def test_institution_extracted(self):
        result = await extract_gpa(
            "Massachusetts Institute of Technology transcript", model="test", base_url="http://test",
        )
        assert result.institution_name == "MIT"

    async def test_confidence_in_range(self):
        result = await extract_gpa("GPA: 3.7/4.0", model="test", base_url="http://test")
        assert 0.0 <= result.confidence <= 1.0
