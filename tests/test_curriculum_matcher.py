"""Tests for curriculum matcher models and helpers."""

from __future__ import annotations

from agentic_admission.curriculum.match_models import (
    CourseMatch,
    CoverageArea,
    CurriculumMatchReport,
    MinorFit,
)
from agentic_admission.curriculum.matcher import (
    _build_bachelor_context,
    _build_minor_context,
    _to_report,
    format_match_report,
)
from agentic_admission.curriculum.models import (
    Course,
    Curriculum,
    Program,
    ProgramLevel,
    StudyPlanEntry,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_curriculum() -> Curriculum:
    p_cs = Program(
        slug="computer-science",
        name="Computer Science",
        level=ProgramLevel.BACHELOR,
        url="https://x",
    )
    p_ds = Program(
        slug="data-science-minor", name="Data Science", level=ProgramLevel.MINOR, url="https://y"
    )
    c1 = Course(code="CS-250", name="Algorithms", credits=6)
    c2 = Course(code="MATH-101", name="Analysis I", credits=8)
    c3 = Course(code="CS-433", name="Machine Learning", credits=6)
    entries = (
        StudyPlanEntry(program_slug="computer-science", course_code="CS-250"),
        StudyPlanEntry(program_slug="computer-science", course_code="MATH-101"),
        StudyPlanEntry(program_slug="data-science-minor", course_code="CS-433"),
        StudyPlanEntry(program_slug="data-science-minor", course_code="CS-250"),
    )
    return Curriculum(programs=(p_cs, p_ds), courses=(c1, c2, c3), entries=entries)


def _sample_report() -> CurriculumMatchReport:
    return CurriculumMatchReport(
        candidate_id="test-001",
        course_matches=(
            CourseMatch(candidate_course="Algorithmen", epfl_codes=("CS-250",), confidence=0.9),
            CourseMatch(
                candidate_course="Lineare Algebra", epfl_codes=("MATH-111",), confidence=0.85
            ),
        ),
        coverage_by_area=(
            CoverageArea(area="CS Core", coverage=0.7, gap_courses=("CS-206",)),
            CoverageArea(area="Mathematics", coverage=0.5, gap_courses=("MATH-101",)),
        ),
        overall_coverage=0.6,
        closest_epfl_bachelor="Computer Science",
        minor_fits=(
            MinorFit(
                minor_slug="data-science-minor",
                minor_name="Data Science",
                fit_score=8,
                prerequisite_coverage=0.75,
                strengths=("algorithms", "linear algebra"),
                gaps=("probability theory",),
                reasoning="Strong CS and math base covers most DS prerequisites.",
            ),
        ),
        summary="Solid CS fundamentals from TU Munich.",
    )


# ---------------------------------------------------------------------------
# Match models
# ---------------------------------------------------------------------------


class TestMatchModels:
    def test_course_match_defaults(self):
        m = CourseMatch(candidate_course="Test")
        assert m.epfl_codes == ()
        assert m.confidence == 0.0

    def test_coverage_area_defaults(self):
        a = CoverageArea(area="Math")
        assert a.coverage == 0.0
        assert a.gap_courses == ()

    def test_minor_fit_defaults(self):
        mf = MinorFit(minor_slug="ds", minor_name="Data Science")
        assert mf.fit_score == 5

    def test_full_report(self):
        report = _sample_report()
        assert report.candidate_id == "test-001"
        assert len(report.course_matches) == 2
        assert report.overall_coverage == 0.6


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------


class TestContextBuilders:
    def test_bachelor_context_includes_courses(self):
        ctx = _build_bachelor_context(_sample_curriculum())
        assert "CS-250" in ctx
        assert "MATH-101" in ctx
        assert "Computer Science" in ctx

    def test_bachelor_context_excludes_minors(self):
        ctx = _build_bachelor_context(_sample_curriculum())
        assert "CS-433" not in ctx

    def test_minor_context_includes_minor_courses(self):
        ctx = _build_minor_context(_sample_curriculum())
        assert "Data Science" in ctx
        assert "CS-433" in ctx

    def test_minor_context_excludes_bachelors(self):
        ctx = _build_minor_context(_sample_curriculum())
        assert "MATH-101" not in ctx

    def test_bachelor_context_is_compact(self):
        """No descriptions — just code + name."""
        ctx = _build_bachelor_context(_sample_curriculum())
        # Should not contain long descriptions, just course codes and names
        assert "ECTS" not in ctx


# ---------------------------------------------------------------------------
# Response conversion
# ---------------------------------------------------------------------------


class TestToReport:
    def test_converts_flat_response(self):
        from agentic_admission.curriculum.matcher import (
            _CoverageAreaResponse,
            _MatchedCourse,
            _MatcherResponse,
            _MinorFitResponse,
        )

        response = _MatcherResponse(
            course_matches=[
                _MatchedCourse(candidate_course="Algo", epfl_codes=["CS-250"], confidence=0.9)
            ],
            coverage_areas=[_CoverageAreaResponse(area="CS", coverage=0.7, gap_courses=[])],
            overall_coverage=0.7,
            closest_epfl_bachelor="Computer Science",
            minor_fits=[
                _MinorFitResponse(
                    minor_slug="ds",
                    minor_name="Data Science",
                    fit_score=8,
                    prerequisite_coverage=0.75,
                    strengths=["algorithms"],
                    gaps=["probability"],
                    reasoning="Good fit.",
                )
            ],
            summary="Strong candidate.",
        )

        report = _to_report("cand-001", response)
        assert isinstance(report, CurriculumMatchReport)
        assert report.candidate_id == "cand-001"
        assert report.course_matches[0].epfl_codes == ("CS-250",)
        assert report.minor_fits[0].fit_score == 8


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


class TestFormatReport:
    def test_format_is_concise(self):
        text = format_match_report(_sample_report())
        # Should be short — no verbose prose
        assert len(text.split("\n")) < 15

    def test_format_includes_key_info(self):
        text = format_match_report(_sample_report())
        assert "60%" in text
        assert "Computer Science" in text
        assert "Data Science" in text
        assert "8/10" in text
