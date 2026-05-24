"""Parse structured fields from EPFL Synthese de la candidature PDFs.

Handles both French and English form variants.  Extracts personal data
(name, gender, nationality) and education data (institution, country,
GPA, study level) using PyMuPDF text extraction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path  # noqa: TC003 — used in runtime signatures

import fitz  # PyMuPDF

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SyntheseRecord:
    """Structured fields extracted from one Synthese PDF."""

    folder_name: str
    application_id: str
    last_name: str
    first_names: str
    gender: str  # "M" | "F" | ""
    nationality: str
    institution_name: str
    institution_country: str
    field_of_study: str
    study_level: str  # "Bachelor" | "Master" | ...
    gpa: str
    gpa_max: str

    @property
    def full_name(self) -> str:
        """Return 'FirstNames LastName'."""
        parts = [self.first_names, self.last_name]
        return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Label maps — French and English variants
# ---------------------------------------------------------------------------

_LABELS = {
    # Personal data
    "last_name": ["Nom", "Legal Family Name"],
    "first_names": ["Prénoms (tels", "First names (as written in"],
    "first_names_skip": ["qu'indiqués sur papiers", "d'identité)", "ID)"],
    "sex": ["Sexe", "Sex"],
    "nationality": ["Nationalité", "Nationality (country of", "Citizenship"],
    "nationality_skip": ["citizenship)"],
    "application_id": ["No candidature", "Application #"],
    # Education data
    "institution_name": ["Nom de l'institution", "Institution name"],
    "institution_country": ["Pays de l'institution", "Institution country"],
    "field_of_study": ["Domaine principal d'études", "Major field of study"],
    "field_of_study_skip": ["d'études"],
    "study_level": ["Niveau d'étude", "Academic level"],
    "gpa": ["GPA ou autre moyenne (si", "GPA or other general average (when"],
    "gpa_skip": ["disponible)", "available)"],
    "gpa_max": ["Note maximale du", "Maximal grade from the"],
    "gpa_max_skip": ["barême", "barème", "grading scale"],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _lines(text: str) -> list[str]:
    """Split text into non-empty stripped lines."""
    return [line.strip() for line in text.split("\n") if line.strip()]


def _find_value(lines: list[str], labels: list[str], skip: list[str] | None = None) -> str:
    """Find the value line following a label, skipping continuation lines.

    Parameters
    ----------
    lines
        All non-empty lines from the PDF page.
    labels
        Possible label strings (French/English).
    skip
        Substrings that indicate a continuation of the label.

    Returns
    -------
    str
        The extracted value, or ``""`` if not found.
    """
    skip = skip or []
    for i, line in enumerate(lines):
        if any(label in line for label in labels):
            j = i + 1
            while j < len(lines) and any(s in lines[j].lower() for s in skip):
                j += 1
            if j < len(lines):
                return lines[j]
    return ""


def _parse_gender(raw: str) -> str:
    """Normalize gender string to M/F/''."""
    low = raw.lower()
    if "masculin" in low or "male" in low:
        return "M"
    if "féminin" in low or "female" in low:
        return "F"
    return ""


def _find_education_page(doc: fitz.Document) -> list[str]:
    """Find the page containing the Education/Etudes section."""
    education_markers = ["Etudes", "Studies"]
    institution_markers = ["Nom de l'institution", "Institution name"]

    for page_num in range(len(doc)):
        text = doc[page_num].get_text()
        has_section = any(marker in text for marker in education_markers)
        has_institution = any(marker in text for marker in institution_markers)
        if has_section and has_institution:
            return _lines(text)

    # Fallback: find any page with institution info
    for page_num in range(len(doc)):
        text = doc[page_num].get_text()
        if any(marker in text for marker in institution_markers):
            return _lines(text)

    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_SYNTHESE_PATTERN = re.compile(r"Synthese de la candidature")


def find_synthese_pdf(dossier_path: Path) -> Path | None:
    """Locate the Synthese de la candidature PDF inside a dossier folder.

    Parameters
    ----------
    dossier_path
        Path to a candidate's dossier directory.

    Returns
    -------
    Path or None
        Path to the Synthese PDF, or None if not found.
    """
    for item in sorted(dossier_path.iterdir()):
        if _SYNTHESE_PATTERN.search(item.name) and item.is_dir():
            pdfs = [f for f in item.iterdir() if f.suffix.lower() == ".pdf"]
            if pdfs:
                return pdfs[0]
    return None


def parse_synthese(pdf_path: Path, folder_name: str = "") -> SyntheseRecord:
    """Extract structured fields from a Synthese PDF.

    Parameters
    ----------
    pdf_path
        Path to the PDF file.
    folder_name
        Name of the enclosing dossier folder (for identification).

    Returns
    -------
    SyntheseRecord
        Extracted candidate data.

    Raises
    ------
    ValueError
        If the PDF cannot be read or has no pages.
    """
    doc = fitz.open(str(pdf_path))
    if len(doc) == 0:
        msg = f"Empty PDF: {pdf_path}"
        raise ValueError(msg)

    # --- Page 1: personal data ---
    p1 = _lines(doc[0].get_text())

    last_name = _find_value(p1, _LABELS["last_name"])
    first_names = _find_value(
        p1, _LABELS["first_names"], skip=[s.lower() for s in _LABELS["first_names_skip"]]
    )
    gender = _parse_gender(_find_value(p1, _LABELS["sex"]))
    nationality = _find_value(
        p1, _LABELS["nationality"], skip=[s.lower() for s in _LABELS.get("nationality_skip", [])]
    )
    application_id = _find_value(p1, _LABELS["application_id"])

    # --- Education page (page 3 FR, page 2 EN) ---
    edu_lines = _find_education_page(doc)

    institution_name = _find_value(edu_lines, _LABELS["institution_name"])
    institution_country = _find_value(edu_lines, _LABELS["institution_country"])
    field_of_study = _find_value(
        edu_lines,
        _LABELS["field_of_study"],
        skip=[s.lower() for s in _LABELS.get("field_of_study_skip", [])],
    )
    study_level = _find_value(edu_lines, _LABELS["study_level"])
    gpa = _find_value(edu_lines, _LABELS["gpa"], skip=[s.lower() for s in _LABELS["gpa_skip"]])
    gpa_max = _find_value(
        edu_lines, _LABELS["gpa_max"], skip=[s.lower() for s in _LABELS["gpa_max_skip"]]
    )

    doc.close()

    return SyntheseRecord(
        folder_name=folder_name or pdf_path.parent.parent.name,
        application_id=application_id,
        last_name=last_name,
        first_names=first_names,
        gender=gender,
        nationality=nationality,
        institution_name=institution_name,
        institution_country=institution_country,
        field_of_study=field_of_study,
        study_level=study_level,
        gpa=gpa,
        gpa_max=gpa_max,
    )
