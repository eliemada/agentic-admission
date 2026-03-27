"""Tests for the domain-specific allow-lists module."""

from __future__ import annotations

from agentic_admission.anonymizer.allow_lists import (
    ACADEMIC_TERMS,
    ACTIVITIES,
    ALL_CATEGORIES,
    FORM_LABELS,
    INSTITUTIONS,
    JOB_TITLES,
    LANGUAGES,
    PRONOUNS,
    TECHNICAL_TERMS,
    build_allow_list,
)


class TestCategories:
    """Tests for allow-list category contents."""

    def test_epfl_in_institutions(self) -> None:
        assert "EPFL" in INSTITUTIONS

    def test_cpp_in_technical(self) -> None:
        assert "C++" in TECHNICAL_TERMS

    def test_pronoun_i_in_pronouns(self) -> None:
        assert "I" in PRONOUNS

    def test_master_in_academic(self) -> None:
        assert "Master of Science" in ACADEMIC_TERMS

    def test_french_in_languages(self) -> None:
        assert "French" in LANGUAGES

    def test_arabic_in_languages(self) -> None:
        assert "Arabic" in LANGUAGES

    def test_nom_in_form_labels(self) -> None:
        assert "Nom" in FORM_LABELS

    def test_prenom_in_form_labels(self) -> None:
        assert "Prénom" in FORM_LABELS

    def test_telephone_in_form_labels(self) -> None:
        assert "Téléphone" in FORM_LABELS

    def test_engineer_in_job_titles(self) -> None:
        assert "Engineer" in JOB_TITLES

    def test_coordinator_in_job_titles(self) -> None:
        assert "Coordinator" in JOB_TITLES

    def test_director_in_job_titles(self) -> None:
        assert "Director" in JOB_TITLES

    def test_btech_in_academic(self) -> None:
        assert "B.Tech" in ACADEMIC_TERMS

    def test_all_categories_count(self) -> None:
        assert len(ALL_CATEGORIES) == 8

    def test_no_empty_categories(self) -> None:
        for category in ALL_CATEGORIES:
            assert len(category) > 0


class TestBuildAllowList:
    """Tests for the build_allow_list factory."""

    def test_returns_sorted_list(self) -> None:
        result = build_allow_list()
        assert result == sorted(result)

    def test_no_duplicates(self) -> None:
        result = build_allow_list()
        assert len(result) == len(set(result))

    def test_contains_key_terms(self) -> None:
        result = build_allow_list()
        assert "EPFL" in result
        assert "C++" in result
        assert "I" in result

    def test_extra_terms_added(self) -> None:
        result = build_allow_list(extra=frozenset({"CustomTerm"}))
        assert "CustomTerm" in result

    def test_exclude_terms_removed(self) -> None:
        result = build_allow_list(exclude=frozenset({"EPFL"}))
        assert "EPFL" not in result

    def test_activities_included(self) -> None:
        result = build_allow_list()
        assert "Swimming" in result
        assert "Archery" in result

    def test_languages_included(self) -> None:
        result = build_allow_list()
        assert "French" in result
        assert "German" in result
        assert "Arabic" in result

    def test_form_labels_included(self) -> None:
        result = build_allow_list()
        assert "Nom" in result
        assert "Prénom" in result

    def test_job_titles_included(self) -> None:
        result = build_allow_list()
        assert "Engineer" in result
        assert "Director" in result

    def test_all_categories_merged(self) -> None:
        result_set = set(build_allow_list())
        for category in (
            INSTITUTIONS,
            ACADEMIC_TERMS,
            PRONOUNS,
            TECHNICAL_TERMS,
            ACTIVITIES,
            LANGUAGES,
            FORM_LABELS,
            JOB_TITLES,
        ):
            assert category.issubset(result_set)
