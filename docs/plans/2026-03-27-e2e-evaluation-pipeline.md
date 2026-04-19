# E2E Evaluation Pipeline — Implementation Plan

**Date:** 2026-03-27
**Goal:** Build the complete pipeline from anonymized dossiers to agent verdicts, including the calibration system (zsearch + LLM-generated profiles) and a CLI runner with comparison against committee decisions.

**Design decisions (from brainstorming):**
- zsearch (Zero Entropy) for letter retrieval — automatic chunking + embedding + retrieval
- LLM-generated calibration profiles via OpenRouter, grouped by school_name (3+ letters), fallback: country+quality → country → generic
- OpenRouter for profile generation (cloud, one-time offline task)
- Configurable LLM backend for evaluation (vLLM on SCITAS or cloud)

---

## Task 1: Add dependencies and config

**Files to create/modify:**
- `pyproject.toml` — add `zeroentropy`, `openai` dependencies
- `src/agentic_admission/config.py` — add new settings fields
- `.env.example` — add new env vars

### 1.1 Add dependencies to `pyproject.toml`

In the `[project] dependencies` list, add after the existing entries:

```python
"zeroentropy>=0.1.0a11",
"openai>=1.60.0",
```

### 1.2 Add config fields to `src/agentic_admission/config.py`

Add these fields to the `Settings` class (after the existing `anonymizer_excluded_entities` field):

```python
# Zero Entropy API for letter retrieval
zeroentropy_api_key: str = ""
zeroentropy_collection: str = "mte-reference-letters"

# OpenRouter for calibration profile generation
openrouter_api_key: str = ""
openrouter_model: str = "anthropic/claude-sonnet-4"
openrouter_base_url: str = "https://openrouter.ai/api/v1"

# Calibration profiles output directory
calibration_profiles_dir: str = "data/processed/calibration_profiles"

# Evaluation output directory
evaluation_output_dir: str = "data/processed/evaluations"
```

### 1.3 Update `.env.example`

Add at the bottom:

```bash
# Zero Entropy API (letter retrieval via zsearch)
ZEROENTROPY_API_KEY=ze-...
ZEROENTROPY_COLLECTION=mte-reference-letters

# OpenRouter (calibration profile generation)
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=anthropic/claude-sonnet-4
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Output directories
CALIBRATION_PROFILES_DIR=data/processed/calibration_profiles
EVALUATION_OUTPUT_DIR=data/processed/evaluations
```

### Verification
```bash
uv lock   # lockfile regenerates with new deps
uv sync --frozen
uv run python -c "from agentic_admission.config import settings; print(settings.zeroentropy_collection)"
```

---

## Task 2: Build the dossier loader

**File to create:** `src/agentic_admission/agents/dossier_loader.py`

This module scans `data/processed/anonymized/` and builds the text inputs that `evaluate_candidate()` expects. It reuses the existing `DocumentType` classification.

### 2.1 Data class for loaded dossier content

```python
"""Load anonymized dossier texts and prepare inputs for the agent orchestrator."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from agentic_admission.models.document import DocumentType, classify_document


class DossierContent(BaseModel, frozen=True):
    """Aggregated text content from one candidate's anonymized dossier.

    Each field maps to an input parameter of ``evaluate_candidate()``.

    Attributes
    ----------
    candidate_id
        Identifier in ``"{semester}_{folder_name}"`` format.
    semester
        Semester directory name.
    folder_name
        Candidate folder name.
    transcript_text
        Concatenated text from all TRANSCRIPT documents.
    letters_text
        Concatenated text from all RECOMMENDATION_LETTER documents.
    motivation_text
        Text from the MOTIVATION_LETTER document.
    cv_text
        Text from the CV document.
    full_dossier_text
        All documents concatenated with headers.
    school_country
        From matched CandidateRecord (empty if unmatched).
    school_name
        From matched CandidateRecord (empty if unmatched).
    school_quality
        From matched CandidateRecord (empty if unmatched).
    decision_final
        Committee's actual decision (for comparison).
    """

    candidate_id: str
    semester: str
    folder_name: str
    transcript_text: str = ""
    letters_text: str = ""
    motivation_text: str = ""
    cv_text: str = ""
    full_dossier_text: str = ""
    school_country: str = ""
    school_name: str = ""
    school_quality: str = ""
    decision_final: str = ""
```

