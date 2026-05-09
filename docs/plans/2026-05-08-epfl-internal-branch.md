# EPFL-Internal Evaluation Branch

**Date**: 2026-05-08
**Status**: Implemented (lint-clean, 33 unit tests pass)
**Trigger**: Admission committee meeting 2026-05-08 — committee flagged that the agent treats EPFL-internal candidates the same as external applicants and the resulting reference scores tank composites for candidates the committee actually wants to consider.

## Problem

The orchestrator runs the same 4-evaluator panel on every dossier, regardless of cohort. For EPFL bachelors transferring into MTE this is wrong on two counts:

1. **EPFL-internal candidates rarely submit reference letters.** Sample of 5 internal dossiers from `2020-21-fall`:

   | Dossier | Reference letters? | Total documents |
   |---|---|---|
   | `47638af6fe7a` | none | 6 |
   | `5c2eb654a2f5` | 2–3 referents | 9 |
   | `3e959371b46e` | none | 4 |
   | `8bea76005f77` | none | 4 |
   | `73ce95cebcce` | none | 5 |

   4 of 5 had no Referent folders at all. The Reference Evaluator was running on empty input, returning `reference_quality=1` and `calibration_confidence=1`, and pulling the composite down by ~25% (combined weight) for candidates the committee discusses based on transcript and motivation alone.

2. **The committee's actual rule for internals is different.** From the 2026-05-08 unofficial guidelines: the threshold for internals is the **algebra + analysis** average against 4.5 (default) / 4.0 (if the candidate switched bachelor section) — not overall GPA, not institution ranking, and not letters.

Secondary issue surfaced while implementing: the previous global scoring weights summed to **0.85**, capping the composite at 8.5/10. Fixed in this branch.

## Design

### Strategy pattern: per-cohort `EvaluationProfile`

New module `src/agentic_admission/agents/evaluation_profile.py` introduces a frozen `EvaluationProfile` dataclass with construction-time invariant checks:

- All 8 dimensions present.
- All weights in `[0, 1]`.
- Sum within `1e-6` of `1.0`.
- If `skip_reference=True`, both reference dimensions must carry weight 0.
- Weights stored as a `MappingProxyType` so consumers cannot mutate them.

Two singletons exported:

```python
EXTERNAL_PROFILE = EvaluationProfile(
    name="external",
    weights={
        "academic_strength":     0.30,
        "institution_quality":   0.18,
        "reference_quality":     0.18,
        "calibration_confidence":0.12,
        "motivation_clarity":    0.06,
        "program_fit":           0.06,
        "risk_flags":            0.05,
        "consistency":           0.05,
    },
    skip_reference=False,
)

EPFL_INTERNAL_PROFILE = EvaluationProfile(
    name="epfl_internal",
    weights={
        "academic_strength":     0.45,  # ↑ committee uses this almost exclusively
        "institution_quality":   0.10,  # ↓ fixed at EPFL — low information
        "reference_quality":     0.0,
        "calibration_confidence":0.0,
        "motivation_clarity":    0.15,  # ↑ remaining differentiator
        "program_fit":           0.15,  # ↑ remaining differentiator
        "risk_flags":            0.075,
        "consistency":           0.075,
    },
    skip_reference=True,
)
```

Both sum to 1.0 (verified at construction and by `test_builtin_profiles_sum_to_one`).

A helper `renormalize_without_reference(profile)` returns a copy with reference weights zeroed and the remainder rescaled — used when an *external* candidate happens to submit no letters at all.

### Detection (`dossier_loader.py`)

Two pure helpers, both unit-tested:

```python
def detect_epfl_internal(school_name: str) -> bool: ...
def has_meaningful_letters(letters_text: str) -> bool: ...
```

Detection is name-based (the parquet `school_name` field), not letter-presence-based: a small minority of EPFL-internal candidates do submit letters, but the committee still scores them under internal rules. Six known name patterns, lowercased substring match. False-positive set tested explicitly (`ETH Zurich`, `Polytechnique Montréal`, `Politecnico di Milano`, French rendering of ETH).

`MIN_MEANINGFUL_LETTERS_LENGTH = 500` chars (stripped) is the cutoff for "letter present". OCR sometimes captures only headers from a template letter file — the cutoff filters those out.

`DossierContent.is_epfl_internal: bool` is set in `enrich_with_parquet` and threaded through `evaluate_candidate(..., is_epfl_internal=...)`.

### Orchestrator branching

`_select_profile(*, is_epfl_internal, has_letters)` returns `(profile, skip_reason)` where `skip_reason` is the audit string included in the sentinel scorecard when reference is skipped. Three cases:

| Internal? | Letters? | Profile | Skip reason |
|---|---|---|---|
| ✓ | * | `EPFL_INTERNAL_PROFILE` | `"EPFL-internal candidate: letters not required"` |
| ✗ | ✓ | `EXTERNAL_PROFILE` | `None` |
| ✗ | ✗ | `renormalize_without_reference(EXTERNAL_PROFILE)` | `"External candidate but no recommendation letters submitted"` |

`_build_reference_task(...)` returns either the live `evaluate_reference` coroutine or a sentinel coroutine producing `make_skipped_reference_scorecard(reason)`. This keeps `evaluate_candidate` below the lint complexity threshold and isolates the branch in one testable place.

### Sentinel reference scorecard

