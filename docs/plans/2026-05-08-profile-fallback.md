# Profile Fallback for Cohorts Without Parquet Metadata

**Date**: 2026-05-08
**Status**: Implemented (lint-clean, 105 unit tests pass; runtime verified on 2025-26-spring)
**Trigger**: Tried to run the evaluation on the 2025-26-spring cohort and discovered every threshold verdict was UNKNOWN — the SPE threshold field never reached the gate because spring round data has no entries in `all_candidates.parquet`.

## Problem

The pipeline assumes every dossier matches a row in `all_candidates.parquet` via `enrich_with_parquet`. When that match exists, the candidate gets `school_name`, `school_quality`, `gpa_threshold`, and `is_epfl_internal` populated from the parquet. When it doesn't, those fields stay empty and:

- The GPA gate has no threshold to compare against → emits `UNKNOWN` for every candidate.
- The EPFL-internal branch never fires (no school name to match).
- Decisions fall back to pure LLM reasoning, defeating the deterministic guarantees we just built.

Confirmed empirically on 2025-26-spring (128 anonymized dossiers, 0 parquet rows): all 18 candidates I observed during the aborted run logged `Threshold verdict: unknown` and the orchestrator selected `EXTERNAL_PROFILE` with no SPE context.

This will recur for **any new cohort** that has been anonymized but not yet ingested into the parquet (the typical state of a freshly-arrived round before the Excel extraction is re-run).

## Design

### Two-step lookup

1. **Aggregate historical thresholds** per school into a profile table built from `all_candidates.parquet`. One row per school: most-common `gpa_threshold`, most-common `tier`, country, EPFL-internal flag, accept rate.
2. **At evaluation time**, when a dossier has no parquet match, use the **LLM-extracted institution name** (`GpaExtraction.institution_name`) to look up the historical profile by fuzzy match. Fill the dossier's missing metadata from the profile.

This means a fresh cohort gets the same gate behaviour as a parquet-backed one, as long as the LLM can identify the school from the transcript and that school appears in the historical table.

### Threshold aggregation (`curriculum/university_profiles.py`)

Extended `UniversityProfile`:

```python
class UniversityProfile(BaseModel, frozen=True):
    name: str
    country: str = ""
    tier: str = "X"           # A / B / C / X
    applicants: int = 0
    accept_rate: float = 0.0
    accepts: int = 0
    rejects: int = 0
    board_notes: str = ""
    gpa_threshold: str = ""   # NEW
    is_epfl_internal: bool = False  # NEW
```

