"""Tests for the intake adapter (ZIP/TAR/directory ingestion)."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest

from agentic_admission.intake.adapter import ArchiveFormat, detect_format, ingest

# ---------------------------------------------------------------------------
# Helpers to build fake dossier trees inside archives
# ---------------------------------------------------------------------------


def _build_tree(root: Path) -> None:
    """Create a minimal dossier tree under *root*."""
    sem = root / "2024-25-fall"
    cand = sem / "akiki"
    doc = cand / "1 - Cand. Master Synthese de la candidature_B123"
    doc.mkdir(parents=True)
    (doc / "summary.pdf").write_bytes(b"%PDF-fake")

    doc2 = cand / "11 - Cand. Master CV_F456"
    doc2.mkdir(parents=True)
    (doc2 / "cv.pdf").write_bytes(b"%PDF-fake")


def _make_zip(tmp_path: Path) -> Path:
    """Create a ZIP archive containing a dossier tree."""
    tree = tmp_path / "tree"
    _build_tree(tree)

    archive_path = tmp_path / "dossiers.zip"
    with zipfile.ZipFile(archive_path, "w") as zf:
        for file_path in tree.rglob("*"):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(tree))
            elif file_path.is_dir():
                # Add directory entries so structure is preserved
                zf.write(file_path, str(file_path.relative_to(tree)) + "/")
    return archive_path


def _make_tar_gz(tmp_path: Path) -> Path:
    """Create a .tar.gz archive containing a dossier tree."""
    tree = tmp_path / "tree"
    _build_tree(tree)

    archive_path = tmp_path / "dossiers.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tf:
        tf.add(tree, arcname=".")
    return archive_path


def _make_per_candidate_zips(tmp_path: Path) -> Path:
    """Create a directory of per-candidate ZIP files."""
    tree = tmp_path / "tree"
    _build_tree(tree)

    zips_dir = tmp_path / "candidate_zips"
    zips_dir.mkdir()

    sem_dir = tree / "2024-25-fall"
    for cand_dir in sem_dir.iterdir():
        if not cand_dir.is_dir():
            continue
        zip_path = zips_dir / f"{cand_dir.name}.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for file_path in cand_dir.rglob("*"):
                if file_path.is_file():
                    arcname = str(Path("2024-25-fall") / cand_dir.name / file_path.relative_to(cand_dir))
                    zf.write(file_path, arcname)
    return zips_dir


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


class TestDetectFormat:
    def test_zip_file(self, tmp_path: Path) -> None:
        path = _make_zip(tmp_path)
        assert detect_format(path) == ArchiveFormat.ZIP

    def test_tar_gz_file(self, tmp_path: Path) -> None:
        path = _make_tar_gz(tmp_path)
        assert detect_format(path) == ArchiveFormat.TAR

    def test_directory(self, tmp_path: Path) -> None:
        _build_tree(tmp_path / "dossiers")
        assert detect_format(tmp_path / "dossiers") == ArchiveFormat.DIRECTORY

    def test_directory_of_zips(self, tmp_path: Path) -> None:
        zips_dir = _make_per_candidate_zips(tmp_path)
        assert detect_format(zips_dir) == ArchiveFormat.ZIP_DIRECTORY

    def test_unknown_file_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "data.csv"
        bad.write_text("a,b,c")
        with pytest.raises(ValueError, match="Unsupported"):
            detect_format(bad)

    def test_nonexistent_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            detect_format(tmp_path / "nope")


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


class TestIngest:
    def test_ingest_directory(self, tmp_path: Path) -> None:
        tree = tmp_path / "dossiers"
        _build_tree(tree)
        dest = tmp_path / "staging"
        dossiers = ingest(tree, dest)
        assert len(dossiers) == 1
        assert dossiers[0].folder_name == "akiki"
        assert len(dossiers[0].documents) >= 2

    def test_ingest_zip(self, tmp_path: Path) -> None:
        archive = _make_zip(tmp_path)
        dest = tmp_path / "staging"
        dossiers = ingest(archive, dest)
        assert len(dossiers) == 1
        assert dossiers[0].folder_name == "akiki"

    def test_ingest_tar_gz(self, tmp_path: Path) -> None:
        archive = _make_tar_gz(tmp_path)
        dest = tmp_path / "staging"
        dossiers = ingest(archive, dest)
        assert len(dossiers) == 1
        assert dossiers[0].folder_name == "akiki"

    def test_ingest_per_candidate_zips(self, tmp_path: Path) -> None:
        zips_dir = _make_per_candidate_zips(tmp_path)
        dest = tmp_path / "staging"
        dossiers = ingest(zips_dir, dest)
        assert len(dossiers) == 1
        assert dossiers[0].folder_name == "akiki"

    def test_ingest_creates_destination(self, tmp_path: Path) -> None:
        tree = tmp_path / "dossiers"
        _build_tree(tree)
        dest = tmp_path / "new" / "staging"
        assert not dest.exists()
        ingest(tree, dest)
        assert dest.exists()

    def test_path_traversal_rejected(self, tmp_path: Path) -> None:
        """Archives with '../' paths must be sanitized."""
        archive_path = tmp_path / "evil.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("../../etc/passwd", "root:x:0:0")
        dest = tmp_path / "staging"
        # Should not extract outside dest, should produce 0 dossiers
        dossiers = ingest(archive_path, dest)
        assert dossiers == []
        assert not (tmp_path / "etc" / "passwd").exists()
