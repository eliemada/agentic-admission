"""Tests for custom Presidio recognizers (AVS/AHV and SCIPER)."""

from __future__ import annotations

from presidio_analyzer import Pattern

from agentic_admission.anonymizer.recognizers import (
    AvsAhvRecognizer,
    SciperRecognizer,
    build_custom_recognizers,
)


class TestAvsAhvRecognizer:
    """Tests for Swiss AVS/AHV social security number recognizer."""

    def test_supported_entity(self) -> None:
        rec = AvsAhvRecognizer()
        assert rec.supported_entities == ["CH_AHV"]

    def test_has_patterns(self) -> None:
        rec = AvsAhvRecognizer()
        assert len(rec.patterns) == 3
        assert all(isinstance(p, Pattern) for p in rec.patterns)

    def test_dots_pattern_matches(self) -> None:
        import re

        rec = AvsAhvRecognizer()
        dots_pattern = next(p for p in rec.patterns if p.name == "avs_dots")
        assert re.search(dots_pattern.regex, "756.1234.5678.90")

    def test_dashes_pattern_matches(self) -> None:
        import re

        rec = AvsAhvRecognizer()
        dashes_pattern = next(p for p in rec.patterns if p.name == "avs_dashes")
        assert re.search(dashes_pattern.regex, "756-1234-5678-90")

    def test_spaces_pattern_matches(self) -> None:
        import re

        rec = AvsAhvRecognizer()
        spaces_pattern = next(p for p in rec.patterns if p.name == "avs_spaces")
        assert re.search(spaces_pattern.regex, "756 1234 5678 90")

    def test_rejects_non_swiss(self) -> None:
        import re

        rec = AvsAhvRecognizer()
        dots_pattern = next(p for p in rec.patterns if p.name == "avs_dots")
        assert re.search(dots_pattern.regex, "123.4567.8901.23") is None


class TestSciperRecognizer:
    """Tests for EPFL SCIPER student ID recognizer."""

    def test_supported_entity(self) -> None:
        rec = SciperRecognizer()
        assert rec.supported_entities == ["EPFL_SCIPER"]

    def test_pattern_matches_six_digits(self) -> None:
        import re

        rec = SciperRecognizer()
        pattern = rec.patterns[0]
        assert re.search(pattern.regex, "123456")
        assert re.search(pattern.regex, "000001")

    def test_pattern_rejects_non_six_digits(self) -> None:
        import re

        rec = SciperRecognizer()
        pattern = rec.patterns[0]
        # 5 digits - no match at word boundary
        assert re.fullmatch(pattern.regex.strip(r"\b"), "12345") is None

    def test_has_context_words(self) -> None:
        rec = SciperRecognizer()
        assert "SCIPER" in rec.context


class TestBuildCustomRecognizers:
    """Tests for the factory function."""

    def test_returns_two_recognizers(self) -> None:
        recs = build_custom_recognizers()
        assert len(recs) == 2
        types = {type(r).__name__ for r in recs}
        assert "AvsAhvRecognizer" in types
        assert "SciperRecognizer" in types
