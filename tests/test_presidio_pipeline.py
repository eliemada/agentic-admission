"""Tests for the Presidio PII anonymization pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agentic_admission.anonymizer.presidio_pipeline import (
    _DOB_ENTITY_TYPES,
    _build_operators,
    _collect_md_files,
    _should_skip,
    anonymize_file,
    anonymize_text,
)

# ---------------------------------------------------------------------------
# Helper tests (no heavy deps needed)
# ---------------------------------------------------------------------------


class TestShouldSkip:
    """Tests for _should_skip freshness check."""

    def test_returns_false_if_dst_missing(self, tmp_path: Path) -> None:
        src = tmp_path / "input.md"
        src.write_text("hello")
        assert _should_skip(src, tmp_path / "output.md") is False

    def test_returns_true_if_dst_newer(self, tmp_path: Path) -> None:
        import os
        import time

        src = tmp_path / "input.md"
        src.write_text("hello")
        time.sleep(0.05)
        dst = tmp_path / "output.md"
        dst.write_text("anonymized")
        # Ensure dst is newer
        os.utime(dst, (dst.stat().st_mtime + 1, dst.stat().st_mtime + 1))
        assert _should_skip(src, dst) is True


class TestCollectMdFiles:
    """Tests for _collect_md_files directory walker."""

    def test_collects_md_files_in_order(self, tmp_path: Path) -> None:
        # semester/candidate/file.md
        s1 = tmp_path / "2024-fall"
        c1 = s1 / "alice"
        c1.mkdir(parents=True)
        (c1 / "cv.md").write_text("cv content")
        (c1 / "letter.md").write_text("letter content")

        c2 = s1 / "bob"
        c2.mkdir(parents=True)
        (c2 / "transcript.md").write_text("transcript")

        files = _collect_md_files(tmp_path)
        assert len(files) == 3
        # alice before bob (sorted), cv before letter (sorted)
        names = [f.name for f in files]
        assert names[0] == "cv.md"
        assert names[1] == "letter.md"
        assert names[2] == "transcript.md"

    def test_empty_dir(self, tmp_path: Path) -> None:
        files = _collect_md_files(tmp_path)
        assert files == []


class TestBuildOperators:
    """Tests for _build_operators operator config builder."""

    def test_known_entity_type(self) -> None:
        ops = _build_operators(["PERSON"])
        assert "PERSON" in ops

    def test_unknown_entity_type_gets_default(self) -> None:
        ops = _build_operators(["UNKNOWN_ENTITY"])
        assert "UNKNOWN_ENTITY" in ops

    def test_dob_entity_uses_dob_year_operator(self) -> None:
        """'date of birth' should use the custom dob_year operator."""
        ops = _build_operators(["date of birth"])
        assert "date of birth" in ops
        assert ops["date of birth"].operator_name == "dob_year"

    def test_date_time_still_uses_replace(self) -> None:
        """DATE_TIME (generic dates) should still use replace with <DATE>."""
        ops = _build_operators(["DATE_TIME"])
        assert ops["DATE_TIME"].operator_name == "replace"

    def test_dob_entity_types_constant(self) -> None:
        assert "date of birth" in _DOB_ENTITY_TYPES
        assert "DATE_TIME" not in _DOB_ENTITY_TYPES


# ---------------------------------------------------------------------------
# Core anonymization tests (using mocked engines)
# ---------------------------------------------------------------------------


class TestAnonymizeText:
    """Tests for anonymize_text using mocked Presidio engines."""

    def test_no_pii_returns_original(self) -> None:
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = []
        mock_anonymizer = MagicMock()

        text = "This text has no PII at all."
        result, counts = anonymize_text(text, mock_analyzer, mock_anonymizer)

        assert result == text
        assert counts == {}

    def test_with_pii_calls_anonymizer(self) -> None:
        # Build mock analyzer result with all attributes filters need
        mock_result = MagicMock()
        mock_result.entity_type = "PERSON"
        mock_result.start = 6
        mock_result.end = 16
        mock_result.score = 0.9

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = [mock_result]

        mock_anon_result = MagicMock()
        mock_anon_result.text = "Hello <PERSON>, welcome."

        mock_anonymizer = MagicMock()
        mock_anonymizer.anonymize.return_value = mock_anon_result

        text = "Hello John Smith, welcome."
        result, counts = anonymize_text(text, mock_analyzer, mock_anonymizer)

        assert result == "Hello <PERSON>, welcome."
        assert counts == {"PERSON": 1}
        mock_anonymizer.anonymize.assert_called_once()


class TestAnonymizeFile:
    """Tests for anonymize_file using mocked engines."""

    def test_anonymizes_file_content(self, tmp_path: Path) -> None:
        src = tmp_path / "input.md"
        src.write_text("Contact John at john@example.com", encoding="utf-8")
        dst = tmp_path / "output.md"

        mock_analyzer = MagicMock()
        person_result = MagicMock()
        person_result.entity_type = "PERSON"
        person_result.start = 8
        person_result.end = 12
        person_result.score = 0.9
        email_result = MagicMock()
        email_result.entity_type = "EMAIL_ADDRESS"
        email_result.start = 16
        email_result.end = 32
        email_result.score = 0.9
        mock_analyzer.analyze.return_value = [person_result, email_result]

        mock_anon_result = MagicMock()
        mock_anon_result.text = "Contact <PERSON> at <EMAIL>"
        mock_anonymizer = MagicMock()
        mock_anonymizer.anonymize.return_value = mock_anon_result

        counts = anonymize_file(src, dst, mock_analyzer, mock_anonymizer)

        assert dst.exists()
        assert dst.read_text(encoding="utf-8") == "Contact <PERSON> at <EMAIL>"
        assert counts["PERSON"] == 1
        assert counts["EMAIL_ADDRESS"] == 1

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        src = tmp_path / "empty.md"
        src.write_text("", encoding="utf-8")
        dst = tmp_path / "output.md"

        mock_analyzer = MagicMock()
        mock_anonymizer = MagicMock()

        counts = anonymize_file(src, dst, mock_analyzer, mock_anonymizer)

        assert counts == {}


# ---------------------------------------------------------------------------
# Integration test with real Presidio (marked slow)
# ---------------------------------------------------------------------------


class TestAnonymizeTextAllowListIntegration:
    """Tests that allow_list and filter_pipeline params are wired correctly."""

    def test_allow_list_disables_default(self) -> None:
        """Passing an explicit empty allow_list skips the domain defaults."""
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = []
        mock_anonymizer = MagicMock()

        anonymize_text("test", mock_analyzer, mock_anonymizer, allow_list=[])
        call_kwargs = mock_analyzer.analyze.call_args
        assert call_kwargs.kwargs.get("allow_list") == [] or call_kwargs[1].get("allow_list") == []

    def test_default_allow_list_populated(self) -> None:
        """Without explicit allow_list, the domain defaults are used."""
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = []
        mock_anonymizer = MagicMock()

        anonymize_text("test", mock_analyzer, mock_anonymizer)
        call_kwargs = mock_analyzer.analyze.call_args
        allow_list = call_kwargs.kwargs.get("allow_list") or call_kwargs[1].get("allow_list")
        assert allow_list is not None
        assert "EPFL" in allow_list
        assert "I" in allow_list

    def test_filter_pipeline_removes_all_returns_original(self) -> None:
        """If filters remove all results, original text is returned."""
        mock_result = MagicMock()
        mock_result.entity_type = "PERSON"
        mock_result.start = 0
        mock_result.end = 1
        mock_result.score = 0.3  # Below threshold

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = [mock_result]
        mock_anonymizer = MagicMock()

        text = "I am a student"
        result, counts = anonymize_text(text, mock_analyzer, mock_anonymizer)

        assert result == text
        assert counts == {}
        mock_anonymizer.anonymize.assert_not_called()


@pytest.mark.slow
class TestAnonymizeTextIntegration:
    """Integration tests using real Presidio engines.

    These tests require spaCy ``en_core_web_sm`` to be installed.
    Run with: ``uv run pytest -m slow``
    """

    @pytest.fixture
    def engines(self):
        """Build real analyzer and anonymizer engines."""
        from agentic_admission.anonymizer.presidio_pipeline import build_analyzer, build_anonymizer

        return build_analyzer(), build_anonymizer()

    def test_detects_email(self, engines) -> None:
        analyzer, anonymizer = engines
        text = "Please contact sarah.connor@example.com for details."
        result, _counts = anonymize_text(text, analyzer, anonymizer)

        assert "sarah.connor@example.com" not in result
        assert "<EMAIL>" in result or "<PII>" in result

    def test_detects_phone(self, engines) -> None:
        analyzer, anonymizer = engines
        text = "Call me at +41 79 123 45 67 for more info."
        result, _counts = anonymize_text(text, analyzer, anonymizer)

        assert "+41 79 123 45 67" not in result

    def test_detects_avs_number(self, engines) -> None:
        analyzer, anonymizer = engines
        text = "My AVS number is 756.1234.5678.90."
        result, _counts = anonymize_text(text, analyzer, anonymizer)

        assert "756.1234.5678.90" not in result


@pytest.mark.slow
class TestFalsePositiveRegression:
    """Regression tests proving specific false positives are fixed.

    Each test targets a known false-positive pattern observed on real
    EPFL admission dossiers.
    """

    @pytest.fixture
    def engines(self):
        """Build real analyzer and anonymizer engines."""
        from agentic_admission.anonymizer.presidio_pipeline import build_analyzer, build_anonymizer

        return build_analyzer(), build_anonymizer()

    def test_pronoun_i_preserved(self, engines) -> None:
        """'I' should NOT be redacted as <PERSON>."""
        analyzer, anonymizer = engines
        text = "I am confident that I can contribute to this program."
        result, _ = anonymize_text(text, analyzer, anonymizer)
        assert "I am confident" in result
        assert "I can contribute" in result

    def test_cpp_preserved(self, engines) -> None:
        """'C++' should NOT be redacted as <PERSON>."""
        analyzer, anonymizer = engines
        text = "I am proficient in C++ and Python."
        result, _ = anonymize_text(text, analyzer, anonymizer)
        assert "C++" in result
        assert "Python" in result

    def test_epfl_preserved(self, engines) -> None:
        """'EPFL' should NOT be redacted as <PII>."""
        analyzer, anonymizer = engines
        text = "I applied to EPFL for the Master in MTE program."
        result, _ = anonymize_text(text, analyzer, anonymizer)
        assert "EPFL" in result

    def test_degree_names_preserved(self, engines) -> None:
        """Degree names should NOT be redacted."""
        analyzer, anonymizer = engines
        text = "I hold a Bachelor of Science in Computer Science."
        result, _ = anonymize_text(text, analyzer, anonymizer)
        assert "Bachelor of Science" in result

    def test_duration_not_redacted(self, engines) -> None:
        """'5 years' should NOT be redacted as <DATE>."""
        analyzer, anonymizer = engines
        text = "I have 5 years of professional experience."
        result, _ = anonymize_text(text, analyzer, anonymizer)
        assert "5 years" in result

    def test_ielts_preserved(self, engines) -> None:
        """'IELTS' should NOT be redacted as <PII>."""
        analyzer, anonymizer = engines
        text = "My IELTS score is 7.5 overall."
        result, _ = anonymize_text(text, analyzer, anonymizer)
        assert "IELTS" in result

    def test_real_email_still_redacted(self, engines) -> None:
        """Real emails must still be caught."""
        analyzer, anonymizer = engines
        text = "Contact me at john.doe@gmail.com for questions."
        result, _ = anonymize_text(text, analyzer, anonymizer)
        assert "john.doe@gmail.com" not in result

    def test_real_phone_still_redacted(self, engines) -> None:
        """Real phone numbers must still be caught."""
        analyzer, anonymizer = engines
        text = "My phone is +41 78 123 45 67."
        result, _ = anonymize_text(text, analyzer, anonymizer)
        assert "+41 78 123 45 67" not in result

    def test_location_preserved(self, engines) -> None:
        """Locations should NOT be redacted (excluded entity)."""
        analyzer, anonymizer = engines
        text = "I studied at the university in Zurich, Switzerland."
        result, _ = anonymize_text(text, analyzer, anonymizer)
        assert "Zurich" in result
        assert "Switzerland" in result

    def test_language_names_preserved(self, engines) -> None:
        """Language names should NOT be redacted."""
        analyzer, anonymizer = engines
        text = "I speak French, German, and English fluently."
        result, _ = anonymize_text(text, analyzer, anonymizer)
        assert "French" in result
        assert "German" in result
        assert "English" in result
