# Contributing to Agentic Admission

Thank you for your interest in improving this project. This guide is short on purpose: the bar is *clarity* and *reproducibility*, not gatekeeping.

This is a research codebase built around a measure-and-close loop. Every change should make the next measurement easier, not harder.

---

## Ground rules

1. **No PII in commits.** Real candidate names, emails, transcripts, or letters must never land in the repository — not in tests, fixtures, comments, screenshots, nor commit messages. The `data/` directory is gitignored on purpose. Synthetic or redacted-by-design examples only.
2. **Spec-first for non-trivial changes.** If a change is larger than a bug fix, write a short Markdown design doc in [`docs/plans/`](docs/plans/) first. State the hypothesis, the alternatives considered, the chosen approach, and the validation criteria. See existing design docs for shape.
3. **Measurement, not opinions.** Claims about agreement / stability / coverage must come with a re-runnable script. Prefer numbers from `scripts/` or `tests/` over numbers from a notebook cell.

---

## Development environment

```bash
git clone https://github.com/eliemada/agentic-admission.git
cd agentic-admission
uv sync --frozen
uv run poe setup-nlp        # one-time spaCy model download
pre-commit install          # ruff + ruff-format + ty + uv lock check
```

Copy `.env.example` to `.env` and fill in your endpoints / API keys (none are required for `lint` / `typecheck` / `test`).

---

## The four-command loop

Every change must satisfy:

```bash
uv run poe lint        # 700+ ruff rules + pre-commit hooks
uv run poe typecheck   # ty check src (zero errors required)
uv run poe test        # 519+ tests, ≥55% coverage gate
uv run poe extract     # rebuild the canonical Parquet if extraction touched
```

If any of these fails, the PR is not ready. CI runs the first three on every push.

---

## Code style

The pyproject is the source of truth — read it before pushing back on a lint warning.

- **Python 3.13+**, type hints on every function signature.
- `from __future__ import annotations` everywhere.
- **Ruff** with `select = ["ALL"]`, line length 100, NumPy-style docstrings.
- **Relative imports are banned** (`ban-relative-imports = "all"`).
- **Pydantic v2** for models. Settings load from `.env` via pydantic-settings.
- **loguru**, not the stdlib `logging` module.
- Use **immutable dataclasses** (`@dataclass(frozen=True)`) when state should not mutate after construction.
- Tests use `pytest --exitfirst --failed-first` and treat warnings as errors.

If your code lives in `scripts/`, `slurm/`, or `dashboard/`, relaxed lint rules apply via `per-file-ignores` — but library code in `src/agentic_admission/` is held to the full ruff `ALL` set.

---

## Testing

- New code paths require new tests. Aim for ≥80% coverage on touched code.
- Use the fixture helpers in [`tests/conftest.py`](tests/conftest.py) (`make_scorecard`, `make_justification`, `make_verdict_summary`, `make_panel_verdict`) instead of constructing models by hand in each test. They were centralised in week 14 to make schema migrations cheap.
- For LLM-touching code, mock the client unless the test is explicitly an integration test (then mark `@pytest.mark.slow` and document the env vars it needs).

---

## Commit hygiene

