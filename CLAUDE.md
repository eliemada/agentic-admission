# CLAUDE.md

Guidance for Claude Code (claude.ai/code) and other AI assistants working in this repository.

## Project Overview

Agentic Admission is a multi-agent LLM panel that triages MTE (Master in Management, Technology, and Entrepreneurship) application dossiers at EPFL. Four specialist evaluator agents read a dossier in parallel, a Chair agent detects disagreement and synthesises a weighted verdict, and a deterministic GPA gate applies a three-band ACCEPT/DISCUSS/REJECT rule. Output is bullet-point pros/cons (not prose) so the committee can scan many candidates quickly.

Calibrated against the 2025-26 EPFL-internal cohort, the panel reaches **82% agreement with the committee** (23/28, single-run), **76.6% decision stability** across 5 runs, and **100% anonymisation coverage** on emails, phones, addresses, and Swiss identifiers (>99% on names after two targeted fixes). The whole system is model-agnostic: it runs on Gemini Flash (~$0.08/dossier), Sonnet 4.6 (~$0.70/dossier), or locally on EPFL's SCITAS cluster via vLLM-served Llama 3.1 (~$0).

Final deliverables live in `reports/`: `final_report.typ` (the semester report, builds to ~400 KB PDF), `final_presentation.pptx` (15-slide defence deck), `anonymization-audit.typ`, plus Graphviz architecture diagrams under `reports/figures/`.

## Commands

uv is the package manager; poethepoet runs all tasks. Prefix with `uv run`.

```bash
uv sync --frozen                  # Install deps from uv.lock (fails if lock stale)
uv run poe lint                   # pre-commit: ruff check, ruff format, ty, etc.
uv run poe typecheck              # ty check src/
uv run poe test                   # pytest + coverage (gate at 55%, currently ~57.9%)
uv run pytest tests/test_chair.py # Run a single test file
```

### Data pipeline (run in order if starting from scratch)

```bash
uv run poe ingest             # Ingest dossier ZIP/TAR/dir into data/staging/
uv run poe normalize-files    # Standardise filenames, convert docx→pdf
uv run poe strip-passports    # Remove passport/ID files (logged before delete)
uv run poe setup-nlp          # One-time: install spaCy en_core_web_sm
uv run poe extract-text       # Docling: PDFs → Markdown (PyMuPDF text, VLM OCR for scans)
uv run poe anonymize          # Presidio + GLiNER: strip PII to <NAME>, <EMAIL>, etc.
uv run poe extract            # Excel → data/processed/all_candidates.parquet (1,342 rows)
uv run poe build-cohort       # Build the cohort manifest from the candidate Parquet
```

### Evaluation

```bash
uv run poe evaluate           # Run the agent panel on the active cohort
uv run poe demo               # Same, on a 5-candidate demo subset
uv run poe calibrate          # Calibration loop: panel vs committee, edit prompts, re-run
```

### Curriculum scraper (university course catalogues)

```bash
uv run poe scrape-curriculum  # Scrape EPFL and partner-university course catalogues
uv run poe mine-universities  # Build per-university profile JSON for the panel
```

### Dashboard

```bash
uv run poe dashboard          # Production: FastAPI serves API + built React frontend
uv run poe dashboard-dev      # Dev: hot-reload FastAPI + Vite dev server in parallel
```

### Notebooks (Marimo, not Jupyter)

```bash
uv run poe eda                # Open notebooks/eda.py
uv run poe dossier-eda        # Open notebooks/dossier_eda.py
uv run poe export-eda         # Render eda.py to reports/eda.html (also: export-dossier-eda)
```

## Architecture

