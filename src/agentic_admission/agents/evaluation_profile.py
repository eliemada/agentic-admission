"""Evaluation profiles: per-cohort scoring weights and evaluator configuration.

A profile selects which evaluators run for a candidate and how their
dimension scores are weighted into the composite. Two profiles are
defined out of the box:

* :data:`EXTERNAL_PROFILE` — the default for non-EPFL bachelors. Reference
  letters are required and weighted alongside academic and motivation
  signals.

* :data:`EPFL_INTERNAL_PROFILE` — for EPFL bachelors transferring into MTE.
  These candidates do not submit recommendation letters in 4 of 5 sampled
  dossiers; the reference dimensions are zero-weighted, and academic
  signal is up-weighted to reflect how the committee actually decides
  internal cases (algebra + analysis average against a 4.5 / 4.0
  threshold).

Profiles validate at construction time that their weights sum to 1.0,
which also fixes a historical bug where the previous global weights
summed to 0.85, capping the composite at 8.5/10.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

_WEIGHT_TOLERANCE: float = 1e-6
"""Allowed absolute deviation from 1.0 when validating profile weights."""

_REFERENCE_DIMENSIONS: frozenset[str] = frozenset(
    {"reference_quality", "calibration_confidence"}
)
"""Dimensions produced by the Reference Letter Specialist."""

ALL_DIMENSIONS: tuple[str, ...] = (
    "academic_strength",
    "institution_quality",
    "reference_quality",
    "calibration_confidence",
    "motivation_clarity",
    "program_fit",
    "risk_flags",
    "consistency",
)
"""Canonical ordering of the 8 scoring dimensions."""


@dataclass(frozen=True)
class EvaluationProfile:
    """Immutable per-cohort scoring profile.

    Attributes
    ----------
    name
        Short identifier (``"external"``, ``"epfl_internal"``).
    weights
        Mapping from dimension name to weight in [0.0, 1.0]. Must include
        every dimension in :data:`ALL_DIMENSIONS` and sum to 1.0 within
        :data:`_WEIGHT_TOLERANCE`.
    skip_reference
        When ``True``, the orchestrator does not invoke the Reference
        Letter Specialist and inserts a sentinel scorecard instead.
        Implies that the reference dimensions carry weight 0.
    """

    name: str
    weights: Mapping[str, float]
    skip_reference: bool

    def __post_init__(self) -> None:
        """Validate invariants and freeze the weights mapping."""
        self._validate_weights()
        if self.skip_reference:
            self._validate_reference_zero()
        # Freeze the mapping so consumers cannot mutate it.
        object.__setattr__(self, "weights", MappingProxyType(dict(self.weights)))

    def _validate_weights(self) -> None:
        missing = set(ALL_DIMENSIONS) - set(self.weights)
        if missing:
            msg = f"Profile {self.name!r} missing weights for {sorted(missing)}"
            raise ValueError(msg)
        extra = set(self.weights) - set(ALL_DIMENSIONS)
        if extra:
            msg = f"Profile {self.name!r} has unknown dimensions {sorted(extra)}"
            raise ValueError(msg)
        for dim, w in self.weights.items():
            if not (0.0 <= w <= 1.0):
                msg = f"Profile {self.name!r} weight for {dim!r} must be in [0,1], got {w}"
                raise ValueError(msg)
        total = sum(self.weights.values())
        if not math.isclose(total, 1.0, abs_tol=_WEIGHT_TOLERANCE):
            msg = f"Profile {self.name!r} weights sum to {total:.6f}, expected 1.0"
            raise ValueError(msg)

    def _validate_reference_zero(self) -> None:
        for dim in _REFERENCE_DIMENSIONS:
            if self.weights[dim] != 0.0:
                msg = (
                    f"Profile {self.name!r} sets skip_reference=True but "
                    f"weight for {dim!r} is {self.weights[dim]} (must be 0.0)"
                )
                raise ValueError(msg)


EXTERNAL_PROFILE: EvaluationProfile = EvaluationProfile(
    name="external",
    weights={
        "academic_strength": 0.30,
        "institution_quality": 0.18,
        "reference_quality": 0.18,
        "calibration_confidence": 0.12,
        "motivation_clarity": 0.06,
        "program_fit": 0.06,
        "risk_flags": 0.05,
        "consistency": 0.05,
    },
    skip_reference=False,
)
"""Default profile for non-EPFL candidates.

