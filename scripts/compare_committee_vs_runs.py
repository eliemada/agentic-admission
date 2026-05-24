"""Compare committee final decisions vs system 5-run verdicts for Spring 2025-26.

Inputs:
* Committee Excel: ``MTE admission commission 2nd round_Spring26.xlsx``
* System runs: ``data/processed/runs/run01..run05/`` (5 verdicts per candidate)

Outputs:
* Markdown report at the path passed as ``--output``.

Maps Excel candidate names → anonymized hashed folders via
``data/processed/anonymized/path_mapping.parquet``. Two known
disambiguation cases are hardcoded (two candidates named "Kim", one
hyphenated last name).
"""

from __future__ import annotations

import argparse
import json
import statistics
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
import pyarrow.parquet as pq


@dataclass
class _RunStack:
    decisions: list[str] = field(default_factory=list)
    composites: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class _CandidateRow:
    name: str
    hash: str
    country: str
    school: str
    committee: str
    decisions: tuple[str, ...]
    composites: tuple[float, ...]
    mode: str
    agree_runs: int
    mean_composite: float
    stdev_composite: float

# Hardcoded disambiguations for cases the heuristic matcher gets wrong.
_NAME_OVERRIDES: dict[str, str] = {
    "Kim Seung Hyun": "26ae784d194a",  # Korean (Kongju National University)
    "Kim Seyoung": "6509240fe849",      # EPFL Informatique bachelor
    "Pacher-Theinburg Clemens Aurel Hugo": "76cc8938ce8f",
}