### 2.2 Scanning function

```python
def load_anonymized_dossier(candidate_dir: Path, semester: str) -> DossierContent:
    """Read anonymized markdown files from a candidate directory.

    Expected layout::

        candidate_dir/
        ├── 1 - Synthese .../text.md
        ├── 2 - Lettre de motivation .../text.md
        └── ...

    Walks each numbered sub-directory, classifies by name, reads ``text.md``,
    and groups content by ``DocumentType``.
    """
```

Logic:
1. Iterate sorted subdirectories of `candidate_dir`
2. For each subdir, call `classify_document(subdir.name)` to get the `DocumentType`
3. Read `subdir / "text.md"` if it exists
4. Group texts by type into a dict: `{DocumentType: list[str]}`
5. Build `DossierContent`:
   - `transcript_text` = join all `TRANSCRIPT` texts with `\n\n---\n\n`
   - `letters_text` = join all `RECOMMENDATION_LETTER` texts
   - `motivation_text` = first `MOTIVATION_LETTER` text (or empty)
   - `cv_text` = first `CV` text (or empty)
   - `full_dossier_text` = all texts concatenated with `## {doc_type.value}\n\n{text}` headers
   - `candidate_id` = `f"{semester}_{candidate_dir.name}"`

### 2.3 Batch loading function

```python
def load_all_anonymized_dossiers(
    anonymized_root: Path,
    *,
    limit: int | None = None,
) -> list[DossierContent]:
    """Scan the anonymized root and load all candidate dossiers.

    Parameters
    ----------
    anonymized_root
        e.g. ``data/processed/anonymized/``
    limit
        If set, only load the first N candidates (for testing).
    """
```

Logic:
1. Walk `anonymized_root / {semester} / {candidate}` structure
2. Call `load_anonymized_dossier()` for each
3. Apply `limit` if set
4. Return list of `DossierContent`

### 2.4 Enrichment with Parquet data

```python
def enrich_with_parquet(
    dossiers: list[DossierContent],
    parquet_path: Path,
) -> list[DossierContent]:
    """Match dossier contents to CandidateRecords and fill in metadata.

    Uses the existing ``intake.matcher`` module to match by name/semester.
    Populates ``school_country``, ``school_name``, ``school_quality``,
    and ``decision_final`` from the matched CandidateRecord.
    """
```

Logic:
1. Load Parquet with `pyarrow.parquet.read_table()` → iterate rows → build `CandidateRecord` list
2. Build `Dossier` objects from each `DossierContent` (semester, folder_name, empty documents list)
3. Call `match_dossiers_to_candidates()` from `intake.matcher`
4. For each match, create a new `DossierContent` with metadata filled in via `model_copy(update={...})`
5. Return enriched list

### Verification
```bash
uv run python -c "
from pathlib import Path
from agentic_admission.agents.dossier_loader import load_all_anonymized_dossiers
ds = load_all_anonymized_dossiers(Path('data/processed/anonymized'), limit=3)
for d in ds:
    print(f'{d.candidate_id}: transcript={len(d.transcript_text)}c, letters={len(d.letters_text)}c')
"
```

---

## Task 3: Build the calibration ingest pipeline (zsearch)

**File to create:** `src/agentic_admission/calibration/__init__.py`
**File to create:** `src/agentic_admission/calibration/ingest.py`

This module uploads all anonymized recommendation letters to a zsearch collection.

### 3.1 `__init__.py`

```python
"""Calibration pipeline: letter retrieval and cultural profile generation."""
```

### 3.2 Ingest function in `ingest.py`

