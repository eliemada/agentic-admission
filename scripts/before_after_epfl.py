"""Before/after comparison for the EPFL-internal prompt fix.

Loads the pre-fix 5 runs (data/processed/runs/run01..05) and post-fix
5 runs (data/processed/runs_postfix/run01..05) for the 28 EPFL-internal
candidates, then prints a per-candidate table showing decision shift,
composite shift, and committee match.

Run::

    uv run python scripts/before_after_epfl.py
"""

from __future__ import annotations

import argparse
import json
import statistics
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import openpyxl
import pyarrow.parquet as pq

_EPFL_HASHES: tuple[str, ...] = (
    "03f04df5270c",
    "04db248bd130",
    "16e8bbe0c623",
    "197a4a37be28",
    "395d50e5cc7d",
    "3e6f13cc2a98",
    "40e9ebcdde2c",
    "4d85b1bfa647",
    "5145dbcf0585",
    "5a65cc3ccc13",
    "6509240fe849",
    "6b91633db1da",
    "7573473ad40c",
    "800d73d4404c",
    "82ddf06044ac",
    "8655be1be89d",
    "8b296c88c36a",
    "8f5f3cc44828",
    "914281699b49",
    "99827b87624a",
    "ab7146ae20e9",
    "b932dc01c73a",
    "c8a8e2176664",
    "ceeedf663cd8",
    "d18ab8318eef",
    "d8a8b2b00d0b",
    "e3966f748a69",
    "f4c248134fc9",
)

_NAME_OVERRIDES: dict[str, str] = {
    "Kim Seyoung": "6509240fe849"  # EPFL Informatique
}


@dataclass(frozen=True)
class _Stats:
    decisions: tuple[str, ...]
    composites: tuple[float, ...]

    @property
    def mode(self) -> str:
        return Counter(self.decisions).most_common(1)[0][0]

    @property
    def mean_composite(self) -> float:
        return statistics.mean(self.composites) if self.composites else 0.0


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _build_hash_to_name(excel_path: Path) -> dict[str, tuple[str, str]]:
    """Return {hash: (name, committee_decision)} for the EPFL-internals."""
    t = pq.read_table("data/processed/anonymized/path_mapping.parquet").to_pandas()
    spring = t[t["original_path"].str.startswith("2025-26-spring/")]
    name_to_hash: dict[str, str] = {}
    for _, row in spring.iterrows():
        orig_parts = row["original_path"].split("/")
        anon_parts = row["anonymized_path"].split("/")
        name_to_hash[orig_parts[1].lower()] = anon_parts[1]

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb.active
    hash_to_info: dict[str, tuple[str, str]] = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0 or not row[0] or not row[1]:
            continue
        name, decision = str(row[1]), str(row[-1] or "").strip().upper()
        decision_norm = {"OK": "accept", "NO": "reject"}.get(decision, "unknown")

        if name in _NAME_OVERRIDES:
            h = _NAME_OVERRIDES[name]
        else:
            tokens = [_strip_accents(t.lower()) for t in name.split()]
            h = None
            for sep in ("_", "-"):
                for n in range(min(len(tokens), 4), 0, -1):
                    key = sep.join(tokens[:n])
                    if key in name_to_hash:
                        h = name_to_hash[key]
                        break
                if h:
                    break
            if h is None:
                continue
        if h in _EPFL_HASHES:
            hash_to_info[h] = (name, decision_norm)
    return hash_to_info


