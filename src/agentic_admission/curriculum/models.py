"""Domain models for EPFL curriculum data.

Relational model: Program ←(StudyPlanEntry)→ Course.
A single course can appear in multiple programs with different roles.
"""

from __future__ import annotations

import enum
from typing import Self

from pydantic import BaseModel, model_validator


class ProgramLevel(enum.StrEnum):
    """Academic level of a program."""

    BACHELOR = "bachelor"
    MASTER = "master"
    MINOR = "minor"


class CourseRole(enum.StrEnum):
    """Role of a course within a study plan block."""

    MANDATORY = "mandatory"
    OPTIONAL = "optional"


class Program(BaseModel, frozen=True):
    """An EPFL degree program (bachelor, master, or minor).

    Attributes
    ----------
    slug : str
        URL slug (e.g. ``computer-science``).
    name : str
        Human-readable name.
    level : ProgramLevel
        Bachelor, master, or minor.
    url : str
        Full URL to the study plan page.
    """

    slug: str
    name: str
    level: ProgramLevel
    url: str


class Course(BaseModel, frozen=True):
    """A unique course at EPFL.

    Attributes
    ----------
    code : str
        Course code (e.g. ``CS-250``).
    name : str
        Course title.
    credits : int | None
        ECTS credits.
    language : str
        Language of instruction (e.g. ``English``, ``French``).
    description : str
        Summary / résumé.
    learning_outcomes : str
        Acquis de formation text.
    prerequisites_text : str
        Raw prerequisite text (often empty).
    teaching_methods : str
        Méthode d'enseignement.
    assessment : str
        Méthode d'évaluation.
    url : str
        Full URL to the coursebook page.
    """

    code: str
    name: str
    credits: int | None = None
    language: str = ""
    description: str = ""
    learning_outcomes: str = ""
    prerequisites_text: str = ""
    teaching_methods: str = ""
    assessment: str = ""
    url: str = ""


class StudyPlanEntry(BaseModel, frozen=True):
    """Link between a program and a course.

    Attributes
    ----------
    program_slug : str
        Program slug (foreign key to :class:`Program`).
    course_code : str
        Course code (foreign key to :class:`Course`).
    semester : str
        Semester label (e.g. ``Fall``, ``Spring``).
    role : CourseRole
        Whether the course is mandatory or optional in this block.
    block_name : str
        Study plan block (e.g. ``Block A``, ``Options in Data Science``).
    """

    program_slug: str
    course_code: str
    semester: str = ""
    role: CourseRole = CourseRole.OPTIONAL
    block_name: str = ""


class Curriculum(BaseModel, frozen=True):
    """Top-level container for the full EPFL curriculum.

    Holds the three entity collections and provides query helpers.

    Attributes
    ----------
    programs : tuple[Program, ...]
        All scraped programs.
    courses : tuple[Course, ...]
        All unique courses (deduplicated by code).
    entries : tuple[StudyPlanEntry, ...]
        Study plan links (many-to-many).
    """

    programs: tuple[Program, ...] = ()
    courses: tuple[Course, ...] = ()
    entries: tuple[StudyPlanEntry, ...] = ()

    @model_validator(mode="after")
    def _validate_no_duplicate_courses(self) -> Self:
        codes = [c.code for c in self.courses]
        dupes = {c for c in codes if codes.count(c) > 1}
        if dupes:
            msg = f"Duplicate course codes: {dupes}"
            raise ValueError(msg)
        return self

    def courses_for_program(self, program_slug: str) -> tuple[Course, ...]:
        """Return all courses linked to a program."""
        codes = {e.course_code for e in self.entries if e.program_slug == program_slug}
        return tuple(c for c in self.courses if c.code in codes)

    def programs_for_course(self, course_code: str) -> tuple[Program, ...]:
        """Return all programs that include a course."""
        slugs = {e.program_slug for e in self.entries if e.course_code == course_code}
        return tuple(p for p in self.programs if p.slug in slugs)