```python
"""Ingest anonymized reference letters into a Zero Entropy zsearch collection."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from zeroentropy import ZeroEntropy

from agentic_admission.config import settings
from agentic_admission.models.document import DocumentType, classify_document


def ingest_reference_letters(
    anonymized_root: Path,
    *,
    collection_name: str | None = None,
    force: bool = False,
) -> int:
    """Upload all anonymized recommendation letters to zsearch.

    Parameters
    ----------
    anonymized_root
        Root of anonymized dossier tree (e.g. ``data/processed/anonymized/``).
    collection_name
        zsearch collection name. Defaults to ``settings.zeroentropy_collection``.
    force
        If True, recreate the collection from scratch.

    Returns
    -------
    int
        Number of documents ingested.
    """
```

Logic:
1. Create `ZeroEntropy(api_key=settings.zeroentropy_api_key)` client
2. Create or get the collection (`client.collections.add(collection_name=name)`)
3. If `force`, delete existing collection first, then recreate
4. Walk `anonymized_root / {semester} / {candidate} / {doc_folder} / text.md`
5. For each `doc_folder`, call `classify_document(doc_folder_name)`
6. Filter to `DocumentType.RECOMMENDATION_LETTER` only
7. Read the `text.md` content
8. Upload to zsearch:
   ```python
   client.documents.add(
       collection_name=name,
       path=f"{semester}/{candidate}/{doc_folder}",
       content={"type": "text", "text": letter_text},
       metadata={
           "semester": semester,
           "candidate": candidate,
           "document_type": "recommendation_letter",
       },
   )
   ```
9. Log progress every 50 documents
10. Return count of ingested documents

### 3.3 CLI entrypoint

Add `if __name__ == "__main__":` block that:
- Parses `--root` (default `data/processed/anonymized`) and `--force` flags
- Calls `ingest_reference_letters()`
- Prints summary

### 3.4 Add poe task to `pyproject.toml`

```toml
[tool.poe.tasks.calibrate-ingest]
help = "Upload anonymized reference letters to zsearch"
cmd = "python -m agentic_admission.calibration.ingest"
```

### Verification
```bash
uv run poe calibrate-ingest --root data/processed/anonymized
# Then verify in Python:
# client.status.get_status(collection_name="mte-reference-letters")
```

---

## Task 4: Build the calibration profiler (LLM-generated profiles)

**File to create:** `src/agentic_admission/calibration/profiler.py`

This module groups candidates by school, sends reference letters to OpenRouter for summarization, and saves profiles as markdown files.

### 4.1 Grouping logic

```python
"""Generate cultural calibration profiles for reference letter evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq
from loguru import logger
from openai import OpenAI

from agentic_admission.config import settings


def _build_school_groups(
    parquet_path: Path,
    anonymized_root: Path,
) -> dict[str, list[dict[str, str]]]:
    """Group candidates by school with their reference letter texts.

    Returns
    -------
    dict[str, list[dict]]
        Mapping from group key to list of
        ``{"candidate": ..., "semester": ..., "letter_text": ..., "decision": ...}``.
    """
```

Logic:
1. Load Parquet → build list of `(school_name, school_country, school_quality, name, academic_year, admission_round, decision_final)`
2. For each candidate, find their anonymized recommendation letters
3. Group by `school_name`:
   - If group has **3+ candidates** → key = `school_{school_name}` (normalized, lowercase, underscores)
   - Else fall back to `{school_country}_{school_quality}` bucket
   - If that bucket also < 3 → fall back to `country_{school_country}`
   - If still < 3 → fall back to `generic`
4. Return the grouped dict

### 4.2 Profile generation

```python
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
```

Logic:
1. Call `_build_school_groups()` to get groups
2. For each group:
   - Skip if profile file already exists and `force` is False
   - Build user prompt with all letters in the group + their outcomes
   - Call OpenRouter via `openai.OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)`
   - Parse response text
   - Write to `output_dir / f"{group_key}.md"` with YAML frontmatter:
     ```markdown
     ---
     group_key: school_eth_zurich
     school_name: ETH Zurich
     school_country: Switzerland
     school_quality: A
     candidate_count: 12
     ---

     {LLM-generated profile text}
     ```
3. Generate a `generic.md` fallback profile from a random sample of 20 letters across all regions
4. Return count of profiles generated

### 4.3 Profile loading function