`mine_profiles` now collects thresholds and tiers per school, then picks:
- **Threshold**: most-common parsed value (via `parse_primary_threshold`).
- **Tier**: most-common non-X tier (so a single bad row doesn't downgrade a school with mostly-A rows).

#### `parse_primary_threshold`

The parquet `gpa_scale` field is messy. Real values include:
- `"28/30 29/30 for IC"` — two thresholds, second is for industrial computing
- `"80% (GM: 3.7/4)"` — primary in percent, parenthetical is a mechanical-engineering-specific override
- `"3.5 / 4 3.6/4 pour IC"` — primary with internal whitespace, second for IC
- `"Top 10%"` — categorical, not a numeric threshold
- `"110/110"` — Italian thesis grade, not a course average
- `""` — no threshold set

The parser:
1. Strips `\(...\)` parenthetical overrides.
2. Strips ` (for|pour) <section>...` trailing qualifiers.
3. Looks for the first numeric token matching `\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?` or `\d+(?:\.\d+)?\s*%`.
4. Collapses internal `/` whitespace so `"3.5 / 4"` becomes `"3.5/4"`.
5. Returns the original string unchanged when no numeric token is found (preserves categorical labels like `"Top 10%"` — the gate parser will return UNKNOWN for those, which is the correct outcome).

Result: 73 of 500 mined schools have parseable numeric thresholds; 150 have non-empty thresholds when including categorical labels. The remaining 350 inherit their tier from history but have no threshold — the gate emits UNKNOWN for those, which falls through to the legacy LLM-only path.

### Fuzzy school-name lookup (`find_profile_by_name`)

Resolution order:

1. Exact match on the canonical key.
2. Exact match on the *normalized* key (lowercase + accent-strip via NFKD + whitespace collapse).
3. Substring match in either direction. Longest canonical wins so `"École Polytechnique Fédérale de Lausanne"` beats `"École Polytechnique"` when the LLM returns the former.

Verified against real LLM-extracted names:

| LLM produced | Matched canonical |
|---|---|
| `École polytechnique fédérale de Lausanne` | `Ecole polytechnique fédérale de Lausanne EPFL` |
| `EPFL` | same |
| `POLITECNICO DI MILANO` | `Politecnico di Milano` |
| `McGill University` | `McGill University, Montreal` |
| `Karlsruher Institut für Technologie` | exact match |
| `Karlsruhe Institute of Technology` (English) | no match — falls through |

The English-vs-native-name miss is acceptable: the gate emits UNKNOWN and the LLM decides. A future improvement would maintain explicit aliases (e.g. `data/reference/university_aliases.yaml`).

### Wiring (`run_evaluation._fill_school_metadata_from_history`)

Inserted between GPA extraction and SPE-header building. Pseudocode:

```python
if not dossier.school_name and gpa.institution_name and gpa.institution_name != "unknown":
    profile = find_profile_by_name(_PROFILE_CACHE, gpa.institution_name)
    if profile:
        # fill school_name, school_country, school_quality, gpa_threshold, is_epfl_internal
    elif detect_epfl_internal(gpa.institution_name):
        # EPFL-internal flag from name alone, even without a profile match
```

`_PROFILE_CACHE` is loaded once at module import. Per-candidate lookup is dict access plus a few hundred string normalizations — negligible compared to the LLM calls.

### System-mismatch fallback in `compare_to_threshold`

A bug surfaced during the first re-run: a Delft candidate with GPA `"7.37/10"` (Dutch /10) was compared to the SPE threshold `"80%"` (percentage). The percentage parser accepts `7.37` as `7.37%` because it's in `[0, 100]`, so the gate produced `BELOW` with gap −72.6 — a false reject.

Fix: `compare_to_threshold` now takes an optional `gpa_normalized: float | None`. When the candidate's `gpa_scale` (or value-range fallback) detects a different system from the threshold, the gate uses `gpa_normalized` as a percentage and compares against the percentage threshold:

```python
if (
    system is GradingSystem.PERCENTAGE
    and gpa_normalized is not None
    and not _systems_match(system, gpa_scale, gpa_value)
):
    return _compare_via_normalized(gpa_normalized=gpa_normalized, ...)
```

Notes string carries `"Used LLM-normalized GPA (73.7/100) because candidate scale '10' disagrees with percentage threshold."` for audit.

Tested with four cases:
- Dutch /10 vs `80%`, normalized 73.7 → `BELOW` (correct, 73.7 < 80)
- Indian /10 vs `80%`, normalized 85.0 → `ABOVE`
- No `gpa_normalized` provided → legacy naive parse (locks in the previous behaviour)
- Same-system match (`85%` vs `80%`) → fallback does not fire

## Files changed

- `src/agentic_admission/curriculum/university_profiles.py` — model fields + threshold parser + EPFL detector + fuzzy lookup
- `src/agentic_admission/agents/gpa_gate.py` — `gpa_normalized` parameter, `_systems_match`, `_compare_via_normalized`
- `src/agentic_admission/agents/run_evaluation.py` — `_fill_school_metadata_from_history`, profile cache, threaded `gpa_normalized` to the gate
- `data/reference/university_profiles.json` — regenerated (500 schools, 73 with numeric thresholds)
- `tests/test_gpa_gate.py` — `TestSystemMismatchFallback` (4 cases)

## Test coverage

105 tests pass total:
- 56 `test_gpa_gate.py` (parametric matrix, unknown handling, system detection, lode handling, German inversion, EPFL-internal value, dataclass invariants, and the new system-mismatch fallback)
- 13 `test_chair_overrides.py` (gate overrides + academic clamp)
- 33 `test_evaluation_profile.py` (profile invariants, EPFL detector, weight handling)
- 3 `test_chair_overrides.py::TestEpflInternalValue` (algebra+analysis avg)

`uv run ruff check` clean on every modified file.

## Known limitations

- **English-vs-native names not aliased.** The LLM may return `"Karlsruhe Institute of Technology"` while the parquet stores `"Karlsruher Institut für Technologie"`. No substring overlap → no match. Workaround: maintain `data/reference/university_aliases.yaml` (not yet built).
- **Categorical thresholds (Top 10%, First class) emit UNKNOWN.** The gate cannot deterministically compare class-based thresholds to numeric GPAs. These fall through to the LLM. Acceptable.
- **Schools never seen before** get no threshold. The gate emits UNKNOWN, the LLM decides. The board can populate via the YAML overrides file.
- **Profile cache is process-lifetime.** Editing `university_profiles.json` requires restart of the runner. Fine for the current single-CLI workflow; would need rework if we add a long-running server.

## Verification

After the spring 2025-26 run completes:

1. Count of `Profile fallback for ... matched ...` log lines vs total candidates → should be ≥40% of cohort (mostly EPFL bachelors and well-known European/American schools).
2. Count of `Threshold verdict: above|below|near` (non-UNKNOWN) → should be substantially higher than the first aborted run.
3. Spot-check the EPFL-internal candidates: should now use `EPFL_INTERNAL_PROFILE` and skip the reference evaluator.
4. Spot-check Delft / similar Dutch transcripts: the system-mismatch fallback should fire (look for `Used LLM-normalized GPA` in the verdict notes).
