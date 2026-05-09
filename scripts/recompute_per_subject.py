"""Deterministic per-subject average from a markdown grade table.

Used as a sanity-check / fallback when the LLM-extracted
``per_subject_averages`` look suspicious. Parses the first markdown
table in the transcript that has columns ``Title`` and ``Marks`` (or
``Grade``) and groups module marks by a hard-coded subject taxonomy.

This is intentionally crude — the goal is to expose how the LLM's
output diverges from the underlying numbers, not to replace the LLM.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

# Subject taxonomy: keyword → canonical bucket. Order matters — the first
# matching keyword wins, so put more specific keywords first.
_SUBJECT_RULES: tuple[tuple[str, str], ...] = (
    ("engineering mathematics", "mathematics"),
    ("calculus", "mathematics"),
    ("linear algebra", "algebra"),
    ("algebra", "algebra"),
    ("analyse", "analysis"),
    ("analysis", "analysis"),
    ("analytical modelling", "analysis"),
    ("statistic", "statistics"),
    ("probability", "statistics"),
    ("mechanic", "mechanics"),
    ("solid mech", "mechanics"),
    ("dynamics", "mechanics"),
    ("stress", "mechanics"),
    ("thermo", "physics"),
    ("fluid", "physics"),
    ("heat transfer", "physics"),
    ("electrical", "electrical"),
    ("electronic", "electrical"),
    ("control system", "control"),
    ("control", "control"),
    ("design", "design"),
    ("manufactur", "manufacturing"),
    ("material", "materials"),
    ("computer", "computer_science"),
    ("programming", "computer_science"),
    ("software", "computer_science"),
    ("data anal", "computer_science"),
    ("information system", "computer_science"),
    ("french", "language"),
    ("english", "language"),
    ("entrepreneur", "business"),
    ("management", "business"),
    ("business", "business"),
    ("finite element", "mechanics"),
    ("instrumentation", "control"),
)


def _bucket(title: str) -> str | None:
    title_low = title.lower()
    for needle, bucket in _SUBJECT_RULES:
        if needle in title_low:
            return bucket
    return None


# Match a markdown row with a title-ish cell and a numeric Marks cell.
# The Coventry diploma supplement table looks like:
#   |    1 | 101MMS | Engineering Mathematics 1 | 4 | 86 | P | 1 | 20 | 10 |
_ROW_RE = re.compile(
    r"^\|[^|]*\|[^|]*\|\s*([^|]+?)\s*\|[^|]*\|\s*(\d{1,3})\s*\|",
    re.MULTILINE,
)


def parse_marks(transcript: str) -> list[tuple[str, int, str | None]]:
    """Return ``(title, mark, bucket)`` for every parsed row."""
    out: list[tuple[str, int, str | None]] = []
    for match in _ROW_RE.finditer(transcript):
        title = match.group(1).strip()
        try:
            mark = int(match.group(2))
        except ValueError:
            continue
        if not (0 <= mark <= 100):
            continue
        out.append((title, mark, _bucket(title)))
    return out


def per_subject_averages(rows: list[tuple[str, int, str | None]]) -> dict[str, float]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for _title, mark, bucket in rows:
        if bucket is None:
            continue
        grouped[bucket].append(mark)
    return {k: round(sum(v) / len(v), 2) for k, v in grouped.items()}


def overall_average(rows: list[tuple[str, int, str | None]]) -> float:
    if not rows:
        return 0.0
    return round(sum(r[1] for r in rows) / len(rows), 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path)
    args = parser.parse_args()

    text = args.transcript.read_text(encoding="utf-8")
    rows = parse_marks(text)

    if not rows:
        print("No mark rows parsed — table format unrecognised.")
        return

    print(f"=== {len(rows)} module rows parsed ===")
    for title, mark, bucket in rows:
        bucket_label = bucket if bucket is not None else "(uncategorised)"
        print(f"  {mark:>3}  {title:<55}  [{bucket_label}]")

    print()
    print(f"Overall average: {overall_average(rows):.2f}")
    print()
    print("Per-subject averages:")
    for subj, avg in sorted(per_subject_averages(rows).items()):
        n = sum(1 for r in rows if r[2] == subj)
        print(f"  {subj:<18}  {avg:>6.2f}  (n={n})")


if __name__ == "__main__":
    main()
