"""Generate cultural calibration profiles for reference letter evaluation."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pyarrow.parquet as pq
from loguru import logger
from openai import OpenAI

from agentic_admission.config import settings
from agentic_admission.intake.matcher import name_to_folder_candidates, semester_from_record
from agentic_admission.models.document import DocumentType, classify_document

_MIN_GROUP_SIZE = 3

_PROFILE_SYSTEM_PROMPT = (
    "You are an expert in international higher education admissions. "
    "You will receive a set of anonymized recommendation letters from the same "
    "institution or region, along with the admission outcomes for each candidate.\n\n"
    "Generate a calibration profile that describes:\n"
    "1. Typical tone and language intensity (superlative vs. reserved)\n"
    "2. Common structural patterns (length, specificity, concrete examples)\n"
    "3. Cultural writing conventions that affect interpretation\n"
    "4. How to distinguish a strong vs. average letter from this context\n"
    "5. Correlation between letter characteristics and admission outcomes\n\n"
    "Be concise (300-500 words). This profile will help a reference letter "
    "evaluator calibrate their assessment."
)


def _normalize_key(name: str) -> str:
    """Normalize a string to a valid filesystem-safe key.

    Parameters
    ----------
    name
        Raw string (e.g. school name, country).

    Returns
    -------
    str
        Lowercased, special chars replaced with underscores, stripped.
    """
    key = name.strip().lower()
    key = re.sub(r"[^a-z0-9]+", "_", key)
    return key.strip("_")


def _collect_letters_for_candidate(
    anonymized_root: Path, semester: str, folder_name: str
) -> list[str]:
    """Read all recommendation letter texts for a specific candidate.

    Parameters
    ----------
    anonymized_root
        Root of anonymized dossier tree.
    semester
        Semester directory name.
    folder_name
        Candidate folder name.

    Returns
    -------
    list[str]
        Text content of each recommendation letter found.
    """
    cand_dir = anonymized_root / semester / folder_name
    if not cand_dir.is_dir():
        return []

    letters: list[str] = []
    for doc_dir in sorted(cand_dir.iterdir()):
        if not doc_dir.is_dir() or doc_dir.name.startswith("."):
            continue
        if classify_document(doc_dir.name) != DocumentType.RECOMMENDATION_LETTER:
            continue
        md_files = list(doc_dir.glob("*.md"))
        if md_files:
            content = md_files[0].read_text(encoding="utf-8").strip()
            if content:
                letters.append(content)
    return letters


def _fallback_key(country: str, quality: str) -> str:
    """Compute the fallback group key for a candidate.

    Parameters
    ----------
    country
        Normalized country key.
    quality
        Normalized quality key.

    Returns
    -------
    str
        Fallback key following the hierarchy: country+quality → country → generic.
    """
    if country and quality:
        return f"{country}_{quality}"
    if country:
        return f"country_{country}"
    return "generic"


def _collect_candidates_with_letters(
    parquet_path: Path, anonymized_root: Path
) -> list[dict[str, str]]:
    """Scan Parquet and match candidates to their anonymized letters.

    Parameters
    ----------
    parquet_path
        Path to ``all_candidates.parquet``.
    anonymized_root
        Root of anonymized dossier tree.

    Returns
    -------
    list[dict[str, str]]
        One entry per candidate with letter text and metadata.
    """
    table = pq.read_table(parquet_path)
    rows = table.to_pydict()
    n_rows = table.num_rows

    result: list[dict[str, str]] = []
    for i in range(n_rows):
        school_name = str(rows["school_name"][i] or "")
        school_country = str(rows["school_country"][i] or "")
        school_quality = str(rows["school_quality"][i] or "")
        academic_year = str(rows["academic_year"][i] or "")
        admission_round = str(rows["admission_round"][i] or "")
        decision = str(rows.get("decision_final", [""])[i] or "")
        name = str(rows["name"][i] or "")

        semester = semester_from_record(academic_year, admission_round)
        if semester is None:
            continue

        folder_keys = name_to_folder_candidates(name)
        if not folder_keys:
            continue

        # Try each candidate folder key to find letters
        for fk in folder_keys:
            letters = _collect_letters_for_candidate(anonymized_root, semester, fk)
            if letters:
                result.append(
                    {
                        "school_name": school_name,
                        "school_country": school_country,
                        "school_quality": school_quality,
                        "decision": decision,
                        "semester": semester,
                        "folder_name": fk,
                        "letter_text": "\n\n---\n\n".join(letters),
                    }
                )
                break

    logger.info("Found {} candidates with reference letters", len(result))
    return result


def _apply_fallback_hierarchy(
    by_school: dict[str, list[dict[str, str]]],
) -> dict[str, list[dict[str, str]]]:
    """Collapse small groups following the fallback hierarchy.

    Parameters
    ----------
    by_school
        Initial grouping by ``school_{name}`` key.

    Returns
    -------
    dict[str, list[dict[str, str]]]
        Final groups after applying fallback collapses.
    """
    groups: dict[str, list[dict[str, str]]] = {}

    for key, members in by_school.items():
        if len(members) >= _MIN_GROUP_SIZE:
            groups[key] = members
        else:
            for member in members:
                country = _normalize_key(member["school_country"])
                quality = _normalize_key(member["school_quality"])
                groups.setdefault(_fallback_key(country, quality), []).append(member)

    # Collapse small country+quality groups into country or generic
    final: dict[str, list[dict[str, str]]] = {}
    for key, members in groups.items():
        if len(members) >= _MIN_GROUP_SIZE or key.startswith("school_"):
            final[key] = members
        else:
            parts = key.split("_")
            country_key = f"country_{parts[0]}" if parts else "generic"
            final.setdefault(country_key, []).extend(members)

    # Collapse small country groups into generic
    result: dict[str, list[dict[str, str]]] = {}
    for key, members in final.items():
        if len(members) >= _MIN_GROUP_SIZE or key.startswith("school_"):
            result[key] = members
        else:
            result.setdefault("generic", []).extend(members)

    return result


def _build_school_groups(
    parquet_path: Path, anonymized_root: Path
) -> dict[str, list[dict[str, str]]]:
    """Group candidates by school with their reference letter texts.

    Fallback hierarchy (applied when a group has fewer than 3 candidates):

    1. ``school_{normalized_name}`` — dedicated institution profile
    2. ``{country}_{quality}`` — country + school quality bucket
    3. ``country_{country}`` — country-only bucket
    4. ``generic`` — catch-all

    Parameters
    ----------
    parquet_path
        Path to ``all_candidates.parquet``.
    anonymized_root
        Root of anonymized dossier tree.

    Returns
    -------
    dict[str, list[dict]]
        Mapping from group key to list of candidate letter records.
    """
    candidates = _collect_candidates_with_letters(parquet_path, anonymized_root)

    # Group by school_name
    by_school: dict[str, list[dict[str, str]]] = {}
    for c in candidates:
        key = f"school_{_normalize_key(c['school_name'])}" if c["school_name"] else ""
        if key:
            by_school.setdefault(key, []).append(c)

    result = _apply_fallback_hierarchy(by_school)

    logger.info("Built {} calibration groups", len(result))
    for key, members in sorted(result.items()):
        logger.debug("  {}: {} candidates", key, len(members))

    return result


def _generate_single_profile(client: OpenAI, group_key: str, members: list[dict[str, str]]) -> str:
    """Generate a calibration profile for one group via OpenRouter.

    Parameters
    ----------
    client
        OpenAI-compatible client pointed at OpenRouter.
    group_key
        The group identifier.
    members
        List of candidate letter records in this group.

    Returns
    -------
    str
        LLM-generated profile text.
    """
    letter_sections = [
        f"### Candidate {i} (Outcome: {m['decision'] or 'unknown'})\n\n{m['letter_text']}"
        for i, m in enumerate(members, 1)
    ]

    user_prompt = (
        f"Group: {group_key}\n"
        f"Number of candidates: {len(members)}\n\n"
        "## Reference Letters\n\n" + "\n\n---\n\n".join(letter_sections)
    )

    extra: dict = {}
    if settings.openrouter_provider:
        extra["extra_body"] = {"provider": {"order": [settings.openrouter_provider]}}

    response = client.chat.completions.create(
        model=settings.openrouter_model,
        messages=[
            {"role": "system", "content": _PROFILE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=1024,
        **extra,
    )

    return response.choices[0].message.content or ""


def generate_profiles(
    parquet_path: Path,
    anonymized_root: Path,
    output_dir: Path | None = None,
    *,
    force: bool = False,
) -> int:
    """Generate calibration profiles for all school groups.

    Parameters
    ----------
    parquet_path
        Path to ``all_candidates.parquet``.
    anonymized_root
        Root of anonymized dossier tree.
    output_dir
        Where to write profile markdown files.
        Defaults to ``settings.calibration_profiles_dir``.
    force
        If True, regenerate existing profiles.

    Returns
    -------
    int
        Number of profiles generated.
    """
    out = output_dir or Path(settings.calibration_profiles_dir)
    out.mkdir(parents=True, exist_ok=True)

    groups = _build_school_groups(parquet_path, anonymized_root)

    client = OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)

    count = 0
    for group_key, members in sorted(groups.items()):
        profile_path = out / f"{group_key}.md"

        if profile_path.exists() and not force:
            logger.debug("Skipping existing profile: {}", group_key)
            continue

        logger.info("Generating profile for '{}' ({} candidates) ...", group_key, len(members))

        profile_text = _generate_single_profile(client, group_key, members)

        countries = {m["school_country"] for m in members if m["school_country"]}
        schools = {m["school_name"] for m in members if m["school_name"]}
        qualities = {m["school_quality"] for m in members if m["school_quality"]}

        frontmatter = (
            f"---\n"
            f"group_key: {group_key}\n"
            f"school_names: {', '.join(sorted(schools)) or 'various'}\n"
            f"countries: {', '.join(sorted(countries)) or 'various'}\n"
            f"school_qualities: {', '.join(sorted(qualities)) or 'various'}\n"
            f"candidate_count: {len(members)}\n"
            f"---\n\n"
        )

        profile_path.write_text(frontmatter + profile_text, encoding="utf-8")
        count += 1
        logger.info("Saved profile: {}", profile_path)

    logger.info("Generated {} calibration profiles in {}", count, out)
    return count


def load_calibration_profile(
    school_name: str, school_country: str, school_quality: str, profiles_dir: Path | None = None
) -> str:
    """Load the best matching calibration profile for a candidate.

    Fallback hierarchy:

    1. ``school_{normalized_name}.md``
    2. ``{country}_{quality}.md``
    3. ``country_{country}.md``
    4. ``generic.md``

    Parameters
    ----------
    school_name
        Institution name.
    school_country
        Country of the institution.
    school_quality
        Quality rating (A/B/C/X).
    profiles_dir
        Directory containing profile files.
        Defaults to ``settings.calibration_profiles_dir``.

    Returns
    -------
    str
        Profile text (frontmatter stripped), or empty string if not found.
    """
    directory = profiles_dir or Path(settings.calibration_profiles_dir)

    keys: list[str] = []
    if school_name:
        keys.append(f"school_{_normalize_key(school_name)}")
    if school_country and school_quality:
        keys.append(f"{_normalize_key(school_country)}_{_normalize_key(school_quality)}")
    if school_country:
        keys.append(f"country_{_normalize_key(school_country)}")
    keys.append("generic")

    for key in keys:
        path = directory / f"{key}.md"
        if path.exists():
            content = path.read_text(encoding="utf-8")
            # Strip YAML frontmatter if present
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    content = content[end + 3 :].strip()
            return content

    logger.debug(
        "No calibration profile found for {} / {} / {}", school_name, school_country, school_quality
    )
    return ""


def main() -> None:
    """CLI entrypoint for profile generation."""
    parser = argparse.ArgumentParser(description="Generate calibration profiles")
    parser.add_argument(
        "--parquet",
        type=Path,
        default=Path("data/processed/all_candidates.parquet"),
        help="Path to candidates Parquet file",
    )
    parser.add_argument(
        "--anonymized-root",
        type=Path,
        default=Path("data/processed/anonymized"),
        help="Root of anonymized dossier tree",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for profiles (default: from .env)",
    )
    parser.add_argument("--force", action="store_true", help="Regenerate existing profiles")
    args = parser.parse_args()

    count = generate_profiles(args.parquet, args.anonymized_root, args.output_dir, force=args.force)
    logger.info("Done. {} profiles generated.", count)


if __name__ == "__main__":
    main()
