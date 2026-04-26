"""Parquet serialization for EPFL curriculum data.

Writes three Parquet files:
- programs.parquet
- courses.parquet
- study_plan_entries.parquet
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger

from agentic_admission.curriculum.models import (
    Course,
    CourseRole,
    Curriculum,
    Program,
    ProgramLevel,
    StudyPlanEntry,
)

_DEFAULT_OUTPUT_DIR = Path("data/reference/epfl_curriculum")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_PROGRAM_SCHEMA = pa.schema(
    [("slug", pa.string()), ("name", pa.string()), ("level", pa.string()), ("url", pa.string())]
)

_COURSE_SCHEMA = pa.schema(
    [
        ("code", pa.string()),
        ("name", pa.string()),
        ("credits", pa.int32()),
        ("language", pa.string()),
        ("description", pa.string()),
        ("learning_outcomes", pa.string()),
        ("prerequisites_text", pa.string()),
        ("teaching_methods", pa.string()),
        ("assessment", pa.string()),
        ("url", pa.string()),
    ]
)

_ENTRY_SCHEMA = pa.schema(
    [
        ("program_slug", pa.string()),
        ("course_code", pa.string()),
        ("semester", pa.string()),
        ("role", pa.string()),
        ("block_name", pa.string()),
    ]
)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


def save_curriculum(curriculum: Curriculum, output_dir: Path = _DEFAULT_OUTPUT_DIR) -> None:
    """Persist a Curriculum to Parquet files.

    Parameters
    ----------
    curriculum : Curriculum
        The curriculum to save.
    output_dir : Path
        Directory for the Parquet files (created if absent).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Programs
    programs_table = pa.table(
        {
            "slug": [p.slug for p in curriculum.programs],
            "name": [p.name for p in curriculum.programs],
            "level": [p.level.value for p in curriculum.programs],
            "url": [p.url for p in curriculum.programs],
        },
        schema=_PROGRAM_SCHEMA,
    )
    pq.write_table(programs_table, output_dir / "programs.parquet")
    logger.info(
        "Wrote {} programs to {}", len(curriculum.programs), output_dir / "programs.parquet"
    )

    # Courses
    courses_table = pa.table(
        {
            "code": [c.code for c in curriculum.courses],
            "name": [c.name for c in curriculum.courses],
            "credits": [c.credits for c in curriculum.courses],
            "language": [c.language for c in curriculum.courses],
            "description": [c.description for c in curriculum.courses],
            "learning_outcomes": [c.learning_outcomes for c in curriculum.courses],
            "prerequisites_text": [c.prerequisites_text for c in curriculum.courses],
            "teaching_methods": [c.teaching_methods for c in curriculum.courses],
            "assessment": [c.assessment for c in curriculum.courses],
            "url": [c.url for c in curriculum.courses],
        },
        schema=_COURSE_SCHEMA,
    )
    pq.write_table(courses_table, output_dir / "courses.parquet")
    logger.info("Wrote {} courses to {}", len(curriculum.courses), output_dir / "courses.parquet")

    # Study plan entries
    entries_table = pa.table(
        {
            "program_slug": [e.program_slug for e in curriculum.entries],
            "course_code": [e.course_code for e in curriculum.entries],
            "semester": [e.semester for e in curriculum.entries],
            "role": [e.role.value for e in curriculum.entries],
            "block_name": [e.block_name for e in curriculum.entries],
        },
        schema=_ENTRY_SCHEMA,
    )
    pq.write_table(entries_table, output_dir / "study_plan_entries.parquet")
    logger.info(
        "Wrote {} entries to {}", len(curriculum.entries), output_dir / "study_plan_entries.parquet"
    )


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def load_curriculum(input_dir: Path = _DEFAULT_OUTPUT_DIR) -> Curriculum:
    """Load a Curriculum from Parquet files.

    Parameters
    ----------
    input_dir : Path
        Directory containing the Parquet files.

    Returns
    -------
    Curriculum
        Loaded curriculum.

    Raises
    ------
    FileNotFoundError
        If any of the three Parquet files is missing.
    """
    programs_path = input_dir / "programs.parquet"
    courses_path = input_dir / "courses.parquet"
    entries_path = input_dir / "study_plan_entries.parquet"

    for path in (programs_path, courses_path, entries_path):
        if not path.exists():
            msg = f"Missing Parquet file: {path}"
            raise FileNotFoundError(msg)

    # Programs
    programs_table = pq.read_table(programs_path)
    programs = tuple(
        Program(
            slug=str(row["slug"]),
            name=str(row["name"]),
            level=ProgramLevel(str(row["level"])),
            url=str(row["url"]),
        )
        for row in programs_table.to_pylist()
    )

    # Courses
    courses_table = pq.read_table(courses_path)
    courses = tuple(
        Course(
            code=str(row["code"]),
            name=str(row["name"]),
            credits=row["credits"],
            language=str(row["language"]),
            description=str(row["description"]),
            learning_outcomes=str(row["learning_outcomes"]),
            prerequisites_text=str(row["prerequisites_text"]),
            teaching_methods=str(row["teaching_methods"]),
            assessment=str(row["assessment"]),
            url=str(row["url"]),
        )
        for row in courses_table.to_pylist()
    )

    # Entries
    entries_table = pq.read_table(entries_path)
    entries = tuple(
        StudyPlanEntry(
            program_slug=str(row["program_slug"]),
            course_code=str(row["course_code"]),
            semester=str(row["semester"]),
            role=CourseRole(str(row["role"])),
            block_name=str(row["block_name"]),
        )
        for row in entries_table.to_pylist()
    )

    return Curriculum(programs=programs, courses=courses, entries=entries)
