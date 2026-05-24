"""Deterministic minor recommendations for EPFL-internal candidates.

For EPFL-bachelor applicants, the committee's actual minor-assignment
heuristic is "stay within or adjacent to the bachelor's section". This
module encodes that heuristic as a fixed table so EPFL-internal candidates
get a predictable, reviewable recommendation without an LLM call.

Detection works against the EPFL ``Synthese de la candidature`` form,
which always lists the bachelor under ``Domaine principal d'études``.
When detection fails (non-EPFL candidate, missing field, OCR garble),
callers should fall back to :func:`agentic_admission.agents.minor_advisor.recommend_minor`
in its LLM-driven mode.
"""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import TYPE_CHECKING

from agentic_admission.models.evaluation import MinorRecommendation, MinorScore
from agentic_admission.models.minor import ALL_MINORS, get_minor_by_name

if TYPE_CHECKING:
    from collections.abc import Mapping

# Fixed scores assigned to the 3 deterministic recommendations (best → 3rd).
# Reserved range is intentionally above 7 to make these visually distinct
# from LLM-produced 1-10 fit scores in the dashboard.
_FIT_SCORE_TOP: int = 10
_FIT_SCORE_SECOND: int = 9
_FIT_SCORE_THIRD: int = 8

_RECOMMENDATION_REASON: str = (
    "Section-default minor for EPFL {bachelor} bachelor — selected "
    "deterministically from the committee's section-adjacency rule."
)

# Map of EPFL bachelor name (French, exactly as it appears in the
# ``Domaine principal d'études`` field of the synthese) to a tuple of
# ``(section_code, ranked minor names)``.
#
# Sources:
# * 17 bachelor names scraped from edu.epfl.ch (see
#   ``data/reference/epfl_curriculum/programs.parquet``).
# * 36 minors from ``models.minor.ALL_MINORS`` (TTC excluded — no longer
#   offered from September 2025).
# * Section-adjacency mapping confirmed with the supervisor on 2026-05-09.
#
# Keys are exact matches (no fuzzy matching) so that mis-spellings or
# legacy bachelor names route to the LLM fallback rather than silently
# pick a wrong section.
_EPFL_BACHELOR_TO_MINORS_RAW: dict[str, tuple[str, tuple[str, str, str]]] = {
    "Informatique": ("IN", ("Computer Science", "Cyber Security", "Data Science")),
    "Systèmes de communication": (
        "SC",
        ("Data Science", "Cyber Security", "Communication Systems"),
    ),
    "Mathématiques": ("MA", ("Mathematics", "Statistics", "Computational Science and Engineering")),
    "Physique": ("PH", ("Physics", "Quantum Science and Engineering", "Photonics")),
    "Génie électrique et électronique": (
        "EL",
        (
            "Electrical and Electronic Engineering",
            "Data and Internet of Things",
            "Space Technologies",
        ),
    ),
    "Génie mécanique": (
        "GM",
        ("Mechanical Engineering", "Energy", "Materials Science and Engineering"),
    ),
    "Microtechnique": ("MT", ("Microengineering", "Photonics", "Biomedical Technologies")),
    "Science et génie des matériaux": (
        "MX",
        ("Materials Science and Engineering", "Chemistry and Chemical Engineering", "Energy"),
    ),
    "Ingénierie des sciences du vivant": (
        "SV",
        ("Life Sciences Engineering", "Computational Biology", "Neuro-X"),
    ),
    "Chimie et génie chimique": (
        "CGC",
        (
            "Chemistry and Chemical Engineering",
            "Biotechnology",
            "Materials Science and Engineering",
        ),
    ),
    "Chimie": (
        "CGC",
        (
            "Chemistry and Chemical Engineering",
            "Biotechnology",
            "Materials Science and Engineering",
        ),
    ),
    "Génie chimique": (
        "CGC",
        (
            "Chemistry and Chemical Engineering",
            "Biotechnology",
            "Materials Science and Engineering",
        ),
    ),
    "Génie civil": ("GC", ("Civil Engineering", "Sustainable Construction", "Energy")),
    "Sciences et ingénierie de l'environnement": (
        "SIE",
        ("Environmental Sciences and Engineering", "Engineering for Sustainability", "Energy"),
    ),
    "Architecture": (
        "AR",
        (
            "Architecture",
            "Integrated Design, Architecture and Sustainability (IDEAS)",
            "Sustainable Construction",
        ),
    ),
    "Sciences humaines et sociales": (
        "SHS",
        ("Digital Humanities, Media and Society", "Systems Engineering", "Financial Engineering"),
    ),
}