- Conventional-commit style: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`. Match what is already in `git log`.
- Atomic commits per logical unit. Rebase / squash before merging.
- Reference the design doc, weekly report, or issue when the context is non-obvious.

---

## PR checklist

- [ ] Lint, typecheck, and tests pass locally
- [ ] New code paths have tests (≥80% coverage on touched files)
- [ ] No PII anywhere (data, fixtures, screenshots, commit message)
- [ ] Design doc updated if behaviour changes (or new design doc added)
- [ ] PR description explains the *why*, not just the *what*

---

## Reporting a bug

Open a GitHub issue with:

1. The exact command you ran (`uv run poe ...`).
2. The full traceback / output.
3. The expected behaviour and what actually happened.
4. Environment: OS, Python version, `uv --version`, output of `uv pip list | grep agentic`.

If the bug involves dossier content, **redact everything** (candidate names, school names, grades) before pasting. If you cannot redact, file a private email to the maintainer instead of a public issue.

---

## Proposing a research direction

Open a GitHub issue titled `[research] <topic>`. Describe the hypothesis, the measurement that would falsify it, and the cost (compute + wall time). The maintainer will route promising directions to a design doc in `docs/plans/`.

The eight open items in [§Limitations & future work of the README](README.md#%EF%B8%8F-limitations--future-work) are good first targets.

---

## Porting this system to a different admission filière

The architecture is portable; the **content** is not. If you want to adapt this codebase to a different EPFL programme (Bachelor admission, Master in Data Science, Executive MBA, Doctoral admission) or to a non-EPFL programme entirely, here is the manifest of what to change. Section 9 of [`reports/final_report.pdf`](reports/final_report.pdf) goes through this in more detail.

### What is generic and stays as-is

| Layer | Module(s) | Why it ports for free |
|---|---|---|
| Schema-drift-tolerant Excel ingestion | `extraction/pipeline.py` | The fuzzy-header engine, multi-row grouping, and hidden-column detection are programme-agnostic. |
| PII anonymisation pipeline | `anonymizer/` | Presidio + GLiNER + post-filters + name propagation work on any text corpus. |
| Multi-agent panel scaffold | `agents/orchestrator.py`, `agents/chair.py` | The four-evaluator + Chair structure with structured JSON outputs is rubric-agnostic. |
| LLM client with retry / billing | `agents/llm_client.py` | Speaks to any OpenAI-compatible endpoint (vLLM, OpenRouter, local Llama). |
| Calibration loop & before/after diffs | `scripts/before_after_epfl.py`, `scripts/compare_committee_vs_runs.py` | The 5-run majority-vote + confusion-matrix protocol is generic. |
| Profile dataclass with validated weights | `agents/evaluation_profile.py` | Just plug in new weights summing to 1.0. |

### What must be retuned per filière

| Layer | What you change | How long it typically takes |
|---|---|---|
| **Header rules** (`extraction/pipeline.py`, `_HEADER_RULES`) | Add regex patterns for the new filière's Excel column names. | 0.5–1 day per Excel schema |
| **Allow-lists** (`anonymizer/allow_lists.py`) | Add filière-specific tokens that the anonymiser should keep (programme codes, course IDs, common school names). | 1–2 days, mostly iteration on samples |
| **Custom recognisers** (`anonymizer/recognizers.py`) | Add recognisers for filière-specific PII (e.g. visa fields for International Doctoral; legal name on Maturité certificates for Bachelor). | 1 day per recogniser |
| **Evaluator prompts** (`agents/prompts.py`) | Re-write each role's system prompt to reflect the rubric the new committee actually uses. Anchors, scoring scale, and exception blocks. | 3–5 days; this is the dominant cost |
| **Profile weights** (`agents/evaluation_profile.py`) | Define a new `EvaluationProfile` dataclass with weights tuned to the new rubric. Validation ensures sum to 1.0. | 1 day + a calibration run |
| **Decision thresholds** (`agents/chair.py`) | Composite floors (`accept`/`waitlist`/`reject`) per filière. | A few hours; tune against historical decisions |
| **Gate rules** (`agents/gpa_gate.py`) | Replace or remove the EPFL-internal three-band rule. Bachelor admission needs a Maturité grade gate; PhD admission usually has no gate. | 1–3 days depending on rule complexity |
| **Cultural calibration profile** (`calibration/`) | Build a new historical-letter corpus for the new committee; regenerate the cultural profile. | 1 week, mostly data collection |

### What is hard-coded to MTE and would need replacing entirely

1. **The EPFL-internal three-band rule** (`gpa_gate.py`, `_EPFL_INTERNAL_ACCEPT_FLOOR`, `_EPFL_INTERNAL_REJECT_FLOOR`). The 4.5 / 4.0 thresholds on algebra+analysis are the MTE committee's documented practice. Other programmes don't have this rule.
2. **The minor recommendation logic** (`agents/epfl_minor_map.py`, `agents/minor_advisor.py`). This module maps EPFL bachelors to recommended MTE minors and is meaningful only for MTE.
3. **The culture-of-letters calibration profile** (`calibration/profiler.py`). Tied to MTE's historical reference-letter pool; each programme would need to build its own.

### Worked port estimates

| Target programme | Engineering cost | Critical dependency |
|---|:---:|---|
| EPFL Bachelor admission (MTE-style rubric) | ~7 dev-days | Federal Maturité grade-conversion table |
| EPFL Master in Data Science / Computer Science | ~6 dev-days | Programme-specific motivation prompt |
| Executive MBA | ~8 dev-days | New "Career Trajectory" evaluator (5th persona) |
| Doctoral admission | ~15 dev-days | Lab-fit retrieval layer over recent papers |
| Bachelor admission cross-section (multi-canton) | ~10 dev-days | Maturité gate + multi-cantonal grade scales |

None of these estimates include the *calibration cost*: acquiring historical committee data, anonymising it, and running validation cycles. Plan an additional 2–4 weeks of wall time per new filière for calibration.

### A practical port checklist

1. [ ] **Get the data.** A minimum of 1–3 years of historical committee Excels + matching dossiers. Anonymise on a separate branch before touching anything else.
2. [ ] **Write a design doc** in `docs/plans/port-to-<filière>.md` listing every rubric difference, every PII difference, and the validation criterion.
3. [ ] **Branch the prompts.** Copy `agents/prompts.py` to a `prompts_<filière>.py` and replace the rubric content. Same for the profile dataclass.
4. [ ] **Add header rules**, then run `uv run poe extract` until the Parquet builds clean.
5. [ ] **Run the anonymiser** on a 50-file sample, hand-audit, iterate on allow-lists and recognisers until coverage is ≥99% on high-sensitivity PII.
6. [ ] **First calibration run** on a small held-out cohort. Compute agreement vs the committee. Use the disagreement classifier (Type A/B/C/D pattern) to find the *one* rule that explains most disagreement — that is your first iteration target.
7. [ ] **Falsifiable iterations.** Each prompt or rule change is a hypothesis: changing X should move candidates Y in direction Z. Re-measure on the same sub-cohort. Keep the before/after diff.
8. [ ] **Bias audit** stratified by gender, nationality, and institution category before the system goes anywhere near a real committee meeting.

The whole port is a **measure-and-close loop on a new corpus**. The codebase exists to make that loop cheap (~$2 / 6 minutes per iteration on a 28-candidate sub-cohort with Sonnet 4.6). The point is not the system — the point is the loop.

---

## Code of conduct

Be kind, be concrete, and be specific. We are here to make a measurement loop tighter — that is the only goal.
