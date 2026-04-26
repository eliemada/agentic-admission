"""Async scraper for EPFL curriculum data from edu.epfl.ch.

Three-phase crawl:
1. Discover programs from study plan index pages.
2. Parse study plan pages for course-to-program links.
3. Fetch full details for each unique course from coursebook pages.

Uses httpx with a semaphore for polite concurrency.

Default scope: MTE master + all EPFL minors (the two program types
relevant to MTE admission minor assignment).  Pass ``levels`` to
``scrape_curriculum`` to override.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from agentic_admission.curriculum.models import (
    Course,
    Curriculum,
    Program,
    ProgramLevel,
    StudyPlanEntry,
)
from agentic_admission.curriculum.parsers import (
    parse_course_page,
    parse_program_index,
    parse_study_plan,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

_EDU_ROOT = "https://edu.epfl.ch"
_LEVEL_INDEX_URLS: dict[ProgramLevel, str] = {
    ProgramLevel.BACHELOR: f"{_EDU_ROOT}/studyplan/en/bachelor/",
    ProgramLevel.MASTER: f"{_EDU_ROOT}/studyplan/en/master/",
    ProgramLevel.MINOR: f"{_EDU_ROOT}/studyplan/en/minor/",
}

_MTE_SLUG = "management-technology-and-entrepreneurship"

_DEFAULT_CONCURRENCY = 5
_DEFAULT_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _fetch(client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore) -> str | None:
    """Fetch a URL with rate limiting, returning HTML or None on failure."""
    async with semaphore:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.warning("Failed to fetch {}", url)
            return None
        else:
            return response.text


async def _discover_programs(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    levels: Sequence[ProgramLevel],
    *,
    master_slugs: Sequence[str] | None = None,
) -> tuple[Program, ...]:
    """Fetch index pages and parse programs.

    Parameters
    ----------
    levels : Sequence[ProgramLevel]
        Which index pages to crawl.
    master_slugs : Sequence[str] | None
        If given, only keep masters whose slug is in this list.
        Minors are always kept in full.
    """
    programs: list[Program] = []
    for level in levels:
        url = _LEVEL_INDEX_URLS[level]
        html = await _fetch(client, url, semaphore)
        if html is None:
            logger.error("Could not fetch {} index at {}", level.value, url)
            continue
        parsed = parse_program_index(html, level)

        # Filter masters to requested slugs
        if level == ProgramLevel.MASTER and master_slugs is not None:
            parsed = tuple(p for p in parsed if p.slug in master_slugs)

        logger.info("Found {} {} programs", len(parsed), level.value)
        programs.extend(parsed)
    return tuple(programs)


async def _scrape_study_plans(
    client: httpx.AsyncClient, programs: Sequence[Program], semaphore: asyncio.Semaphore
) -> tuple[StudyPlanEntry, ...]:
    """Fetch and parse study plan pages for all programs."""

    async def _fetch_and_parse(program: Program) -> tuple[StudyPlanEntry, ...]:
        html = await _fetch(client, program.url, semaphore)
        if html is None:
            return ()
        entries = parse_study_plan(html, program)
        logger.debug("{}: {} course entries", program.slug, len(entries))
        return entries

    tasks = [_fetch_and_parse(p) for p in programs]
    results = await asyncio.gather(*tasks)
    all_entries: list[StudyPlanEntry] = []
    for batch in results:
        all_entries.extend(batch)
    logger.info("Total study plan entries: {}", len(all_entries))
    return tuple(all_entries)


async def _scrape_courses(
    client: httpx.AsyncClient, programs: Sequence[Program], semaphore: asyncio.Semaphore
) -> tuple[Course, ...]:
    """Fetch and parse coursebook pages for all unique courses."""
    course_urls: dict[str, str] = {}
    for program in programs:
        html = await _fetch(client, program.url, semaphore)
        if html is None:
            continue
        _extract_course_urls(html, course_urls)

    logger.info("Unique course URLs to fetch: {}", len(course_urls))

    async def _fetch_and_parse_course(url: str) -> Course | None:
        full_url = url if url.startswith("http") else _EDU_ROOT + url
        html = await _fetch(client, full_url, semaphore)
        if html is None:
            return None
        return parse_course_page(html, full_url)

    tasks = [_fetch_and_parse_course(url) for url in course_urls.values()]
    results = await asyncio.gather(*tasks)
    courses = [c for c in results if c is not None]
    logger.info("Successfully parsed {} courses", len(courses))
    return tuple(courses)


def _extract_course_urls(html: str, accumulator: dict[str, str]) -> None:
    """Extract coursebook URLs from a study plan page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main")
    if main is None:
        return

    for div in main.find_all("div", class_="cours-name"):
        link = div.find("a", href=True)
        if link is None:
            continue
        href = str(link["href"])
        slug = href.rstrip("/").split("/")[-1]
        if slug not in accumulator:
            accumulator[slug] = href


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def scrape_curriculum(
    *,
    levels: Sequence[ProgramLevel] = (ProgramLevel.MASTER, ProgramLevel.MINOR),
    master_slugs: Sequence[str] = (_MTE_SLUG,),
    concurrency: int = _DEFAULT_CONCURRENCY,
    request_timeout: float = _DEFAULT_TIMEOUT,
) -> Curriculum:
    """Scrape EPFL curriculum and return a Curriculum.

    By default scrapes only the MTE master and all minors — the programs
    relevant to MTE admission minor assignment.

    Parameters
    ----------
    levels : Sequence[ProgramLevel]
        Which program levels to crawl (default: master + minor).
    master_slugs : Sequence[str]
        When crawling masters, only keep these slugs (default: MTE only).
        Ignored for bachelor/minor levels.
    concurrency : int
        Maximum concurrent HTTP requests (default 5).
    request_timeout : float
        HTTP request timeout in seconds.

    Returns
    -------
    Curriculum
        Complete curriculum with programs, courses, and study plan entries.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        timeout=request_timeout,
        follow_redirects=True,
        headers={"User-Agent": "EPFL-MTE-Admission-Scraper/1.0"},
    ) as client:
        # Phase 1: discover programs
        programs = await _discover_programs(client, semaphore, levels, master_slugs=master_slugs)
        if not programs:
            msg = "No programs discovered — check network connectivity"
            raise RuntimeError(msg)

        # Phase 2: scrape study plans
        entries = await _scrape_study_plans(client, programs, semaphore)

        # Phase 3: scrape individual course pages
        courses = await _scrape_courses(client, programs, semaphore)

    # Deduplicate courses by code (same course may appear in multiple programs)
    seen_codes: set[str] = set()
    unique_courses: list[Course] = []
    for course in courses:
        if course.code not in seen_codes:
            seen_codes.add(course.code)
            unique_courses.append(course)

    logger.info(
        "Curriculum scraped: {} programs, {} courses, {} entries",
        len(programs),
        len(unique_courses),
        len(entries),
    )

    return Curriculum(programs=programs, courses=tuple(unique_courses), entries=entries)