```
src/agentic_admission/        # ~12,400 LOC across ~58 modules
├── main.py                   # Entry point: configures loguru, launches pipeline
├── config.py                 # pydantic-settings: loads .env
├── models/                   # Pydantic models
│   ├── candidate.py          # CandidateRecord (18 fields per applicant)
│   ├── document.py           # Per-document metadata
│   ├── dossier.py            # Full dossier (multiple documents)
│   ├── evaluation.py         # AgentScorecard, PanelVerdict, DebateTranscript
│   └── minor.py              # Disciplinary-minor catalogue (36 minors, 18 sections)
├── agents/                   # The 4-evaluator panel + Chair
│   ├── llm_client.py         # 352 lines: shared httpx, JSON-schema mode, exp backoff
│   ├── evaluators.py         # 306 lines: Academic, Reference, Motivation, Devil's Advocate
│   ├── chair.py              # 705 lines: disagreement detection, debate, weighted synthesis, 3-band gate
│   ├── evaluation_profile.py # EXTERNAL_PROFILE vs INTERNAL_PROFILE (different weights)
│   ├── gpa_gate.py           # Three-band GPA rule applied post-synthesis
│   ├── gpa_extractor.py      # Pulls GPA + per-course detail from anonymised transcripts
│   ├── epfl_minor_map.py     # Bachelor-section → default minor mapping
│   ├── minor_advisor.py      # LLM-driven minor recommendation from bachelor + courses + motivation
│   ├── dossier_loader.py     # Loads anonymised Markdown + metadata for one candidate
│   ├── orchestrator.py       # Async fan-out across the 4 evaluators
│   ├── prompts.py            # Per-evaluator system + user prompt templates
│   └── run_evaluation.py     # CLI entry: `poe evaluate`
├── extraction/
│   ├── pipeline.py           # 523 lines: heterogeneous-Excel parsing, fuzzy headers, 2020-2026 schema drift
│   ├── synthese_parser.py    # Parses synthese candidate dossier PDFs
│   └── cohort_builder.py     # Assembles a per-round cohort from the master Parquet
├── anonymizer/               # Presidio + GLiNER + custom recognizers + 9 post-filters
│   ├── presidio_pipeline.py  # `poe anonymize` entry point
│   ├── recognizers.py        # SCIPER, AVS, IBAN, Swiss phone patterns
│   ├── post_filters.py       # 9 filters: dedupe, span merge, header strip, etc.
│   ├── dob_operator.py       # Date-of-birth redaction operator
│   ├── strip_passports.py    # Pre-anonymisation pass: removes ID document images
│   ├── allow_lists.py        # Whitelisted entities (cities, university names)
│   └── thresholds.py         # Per-entity confidence thresholds
├── calibration/              # Compare panel verdicts to committee ground truth
│   ├── ingest.py             # `poe calibrate-ingest`: ground-truth from Excel
│   ├── profiler.py           # `poe calibrate-profiles`: per-candidate profile JSON for the panel
│   └── retriever.py          # Hooks into Zero Entropy for letter retrieval
├── curriculum/               # University course-catalogue scraper for minor matching
│   ├── scraper.py            # Fetch course pages
│   ├── parsers.py            # Per-university HTML parsers
│   ├── matcher.py            # Course → EPFL-minor matching
│   └── university_profiles.py  # Per-university metadata
├── intake/                   # Ingest dossier archives into staging
│   ├── adapter.py            # ZIP/TAR/dir adapter
│   ├── scanner.py            # Walk staging tree
│   └── matcher.py            # Match dossier files to candidate Parquet rows
└── preprocessing/
    ├── normalize_files.py    # Standardise filenames, docx→pdf
    └── text_extraction.py    # Two-phase: PyMuPDF (fast text) + Docling VLM OCR (scanned)
```

### Agent pipeline at runtime

1. **Phase 1 — Independent Evaluation (parallel).** Each evaluator reads its slice of the anonymised dossier and emits an `AgentScorecard` with integer scores 1-10 across its assigned dimensions. Concretely, the 8 dimensions in use (names match `evaluation_profile.py` exactly):
   - Academic Evaluator → `academic_strength`, `institution_quality`
   - Reference Evaluator → `reference_quality`, `calibration_confidence`
   - Motivation Evaluator → `motivation_clarity`, `program_fit`
   - Devil's Advocate → `risk_flags`, `consistency`
   Output is bullet-point pros/cons, never prose. Evaluators never see each other's scorecards (prevents anchoring).