```python
def load_calibration_profile(
    school_name: str,
    school_country: str,
    school_quality: str,
    profiles_dir: Path | None = None,
) -> str:
    """Load the best matching calibration profile for a candidate.

    Fallback hierarchy:
    1. ``school_{normalized_name}.md``
    2. ``{country}_{quality}.md``
    3. ``country_{country}.md``
    4. ``generic.md``

    Returns the profile text, or empty string if nothing found.
    """
```

Logic:
1. Normalize school_name to lowercase with underscores, remove special chars
2. Try each fallback key in order
3. Read and return the first matching file's content (strip frontmatter)
4. Return empty string if nothing found

### 4.4 CLI entrypoint and poe task

```python
if __name__ == "__main__":
    # Parse --parquet, --anonymized-root, --output-dir, --force
    generate_profiles(...)
```

```toml
[tool.poe.tasks.calibrate-profiles]
help = "Generate cultural calibration profiles from historical letters"
cmd = "python -m agentic_admission.calibration.profiler"
```

### Verification
```bash
uv run poe calibrate-profiles
ls data/processed/calibration_profiles/
cat data/processed/calibration_profiles/school_eth_zurich.md
```

---

## Task 5: Build the calibration retriever (zsearch query)

**File to create:** `src/agentic_admission/calibration/retriever.py`

This module queries zsearch at evaluation time to get historical letters similar to the candidate's.

### 5.1 Retrieval function

```python
"""Retrieve similar historical reference letters from zsearch."""

from __future__ import annotations

from zeroentropy import ZeroEntropy

from agentic_admission.config import settings


def retrieve_similar_letters(
    candidate_letters: str,
    *,
    collection_name: str | None = None,
    top_k: int = 5,
) -> str:
    """Query zsearch for historical letters similar to the candidate's.

    Parameters
    ----------
    candidate_letters
        The candidate's own reference letter text (used as query).
    collection_name
        zsearch collection. Defaults to ``settings.zeroentropy_collection``.
    top_k
        Number of similar letters to retrieve.

    Returns
    -------
    str
        Formatted markdown of top-K historical letters with metadata.
    """
```

Logic:
1. Create `ZeroEntropy(api_key=settings.zeroentropy_api_key)` client
2. Call `client.queries.top_snippets(collection_name=name, query=candidate_letters, k=top_k)`
3. Format results as markdown:
   ```markdown
   ### Historical Letter 1
   **Source:** {semester}/{candidate}

   {snippet_text}

   ---

   ### Historical Letter 2
   ...
   ```
4. Return the formatted string

### 5.2 Combined retrieval (profile + letters)

```python
def get_calibration_context(
    candidate_letters: str,
    school_name: str,
    school_country: str,
    school_quality: str,
    *,
    top_k: int = 5,
) -> tuple[str, str]:
    """Get both the calibration profile and historical letters for a candidate.

    Returns
    -------
    tuple[str, str]
        (calibration_context, historical_letters) ready for ``evaluate_reference()``.
    """
```

Logic:
1. Call `load_calibration_profile()` from `profiler.py`
2. Call `retrieve_similar_letters()`
3. Return the tuple

### Verification
```bash
uv run python -c "
from agentic_admission.calibration.retriever import get_calibration_context
ctx, letters = get_calibration_context('This student is excellent...', 'ETH Zurich', 'Switzerland', 'A')
print(f'Profile: {len(ctx)} chars, Letters: {len(letters)} chars')
"
```

---

## Task 6: Build the evaluation runner (CLI)

**File to create:** `src/agentic_admission/agents/run_evaluation.py`

This is the main CLI script that ties everything together.

### 6.1 Main runner function

