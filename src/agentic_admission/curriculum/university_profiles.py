"""University profile builder: mines historical decisions + board overrides.

Two-layer system:
1. **Auto-generated** from historical parquet data (accept/reject rates,
   typical SPE GPA threshold, and EPFL-internal flag per school).
2. **Board overrides** in ``data/reference/university_overrides.yaml`` — human-editable
   file where the admissions board can add, correct, or annotate universities.

At evaluation time, overrides take precedence over auto-generated profiles.

Usage::

    # Generate profiles from historical data
    python -m agentic_admission.curriculum.university_profiles

    # Load merged profiles at evaluation time
    profiles = load_university_profiles()
    profile = profiles.get("Politecnico di Milano")

    # Fuzzy-lookup by an LLM-extracted institution name (different casing,
    # accents, partial match):
    profile = find_profile_by_name(profiles, "Politecnico di milano")
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from loguru import logger
from pydantic import BaseModel

_PARQUET_PATH = Path("data/processed/all_candidates.parquet")
_AUTO_OUTPUT = Path("data/reference/university_profiles.json")
_OVERRIDES_PATH = Path("data/reference/university_overrides.yaml")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class UniversityProfile(BaseModel, frozen=True):
    """Profile for a single university.

    Attributes
    ----------
    name : str
        University name (as it appears in the data).
    country : str
        Country (may be in French).
    tier : str
        Quality tier: A (priority), B (good), C (low interest), X (unknown).
    applicants : int
        Total number of historical applicants.
    accept_rate : float
        Historical acceptance rate (0.0-1.0).
    accepts : int
        Number of accepted candidates.
    rejects : int
        Number of rejected candidates.
    board_notes : str
        Free-text notes from the admissions board.
    """

    name: str
    country: str = ""
    tier: str = "X"
    applicants: int = 0
    accept_rate: float = 0.0
    accepts: int = 0
    rejects: int = 0
    board_notes: str = ""
    gpa_threshold: str = ""
    """Most-common SPE GPA admission threshold seen for this school
    (e.g. ``"3.5/4"``, ``"1.7/1"``, ``"80%"``, ``"28/30"``). Empty when
    historical rows did not carry one. Section-specific overrides
    (``"... for IC"``, ``"(GM: ...)"``) are stripped before counting.
    """

    is_epfl_internal: bool = False
    """``True`` when the school name matches an EPFL bachelor source.
    Computed at mine time via :func:`detect_epfl_internal`.
    """


# ---------------------------------------------------------------------------
# Decision normalization
# ---------------------------------------------------------------------------


def _normalize_decision(row: dict[str, Any]) -> str:
    """Normalize a committee decision to accept/reject/discuss/empty."""
    raw = (row.get("decision_final") or row.get("decision_section") or "").strip().lower()
    if raw in ("ok", "admis", "accepté", "accepted"):
        return "accept"
    if raw in ("no", "refusé", "refused", "rejected"):
        return "reject"
    if raw in ("a discuter", "waitlist", "liste attente"):
        return "discuss"
    return ""


def _normalize_tier(quality: str) -> str:
    """Extract tier letter from school_quality field."""
    q = quality.strip().upper()
    if q.startswith("A"):
        return "A"
    if q.startswith("B"):
        return "B"
    if q.startswith("C"):
        return "C"
    return "X"


_EPFL_NAME_PATTERNS: tuple[str, ...] = (
    "epfl",
    "polytechnique fédérale de lausanne",
    "polytechnique federale de lausanne",
    "ecole polytechnique fédérale",
    "ecole polytechnique federale",
    "swiss federal institute of technology lausanne",
)


def detect_epfl_internal(school_name: str) -> bool:
    """Return ``True`` when ``school_name`` matches an EPFL bachelor source.

    Mirrors :func:`agentic_admission.agents.dossier_loader.detect_epfl_internal`
    — kept duplicated here because ``curriculum`` should not import from
    ``agents``.
    """
    if not school_name:
        return False
    haystack = school_name.lower()
    return any(pattern in haystack for pattern in _EPFL_NAME_PATTERNS)


_PARENTHETICAL_RE = re.compile(r"\s*\([^)]*\)\s*")
_SECTION_TAIL_RE = re.compile(r"\s+(?:for|pour)\s+\w+.*$", re.IGNORECASE)
# Numeric threshold token: either a slash form (with optional spaces) or
# a percent form. Examples matched: "28/30", "3.5 / 4", "1.7/1", "80%".
_THRESHOLD_TOKEN_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?\b|\b\d+(?:\.\d+)?\s*%",
)


def parse_primary_threshold(raw: str) -> str:
    """Extract the primary threshold from a possibly-multi-section string.

    Real parquet values include section-specific overrides like
    ``"28/30 29/30 for IC"`` or ``"80% (GM: 3.7/4)"`` or
    ``"3.5 / 4 3.9 / 4 for IC"``. Take the first numeric threshold token
    and discard the rest. Categorical labels like ``"Top 10%"`` and
    ``"First class"`` are preserved verbatim — the GPA gate will return
    UNKNOWN for those, which is the right outcome.

    Parameters
    ----------
    raw
        The raw ``gpa_scale`` field from the parquet.

    Returns
    -------
    str
        Cleaned threshold (e.g. ``"28/30"``, ``"80%"``, ``"3.5 / 4"``)
        or the original string when no numeric token is present, or ``""``.
    """
    text = (raw or "").strip()
    if not text:
        return ""
    text = _PARENTHETICAL_RE.sub(" ", text).strip()
    text = _SECTION_TAIL_RE.sub("", text).strip()
    if not text:
        return ""
    # First numeric token wins. Special-case: "Top 10%" should not be
    # collapsed to "10%" because the categorical label encodes "top 10
    # percent of cohort", not "average 10%".
    if text.lower().startswith("top "):
        return text
    match = _THRESHOLD_TOKEN_RE.search(text)
    if match:
        # Collapse internal whitespace around the slash so downstream
        # parsers see "3.5/4" instead of "3.5 / 4".
        return re.sub(r"\s*/\s*", "/", match.group(0)).strip()
    return text


def _normalize_school_name(name: str) -> str:
    """Lowercase, strip accents, collapse whitespace.

    Used for fuzzy matching between LLM-extracted institution names and
    the canonical names stored in the profiles table.
    """
    if not name:
        return ""
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


# ---------------------------------------------------------------------------
# Mining
# ---------------------------------------------------------------------------


def mine_profiles(parquet_path: Path = _PARQUET_PATH) -> dict[str, UniversityProfile]:
    """Mine university profiles from historical candidate data.

    Parameters
    ----------
    parquet_path
        Path to ``all_candidates.parquet``.

    Returns
    -------
    dict[str, UniversityProfile]
        Keyed by university name.
    """
    table = pq.read_table(parquet_path)
    rows = table.to_pylist()

    schools: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = row["school_name"].strip()
        if not name or "inconnue" in name.lower() or "étrangère" in name.lower():
            continue

        decision = _normalize_decision(row)
        quality = row.get("school_quality", "")
        country = row.get("school_country", "").strip()
        threshold = parse_primary_threshold(row.get("gpa_scale", ""))

        if name not in schools:
            schools[name] = {
                "country": country,
                "tier": _normalize_tier(quality),
                "decisions": [],
                "thresholds": [],
                "tiers_seen": [],
            }

        if decision:
            schools[name]["decisions"].append(decision)
        if threshold:
            schools[name]["thresholds"].append(threshold)
        # Track tier votes too so a row with non-empty quality wins over
        # an earlier "X" default.
        normalized_tier = _normalize_tier(quality)
        schools[name]["tiers_seen"].append(normalized_tier)

    profiles: dict[str, UniversityProfile] = {}
    for name, data in schools.items():
        counts = Counter(data["decisions"])
        total = len(data["decisions"])
        accepts = counts.get("accept", 0)

        threshold_counter = Counter(data["thresholds"])
        primary_threshold = (
            threshold_counter.most_common(1)[0][0] if threshold_counter else ""
        )

        # Tier preference: most-common non-X, fall back to X.
        tier_counter = Counter(t for t in data["tiers_seen"] if t != "X")
        primary_tier = (
            tier_counter.most_common(1)[0][0] if tier_counter else "X"
        )

        profiles[name] = UniversityProfile(
            name=name,
            country=data["country"],
            tier=primary_tier,
            applicants=total,
            accept_rate=accepts / total if total > 0 else 0.0,
            accepts=accepts,
            rejects=counts.get("reject", 0),
            gpa_threshold=primary_threshold,
            is_epfl_internal=detect_epfl_internal(name),
        )

    logger.info("Mined {} university profiles from {}", len(profiles), parquet_path)
    return profiles


def save_profiles(profiles: dict[str, UniversityProfile], output_path: Path = _AUTO_OUTPUT) -> None:
    """Save auto-generated profiles to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {name: p.model_dump() for name, p in sorted(profiles.items())}
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved {} profiles to {}", len(data), output_path)


