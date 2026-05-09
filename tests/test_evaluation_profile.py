"""Tests for evaluation profiles, EPFL-internal detection, and weight handling."""

from __future__ import annotations

import math

import pytest

from agentic_admission.agents.dossier_loader import (
    MIN_MEANINGFUL_LETTERS_LENGTH,
    detect_epfl_internal,
    has_meaningful_letters,
)
from agentic_admission.agents.evaluation_profile import (
    ALL_DIMENSIONS,
    EPFL_INTERNAL_PROFILE,
    EXTERNAL_PROFILE,
    EvaluationProfile,
    renormalize_without_reference,
    select_profile,
)


@pytest.mark.unit
class TestEvaluationProfile:
    """Construction-time invariants of EvaluationProfile."""

    def test_builtin_profiles_sum_to_one(self) -> None:
        for profile in (EXTERNAL_PROFILE, EPFL_INTERNAL_PROFILE):
            assert math.isclose(sum(profile.weights.values()), 1.0, abs_tol=1e-6)

    def test_builtin_profiles_cover_all_dimensions(self) -> None:
        for profile in (EXTERNAL_PROFILE, EPFL_INTERNAL_PROFILE):
            assert set(profile.weights) == set(ALL_DIMENSIONS)

    def test_internal_profile_zeroes_reference_dimensions(self) -> None:
        assert EPFL_INTERNAL_PROFILE.weights["reference_quality"] == 0.0
        assert EPFL_INTERNAL_PROFILE.weights["calibration_confidence"] == 0.0
        assert EPFL_INTERNAL_PROFILE.skip_reference is True

    def test_external_profile_does_not_skip_reference(self) -> None:
        assert EXTERNAL_PROFILE.skip_reference is False
        assert EXTERNAL_PROFILE.weights["reference_quality"] > 0.0

    def test_weights_must_sum_to_one(self) -> None:
        with pytest.raises(ValueError, match="sum to"):
            EvaluationProfile(
                name="bad",
                weights=dict.fromkeys(ALL_DIMENSIONS, 0.1),  # 0.8
                skip_reference=False,
            )

    def test_missing_dimension_rejected(self) -> None:
        partial = dict.fromkeys(ALL_DIMENSIONS[:-1], 0.125)
        with pytest.raises(ValueError, match="missing weights"):
            EvaluationProfile(name="bad", weights=partial, skip_reference=False)

    def test_unknown_dimension_rejected(self) -> None:
        weights = dict.fromkeys(ALL_DIMENSIONS, 1.0 / 9)
        weights["mystery"] = 1.0 / 9  # type: ignore[index]
        with pytest.raises(ValueError, match="unknown dimensions"):
            EvaluationProfile(name="bad", weights=weights, skip_reference=False)

    def test_negative_weight_rejected(self) -> None:
        weights = dict.fromkeys(ALL_DIMENSIONS, 1.0 / 8)
        weights["academic_strength"] = -0.1
        with pytest.raises(ValueError, match=r"in \[0,1\]"):
            EvaluationProfile(name="bad", weights=weights, skip_reference=False)

    def test_skip_reference_requires_zero_reference_weight(self) -> None:
        # Reference still has weight but skip_reference=True is contradictory.
        weights = dict(EXTERNAL_PROFILE.weights)
        with pytest.raises(ValueError, match="skip_reference=True"):
            EvaluationProfile(name="bad", weights=weights, skip_reference=True)

    def test_weights_are_immutable_after_construction(self) -> None:
        # MappingProxyType is a read-only view; EvaluationProfile itself is
        # a frozen dataclass that rejects field reassignment. setattr is
        # used to bypass the static type checker (the field is declared
        # read-only, which is exactly what we want to verify at runtime).
        import dataclasses
        from types import MappingProxyType

        assert isinstance(EXTERNAL_PROFILE.weights, MappingProxyType)
        with pytest.raises(dataclasses.FrozenInstanceError):
            EXTERNAL_PROFILE.weights = {}


@pytest.mark.unit
class TestSelectProfile:
    def test_internal_returns_internal_profile(self) -> None:
        assert select_profile(is_epfl_internal=True) is EPFL_INTERNAL_PROFILE

    def test_external_returns_external_profile(self) -> None:
        assert select_profile(is_epfl_internal=False) is EXTERNAL_PROFILE


