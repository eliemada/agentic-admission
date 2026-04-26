# EPFL Curriculum Scraper Design

**Date**: 2026-04-20
**Status**: Implemented

## Goal

Scrape the MTE master program and all EPFL minors from `edu.epfl.ch` to build a competency reference for minor assignment. The MTE master defines what the destination expects; the minors define what candidates can be assigned to. This enables LLM-powered comparison of candidates' transcripts against EPFL's knowledge graph.

## Architecture

### Domain Model (Relational)

```
Program ←── StudyPlanEntry ──→ Course
```

- **Program**: A degree program (slug, name, level, url). Default scope: 1 master (MTE) + ~30 minors. Supports bachelor/master/minor levels.
- **Course**: A unique course (code, name, credits, language, description, learning outcomes, prerequisites, teaching methods, assessment, url).
- **StudyPlanEntry**: Many-to-many link (program_slug, course_code, semester, role, block_name). One course can appear in CS as mandatory and in Math as optional.
- **Curriculum**: Top-level container with query helpers (`courses_for_program`, `programs_for_course`).

All models are frozen Pydantic v2.

### Module Layout

```
src/agentic_admission/curriculum/
├── __init__.py
├── __main__.py       # CLI: python -m agentic_admission.curriculum
├── models.py         # Program, Course, StudyPlanEntry, Curriculum
├── parsers.py        # HTML → domain models (pure functions, no I/O)
├── scraper.py        # Async httpx crawler with semaphore rate-limiting
└── storage.py        # Curriculum ↔ Parquet (3 files)
```

### Scraping Strategy

Three-phase async crawl using httpx:

1. **Discover**: Fetch `/studyplan/en/master/` and `/studyplan/en/minor/` index pages → filter to MTE master + all minors
2. **Study Plans**: For each program, fetch its study plan page → StudyPlanEntry records + coursebook URLs
3. **Courses**: For each unique course URL, fetch coursebook page → Course records

Default scope: MTE master + all minors (~31 programs). Pass `levels` and `master_slugs` to `scrape_curriculum()` to override (e.g., add bachelors for competency baseline comparison).

Concurrency: 5 requests (semaphore). Polite user-agent header.

### Storage

Three Parquet files in `data/reference/epfl_curriculum/`:
- `programs.parquet`
- `courses.parquet`
- `study_plan_entries.parquet`

### Key Design Decisions

1. **Parsers are pure functions** — they take HTML strings and return domain models. No network I/O. Easy to test with HTML fixtures.
2. **Scraper re-fetches study plans** to collect coursebook URLs rather than maintaining state between phases. Trades ~50 extra requests for simpler code.
3. **Course deduplication by code** — the same course (e.g. MATH-101) appears in multiple programs; we store it once.
4. **No caching** — full scrape is infrequent (once/year). Simplicity over caching infrastructure.

## Future: Competency Taxonomy

The scraped data is phase 1. Phase 2 (not yet built):
1. LLM extracts a competency taxonomy from course descriptions/learning outcomes
2. Candidate transcripts are mapped to the same taxonomy
3. Gap analysis: coverage against EPFL baseline → data-driven institution quality signal

## Usage

```bash
uv run poe scrape-curriculum
```
