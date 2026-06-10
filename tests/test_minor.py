"""Tests for the EPFL minor registry and recommendation-exclusion rules."""

from __future__ import annotations

import pytest

from agentic_admission.models.minor import (
    ALL_MINORS,
    format_minor_list,
    get_minor_by_name,
    is_mte_master_minor,
    is_non_recommendable_minor,
    selectable_minors,
)

_MTE_MASTER_MINOR = "Management, Technology and Entrepreneurship"
_FINANCIAL_ENGINEERING = "Financial Engineering"


@pytest.mark.unit
class TestNonRecommendableMinors:
    """The MTE master minor and Financial Engineering can never be recommended."""

    @pytest.mark.parametrize("name", [_MTE_MASTER_MINOR, _FINANCIAL_ENGINEERING])
    def test_flagged_non_recommendable(self, name: str) -> None:
        assert is_non_recommendable_minor(name)

    @pytest.mark.parametrize("name", [_MTE_MASTER_MINOR, _FINANCIAL_ENGINEERING])
    def test_match_is_case_and_whitespace_insensitive(self, name: str) -> None:
        assert is_non_recommendable_minor(f"  {name.upper()}  ")

    @pytest.mark.parametrize("name", ["Computer Science", "Systems Engineering", "Statistics"])
    def test_ordinary_minors_are_recommendable(self, name: str) -> None:
        assert not is_non_recommendable_minor(name)

    def test_empty_string_is_not_flagged(self) -> None:
        assert not is_non_recommendable_minor("")

    def test_mte_predicate_still_only_matches_mte(self) -> None:
        # The narrow MTE predicate must NOT swallow Financial Engineering —
        # only the broader is_non_recommendable_minor does.
        assert is_mte_master_minor(_MTE_MASTER_MINOR)
        assert not is_mte_master_minor(_FINANCIAL_ENGINEERING)


@pytest.mark.unit
class TestSelectableMinors:
    """selectable_minors() excludes the non-recommendable set but keeps the registry whole."""

    def test_financial_engineering_excluded(self) -> None:
        names = {m.name for m in selectable_minors()}
        assert _FINANCIAL_ENGINEERING not in names

    def test_mte_master_minor_excluded(self) -> None:
        names = {m.name for m in selectable_minors()}
        assert _MTE_MASTER_MINOR not in names

    def test_excludes_exactly_the_non_recommendable_set(self) -> None:
        selectable = {m.name for m in selectable_minors()}
        every = {m.name for m in ALL_MINORS}
        assert every - selectable == {_MTE_MASTER_MINOR, _FINANCIAL_ENGINEERING}

    def test_financial_engineering_remains_in_registry(self) -> None:
        # Kept in ALL_MINORS so historical transcripts still resolve it.
        assert get_minor_by_name(_FINANCIAL_ENGINEERING) is not None

    def test_format_minor_list_omits_non_recommendable(self) -> None:
        listing = format_minor_list()
        assert _FINANCIAL_ENGINEERING not in listing
        assert _MTE_MASTER_MINOR not in listing