2. **Phase 2 — Disagreement Detection.** The Chair detects *semantic* disagreement via an LLM call (`chair.py detect_disagreements`): two evaluators interpreting the same evidence differently, not a numeric score-gap threshold.
3. **Phase 3 — Targeted Debate** (conditional). For each flagged dimension, run a 2-round structured debate: round 1 positions, round 2 rebuttals. If no conflicts, skip.
4. **Phase 4 — Final Synthesis.** Chair computes a weighted composite over 8 dimensions. Profile-dependent weights live in `agents/evaluation_profile.py` as `EXTERNAL_PROFILE` and `EPFL_INTERNAL_PROFILE` (both frozen dataclasses; weights must sum to 1.0 or construction fails). Shape of the weighting:
   - **External candidates** (default): academic_strength + institution_quality + reference_quality dominate (66%); calibration_confidence carries 12%; motivation and program_fit are tiebreakers (6% each); risk_flags + consistency are sanity checks (10% combined).
   - **EPFL-internal candidates** (`skip_reference=True`): reference dimensions zero out because internal applicants don't submit letters; academic_strength jumps to 45%; motivation_clarity + program_fit are upweighted to 15% each to compensate.
   Always read the live weights from `evaluation_profile.py` before citing them. They have been re-tuned multiple times during calibration.
5. **GPA gate** (deterministic, post-synthesis). Applies the 3-band rule:
   - ACCEPT: composite ≥ ACCEPT_COMPOSITE_FLOOR (7.5 for EPFL-internal)
   - REJECT: composite < REJECT_COMPOSITE_FLOOR (7.0 external, 6.5 internal)
   - WAITLIST: between the two floors (sent to committee)
   Calibrated against the 2024-25 fall ground truth (see `agents/chair.py` for the calibration history comments).

### Dashboard

`dashboard/` is a FastAPI app (`api.py`) serving a React/TypeScript frontend (`frontend/`, built with Vite). It loads pre-computed `PanelVerdict` JSONs and presents them as bullet-point pros/cons with a click-to-expand debate panel. As of writing, the frontend ships with Vite 8, TypeScript 6, React 19, and lucide-react 1. No automated frontend tests yet; verify with `npm run build` in `dashboard/frontend/`.

## Reports

```
reports/
├── README.md                        # Deliverables index (start here for grading)
├── final_report.typ                 # Semester report; builds with `typst compile`
├── final_report.pdf                 # Rendered (whitelisted in .gitignore, committed)
├── final_presentation.pptx          # 15-slide defence deck
├── anonymization-audit.typ/.pdf     # Anonymisation methodology + coverage numbers
├── architecture-design.pdf          # Pre-implementation architecture sketch
├── references.bib                   # Report bibliography
├── figures/
│   ├── deliberation_protocol.dot/.png/.pdf/.svg         # Portrait diagram for the report
│   ├── deliberation_protocol_landscape.dot/.png         # Landscape variant for slide 7
│   └── completeness_matrix.png                          # Per-year document-completeness heatmap
├── weekly/
│   ├── template.typ                 # Shared weekly-report template (also used by the audit)
│   └── semaine-{01..14}.typ/.pdf    # Weekly progress reports (PDFs committed)
└── calibration/
    └── *.md                         # Per-iteration calibration analyses (committee vs system)
```

Rebuild any Typst report: `cd reports && typst compile final_report.typ`. Rebuild a Graphviz diagram: `cd reports/figures && dot -Tpng deliberation_protocol_landscape.dot -o deliberation_protocol_landscape.png`.

## Code Conventions

