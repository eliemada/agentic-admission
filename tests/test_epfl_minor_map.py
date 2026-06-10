"""Tests for the deterministic EPFL minor mapping."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from agentic_admission.agents.epfl_minor_map import (
    EPFL_BACHELOR_TO_MINORS,
    build_deterministic_recommendation,
    detect_epfl_bachelor,
)
from agentic_admission.models.minor import ALL_MINORS, get_minor_by_name, is_non_recommendable_minor


def _make_async_none() -> Callable[..., Coroutine[Any, Any, None]]:
    """Return an async function that ignores kwargs and returns None.

    Used to short-circuit ``_try_curriculum_match`` in tests so they
    don't need a curriculum on disk.
    """

    async def _none(**_kwargs: object) -> None:
        return None

    return _none


@pytest.mark.unit
class TestMappingTable:
    """Structural invariants of the EPFL_BACHELOR_TO_MINORS table."""

    def test_table_has_at_least_one_entry_per_section(self) -> None:
        # If the table is empty the deterministic short-circuit can never
        # fire — that's a regression worth catching.
        assert len(EPFL_BACHELOR_TO_MINORS) >= 16

    def test_every_mapped_minor_exists_in_registry(self) -> None:
        known = {m.name for m in ALL_MINORS}
        for bachelor, (_section, minors) in EPFL_BACHELOR_TO_MINORS.items():
            for name in minors:
                assert name in known, f"Mapping for {bachelor!r} references unknown minor {name!r}"

    def test_no_recommendation_includes_mte_master_minor(self) -> None:
        # MTE candidates already get the minor advisor's exclusion check;
        # the deterministic table should never propose the MTE master's
        # mirror minor either.
        for bachelor, (_section, minors) in EPFL_BACHELOR_TO_MINORS.items():
            for name in minors:
                assert "Management, Technology and Entrepreneurship" not in name, (
                    f"Mapping for {bachelor!r} should not include MTE master minor"
                )

    def test_no_recommendation_includes_non_recommendable_minor(self) -> None:
        # The deterministic table bypasses the advisor's safety-net filter,
        # so it must never propose a non-recommendable minor (the MTE master
        # mirror minor or Financial Engineering) on its own.
        for bachelor, (_section, minors) in EPFL_BACHELOR_TO_MINORS.items():
            for name in minors:
                assert not is_non_recommendable_minor(name), (
                    f"Mapping for {bachelor!r} proposes non-recommendable minor {name!r}"
                )

    def test_table_is_immutable(self) -> None:
        from types import MappingProxyType

        # MappingProxyType is the only stdlib read-only mapping that
        # raises TypeError on __setitem__. If someone swaps it for a
        # plain dict the immutability guarantee disappears silently.
        assert isinstance(EPFL_BACHELOR_TO_MINORS, MappingProxyType)


@pytest.mark.unit
class TestDetectEpflBachelor:
    """Detection from synthese-style dossier text."""

    def test_returns_none_when_no_text(self) -> None:
        assert detect_epfl_bachelor("") is None

    def test_returns_none_without_epfl_marker(self) -> None:
        text = (
            "Nom de l'institution\nUniversité de Genève\nDomaine principal d'études\nInformatique\n"
        )
        assert detect_epfl_bachelor(text) is None

    def test_returns_none_without_domain_field(self) -> None:
        text = "Ecole polytechnique fédérale de Lausanne EPFL\n(no domain listed)"
        assert detect_epfl_bachelor(text) is None

    def test_detects_chemistry_bachelor(self) -> None:
        text = (
            "Education\n"
            "Ecole polytechnique fédérale de Lausanne EPFL\n"
            "Lausanne\n"
            "Domaine principal d'études\n"
            "Chimie et génie chimique\n"
            "Niveau d'étude\nBachelor\n"
        )
        assert detect_epfl_bachelor(text) == "Chimie et génie chimique"

    def test_detects_mechanical_bachelor(self) -> None:
        text = (
            "Ecole polytechnique fédérale de Lausanne EPFL\n"
            "Domaine principal d'études\n"
            "Génie mécanique\n"
        )
        assert detect_epfl_bachelor(text) == "Génie mécanique"

    def test_handles_unaccented_form_field(self) -> None:
        # OCR sometimes drops the é in "études".
        text = (
            "Ecole polytechnique federale de Lausanne EPFL\n"
            "Domaine principal d'etudes\n"
            "Informatique\n"
        )
        assert detect_epfl_bachelor(text) == "Informatique"

    def test_returns_none_for_unmapped_bachelor(self) -> None:
        # Real but never-yet-seen bachelor name (typo'd domain).
        text = (
            "Ecole polytechnique fédérale de Lausanne EPFL\n"
            "Domaine principal d'études\n"
            "Astronautique théorique\n"
        )
        assert detect_epfl_bachelor(text) is None

    def test_relaxed_case_match(self) -> None:
        text = (
            "Ecole polytechnique fédérale de Lausanne EPFL\n"
            "Domaine principal d'études\n"
            "informatique\n"
        )
        assert detect_epfl_bachelor(text) == "Informatique"


@pytest.mark.unit
class TestBuildDeterministicRecommendation:
    """Shape of the produced MinorRecommendation."""

    def test_returns_three_minors(self) -> None:
        rec = build_deterministic_recommendation("Informatique")
        assert len(rec.recommended) == 3

    def test_primary_is_top_minor(self) -> None:
        rec = build_deterministic_recommendation("Informatique")
        assert rec.primary_minor == rec.recommended[0].minor_name

    def test_scores_are_descending(self) -> None:
        rec = build_deterministic_recommendation("Génie mécanique")
        scores = [s.fit_score for s in rec.recommended]
        assert scores == sorted(scores, reverse=True)
        assert scores == [10, 9, 8]

    def test_section_codes_match_registry(self) -> None:
        rec = build_deterministic_recommendation("Informatique")
        for s in rec.recommended:
            registry_minor = get_minor_by_name(s.minor_name)
            assert registry_minor is not None
            assert s.section_code == registry_minor.section_code

    def test_reasoning_mentions_bachelor(self) -> None:
        rec = build_deterministic_recommendation("Microtechnique")
        for s in rec.recommended:
            assert "Microtechnique" in s.reasoning

    def test_unmapped_bachelor_raises(self) -> None:
        with pytest.raises(KeyError):
            build_deterministic_recommendation("Not A Real Bachelor")

    def test_cs_bachelor_recommends_cs_minor_first(self) -> None:
        # The user's worked example: CS bachelor → CS / Cyber Security / Data Science.
        rec = build_deterministic_recommendation("Informatique")
        names = [s.minor_name for s in rec.recommended]
        assert names == ["Computer Science", "Cyber Security", "Data Science"]


@pytest.mark.unit
class TestRecommendMinorShortCircuit:
    """recommend_minor should skip the LLM when EPFL bachelor is detected."""

    @pytest.mark.asyncio
    async def test_short_circuits_for_detected_epfl_bachelor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agentic_admission.agents import minor_advisor

        async def _fail(*_args: object, **_kwargs: object) -> object:
            msg = "LLM should not be called for detected EPFL bachelor"
            raise AssertionError(msg)

        monkeypatch.setattr(minor_advisor, "complete", _fail)

        full_dossier_text = (
            "Ecole polytechnique fédérale de Lausanne EPFL\n"
            "Domaine principal d'études\n"
            "Informatique\n"
        )
        result = await minor_advisor.recommend_minor(
            transcript_text="(unused)",
            cv_text="(unused)",
            model="ignored",
            base_url="ignored",
            is_epfl_internal=True,
            full_dossier_text=full_dossier_text,
        )

        names = [s.minor_name for s in result.recommended]
        assert names == ["Computer Science", "Cyber Security", "Data Science"]

    @pytest.mark.asyncio
    async def test_falls_back_to_llm_when_bachelor_not_detected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agentic_admission.agents import minor_advisor
        from agentic_admission.agents.minor_advisor import MinorAdvisorResponse

        called: list[bool] = []

        async def _fake_complete(*_args: object, **_kwargs: object) -> MinorAdvisorResponse:
            called.append(True)
            return MinorAdvisorResponse(
                minor_1_name="Computer Science",
                minor_1_section="IN",
                minor_1_score=8,
                minor_1_reason="LLM-driven fallback",
                minor_2_name="Data Science",
                minor_2_section="SC",
                minor_2_score=7,
                minor_2_reason="LLM-driven fallback",
                minor_3_name="Cyber Security",
                minor_3_section="IN",
                minor_3_score=6,
                minor_3_reason="LLM-driven fallback",
            )

        monkeypatch.setattr(minor_advisor, "complete", _fake_complete)
        # Block the curriculum-match attempt so we don't hit the network.
        monkeypatch.setattr(minor_advisor, "_try_curriculum_match", _make_async_none())

        result = await minor_advisor.recommend_minor(
            transcript_text="(transcript)",
            cv_text="(cv)",
            model="ignored",
            base_url="ignored",
            is_epfl_internal=True,
            full_dossier_text="No EPFL marker in this dossier text.",
        )

        assert called, "LLM should be invoked when bachelor cannot be detected"
        assert result.recommended[0].fit_score == 8

    @pytest.mark.asyncio
    async def test_external_candidate_skips_deterministic_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agentic_admission.agents import minor_advisor
        from agentic_admission.agents.minor_advisor import MinorAdvisorResponse

        called: list[bool] = []

        async def _fake_complete(*_args: object, **_kwargs: object) -> MinorAdvisorResponse:
            called.append(True)
            return MinorAdvisorResponse(
                minor_1_name="Computer Science",
                minor_1_section="IN",
                minor_1_score=7,
                minor_1_reason="ext",
                minor_2_name="Systems Engineering",
                minor_2_section="MTE",
                minor_2_score=6,
                minor_2_reason="ext",
                minor_3_name="Statistics",
                minor_3_section="MA",
                minor_3_score=5,
                minor_3_reason="ext",
            )

        monkeypatch.setattr(minor_advisor, "complete", _fake_complete)
        monkeypatch.setattr(minor_advisor, "_try_curriculum_match", _make_async_none())

        # Even though full_dossier_text contains EPFL markers, the
        # candidate is flagged external — the deterministic path must
        # not fire.
        full_dossier_text = (
            "Ecole polytechnique fédérale de Lausanne EPFL\n"
            "Domaine principal d'études\n"
            "Informatique\n"
        )
        result = await minor_advisor.recommend_minor(
            transcript_text="(transcript)",
            cv_text="(cv)",
            model="ignored",
            base_url="ignored",
            is_epfl_internal=False,
            full_dossier_text=full_dossier_text,
        )

        assert called, "LLM should run for external candidates regardless of dossier text"
        assert result.primary_minor == "Computer Science"

    @pytest.mark.asyncio
    async def test_financial_engineering_dropped_from_llm_output(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Financial Engineering is non-recommendable (same committee as the
        # MTE master). If the LLM proposes it anyway it must be filtered out
        # and never surface as the primary recommendation.
        from agentic_admission.agents import minor_advisor
        from agentic_admission.agents.minor_advisor import MinorAdvisorResponse

        async def _fake_complete(*_args: object, **_kwargs: object) -> MinorAdvisorResponse:
            return MinorAdvisorResponse(
                minor_1_name="Financial Engineering",
                minor_1_section="IF",
                minor_1_score=9,
                minor_1_reason="llm ignored exclusion",
                minor_2_name="Systems Engineering",
                minor_2_section="MTE",
                minor_2_score=7,
                minor_2_reason="ext",
                minor_3_name="Statistics",
                minor_3_section="MA",
                minor_3_score=5,
                minor_3_reason="ext",
            )

        monkeypatch.setattr(minor_advisor, "complete", _fake_complete)
        monkeypatch.setattr(minor_advisor, "_try_curriculum_match", _make_async_none())

        result = await minor_advisor.recommend_minor(
            transcript_text="(transcript)",
            cv_text="(cv)",
            model="ignored",
            base_url="ignored",
            is_epfl_internal=False,
            full_dossier_text="No EPFL marker here.",
        )

        names = [s.minor_name for s in result.recommended]
        assert "Financial Engineering" not in names
        assert result.primary_minor == "Systems Engineering"