def _load_runs(run_dirs: list[Path]) -> dict[str, _Stats]:
    decisions: dict[str, list[str]] = {h: [] for h in _EPFL_HASHES}
    composites: dict[str, list[float]] = {h: [] for h in _EPFL_HASHES}
    for rd in run_dirs:
        for path in sorted(rd.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            cid = data["candidate_id"]
            h = cid.split("_", 1)[1] if "_" in cid else cid
            if h in decisions:
                decisions[h].append(data["decision"])
                composites[h].append(float(data["composite_score"]))
    return {h: _Stats(tuple(decisions[h]), tuple(composites[h])) for h in _EPFL_HASHES}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--excel",
        type=Path,
        default=Path("/Users/eliebruno/Desktop/MTE admission commission 2nd round_Spring26.xlsx"),
    )
    p.add_argument(
        "--pre-runs",
        nargs="+",
        type=Path,
        default=[Path(f"data/processed/runs/run{i:02d}") for i in range(1, 6)],
    )
    p.add_argument(
        "--post-runs",
        nargs="+",
        type=Path,
        default=[Path(f"data/processed/runs_postfix/run{i:02d}") for i in range(1, 6)],
    )
    p.add_argument(
        "--output", type=Path, default=Path("reports/calibration/epfl-internal-fix-before-after.md")
    )
    args = p.parse_args()

    info = _build_hash_to_name(args.excel)
    pre = _load_runs(args.pre_runs)
    post = _load_runs(args.post_runs)

    lines: list[str] = ["# EPFL-internal prompt fix: before vs after\n"]
    lines.append(
        "_28 EPFL-internal candidates from Spring 2025-26, 5 runs each, "
        "before vs after the prompt change clarifying that MTE applies the "
        "section-switcher 4.0 threshold (not 4.5)._\n"
    )

    rows: list[tuple[str, str, str, str, float, float, str]] = []
    for h in _EPFL_HASHES:
        if h not in info:
            continue
        name, committee = info[h]
        pre_s, post_s = pre[h], post[h]
        if not pre_s.decisions or not post_s.decisions:
            continue
        rows.append(
            (
                h,
                name,
                committee,
                pre_s.mode,
                pre_s.mean_composite,
                post_s.mean_composite,
                post_s.mode,
            )
        )

    # Aggregates
    pre_modes = Counter(r[3] for r in rows)
    post_modes = Counter(r[6] for r in rows)
    committee_counts = Counter(r[2] for r in rows)
    pre_agree = sum(1 for r in rows if r[3] == r[2])
    post_agree = sum(1 for r in rows if r[6] == r[2])

    lines.append("## Aggregate counts on the 28 EPFL-internals\n")
    lines.append("| Source | accept | reject | waitlist | agree with committee |")
    lines.append("| --- | --- | --- | --- | --- |")
    lines.append(
        f"| Committee | {committee_counts.get('accept', 0)} | "
        f"{committee_counts.get('reject', 0)} | 0 | — |"
    )
    lines.append(
        f"| System BEFORE (mode) | {pre_modes.get('accept', 0)} | "
        f"{pre_modes.get('reject', 0)} | {pre_modes.get('waitlist', 0)} | "
        f"**{pre_agree}/{len(rows)}** ({100 * pre_agree / len(rows):.0f}%) |"
    )
    lines.append(
        f"| System AFTER (mode) | {post_modes.get('accept', 0)} | "
        f"{post_modes.get('reject', 0)} | {post_modes.get('waitlist', 0)} | "
        f"**{post_agree}/{len(rows)}** ({100 * post_agree / len(rows):.0f}%) |"
    )
    lines.append("")

    lines.append("## Per-candidate before / after\n")
    lines.append("| Name | Committee | Before | Comp B | Comp A | After | Δcomp | Δdecision |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for _h, name, committee, pre_mode, pre_comp, post_comp, post_mode in sorted(
        rows, key=lambda r: (r[2] != "accept", r[3], -r[5])
    ):
        delta = post_comp - pre_comp
        flip = "→" if pre_mode == post_mode else "**FLIP**"
        agree_pre = "✓" if pre_mode == committee else " "
        agree_post = "✓" if post_mode == committee else " "
        lines.append(
            f"| {name} | {committee} | {pre_mode} {agree_pre} | "
            f"{pre_comp:.2f} | {post_comp:.2f} | {post_mode} {agree_post} | "
            f"{delta:+.2f} | {flip} |"
        )
    lines.append("")

    # Disagreement-resolved summary
    fixed = [r for r in rows if r[3] != r[2] and r[6] == r[2]]
    broken = [r for r in rows if r[3] == r[2] and r[6] != r[2]]
    still_wrong = [r for r in rows if r[3] != r[2] and r[6] != r[2]]
    lines.append("## Outcome\n")
    lines.append(f"- **Disagreements fixed by the prompt change:** {len(fixed)}")
    if fixed:
        for r in fixed:
            lines.append(f"  - {r[1]}: {r[3]} → {r[6]} (committee={r[2]})")
    lines.append(f"- **Newly introduced disagreements (regressions):** {len(broken)}")
    if broken:
        for r in broken:
            lines.append(f"  - {r[1]}: {r[3]} → {r[6]} (committee={r[2]})")
    lines.append(f"- **Still disagreeing after fix:** {len(still_wrong)}")
    if still_wrong:
        for r in still_wrong:
            lines.append(f"  - {r[1]}: {r[3]} → {r[6]} (committee={r[2]})")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.output} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