# Map committee shorthand to our internal decision vocabulary.
_COMMITTEE_DECISION_MAP: dict[str, str] = {
    "OK": "accept",
    "NO": "reject",
    "A discuter": "waitlist",
    "A DISCUTER": "waitlist",
    "DISCUSS": "waitlist",
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _build_name_to_hash() -> dict[str, str]:
    t = pq.read_table("data/processed/anonymized/path_mapping.parquet").to_pandas()
    spring = t[t["original_path"].str.startswith("2025-26-spring/")]
    out: dict[str, str] = {}
    for _, row in spring.iterrows():
        orig_parts = row["original_path"].split("/")
        anon_parts = row["anonymized_path"].split("/")
        if len(orig_parts) >= 2 and len(anon_parts) >= 2:
            out[orig_parts[1].lower()] = anon_parts[1]
    return out


def _resolve_hash(full_name: str, name_to_hash: dict[str, str]) -> str | None:
    if full_name in _NAME_OVERRIDES:
        return _NAME_OVERRIDES[full_name]
    tokens = [_strip_accents(t.lower()) for t in full_name.split()]
    # Try increasing prefix joined as `_` first, then `-`.
    for sep in ("_", "-"):
        for n in range(min(len(tokens), 4), 0, -1):
            key = sep.join(tokens[:n])
            if key in name_to_hash:
                return name_to_hash[key]
    for t in tokens:
        if t in name_to_hash:
            return name_to_hash[t]
    return None


def _parse_committee_excel(xl_path: Path) -> list[dict[str, object]]:
    wb = openpyxl.load_workbook(xl_path, data_only=True)
    ws = wb.active
    candidates: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        if row[0] is not None and row[1]:
            if current:
                candidates.append(current)
            current = {
                "no": row[0],
                "name": row[1],
                "country": row[2],
                "school": row[3],
                "quality": row[4],
                "decision_section": row[-1],
            }
    if current:
        candidates.append(current)
    return candidates


def _load_runs(run_dirs: list[Path]) -> dict[str, _RunStack]:
    """Load all verdicts. Returns ``{candidate_id: _RunStack}``."""
    out: dict[str, _RunStack] = defaultdict(_RunStack)
    for rd in run_dirs:
        for path in sorted(rd.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            cid = data["candidate_id"]
            out[cid].decisions.append(data["decision"])
            out[cid].composites.append(float(data["composite_score"]))
    return out


def _normalize_committee(raw: object) -> str:
    s = str(raw or "").strip()
    return _COMMITTEE_DECISION_MAP.get(s.upper(), "unknown")


def _format_md(
    candidates: list[dict[str, object]],
    name_to_hash: dict[str, str],
    runs: dict[str, _RunStack],
    n_runs: int,
) -> str:
    lines: list[str] = ["# Committee vs system — Spring 2025-26 (5 runs)\n"]

    rows: list[_CandidateRow] = []
    unmatched: list[str] = []
    no_verdict: list[str] = []
    for c in candidates:
        h = _resolve_hash(str(c["name"]), name_to_hash)
        if h is None:
            unmatched.append(str(c["name"]))
            continue
        cid = f"2025-26-spring_{h}"
        verdicts = runs.get(cid)
        if not verdicts or not verdicts.decisions:
            no_verdict.append(str(c["name"]))
            continue
        committee = _normalize_committee(c["decision_section"])
        decisions = verdicts.decisions
        composites = verdicts.composites
        mode = Counter(decisions).most_common(1)[0][0]
        agree_runs = sum(1 for d in decisions if d == committee)
        rows.append(
            _CandidateRow(
                name=str(c["name"]),
                hash=h,
                country=str(c["country"] or ""),
                school=str(c["school"] or ""),
                committee=committee,
                decisions=tuple(decisions),
                composites=tuple(composites),
                mode=mode,
                agree_runs=agree_runs,
                mean_composite=statistics.mean(composites),
                stdev_composite=(
                    statistics.stdev(composites) if len(composites) >= 2 else 0.0
                ),
            ),
        )

    # --- Coverage ---
    lines.append("## 1. Coverage\n")
    lines.append(f"- Committee Excel candidates: **{len(candidates)}**")
    lines.append(f"- Matched to anonymized verdicts: **{len(rows)}**")
    if unmatched:
        lines.append(f"- Unmatched names ({len(unmatched)}): {unmatched}")
    if no_verdict:
        lines.append(f"- Matched but no system verdict ({len(no_verdict)}): {no_verdict}")
    lines.append("")

    # --- Aggregate counts ---
    committee_counts = Counter(r.committee for r in rows)
    mode_counts = Counter(r.mode for r in rows)
    lines.append("## 2. Aggregate counts\n")
    lines.append("| Source | accept | reject | waitlist | total |")
    lines.append("| --- | --- | --- | --- | --- |")
    lines.append(
        f"| Committee | {committee_counts.get('accept', 0)} | "
        f"{committee_counts.get('reject', 0)} | "
        f"{committee_counts.get('waitlist', 0)} | {sum(committee_counts.values())} |"
    )
    lines.append(
        f"| System (mode of {n_runs}) | {mode_counts.get('accept', 0)} | "
        f"{mode_counts.get('reject', 0)} | "
        f"{mode_counts.get('waitlist', 0)} | {sum(mode_counts.values())} |"
    )
    lines.append("")

    # --- Confusion matrix (committee × system mode) ---
    matrix: dict[tuple[str, str], int] = defaultdict(int)
    for r in rows:
        matrix[(r.committee, r.mode)] += 1
    syslabels = ["accept", "waitlist", "reject"]
    lines.append("## 3. Confusion matrix — Committee (rows) × System mode (cols)\n")
    lines.append("| | " + " | ".join(syslabels) + " | total |")
    lines.append("| --- |" + " --- |" * (len(syslabels) + 1))
    for c in syslabels:
        cells = [str(matrix.get((c, s), 0)) for s in syslabels]
        total = sum(matrix.get((c, s), 0) for s in syslabels)
        lines.append(f"| **{c}** | " + " | ".join(cells) + f" | {total} |")
    lines.append("")

    # --- Agreement ---
    full_agree = sum(1 for r in rows if r.committee == r.mode)
    n = len(rows)
    pct = 100.0 * full_agree / n if n else 0
    lines.append("## 4. Agreement (committee vs system mode)\n")
    lines.append(f"- Mode agrees with committee: **{full_agree}/{n}** ({pct:.1f}%)")
    lines.append(
        f"- Disagreements: **{n - full_agree}/{n}** "
        f"({100 - pct:.1f}%)\n",
    )

    # --- Disagreements grouped ---
    disagreements = [r for r in rows if r.committee != r.mode]
    grouped: dict[tuple[str, str], list[_CandidateRow]] = defaultdict(list)
    for r in disagreements:
        grouped[(r.committee, r.mode)].append(r)

    lines.append("## 5. Disagreement breakdown\n")
    for (com, sys), items in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        lines.append(
            f"### Committee = **{com}** | System mode = **{sys}** ({len(items)} cases)\n",
        )
        lines.append(
            "| Name | Country | School | Mean comp | Stdev | Per-run decisions |",
        )
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for r in sorted(items, key=lambda x: -x.mean_composite):
            decs = " · ".join(r.decisions)
            lines.append(
                f"| {r.name} | {r.country} | {r.school} | "
                f"{r.mean_composite:.2f} | {r.stdev_composite:.2f} | {decs} |",
            )
        lines.append("")

    # --- Borderline cases (always disagreeing but composite near boundary) ---
    near_8 = [r for r in disagreements if 7.0 <= r.mean_composite < 8.5]
    if near_8:
        lines.append("## 6. Disagreements near composite boundary (7.0 ≤ mean < 8.5)\n")
        lines.append(
            f"_{len(near_8)} cases — these are the ones where seuil-tweaking might flip._\n",
        )

    # --- Footer ---
    lines.append("---\n")
    lines.append(
        f"_Generated from {n_runs} runs across {n} matched candidates of "
        f"{len(candidates)} committee entries._",
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel", type=Path, required=True)
    parser.add_argument("--runs", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    name_to_hash = _build_name_to_hash()
    candidates = _parse_committee_excel(args.excel)
    runs = _load_runs(args.runs)

    md = _format_md(candidates, name_to_hash, runs, n_runs=len(args.runs))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md, encoding="utf-8")
    print(f"Wrote {args.output} ({len(md.splitlines())} lines)")


if __name__ == "__main__":
    main()
