"""Tests for the DobYearOperator custom Presidio operator."""

from __future__ import annotations

import pytest
from presidio_anonymizer.operators import OperatorType

from agentic_admission.anonymizer.dob_operator import DobYearOperator


@pytest.fixture
def operator() -> DobYearOperator:
    """Create a DobYearOperator instance."""
    return DobYearOperator()


class TestDobYearOperator:
    """Tests for year extraction and placeholder generation."""

    def test_extracts_year_from_slash_date(self, operator: DobYearOperator) -> None:
        assert operator.operate("15/03/1995") == "<DOB_1995>"

    def test_extracts_year_from_dash_date(self, operator: DobYearOperator) -> None:
        assert operator.operate("1990-05-15") == "<DOB_1990>"

    def test_extracts_year_from_written_date(self, operator: DobYearOperator) -> None:
        assert operator.operate("March 15, 2001") == "<DOB_2001>"

    def test_extracts_year_standalone(self, operator: DobYearOperator) -> None:
        assert operator.operate("1988") == "<DOB_1988>"

    def test_extracts_year_2000s(self, operator: DobYearOperator) -> None:
        assert operator.operate("Born 2003") == "<DOB_2003>"

    def test_fallback_no_year(self, operator: DobYearOperator) -> None:
        assert operator.operate("some text without year") == "<DOB>"

    def test_fallback_empty_string(self, operator: DobYearOperator) -> None:
        assert operator.operate("") == "<DOB>"

    def test_first_year_wins(self, operator: DobYearOperator) -> None:
        """If multiple years present, the first is used."""
        assert operator.operate("1995-2020") == "<DOB_1995>"

    def test_ignores_non_year_numbers(self, operator: DobYearOperator) -> None:
        """Numbers outside 1900-2099 are not matched."""
        assert operator.operate("Score: 850") == "<DOB>"

    def test_boundary_year_1900(self, operator: DobYearOperator) -> None:
        assert operator.operate("1900") == "<DOB_1900>"

    def test_boundary_year_2099(self, operator: DobYearOperator) -> None:
        assert operator.operate("2099") == "<DOB_2099>"


class TestDobYearOperatorMeta:
    """Tests for operator metadata."""

    def test_operator_name(self, operator: DobYearOperator) -> None:
        assert operator.operator_name() == "dob_year"

    def test_operator_type(self, operator: DobYearOperator) -> None:
        assert operator.operator_type() == OperatorType.Anonymize

    def test_validate_no_error(self, operator: DobYearOperator) -> None:
        """validate() should not raise."""
        operator.validate()
        operator.validate(params={})
