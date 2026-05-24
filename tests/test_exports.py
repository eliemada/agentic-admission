"""Unit tests for the dashboard CSV/Excel candidate export."""

from __future__ import annotations

import csv
import io

from dashboard.exports import _CANDIDATE_COLS, _flatten_candidate, candidates_to_csv


def _make_verdict(minor_recommendation: dict | None) -> dict:
    """Build a minimal verdict dict in the shape produced by ``load_verdict``."""
    return {
        "candidate_id": "2025-26-spring_abc123",
        "candidate_name": "Test Candidate",
        "school": "TU Delft",
        "status": "admit",
        "confidence": 0.82,
        "moderator": {"composite": 7.5},
        "gpa": "8.0",
        "gpa_max": "10",
        "gpa_normalized": 80.0,
        "final_scores": {
            "academic_strength": 8,
            "institution_quality": 7,
            "reference_quality": 7,
            "calibration_confidence": 6,
            "motivation_clarity": 8,
            "program_fit": 7,
            "risk_flags": 8,
            "consistency": 7,
        },
        "verdict_pros": ["Strong quant background", "Clear MTE motivation"],
        "verdict_cons": ["Gap year unexplained"],
        "minor_recommendation": minor_recommendation,
        "_override": {"decision": "accept", "comment": "looks great"},
    }


def _expected_minor_recommendation() -> dict:
    return {
        "primary_minor": "Space Technologies",
        "recommended": [
            {
                "minor_name": "Space Technologies",
                "section_code": "EL",
                "fit_score": 10,
                "reasoning": "Aerospace bachelor with strong control + signals coverage.",
            },
            {
                "minor_name": "Systems Engineering",
                "section_code": "MTE",
                "fit_score": 9,
                "reasoning": "Aerospace System Design course covers core systems prerequisites.",
            },
            {
                "minor_name": "Data Science",
                "section_code": "SC",
                "fit_score": 7,
                "reasoning": "Strong calculus + linear algebra foundation.",
            },
        ],
    }


def test_flatten_candidate_includes_minor_columns() -> None:
    """A verdict with a populated minor recommendation surfaces all three slots."""
    verdict = _make_verdict(_expected_minor_recommendation())
    row = _flatten_candidate(verdict)

    labels = [label for label, _ in _CANDIDATE_COLS]
    cells = dict(zip(labels, row, strict=True))

    assert cells["Primary Minor"] == "Space Technologies"
    assert cells["Minor #1"] == "Space Technologies"
    assert cells["Minor #1 Score"] == 10
    assert "Aerospace bachelor" in cells["Minor #1 Reason"]
    assert cells["Minor #2"] == "Systems Engineering"
    assert cells["Minor #2 Score"] == 9
    assert cells["Minor #3"] == "Data Science"
    assert cells["Minor #3 Score"] == 7


def test_flatten_candidate_handles_missing_minor() -> None:
    """Missing ``minor_recommendation`` produces blank — not absent — minor cells."""
    verdict = _make_verdict(None)
    row = _flatten_candidate(verdict)

    labels = [label for label, _ in _CANDIDATE_COLS]
    cells = dict(zip(labels, row, strict=True))

    for label in (
        "Primary Minor",
        "Minor #1",
        "Minor #1 Score",
        "Minor #1 Reason",
        "Minor #2",
        "Minor #2 Score",
        "Minor #2 Reason",
        "Minor #3",
        "Minor #3 Score",
        "Minor #3 Reason",
    ):
        assert cells[label] == "", f"{label!r} should be empty when minor_recommendation is None"


def test_flatten_candidate_handles_partial_minor_list() -> None:
    """A truncated recommendation list still produces a constant-width row."""
    rec = _expected_minor_recommendation()
    rec["recommended"] = rec["recommended"][:1]  # Only one suggestion
    verdict = _make_verdict(rec)
    row = _flatten_candidate(verdict)

    labels = [label for label, _ in _CANDIDATE_COLS]
    cells = dict(zip(labels, row, strict=True))

    assert cells["Minor #1"] == "Space Technologies"
    assert cells["Minor #2"] == ""
    assert cells["Minor #2 Score"] == ""
    assert cells["Minor #3"] == ""


def test_csv_export_emits_header_and_rows() -> None:
    """The CSV header includes the new minor columns and every row matches its width."""
    verdicts = [_make_verdict(_expected_minor_recommendation()), _make_verdict(None)]
    raw = candidates_to_csv(verdicts)
    text = raw.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    expected_labels = [label for label, _ in _CANDIDATE_COLS]
    assert rows[0] == expected_labels
    assert len(rows) == 1 + len(verdicts)
    assert "Minor #1 Reason" in rows[0]
    # Empty minor row keeps column width identical.
    assert len(rows[1]) == len(expected_labels)
    assert len(rows[2]) == len(expected_labels)