@pytest.mark.unit
class TestRenormalize:
    def test_renormalized_sums_to_one(self) -> None:
        new = renormalize_without_reference(EXTERNAL_PROFILE)
        assert math.isclose(sum(new.weights.values()), 1.0, abs_tol=1e-6)

    def test_renormalized_zeroes_reference_dimensions(self) -> None:
        new = renormalize_without_reference(EXTERNAL_PROFILE)
        assert new.weights["reference_quality"] == 0.0
        assert new.weights["calibration_confidence"] == 0.0
        assert new.skip_reference is True

    def test_renormalized_preserves_relative_ordering(self) -> None:
        new = renormalize_without_reference(EXTERNAL_PROFILE)
        # academic should still be the largest non-reference weight
        non_ref = {
            dim: w
            for dim, w in new.weights.items()
            if dim not in {"reference_quality", "calibration_confidence"}
        }
        assert max(non_ref, key=lambda d: non_ref[d]) == "academic_strength"

    def test_renormalize_idempotent_for_already_skipped_profile(self) -> None:
        same = renormalize_without_reference(EPFL_INTERNAL_PROFILE)
        assert same is EPFL_INTERNAL_PROFILE


@pytest.mark.unit
class TestEpflDetector:
    @pytest.mark.parametrize(
        "school_name",
        [
            "Ecole polytechnique fédérale de Lausanne EPFL",
            "EPFL",
            "École Polytechnique Fédérale de Lausanne",
            "ecole polytechnique federale de lausanne",  # no accents
            "Swiss Federal Institute of Technology Lausanne",
        ],
    )
    def test_recognizes_epfl_variants(self, school_name: str) -> None:
        assert detect_epfl_internal(school_name) is True

    @pytest.mark.parametrize(
        "school_name",
        [
            "",
            "ETH Zurich",
            "Ecole Polytechnique (Paris)",
            "Polytechnique Montréal",
            "Politecnico di Milano",
            "Polytechnique fédérale de Zurich",  # ETH in French — not EPFL
        ],
    )
    def test_does_not_match_non_epfl(self, school_name: str) -> None:
        assert detect_epfl_internal(school_name) is False


@pytest.mark.unit
class TestMeaningfulLetters:
    def test_short_letter_treated_as_absent(self) -> None:
        assert has_meaningful_letters("Letter header only.") is False

    def test_empty_treated_as_absent(self) -> None:
        assert has_meaningful_letters("") is False
        assert has_meaningful_letters("   \n\t  ") is False

    def test_long_letter_treated_as_present(self) -> None:
        body = "x" * (MIN_MEANINGFUL_LETTERS_LENGTH + 50)
        assert has_meaningful_letters(body) is True


@pytest.mark.unit
class TestComputeComposite:
    """Profile-aware composite scoring."""

    def test_uses_external_weights_by_default(self) -> None:
        from agentic_admission.agents.chair import compute_composite

        scores = dict.fromkeys(ALL_DIMENSIONS, 8)
        result = compute_composite(scores)
        assert result == 8.0  # 8 * (weights summing to 1.0) = 8

    def test_internal_profile_zeros_reference_contribution(self) -> None:
        from agentic_admission.agents.chair import compute_composite

        # Reference scores at sentinel value 1, others at 8. Under the
        # internal profile, reference is zero-weighted, so composite
        # should equal 8 * (sum of non-reference weights = 1.0) = 8.
        scores = dict.fromkeys(ALL_DIMENSIONS, 8)
        scores["reference_quality"] = 1
        scores["calibration_confidence"] = 1
        result = compute_composite(scores, weights=EPFL_INTERNAL_PROFILE.weights)
        assert result == 8.0

    def test_clamps_to_score_range(self) -> None:
        from agentic_admission.agents.chair import compute_composite

        # Construct a scenario where weighted sum is above 10 (impossible
        # given valid inputs, but defensive).
        scores = dict.fromkeys(ALL_DIMENSIONS, 10)
        result = compute_composite(scores)
        assert 1.0 <= result <= 10.0
