"""Per-entity-type confidence thresholds for PII detection.

Default thresholds are tuned for EPFL admission dossiers where common words,
pronouns, and degree names are frequently misidentified as PII entities.
Higher thresholds for ambiguous entity types reduce false positives.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Threshold tiers by entity ambiguity level
_LOW_AMBIGUITY_THRESHOLD = 0.4
_MEDIUM_THRESHOLD = 0.5
_HIGH_AMBIGUITY_THRESHOLD = 0.6
_VERY_HIGH_AMBIGUITY_THRESHOLD = 0.65

_DEFAULT_ENTITY_THRESHOLDS: dict[str, float] = {
    # Low ambiguity — these patterns are fairly unambiguous
    "EMAIL_ADDRESS": _LOW_AMBIGUITY_THRESHOLD,
    "PHONE_NUMBER": _LOW_AMBIGUITY_THRESHOLD,
    "URL": _LOW_AMBIGUITY_THRESHOLD,
    "IP_ADDRESS": _LOW_AMBIGUITY_THRESHOLD,
    "email": _LOW_AMBIGUITY_THRESHOLD,
    "phone number": _LOW_AMBIGUITY_THRESHOLD,
    "mobile phone number": _LOW_AMBIGUITY_THRESHOLD,
    # Medium ambiguity — structured but can have false matches
    "IBAN_CODE": _MEDIUM_THRESHOLD,
    "CREDIT_CARD": _MEDIUM_THRESHOLD,
    "CH_AHV": _MEDIUM_THRESHOLD,
    "EPFL_SCIPER": _MEDIUM_THRESHOLD,
    "date of birth": _MEDIUM_THRESHOLD,
    "passport number": _MEDIUM_THRESHOLD,
    "social security number": _MEDIUM_THRESHOLD,
    "credit card number": _MEDIUM_THRESHOLD,
    "address": _MEDIUM_THRESHOLD,
    "DATE_TIME": _MEDIUM_THRESHOLD,
    # High ambiguity — names/persons produce many false positives
    "PERSON": _HIGH_AMBIGUITY_THRESHOLD,
    "person": _HIGH_AMBIGUITY_THRESHOLD,
    "name": _HIGH_AMBIGUITY_THRESHOLD,
    "LOCATION": _HIGH_AMBIGUITY_THRESHOLD,
    # Very high ambiguity — nationality/org detection is noisy
    "NRP": _VERY_HIGH_AMBIGUITY_THRESHOLD,
    "organization": _VERY_HIGH_AMBIGUITY_THRESHOLD,
}

_DEFAULT_FALLBACK = _MEDIUM_THRESHOLD


@dataclass(frozen=True)
class ThresholdConfig:
    """Immutable per-entity threshold configuration.

    Attributes
    ----------
    entity_thresholds
        Mapping from entity type to minimum confidence score.
    fallback
        Default threshold for entity types not in the mapping.
    """

    entity_thresholds: dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_ENTITY_THRESHOLDS),
    )
    fallback: float = _DEFAULT_FALLBACK

    def get_threshold(self, entity_type: str) -> float:
        """Return the minimum confidence for *entity_type*.

        Parameters
        ----------
        entity_type
            Presidio or GLiNER entity type string.

        Returns
        -------
        float
            The threshold; falls back to :attr:`fallback` for unknown types.
        """
        return self.entity_thresholds.get(entity_type, self.fallback)


def build_threshold_config(
    *,
    overrides: dict[str, float] | None = None,
    fallback: float | None = None,
) -> ThresholdConfig:
    """Create a :class:`ThresholdConfig` with optional overrides.

    Parameters
    ----------
    overrides
        Entity-type → threshold pairs to override defaults.
    fallback
        Custom fallback threshold for unknown entity types.

    Returns
    -------
    ThresholdConfig
        Frozen config instance.
    """
    thresholds = dict(_DEFAULT_ENTITY_THRESHOLDS)
    if overrides is not None:
        thresholds.update(overrides)
    return ThresholdConfig(
        entity_thresholds=thresholds,
        fallback=fallback if fallback is not None else _DEFAULT_FALLBACK,
    )
