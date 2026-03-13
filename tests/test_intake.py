"""Tests for intake scanning and candidate matching."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_admission.intake.matcher import (
    match_dossiers_to_candidates,
    name_to_folder_candidates,
    name_to_folder_key,
    semester_from_record,
)
from agentic_admission.intake.scanner import scan_dossier_tree
from agentic_admission.models.candidate import CandidateRecord
from agentic_admission.models.dossier import Dossier

# ---------------------------------------------------------------------------
# Semester mapping
# ---------------------------------------------------------------------------


class TestSemesterFromRecord:
    """Map (academic_year, admission_round) → semester directory name."""

    def test_round1_fall(self) -> None:
        assert semester_from_record("2024-25", "round1") == "2024-25-fall"

    def test_round2_spring(self) -> None:
        assert semester_from_record("2024-25", "round2") == "2024-25-spring"

    def test_standalone_year_round1(self) -> None:
        # "2020" round1 came from P2020 (Printemps) — no dossier folder exists
        result = semester_from_record("2020", "round1")
        assert result is None

    def test_standalone_year_round2(self) -> None:
        result = semester_from_record("2020", "round2")
        assert result is None


# ---------------------------------------------------------------------------
# Name → folder key
# ---------------------------------------------------------------------------


class TestNameToFolderKey:
    """Convert CandidateRecord.name to the dossier folder naming convention."""

    def test_simple_name(self) -> None:
        assert name_to_folder_key("Akiki Christopher") == "akiki"

    def test_compound_last_name_candidates(self) -> None:
        # "Aponte Gomez Camilo Andres" → candidates include "aponte_gomez"
        candidates = name_to_folder_candidates("Aponte Gomez Camilo Andres")
        assert "aponte_gomez" in candidates
        assert "aponte" in candidates

    def test_long_name_candidates(self) -> None:
        candidates = name_to_folder_candidates("Abdelmoteleb Sara Samir Hassan")
        assert "abdelmoteleb" in candidates

    def test_empty_name(self) -> None:
        assert name_to_folder_key("") == ""

    def test_accented_characters(self) -> None:
        candidates = name_to_folder_candidates("Müller Hans")
        assert "muller" in candidates

    def test_von_der_compound(self) -> None:
        candidates = name_to_folder_candidates("Von Der Höh Lorenz Christoph Wilhelm")
        assert "von_der_hoh" in candidates


# ---------------------------------------------------------------------------
# Scanner (filesystem)
# ---------------------------------------------------------------------------


class TestScanDossierTree:
    """Scan a dossier directory tree into Dossier objects."""

    def test_scan_test_sample(self) -> None:
        root = Path("data/test_sample/dossiers")
        if not root.exists():
            pytest.skip("test_sample data not available")
        dossiers = scan_dossier_tree(root)
        assert len(dossiers) == 2  # abdelmoteleb and akiki
        names = {d.folder_name for d in dossiers}
        assert "abdelmoteleb" in names
        assert "akiki" in names

    def test_documents_populated(self) -> None:
        root = Path("data/test_sample/dossiers")
        if not root.exists():
            pytest.skip("test_sample data not available")
        dossiers = scan_dossier_tree(root)
        for d in dossiers:
            assert len(d.documents) > 0

    def test_empty_directory(self, tmp_path: Path) -> None:
        dossiers = scan_dossier_tree(tmp_path)
        assert dossiers == []


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------


class TestMatchDossiersToCandidates:
    """Match Dossier objects to CandidateRecord entries."""

    @staticmethod
    def _make_candidate(name: str, year: str, rnd: str) -> CandidateRecord:
        return CandidateRecord(
            source_file="test.xlsx", academic_year=year, admission_round=rnd, name=name
        )

    @staticmethod
    def _make_dossier(folder: str, semester: str) -> Dossier:
        return Dossier(folder_name=folder, semester=semester, documents=[])

    def test_exact_match(self) -> None:
        candidates = [self._make_candidate("Akiki Christopher", "2024-25", "round1")]
        dossiers = [self._make_dossier("akiki", "2024-25-fall")]
        matched, unmatched_d, unmatched_c = match_dossiers_to_candidates(dossiers, candidates)
        assert len(matched) == 1
        assert matched[0].candidate is not None
        assert matched[0].candidate.name == "Akiki Christopher"
        assert unmatched_d == []
        assert unmatched_c == []

    def test_compound_name_match(self) -> None:
        candidates = [self._make_candidate("Aponte Gomez Camilo Andres", "2024-25", "round1")]
        dossiers = [self._make_dossier("aponte_gomez", "2024-25-fall")]
        matched, _unmatched_d, _unmatched_c = match_dossiers_to_candidates(dossiers, candidates)
        assert len(matched) == 1

    def test_no_match(self) -> None:
        candidates = [self._make_candidate("Nobody Exists", "2024-25", "round1")]
        dossiers = [self._make_dossier("someone_else", "2024-25-fall")]
        matched, _unmatched_d, _unmatched_c = match_dossiers_to_candidates(dossiers, candidates)
        assert matched == []
        assert len(_unmatched_d) == 1
        assert len(_unmatched_c) == 1

    def test_different_semester(self) -> None:
        candidates = [self._make_candidate("Akiki Christopher", "2024-25", "round2")]
        dossiers = [self._make_dossier("akiki", "2024-25-fall")]
        matched, _unmatched_d, _unmatched_c = match_dossiers_to_candidates(dossiers, candidates)
        # Different semester → no match
        assert matched == []

    def test_standalone_year_skipped(self) -> None:
        candidates = [self._make_candidate("Someone Name", "2020", "round1")]
        dossiers = [self._make_dossier("someone", "2024-25-fall")]
        matched, _unmatched_d, _unmatched_c = match_dossiers_to_candidates(dossiers, candidates)
        assert matched == []
