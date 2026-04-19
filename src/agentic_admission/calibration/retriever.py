"""Retrieve similar historical reference letters from zsearch."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from pathlib import Path
from zeroentropy import ZeroEntropy

from agentic_admission.calibration.profiler import load_calibration_profile
from agentic_admission.config import settings

_DEFAULT_TOP_K = 5


def retrieve_similar_letters(
    candidate_letters: str,
    *,
    collection_name: str | None = None,
    top_k: int = _DEFAULT_TOP_K,
) -> str:
    """Query zsearch for historical letters similar to the candidate's.

    Uses ``top_snippets`` to get the most relevant passages from the
    letter corpus, automatically reranked by zsearch.

    Parameters
    ----------
    candidate_letters
        The candidate's own reference letter text (used as the query).
    collection_name
        zsearch collection. Defaults to ``settings.zeroentropy_collection``.
    top_k
        Number of similar snippets to retrieve.

    Returns
    -------
    str
        Formatted markdown of top-K historical letter snippets with metadata.
        Empty string if no results or if the API key is not configured.
    """
    if not settings.zeroentropy_api_key:
        logger.debug("ZEROENTROPY_API_KEY not set, skipping letter retrieval")
        return ""

    if not candidate_letters.strip():
        return ""

    name = collection_name or settings.zeroentropy_collection
    client = ZeroEntropy(api_key=settings.zeroentropy_api_key)

    # Truncate query if very long — zsearch handles this but let's be safe
    query = candidate_letters[:8000]

    try:
        response = client.queries.top_snippets(
            collection_name=name,
            query=query,
            k=top_k,
        )
    except Exception:
        logger.warning("zsearch query failed, returning empty historical letters")
        return ""

    if not response.results:
        logger.debug("No similar letters found in zsearch")
        return ""

    sections: list[str] = []
    for i, result in enumerate(response.results, 1):
        source = result.path or "unknown"
        score = f"{result.score:.3f}" if result.score is not None else "N/A"
        sections.append(
            f"### Historical Letter {i} (score: {score})\n"
            f"**Source:** {source}\n\n"
            f"{result.content}"
        )

    formatted = "\n\n---\n\n".join(sections)
    logger.debug("Retrieved {} similar letter snippets from zsearch", len(response.results))
    return formatted


def get_calibration_context(
    candidate_letters: str,
    school_name: str,
    school_country: str,
    school_quality: str,
    *,
    profiles_dir: Path | None = None,
    top_k: int = _DEFAULT_TOP_K,
) -> tuple[str, str]:
    """Get both the calibration profile and historical letters for a candidate.

    This is the main entry point at evaluation time, returning the two
    strings needed by ``evaluate_reference()``.

    Parameters
    ----------
    candidate_letters
        The candidate's reference letter text.
    school_name
        Institution name (for profile lookup).
    school_country
        Country of the institution.
    school_quality
        Quality rating (A/B/C/X).
    profiles_dir
        Override for calibration profiles directory.
    top_k
        Number of historical letter snippets to retrieve.

    Returns
    -------
    tuple[str, str]
        ``(calibration_context, historical_letters)`` ready for
        ``evaluate_reference()``.
    """
    profile = load_calibration_profile(
        school_name=school_name,
        school_country=school_country,
        school_quality=school_quality,
        profiles_dir=profiles_dir,
    )

    historical = retrieve_similar_letters(
        candidate_letters,
        top_k=top_k,
    )

    return profile, historical
