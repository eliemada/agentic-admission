"""EPFL disciplinary and interdisciplinary minors for 2025-26."""

from __future__ import annotations

from pydantic import BaseModel


class Minor(BaseModel, frozen=True):
    """A single EPFL minor program.

    Attributes
    ----------
    name
        Official name (bilingual FR/EN where applicable).
    minor_type
        ``"disciplinary"`` or ``"interdisciplinary"``.
    section_code
        Owning section code (e.g. ``"IN"``, ``"MTE"``).
    contact
        Contact person name(s).
    """

    name: str
    minor_type: str
    section_code: str
    contact: str


ALL_MINORS: tuple[Minor, ...] = (
    Minor(
        name="Architecture",
        minor_type="disciplinary",
        section_code="AR",
        contact="Kochnitzky Palluel L.",
    ),
    Minor(
        name="Biotechnology", minor_type="interdisciplinary", section_code="CGC", contact="Pick H."
    ),
    Minor(
        name="Chemistry and Chemical Engineering",
        minor_type="disciplinary",
        section_code="CGC",
        contact="Marendaz J.-L.",
    ),
    Minor(
        name="Computational Biology",
        minor_type="interdisciplinary",
        section_code="IN",
        contact="Salathé M.",
    ),
    Minor(
        name="Sustainable Construction",
        minor_type="interdisciplinary",
        section_code="GC",
        contact="Goulouti K.",
    ),
    Minor(
        name="Cyber Security", minor_type="disciplinary", section_code="IN", contact="Hazboun E."
    ),
    Minor(
        name="Data and Internet of Things",
        minor_type="interdisciplinary",
        section_code="EL",
        contact="Atienza D.",
    ),
    Minor(name="Data Science", minor_type="disciplinary", section_code="SC", contact="Hazboun E."),
    Minor(
        name="Integrated Design, Architecture and Sustainability (IDEAS)",
        minor_type="interdisciplinary",
        section_code="AR",
        contact="Andersen M., Rey E.",
    ),
    Minor(name="Energy", minor_type="interdisciplinary", section_code="GM", contact="Maréchal F."),
    Minor(
        name="Civil Engineering",
        minor_type="disciplinary",
        section_code="GC",
        contact="Goulouti K.",
    ),
    Minor(
        name="Electrical and Electronic Engineering",
        minor_type="disciplinary",
        section_code="EL",
        contact="Gay-Balmaz Ph.",
    ),
    Minor(
        name="Mechanical Engineering",
        minor_type="disciplinary",
        section_code="GM",
        contact="Prenleloup A.",
    ),
    Minor(
        name="Digital Humanities, Media and Society",
        minor_type="interdisciplinary",
        section_code="DH",
        contact="Collins Kathleen",
    ),
    Minor(name="Imaging", minor_type="interdisciplinary", section_code="MT", contact="Sage Daniel"),
    Minor(
        name="Systems Engineering",
        minor_type="interdisciplinary",
        section_code="MTE",
        contact="Weber Th.",
    ),
    Minor(
        name="Engineering for Sustainability",
        minor_type="interdisciplinary",
        section_code="SIE",
        contact="Gilliéron P.Y., Leterrier Y.",
    ),
    Minor(
        name="Computer Science", minor_type="disciplinary", section_code="IN", contact="Hazboun E."
    ),
    Minor(
        name="Life Sciences Engineering",
        minor_type="disciplinary",
        section_code="SV",
        contact="Bezler A.",
    ),
    Minor(
        name="Financial Engineering",
        minor_type="disciplinary",
        section_code="IF",
        contact="Malamud S.",
    ),
    Minor(
        name="Management, Technology and Entrepreneurship",
        minor_type="interdisciplinary",
        section_code="MTE",
        contact="de Rassenfosse G.",
    ),
    Minor(name="Mathematics", minor_type="disciplinary", section_code="MA", contact="Pouchon O."),
    Minor(
        name="Mathematics-Statistics",
        minor_type="interdisciplinary",
        section_code="MA",
        contact="Mhalla L.",
    ),
    Minor(
        name="Microengineering", minor_type="disciplinary", section_code="MT", contact="Gautsch S."
    ),
    Minor(
        name="Neuro-X", minor_type="disciplinary", section_code="NX", contact="Hummel F, Micera S."
    ),
    Minor(name="Photonics", minor_type="interdisciplinary", section_code="MT", contact="Martin O."),
    Minor(name="Physics", minor_type="disciplinary", section_code="PH", contact="Mari D."),
    Minor(
        name="Physics of Living Systems",
        minor_type="interdisciplinary",
        section_code="SV",
        contact="Persat A.",
    ),
    Minor(
        name="Quantum Science and Engineering",
        minor_type="disciplinary",
        section_code="SIQ",
        contact="Macris N. et Klinke H.",
    ),
    Minor(
        name="Biomedical Technologies",
        minor_type="interdisciplinary",
        section_code="MT",
        contact="Guiducci C.",
    ),
    Minor(
        name="Space Technologies",
        minor_type="interdisciplinary",
        section_code="EL",
        contact="Kneib J.-P.",
    ),
    Minor(
        name="Materials Science and Engineering",
        minor_type="disciplinary",
        section_code="MX",
        contact="Marselli B.",
    ),
    Minor(
        name="Computational Science and Engineering",
        minor_type="disciplinary",
        section_code="MA",
        contact="Pouchon O.",
    ),
    Minor(
        name="Environmental Sciences and Engineering",
        minor_type="disciplinary",
        section_code="SIE",
        contact="Gilliéron P.-Y",
    ),
    Minor(name="Statistics", minor_type="disciplinary", section_code="MA", contact="Mhalla L."),
    Minor(
        name="Communication Systems",
        minor_type="disciplinary",
        section_code="SC",
        contact="Hazboun E.",
    ),
)
"""Complete registry of 36 EPFL minors for 2025-26.

Note: 'Territories in Transformation and Climate (TTC)' is excluded as it is
no longer offered from September 2025.
"""

