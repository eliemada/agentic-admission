"""Tests for the deterministic GPA-vs-threshold gate."""

from __future__ import annotations

import pytest

from agentic_admission.agents.gpa_gate import (
    GradingSystem,
    ThresholdDirection,
    ThresholdVerdict,
    compare_to_threshold,
    detect_grading_system,
    epfl_internal_value,
)

# ---------------------------------------------------------------------------
# Per-system parametrised cases. Each row is:
#   (gpa_value, gpa_scale, threshold, expected_direction, expected_system)
# ---------------------------------------------------------------------------

_PARAMETRIC_CASES: tuple[
    tuple[str, str, str, ThresholdDirection, GradingSystem], ...
] = (
    # US 4.0
    ("3.7", "4.0", "3.0/4.0", ThresholdDirection.ABOVE, GradingSystem.US_4),
    ("2.5", "4.0", "3.0/4.0", ThresholdDirection.BELOW, GradingSystem.US_4),
    ("3.05", "4.0", "3.0/4.0", ThresholdDirection.NEAR, GradingSystem.US_4),
    # Swiss /6
    ("5.3", "6", "4.5/6", ThresholdDirection.ABOVE, GradingSystem.SWISS_6),
    ("4.0", "6", "4.5/6", ThresholdDirection.BELOW, GradingSystem.SWISS_6),
    ("4.55", "6", "4.5/6", ThresholdDirection.NEAR, GradingSystem.SWISS_6),
    # French /20
    ("14.5", "20", "14.0/20", ThresholdDirection.ABOVE, GradingSystem.FRENCH_20),
    ("13.0", "20", "14.0/20", ThresholdDirection.BELOW, GradingSystem.FRENCH_20),
    ("14.2", "20", "14.0/20", ThresholdDirection.NEAR, GradingSystem.FRENCH_20),
    # German 1-5 (lower = better)
    ("1.5", "1", "1.7/1", ThresholdDirection.ABOVE, GradingSystem.GERMAN_1_5),
    ("2.3", "1", "1.7/1", ThresholdDirection.BELOW, GradingSystem.GERMAN_1_5),
    ("1.75", "1", "1.7/1", ThresholdDirection.NEAR, GradingSystem.GERMAN_1_5),
    # Italian /30
    ("28", "30", "28/30", ThresholdDirection.NEAR, GradingSystem.ITALIAN_30),
    ("29", "30", "28/30", ThresholdDirection.ABOVE, GradingSystem.ITALIAN_30),
    ("27", "30", "28/30", ThresholdDirection.BELOW, GradingSystem.ITALIAN_30),
    ("30 e lode", "30", "28/30", ThresholdDirection.ABOVE, GradingSystem.ITALIAN_30),
    # 30L is strictly above 30 (committee treats it as a distinction).
    ("30L", "30", "30/30", ThresholdDirection.ABOVE, GradingSystem.ITALIAN_30),
    # Indian /10 CGPA
    ("8.5", "10", "8.0/10", ThresholdDirection.ABOVE, GradingSystem.INDIAN_10),
    ("7.5", "10", "8.0/10", ThresholdDirection.BELOW, GradingSystem.INDIAN_10),
    # Percentage
    ("85%", "", "80%", ThresholdDirection.ABOVE, GradingSystem.PERCENTAGE),
    ("75", "", "80%", ThresholdDirection.BELOW, GradingSystem.PERCENTAGE),
    # UK class
    ("First", "", "2:1", ThresholdDirection.ABOVE, GradingSystem.UK_CLASS),
    ("2.2", "", "2:1", ThresholdDirection.BELOW, GradingSystem.UK_CLASS),
    ("2:1", "", "2:1", ThresholdDirection.NEAR, GradingSystem.UK_CLASS),
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("gpa_value", "gpa_scale", "threshold", "expected_direction", "expected_system"),
    _PARAMETRIC_CASES,
)
def test_compare_to_threshold_directions(
    gpa_value: str,
    gpa_scale: str,
    threshold: str,
    expected_direction: ThresholdDirection,
    expected_system: GradingSystem,
) -> None:
    """Per-system parametric coverage of ABOVE/NEAR/BELOW classification."""
    verdict = compare_to_threshold(
        gpa_value=gpa_value, gpa_scale=gpa_scale, threshold=threshold,
    )
    assert verdict.direction is expected_direction, (
        f"{gpa_value!r} vs {threshold!r}: expected {expected_direction.value}, "
        f"got {verdict.direction.value} (gap {verdict.gap:+.2f})"
    )
    assert verdict.system is expected_system


