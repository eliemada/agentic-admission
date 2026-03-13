"""Tests for the dossier file normalization module."""

from __future__ import annotations

from pathlib import Path

from agentic_admission.preprocessing.normalize_files import (
    _detect_type,
    _fix_filename,
    normalize_dossiers,
)


class TestDetectType:
    """Tests for magic-byte file type detection."""

    def test_detects_pdf(self, tmp_path: Path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 rest of content")
        assert _detect_type(pdf) == ".pdf"

    def test_detects_docx(self, tmp_path: Path) -> None:
        docx = tmp_path / "test.docx"
        docx.write_bytes(b"PK\x03\x04 rest of content")
        assert _detect_type(docx) == ".docx"

    def test_unknown_type(self, tmp_path: Path) -> None:
        unknown = tmp_path / "test.xyz"
        unknown.write_bytes(b"UNKNOWN_MAGIC_BYTES")
        assert _detect_type(unknown) == ""

    def test_empty_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.write_bytes(b"")
        assert _detect_type(empty) == ""

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        assert _detect_type(tmp_path / "nonexistent") == ""


class TestFixFilename:
    """Tests for filename correction based on detected type."""

    def test_already_correct(self) -> None:
        assert _fix_filename("document.pdf", ".pdf") == "document.pdf"

    def test_wrong_extension(self) -> None:
        assert _fix_filename("document.xyz", ".pdf") == "document.pdf"

    def test_no_extension(self) -> None:
        # stem = "noext", so it gets ".pdf" appended
        assert _fix_filename("noext", ".pdf") == "noext.pdf"

    def test_docx_detected(self) -> None:
        assert _fix_filename("file.pdf", ".docx") == "file.docx"


class TestNormalizeDossiers:
    """Integration tests for normalize_dossiers."""

    def test_copies_pdf_files(self, tmp_path: Path) -> None:
        # Build source tree: semester/candidate/doc_folder/file.pdf
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        cand = src / "2024-fall" / "doe" / "1 - CV_F123"
        cand.mkdir(parents=True)
        (cand / "resume.pdf").write_bytes(b"%PDF-1.4 fake pdf content")

        report = normalize_dossiers(src, dst, convert=False)

        assert report.total == 1
        assert report.copied == 1
        assert len(report.errors) == 0

        # Check output exists
        output_files = list(dst.rglob("*.pdf"))
        assert len(output_files) == 1

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        cand = src / "2024-fall" / "doe" / "1 - CV_F123"
        cand.mkdir(parents=True)
        (cand / "resume.pdf").write_bytes(b"%PDF-1.4 fake pdf content")

        report = normalize_dossiers(src, dst, convert=False, dry_run=True)

        assert report.copied == 1
        assert not dst.exists()

    def test_skips_unknown_files(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        cand = src / "2024-fall" / "doe" / "1 - Doc_F123"
        cand.mkdir(parents=True)
        (cand / "mystery.bin").write_bytes(b"UNKNOWN_MAGIC")

        report = normalize_dossiers(src, dst, convert=False)

        assert report.total == 1
        assert len(report.errors) == 1

    def test_renames_misextended_pdf(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        cand = src / "2024-fall" / "doe" / "1 - CV_F123"
        cand.mkdir(parents=True)
        # PDF content but wrong extension
        (cand / "resume.xyz").write_bytes(b"%PDF-1.4 fake pdf content")

        report = normalize_dossiers(src, dst, convert=False)

        assert report.copied == 1
        assert report.renamed == 1

        output_files = list(dst.rglob("*.pdf"))
        assert len(output_files) == 1
        assert output_files[0].name == "resume.pdf"

    def test_skips_zip_files(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        cand = src / "2024-fall" / "doe" / "1 - Doc_F123"
        cand.mkdir(parents=True)
        (cand / "archive.zip").write_bytes(b"PK\x03\x04 zip content")

        report = normalize_dossiers(src, dst, convert=False)

        assert report.total == 0
        assert report.skipped == 1
