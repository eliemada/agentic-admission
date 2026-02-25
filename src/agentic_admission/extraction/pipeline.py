"""Extract and normalize MTE admission Excel files into Parquet.

Handles the heterogeneous column layouts across 6 years of admission data,
groups multi-row candidate records (one row per committee member), and
writes a single normalized Parquet file.

Run standalone
--------------
.. code-block:: bash

    uv run python -m agentic_admission.extraction.pipeline
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger
from openpyxl import load_workbook

from agentic_admission.models.candidate import CandidateRecord

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DATA_RAW = Path("data/raw/applications")
_DATA_OUT = Path("data/processed/all_candidates.parquet")

# Canonical field names for candidate info columns.  Each entry maps a
# search substring (applied to *normalised* headers) to the field name.
# Order matters: first match wins.
_HEADER_RULES: list[tuple[str, str]] = [
    ("nom", "name"),
    ("pays", "school_country"),
    ("ecole de provenance", "school_name"),
    ("qualit", "school_quality"),
    ("remarques spe", "spe_remarks"),
    ("remarques   spe", "spe_remarks"),
    ("remarques  spe", "spe_remarks"),
    ("gpa min", "gpa_scale"),
    ("niveau", "study_level"),
    ("gpa cand", "gpa_candidate"),
    ("gpa  cand", "gpa_candidate"),
    ("note max", "gpa_max"),
    ("note  max", "gpa_max"),
    ("gender", "gender"),
]

_EVAL_TRIPLET_MIN = 3
_EVAL_PAIR_MIN = 2
_HIDDEN_GENDER_COL = 2


# ---------------------------------------------------------------------------
# Header normalisation helpers
# ---------------------------------------------------------------------------


def _norm(raw: str | None) -> str:
    """Lowercase, strip, and collapse internal whitespace."""
    if raw is None:
        return ""
    return " ".join(str(raw).lower().strip().split())


def _cell(value: Any) -> str:
    """Convert an openpyxl cell value to a trimmed string."""
    if value is None:
        return ""
    return str(value).strip()


def _safe_cell(row: list[Any], idx: int | None) -> str:
    """Safely read a cell value from a row by index."""
    if idx is None or idx >= len(row):
        return ""
    return _cell(row[idx])


# ---------------------------------------------------------------------------
# Column mapping (split into sub-functions to reduce complexity)
# ---------------------------------------------------------------------------


def _find_candidate_number(normed: list[str]) -> tuple[int, set[int]]:
    """Locate the candidate number column.

    Returns
    -------
    tuple[int, set[int]]
        ``(column_index, {column_index})``
    """
    for i, h in enumerate(normed):
        if h in ("no", "no.", "no "):
            return i, {i}
    return 0, {0}


def _match_header_patterns(
    normed: list[str],
    used: set[int],
) -> tuple[dict[str, int], set[int]]:
    """Apply ``_HEADER_RULES`` to identify candidate-info columns.

    Returns
    -------
    tuple[dict[str, int], set[int]]
        ``(mapping, updated_used)``
    """
    mapping: dict[str, int] = {}
    assigned: set[str] = set()
    new_used = set(used)

    for i, h in enumerate(normed):
        if i in new_used or not h:
            continue
        for pattern, field in _HEADER_RULES:
            if field in assigned:
                continue
            if pattern in h:
                mapping[field] = i
                new_used.add(i)
                assigned.add(field)
                break

    return mapping, new_used


def _match_decision_columns(
    normed: list[str],
    used: set[int],
) -> tuple[dict[str, int], set[int]]:
    """Identify aggregate decision columns (order-dependent).

    Returns
    -------
    tuple[dict[str, int], set[int]]
        ``(mapping, updated_used)``
    """
    mapping: dict[str, int] = {}
    new_used = set(used)
    generic_idx = 0
    generic_order = ["decision_section", "decision_permanent_member", "decision_final"]

    for i, h in enumerate(normed):
        if i in new_used:
            continue
        if "décision" not in h and "decision" not in h:
            continue
        if "finale" in h:
            mapping["decision_final"] = i
        elif "membre" in h or "permanent" in h:
            mapping["decision_permanent_member"] = i
        elif "proposition" not in h and generic_idx < len(generic_order):
            mapping[generic_order[generic_idx]] = i
            generic_idx += 1
        new_used.add(i)

    return mapping, new_used


def _find_evaluator_triplet(
    headers: list[str],
    used: set[int],
    mapping: dict[str, int],
) -> dict[str, int]:
    """Locate the evaluator triplet (initials, decision, comment).

    The triplet sits between the last GPA column and the aggregate
    decision columns.

    Returns
    -------
    dict[str, int]
        Internal keys ``_eval_initials``, ``_eval_decision``,
        ``_eval_comment``.
    """
    last_info_col = max(
        mapping.get("gpa_max", 0),
        mapping.get("gpa_candidate", 0),
        mapping.get("gpa_scale", 0),
    )
    candidates = [
        i for i in range(last_info_col + 1, len(headers)) if i not in used
    ]
    result: dict[str, int] = {}
    if len(candidates) >= _EVAL_TRIPLET_MIN:
        result["_eval_initials"] = candidates[0]
        result["_eval_decision"] = candidates[1]
        result["_eval_comment"] = candidates[2]
    elif len(candidates) >= _EVAL_PAIR_MIN:
        result["_eval_initials"] = candidates[0]
        result["_eval_decision"] = candidates[1]
    return result


def _map_columns(headers: list[str]) -> dict[str, int]:
    """Map canonical field names to column indices for a given header row.

    Parameters
    ----------
    headers : list[str]
        Raw header strings from the first Excel row.

    Returns
    -------
    dict[str, int]
        ``{field_name: column_index}`` for every recognised column.
    """
    normed = [_norm(h) for h in headers]

    num_col, used = _find_candidate_number(normed)
    mapping: dict[str, int] = {"candidate_number": num_col}

    info_map, used = _match_header_patterns(normed, used)
    mapping.update(info_map)

    dec_map, used = _match_decision_columns(normed, used)
    mapping.update(dec_map)

    eval_map = _find_evaluator_triplet(headers, used, mapping)
    mapping.update(eval_map)

    # Gender in hidden column 2 (2024-25 files)
    if "gender" not in mapping and _HIDDEN_GENDER_COL not in used:
        mapping["_maybe_gender_col"] = _HIDDEN_GENDER_COL

    return mapping


# ---------------------------------------------------------------------------
# Filename metadata
# ---------------------------------------------------------------------------

_FILENAME_RE = re.compile(
    r"mte_applications_(?P<year>[\d\-]+)_(?P<round>round\d+)\.xlsx",
)


def _parse_filename(name: str) -> tuple[str, str]:
    """Extract academic year and round from a normalised filename.

    Parameters
    ----------
    name : str
        Filename like ``mte_applications_2023-24_round1.xlsx``.

    Returns
    -------
    tuple[str, str]
        ``(academic_year, admission_round)``
    """
    m = _FILENAME_RE.match(name)
    if not m:
        return ("unknown", "unknown")
    return (m.group("year"), m.group("round"))


# ---------------------------------------------------------------------------
# Row grouping
# ---------------------------------------------------------------------------


def _is_new_candidate(val: Any) -> bool:
    """Return True if *val* looks like a candidate number."""
    if val is None:
        return False
    s = str(val).strip()
    if s in ("", "None"):
        return False
    try:
        int(float(s))
    except (ValueError, TypeError):
        return False
    return True


def _group_rows(
    rows: list[list[Any]],
    num_col: int,
) -> list[list[list[Any]]]:
    """Group Excel rows into per-candidate bundles.

    A new candidate starts whenever ``rows[r][num_col]`` is a non-empty
    integer-like value.  Continuation rows belong to the previous candidate.

    Parameters
    ----------
    rows : list[list[Any]]
        All data rows (excluding the header row).
    num_col : int
        Column index for the candidate number.

    Returns
    -------
    list[list[list[Any]]]
        List of groups; each group is a list of rows for one candidate.
    """
    groups: list[list[list[Any]]] = []
    current: list[list[Any]] = []

    for row in rows:
        val = row[num_col] if num_col < len(row) else None
        if _is_new_candidate(val):
            if current:
                groups.append(current)
            current = [row]
        elif current:
            current.append(row)

    if current:
        groups.append(current)

    return groups


# ---------------------------------------------------------------------------
# Candidate extraction (split into helpers)
# ---------------------------------------------------------------------------


def _collect_evaluations(
    group: list[list[Any]],
    col_map: dict[str, int],
) -> str:
    """Merge committee evaluations from all rows into a single string."""
    init_col = col_map.get("_eval_initials")
    dec_col = col_map.get("_eval_decision")
    com_col = col_map.get("_eval_comment")

    evaluations: list[str] = []
    for row in group:
        initials = _safe_cell(row, init_col)
        decision = _safe_cell(row, dec_col)
        comment = _safe_cell(row, com_col)

        if not (initials or decision or comment):
            continue

        entry = f"[{initials}]" if initials else ""
        if decision:
            entry = f"{entry} {decision}" if entry else decision
        if comment:
            entry = f"{entry} — {comment}" if entry else comment
        evaluations.append(entry.strip())

    return "\n".join(evaluations)


def _first_nonempty(
    group: list[list[Any]],
    col_map: dict[str, int],
    field: str,
) -> str:
    """Return the first non-empty value for *field* across all rows."""
    idx = col_map.get(field)
    if idx is None:
        return ""
    for row in group:
        val = _safe_cell(row, idx)
        if val:
            return val
    return ""


def _detect_gender(
    group: list[list[Any]],
    col_map: dict[str, int],
    primary: list[Any],
) -> str:
    """Detect gender from a labeled column or hidden column 2."""
    gender_idx = col_map.get("gender")
    if gender_idx is not None:
        return _safe_cell(primary, gender_idx)

    maybe_col = col_map.get("_maybe_gender_col")
    if maybe_col is None:
        return ""
    for row in group:
        val = _safe_cell(row, maybe_col)
        if val in ("M", "F"):
            return val
    return ""


def _extract_candidate(
    group: list[list[Any]],
    col_map: dict[str, int],
    source_file: str,
    academic_year: str,
    admission_round: str,
) -> CandidateRecord:
    """Build a ``CandidateRecord`` from a group of rows.

    Parameters
    ----------
    group : list[list[Any]]
        Rows belonging to a single candidate.
    col_map : dict[str, int]
        Column mapping from ``_map_columns``.
    source_file : str
        Filename of the source Excel file.
    academic_year : str
        Academic year string.
    admission_round : str
        Round string.

    Returns
    -------
    CandidateRecord
    """
    primary = group[0]

    def _get(field: str) -> str:
        return _safe_cell(primary, col_map.get(field))

    raw_num = _get("candidate_number")
    try:
        cand_num: int | None = int(float(raw_num))
    except (ValueError, TypeError):
        cand_num = None

    return CandidateRecord(
        source_file=source_file,
        academic_year=academic_year,
        admission_round=admission_round,
        candidate_number=cand_num,
        name=_get("name"),
        school_country=_get("school_country"),
        school_name=_get("school_name"),
        school_quality=_get("school_quality"),
        spe_remarks=_get("spe_remarks"),
        gpa_scale=_get("gpa_scale"),
        study_level=_get("study_level"),
        gpa_candidate=_get("gpa_candidate"),
        gpa_max=_get("gpa_max"),
        gender=_detect_gender(group, col_map, primary),
        committee_evaluations=_collect_evaluations(group, col_map),
        decision_section=_first_nonempty(group, col_map, "decision_section"),
        decision_permanent_member=_first_nonempty(
            group, col_map, "decision_permanent_member",
        ),
        decision_final=_first_nonempty(group, col_map, "decision_final"),
    )


# ---------------------------------------------------------------------------
# File-level parsing
# ---------------------------------------------------------------------------


def parse_file(filepath: Path) -> list[CandidateRecord]:
    """Read one admission Excel file and return normalised candidate records.

    Parameters
    ----------
    filepath : Path
        Path to an ``.xlsx`` file.

    Returns
    -------
    list[CandidateRecord]
        One record per candidate.
    """
    wb = load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        wb.close()
        return []

    all_rows: list[list[Any]] = []
    headers: list[str] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = [_cell(c) for c in row]
        else:
            all_rows.append(list(row))
    wb.close()

    col_map = _map_columns(headers)
    year, rnd = _parse_filename(filepath.name)
    num_col = col_map.get("candidate_number", 0)
    groups = _group_rows(all_rows, num_col)

    logger.info(
        "Parsed {} → {} candidates from {} rows",
        filepath.name,
        len(groups),
        len(all_rows),
    )

    return [
        _extract_candidate(g, col_map, filepath.name, year, rnd)
        for g in groups
    ]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _records_to_table(records: list[CandidateRecord]) -> pa.Table:
    """Convert a list of candidate records to a PyArrow table."""
    columns: dict[str, list[Any]] = {
        field: [] for field in CandidateRecord.model_fields
    }
    for rec in records:
        dump = rec.model_dump()
        for field, col_list in columns.items():
            col_list.append(dump[field])
    return pa.table(columns)


def run_pipeline(
    input_dir: Path = _DATA_RAW,
    output_path: Path = _DATA_OUT,
) -> Path:
    """Read all admission Excel files and write a single Parquet file.

    Parameters
    ----------
    input_dir : Path
        Directory containing normalised ``mte_applications_*.xlsx`` files.
    output_path : Path
        Output Parquet path.

    Returns
    -------
    Path
        The path to the written Parquet file.
    """
    all_records: list[CandidateRecord] = []

    for xlsx in sorted(input_dir.glob("mte_applications_*.xlsx")):
        records = parse_file(xlsx)
        all_records.extend(records)

    logger.info("Total candidates extracted: {}", len(all_records))

    table = _records_to_table(all_records)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, output_path)
    logger.info("Wrote {} rows to {}", len(all_records), output_path)

    return output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    from loguru import logger as _logger

    _logger.remove()
    _logger.add(sys.stderr, level="INFO")
    run_pipeline()