@pytest.mark.unit
class TestUnknownInputs:
    """Inputs the gate must safely classify as UNKNOWN."""

    def test_na_value(self) -> None:
        v = compare_to_threshold(gpa_value="N/A", gpa_scale="", threshold="3.0/4.0")
        assert v.direction is ThresholdDirection.UNKNOWN

    def test_empty_value(self) -> None:
        v = compare_to_threshold(gpa_value="", gpa_scale="", threshold="3.0/4.0")
        assert v.direction is ThresholdDirection.UNKNOWN

    def test_empty_threshold(self) -> None:
        v = compare_to_threshold(gpa_value="3.7", gpa_scale="4.0", threshold="")
        assert v.direction is ThresholdDirection.UNKNOWN

    def test_unparseable_value(self) -> None:
        # Garbled OCR — random non-numeric string.
        v = compare_to_threshold(
            gpa_value="--garbage--", gpa_scale="4.0", threshold="3.0/4.0",
        )
        assert v.direction is ThresholdDirection.UNKNOWN
        assert v.system is GradingSystem.US_4  # detection succeeded; parse failed

    def test_value_outside_system_range(self) -> None:
        # 4.5 in US 4.0 system is impossible — parser rejects.
        v = compare_to_threshold(
            gpa_value="4.5", gpa_scale="4.0", threshold="3.0/4.0",
        )
        assert v.direction is ThresholdDirection.UNKNOWN

    def test_unknown_system_falls_back_to_unknown(self) -> None:
        v = compare_to_threshold(
            gpa_value="hello", gpa_scale="bizarre", threshold="??",
        )
        assert v.direction is ThresholdDirection.UNKNOWN


@pytest.mark.unit
class TestSystemDetection:
    """Heuristics for picking a grading system."""

    @pytest.mark.parametrize(
        ("scale", "value", "expected"),
        [
            ("/20", "14", GradingSystem.FRENCH_20),
            ("/30", "28", GradingSystem.ITALIAN_30),
            ("CGPA", "8.5", GradingSystem.INDIAN_10),
            ("/4.0", "3.5", GradingSystem.US_4),
            ("/6", "5.3", GradingSystem.SWISS_6),
            ("/1", "1.7", GradingSystem.GERMAN_1_5),
            ("80%", "85%", GradingSystem.PERCENTAGE),
            ("First class", "", GradingSystem.UK_CLASS),
        ],
    )
    def test_explicit_anchor(
        self, scale: str, value: str, expected: GradingSystem
    ) -> None:
        assert detect_grading_system(scale, value) is expected

    def test_value_range_fallback_us(self) -> None:
        assert detect_grading_system("", "3.5") is GradingSystem.US_4

    def test_value_range_fallback_swiss(self) -> None:
        assert detect_grading_system("", "5.3") is GradingSystem.SWISS_6

    def test_value_range_fallback_indian(self) -> None:
        assert detect_grading_system("", "8.5") is GradingSystem.INDIAN_10

    def test_unknown_when_nothing_matches(self) -> None:
        assert detect_grading_system("", "nonsense") is GradingSystem.UNKNOWN


@pytest.mark.unit
class TestVerdictFormatting:
    def test_to_prompt_line_above(self) -> None:
        v = compare_to_threshold(gpa_value="3.7", gpa_scale="4.0", threshold="3.0/4.0")
        line = v.to_prompt_line()
        assert "ABOVE" in line
        assert "3.7" in line
        assert "3.0" in line

    def test_to_prompt_line_unknown_omits_values(self) -> None:
        v = compare_to_threshold(gpa_value="N/A", gpa_scale="", threshold="3.0/4.0")
        line = v.to_prompt_line()
        assert "UNKNOWN" in line


@pytest.mark.unit
class TestItalianLode:
    def test_lode_above_30(self) -> None:
        v = compare_to_threshold(gpa_value="30 e lode", gpa_scale="30", threshold="30/30")
        assert v.direction is ThresholdDirection.ABOVE
        assert v.extracted_value == 30.5

    def test_30l_alias(self) -> None:
        v = compare_to_threshold(gpa_value="30L", gpa_scale="30", threshold="30/30")
        assert v.direction is ThresholdDirection.ABOVE
        assert v.extracted_value == 30.5

    def test_cum_laude_alias(self) -> None:
        v = compare_to_threshold(
            gpa_value="30 cum laude", gpa_scale="30", threshold="30/30"
        )
        assert v.direction is ThresholdDirection.ABOVE