_SECTION_CODES: frozenset[str] = frozenset(m.section_code for m in ALL_MINORS)


def get_minors_by_section(section_code: str) -> tuple[Minor, ...]:
    """Return all minors belonging to a section.

    Parameters
    ----------
    section_code
        Two- or three-letter section code (e.g. ``"IN"``).
    """
    return tuple(m for m in ALL_MINORS if m.section_code == section_code)


def get_minor_by_name(name: str) -> Minor | None:
    """Case-insensitive lookup by minor name.

    Parameters
    ----------
    name
        Full or partial minor name.
    """
    lower = name.lower()
    for m in ALL_MINORS:
        if m.name.lower() == lower:
            return m
    for m in ALL_MINORS:
        if lower in m.name.lower():
            return m
    return None


_MTE_MASTER_MINOR_NAME: str = "Management, Technology and Entrepreneurship"
"""Name of the minor that mirrors the MTE master program itself.

A candidate admitted to the MTE master cannot take this minor — it is
the master's own curriculum re-packaged as a minor for OTHER programs'
students. The minor advisor must filter it out.
"""


def is_mte_master_minor(minor_name: str) -> bool:
    """Return True when ``minor_name`` is the MTE master's mirror minor."""
    if not minor_name:
        return False
    return minor_name.strip().lower() == _MTE_MASTER_MINOR_NAME.lower()


def selectable_minors() -> tuple[Minor, ...]:
    """Return the minors a candidate can be assigned to.

    Excludes :data:`_MTE_MASTER_MINOR_NAME` because the candidate is being
    admitted to that master — they cannot also pick it as their minor.
    """
    return tuple(m for m in ALL_MINORS if not is_mte_master_minor(m.name))


def format_minor_list() -> str:
    """Format selectable minors as a numbered markdown list for LLM context.

    The MTE master's mirror minor is excluded — see :func:`selectable_minors`.
    """
    lines: list[str] = []
    for i, m in enumerate(selectable_minors(), 1):
        lines.append(f"{i}. {m.name} ({m.minor_type}, section: {m.section_code})")
    return "\n".join(lines)
