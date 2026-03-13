"""Walk a dossier directory tree and build Dossier objects."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from loguru import logger

from agentic_admission.models.document import (
    DossierDocument,
    classify_document,
    parse_document_number,
)
from agentic_admission.models.dossier import Dossier


def _scan_candidate_folder(
    candidate_dir: Path,
    semester: str,
    dossier_root: Path,
) -> Dossier:
    """Build a ``Dossier`` from a single candidate folder.

    Parameters
    ----------
    candidate_dir
        Absolute path to a candidate's folder (e.g. ``…/2024-25-fall/akiki``).
    semester
        The semester name (e.g. ``"2024-25-fall"``).
    dossier_root
        Root of the dossier tree, used to compute relative paths.

    Returns
    -------
    Dossier
        A dossier with classified documents.
    """
    documents: list[DossierDocument] = []

    # Each numbered sub-folder (or direct file) is a document
    for entry in sorted(candidate_dir.iterdir()):
        if entry.name.startswith("."):
            continue

        relative = PurePosixPath(entry.relative_to(dossier_root))
        doc_type = classify_document(entry.name)
        number = parse_document_number(entry.name)

        documents.append(
            DossierDocument(path=relative, document_type=doc_type, number=number),
        )

    return Dossier(
        folder_name=candidate_dir.name,
        semester=semester,
        documents=documents,
    )


def scan_dossier_tree(root: Path) -> list[Dossier]:
    """Scan a dossier root directory and return one ``Dossier`` per candidate.

    Expected layout::

        root/
        ├── 2024-25-fall/
        │   ├── akiki/
        │   │   ├── 1 - Cand. Master Synthese …/
        │   │   └── 2 - Cand. Master Lettre …/
        │   └── …
        └── 2024-25-spring/

    Parameters
    ----------
    root
        Root directory containing semester sub-directories.

    Returns
    -------
    list[Dossier]
        One dossier per candidate folder found.
    """
    if not root.is_dir():
        logger.warning("Dossier root does not exist: {}", root)
        return []

    dossiers: list[Dossier] = []

    semester_dirs = sorted(d for d in root.iterdir() if d.is_dir())
    for semester_dir in semester_dirs:
        semester = semester_dir.name
        candidate_dirs = sorted(d for d in semester_dir.iterdir() if d.is_dir())

        for cand_dir in candidate_dirs:
            dossier = _scan_candidate_folder(cand_dir, semester, root)
            dossiers.append(dossier)

        logger.debug(
            "Scanned {}: {} candidates",
            semester,
            len(candidate_dirs),
        )

    logger.info("Scanned {} dossiers from {}", len(dossiers), root)
    return dossiers
