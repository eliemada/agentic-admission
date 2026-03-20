"""Tests for post-analysis PII false-positive filters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentic_admission.anonymizer.post_filters import (
    apply_filters,
    build_filter_pipeline,
    filter_by_entity_threshold,
    filter_by_length,
    filter_common_words,
    filter_duration_as_date,
    filter_excluded_entities,
    filter_partial_words,
)
from agentic_admission.anonymizer.thresholds import build_threshold_config


@dataclass
class FakeResult:
    """Minimal stand-in for a Presidio RecognizerResult."""

    entity_type: str
    start: int
    end: int
    score: float


# ---------------------------------------------------------------------------
# filter_excluded_entities
# ---------------------------------------------------------------------------


class TestFilterExcludedEntities:
    """Tests for entity type exclusion filter."""

    def test_drops_excluded_location(self) -> None:
        text = "Lives in Zurich"
        results: list[Any] = [FakeResult("LOCATION", 9, 15, 0.8)]
        filtered = filter_excluded_entities(text, results, excluded=frozenset({"LOCATION"}))
        assert len(filtered) == 0

    def test_drops_excluded_nrp(self) -> None:
        text = "Swiss citizen"
        results: list[Any] = [FakeResult("NRP", 0, 5, 0.7)]
        filtered = filter_excluded_entities(text, results, excluded=frozenset({"NRP"}))
        assert len(filtered) == 0

    def test_drops_excluded_organization(self) -> None:
        text = "Worked at Google"
        results: list[Any] = [FakeResult("organization", 10, 16, 0.8)]
        filtered = filter_excluded_entities(text, results, excluded=frozenset({"organization"}))
        assert len(filtered) == 0

    def test_keeps_non_excluded_entities(self) -> None:
        text = "John Smith lives in Zurich"
        results: list[Any] = [FakeResult("PERSON", 0, 10, 0.9), FakeResult("LOCATION", 20, 26, 0.8)]
        filtered = filter_excluded_entities(text, results, excluded=frozenset({"LOCATION"}))
        assert len(filtered) == 1
        assert filtered[0].entity_type == "PERSON"

    def test_empty_exclusion_set_keeps_all(self) -> None:
        text = "Zurich"
        results: list[Any] = [FakeResult("LOCATION", 0, 6, 0.8)]
        filtered = filter_excluded_entities(text, results, excluded=frozenset())
        assert len(filtered) == 1

    def test_multiple_exclusions(self) -> None:
        text = "Swiss person in Zurich at Google"
        results: list[Any] = [
            FakeResult("NRP", 0, 5, 0.7),
            FakeResult("LOCATION", 16, 22, 0.8),
            FakeResult("organization", 26, 32, 0.8),
            FakeResult("PERSON", 6, 12, 0.9),
        ]
        filtered = filter_excluded_entities(
            text, results, excluded=frozenset({"LOCATION", "NRP", "organization"})
        )
        assert len(filtered) == 1
        assert filtered[0].entity_type == "PERSON"


# ---------------------------------------------------------------------------
# filter_by_entity_threshold
# ---------------------------------------------------------------------------


class TestFilterByEntityThreshold:
    """Tests for per-entity confidence threshold filtering."""

    def test_keeps_high_confidence_person(self) -> None:
        text = "John Smith is here"
        results: list[Any] = [FakeResult("PERSON", 0, 10, 0.8)]
        filtered = filter_by_entity_threshold(text, results)
        assert len(filtered) == 1

    def test_drops_low_confidence_person(self) -> None:
        text = "I am here"
        results: list[Any] = [FakeResult("PERSON", 0, 1, 0.4)]
        filtered = filter_by_entity_threshold(text, results)
        assert len(filtered) == 0

    def test_keeps_low_confidence_email(self) -> None:
        """EMAIL_ADDRESS has a lower threshold (0.4)."""
        text = "email@example.com"
        results: list[Any] = [FakeResult("EMAIL_ADDRESS", 0, 17, 0.45)]
        filtered = filter_by_entity_threshold(text, results)
        assert len(filtered) == 1

    def test_custom_config(self) -> None:
        config = build_threshold_config(overrides={"PERSON": 0.9})
        text = "John Smith"
        results: list[Any] = [FakeResult("PERSON", 0, 10, 0.85)]
        filtered = filter_by_entity_threshold(text, results, config=config)
        assert len(filtered) == 0

    def test_nrp_needs_very_high_score(self) -> None:
        text = "Egyptian"
        results: list[Any] = [FakeResult("NRP", 0, 8, 0.6)]
        filtered = filter_by_entity_threshold(text, results)
        assert len(filtered) == 0


# ---------------------------------------------------------------------------
# filter_partial_words
# ---------------------------------------------------------------------------


class TestFilterPartialWords:
    """Tests for word-boundary alignment filtering."""

    def test_keeps_full_word_entity(self) -> None:
        text = "Hello John Smith here"
        results: list[Any] = [FakeResult("PERSON", 6, 16, 0.8)]
        filtered = filter_partial_words(text, results)
        assert len(filtered) == 1

    def test_drops_entity_breaking_start(self) -> None:
        """Simulates 'Wit<PERSON>' from 'With' where 'h' matched as entity."""
        text = "With"
        results: list[Any] = [FakeResult("PERSON", 3, 4, 0.5)]
        filtered = filter_partial_words(text, results)
        assert len(filtered) == 0

    def test_drops_entity_breaking_end(self) -> None:
        """Simulates 'Internatio<PII>nal' where middle matched."""
        text = "International"
        results: list[Any] = [FakeResult("NRP", 0, 8, 0.5)]
        filtered = filter_partial_words(text, results)
        assert len(filtered) == 0

    def test_keeps_entity_at_start_of_text(self) -> None:
        text = "John is here"
        results: list[Any] = [FakeResult("PERSON", 0, 4, 0.8)]
        filtered = filter_partial_words(text, results)
        assert len(filtered) == 1

    def test_keeps_entity_at_end_of_text(self) -> None:
        text = "Hello John"
        results: list[Any] = [FakeResult("PERSON", 6, 10, 0.8)]
        filtered = filter_partial_words(text, results)
        assert len(filtered) == 1

    def test_keeps_entity_followed_by_punctuation(self) -> None:
        text = "Hello John, welcome."
        results: list[Any] = [FakeResult("PERSON", 6, 10, 0.8)]
        filtered = filter_partial_words(text, results)
        assert len(filtered) == 1


# ---------------------------------------------------------------------------
# filter_by_length
# ---------------------------------------------------------------------------


class TestFilterByLength:
    """Tests for minimum entity length filtering."""

    def test_drops_single_char_person(self) -> None:
        """'I' as PERSON should be dropped (min length 2)."""
        text = "I am a student"
        results: list[Any] = [FakeResult("PERSON", 0, 1, 0.5)]
        filtered = filter_by_length(text, results)
        assert len(filtered) == 0

    def test_keeps_real_name(self) -> None:
        text = "John Smith"
        results: list[Any] = [FakeResult("PERSON", 0, 10, 0.8)]
        filtered = filter_by_length(text, results)
        assert len(filtered) == 1

    def test_keeps_two_char_person(self) -> None:
        text = "Li is here"
        results: list[Any] = [FakeResult("PERSON", 0, 2, 0.8)]
        filtered = filter_by_length(text, results)
        assert len(filtered) == 1

    def test_drops_short_nrp(self) -> None:
        """NRP minimum is 3 chars."""
        text = "UK is great"
        results: list[Any] = [FakeResult("NRP", 0, 2, 0.7)]
        filtered = filter_by_length(text, results)
        assert len(filtered) == 0

    def test_email_no_length_restriction(self) -> None:
        """EMAIL_ADDRESS has no special min length (default 1)."""
        text = "a@b.c"
        results: list[Any] = [FakeResult("EMAIL_ADDRESS", 0, 5, 0.9)]
        filtered = filter_by_length(text, results)
        assert len(filtered) == 1


# ---------------------------------------------------------------------------
# filter_common_words
# ---------------------------------------------------------------------------


class TestFilterCommonWords:
    """Tests for common word filtering."""

    def test_drops_pronoun_he_as_person(self) -> None:
        text = "He went home"
        results: list[Any] = [FakeResult("PERSON", 0, 2, 0.5)]
        filtered = filter_common_words(text, results)
        assert len(filtered) == 0

    def test_drops_pronoun_my_as_person(self) -> None:
        text = "My name is John"
        results: list[Any] = [FakeResult("PERSON", 0, 2, 0.5)]
        filtered = filter_common_words(text, results)
        assert len(filtered) == 0

    def test_keeps_real_name(self) -> None:
        text = "John went home"
        results: list[Any] = [FakeResult("PERSON", 0, 4, 0.8)]
        filtered = filter_common_words(text, results)
        assert len(filtered) == 1

    def test_ignores_non_prone_entity_types(self) -> None:
        """EMAIL_ADDRESS should not be filtered even if text matches a common word."""
        text = "i@example.com"
        results: list[Any] = [FakeResult("EMAIL_ADDRESS", 0, 13, 0.9)]
        filtered = filter_common_words(text, results)
        assert len(filtered) == 1

    def test_drops_the_as_location(self) -> None:
        text = "The is nice"
        results: list[Any] = [FakeResult("LOCATION", 0, 3, 0.5)]
        filtered = filter_common_words(text, results)
        assert len(filtered) == 0

    def test_case_insensitive(self) -> None:
        text = "HE went home"
        results: list[Any] = [FakeResult("PERSON", 0, 2, 0.5)]
        filtered = filter_common_words(text, results)
        assert len(filtered) == 0


# ---------------------------------------------------------------------------
# filter_duration_as_date
# ---------------------------------------------------------------------------


class TestFilterDurationAsDate:
    """Tests for duration vs date filtering."""

    def test_drops_years_duration(self) -> None:
        text = "I have 5 years of experience"
        results: list[Any] = [FakeResult("DATE_TIME", 7, 14, 0.5)]
        filtered = filter_duration_as_date(text, results)
        assert len(filtered) == 0

    def test_drops_months_duration(self) -> None:
        text = "a 3 months internship"
        results: list[Any] = [FakeResult("DATE_TIME", 2, 10, 0.5)]
        filtered = filter_duration_as_date(text, results)
        assert len(filtered) == 0

    def test_drops_singular_year(self) -> None:
        text = "1 year ago"
        results: list[Any] = [FakeResult("DATE_TIME", 0, 6, 0.5)]
        filtered = filter_duration_as_date(text, results)
        assert len(filtered) == 0

    def test_keeps_real_date(self) -> None:
        text = "born on 1990-05-15"
        results: list[Any] = [FakeResult("DATE_TIME", 8, 18, 0.8)]
        filtered = filter_duration_as_date(text, results)
        assert len(filtered) == 1

    def test_keeps_non_date_entity(self) -> None:
        text = "5 years of experience"
        results: list[Any] = [FakeResult("PERSON", 0, 7, 0.5)]
        filtered = filter_duration_as_date(text, results)
        assert len(filtered) == 1

    def test_drops_semesters_duration(self) -> None:
        text = "2 semesters"
        results: list[Any] = [FakeResult("DATE_TIME", 0, 11, 0.5)]
        filtered = filter_duration_as_date(text, results)
        assert len(filtered) == 0


# ---------------------------------------------------------------------------
# Pipeline composition
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# filter_numeric_ids
# ---------------------------------------------------------------------------


class TestFilterNumericIds:
    """Tests for numeric application code filter."""

    def test_drops_pure_digit_phone(self) -> None:
        """Pure 10-digit string should NOT be classified as PHONE."""
        from agentic_admission.anonymizer.post_filters import filter_numeric_ids

        text = "Code: 2839273087 here"
        results: list[Any] = [FakeResult("PHONE_NUMBER", 6, 16, 0.7)]
        filtered = filter_numeric_ids(text, results)
        assert len(filtered) == 0

    def test_keeps_real_phone_with_plus(self) -> None:
        """Phone with + prefix should be kept."""
        from agentic_admission.anonymizer.post_filters import filter_numeric_ids

        text = "Call +96104912018 please"
        results: list[Any] = [FakeResult("PHONE_NUMBER", 5, 17, 0.9)]
        filtered = filter_numeric_ids(text, results)
        assert len(filtered) == 1

    def test_keeps_real_phone_with_formatting(self) -> None:
        """Phone with spaces/dashes should be kept."""
        from agentic_admission.anonymizer.post_filters import filter_numeric_ids

        text = "Call +41 21 693 43 45 please"
        results: list[Any] = [FakeResult("PHONE_NUMBER", 5, 21, 0.9)]
        filtered = filter_numeric_ids(text, results)
        assert len(filtered) == 1

    def test_keeps_real_email(self) -> None:
        """Real email should NOT be affected."""
        from agentic_admission.anonymizer.post_filters import filter_numeric_ids

        text = "Mail rollaabiantoun@hotmail.com"
        results: list[Any] = [FakeResult("EMAIL_ADDRESS", 5, 30, 0.9)]
        filtered = filter_numeric_ids(text, results)
        assert len(filtered) == 1

    def test_drops_pure_digit_email(self) -> None:
        """Pure digit string misclassified as EMAIL should be dropped."""
        from agentic_admission.anonymizer.post_filters import filter_numeric_ids

        text = "Code 2839273087"
        results: list[Any] = [FakeResult("EMAIL_ADDRESS", 5, 15, 0.6)]
        filtered = filter_numeric_ids(text, results)
        assert len(filtered) == 0

    def test_ignores_non_phone_email_entities(self) -> None:
        """PERSON entities with digits should not be affected."""
        from agentic_admission.anonymizer.post_filters import filter_numeric_ids

        text = "Agent 007"
        results: list[Any] = [FakeResult("PERSON", 6, 9, 0.5)]
        filtered = filter_numeric_ids(text, results)
        assert len(filtered) == 1


class TestBuildFilterPipeline:
    """Tests for pipeline composition."""

    def test_returns_seven_filters(self) -> None:
        pipeline = build_filter_pipeline()
        assert len(pipeline) == 7

    def test_custom_threshold_config(self) -> None:
        config = build_threshold_config(overrides={"PERSON": 0.9})
        pipeline = build_filter_pipeline(threshold_config=config)
        assert len(pipeline) == 7

    def test_exclusion_filter_is_first(self) -> None:
        """The exclusion filter must run before all other filters."""
        pipeline = build_filter_pipeline(excluded_entities=frozenset({"LOCATION"}))
        text = "Zurich is nice"
        results: list[Any] = [FakeResult("LOCATION", 0, 6, 0.9)]
        # The first filter should drop excluded entities
        after_first = pipeline[0](text, results)
        assert len(after_first) == 0


class TestApplyFilters:
    """Tests for the full pipeline application."""

    def test_empty_results_stay_empty(self) -> None:
        pipeline = build_filter_pipeline()
        filtered = apply_filters("some text", [], pipeline)
        assert filtered == []

    def test_pipeline_removes_false_positive_pronoun(self) -> None:
        """'I' as PERSON should be caught by length + common word filters."""
        text = "I am a student at EPFL"
        results: list[Any] = [FakeResult("PERSON", 0, 1, 0.5)]
        pipeline = build_filter_pipeline()
        filtered = apply_filters(text, results, pipeline)
        assert len(filtered) == 0

    def test_pipeline_keeps_real_email(self) -> None:
        text = "Contact john@example.com for info"
        results: list[Any] = [FakeResult("EMAIL_ADDRESS", 8, 24, 0.9)]
        pipeline = build_filter_pipeline()
        filtered = apply_filters(text, results, pipeline)
        assert len(filtered) == 1

    def test_pipeline_removes_duration(self) -> None:
        text = "5 years of experience"
        results: list[Any] = [FakeResult("DATE_TIME", 0, 7, 0.6)]
        pipeline = build_filter_pipeline()
        filtered = apply_filters(text, results, pipeline)
        assert len(filtered) == 0