def _validate_table_against_registry() -> None:
    """Fail fast at import if any mapped minor name isn't in ``ALL_MINORS``.

    The 3-entry-per-bachelor invariant is already enforced by the
    ``tuple[str, str, str]`` value type — no runtime check needed.
    """
    known_names = {m.name for m in ALL_MINORS}
    bad: list[tuple[str, str]] = [
        (bachelor, name)
        for bachelor, (_section, minors) in _EPFL_BACHELOR_TO_MINORS_RAW.items()
        for name in minors
        if name not in known_names
    ]
    if bad:
        details = ", ".join(f"{b}->{n!r}" for b, n in bad)
        msg = f"EPFL minor mapping references unknown minors: {details}"
        raise ValueError(msg)


_validate_table_against_registry()

# Read-only mapping: EPFL bachelor name -> (section, top-3 minors).
#
# Exposed via ``MappingProxyType`` so callers cannot mutate the table at
# runtime. Order of the minor tuple is the recommendation order (best
# fit first).
EPFL_BACHELOR_TO_MINORS: Mapping[str, tuple[str, tuple[str, str, str]]] = MappingProxyType(
    _EPFL_BACHELOR_TO_MINORS_RAW
)


# Anchored on the labelled form field rather than free-text bachelor names
# to avoid false positives in motivation letters / CV ("...interested in
# microengineering...").
_DOMAIN_RE: re.Pattern[str] = re.compile(
    r"Domaine principal d'[ée]tudes\s*\n\s*([^\n]+)", re.IGNORECASE
)

_EPFL_MARKER_RE: re.Pattern[str] = re.compile(
    r"Ecole polytechnique f[ée]d[ée]rale de Lausanne EPFL", re.IGNORECASE
)


def detect_epfl_bachelor(dossier_text: str) -> str | None:
    """Return the EPFL bachelor name (French) found in the dossier text.

    Detection requires both:

    1. The candidate's listed institution contains the EPFL marker
       (``Ecole polytechnique fédérale de Lausanne EPFL``).
    2. The ``Domaine principal d'études`` form field is present and
       its value matches a known bachelor in
       :data:`EPFL_BACHELOR_TO_MINORS`.

    Returns ``None`` when either condition fails. The caller should
    then fall back to LLM-driven recommendation.

    Parameters
    ----------
    dossier_text
        Concatenated markdown of all dossier documents (typically
        ``DossierContent.full_dossier_text``).

    Returns
    -------
    str | None
        Exact bachelor name as it appears in the mapping table, or
        ``None`` if not detected / not mapped.
    """
    if not dossier_text or not _EPFL_MARKER_RE.search(dossier_text):
        return None
    match = _DOMAIN_RE.search(dossier_text)
    if match is None:
        return None
    candidate = match.group(1).strip()
    if candidate in EPFL_BACHELOR_TO_MINORS:
        return candidate
    # Try a relaxed match against the keys (case-insensitive) so that
    # minor capitalisation drift in OCR doesn't defeat detection.
    lowered = candidate.lower()
    for key in EPFL_BACHELOR_TO_MINORS:
        if key.lower() == lowered:
            return key
    return None


def build_deterministic_recommendation(bachelor_fr: str) -> MinorRecommendation:
    """Build the deterministic ``MinorRecommendation`` for an EPFL bachelor.

    Each recommended minor's ``section_code`` is taken from the registry
    (``ALL_MINORS``), not from the bachelor's section — these can differ
    (e.g., a CS bachelor → Data Science minor, which is owned by SC).

    Parameters
    ----------
    bachelor_fr
        French bachelor name. Must be a key in :data:`EPFL_BACHELOR_TO_MINORS`.

    Returns
    -------
    MinorRecommendation
        Three ranked minors with fixed scores 10/9/8 and a deterministic
        reasoning string.

    Raises
    ------
    KeyError
        If ``bachelor_fr`` is not in the mapping. Callers should normally
        check via :func:`detect_epfl_bachelor` before invoking this.
    """
    section, names = EPFL_BACHELOR_TO_MINORS[bachelor_fr]
    fit_scores = (_FIT_SCORE_TOP, _FIT_SCORE_SECOND, _FIT_SCORE_THIRD)
    reasoning = _RECOMMENDATION_REASON.format(bachelor=bachelor_fr)

    scored: list[MinorScore] = []
    for name, fit in zip(names, fit_scores, strict=True):
        minor = get_minor_by_name(name)
        # Mapping is validated at import; this lookup cannot fail.
        assert minor is not None, f"Mapped minor {name!r} missing from registry"
        scored.append(
            MinorScore(
                minor_name=minor.name,
                section_code=minor.section_code,
                fit_score=fit,
                reasoning=reasoning,
            )
        )

    # Bachelor's section is informational; not currently surfaced on
    # MinorRecommendation but kept here to make logging callers aware.
    _ = section

    return MinorRecommendation(recommended=tuple(scored), primary_minor=scored[0].minor_name)
