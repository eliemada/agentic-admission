"""Deterministic GPA-vs-threshold comparison.

The committee's rule is mechanical: a candidate whose GPA falls below the
SPE-set institutional threshold is refused, with very few exceptions. The
LLM is bad at applying this rule consistently because it has to:

1. parse a free-text GPA value (``"3.7"``, ``"14.5/20"``, ``"30L"``),
2. parse a free-text threshold (``"1.7/1"``, ``"4.5"``, ``"80%"``),
3. know the direction of each grading system (German 1.0 = best, all
   others higher = better), and
4. apply the cap on ``academic_strength``.

This module replaces step 1-3 with deterministic parsers and produces a
:class:`ThresholdVerdict` that the orchestrator and Chair can act on
without any further LLM reasoning.

The gate is one-way only: a BELOW verdict mechanically forces rejection,
matching the committee's stated policy ("below the bar = refused"). It
does not provide an override path; if a candidate genuinely deserves an
exception, that decision happens in the committee meeting, not in the
agent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# Per-system numeric ranges (named constants — ruff PLR2004 forbids inline
# magic numbers in comparisons, and naming them makes the parsers easier
# to scan).
# ---------------------------------------------------------------------------

_US_MIN, _US_MAX = 0.0, 4.0
_SWISS_MIN, _SWISS_MAX = 1.0, 6.0
_FRENCH_MIN, _FRENCH_MAX = 0.0, 20.0
_GERMAN_MIN, _GERMAN_MAX = 1.0, 5.0
_ITALIAN_MIN, _ITALIAN_MAX = 18.0, 30.0
_INDIAN_MIN, _INDIAN_MAX = 0.0, 10.0
_PCT_MIN, _PCT_MAX = 0.0, 100.0
_ITALIAN_LODE_VALUE: float = 30.5

# UK-class equivalent percentages (committee-aligned).
_UK_FIRST: float = 75.0
_UK_UPPER_SECOND: float = 65.0
_UK_LOWER_SECOND: float = 55.0
_UK_THIRD: float = 45.0


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class ThresholdDirection(Enum):
    """Where the candidate sits relative to the SPE threshold."""

    BELOW = "below"
    """Below the threshold by more than the system's NEAR window."""

    NEAR = "near"
    """Within the system's NEAR window of the threshold (borderline case)."""

    ABOVE = "above"
    """At or above the threshold by more than the NEAR window."""

    UNKNOWN = "unknown"
    """Either side could not be parsed — the gate cannot decide."""


class GradingSystem(Enum):
    """Grading systems the gate can parse."""

    US_4 = "us_4"  # 0.0 - 4.0, higher = better
    SWISS_6 = "swiss_6"  # 1.0 - 6.0, higher = better
    FRENCH_20 = "french_20"  # 0 - 20, higher = better
    GERMAN_1_5 = "german_1_5"  # 1.0 - 5.0, LOWER = better
    ITALIAN_30 = "italian_30"  # 18 - 30 (+ lode), higher = better
    INDIAN_10 = "indian_10"  # 0 - 10, higher = better
    PERCENTAGE = "percentage"  # 0 - 100
    UK_CLASS = "uk_class"  # First / 2:1 / 2:2 / Third
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ThresholdVerdict:
    """Result of comparing a candidate's GPA to the SPE threshold.

    Attributes
    ----------
    direction
        Where the candidate sits relative to the threshold.
    gap
        Signed difference in the system's *natural* direction. Positive
        means "above threshold by ``gap``", negative means "below by
        ``|gap|``". Always positive=better, regardless of grading system.
    confidence
        Parser confidence in [0, 1]. ``0.9+`` when both sides parsed
        cleanly, lower when scale was inferred or a fallback applied.
    system
        The grading system used to compare both values.
    extracted_value
        The candidate's GPA on the system's native scale, after parsing.
        ``None`` when parsing failed.
    threshold_value
        The SPE threshold on the system's native scale, after parsing.
        ``None`` when parsing failed.
    notes
        Human-readable parser annotations (e.g. ``"30 e lode treated as 30.5"``,
        ``"Italian retakes can inflate averages — bar is 28+"``).
    """

    direction: ThresholdDirection
    gap: float
    confidence: float
    system: GradingSystem
    extracted_value: float | None = None
    threshold_value: float | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_prompt_line(self) -> str:
        """Format as a single line for injection into the agent prompt."""
        if self.direction is ThresholdDirection.UNKNOWN:
            return (
                f"GPA THRESHOLD VERDICT: UNKNOWN "
                f"(could not parse extracted GPA or threshold; system={self.system.value})"
            )
        return (
            f"GPA THRESHOLD VERDICT: {self.direction.value.upper()} "
            f"(extracted {self.extracted_value} vs threshold {self.threshold_value}, "
            f"gap {self.gap:+.2f}, system={self.system.value}, "
            f"confidence={self.confidence:.0%})"
        )