```python
"""CLI runner: evaluate candidates E2E and compare with committee decisions."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from loguru import logger

from agentic_admission.agents.dossier_loader import (
    DossierContent,
    enrich_with_parquet,
    load_all_anonymized_dossiers,
)
from agentic_admission.agents.orchestrator import evaluate_candidate
from agentic_admission.calibration.retriever import get_calibration_context
from agentic_admission.config import settings
from agentic_admission.models.evaluation import PanelVerdict


async def evaluate_single(
    dossier: DossierContent,
    *,
    model: str,
    base_url: str,
) -> PanelVerdict:
    """Evaluate one candidate through the full pipeline.

    Steps:
    1. Get calibration context (profile + historical letters from zsearch)
    2. Call the 4-phase agent orchestrator
    3. Return the PanelVerdict
    """
    calibration_context, historical_letters = get_calibration_context(
        candidate_letters=dossier.letters_text,
        school_name=dossier.school_name,
        school_country=dossier.school_country,
        school_quality=dossier.school_quality,
    )

    return await evaluate_candidate(
        candidate_id=dossier.candidate_id,
        transcript_text=dossier.transcript_text,
        letters_text=dossier.letters_text,
        calibration_context=calibration_context,
        historical_letters=historical_letters,
        motivation_text=dossier.motivation_text,
        cv_text=dossier.cv_text,
        full_dossier_text=dossier.full_dossier_text,
        model=model,
        base_url=base_url,
    )
```

### 6.2 Batch runner

```python
async def run_batch(
    dossiers: list[DossierContent],
    *,
    model: str,
    base_url: str,
    output_dir: Path,
    concurrency: int = 4,
) -> list[tuple[DossierContent, PanelVerdict]]:
    """Evaluate a batch of candidates with bounded concurrency.

    Uses ``asyncio.Semaphore`` to limit parallel LLM calls.
    Saves each verdict as JSON immediately after completion.
    """
```

Logic:
1. Create `asyncio.Semaphore(concurrency)`
2. For each dossier, create an async task wrapped with the semaphore
3. On completion, save verdict to `output_dir / f"{dossier.candidate_id}.json"`:
   ```python
   verdict_path = output_dir / f"{dossier.candidate_id}.json"
   verdict_path.write_text(verdict.model_dump_json(indent=2))
   ```
4. Collect results as `list[tuple[DossierContent, PanelVerdict]]`
5. Return results

### 6.3 Comparison table

```python
def print_comparison_table(
    results: list[tuple[DossierContent, PanelVerdict]],
) -> None:
    """Print a table comparing agent decisions vs committee decisions."""
```

Logic:
1. Print header: `Candidate | Agent | Committee | Composite | Match`
2. For each result:
   - Agent decision = `verdict.decision.value`
   - Committee decision = normalize `dossier.decision_final` (map "OK"→accept, "NO"→reject, etc.)
   - Match = "✓" if they agree, "✗" if not
3. Print summary: `Agreement: X/Y (Z%)`