`chair.make_skipped_reference_scorecard(reason)` builds an `AgentScorecard(role=REFERENCE)` with both dimension scores at 1 (the schema's minimum, since `AgentScorecard` validates 1–10) and structured `DimensionJustification(cons=("Skipped: <reason>",))`. The Chair's user prompt is augmented when `profile.skip_reference` is true:

> IMPORTANT: This candidate's reference dimensions are zero-weighted (no/insufficient recommendation letters submitted). Do NOT lower the recommendation because reference scores are 1 — the Reference scorecard is a sentinel placeholder.

This prevents the Chair from re-amplifying a sentinel reference score back into the verdict via the `decision` field.

### Composite computation

`compute_composite(final_scores, *, weights=None)` now takes an explicit weights mapping. Default is `EXTERNAL_PROFILE.weights`. `synthesize` accepts a `profile: EvaluationProfile = EXTERNAL_PROFILE` parameter and threads `profile.weights` into `compute_composite`. Logs include the profile name for audit trails.

### Academic Evaluator prompt extension

`_EPFL_INTERNAL_BLOCK` appended to the Academic Evaluator prompt explicitly tells the LLM:

- Use **algebra + analysis** average for EPFL-internal candidates, not overall GPA.
- Threshold: 4.5/6 normal, 4.0/6 for section-switchers.
- Detect mise-à-niveau patterns by reading the transcript chronologically.
- Convert advanced-class scale (~3.4 advanced ≈ 4.9 standard).

This addresses the Max Grover (#102) failure mode from the meeting where the agent rejected on raw average without seeing the trajectory.

## Files changed

- **New** `src/agentic_admission/agents/evaluation_profile.py` (190 lines)
- **New** `tests/test_evaluation_profile.py` (33 unit tests)
- **New** `docs/unofficial-guidelines.md` — committee rules captured from the meeting
- `src/agentic_admission/agents/dossier_loader.py` — `detect_epfl_internal`, `has_meaningful_letters`, `is_epfl_internal` field on `DossierContent`, wired in `enrich_with_parquet`.
- `src/agentic_admission/agents/orchestrator.py` — `_select_profile`, `_build_reference_task`, profile threading.
- `src/agentic_admission/agents/chair.py` — `make_skipped_reference_scorecard`, `compute_composite(weights=...)`, profile-aware synthesis prompt.
- `src/agentic_admission/agents/prompts.py` — `_EPFL_INTERNAL_BLOCK` appended to the Academic prompt.
- `src/agentic_admission/agents/run_evaluation.py` — passes `is_epfl_internal=dossier.is_epfl_internal` through.

## Test coverage

`tests/test_evaluation_profile.py` — 33 tests across 6 test classes:

- **TestEvaluationProfile** (10): weight-sum invariant, missing/unknown dimension rejection, negative weight rejection, `skip_reference` consistency, `MappingProxyType` immutability, `FrozenInstanceError` on field reassignment.
- **TestSelectProfile** (2): identity returns of the right singleton.
- **TestRenormalize** (4): sum-to-one after zeroing reference, ordering preservation, idempotent for already-skipped profiles.
- **TestEpflDetector** (11 parametrized): 5 EPFL name variants accepted, 6 confounders rejected (ETH, Polytechnique Paris, Polytechnique Montréal, Politecnico di Milano, French rendering of ETH, empty string).
- **TestMeaningfulLetters** (3): short/empty/whitespace below cutoff, long content above.
- **TestComputeComposite** (3): default weights, internal-profile reference zeroing, range clamping.

All 33 pass. `uv run ruff check` clean on every modified file.

## What this does NOT fix

Deferred to a follow-up branch (see `docs/plans/...` to be filed):

- **Deterministic GPA threshold gate.** The threshold comparison is still LLM-driven through prompt instructions. The next branch will add `agents/gpa_gate.py` with per-grading-system parsers, structured `THRESHOLD_VERDICT: BELOW/NEAR/ABOVE` injection, and a programmatic clamp on `academic_strength` after Phase 1.
- **GPA confidence gating.** `GpaExtraction.confidence` is computed but not consumed downstream. Next branch will route low-confidence dossiers to `WAITLIST` instead of accept/reject.
- **Italian grading system support.** The `gpa_extractor.py` prompt still has no Italian (18–30 / 30 e lode) rules and no awareness of retake-inflation. Bologna 28 vs Sapienza 29 is invisible.
- **Per-subject GPA extraction for internals.** The Academic Evaluator now knows to use algebra + analysis, but the structured `GpaExtraction` model still returns one flat number. Adding `per_subject_averages: dict[str, float]` would let us apply the 4.5 / 4.0 threshold deterministically.
- **Web-research tooling (Perplexity).** Discussed; not implemented in this branch. The right shape is (a) a once-per-cohort enrichment job populating `university_profiles.parquet`, plus (b) on-demand verification of specific claims (awards, letter-writer titles) gated by Devil's-Advocate flags. Not yet built.

## Backtesting plan

The `print_comparison_table` in `run_evaluation.py` already produces an agent-vs-committee match rate. Once this branch is merged, the next step is:

1. Re-evaluate the historical EPFL-internal dossiers (`school_name` matches detector, `decision_final` non-empty) under the new profile.
2. Compare the composite score distribution before/after the change (expected: ~+1.5 points on average for EPFL-internal candidates due to removing the reference drag).
3. Compare per-decision agreement (`accept` vs `reject` vs `waitlist`) before/after.
4. Spot-check the 4 / 5 sample candidates above to confirm none flip from `accept` to `reject` or vice-versa for surprising reasons.

The agreement number is the single best calibration signal; if it drops, the profile weights were misconfigured.
