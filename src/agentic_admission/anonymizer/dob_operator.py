"""Custom Presidio operator that preserves the birth year in DOB placeholders.

Produces ``<DOB_1995>`` instead of ``<DOB>`` so that age — a rejection
criterion — remains visible in anonymized dossiers while the full date
(day/month) is still redacted.
"""

from __future__ import annotations

import re
from typing import Any

from presidio_anonymizer.operators import Operator, OperatorType

_YEAR_PATTERN = re.compile(r"\b((?:19|20)\d{2})\b")
# Match 4-digit years from 1900-2099 at word boundaries.


class DobYearOperator(Operator):
    """Replace date-of-birth text with ``<DOB_YYYY>``, preserving the year.

    Falls back to ``<DOB>`` if no 4-digit year is found in the matched text.
    """

    def operate(self, text: str = "", params: dict[str, Any] | None = None) -> str:  # noqa: ARG002
        """Replace *text* with a year-preserving DOB placeholder.

        Parameters
        ----------
        text
            The matched entity text (e.g. ``"15/03/1995"``).
        params
            Unused operator parameters.

        Returns
        -------
        str
            ``<DOB_YYYY>`` if a year is found, otherwise ``<DOB>``.
        """
        match = _YEAR_PATTERN.search(text)
        if match:
            return f"<DOB_{match.group(1)}>"
        return "<DOB>"

    def validate(self, params: dict[str, Any] | None = None) -> None:
        """Validate operator parameters (none required)."""

    def operator_name(self) -> str:
        """Return the operator registry name."""
        return "dob_year"

    def operator_type(self) -> OperatorType:
        """Return the operator type (anonymize, not deanonymize)."""
        return OperatorType.Anonymize
