"""Match dossier folders to CandidateRecord entries from the Parquet."""

from __future__ import annotations

import re
import unicodedata

from loguru import logger

from agentic_admission.models.candidate import CandidateRecord
from agentic_admission.models.dossier import Dossier

# ---------------------------------------------------------------------------
# Semester mapping
# ---------------------------------------------------------------------------

# Academic years in "{YYYY}" format (e.g. "2020", "2021") do not have
# corresponding dossier folders.  Only "{YYYY}-{YY}" years map to semesters.
_YEAR_RANGE_PATTERN = re.compile(r"^\d{4}-\d{2}$")

_ROUND_TO_SEASON: dict[str, str] = {"round1": "fall", "round2": "spring"}


def semester_from_record(academic_year: str, admission_round: str) -> str | None:
    """Map a candidate's year and round to a semester directory name.

    Parameters
    ----------
    academic_year
        E.g. ``"2024-25"`` or ``"2020"``.
    admission_round
        E.g. ``"round1"`` or ``"round2"``.

    Returns
    -------
    str | None
        Semester name like ``"2024-25-fall"``, or ``None`` if no dossier folder
        is expected (standalone years without dossiers).
    """
    if not _YEAR_RANGE_PATTERN.match(academic_year):
        return None
    season = _ROUND_TO_SEASON.get(admission_round)
    if season is None:
        return None
    return f"{academic_year}-{season}"


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------


def _strip_accents(text: str) -> str:
    """Remove diacritical marks from *text* (e.g. ``"ö"`` → ``"o"``)."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


# Lowercase particles that are typically part of compound last names
_PARTICLES: frozenset[str] = frozenset(
    {"von", "van", "de", "del", "der", "di", "el", "al", "ben", "bin", "da", "dos", "las", "los"}
)


def name_to_folder_key(name: str) -> str:
    """Return the *best-guess* folder key for a candidate name.

    This is a convenience wrapper around :func:`name_to_folder_candidates`
    that returns only the top candidate.  Used when a single key is needed.

    Parameters
    ----------
    name
        Full name in ``"Last [Last2…] First [Middle…]"`` order.

    Returns
    -------
    str
        Most-likely folder key, or ``""`` for empty input.
    """
    candidates = name_to_folder_candidates(name)
    return candidates[0] if candidates else ""


def name_to_folder_candidates(name: str) -> list[str]:
    """Generate possible folder keys for a candidate name, best-first.

    The dossier tree uses lowercased last names (with underscores for
    compounds).  Since we cannot always determine how many tokens form the
    last name vs. given names, we return multiple hypotheses:

    1. Particle-aware greedy match (e.g. ``"von_der_hoh"``).
    2. First two tokens joined (e.g. ``"aponte_gomez"``).
    3. First token only (e.g. ``"akiki"``).

    De-duplicated, preserving order.

    Parameters
    ----------
    name
        Full name in ``"Last [Last2…] First [Middle…]"`` order.

    Returns
    -------
    list[str]
        Possible folder keys, most likely first.
    """
    if not name.strip():
        return []

    tokens = name.split()
    normalized = [_strip_accents(t).lower() for t in tokens]

    if len(normalized) == 1:
        return [normalized[0]]

    candidates: list[str] = []

    # Strategy 1: particle-aware greedy consumption
    parts = [normalized[0]]
    for i in range(1, len(normalized)):
        remaining_after = len(normalized) - i - 1
        if remaining_after < 1:
            break
        if normalized[i] in _PARTICLES or (i > 0 and normalized[i - 1] in _PARTICLES):
            parts.append(normalized[i])
        else:
            break
    if len(parts) > 1:
        candidates.append("_".join(parts))

    # Strategy 2: first two tokens joined (covers compound surnames without
    # particles, like "Aponte Gomez")
    if len(normalized) >= 3:  # noqa: PLR2004 — need ≥1 given name left
        candidates.append("_".join(normalized[:2]))

    # Strategy 3: first token only (most common case)
    candidates.append(normalized[0])

    # De-duplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

MatchResult = tuple[list[Dossier], list[Dossier], list[CandidateRecord]]
# ``(matched_dossiers, unmatched_dossiers, unmatched_candidates)``.


def match_dossiers_to_candidates(
    dossiers: list[Dossier], candidates: list[CandidateRecord]
) -> MatchResult:
    """Match dossier folders to candidate records by name and semester.

    For each candidate, compute the expected semester and folder key, then
    look for a matching dossier.  Matched dossiers get a copy with the
    ``candidate`` field populated.

    Parameters
    ----------
    dossiers
        Dossier objects from :func:`scan_dossier_tree`.
    candidates
        Candidate records from the Parquet file.

    Returns
    -------
    MatchResult
        Tuple of (matched dossiers, unmatched dossiers, unmatched candidates).
    """
    # Index dossiers by (semester, folder_name)
    dossier_index: dict[tuple[str, str], Dossier] = {
        (d.semester, d.folder_name): d for d in dossiers
    }

    matched: list[Dossier] = []
    unmatched_candidates: list[CandidateRecord] = []
    matched_keys: set[tuple[str, str]] = set()

    for candidate in candidates:
        semester = semester_from_record(candidate.academic_year, candidate.admission_round)
        if semester is None:
            unmatched_candidates.append(candidate)
            continue

        folder_keys = name_to_folder_candidates(candidate.name)
        if not folder_keys:
            unmatched_candidates.append(candidate)
            continue

        found = False
        for folder_key in folder_keys:
            key = (semester, folder_key)
            dossier = dossier_index.get(key)
            if dossier is not None:
                matched_dossier = dossier.model_copy(update={"candidate": candidate})
                matched.append(matched_dossier)
                matched_keys.add(key)
                found = True
                break

        if not found:
            logger.debug("No dossier for {} in {}", folder_keys, semester)
            unmatched_candidates.append(candidate)

    unmatched_dossiers = [d for d in dossiers if (d.semester, d.folder_name) not in matched_keys]

    logger.info(
        "Matching: {} matched, {} unmatched dossiers, {} unmatched candidates",
        len(matched),
        len(unmatched_dossiers),
        len(unmatched_candidates),
    )
    return matched, unmatched_dossiers, unmatched_candidates
