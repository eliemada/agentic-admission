"""Tests for the passport stripping module."""

from __future__ import annotations

from pathlib import Path

from agentic_admission.anonymizer.strip_passports import (
    _is_passport_dir,
    delete_passport_dirs,
    scan_dossiers,
    write_inventory,
)


class TestIsPassportDir:
    """Tests for _is_passport_dir helper."""

    def test_matches_passeport(self) -> None:
        assert _is_passport_dir("10 - Passeport_F123456") is True

    def test_matches_identite(self) -> None:
        assert _is_passport_dir("10 - Pièce d'identité_F654321") is True

    def test_matches_identite_without_accent(self) -> None:
        assert _is_passport_dir("10 - Piece identite_F654321") is True

    def test_case_insensitive(self) -> None:
        assert _is_passport_dir("PASSEPORT") is True
        assert _is_passport_dir("Identité") is True

    def test_non_passport_dir(self) -> None:
        assert _is_passport_dir("1 - CV_F123456") is False
        assert _is_passport_dir("2 - Lettre de motivation_F789") is False


class TestScanDossiers:
    """Tests for scan_dossiers using a temporary directory tree."""

    def test_detects_passport_dirs(self, tmp_path: Path) -> None:
        # Build: semester/candidate with a passport folder
        semester = tmp_path / "2024-25-fall"
        cand = semester / "smith"
        passport = cand / "10 - Passeport_F123"
        passport.mkdir(parents=True)

        # Add a file inside the passport folder
        (passport / "scan.pdf").write_bytes(b"%PDF-fake" + b"\x00" * 2048)

        rows = scan_dossiers(tmp_path)

        assert len(rows) == 1
        assert rows[0]["semester"] == "2024-25-fall"
        assert rows[0]["candidate_folder"] == "smith"
        assert rows[0]["has_passport_id"] is True
        assert rows[0]["passport_file_count"] == 1
        assert rows[0]["passport_size_kb"] > 0

    def test_no_passport_dir(self, tmp_path: Path) -> None:
        semester = tmp_path / "2024-25-fall"
        cand = semester / "doe"
        cv = cand / "1 - CV_F123"
        cv.mkdir(parents=True)
        (cv / "resume.pdf").write_bytes(b"%PDF-fake")

        rows = scan_dossiers(tmp_path)

        assert len(rows) == 1
        assert rows[0]["has_passport_id"] is False
        assert rows[0]["passport_file_count"] == 0

    def test_multiple_candidates(self, tmp_path: Path) -> None:
        semester = tmp_path / "2024-25-fall"
        # Candidate with passport
        cand1 = semester / "alice"
        (cand1 / "10 - Passeport_F1").mkdir(parents=True)
        (cand1 / "10 - Passeport_F1" / "id.pdf").write_bytes(b"%PDF")

        # Candidate without passport
        cand2 = semester / "bob"
        (cand2 / "1 - CV_F2").mkdir(parents=True)
        (cand2 / "1 - CV_F2" / "cv.pdf").write_bytes(b"%PDF")

        rows = scan_dossiers(tmp_path)

        assert len(rows) == 2
        by_name = {r["candidate_folder"]: r for r in rows}
        assert by_name["alice"]["has_passport_id"] is True
        assert by_name["bob"]["has_passport_id"] is False


class TestWriteInventory:
    """Tests for write_inventory parquet output."""

    def test_writes_parquet(self, tmp_path: Path) -> None:
        import pyarrow.parquet as pq

        rows = [
            {
                "semester": "2024-25-fall",
                "candidate_folder": "smith",
                "has_passport_id": True,
                "passport_file_count": 2,
                "passport_size_kb": 150.5,
                "passport_dir": "/tmp/fake",
            }
        ]
        output = tmp_path / "inventory.parquet"
        write_inventory(rows, output)

        assert output.exists()
        table = pq.read_table(output)
        assert table.num_rows == 1
        assert table.column_names == [
            "semester",
            "candidate_folder",
            "has_passport_id",
            "passport_file_count",
            "passport_size_kb",
        ]


class TestDeletePassportDirs:
    """Tests for delete_passport_dirs."""

    def test_deletes_existing_dirs(self, tmp_path: Path) -> None:
        passport_dir = tmp_path / "passport"
        passport_dir.mkdir()
        (passport_dir / "scan.pdf").write_bytes(b"%PDF-fake")

        rows = [
            {
                "semester": "2024",
                "candidate_folder": "test",
                "has_passport_id": True,
                "passport_file_count": 1,
                "passport_size_kb": 10.0,
                "passport_dir": str(passport_dir),
            }
        ]

        deleted, freed_mb = delete_passport_dirs(rows)

        assert deleted == 1
        assert freed_mb > 0
        assert not passport_dir.exists()

    def test_skips_non_passport_rows(self, tmp_path: Path) -> None:
        rows = [
            {
                "semester": "2024",
                "candidate_folder": "test",
                "has_passport_id": False,
                "passport_file_count": 0,
                "passport_size_kb": 0.0,
                "passport_dir": "",
            }
        ]

        deleted, freed_mb = delete_passport_dirs(rows)

        assert deleted == 0
        assert freed_mb == 0.0