- **Python 3.13+** required (see `pyproject.toml`). Type hints on every function. `from __future__ import annotations` at the top of every module.
- **Ruff** with `select = ["ALL"]` (strict); line length 100; numpy-style docstrings; relative imports banned (`ban-relative-imports = "all"`).
- **Pydantic v2** for all data models and settings. Settings loaded from `.env` via `pydantic-settings`.
- **loguru** for logging, never stdlib `logging`.
- Tests run with `--exitfirst --failed-first` and treat warnings as errors. Coverage gate at 55% (currently ~57.9%, 535 tests across 30 files).
- Pre-commit hooks: ruff check, ruff format, **ty** (Astral's type checker, not mypy), uv lock consistency, file-end normalisation.
- **`# type: ignore[...]` does not work for `ty`.** When `ty` complains about a loose `object` parameter, type it properly via a `TYPE_CHECKING` import. See `preprocessing/text_extraction.py` for the pattern.

## CI

GitHub Actions (`.github/workflows/test.yml`) runs lint → typecheck → test on every push to `main` and every PR. Frontend is not tested in CI; run `npm run build` in `dashboard/frontend/` manually before merging dashboard changes.

## Environment

Copy `.env.example` to `.env`. Loaded by `config.py` via `pydantic-settings`. Vars in use:

```bash
# Logging
LOG_LEVEL=INFO

# Text LLM (vLLM on SCITAS, or OpenAI-compatible endpoint)
MODEL_NAME=meta-llama/Llama-3.1-8B-Instruct
MODEL_BASE_URL=http://localhost:8000/v1

# Vision LLM for scanned PDFs (Docling VLM pipeline)
VLM_MODEL_NAME=reducto/RolmOCR
VLM_BASE_URL=http://localhost:8001/v1

# Anonymisation
PRESIDIO_SCORE_THRESHOLD=0.5
GLINER_MODEL=knowledgator/gliner-multitask-large-v0.5
ANONYMIZER_EXCLUDED_ENTITIES_RAW=LOCATION,NRP,organization,ORGANIZATION

# Reference-letter retrieval
ZEROENTROPY_API_KEY=ze-...
ZEROENTROPY_COLLECTION=mte-reference-letters

# Calibration profile generation
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=anthropic/claude-sonnet-4
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

## Data

`data/` is gitignored in full. `data/FILE_MAPPING.md` documents the raw Excel inventory and per-year schema differences. `data.tar` (~9.6 GB) holds the full raw application and dossier archive. The processed Parquet at `data/processed/all_candidates.parquet` carries 1,342 candidates across 6 academic years (2020-21 through 2025-26).

PII handling is non-negotiable: every dossier goes through `anonymizer/presidio_pipeline.py` (Presidio + GLiNER + 9 custom post-filters + Swiss-specific recognizers for SCIPER/AVS/IBAN) before any LLM sees it. Audit coverage: 100% on emails, phones, addresses, government IDs; 99.x% on names after two regex fixes. Methodology and stratified-sample numbers are in `reports/anonymization-audit.typ`.

## Important nuances for future sessions

- **Minor assignment is a first-class output.** Per the 2026-04-19 supervisor meeting, the system must not only emit ACCEPT/DISCUSS/REJECT but also recommend a disciplinary minor for accepted candidates. The mapping rules live in `agents/epfl_minor_map.py` (36 minors across 18 sections, 16 bachelor mappings, default-fallback: Industrial Engineering bachelor → Systems Engineering minor). `agents/minor_advisor.py` does the LLM-driven recommendation from bachelor + courses + motivation. EPFL-internal candidates get lighter-weight evaluation.
- **`typer` is pinned directly** in `pyproject.toml` even though nothing in this codebase imports it. `weasel 1.0` dropped it as a hard transitive, but `spacy.cli.download` still imports it at module load and `presidio_analyzer.nlp_engine` triggers that import. Removing the pin breaks every test that touches the anonymiser. See the comment above the dep in `pyproject.toml`.
- **EPFL-internal vs external candidates use different weights AND different thresholds.** Don't tune one without the other. The split was the single biggest calibration win, taking EPFL-internal agreement from 68% to 82% (PR #23).
- **Output format is bullet-point pros/cons in two columns (+ / −), never prose paragraphs.** This is a hard requirement from the professor. Agent prompts must instruct bullet output. The dashboard renders + in green, − in red, debates behind click-to-expand.
- **Calibration is iterative and cheap.** One cycle ~$2 + 6 minutes on 28 candidates: run panel → aggregate majority vote → diff against committee → identify disagreement class → form hypothesis → edit prompt → re-run. The 50% → 82% trajectory in 3 weeks came from this loop, not from a single big change.

## References

- `reports/final_report.typ` — full semester writeup with methodology, results, limitations
- `reports/final_presentation.pptx` — 15-slide defence deck with speaker notes
- `docs/plans/2026-03-24-admission-dashboard-design.md` — original dashboard design
- `docs/plans/2026-05-08-gpa-gate.md` — GPA gate calibration record
- `data/FILE_MAPPING.md` — raw Excel inventory + per-year schema notes
