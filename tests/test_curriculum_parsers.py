"""Tests for curriculum HTML parsers."""

from __future__ import annotations

from agentic_admission.curriculum.models import CourseRole, Program, ProgramLevel
from agentic_admission.curriculum.parsers import (
    parse_course_page,
    parse_program_index,
    parse_study_plan,
)

# ---------------------------------------------------------------------------
# Fixtures: minimal HTML fragments that mirror edu.epfl.ch structure
# ---------------------------------------------------------------------------

PROGRAM_INDEX_HTML = """
<html><body><main>
<ul>
  <li><a href="/studyplan/en/bachelor/computer-science/" title="Computer Science">CS</a></li>
  <li><a href="/studyplan/en/bachelor/mathematics/" title="Mathematics">Math</a></li>
  <li><a href="/unrelated/link/">Ignore me</a></li>
</ul>
</main></body></html>
"""

STUDY_PLAN_HTML = """
<html><body><main>
<h2>Block A</h2>
<div class="line">
  <div class="cours-name">
    <a href="/coursebook/en/algorithms-CS-250">Algorithms</a>
  </div>
  <span>CS-250 / Section IN</span>
</div>
<h3>Group options</h3>
<div class="line">
  <div class="cours-name">
    <a href="/coursebook/en/machine-learning-CS-433">Machine Learning</a>
  </div>
  <span>CS-433 / Section IN</span>
</div>
<div class="cours-name">
  <!-- No link — should be skipped -->
  <span>Placeholder</span>
</div>
</main></body></html>
"""

COURSE_PAGE_HTML = """
<html><body><main>
<h1>Algorithms</h1>
<div class="course-summary">
  <p>CS-250 / coefficient 6</p>
  <p><a href="https://people.epfl.ch/123">Prof. X</a></p>
  <p>Langue: English</p>
</div>
<h2>Résumé</h2>
<p>Study of fundamental algorithms.</p>
<h2>Acquis de formation</h2>
<ul>
  <li>Design efficient algorithms</li>
  <li>Analyze complexity</li>
</ul>
<h2>Méthode d'enseignement</h2>
<p>Lecture and exercises</p>
<h2>Méthode d'évaluation</h2>
<p>Written exam</p>
<div class="study-plans">
  <button class="collapse-title-desktop">Computer Science 2024-2025 Fall</button>
</div>
</main></body></html>
"""


# ---------------------------------------------------------------------------
# Program index
# ---------------------------------------------------------------------------


class TestParseProgramIndex:
    def test_discovers_programs(self):
        programs = parse_program_index(PROGRAM_INDEX_HTML, ProgramLevel.BACHELOR)
        assert len(programs) == 2
        slugs = {p.slug for p in programs}
        assert slugs == {"computer-science", "mathematics"}

    def test_sets_level(self):
        programs = parse_program_index(PROGRAM_INDEX_HTML, ProgramLevel.BACHELOR)
        assert all(p.level == ProgramLevel.BACHELOR for p in programs)

    def test_builds_full_urls(self):
        programs = parse_program_index(PROGRAM_INDEX_HTML, ProgramLevel.BACHELOR)
        for p in programs:
            assert p.url.startswith("https://edu.epfl.ch")

    def test_empty_page(self):
        programs = parse_program_index("<html><body></body></html>", ProgramLevel.MASTER)
        assert programs == ()

    def test_ignores_non_study_plan_links(self):
        programs = parse_program_index(PROGRAM_INDEX_HTML, ProgramLevel.BACHELOR)
        # The /unrelated/link/ should not be included
        assert len(programs) == 2


# ---------------------------------------------------------------------------
# Study plan
# ---------------------------------------------------------------------------


class TestParseStudyPlan:
    @staticmethod
    def _program() -> Program:
        return Program(
            slug="computer-science",
            name="Computer Science",
            level=ProgramLevel.BACHELOR,
            url="https://edu.epfl.ch/studyplan/en/bachelor/computer-science",
        )

    def test_extracts_entries(self):
        entries = parse_study_plan(STUDY_PLAN_HTML, self._program())
        assert len(entries) == 2

    def test_block_a_is_mandatory(self):
        entries = parse_study_plan(STUDY_PLAN_HTML, self._program())
        block_a_entries = [e for e in entries if "Block" in e.block_name]
        assert all(e.role == CourseRole.MANDATORY for e in block_a_entries)

    def test_group_options_is_optional(self):
        entries = parse_study_plan(STUDY_PLAN_HTML, self._program())
        option_entries = [e for e in entries if "option" in e.block_name.lower()]
        assert all(e.role == CourseRole.OPTIONAL for e in option_entries)

    def test_extracts_course_code(self):
        entries = parse_study_plan(STUDY_PLAN_HTML, self._program())
        codes = {e.course_code for e in entries}
        assert "CS-250" in codes or any("CS-250" in c for c in codes)

    def test_skips_entries_without_links(self):
        entries = parse_study_plan(STUDY_PLAN_HTML, self._program())
        # The placeholder div without an <a> should be skipped
        assert len(entries) == 2


# ---------------------------------------------------------------------------
# Course page
# ---------------------------------------------------------------------------


class TestParseCoursePageFn:
    def test_extracts_name(self):
        course = parse_course_page(COURSE_PAGE_HTML, "https://test")
        assert course is not None
        assert course.name == "Algorithms"

    def test_extracts_code(self):
        course = parse_course_page(COURSE_PAGE_HTML, "https://test")
        assert course is not None
        assert course.code == "CS-250"

    def test_extracts_credits(self):
        course = parse_course_page(COURSE_PAGE_HTML, "https://test")
        assert course is not None
        assert course.credits == 6

    def test_extracts_language(self):
        course = parse_course_page(COURSE_PAGE_HTML, "https://test")
        assert course is not None
        assert course.language == "English"

    def test_extracts_description(self):
        course = parse_course_page(COURSE_PAGE_HTML, "https://test")
        assert course is not None
        assert "fundamental algorithms" in course.description.lower()

    def test_extracts_learning_outcomes(self):
        course = parse_course_page(COURSE_PAGE_HTML, "https://test")
        assert course is not None
        assert "efficient algorithms" in course.learning_outcomes.lower()

    def test_extracts_teaching_methods(self):
        course = parse_course_page(COURSE_PAGE_HTML, "https://test")
        assert course is not None
        assert "Lecture" in course.teaching_methods

    def test_extracts_assessment(self):
        course = parse_course_page(COURSE_PAGE_HTML, "https://test")
        assert course is not None
        assert "Written exam" in course.assessment

    def test_stores_url(self):
        course = parse_course_page(COURSE_PAGE_HTML, "https://test/page")
        assert course is not None
        assert course.url == "https://test/page"

    def test_returns_none_for_missing_code(self):
        html = "<html><body><main><h1>Bad page</h1></main></body></html>"
        assert parse_course_page(html, "https://test") is None

    def test_returns_none_for_no_main(self):
        html = "<html><body><p>No main</p></body></html>"
        assert parse_course_page(html, "https://test") is None
