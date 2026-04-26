"""Tests for curriculum Parquet storage (round-trip)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_admission.curriculum.models import (
    Course,
    CourseRole,
    Curriculum,
    Program,
    ProgramLevel,
    StudyPlanEntry,
)
from agentic_admission.curriculum.storage import load_curriculum, save_curriculum


def _sample_curriculum() -> Curriculum:
    p1 = Program(slug="cs", name="CS", level=ProgramLevel.BACHELOR, url="https://x/cs")
    p2 = Program(slug="mte", name="MTE", level=ProgramLevel.MASTER, url="https://x/mte")
    c1 = Course(
        code="CS-250",
        name="Algorithms",
        credits=6,
        language="English",
        description="Algorithm design",
        learning_outcomes="Analyze complexity",
        prerequisites_text="MATH-101",
        teaching_methods="Lecture",
        assessment="Written exam",
        url="https://edu.epfl.ch/coursebook/en/algorithms-CS-250",
    )
    c2 = Course(code="MATH-101", name="Analysis I", credits=8)
    entries = (
        StudyPlanEntry(
            program_slug="cs",
            course_code="CS-250",
            semester="Fall",
            role=CourseRole.MANDATORY,
            block_name="Block A",
        ),
        StudyPlanEntry(program_slug="cs", course_code="MATH-101"),
        StudyPlanEntry(program_slug="mte", course_code="CS-250"),
    )
    return Curriculum(programs=(p1, p2), courses=(c1, c2), entries=entries)


class TestRoundTrip:
    def test_save_and_load(self, tmp_path: Path):
        original = _sample_curriculum()
        save_curriculum(original, tmp_path)

        # Verify files exist
        assert (tmp_path / "programs.parquet").exists()
        assert (tmp_path / "courses.parquet").exists()
        assert (tmp_path / "study_plan_entries.parquet").exists()

        loaded = load_curriculum(tmp_path)

        assert len(loaded.programs) == len(original.programs)
        assert len(loaded.courses) == len(original.courses)
        assert len(loaded.entries) == len(original.entries)

    def test_program_data_preserved(self, tmp_path: Path):
        original = _sample_curriculum()
        save_curriculum(original, tmp_path)
        loaded = load_curriculum(tmp_path)

        loaded_slugs = {p.slug for p in loaded.programs}
        original_slugs = {p.slug for p in original.programs}
        assert loaded_slugs == original_slugs

    def test_course_data_preserved(self, tmp_path: Path):
        original = _sample_curriculum()
        save_curriculum(original, tmp_path)
        loaded = load_curriculum(tmp_path)

        loaded_cs = next(c for c in loaded.courses if c.code == "CS-250")
        original_cs = next(c for c in original.courses if c.code == "CS-250")
        assert loaded_cs.name == original_cs.name
        assert loaded_cs.credits == original_cs.credits
        assert loaded_cs.language == original_cs.language
        assert loaded_cs.description == original_cs.description

    def test_entry_roles_preserved(self, tmp_path: Path):
        original = _sample_curriculum()
        save_curriculum(original, tmp_path)
        loaded = load_curriculum(tmp_path)

        mandatory_entries = [e for e in loaded.entries if e.role == CourseRole.MANDATORY]
        assert len(mandatory_entries) == 1
        assert mandatory_entries[0].course_code == "CS-250"

    def test_query_helpers_work_after_load(self, tmp_path: Path):
        original = _sample_curriculum()
        save_curriculum(original, tmp_path)
        loaded = load_curriculum(tmp_path)

        cs_courses = loaded.courses_for_program("cs")
        assert len(cs_courses) == 2

        cs250_programs = loaded.programs_for_course("CS-250")
        assert len(cs250_programs) == 2

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="Missing Parquet file"):
            load_curriculum(tmp_path)

    def test_creates_directory(self, tmp_path: Path):
        nested = tmp_path / "a" / "b" / "c"
        save_curriculum(_sample_curriculum(), nested)
        assert (nested / "programs.parquet").exists()