### 6.4 CLI entrypoint

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="Run E2E admission evaluation")
    parser.add_argument("--anonymized-root", type=Path, default=Path("data/processed/anonymized"))
    parser.add_argument("--parquet", type=Path, default=Path("data/processed/all_candidates.parquet"))
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=5, help="Number of candidates to evaluate")
    parser.add_argument("--model", type=str, default=None, help="LLM model (default: from .env)")
    parser.add_argument("--base-url", type=str, default=None, help="LLM base URL (default: from .env)")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()

    model = args.model or settings.model_name
    base_url = args.base_url or settings.model_base_url
    output_dir = args.output_dir or Path(settings.evaluation_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load and enrich dossiers
    dossiers = load_all_anonymized_dossiers(args.anonymized_root, limit=args.limit)
    dossiers = enrich_with_parquet(dossiers, args.parquet)

    # Run evaluation
    results = asyncio.run(run_batch(
        dossiers, model=model, base_url=base_url,
        output_dir=output_dir, concurrency=args.concurrency,
    ))

    # Print comparison
    print_comparison_table(results)


if __name__ == "__main__":
    main()
```

### 6.5 Add poe tasks

```toml
[tool.poe.tasks.evaluate]
help = "Run E2E admission evaluation on anonymized dossiers"
cmd = "python -m agentic_admission.agents.run_evaluation"

[tool.poe.tasks.calibrate]
help = "Run full calibration pipeline (ingest + profiles)"
sequence = [
    { cmd = "python -m agentic_admission.calibration.ingest" },
    { cmd = "python -m agentic_admission.calibration.profiler" },
]
```

### Verification
```bash
# Local test (with OpenRouter as LLM backend for quick testing)
uv run poe evaluate --limit 3 \
  --model anthropic/claude-sonnet-4 \
  --base-url https://openrouter.ai/api/v1

# SCITAS (with local vLLM)
uv run poe evaluate --limit 20
```

---

## Task 7: Write tests

**Files to create:**
- `tests/test_dossier_loader.py`
- `tests/test_calibration_ingest.py`
- `tests/test_calibration_profiler.py`
- `tests/test_calibration_retriever.py`
- `tests/test_run_evaluation.py`

### 7.1 `test_dossier_loader.py`

Tests for:
- `load_anonymized_dossier()` with a mock directory structure (using `tmp_path`)
- Classification of documents into correct types
- `full_dossier_text` contains all documents
- Empty directories produce empty strings
- `enrich_with_parquet()` populates metadata fields
- `load_all_anonymized_dossiers()` with `limit` parameter

### 7.2 `test_calibration_ingest.py`

Tests for:
- `ingest_reference_letters()` only uploads RECOMMENDATION_LETTER documents
- Skips non-letter documents
- `force=True` recreates the collection
- Handles empty directories gracefully
- Mock the `ZeroEntropy` client to avoid real API calls

### 7.3 `test_calibration_profiler.py`

Tests for:
- `_build_school_groups()` grouping logic:
  - Schools with 3+ candidates get dedicated groups
  - Fallback to country+quality
  - Fallback to country
  - Fallback to generic
- `load_calibration_profile()` fallback hierarchy
- Profile file format (frontmatter + content)
- Mock OpenAI client for `generate_profiles()`

### 7.4 `test_calibration_retriever.py`

Tests for:
- `retrieve_similar_letters()` formats results correctly
- `get_calibration_context()` returns both profile and letters
- Mock the `ZeroEntropy` client

### 7.5 `test_run_evaluation.py`

Tests for:
- `evaluate_single()` calls orchestrator with correct params
- `run_batch()` respects concurrency limit
- `print_comparison_table()` handles different decision formats
- Decision normalization ("OK"→accept, "NO"→reject, "A discuter"→waitlist)
- JSON output file creation

All tests should use `pytest-mock` to patch external API calls. No real API calls in tests.

### Verification
```bash
uv run poe test
```

---

## Task 8: Add SLURM scripts for calibration and evaluation

**Files to create:**
- `slurm/calibrate.sh` — run calibration pipeline (ingest + profiles)
- `slurm/evaluate.sh` — run evaluation pipeline on SCITAS

### 8.1 `slurm/calibrate.sh`

A CPU-only job (no GPU needed) that:
1. Installs deps with `uv sync --frozen`
2. Runs `uv run poe calibrate-ingest`
3. Runs `uv run poe calibrate-profiles`
4. Reports number of profiles generated

SLURM config: `--partition=cpu`, `--qos=normal`, `--time=02:00:00`, `--mem=8G`

### 8.2 `slurm/evaluate.sh`

A GPU job that:
1. Starts vLLM with Qwen 2.5 (or configurable model)
2. Waits for health check
3. Runs `uv run poe evaluate --limit N`
4. Saves verdicts to `data/processed/evaluations/`
5. Prints comparison table

SLURM config: `--partition=gpu`, `--qos=normal`, `--gres=gpu:1`, `--time=06:00:00`, `--mem=32G`

### Verification
```bash
sbatch slurm/calibrate.sh
sbatch slurm/evaluate.sh
```

---

## Execution Order

| Task | Depends on | Can parallelize |
|------|-----------|-----------------|
| 1. Dependencies + config | — | — |
| 2. Dossier loader | Task 1 | — |
| 3. Calibration ingest | Task 1 | With Task 2 |
| 4. Calibration profiler | Task 1 | With Task 2, 3 |
| 5. Calibration retriever | Task 3, 4 | — |
| 6. Evaluation runner | Task 2, 5 | — |
| 7. Tests | Task 2-6 | — |
| 8. SLURM scripts | Task 6 | With Task 7 |

**Recommended batch execution:**
- **Batch 1:** Tasks 1, 2, 3, 4 (all independent after Task 1)
- **Batch 2:** Task 5, 6
- **Batch 3:** Tasks 7, 8
