# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent system for MTE (Master in Management, Technology, and Entrepreneurship) admission decision support at EPFL. Processes heterogeneous Excel application data spanning 2020–2026 and normalizes it into Parquet format. The long-term goal is LLM-based agent evaluation of dossiers, running locally on SCITAS HPC clusters.

## Commands

All commands use **uv** as the package manager and **poethepoet** as the task runner. Prefix poe tasks with `uv run`:

```bash
uv sync --frozen            # Install dependencies (lockfile must be up-to-date)
uv run poe lint             # Run all pre-commit hooks (ruff check, ruff format, ty, etc.)
uv run poe typecheck        # Type check with ty
uv run poe test             # Run pytest with coverage (fails under 40%)
uv run pytest tests/test_import.py::test_package_imports  # Run a single test
uv run poe extract          # Extract Excel files → data/processed/all_candidates.parquet
uv run poe run              # Run the main admission agent pipeline
```

## Architecture

```
src/agentic_admission/
├── main.py              # Entry point: configures loguru, launches pipeline
├── config.py            # Pydantic Settings (from .env): log_level, model_name, model_base_url
├── models/candidate.py  # CandidateRecord: Pydantic model with 18 fields per applicant
├── extraction/pipeline.py  # Core: Excel parsing, header normalization, multi-row grouping → Parquet
├── agents/              # WIP: multi-agent orchestration
└── anonymizer/          # WIP: PII anonymization pipeline
```

**Extraction pipeline** (`extraction/pipeline.py`) is the most complex module (~570 lines). It handles varying column layouts across years using fuzzy header matching (`_HEADER_RULES`), groups multi-row records (one row per committee member), detects evaluator triplets and aggregate decision columns, and extracts gender from hidden columns in newer files.

**Data flow**: Raw Excel files in `data/raw/applications/` → `CandidateRecord` Pydantic models → single Parquet file at `data/processed/all_candidates.parquet` (1,342 candidates).

**Notebooks** are Marimo-based (not Jupyter): `notebooks/eda.py` and `notebooks/dossier_eda.py`, opened via `uv run poe eda` / `uv run poe dossier-eda`.

## Code Conventions

- **Python 3.12+**, type hints on all functions, `from __future__ import annotations` everywhere
- **Ruff** with `select = ["ALL"]` (strict), line length 100, numpy-style docstrings
- **Relative imports are banned** (`ban-relative-imports = "all"`)
- **Pydantic v2** for models and settings; settings loaded from `.env` file
- **loguru** for logging (not stdlib `logging`)
- Tests use `--exitfirst --failed-first` and treat warnings as errors
- Pre-commit hooks enforce: ruff check, ruff format, ty check, uv lock consistency

## CI

GitHub Actions (`.github/workflows/test.yml`): lint → type check → test on every push to `main` and all PRs.

## Environment

Copy `.env.example` to `.env`. Config is loaded by `config.py` via pydantic-settings:
- `LOG_LEVEL` — logging verbosity (default: INFO)
- `MODEL_NAME` — LLM model identifier (default: meta-llama/Llama-3.1-8B-Instruct)
- `MODEL_BASE_URL` — local model serving endpoint (default: http://localhost:8000/v1)

## Data

Data files (`data/`) are gitignored. See `data/FILE_MAPPING.md` for the full inventory of raw Excel files and naming conventions. The `data.tar` archive (~9.6 GB) contains all raw application and dossier data.
