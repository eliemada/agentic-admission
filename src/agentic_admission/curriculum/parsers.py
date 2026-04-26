"""HTML parsers for edu.epfl.ch study plan and coursebook pages.

Each parser takes raw HTML (str) and returns domain model instances.
No network I/O happens here — that's the scraper's job.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from agentic_admission.curriculum.models import (
    Course,
    CourseRole,
    Program,
    ProgramLevel,
    StudyPlanEntry,
)

_EDU_ROOT = "https://edu.epfl.ch"


# ---------------------------------------------------------------------------
# Program index parsing
# ---------------------------------------------------------------------------


def parse_program_index(html: str, level: ProgramLevel) -> tuple[Program, ...]:
    """Parse a study plan index page (bachelor/ or master/) into Programs.

    Parameters
    ----------
    html : str
        Raw HTML of the index page.
    level : ProgramLevel
        Whether this is a bachelor or master index.

    Returns
    -------
    tuple[Program, ...]
        Discovered programs.
    """
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main")
    if main is None:
        return ()

    programs: list[Program] = []
    for link in main.find_all("a", href=True):
        href = str(link["href"])
        # Only keep links that match /studyplan/en/{level}/...
        if f"/studyplan/en/{level.value}/" not in href:
            continue

        slug = href.rstrip("/").split("/")[-1]
        name = str(link.get("title", "") or link.get_text(strip=True))
        url = href if href.startswith("http") else _EDU_ROOT + href

        programs.append(Program(slug=slug, name=name, level=level, url=url))

    return tuple(programs)


# ---------------------------------------------------------------------------
# Study plan page parsing
# ---------------------------------------------------------------------------


def _classify_block_role(block_heading: str) -> CourseRole:
    """Infer mandatory/optional from a block heading."""
    heading_lower = block_heading.lower()
    if any(kw in heading_lower for kw in ("block", "bloc", "obligatoire")):
        return CourseRole.MANDATORY
    return CourseRole.OPTIONAL


def _extract_course_code_from_text(text: str) -> str:
    """Extract a course code like CS-250 or MATH-101(a) from surrounding text."""
    match = re.search(r"[A-Z]{2,6}-\d{3}\w*(?:\([a-z]\))?", text)
    return match.group(0) if match else ""


def parse_study_plan(html: str, program: Program) -> tuple[StudyPlanEntry, ...]:
    """Parse a study plan page into StudyPlanEntry records.

    Parameters
    ----------
    html : str
        Raw HTML of the study plan page.
    program : Program
        The program this study plan belongs to.

    Returns
    -------
    tuple[StudyPlanEntry, ...]
        Course-to-program links.
    """
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main")
    if main is None:
        return ()

    entries: list[StudyPlanEntry] = []
    current_block = "Unknown"
    current_role = CourseRole.OPTIONAL

    # Walk through headings and course-name divs
    for element in main.find_all(["h2", "h3", "h4", "div"]):
        # Track block headings
        if element.name in {"h2", "h3", "h4"}:
            heading_text = element.get_text(strip=True)
            if heading_text:
                current_block = heading_text
                current_role = _classify_block_role(heading_text)
            continue

        # Course entries live in div.cours-name
        if not isinstance(element, Tag):
            continue
        if "cours-name" not in (element.get("class") or []):
            continue

        link = element.find("a", href=True)
        if link is None:
            continue

        href = str(link["href"])

        # Try to extract course code from sibling text or the URL slug
        parent_row = element.parent
        code = ""
        if parent_row:
            row_text = parent_row.get_text(" ", strip=True)
            code = _extract_course_code_from_text(row_text)

        if not code:
            # Fallback: derive from URL slug (e.g. /analysis-i-MATH-101/)
            slug_part = href.rstrip("/").split("/")[-1]
            code_match = re.search(r"([A-Z]{2,6}-\d{3}\w*(?:\([a-z]\))?)", slug_part)
            code = code_match.group(1) if code_match else slug_part

        entries.append(
            StudyPlanEntry(
                program_slug=program.slug,
                course_code=code,
                role=current_role,
                block_name=current_block,
            )
        )

    return tuple(entries)


# ---------------------------------------------------------------------------
# Coursebook page parsing
# ---------------------------------------------------------------------------


def _extract_section_text(soup: BeautifulSoup, heading_pattern: str) -> str:
    """Extract text after an h2/h3 whose text matches a pattern.

    Collects all sibling content until the next heading.
    """
    for heading in soup.find_all(["h2", "h3"]):
        if re.search(heading_pattern, heading.get_text(strip=True), re.IGNORECASE):
            parts: list[str] = []
            for sibling in heading.next_siblings:
                if isinstance(sibling, Tag) and sibling.name in {"h2", "h3"}:
                    break
                text = (
                    sibling.get_text(" ", strip=True)
                    if isinstance(sibling, Tag)
                    else str(sibling).strip()
                )
                if text:
                    parts.append(text)
            return "\n".join(parts)
    return ""


def parse_course_page(html: str, url: str) -> Course | None:
    """Parse a coursebook page into a Course.

    Parameters
    ----------
    html : str
        Raw HTML of the coursebook page.
    url : str
        The URL this page was fetched from.

    Returns
    -------
    Course | None
        Parsed course, or None if the page structure is unexpected.
    """
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main")
    if main is None:
        return None

    # Title
    h1 = main.find("h1")
    name = h1.get_text(strip=True) if h1 else ""

    # Code and credits from div.course-summary
    code = ""
    ects: int | None = None
    language = ""
    summary_div = soup.find("div", class_="course-summary")

    if summary_div:
        paragraphs = summary_div.find_all("p")
        if paragraphs:
            # First <p>: "CODE / coefficient N"
            first_p = paragraphs[0].get_text(strip=True)
            parts = first_p.split("/")
            code = parts[0].strip()
            if len(parts) > 1:
                credit_match = re.findall(r"\d+", parts[1])
                if credit_match:
                    ects = int(credit_match[0])

        # Language: third <p> if it contains "Langue"
        if len(paragraphs) > 2:  # noqa: PLR2004
            lang_text = paragraphs[2].get_text(strip=True)
            if "Langue" in lang_text or "Language" in lang_text:
                lang_parts = lang_text.split(":")
                if len(lang_parts) > 1:
                    language = lang_parts[1].strip()

    if not code:
        return None

    # Content sections via heading patterns
    description = _extract_section_text(soup, r"(?:R[eé]sum[eé]|Summary)")
    learning_outcomes = _extract_section_text(
        soup, r"(?:Acquis de formation|Learning outcomes|Learning Outcomes)"
    )
    prerequisites_text = _extract_section_text(
        soup, r"(?:Pr[eé]requis|Required courses|Prerequisites)"
    )
    teaching_methods = _extract_section_text(
        soup, r"(?:M[eé]thode d.enseignement|Teaching methods)"
    )
    assessment = _extract_section_text(soup, r"(?:M[eé]thode d.[eé]valuation|Assessment methods)")

    return Course(
        code=code,
        name=name,
        credits=ects,
        language=language,
        description=description,
        learning_outcomes=learning_outcomes,
        prerequisites_text=prerequisites_text,
        teaching_methods=teaching_methods,
        assessment=assessment,
        url=url,
    )