# ---------------------------------------------------------------------------
# Board overrides (YAML)
# ---------------------------------------------------------------------------


def _create_overrides_template(path: Path) -> None:
    """Create a starter overrides file with instructions."""
    template = """\
# University Overrides — Admissions Board
#
# Add or correct university profiles here. These take precedence
# over the auto-generated profiles from historical data.
#
# Fields:
#   tier: A (priority) | B (good) | C (low interest) | X (unknown)
#   board_notes: free-text context for evaluators
#
# Examples:
#
# Bocconi University:
#   tier: A
#   country: Italy
#   board_notes: "Top European business school, strong quant programs"
#
# Indian Institute of Technology (any campus):
#   tier: A
#   country: India
#   board_notes: "IIT system is highly selective, treat as tier A regardless of campus"
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(template, encoding="utf-8")
    logger.info("Created overrides template at {}", path)


def load_overrides(path: Path = _OVERRIDES_PATH) -> dict[str, dict[str, str]]:
    """Load board overrides from YAML.

    Returns
    -------
    dict[str, dict[str, str]]
        Keyed by university name, values are override fields.
    """
    if not path.exists():
        _create_overrides_template(path)
        return {}

    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        logger.warning("PyYAML not installed — skipping overrides")
        return {}

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}

    return {str(k): v for k, v in raw.items() if isinstance(v, dict)}


# ---------------------------------------------------------------------------
# Merged loading (auto + overrides)
# ---------------------------------------------------------------------------


def load_university_profiles(
    auto_path: Path = _AUTO_OUTPUT, overrides_path: Path = _OVERRIDES_PATH
) -> dict[str, UniversityProfile]:
    """Load merged university profiles (auto-generated + board overrides).

    Parameters
    ----------
    auto_path
        Path to auto-generated ``university_profiles.json``.
    overrides_path
        Path to board ``university_overrides.yaml``.

    Returns
    -------
    dict[str, UniversityProfile]
        Merged profiles keyed by university name.
    """
    # Load auto-generated
    profiles: dict[str, UniversityProfile] = {}
    if auto_path.exists():
        raw = json.loads(auto_path.read_text(encoding="utf-8"))
        for name, data in raw.items():
            profiles[name] = UniversityProfile.model_validate(data)
        logger.debug("Loaded {} auto-generated profiles", len(profiles))

    # Apply overrides
    overrides = load_overrides(overrides_path)
    for name, fields in overrides.items():
        if name in profiles:
            # Merge: override fields take precedence
            updated = profiles[name].model_dump()
            updated.update({k: v for k, v in fields.items() if v is not None})
            profiles[name] = UniversityProfile.model_validate(updated)
        else:
            # New university from board
            profiles[name] = UniversityProfile(name=name, **fields)

    if overrides:
        logger.info("Applied {} board overrides", len(overrides))

    return profiles


def find_profile_by_name(
    profiles: dict[str, UniversityProfile], school_name: str
) -> UniversityProfile | None:
    """Look up a profile by ``school_name`` with normalization + substring fallback.

    Resolution order:

    1. Exact match on the canonical key.
    2. Exact match on the *normalized* (lowercase, accent-stripped) key.
    3. Substring match in either direction. The longest matching candidate
       wins to prefer ``"École Polytechnique Fédérale de Lausanne"`` over
       ``"École Polytechnique"`` when the LLM returns the former.

    Parameters
    ----------
    profiles
        Loaded profile table (from :func:`load_university_profiles`).
    school_name
        Free-text school name, typically the LLM-extracted institution.

    Returns
    -------
    UniversityProfile | None
        Best-effort match, or ``None`` when no candidate matches.
    """
    if not school_name:
        return None

    direct = profiles.get(school_name)
    if direct is not None:
        return direct

    normalized = _normalize_school_name(school_name)
    if not normalized:
        return None

    # Pre-build the normalized index once; small relative to load cost.
    indexed = [(canonical, _normalize_school_name(canonical), p) for canonical, p in profiles.items()]

    for _, norm_canon, profile in indexed:
        if norm_canon == normalized:
            return profile

    # Substring match — longest canonical wins (more specific).
    candidates = [
        (canonical, profile)
        for canonical, norm_canon, profile in indexed
        if norm_canon and (norm_canon in normalized or normalized in norm_canon)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda kv: len(kv[0]), reverse=True)
    return candidates[0][1]


def format_university_context(profiles: dict[str, UniversityProfile], school_name: str) -> str:
    """Format a university profile as concise context for an evaluator.

    Parameters
    ----------
    profiles
        Loaded profiles.
    school_name
        The candidate's university name.

    Returns
    -------
    str
        Short context string, or empty if unknown.
    """
    profile = profiles.get(school_name)
    if profile is None:
        return ""

    parts = [f"Tier {profile.tier}"]
    if profile.applicants > 0:
        parts.append(f"{profile.accept_rate:.0%} accept rate ({profile.applicants} applicants)")
    if profile.board_notes:
        parts.append(profile.board_notes)

    return f"[{school_name}: {', '.join(parts)}]"


# ---------------------------------------------------------------------------
# CLI: generate profiles
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    profiles = mine_profiles()
    save_profiles(profiles)

    # Also create overrides template if it doesn't exist
    if not _OVERRIDES_PATH.exists():
        _create_overrides_template(_OVERRIDES_PATH)
