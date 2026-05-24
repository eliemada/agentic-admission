"""Ingest anonymized reference letters into a Zero Entropy zsearch collection."""

from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger
from zeroentropy import ZeroEntropy

from agentic_admission.config import settings
from agentic_admission.models.document import DocumentType, classify_document

_PROGRESS_INTERVAL = 50


def _find_letter_files(anonymized_root: Path) -> list[tuple[str, str, Path]]:
    """Discover all recommendation letter text files.

    Parameters
    ----------
    anonymized_root
        Root of anonymized dossier tree.

    Returns
    -------
    list[tuple[str, str, Path]]
        List of ``(doc_path, semester, text_file_path)`` for each letter found.
    """
    results: list[tuple[str, str, Path]] = []

    for semester_dir in sorted(d for d in anonymized_root.iterdir() if d.is_dir()):
        semester = semester_dir.name
        for cand_dir in sorted(d for d in semester_dir.iterdir() if d.is_dir()):
            for doc_dir in sorted(cand_dir.iterdir()):
                if not doc_dir.is_dir() or doc_dir.name.startswith("."):
                    continue
                if classify_document(doc_dir.name) != DocumentType.RECOMMENDATION_LETTER:
                    continue
                md_files = list(doc_dir.glob("*.md"))
                if md_files:
                    doc_path = f"{semester}/{cand_dir.name}/{doc_dir.name}"
                    results.append((doc_path, semester, md_files[0]))

    return results


def _ensure_collection(client: ZeroEntropy, name: str, *, force: bool) -> None:
    """Create or recreate a zsearch collection.

    Parameters
    ----------
    client
        ZeroEntropy client.
    name
        Collection name.
    force
        If True, delete existing collection first.
    """
    if force:
        logger.info("Force mode: deleting collection '{}' if it exists", name)
        try:
            client.collections.delete(collection_name=name)
        except Exception:
            logger.debug("Collection '{}' did not exist, nothing to delete", name)

    try:
        client.collections.add(collection_name=name)
        logger.info("Created collection '{}'", name)
    except Exception:
        logger.debug("Collection '{}' already exists", name)


def ingest_reference_letters(
    anonymized_root: Path, *, collection_name: str | None = None, force: bool = False
) -> int:
    """Upload all anonymized recommendation letters to zsearch.

    The zsearch ingestion pipeline automatically chunks each letter at two
    granularities (coarse ~2000 chars, fine ~200 chars) and embeds them
    with ``zembed-1``.

    Parameters
    ----------
    anonymized_root
        Root of anonymized dossier tree (e.g. ``data/processed/anonymized/``).
    collection_name
        zsearch collection name. Defaults to ``settings.zeroentropy_collection``.
    force
        If True, delete and recreate the collection from scratch.

    Returns
    -------
    int
        Number of documents ingested.
    """
    name = collection_name or settings.zeroentropy_collection
    client = ZeroEntropy(api_key=settings.zeroentropy_api_key)

    _ensure_collection(client, name, force=force)

    if not anonymized_root.is_dir():
        logger.warning("Anonymized root does not exist: {}", anonymized_root)
        return 0

    letter_files = _find_letter_files(anonymized_root)
    logger.info("Found {} recommendation letters to ingest", len(letter_files))

    count = 0
    for doc_path, semester, text_file in letter_files:
        letter_text = text_file.read_text(encoding="utf-8").strip()
        if not letter_text:
            continue

        candidate = text_file.parent.parent.name

        try:
            client.documents.add(
                collection_name=name,
                path=doc_path,
                content={"type": "text", "text": letter_text},
                metadata={
                    "semester": semester,
                    "candidate": candidate,
                    "document_type": "recommendation_letter",
                },
            )
            count += 1

            if count % _PROGRESS_INTERVAL == 0:
                logger.info("Ingested {} letters so far ...", count)

        except Exception:
            logger.warning("Failed to ingest {}", doc_path)

    logger.info("Ingestion complete: {} reference letters uploaded to '{}'", count, name)
    return count


def main() -> None:
    """CLI entrypoint for letter ingestion."""
    parser = argparse.ArgumentParser(description="Ingest reference letters into zsearch")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data/processed/anonymized"),
        help="Root of anonymized dossier tree",
    )
    parser.add_argument(
        "--collection", type=str, default=None, help="zsearch collection name (default: from .env)"
    )
    parser.add_argument("--force", action="store_true", help="Delete and recreate the collection")
    args = parser.parse_args()

    count = ingest_reference_letters(args.root, collection_name=args.collection, force=args.force)
    logger.info("Done. {} documents ingested.", count)


if __name__ == "__main__":
    main()
