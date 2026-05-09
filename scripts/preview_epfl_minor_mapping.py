"""Preview: deterministic EPFL-internal minor recommendations.

Detects each EPFL-internal candidate's bachelor program from the synthese
file, then maps it to a fixed shortlist of 3 minors per the proposed
section→minors table. Pure preview — no production code is touched.

Run with::

    uv run python scripts/preview_epfl_minor_mapping.py
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

_ANON_ROOT = Path("data/processed/anonymized/2025-26-spring")

# Official EPFL bachelor name (French, as it appears in the synthese form)
# → (section_code, ranked tuple of 3 minors).
# Names cover all 17 bachelors detected in the curriculum scrape, plus
# the legacy "Génie chimique"/"Chimie" splits that the unified
# "Chimie et génie chimique" bachelor descends from.
_BACHELOR_TO_MINORS: dict[str, tuple[str, tuple[str, str, str]]] = {
    "Informatique": (
        "IN",
        ("Computer Science", "Cyber Security", "Data Science"),
    ),
    "Systèmes de communication": (
        "SC",
        ("Data Science", "Cyber Security", "Communication Systems"),
    ),
    "Mathématiques": (
        "MA",
        ("Mathematics", "Statistics", "Computational Science and Engineering"),
    ),
    "Physique": (
        "PH",
        ("Physics", "Quantum Science and Engineering", "Photonics"),
    ),
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
    "Microtechnique": (
        "MT",
        ("Microengineering", "Photonics", "Biomedical Technologies"),
    ),
    "Science et génie des matériaux": (
        "MX",
        (
            "Materials Science and Engineering",
            "Chemistry and Chemical Engineering",
            "Energy",
        ),
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
    "Génie civil": (
        "GC",
        ("Civil Engineering", "Sustainable Construction", "Energy"),
    ),
    "Sciences et ingénierie de l'environnement": (
        "SIE",
        (
            "Environmental Sciences and Engineering",
            "Engineering for Sustainability",
            "Energy",
        ),
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
        (
            "Digital Humanities, Media and Society",
            "Systems Engineering",
            "Financial Engineering",
        ),
    ),
}


class CandidatePreview(NamedTuple):
    folder: str
    bachelor_fr: str | None
    section: str | None
    minors: tuple[str, str, str] | None


_DOMAIN_RE = re.compile(
    r"Domaine principal d'études\s*\n([^\n]+)",
    re.IGNORECASE,
)
_EPFL_RE = re.compile(
    r"Ecole polytechnique f[ée]d[ée]rale de Lausanne EPFL",
    re.IGNORECASE,
)


def _find_synthese(candidate_dir: Path) -> Path | None:
    for sub in candidate_dir.iterdir():
        if not sub.is_dir() or "Synthese de la candidature" not in sub.name:
            continue
        md_files = list(sub.glob("*.md"))
        if md_files:
            return md_files[0]
    return None


def _detect_bachelor(synthese_text: str) -> str | None:
    """Return the EPFL bachelor name (French) or None if not detected."""
    if not _EPFL_RE.search(synthese_text):
        return None
    match = _DOMAIN_RE.search(synthese_text)
    if not match:
        return None
    return match.group(1).strip()


def preview_candidate(candidate_dir: Path) -> CandidatePreview | None:
    synthese = _find_synthese(candidate_dir)
    if synthese is None:
        return None
    text = synthese.read_text(encoding="utf-8")
    bachelor = _detect_bachelor(text)
    if bachelor is None:
        return None
    mapping = _BACHELOR_TO_MINORS.get(bachelor)
    if mapping is None:
        return CandidatePreview(candidate_dir.name, bachelor, None, None)
    section, minors = mapping
    return CandidatePreview(candidate_dir.name, bachelor, section, minors)


def main() -> None:
    if not _ANON_ROOT.is_dir():
        msg = f"Anonymized root not found: {_ANON_ROOT}"
        raise SystemExit(msg)

    previews: list[CandidatePreview] = []
    for cand_dir in sorted(_ANON_ROOT.iterdir()):
        if not cand_dir.is_dir():
            continue
        preview = preview_candidate(cand_dir)
        if preview is not None:
            previews.append(preview)

    epfl_internals = [p for p in previews if p.bachelor_fr is not None]
    unmapped = [p for p in epfl_internals if p.minors is None]

    print(f"Spring 2025-26: {len(epfl_internals)} EPFL-internal candidates detected\n")
    print(f"{'Folder':14}  {'Bachelor (FR)':40}  {'Sec':4}  Minors")
    print("-" * 120)
    for p in epfl_internals:
        if p.minors is None:
            print(f"{p.folder:14}  {p.bachelor_fr or '?':40}  {'?':4}  *** unmapped ***")
        else:
            minors_str = ", ".join(p.minors)
            print(f"{p.folder:14}  {p.bachelor_fr or '?':40}  {p.section or '?':4}  {minors_str}")

    print()
    by_bachelor: dict[str, int] = {}
    for p in epfl_internals:
        key = p.bachelor_fr or "(unknown)"
        by_bachelor[key] = by_bachelor.get(key, 0) + 1
    print("Distribution by bachelor:")
    for name, count in sorted(by_bachelor.items(), key=lambda kv: -kv[1]):
        print(f"  {count:3d}  {name}")

    if unmapped:
        print(f"\nWARNING: {len(unmapped)} candidate(s) had no mapping entry:")
        for p in unmapped:
            print(f"  {p.folder}: {p.bachelor_fr}")
    else:
        print("\nAll detected EPFL bachelors are covered by the mapping.")


if __name__ == "__main__":
    main()
