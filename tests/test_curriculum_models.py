"""Tests for curriculum domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_admission.curriculum.models import (
    Course,
    CourseRole,
    Curriculum,
    Program,
    ProgramLevel,
    StudyPlanEntry,
)

# ---------------------------------------------------------------------------
# Program
# ---------------------------------------------------------------------------


class TestProgram:
    def test_create_bachelor(self):
        p = Program(
            slug="computer-science",
            name="Computer Science",
            level=ProgramLevel.BACHELOR,
            url="https://edu.epfl.ch/studyplan/en/bachelor/computer-science",
        )
        assert p.slug == "computer-science"
        assert p.level == ProgramLevel.BACHELOR

    def test_frozen(self):
        p = Program(slug="cs", name="CS", level=ProgramLevel.MASTER, url="https://x")
        with pytest.raises(ValidationError, match="frozen"):
            p.slug = "new"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Course
# ---------------------------------------------------------------------------


class TestCourse:
    def test_create_minimal(self):
        c = Course(code="CS-250", name="Algorithms")
        assert c.code == "CS-250"
        assert c.credits is None
        assert c.description == ""

    def test_create_full(self):
        c = Course(
            code="MATH-101",
            name="Analysis I",
            credits=6,
            language="French",
            description="Fundamental analysis",
            learning_outcomes="Prove convergence",
            prerequisites_text="",
            teaching_methods="Lecture",
            assessment="Written exam",
            url="https://edu.epfl.ch/coursebook/en/analysis-i-MATH-101",
        )
        assert c.credits == 6
        assert c.language == "French"

    def test_frozen(self):
        c = Course(code="X-001", name="Test")
        with pytest.raises(ValidationError, match="frozen"):
            c.code = "Y-002"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# StudyPlanEntry
# ---------------------------------------------------------------------------


class TestStudyPlanEntry:
    def test_defaults(self):
        e = StudyPlanEntry(program_slug="cs", course_code="CS-250")
        assert e.role == CourseRole.OPTIONAL
        assert e.block_name == ""

    def test_mandatory(self):
        e = StudyPlanEntry(
            program_slug="cs", course_code="CS-250", role=CourseRole.MANDATORY, block_name="Block A"
        )
        assert e.role == CourseRole.MANDATORY


# ---------------------------------------------------------------------------
# Curriculum
# ---------------------------------------------------------------------------


def _make_curriculum() -> Curriculum:
    p1 = Program(slug="cs", name="CS", level=ProgramLevel.BACHELOR, url="https://x/cs")
    p2 = Program(slug="math", name="Math", level=ProgramLevel.BACHELOR, url="https://x/math")
    c1 = Course(code="CS-250", name="Algorithms")
    c2 = Course(code="MATH-101", name="Analysis I")
    c3 = Course(code="MATH-203", name="Analysis III")
    entries = (
        StudyPlanEntry(program_slug="cs", course_code="CS-250"),
        StudyPlanEntry(program_slug="cs", course_code="MATH-101"),
        StudyPlanEntry(program_slug="math", course_code="MATH-101"),
        StudyPlanEntry(program_slug="math", course_code="MATH-203"),
    )
    return Curriculum(programs=(p1, p2), courses=(c1, c2, c3), entries=entries)


class TestCurriculum:
    def test_courses_for_program(self):
        cur = _make_curriculum()
        cs_courses = cur.courses_for_program("cs")
        codes = {c.code for c in cs_courses}
        assert codes == {"CS-250", "MATH-101"}

    def test_programs_for_course(self):
        cur = _make_curriculum()
        programs = cur.programs_for_course("MATH-101")
        slugs = {p.slug for p in programs}
        assert slugs == {"cs", "math"}

    def test_duplicate_course_codes_rejected(self):
        c1 = Course(code="CS-250", name="Algorithms")
        c2 = Course(code="CS-250", name="Algorithms Duplicate")
        with pytest.raises(ValueError, match="Duplicate course codes"):
            Curriculum(courses=(c1, c2))

    def test_frozen(self):
        cur = _make_curriculum()
        with pytest.raises(ValidationError, match="frozen"):
            cur.programs = ()  # type: ignore[misc]