@pytest.mark.unit
class TestGermanInversion:
    """German scale uses 1.0 = best — gap sign must be flipped accordingly."""

    def test_above_threshold_means_lower_value(self) -> None:
        # Candidate 1.5 is BETTER than threshold 1.7.
        v = compare_to_threshold(gpa_value="1.5", gpa_scale="1", threshold="1.7/1")
        assert v.direction is ThresholdDirection.ABOVE
        assert v.gap > 0

    def test_below_threshold_means_higher_value(self) -> None:
        # Candidate 2.3 is WORSE than threshold 1.7.
        v = compare_to_threshold(gpa_value="2.3", gpa_scale="1", threshold="1.7/1")
        assert v.direction is ThresholdDirection.BELOW
        assert v.gap < 0


@pytest.mark.unit
class TestSystemMismatchFallback:
    """Cross-system comparison via gpa_normalized.

    Reproduces the Delft case: Dutch /10 transcript ("7.37"), SPE
    threshold "80%". Without the fallback, the percentage parser
    silently treats 7.37 as 7.37%, producing a false reject with gap
    -72. With gpa_normalized=73.7, comparison happens against 80% and
    returns NEAR/BELOW with a small gap.
    """

    def test_dutch_transcript_vs_percent_threshold_uses_normalized(self) -> None:
        v = compare_to_threshold(
            gpa_value="7.37",
            gpa_scale="10",
            threshold="80%",
            gpa_normalized=73.7,
        )
        assert v.system is GradingSystem.PERCENTAGE
        assert v.extracted_value == 73.7
        # 73.7 vs 80, gap -6.3 which is BELOW (NEAR window for percentage = 1.0)
        assert v.direction is ThresholdDirection.BELOW
        assert any("LLM-normalized" in n for n in v.notes)

    def test_above_after_normalization(self) -> None:
        v = compare_to_threshold(
            gpa_value="8.5",
            gpa_scale="10",
            threshold="80%",
            gpa_normalized=85.0,
        )
        assert v.direction is ThresholdDirection.ABOVE

    def test_no_normalized_falls_back_to_naive_parse(self) -> None:
        # Without gpa_normalized, the parser parses 7.37 as 7.37% and
        # returns BELOW with a huge gap. This is the LEGACY behaviour; we
        # test it to lock in that the new code path only fires when the
        # caller passes gpa_normalized.
        v = compare_to_threshold(gpa_value="7.37", gpa_scale="10", threshold="80%")
        assert v.direction is ThresholdDirection.BELOW
        assert v.extracted_value == 7.37  # parsed as percentage

    def test_systems_matching_does_not_trigger_fallback(self) -> None:
        # Candidate scale and threshold are both percentage — no fallback.
        v = compare_to_threshold(
            gpa_value="85%",
            gpa_scale="100",
            threshold="80%",
            gpa_normalized=85.0,
        )
        assert v.direction is ThresholdDirection.ABOVE
        assert v.extracted_value == 85.0
        # No mismatch note expected.
        assert not any("LLM-normalized" in n for n in v.notes)


@pytest.mark.unit
class TestEpflInternalValue:
    def test_uses_algebra_and_analysis(self) -> None:
        result = epfl_internal_value({"analysis": 4.5, "algebra": 4.0, "physics": 5.5})
        assert result == "4.250"

    def test_only_analysis_present(self) -> None:
        result = epfl_internal_value({"analysis": 4.5, "physics": 5.0})
        assert result == "4.500"

    def test_neither_present_returns_none(self) -> None:
        assert epfl_internal_value({"physics": 5.0}) is None

    def test_empty_dict_returns_none(self) -> None:
        assert epfl_internal_value({}) is None

    def test_none_returns_none(self) -> None:
        assert epfl_internal_value(None) is None


@pytest.mark.unit
class TestVerdictDataclass:
    def test_frozen(self) -> None:
        import dataclasses

        v = ThresholdVerdict(
            direction=ThresholdDirection.ABOVE,
            gap=0.5,
            confidence=0.9,
            system=GradingSystem.US_4,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            v.gap = 0.0  # type: ignore[misc]
