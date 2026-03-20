"""Post-analysis filters to reduce PII false positives.

Each filter is a pure function ``(text, results) -> filtered_results`` that
removes analyzer results matching known false-positive patterns. Filters are
composed into a pipeline via :func:`build_filter_pipeline` and applied with
:func:`apply_filters`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any

from agentic_admission.anonymizer.thresholds import ThresholdConfig, build_threshold_config

# ---------------------------------------------------------------------------
# Excluded entity types (configurable via settings)
# ---------------------------------------------------------------------------


def _get_excluded_entities() -> frozenset[str]:
    """Return the exclusion set from settings (already parsed at startup)."""
    from agentic_admission.config import settings

    return settings.anonymizer_excluded_entities


# Type alias for filter functions.
FilterFunc = Callable[[str, list[Any]], list[Any]]

# ---------------------------------------------------------------------------
# Common-word sets for pronoun / determiner filtering
# ---------------------------------------------------------------------------

_COMMON_WORDS: frozenset[str] = frozenset(
    {
        # Pronouns
        "i",
        "he",
        "she",
        "it",
        "we",
        "they",
        "me",
        "him",
        "her",
        "us",
        "them",
        "my",
        "his",
        "its",
        "our",
        "their",
        "myself",
        "himself",
        "herself",
        "itself",
        "ourselves",
        "themselves",
        "you",
        "your",
        "yours",
        "yourself",
        # Determiners / prepositions often misidentified
        "the",
        "a",
        "an",
        "this",
        "that",
        "these",
        "those",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "and",
        "or",
        "but",
        "not",
        "no",
        "if",
        "so",
        "as",
        "is",
        "am",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "has",
        "have",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "can",
        "could",
    }
)

# Entity types that are prone to common-word false positives.
_COMMON_WORD_ENTITY_TYPES: frozenset[str] = frozenset(
    {"PERSON", "person", "name", "LOCATION", "NRP", "organization"}
)

# Duration pattern: digits followed by time units (not calendar dates).
_DURATION_PATTERN = re.compile(
    r"^\d+\s*(?:years?|months?|weeks?|days?|hours?|semesters?)$", re.IGNORECASE
)

# Minimum entity text length by entity type.
_MIN_ENTITY_LENGTH: dict[str, int] = {
    "PERSON": 2,
    "person": 2,
    "name": 2,
    "LOCATION": 2,
    "NRP": 3,
    "organization": 3,
    "address": 3,
}

_DEFAULT_MIN_LENGTH = 1


# ---------------------------------------------------------------------------
# Individual filter functions
# ---------------------------------------------------------------------------


def filter_excluded_entities(
    text: str, results: list[Any], *, excluded: frozenset[str] | None = None
) -> list[Any]:
    """Drop results whose entity type is in the exclusion set.

    This is the primary mechanism for preserving LOCATION, NRP (nationality),
    and organization names that are valuable admission signals.

    Parameters
    ----------
    text
        Original text (unused, kept for pipeline signature consistency).
    results
        Presidio analyzer results.
    excluded
        Entity types to drop. Defaults to the config-driven set.

    Returns
    -------
    list
        Results not matching any excluded entity type.
    """
    excluded_set = excluded if excluded is not None else _get_excluded_entities()
    if not excluded_set:
        return results
    return [r for r in results if r.entity_type not in excluded_set]


def filter_by_entity_threshold(
    text: str, results: list[Any], *, config: ThresholdConfig | None = None
) -> list[Any]:
    """Drop results below per-entity-type minimum confidence.

    Parameters
    ----------
    text
        Original text (unused, kept for pipeline signature consistency).
    results
        Presidio analyzer results.
    config
        Threshold config; uses defaults if ``None``.

    Returns
    -------
    list
        Filtered results above their entity-specific threshold.
    """
    cfg = config if config is not None else build_threshold_config()
    return [r for r in results if r.score >= cfg.get_threshold(r.entity_type)]


def filter_partial_words(text: str, results: list[Any]) -> list[Any]:
    """Drop entities that break word boundaries.

    Catches false positives like ``"Wit<PERSON>"`` (from "With") or
    ``"Internatio<PII>"`` where the entity span cuts through a word.

    Parameters
    ----------
    text
        Original text.
    results
        Presidio analyzer results.

    Returns
    -------
    list
        Results whose spans align with word boundaries.
    """
    filtered = []
    for r in results:
        start, end = r.start, r.end

        # Check character before start is a word boundary
        if start > 0 and text[start - 1].isalnum():
            continue

        # Check character after end is a word boundary
        if end < len(text) and text[end].isalnum():
            continue

        filtered.append(r)
    return filtered


def filter_by_length(text: str, results: list[Any]) -> list[Any]:
    """Drop entities shorter than the minimum for their type.

    Prevents single-character entities like ``"I"`` being flagged as PERSON.

    Parameters
    ----------
    text
        Original text.
    results
        Presidio analyzer results.

    Returns
    -------
    list
        Results meeting minimum length requirements.
    """
    filtered = []
    for r in results:
        entity_text = text[r.start : r.end]
        min_len = _MIN_ENTITY_LENGTH.get(r.entity_type, _DEFAULT_MIN_LENGTH)
        if len(entity_text.strip()) >= min_len:
            filtered.append(r)
    return filtered


def filter_common_words(text: str, results: list[Any]) -> list[Any]:
    """Drop common words (pronouns, determiners, prepositions) misidentified as PII.

    Only applies to entity types prone to common-word false positives
    (PERSON, LOCATION, NRP, organization).

    Parameters
    ----------
    text
        Original text.
    results
        Presidio analyzer results.

    Returns
    -------
    list
        Results that are not common English words.
    """
    filtered = []
    for r in results:
        if r.entity_type in _COMMON_WORD_ENTITY_TYPES:
            entity_text = text[r.start : r.end].strip().lower()
            if entity_text in _COMMON_WORDS:
                continue
        filtered.append(r)
    return filtered


def filter_duration_as_date(text: str, results: list[Any]) -> list[Any]:
    """Drop DATE_TIME entities that are actually durations, not calendar dates.

    Catches ``"5 years"``, ``"3 months"``, ``"2 semesters"`` which are time
    spans, not datable events.

    Parameters
    ----------
    text
        Original text.
    results
        Presidio analyzer results.

    Returns
    -------
    list
        Results excluding duration-like DATE_TIME matches.
    """
    filtered = []
    for r in results:
        if r.entity_type == "DATE_TIME":
            entity_text = text[r.start : r.end].strip()
            if _DURATION_PATTERN.match(entity_text):
                continue
        filtered.append(r)
    return filtered


# Pure-digit pattern: 7-13 digits with no phone formatting.
_PURE_DIGITS_PATTERN = re.compile(r"^\d{7,13}$")

# Entity types where pure-digit strings are likely misclassified.
_NUMERIC_ID_ENTITY_TYPES: frozenset[str] = frozenset({"PHONE_NUMBER", "EMAIL_ADDRESS"})


def filter_numeric_ids(text: str, results: list[Any]) -> list[Any]:
    """Drop PHONE/EMAIL matches that are pure digit strings (application codes).

    Catches administrative numeric codes like ``"2839273087"`` that get
    misclassified as phone numbers or email addresses by pattern matchers.

    Parameters
    ----------
    text
        Original text.
    results
        Presidio analyzer results.

    Returns
    -------
    list
        Results excluding pure-digit misclassifications.
    """
    filtered = []
    for r in results:
        if r.entity_type in _NUMERIC_ID_ENTITY_TYPES:
            entity_text = text[r.start : r.end].strip()
            if _PURE_DIGITS_PATTERN.match(entity_text):
                continue
        filtered.append(r)
    return filtered


# ---------------------------------------------------------------------------
# Pipeline composition
# ---------------------------------------------------------------------------


def build_filter_pipeline(
    *,
    threshold_config: ThresholdConfig | None = None,
    excluded_entities: frozenset[str] | None = None,
) -> list[FilterFunc]:
    """Build the default filter pipeline.

    Parameters
    ----------
    threshold_config
        Custom threshold config; uses defaults if ``None``.
    excluded_entities
        Entity types to drop before any other filtering.
        Defaults to the config-driven set (``ANONYMIZER_EXCLUDED_ENTITIES``).

    Returns
    -------
    list[FilterFunc]
        Ordered list of filter functions to apply sequentially.
    """
    cfg = threshold_config if threshold_config is not None else build_threshold_config()
    excluded = excluded_entities if excluded_entities is not None else _get_excluded_entities()

    def _exclusion_filter(text: str, results: list[Any]) -> list[Any]:
        return filter_excluded_entities(text, results, excluded=excluded)

    def _threshold_filter(text: str, results: list[Any]) -> list[Any]:
        return filter_by_entity_threshold(text, results, config=cfg)

    return [
        _exclusion_filter,
        _threshold_filter,
        filter_partial_words,
        filter_by_length,
        filter_common_words,
        filter_duration_as_date,
        filter_numeric_ids,
    ]


def apply_filters(text: str, results: list[Any], filters: Sequence[FilterFunc]) -> list[Any]:
    """Apply a sequence of filters to analyzer results.

    Parameters
    ----------
    text
        Original text.
    results
        Presidio analyzer results.
    filters
        Ordered filter functions to apply.

    Returns
    -------
    list
        Results that survived all filters.
    """
    current = list(results)
    for f in filters:
        current = f(text, current)
    return current