Re-balances the previous (broken) weights from 0.85 to 1.0 while
preserving relative ordering: academic + institution lead (48%),
reference + calibration follow (30%), motivation + fit are minor
tiebreakers (12%), devil's-advocate dimensions are sanity checks (10%).
"""


EPFL_INTERNAL_PROFILE: EvaluationProfile = EvaluationProfile(
    name="epfl_internal",
    weights={
        "academic_strength": 0.45,
        "institution_quality": 0.10,
        "reference_quality": 0.0,
        "calibration_confidence": 0.0,
        "motivation_clarity": 0.15,
        "program_fit": 0.15,
        "risk_flags": 0.075,
        "consistency": 0.075,
    },
    skip_reference=True,
)
"""Profile for EPFL bachelors transferring into MTE.

Rationale, derived from the 2026-05-08 admission committee meeting:

* Most internal candidates submit no recommendation letters
  (4 of 5 sampled dossiers). Forcing the reference evaluator on these
  candidates returns ``reference_quality=1-2`` and tanks the composite
  by ~25%.
* The committee's actual rule for internals is the algebra + analysis
  average against a 4.5 (default) or 4.0 (section-switcher) threshold.
  ``academic_strength`` should therefore carry most of the weight.
* Institution quality is fixed (always EPFL) so it carries less signal —
  weight reduced from 18% to 10%.
* Motivation and program fit are the two remaining differentiators
  for internal candidates, so they are up-weighted (5% → 15% each).
"""


def select_profile(*, is_epfl_internal: bool) -> EvaluationProfile:
    """Pick the profile that matches a dossier.

    Parameters
    ----------
    is_epfl_internal
        ``True`` when the candidate is transferring from an EPFL bachelor.

    Returns
    -------
    EvaluationProfile
        :data:`EPFL_INTERNAL_PROFILE` or :data:`EXTERNAL_PROFILE`.
    """
    return EPFL_INTERNAL_PROFILE if is_epfl_internal else EXTERNAL_PROFILE


def renormalize_without_reference(profile: EvaluationProfile) -> EvaluationProfile:
    """Return a copy of ``profile`` with reference weights zeroed and re-normalized.

    Used when an external candidate happens to submit no letters at all:
    rather than running the reference evaluator on empty input, redistribute
    its weight proportionally across the remaining dimensions.

    Parameters
    ----------
    profile
        Source profile (typically :data:`EXTERNAL_PROFILE`).

    Returns
    -------
    EvaluationProfile
        New profile with ``skip_reference=True`` and weights summing to 1.0.

    Raises
    ------
    ValueError
        If every non-reference weight is also 0 (no remaining mass to
        redistribute).
    """
    if profile.skip_reference:
        return profile

    remaining = {
        dim: w for dim, w in profile.weights.items() if dim not in _REFERENCE_DIMENSIONS
    }
    remaining_total = sum(remaining.values())
    if remaining_total <= 0.0:
        msg = (
            f"Cannot renormalize {profile.name!r}: non-reference weights "
            f"sum to {remaining_total}"
        )
        raise ValueError(msg)

    scale = 1.0 / remaining_total
    new_weights: dict[str, float] = dict.fromkeys(_REFERENCE_DIMENSIONS, 0.0)
    new_weights.update({dim: w * scale for dim, w in remaining.items()})

    return EvaluationProfile(
        name=f"{profile.name}_no_reference",
        weights=new_weights,
        skip_reference=True,
    )