# ---------------------------------------------------------------------------
# Per-system parsers
# ---------------------------------------------------------------------------

_FLOAT_PATTERN = r"\d+(?:[.,]\d+)?"


def _to_float(token: str) -> float | None:
    """Parse a numeric token tolerant of comma decimals."""
    try:
        return float(token.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def _parse_simple_scale(raw: str, scale_pattern: str, lo: float, hi: float) -> float | None:
    """Parse ``"value"`` or ``"value/scale"`` into a float clamped to ``[lo, hi]``."""
    match = re.match(rf"^\s*({_FLOAT_PATTERN})\s*(?:/\s*{scale_pattern})?\s*$", raw or "")
    if match is None:
        return None
    val = _to_float(match.group(1))
    if val is None or not (lo <= val <= hi):
        return None
    return val


def _parse_us_4(raw: str) -> float | None:
    """Parse ``"3.7"`` or ``"3.7/4.0"`` style. Range 0.0-4.0."""
    return _parse_simple_scale(raw, r"4(?:\.0+)?", _US_MIN, _US_MAX)


def _parse_swiss_6(raw: str) -> float | None:
    """Parse ``"5.3"`` or ``"5.3/6"``. Range 1.0-6.0."""
    return _parse_simple_scale(raw, r"6(?:\.0+)?", _SWISS_MIN, _SWISS_MAX)


def _parse_french_20(raw: str) -> float | None:
    """Parse ``"14.5"`` or ``"14.5/20"``. Range 0-20."""
    return _parse_simple_scale(raw, r"20(?:\.0+)?", _FRENCH_MIN, _FRENCH_MAX)


def _parse_german(raw: str) -> float | None:
    """Parse ``"1.7"`` or ``"1.7/1"``. Range 1.0-5.0 (lower = better)."""
    return _parse_simple_scale(raw, r"[15](?:\.0+)?", _GERMAN_MIN, _GERMAN_MAX)


def _parse_italian_30(raw: str) -> float | None:
    """Parse ``"28"`` / ``"28/30"`` / ``"30L"`` / ``"30 e lode"``.

    Range 18-30. ``30 e lode`` and ``30L`` map to 30.5 (slightly above 30)
    so a "30 e lode" candidate compares strictly above a "30" threshold.
    """
    raw_lower = (raw or "").strip().lower()
    if not raw_lower:
        return None

    if "lode" in raw_lower or "laude" in raw_lower or re.search(r"30\s*l\b", raw_lower):
        match = re.search(r"(\d+)", raw_lower)
        if match and _to_float(match.group(1)) == _ITALIAN_MAX:
            return _ITALIAN_LODE_VALUE

    return _parse_simple_scale(raw_lower, r"30(?:\.0+)?", _ITALIAN_MIN, _ITALIAN_MAX)


def _parse_indian_10(raw: str) -> float | None:
    """Parse ``"8.5"`` or ``"8.5/10"``. Range 0-10 (CGPA)."""
    return _parse_simple_scale(raw, r"10(?:\.0+)?", _INDIAN_MIN, _INDIAN_MAX)


def _parse_percentage(raw: str) -> float | None:
    """Parse ``"85"`` or ``"85%"``. Range 0-100."""
    raw = (raw or "").strip().rstrip("%").strip()
    val = _to_float(raw)
    if val is None or not (_PCT_MIN <= val <= _PCT_MAX):
        return None
    return val


_UK_CLASS_TABLE: dict[str, float] = {
    "first": _UK_FIRST,
    "first class": _UK_FIRST,
    "first class honours": _UK_FIRST,
    "1st": _UK_FIRST,
    "upper second": _UK_UPPER_SECOND,
    "upper second class": _UK_UPPER_SECOND,
    "2:1": _UK_UPPER_SECOND,
    "2.1": _UK_UPPER_SECOND,
    "2i": _UK_UPPER_SECOND,
    "lower second": _UK_LOWER_SECOND,
    "lower second class": _UK_LOWER_SECOND,
    "2:2": _UK_LOWER_SECOND,
    "2.2": _UK_LOWER_SECOND,
    "2ii": _UK_LOWER_SECOND,
    "third": _UK_THIRD,
    "third class": _UK_THIRD,
    "3rd": _UK_THIRD,
}


def _parse_uk_class(raw: str) -> float | None:
    """Parse ``"First"`` / ``"2:1"`` / ``"2.2"``. Returns equivalent percentage."""
    if not raw:
        return None
    return _UK_CLASS_TABLE.get(raw.strip().lower())


# ---------------------------------------------------------------------------
# Per-system metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _SystemRule:
    """Per-system parser, direction, and NEAR window."""

    parser: Callable[[str], float | None]
    higher_is_better: bool
    near_window: float
    label: str


_SYSTEM_RULES: dict[GradingSystem, _SystemRule] = {
    GradingSystem.US_4: _SystemRule(
        parser=_parse_us_4, higher_is_better=True, near_window=0.10, label="US 4.0"
    ),
    GradingSystem.SWISS_6: _SystemRule(
        parser=_parse_swiss_6, higher_is_better=True, near_window=0.10, label="Swiss /6"
    ),
    GradingSystem.FRENCH_20: _SystemRule(
        parser=_parse_french_20, higher_is_better=True, near_window=0.50, label="French /20"
    ),
    GradingSystem.GERMAN_1_5: _SystemRule(
        parser=_parse_german, higher_is_better=False, near_window=0.10, label="German 1-5"
    ),
    GradingSystem.ITALIAN_30: _SystemRule(
        parser=_parse_italian_30, higher_is_better=True, near_window=0.50, label="Italian /30"
    ),
    GradingSystem.INDIAN_10: _SystemRule(
        parser=_parse_indian_10, higher_is_better=True, near_window=0.20, label="Indian CGPA /10"
    ),
    GradingSystem.PERCENTAGE: _SystemRule(
        parser=_parse_percentage, higher_is_better=True, near_window=1.0, label="Percentage"
    ),
    GradingSystem.UK_CLASS: _SystemRule(
        parser=_parse_uk_class, higher_is_better=True, near_window=5.0, label="UK classifications"
    ),
}


# ---------------------------------------------------------------------------
# System detection
# ---------------------------------------------------------------------------


_DETECTION_PATTERNS: tuple[tuple[GradingSystem, re.Pattern[str]], ...] = (
    (GradingSystem.UK_CLASS, re.compile(r"first|2:1|2:2|third|honour", re.IGNORECASE)),
    (GradingSystem.PERCENTAGE, re.compile(r"%|percent|/\s*100\b")),
    (GradingSystem.FRENCH_20, re.compile(r"/\s*20\b|\b20\s*$")),
    (GradingSystem.ITALIAN_30, re.compile(r"/\s*30\b|lode|laude|\b30\s*l\b", re.IGNORECASE)),
    (GradingSystem.INDIAN_10, re.compile(r"/\s*10\b|cgpa", re.IGNORECASE)),
    (GradingSystem.US_4, re.compile(r"/\s*4(?:\.0+)?\b")),
    (GradingSystem.SWISS_6, re.compile(r"/\s*6(?:\.0+)?\b|swiss", re.IGNORECASE)),
    # German is the awkward case: scale ``"1"`` means "best is 1.0". We
    # match either an explicit ``/1`` or a bare ``german``/``deutsch`` keyword.
    # Bare ``"1"`` alone is too ambiguous (could be a 1-credit course).
    (GradingSystem.GERMAN_1_5, re.compile(r"/\s*1\b|german|deutsch", re.IGNORECASE)),
)


def detect_grading_system(scale_hint: str, value_hint: str = "") -> GradingSystem:
    """Heuristically identify which grading system a value uses.

    Strategy:

    1. Look for an explicit scale anchor in either string (``"/20"``, ``"/30"``).
    2. Fall back to numeric range checks on ``value_hint``.

    Parameters
    ----------
    scale_hint
        The scale string (e.g. ``"/20"`` or ``"6"``). Usually the SPE
        threshold or the extractor's ``gpa_scale`` field.
    value_hint
        The candidate's GPA value, used as a fallback when ``scale_hint``
        is empty or ambiguous.

    Returns
    -------
    GradingSystem
        Detected system, or :data:`GradingSystem.UNKNOWN` when no rule
        matched.
    """
    haystack = f"{scale_hint or ''} {value_hint or ''}".strip()
    for system, pattern in _DETECTION_PATTERNS:
        if pattern.search(haystack):
            return system

    # Fallback: value-range heuristics. Ordered intervals; first match wins.
    val = _to_float((value_hint or "").strip().rstrip("%"))
    if val is None:
        return GradingSystem.UNKNOWN
    range_ladder: tuple[tuple[float, float, GradingSystem], ...] = (
        (_US_MIN, _US_MAX, GradingSystem.US_4),
        (_US_MAX, _SWISS_MAX, GradingSystem.SWISS_6),
        (_SWISS_MAX, _INDIAN_MAX, GradingSystem.INDIAN_10),
        (_INDIAN_MAX, _FRENCH_MAX, GradingSystem.FRENCH_20),
        (_FRENCH_MAX, _ITALIAN_MAX, GradingSystem.ITALIAN_30),
        (_ITALIAN_MAX, _PCT_MAX, GradingSystem.PERCENTAGE),
    )
    for lo, hi, system in range_ladder:
        if lo <= val <= hi:
            return system
    return GradingSystem.UNKNOWN


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _unknown(system: GradingSystem, *notes: str) -> ThresholdVerdict:
    return ThresholdVerdict(
        direction=ThresholdDirection.UNKNOWN,
        gap=0.0,
        confidence=0.0,
        system=system,
        notes=tuple(notes),
    )


_DEFAULT_PARSER_CONFIDENCE: float = 0.9
_UK_CLASS_CONFIDENCE: float = 0.7


def _classify_gap(gap: float, near_window: float) -> ThresholdDirection:
    """Map a signed gap to BELOW/NEAR/ABOVE."""
    if abs(gap) < near_window:
        return ThresholdDirection.NEAR
    return ThresholdDirection.ABOVE if gap >= 0 else ThresholdDirection.BELOW


def _system_notes(system: GradingSystem) -> tuple[tuple[str, ...], float]:
    """Return per-system parser notes and a confidence override."""
    if system is GradingSystem.ITALIAN_30:
        return (
            (
                "Italian system: averages can be inflated by retakes; "
                "the SPE threshold accounts for this.",
            ),
            _DEFAULT_PARSER_CONFIDENCE,
        )
    if system is GradingSystem.UK_CLASS:
        return (
            ("UK classifications are coarse — only NEAR/ABOVE/BELOW resolution.",),
            _UK_CLASS_CONFIDENCE,
        )
    return ((), _DEFAULT_PARSER_CONFIDENCE)


def _resolve_system(threshold: str, gpa_scale: str, gpa_value: str) -> GradingSystem:
    """Detect the grading system, threshold first then candidate scale."""
    system = detect_grading_system(threshold, gpa_value)
    if system is GradingSystem.UNKNOWN:
        system = detect_grading_system(gpa_scale, gpa_value)
    return system


_EPFL_INTERNAL_SUBJECTS: tuple[str, ...] = ("analysis", "algebra")


def epfl_internal_value(per_subject: dict[str, float] | None) -> str | None:
    """Compute the algebra+analysis average for EPFL-internal candidates.

    Returns ``None`` when neither subject is present (gate falls back to
    overall GPA in that case). Returns the rounded average as a string so
    it slots into :func:`compare_to_threshold` directly.
    """
    if not per_subject:
        return None
    relevant = [per_subject[k] for k in _EPFL_INTERNAL_SUBJECTS if k in per_subject]
    if not relevant:
        return None
    avg = sum(relevant) / len(relevant)
    return f"{avg:.3f}"


# ---------------------------------------------------------------------------
# EPFL-internal 3-band rule (Geraldine, 2026-05-12)
# ---------------------------------------------------------------------------
#
# Replaces the single 4.0 section-switcher threshold with three bands on
# the algebra+analysis Swiss /6 average:
#
#   - ``>= 4.5``        → ACCEPT (meets the EPFL-master standard)
#   - ``4.0 <= x < 4.5`` → DISCUSS (committee reviews in detail)
#   - ``< 4.0``         → REJECT (auto-handled, hard floor)
#
# The 4.0 floor is the only true rejection bar; the 4.0-4.5 band must
# reach the committee, not be auto-rejected. This is the rule that fired
# (informally) when the committee admitted Etienne Maillard at 4.31.

_EPFL_INTERNAL_ACCEPT_FLOOR: float = 4.5
_EPFL_INTERNAL_REJECT_FLOOR: float = 4.0


class EpflInternalBand(Enum):
    """Three-band classification for an EPFL-internal MTE candidate.

    Operates on the candidate's algebra + analysis average (Swiss /6).
    Only the Swiss /6 scale is supported — EPFL-internal candidates by
    definition come from EPFL bachelors, which always use this scale.
    """

    ACCEPT = "accept"
    """Average ≥ 4.5 — meets the EPFL-master academic bar."""

    DISCUSS = "discuss"
    """4.0 ≤ average < 4.5 — committee reviews case-by-case."""

    REJECT = "reject"
    """Average < 4.0 — auto-rejected by the hard floor."""

    UNKNOWN = "unknown"
    """Average could not be parsed as a Swiss /6 grade."""


def epfl_internal_band(value_str: str | None) -> EpflInternalBand:
    """Classify an EPFL-internal candidate by the 3-band committee rule.

    Parameters
    ----------
    value_str
        Algebra + analysis average as a string parseable by the Swiss /6
        parser (e.g. ``"4.31"`` or :func:`epfl_internal_value` output).

    Returns
    -------
    EpflInternalBand
        :data:`EpflInternalBand.ACCEPT`, :data:`DISCUSS`, :data:`REJECT`,
        or :data:`UNKNOWN` when parsing fails.

    Notes
    -----
    The thresholds (4.5 / 4.0) are committee policy, not parser tuning.
    Changing them changes admissions outcomes — do so only when minutes
    record a new rule.
    """
    if value_str is None:
        return EpflInternalBand.UNKNOWN
    val = _parse_swiss_6(value_str)
    if val is None:
        return EpflInternalBand.UNKNOWN
    if val >= _EPFL_INTERNAL_ACCEPT_FLOOR:
        return EpflInternalBand.ACCEPT
    if val >= _EPFL_INTERNAL_REJECT_FLOOR:
        return EpflInternalBand.DISCUSS
    return EpflInternalBand.REJECT


def _compare_via_normalized(
    *, gpa_normalized: float, gpa_scale: str, threshold: str
) -> ThresholdVerdict:
    """Compare LLM-normalized GPA (0-100) against a percentage threshold."""
    threshold_val = _parse_percentage(threshold)
    if threshold_val is None:
        return _unknown(
            GradingSystem.PERCENTAGE, f"Could not parse percentage threshold {threshold!r}"
        )
    gap = gpa_normalized - threshold_val
    direction = _classify_gap(gap, _SYSTEM_RULES[GradingSystem.PERCENTAGE].near_window)
    return ThresholdVerdict(
        direction=direction,
        gap=round(gap, 3),
        confidence=_DEFAULT_PARSER_CONFIDENCE,
        system=GradingSystem.PERCENTAGE,
        extracted_value=round(gpa_normalized, 2),
        threshold_value=threshold_val,
        notes=(
            f"Used LLM-normalized GPA ({gpa_normalized:.1f}/100) because "
            f"candidate scale {gpa_scale!r} disagrees with percentage threshold.",
        ),
    )


def _systems_match(threshold_system: GradingSystem, gpa_scale: str, gpa_value: str) -> bool:
    """Whether the candidate's scale + value are consistent with the threshold's system.

    The percentage parser accepts any number in [0, 100], which silently
    accepts a ``"7.37"`` (intended as Indian /10) as ``7.37%``. Use the
    candidate's ``gpa_scale`` and ``gpa_value`` as a sanity check before
    trusting the parser's output. Passing ``gpa_value`` lets the value-
    range fallback in :func:`detect_grading_system` kick in when the
    scale string is bare (e.g. ``"10"`` without a leading slash).
    """
    if not gpa_scale and not gpa_value:
        return True  # nothing to disagree about
    candidate_system = detect_grading_system(gpa_scale, gpa_value)
    if candidate_system is GradingSystem.UNKNOWN:
        return True
    return candidate_system is threshold_system


def compare_to_threshold(
    *,
    gpa_value: str,
    gpa_scale: str,
    threshold: str,
    gpa_normalized: float | None = None,
    school_name: str = "",  # reserved for future per-school tweaks
) -> ThresholdVerdict:
    """Compare a candidate's GPA against the SPE-set threshold.

    Detection priority is **threshold first**: SPE chooses the scale, so
    when the threshold can be parsed under system X, we parse the
    candidate's value under the same system X. This avoids
    misinterpreting a Swiss "5.3" as a German grade.

    When the candidate's ``gpa_scale`` disagrees with the threshold's
    detected system (e.g. threshold is ``"80%"`` but candidate is
    ``"7.37/10"``), the function uses ``gpa_normalized`` (0-100, from the
    LLM extractor) as a fallback against a percentage threshold. Without
    this, the percentage parser would silently accept ``"7.37"`` as
    ``7.37%`` and produce a false-reject.

    Parameters
    ----------
    gpa_value
        Candidate's GPA value as extracted from the transcript.
    gpa_scale
        Candidate's GPA scale string (e.g. ``"4.0"``, ``"20"``).
    threshold
        SPE-set threshold (e.g. ``"4.5"``, ``"1.7/1"``, ``"80%"``).
    gpa_normalized
        Optional 0-100 normalized GPA from the LLM extractor. Used as a
        cross-system fallback when ``gpa_scale`` disagrees with the
        threshold's system.
    school_name
        Reserved for future per-school adjustments. Currently unused.

    Returns
    -------
    ThresholdVerdict
        Structured comparison result. ``direction == UNKNOWN`` when
        either side cannot be parsed.
    """
    del school_name  # reserved

    cleaned_value = (gpa_value or "").strip()
    cleaned_threshold = (threshold or "").strip()
    if not cleaned_value or cleaned_value.upper() == "N/A":
        return _unknown(GradingSystem.UNKNOWN, "Candidate GPA is N/A or empty")
    if not cleaned_threshold:
        return _unknown(GradingSystem.UNKNOWN, "SPE threshold is empty")

    system = _resolve_system(threshold, gpa_scale, gpa_value)
    if system is GradingSystem.UNKNOWN:
        return _unknown(GradingSystem.UNKNOWN, "Could not identify grading system")

    rule = _SYSTEM_RULES[system]

    # System-mismatch fallback: when the candidate's own scale points to a
    # different system than the threshold's, the raw value cannot be
    # compared directly. Use the LLM-normalized 0-100 value against the
    # threshold parsed as a percentage.
    if (
        system is GradingSystem.PERCENTAGE
        and gpa_normalized is not None
        and not _systems_match(system, gpa_scale, gpa_value)
    ):
        return _compare_via_normalized(
            gpa_normalized=gpa_normalized, gpa_scale=gpa_scale, threshold=threshold
        )

    extracted = rule.parser(gpa_value)
    threshold_val = rule.parser(threshold)
    if extracted is None or threshold_val is None:
        which = "candidate GPA" if extracted is None else "threshold"
        token = gpa_value if extracted is None else threshold
        return _unknown(system, f"Could not parse {which} {token!r} under {rule.label}")

    # German: lower = better, so flip the sign so the contract holds:
    # positive gap always means "better than threshold".
    gap = extracted - threshold_val if rule.higher_is_better else threshold_val - extracted
    direction = _classify_gap(gap, rule.near_window)
    notes, confidence = _system_notes(system)

    return ThresholdVerdict(
        direction=direction,
        gap=round(gap, 3),
        confidence=confidence,
        system=system,
        extracted_value=extracted,
        threshold_value=threshold_val,
        notes=notes,
    )
