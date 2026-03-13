"""Custom Presidio recognizers for Swiss and EPFL-specific PII.

Recognizers
-----------
AvsAhvRecognizer
    Swiss social security numbers (AVS/AHV) in format ``756.XXXX.XXXX.XX``.
SciperRecognizer
    EPFL SCIPER student IDs (6-digit numbers with contextual keywords).
"""

from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

# ---------------------------------------------------------------------------
# AVS / AHV recognizer
# ---------------------------------------------------------------------------

_AVS_PATTERNS = [
    Pattern(name="avs_dots", regex=r"\b756\.\d{4}\.\d{4}\.\d{2}\b", score=0.9),
    Pattern(name="avs_dashes", regex=r"\b756-\d{4}-\d{4}-\d{2}\b", score=0.9),
    Pattern(name="avs_spaces", regex=r"\b756\s\d{4}\s\d{4}\s\d{2}\b", score=0.85),
]


class AvsAhvRecognizer(PatternRecognizer):
    """Detect Swiss AVS/AHV social security numbers.

    Matches the format ``756.XXXX.XXXX.XX`` with dots, dashes, or spaces.
    The ``756`` prefix is specific to Switzerland.
    """

    def __init__(self) -> None:
        super().__init__(
            supported_entity="CH_AHV",
            patterns=_AVS_PATTERNS,
            supported_language="en",
            context=["AVS", "AHV", "numéro", "sécurité sociale", "social security"],
        )


# ---------------------------------------------------------------------------
# SCIPER recognizer
# ---------------------------------------------------------------------------

_SCIPER_PATTERNS = [Pattern(name="sciper_6digit", regex=r"\b\d{6}\b", score=0.3)]

_SCIPER_CONTEXT = ["SCIPER", "sciper", "Sciper", "matricule", "student ID", "numéro étudiant"]


class SciperRecognizer(PatternRecognizer):
    """Detect EPFL SCIPER student identification numbers.

    Matches exactly 6 digits. Because this is ambiguous (any 6-digit number),
    the base score is low (0.3) and relies on contextual keywords like
    ``SCIPER`` or ``matricule`` within the surrounding text to boost
    confidence above the detection threshold.
    """

    def __init__(self) -> None:
        super().__init__(
            supported_entity="EPFL_SCIPER",
            patterns=_SCIPER_PATTERNS,
            supported_language="en",
            context=_SCIPER_CONTEXT,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_custom_recognizers() -> list[PatternRecognizer]:
    """Return instances of all custom recognizers."""
    return [AvsAhvRecognizer(), SciperRecognizer()]
