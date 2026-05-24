"""Cross-run variance statistics for the cohort evaluation pipeline.

Loads N runs of the same cohort (one directory per run) and computes:

* Per-candidate decision stability across runs.
* List of "flippers" — candidates whose decision differed across runs.
* Composite score variance per candidate.
* Per-dimension score variance (which of the 8 are most/least stable).
* EPFL-internal invariance check — the deterministic minor mapping
  must produce identical recommendations across runs.
* Aggregate accept/reject/waitlist counts per run.

Run::

    uv run python scripts/cohort_variance_stats.py \\
        --runs data/processed/runs/run01 data/processed/runs/run02 ... \\
        --output reports/cohort-variance-2026-05-09.md
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

_DIMENSIONS: tuple[str, ...] = (
    "academic_strength",
    "institution_quality",
    "reference_quality",
    "calibration_confidence",
    "motivation_clarity",
    "program_fit",
    "risk_flags",
    "consistency",
)


@dataclass(frozen=True)
class Verdict:
    candidate_id: str
    decision: str
    composite: float
    final_scores: dict[str, int]
    primary_minor: str | None


def _load_run(run_dir: Path) -> dict[str, Verdict]:
    """Read all *.json verdicts from a run directory."""
    verdicts: dict[str, Verdict] = {}
    for path in sorted(run_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        primary_minor = None
        if (mr := data.get("minor_recommendation")) is not None:
            primary_minor = mr.get("primary_minor")
        verdicts[data["candidate_id"]] = Verdict(
            candidate_id=data["candidate_id"],
            decision=data["decision"],
            composite=float(data["composite_score"]),
            final_scores={d: int(data["final_scores"].get(d, 0)) for d in _DIMENSIONS},
            primary_minor=primary_minor,
        )
    return verdicts


def _decision_stability(per_candidate: dict[str, list[str]]) -> tuple[int, int, list[str]]:
    """Return (n_stable, n_total, list_of_flippers).

    "Stable" = all runs produced the same decision.
    """
    flippers: list[str] = []
    stable = 0
    for cid, decisions in per_candidate.items():
        if len(set(decisions)) == 1:
            stable += 1
        else:
            flippers.append(cid)
    return stable, len(per_candidate), sorted(flippers)


def _composite_variance(
    per_candidate: dict[str, list[float]],
) -> list[tuple[str, float, float, float]]:
    """Return ``(cid, mean, stdev, range)`` sorted by stdev desc."""
    rows: list[tuple[str, float, float, float]] = []
    for cid, scores in per_candidate.items():
        if len(scores) < 2:
            continue
        rows.append(
            (
                cid,
                statistics.mean(scores),
                statistics.stdev(scores),
                max(scores) - min(scores),
            )
        )
    rows.sort(key=lambda r: r[2], reverse=True)
    return rows


def _per_dimension_variance(
    per_candidate_per_dim: dict[str, dict[str, list[int]]],
) -> dict[str, float]:
    """Return mean(stdev) per dimension across all candidates."""
    out: dict[str, float] = {}
    for dim in _DIMENSIONS:
        stdevs: list[float] = []
        for dims in per_candidate_per_dim.values():
            scores = dims.get(dim, [])
            if len(scores) >= 2:
                stdevs.append(statistics.stdev(scores))
        out[dim] = statistics.mean(stdevs) if stdevs else 0.0
    return out


def _epfl_invariance(
    per_candidate_minors: dict[str, list[str | None]],
    epfl_internal_ids: set[str],
) -> tuple[int, int, list[str]]:
    """For EPFL-internal candidates, verify minor recommendation is constant."""
    if not epfl_internal_ids:
        return 0, 0, []
    invariant = 0
    violators: list[str] = []
    total = 0
    for cid in epfl_internal_ids:
        minors = per_candidate_minors.get(cid, [])
        named = [m for m in minors if m]
        if not named:
            continue
        total += 1
        if len(set(named)) == 1:
            invariant += 1
        else:
            violators.append(cid)
    return invariant, total, sorted(violators)


def _aggregate_counts_per_run(runs: list[dict[str, Verdict]]) -> list[Counter[str]]:
    return [Counter(v.decision for v in r.values()) for r in runs]


def _format_md(
    runs: list[dict[str, Verdict]],
    run_names: list[str],
    epfl_internal_ids: set[str],
) -> str:
    lines: list[str] = []
    lines.append("# Cohort Variance Report — 5x Spring 2025-26\n")
    lines.append(f"_Generated from {len(runs)} runs._\n")

    # Per-candidate aggregates
    candidates = sorted(set().union(*(set(r.keys()) for r in runs)))
    decisions: dict[str, list[str]] = defaultdict(list)
    composites: dict[str, list[float]] = defaultdict(list)
    minors: dict[str, list[str | None]] = defaultdict(list)
    dims: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    coverage: dict[str, int] = defaultdict(int)

    for run in runs:
        for cid in candidates:
            v = run.get(cid)
            if v is None:
                continue
            coverage[cid] += 1
            decisions[cid].append(v.decision)
            composites[cid].append(v.composite)
            minors[cid].append(v.primary_minor)
            for dim, score in v.final_scores.items():
                dims[cid][dim].append(score)

    full_coverage = [c for c, n in coverage.items() if n == len(runs)]
    partial = [c for c, n in coverage.items() if 0 < n < len(runs)]
    missing = [c for c, n in coverage.items() if n == 0]

    # --- Coverage ---
    lines.append("## 1. Coverage\n")
    lines.append(f"- Total candidates seen across all runs: **{len(candidates)}**")
    lines.append(f"- Evaluated in *all {len(runs)}* runs: **{len(full_coverage)}**")
    lines.append(f"- Partial coverage (1..{len(runs) - 1} runs): **{len(partial)}**")
    lines.append(f"- Missing from every run: **{len(missing)}**\n")
    if partial:
        lines.append("Partial-coverage candidates (run failures):\n")
        for cid in sorted(partial):
            lines.append(f"  - `{cid}` ({coverage[cid]}/{len(runs)} runs)")
        lines.append("")

    # --- Decision stability (use full-coverage subset only) ---
    full = {c: decisions[c] for c in full_coverage}
    stable, total, flippers = _decision_stability(full)
    lines.append("## 2. Decision stability\n")
    if total > 0:
        pct = 100.0 * stable / total
        lines.append(
            f"- **{stable}/{total}** candidates ({pct:.1f}%) got the *same* decision in all "
            f"{len(runs)} runs."
        )
    lines.append(f"- **{len(flippers)}** flippers (decision changed across runs).\n")

    if flippers:
        lines.append("### Flippers — decision per run\n")
        header = "| Candidate | " + " | ".join(run_names) + " | Mode |"
        sep = "| --- |" + " --- |" * (len(run_names) + 1)
        lines.append(header)
        lines.append(sep)
        for cid in flippers:
            ds = decisions[cid]
            mode = Counter(ds).most_common(1)[0][0]
            row = f"| `{cid}` | " + " | ".join(ds) + f" | {mode} |"
            lines.append(row)
        lines.append("")

    # --- Aggregate counts per run ---
    counts = _aggregate_counts_per_run(runs)
    lines.append("## 3. Aggregate decisions per run\n")
    decisions_seen = sorted({d for c in counts for d in c})
    header = "| Run | " + " | ".join(decisions_seen) + " | Total |"
    sep = "| --- |" + " --- |" * (len(decisions_seen) + 1)
    lines.append(header)
    lines.append(sep)
    for name, c in zip(run_names, counts, strict=True):
        cells = [str(c.get(d, 0)) for d in decisions_seen]
        lines.append(f"| {name} | " + " | ".join(cells) + f" | {sum(c.values())} |")
    lines.append("")

    # --- Composite variance ---
    rows = _composite_variance({c: composites[c] for c in full_coverage})
    if rows:
        mean_stdev = statistics.mean(r[2] for r in rows)
        max_stdev = max(rows, key=lambda r: r[2])
        lines.append("## 4. Composite score variance (full-coverage candidates)\n")
        lines.append(f"- Mean per-candidate stdev: **{mean_stdev:.3f}**")
        lines.append(
            f"- Max stdev: **{max_stdev[2]:.3f}** (candidate `{max_stdev[0]}`, "
            f"mean {max_stdev[1]:.2f}, range {max_stdev[3]:.2f})\n"
        )
        lines.append("### Top 10 most-variable composites\n")
        lines.append("| Candidate | Mean | Stdev | Range |")
        lines.append("| --- | --- | --- | --- |")
        for cid, mean, stdev, rng in rows[:10]:
            lines.append(f"| `{cid}` | {mean:.2f} | {stdev:.3f} | {rng:.2f} |")
        lines.append("")

    # --- Per-dimension variance ---
    per_dim = _per_dimension_variance({c: dims[c] for c in full_coverage})
    if per_dim:
        lines.append("## 5. Per-dimension stability (mean stdev across candidates)\n")
        lines.append("| Dimension | Mean stdev |")
        lines.append("| --- | --- |")
        for dim, stdev in sorted(per_dim.items(), key=lambda kv: kv[1]):
            lines.append(f"| {dim} | {stdev:.3f} |")
        lines.append("")
        most_stable = min(per_dim.items(), key=lambda kv: kv[1])
        least_stable = max(per_dim.items(), key=lambda kv: kv[1])
        lines.append(
            f"_Most stable_: **{most_stable[0]}** ({most_stable[1]:.3f}). "
            f"_Least stable_: **{least_stable[0]}** ({least_stable[1]:.3f}).\n"
        )

    # --- EPFL invariance ---
    inv, tot, viol = _epfl_invariance(minors, epfl_internal_ids)
    lines.append("## 6. EPFL-internal minor invariance\n")
    if tot == 0:
        lines.append("_No EPFL-internal candidates with minor recommendations to check._\n")
    else:
        pct = 100.0 * inv / tot
        lines.append(
            f"- **{inv}/{tot}** EPFL-internal candidates ({pct:.1f}%) got the *same* primary "
            f"minor in every run (deterministic mapping invariant)."
        )
        if viol:
            lines.append(f"- Violators ({len(viol)}):")
            for cid in viol:
                names = [m or "(none)" for m in minors[cid]]
                lines.append(f"  - `{cid}`: {names}")
        else:
            lines.append("- No violators — deterministic mapping holds across all runs. ✓")
        lines.append("")

    # --- Footer ---
    lines.append("---\n")
    lines.append(f"_Stats computed from {len(runs)} runs across {len(full_coverage)} candidates._")
    return "\n".join(lines)


def _detect_epfl_internal_ids(runs: list[dict[str, Verdict]]) -> set[str]:
    """Heuristic: a candidate is EPFL-internal if its primary minor matches the
    deterministic mapping shape (any run shows section-default reasoning).

    Since the JSON verdict only stores ``primary_minor`` and not the
    ``is_epfl_internal`` flag, we approximate: a candidate is EPFL-internal
    when at least one run gave it a primary_minor whose name appears in our
    deterministic mapping's value set. This is a best-effort flag for the
    invariance check — false positives are harmless.
    """
    from agentic_admission.agents.epfl_minor_map import EPFL_BACHELOR_TO_MINORS

    candidate_minors = {
        name for _section, names in EPFL_BACHELOR_TO_MINORS.values() for name in names
    }
    epfl_ids: set[str] = set()
    for run in runs:
        for cid, v in run.items():
            if v.primary_minor and v.primary_minor in candidate_minors:
                epfl_ids.add(cid)
    return epfl_ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs", nargs="+", required=True, type=Path, help="One or more run directories"
    )
    parser.add_argument("--output", type=Path, required=True, help="Output Markdown path")
    args = parser.parse_args()

    runs: list[dict[str, Verdict]] = []
    run_names: list[str] = []
    for run_dir in args.runs:
        if not run_dir.is_dir():
            msg = f"Run directory not found: {run_dir}"
            raise SystemExit(msg)
        runs.append(_load_run(run_dir))
        run_names.append(run_dir.name)

    epfl_ids = _detect_epfl_internal_ids(runs)
    md = _format_md(runs, run_names, epfl_ids)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md, encoding="utf-8")
    print(f"Wrote {args.output} ({len(md.splitlines())} lines)")


if __name__ == "__main__":
    main()
