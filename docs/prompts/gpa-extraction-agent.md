# GPA Extraction Agent — Implementation Prompt

Paste this entire file into a new Claude Code window.

---

## Task

Build a GPA extraction agent that reads anonymized transcript documents and extracts structured GPA information. This agent runs as part of the dossier loading phase, before the evaluation agents.

## Codebase Context

This is a multi-agent admission evaluation system for EPFL's MTE program. The pipeline is:

```
Anonymized dossier texts → Dossier Loader → GPA Agent (NEW) → 4 Evaluator Agents → Chair → Verdict
```

### Key files to read first

```bash
# Read these to understand the existing patterns:
cat src/agentic_admission/agents/evaluators.py   # How typed response models work
cat src/agentic_admission/agents/llm_client.py    # How LLM calls are made (httpx + JSON Schema)
cat src/agentic_admission/agents/dossier_loader.py  # DossierContent model — where GPA will be added
cat src/agentic_admission/models/document.py      # DocumentType.TRANSCRIPT classification
cat src/agentic_admission/config.py               # Settings (openrouter_api_key, etc.)
```

### How agents work in this codebase

Each agent:
1. Has a **typed Pydantic response model** with explicit named fields (NOT generic `dict[str, int]`)
2. Sends a system prompt + user content to the LLM via `complete()` from `llm_client.py`
3. The LLM responds with JSON matching the Pydantic schema
4. The response is validated and returned

Example from `evaluators.py`:

```python
class AcademicResponse(BaseModel, frozen=True):
    academic_strength: int
    academic_strength_justification: str
    institution_quality: int
    institution_quality_justification: str

response = await complete(
    messages=messages,
    response_model=AcademicResponse,
    model=model, base_url=base_url, client=client,
)
```

### Transcript content

Transcripts are anonymized markdown at `data/processed/anonymized/{semester}/{candidate}/{doc_folder}/text.md`. They contain grades in many formats:

- French system: 14.5/20, 16/20
- Swiss system: 5.3/6, 4.75/6
- US system: 3.7/4.0, A, B+
- Indian system: 8.5/10, 85/100
- UK system: First Class Honours, 68%
- German system: 1.3, 2.5 (1=best, 5=worst)
- Multiple transcripts per candidate (bachelor + exchange + etc.)

The `DossierContent.transcript_text` field contains all transcripts concatenated.

### Where GPA fits in

Currently `DossierContent` has these fields but GPA is NOT extracted:

```python
class DossierContent(BaseModel, frozen=True):
    candidate_id: str
    semester: str
    folder_name: str
    transcript_text: str = ""    # <-- GPA agent reads this
    letters_text: str = ""
    motivation_text: str = ""
    cv_text: str = ""
    full_dossier_text: str = ""
    # ... metadata fields
```

## What to build

### 1. Response model: `GpaExtraction`

Create `src/agentic_admission/agents/gpa_extractor.py`:

```python
class GpaExtraction(BaseModel, frozen=True):
    """Structured GPA information extracted from transcripts."""

    gpa_value: str              # e.g. "3.7", "14.5", "5.3"
    gpa_scale: str              # e.g. "4.0", "20", "6.0"
    gpa_normalized: float       # Normalized to 0-100 scale for comparison
    grading_system: str         # e.g. "US 4.0", "French /20", "Swiss /6", "German 1-5"
    institution_name: str       # Extracted from transcript
    degree_name: str            # e.g. "BSc Electrical Engineering"
    notable_courses: str        # Strengths/weaknesses in specific courses
    trajectory: str             # "improving", "declining", "stable", "mixed"
    confidence: float           # 0.0-1.0, how confident the extraction is
```

### 2. System prompt

The prompt should instruct the LLM to:
- Identify the grading scale from context clues (university name, country, grade format)
- Extract the overall GPA/average
- Normalize to a 0-100 scale using these conversions:
  - US: GPA × 25 (so 4.0 → 100, 3.0 → 75)
  - French /20: score × 5 (so 16/20 → 80)
  - Swiss /6: (score - 1) × 20 (so 5.0/6 → 80, 4.0/6 → 60)
  - German: (5 - score) × 25 (so 1.0 → 100, 2.5 → 62.5)
  - Indian /10: score × 10
  - Percentage: as-is
- Handle multiple transcripts (pick primary institution, note exchange grades)
- Flag if GPA cannot be determined (e.g. transcript is an image, or grades are pass/fail)

### 3. Integration

Add a `extract_gpa` function:

```python
async def extract_gpa(
    transcript_text: str,
    *,
    model: str,
    base_url: str,
    client: httpx.AsyncClient | None = None,
) -> GpaExtraction:
```

### 4. Wire into `DossierContent`

Add GPA fields to `DossierContent`:

```python
class DossierContent(BaseModel, frozen=True):
    # ... existing fields ...
    gpa_value: str = ""
    gpa_scale: str = ""
    gpa_normalized: float = 0.0
    institution_name: str = ""
```

### 5. Wire into `run_evaluation.py`

In `evaluate_single()`, call `extract_gpa()` before the orchestrator, and pass the results into the dossier content. The GPA info should also be displayed in the dashboard.

### 6. Wire into dashboard

In `dashboard/verdict_loader.py`, the `load_verdict()` function should read GPA from the verdict JSON (once it's saved there) and display it in the candidate card.

## Important conventions

- `from __future__ import annotations` at top of every file
- All models use `frozen=True`
- Type hints on all functions, numpy-style docstrings
- `loguru` for logging (not stdlib logging)
- Ruff with `select = ["ALL"]`, line length 100
- Run `uv run ruff check` after writing code
- The LLM is called via OpenRouter (OpenAI-compatible, needs API key in Authorization header)
- The orchestrator creates an `httpx.AsyncClient` with auth headers and shares it

## Testing

Run the extraction on a few candidates to verify:

```bash
uv run python -c "
from pathlib import Path
from agentic_admission.agents.dossier_loader import load_all_anonymized_dossiers
ds = load_all_anonymized_dossiers(Path('data/processed/anonymized'), limit=3)
# Show first 500 chars of transcript to understand the format
for d in ds:
    print(f'{d.candidate_id}:')
    print(d.transcript_text[:500])
    print('---')
"
```

Then run the full pipeline:

```bash
uv run python -m agentic_admission.agents.run_evaluation \
  --limit 5 \
  --model anthropic/claude-sonnet-4.6 \
  --base-url https://openrouter.ai/api/v1
```
