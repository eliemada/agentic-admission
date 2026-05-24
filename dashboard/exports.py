"""Export utilities for CSV, Excel, and PDF generation.

Excel exports follow EPFL brand styling with:
- Logo header, batch/semester metadata, generation timestamp
- Conditional formatting for status and score columns
- Frozen panes, auto-filters, print-area configuration
- Consistent color palette matching the admission console design system
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from pathlib import Path

from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XlImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

# ---------------------------------------------------------------------------
# Design tokens (matching the admission console)
# ---------------------------------------------------------------------------

_LOGO_PATH = Path(__file__).resolve().parent / "assets" / "epfl_logo.png"

# EPFL red + console palette
_EPFL_RED = "FF0000"
_ACCENT = "4F46E5"  # indigo
_BG = "FAFAFA"
_BG_HEADER = "18181B"  # zinc-900
_FG_HEADER = "FFFFFF"
_BG_SUBHEADER = "F4F4F5"  # zinc-100
_BORDER_COLOR = "E4E4E7"  # zinc-200

_ADMIT_BG = "F0FDF4"
_ADMIT_FG = "15803D"
_REJECT_BG = "FEF2F2"
_REJECT_FG = "B91C1C"
_DISCUSS_BG = "FFFBEB"
_DISCUSS_FG = "B45309"
_PENDING_BG = "F4F4F5"
_PENDING_FG = "52525B"

_TIER_COLORS = {
    "A": ("EEF2FF", "3730A3"),  # indigo
    "B": ("ECFEFF", "155E75"),  # cyan
    "C": ("F7FEE7", "4D7C0F"),  # lime
    "X": ("F4F4F5", "52525B"),  # neutral
}

_STATUS_STYLES = {
    "admit": (_ADMIT_BG, _ADMIT_FG),
    "reject": (_REJECT_BG, _REJECT_FG),
    "discuss": (_DISCUSS_BG, _DISCUSS_FG),
    "pending": (_PENDING_BG, _PENDING_FG),
}

_thin_border = Border(
    left=Side(style="thin", color=_BORDER_COLOR),
    right=Side(style="thin", color=_BORDER_COLOR),
    top=Side(style="thin", color=_BORDER_COLOR),
    bottom=Side(style="thin", color=_BORDER_COLOR),
)


# ---------------------------------------------------------------------------
# Shared Excel helpers
# ---------------------------------------------------------------------------


def _add_header_block(
    ws: Worksheet, title: str, subtitle: str, semester: str, row_count: int
) -> int:
    """Add a branded header block with logo, title, metadata. Returns the next row."""
    # Row 1: Logo + title
    ws.merge_cells("A1:C3")
    if _LOGO_PATH.exists():
        img = XlImage(str(_LOGO_PATH))
        img.width = 120
        img.height = 58
        ws.add_image(img, "A1")

    ws.merge_cells("D1:H1")
    title_cell = ws["D1"]
    title_cell.value = title
    title_cell.font = Font(name="Calibri", size=18, bold=True, color=_BG_HEADER)
    title_cell.alignment = Alignment(vertical="center")

    # Row 2: Subtitle
    ws.merge_cells("D2:H2")
    sub_cell = ws["D2"]
    sub_cell.value = subtitle
    sub_cell.font = Font(name="Calibri", size=11, color="71717A")
    sub_cell.alignment = Alignment(vertical="center")

    # Row 3: Metadata
    ws.merge_cells("D3:H3")
    now = datetime.now(tz=UTC).strftime("%d %B %Y, %H:%M UTC")
    meta_cell = ws["D3"]
    meta_cell.value = f"Batch: {semester}  |  {row_count} records  |  Generated: {now}"
    meta_cell.font = Font(name="Calibri", size=9, italic=True, color="A1A1AA")
    meta_cell.alignment = Alignment(vertical="center")

    # Row 4: thin red accent line
    ws.row_dimensions[4].height = 4
    for col in range(1, 20):
        c = ws.cell(row=4, column=col)
        c.fill = PatternFill(start_color=_EPFL_RED, end_color=_EPFL_RED, fill_type="solid")

    ws.row_dimensions[1].height = 22
    ws.row_dimensions[2].height = 18
    ws.row_dimensions[3].height = 16

    return 6  # data starts at row 6 (row 5 = spacer)


# Approximate height per text line in Excel at the default font size
# (Calibri 11).
_LINE_HEIGHT_PT: float = 15.0

# Minimum row height -- keeps non-wrapping rows from looking cramped.
_MIN_ROW_HEIGHT_PT: float = 22.0

# Cap so a single very long pros/cons cell does not produce a 1000-pt row.
_MAX_ROW_HEIGHT_PT: float = 240.0

_VERTICAL_PADDING_PT: float = 6.0


def _line_count(value: object, col_width: int) -> int:
    r"""Estimate how many display lines a wrap-text cell will need.

    Counts explicit ``\n`` line breaks and adds extra lines for soft-
    wrapping when a single line exceeds the column width. ``col_width``
    is the Excel column width (in characters at the default font), so
    we treat it as the soft wrap point.
    """
    text = "" if value is None else str(value)
    if not text:
        return 1
    # Conservative chars-per-line: column width measured in default-font
    # characters; subtract a small margin for inter-character spacing.
    wrap_at = max(8, col_width - 2)
    lines = 0
    for explicit in text.split("\n"):
        if not explicit:
            lines += 1
            continue
        # Ceil-divide explicit-line length by wrap point.
        lines += max(1, (len(explicit) + wrap_at - 1) // wrap_at)
    return lines


def _row_height_for(values: list[object], wrap_columns: dict[int, int]) -> float:
    """Compute a row height that fits every wrapping cell in the row.

    Parameters
    ----------
    values
        The row's flattened cell values, in column order.
    wrap_columns
        ``{1-indexed column number: column width in chars}`` for every
        cell that uses ``wrap_text=True``.
    """
    max_lines = 1
    for col_idx, col_width in wrap_columns.items():
        # values is 0-indexed; col_idx is 1-indexed
        if col_idx - 1 < len(values):
            max_lines = max(max_lines, _line_count(values[col_idx - 1], col_width))
    height = max_lines * _LINE_HEIGHT_PT + _VERTICAL_PADDING_PT
    return min(_MAX_ROW_HEIGHT_PT, max(_MIN_ROW_HEIGHT_PT, height))


def _write_table_header(ws: Worksheet, row: int, columns: list[tuple[str, int]]) -> None:
    """Write a dark styled header row."""
    ws.row_dimensions[row].height = 28
    for col_idx, (label, width) in enumerate(columns, 1):
        cell = ws.cell(row=row, column=col_idx, value=label)
        cell.font = Font(name="Calibri", size=10, bold=True, color=_FG_HEADER)
        cell.fill = PatternFill(start_color=_BG_HEADER, end_color=_BG_HEADER, fill_type="solid")
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        cell.border = _thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width


def _style_data_cell(
    ws: Worksheet,
    row: int,
    col: int,
    value: object,
    *,
    mono: bool = False,
    align_right: bool = False,
    fill_bg: str | None = None,
    fill_fg: str | None = None,
    wrap: bool = False,
) -> None:
    """Write and style a data cell."""
    cell = ws.cell(row=row, column=col, value=value)
    font_name = "Consolas" if mono else "Calibri"
    color = fill_fg or "18181B"
    cell.font = Font(name=font_name, size=10, color=color)
    cell.alignment = Alignment(
        horizontal="right" if align_right else "left", vertical="center", wrap_text=wrap
    )
    cell.border = _thin_border
    if fill_bg:
        cell.fill = PatternFill(start_color=fill_bg, end_color=fill_bg, fill_type="solid")
    # Zebra striping
    elif row % 2 == 0:
        cell.fill = PatternFill(
            start_color=_BG_SUBHEADER, end_color=_BG_SUBHEADER, fill_type="solid"
        )


def _finalize_sheet(ws: Worksheet, header_row: int, last_col: int) -> None:
    """Add auto-filter, freeze panes, and print setup."""
    last_col_letter = get_column_letter(last_col)
    ws.auto_filter.ref = f"A{header_row}:{last_col_letter}{ws.max_row}"
    ws.freeze_panes = f"A{header_row + 1}"
    ws.sheet_properties.pageSetUpPr = None  # avoid issues
    ws.print_title_rows = f"{header_row}:{header_row}"


# ---------------------------------------------------------------------------
# Candidates Excel
# ---------------------------------------------------------------------------

_CANDIDATE_COLS: list[tuple[str, int]] = [
    ("Candidate", 24),
    ("School", 32),
    ("AI Decision", 12),
    ("Committee Decision", 16),
    ("Committee Comment", 40),
    ("Confidence %", 14),
    ("Composite", 12),
    ("GPA", 10),
    ("GPA Scale", 10),
    ("GPA Norm.", 10),
    ("Academic", 11),
    ("Institution", 11),
    ("Reference", 11),
    ("Calibration", 11),
    ("Motivation", 11),
    ("Program Fit", 11),
    ("Risk Flags", 11),
    ("Consistency", 11),
    ("Primary Minor", 22),
    ("Minor #1", 22),
    ("Minor #1 Score", 9),
    ("Minor #1 Reason", 50),
    ("Minor #2", 22),
    ("Minor #2 Score", 9),
    ("Minor #2 Reason", 50),
    ("Minor #3", 22),
    ("Minor #3 Score", 9),
    ("Minor #3 Reason", 50),
    ("Strengths", 45),
    ("Concerns", 45),
]


def _minor_slot(minor: dict, idx: int) -> tuple[str, object, str]:
    """Return ``(name, score, reason)`` for the i-th recommended minor.

    Empty triple when the slot is missing — keeps row width constant so
    the spreadsheet stays well-formed.
    """
    recs = minor.get("recommended") or []
    if idx >= len(recs):
        return ("", "", "")
    entry = recs[idx] or {}
    return (
        entry.get("minor_name", "") or "",
        entry.get("fit_score", "") if entry.get("fit_score") is not None else "",
        entry.get("reasoning", "") or "",
    )


def _flatten_candidate(c: dict) -> list:
    """Flatten a verdict dict into an ordered values list."""
    scores = c.get("final_scores", {})
    confidence = c.get("confidence", 0)
    override = c.get("_override", {})
    minor = c.get("minor_recommendation") or {}
    primary_minor = minor.get("primary_minor", "")
    m1_name, m1_score, m1_reason = _minor_slot(minor, 0)
    m2_name, m2_score, m2_reason = _minor_slot(minor, 1)
    m3_name, m3_score, m3_reason = _minor_slot(minor, 2)
    return [
        c.get("candidate_name", "") or c.get("candidate_id", ""),
        c.get("school", ""),
        c.get("status", ""),
        override.get("decision", ""),
        override.get("comment", ""),
        round(confidence * 100, 1) if confidence else "",
        c.get("moderator", {}).get("composite", ""),
        c.get("gpa", ""),
        c.get("gpa_max", ""),
        c.get("gpa_normalized", ""),
        scores.get("academic_strength", ""),
        scores.get("institution_quality", ""),
        scores.get("reference_quality", ""),
        scores.get("calibration_confidence", ""),
        scores.get("motivation_clarity", ""),
        scores.get("program_fit", ""),
        scores.get("risk_flags", ""),
        scores.get("consistency", ""),
        primary_minor,
        m1_name,
        m1_score,
        m1_reason,
        m2_name,
        m2_score,
        m2_reason,
        m3_name,
        m3_score,
        m3_reason,
        "\n".join(f"+ {p}" for p in c.get("verdict_pros", [])),
        "\n".join(f"- {p}" for p in c.get("verdict_cons", [])),
    ]


def candidates_to_csv(candidates: list[dict]) -> bytes:
    """Generate CSV bytes from verdict dicts."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([label for label, _ in _CANDIDATE_COLS])
    for c in candidates:
        writer.writerow(_flatten_candidate(c))
    return buf.getvalue().encode("utf-8-sig")


def candidates_to_excel(candidates: list[dict], semester: str = "") -> bytes:
    """Generate a professionally formatted Excel workbook for candidates."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Evaluation Results"
    ws.sheet_view.showGridLines = False

    sem = semester or (candidates[0].get("semester", "All") if candidates else "All")
    data_start = _add_header_block(
        ws,
        title="MTE Admission Evaluations",
        subtitle="EPFL IC Master's in Management, Technology & Entrepreneurship",
        semester=sem,
        row_count=len(candidates),
    )

    _write_table_header(ws, data_start, _CANDIDATE_COLS)

    # Column indices (1-indexed) — keep in sync with _CANDIDATE_COLS.
    col_comment = 5
    score_cols = range(11, 19)  # Academic..Consistency
    minor_reason_cols = (22, 25, 28)
    minor_score_cols = (21, 24, 27)
    pros_cons_cols = (29, 30)
    numeric_text_cols = (6, 7, 8, 9, 10)

    wrap_indices = {col_comment, *minor_reason_cols, *pros_cons_cols}
    wrap_cols = {
        col_idx + 1: width
        for col_idx, (_, width) in enumerate(_CANDIDATE_COLS)
        if (col_idx + 1) in wrap_indices
    }

    for row_offset, c in enumerate(candidates):
        row = data_start + 1 + row_offset
        vals = _flatten_candidate(c)
        ws.row_dimensions[row].height = _row_height_for(vals, wrap_cols)
        status = c.get("status", "")
        bg, fg = _STATUS_STYLES.get(status, (None, None))

        for col_idx, val in enumerate(vals, 1):
            is_ai_decision = col_idx == 3
            is_committee_decision = col_idx == 4
            is_comment = col_idx == col_comment
            is_score = col_idx in score_cols
            is_minor_score = col_idx in minor_score_cols
            is_minor_reason = col_idx in minor_reason_cols
            is_pros_cons = col_idx in pros_cons_cols

            if is_ai_decision:
                _style_data_cell(ws, row, col_idx, str(val).upper(), fill_bg=bg, fill_fg=fg)
            elif is_committee_decision:
                comm_bg, comm_fg = _STATUS_STYLES.get(
                    {"accept": "admit", "reject": "reject", "waitlist": "discuss"}.get(
                        str(val).lower(), ""
                    ),
                    (None, None),
                )
                _style_data_cell(
                    ws,
                    row,
                    col_idx,
                    str(val).upper() if val else "",
                    fill_bg=comm_bg,
                    fill_fg=comm_fg,
                )
            elif is_comment:
                _style_data_cell(ws, row, col_idx, val, wrap=True)
            elif is_score:
                score_bg = None
                score_fg = None
                if isinstance(val, (int, float)) and val != "":
                    if val >= 7:
                        score_bg, score_fg = _ADMIT_BG, _ADMIT_FG
                    elif val <= 4:
                        score_bg, score_fg = _REJECT_BG, _REJECT_FG
                _style_data_cell(
                    ws,
                    row,
                    col_idx,
                    val,
                    mono=True,
                    align_right=True,
                    fill_bg=score_bg,
                    fill_fg=score_fg,
                )
            elif is_minor_score:
                _style_data_cell(ws, row, col_idx, val, mono=True, align_right=True)
            elif is_minor_reason or is_pros_cons:
                _style_data_cell(ws, row, col_idx, val, wrap=True)
            elif col_idx in numeric_text_cols:
                _style_data_cell(ws, row, col_idx, val, mono=True, align_right=True)
            else:
                _style_data_cell(ws, row, col_idx, val)

    _finalize_sheet(ws, data_start, len(_CANDIDATE_COLS))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Cohort Excel
# ---------------------------------------------------------------------------

_COHORT_COLS: list[tuple[str, int]] = [
    ("Full Name", 28),
    ("Application ID", 18),
    ("Gender", 9),
    ("Nationality", 18),
    ("Institution", 38),
    ("Country", 18),
    ("Field of Study", 26),
    ("Study Level", 14),
    ("GPA", 8),
    ("GPA Max", 9),
]

_COHORT_KEYS = [
    "full_name",
    "application_id",
    "gender",
    "nationality",
    "institution_name",
    "institution_country",
    "field_of_study",
    "study_level",
    "gpa",
    "gpa_max",
]


def cohort_to_csv(cohort: list[dict]) -> bytes:
    """Generate CSV bytes from cohort data."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([label for label, _ in _COHORT_COLS])
    for c in cohort:
        writer.writerow([c.get(k, "") for k in _COHORT_KEYS])
    return buf.getvalue().encode("utf-8-sig")


def cohort_to_excel(cohort: list[dict], semester: str = "") -> bytes:
    """Generate a professionally formatted Excel workbook for a cohort."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Cohort"
    ws.sheet_view.showGridLines = False

    data_start = _add_header_block(
        ws,
        title="MTE Admission Cohort",
        subtitle="EPFL IC Master's in Management, Technology & Entrepreneurship",
        semester=semester or "Unknown",
        row_count=len(cohort),
    )

    _write_table_header(ws, data_start, _COHORT_COLS)

    for row_offset, c in enumerate(cohort):
        row = data_start + 1 + row_offset
        ws.row_dimensions[row].height = 22
        for col_idx, key in enumerate(_COHORT_KEYS, 1):
            val = c.get(key, "")
            is_num = key in ("gpa", "gpa_max")
            _style_data_cell(ws, row, col_idx, val, mono=is_num, align_right=is_num)

    _finalize_sheet(ws, data_start, len(_COHORT_COLS))

    # Summary sheet
    summary = wb.create_sheet("Summary", 0)
    summary.sheet_view.showGridLines = False
    _add_header_block(
        summary,
        title="Cohort Summary",
        subtitle="EPFL IC Master's - MTE",
        semester=semester or "Unknown",
        row_count=len(cohort),
    )

    stats_start = 6
    stats = [
        ("Total Candidates", len(cohort)),
        ("Women", sum(1 for c in cohort if c.get("gender") == "F")),
        ("Men", sum(1 for c in cohort if c.get("gender") == "M")),
        ("Unique Countries", len({c.get("institution_country", "") for c in cohort})),
        ("Unique Institutions", len({c.get("institution_name", "") for c in cohort})),
    ]

    for i, (label, val) in enumerate(stats):
        r = stats_start + i
        _style_data_cell(summary, r, 1, label)
        _style_data_cell(summary, r, 2, val, mono=True, align_right=True)
    summary.column_dimensions["A"].width = 22
    summary.column_dimensions["B"].width = 14

    # Country breakdown
    country_row = stats_start + len(stats) + 2
    summary.cell(row=country_row, column=1, value="Country Distribution").font = Font(
        name="Calibri", size=11, bold=True, color=_BG_HEADER
    )
    countries: dict[str, int] = {}
    for c in cohort:
        cc = c.get("institution_country", "Unknown")
        countries[cc] = countries.get(cc, 0) + 1
    for i, (country, count) in enumerate(sorted(countries.items(), key=lambda x: -x[1])):
        r = country_row + 1 + i
        _style_data_cell(summary, r, 1, country)
        _style_data_cell(summary, r, 2, count, mono=True, align_right=True)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# University Excel
# ---------------------------------------------------------------------------

_UNI_COLS: list[tuple[str, int]] = [
    ("Institution", 40),
    ("Country", 18),
    ("Tier", 8),
    ("Applicants", 12),
    ("Admits", 10),
    ("Accept Rate %", 13),
    ("Board Notes", 50),
]

_UNI_KEYS = ["name", "country", "tier", "applicants", "accepts", "accept_rate", "board_notes"]


def universities_to_csv(universities: list[dict]) -> bytes:
    """Generate CSV bytes from university profiles."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([label for label, _ in _UNI_COLS])
    for u in universities:
        row = [u.get(k, "") for k in _UNI_KEYS]
        # Convert accept_rate to percentage
        if isinstance(row[5], float):
            row[5] = round(row[5] * 100, 1)
        writer.writerow(row)
    return buf.getvalue().encode("utf-8-sig")


def universities_to_excel(universities: list[dict]) -> bytes:
    """Generate a professionally formatted Excel workbook for universities."""
    wb = Workbook()
    ws = wb.active
    ws.title = "University Tiers"
    ws.sheet_view.showGridLines = False

    data_start = _add_header_block(
        ws,
        title="University Tier Classification",
        subtitle="EPFL IC Master's - Calibration reference for admission decisions",
        semester="All years",
        row_count=len(universities),
    )

    _write_table_header(ws, data_start, _UNI_COLS)

    for row_offset, u in enumerate(universities):
        row = data_start + 1 + row_offset
        ws.row_dimensions[row].height = 22

        vals = [u.get(k, "") for k in _UNI_KEYS]
        tier = str(u.get("tier", "X"))
        tier_bg, tier_fg = _TIER_COLORS.get(tier, _TIER_COLORS["X"])

        for col_idx, val in enumerate(vals, 1):
            if col_idx == 3:  # Tier column
                _style_data_cell(ws, row, col_idx, val, fill_bg=tier_bg, fill_fg=tier_fg)
            elif col_idx in (4, 5):  # Numeric
                _style_data_cell(ws, row, col_idx, val, mono=True, align_right=True)
            elif col_idx == 6:  # Accept rate
                pct = round(val * 100, 1) if isinstance(val, float) else val
                _style_data_cell(ws, row, col_idx, pct, mono=True, align_right=True)
            elif col_idx == 7:  # Notes
                _style_data_cell(ws, row, col_idx, val, wrap=True)
            else:
                _style_data_cell(ws, row, col_idx, val)

    _finalize_sheet(ws, data_start, len(_UNI_COLS))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# PDF candidate report
# ---------------------------------------------------------------------------


def _sanitize(text: str) -> str:
    """Replace Unicode characters that latin-1 can't encode."""
    return (
        text.replace("\u2014", "--")
        .replace("\u2013", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2026", "...")
        .replace("\u00a0", " ")
    )


class _CandidatePDF(FPDF):
    """Custom PDF for candidate evaluation reports."""

    def header(self) -> None:
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(113, 113, 122)
        self.cell(0, 6, "EPFL Admission Console -- Candidate Report", new_x="LMARGIN", new_y="NEXT")
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(161, 161, 170)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def candidate_to_pdf(candidate: dict) -> bytes:
    """Generate a one-page PDF report for a candidate evaluation."""
    pdf = _CandidatePDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    cid = candidate.get("candidate_id", "Unknown")
    status = candidate.get("status", "pending").upper()
    school = candidate.get("school", "")
    gpa = candidate.get("gpa", "")
    gpa_max = candidate.get("gpa_max", "")
    confidence = round(candidate.get("confidence", 0) * 100, 1)
    moderator = candidate.get("moderator", {})
    composite = moderator.get("composite", 0)
    final_scores = candidate.get("final_scores", {})
    pros = candidate.get("verdict_pros", [])
    cons = candidate.get("verdict_cons", [])
    evaluations = candidate.get("evaluations", [])

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(24, 24, 27)
    name_display = (
        cid.replace("_", " ").split(" ", 1)[-1].replace("-", " ").title() if "_" in cid else cid
    )
    pdf.cell(0, 10, _sanitize(name_display), new_x="LMARGIN", new_y="NEXT")

    # Meta line
    pdf.set_font("Courier", "", 9)
    pdf.set_text_color(113, 113, 122)
    gpa_str = f"GPA {gpa}/{gpa_max}" if gpa and gpa_max else ""
    meta_parts = [p for p in [cid, _sanitize(school), gpa_str, f"Confidence {confidence}%"] if p]
    pdf.cell(0, 5, " | ".join(meta_parts), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Status + composite
    status_colors = {"ADMIT": (22, 163, 74), "REJECT": (220, 38, 38), "DISCUSS": (217, 119, 6)}
    r, g, b = status_colors.get(status, (113, 113, 122))
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(r, g, b)
    pdf.cell(30, 8, status)
    pdf.set_font("Courier", "", 10)
    pdf.set_text_color(82, 82, 91)
    pdf.cell(0, 8, f"composite {composite}/10", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Final scores
    if final_scores:
        _section_title(pdf, "FINAL SCORES")
        pdf.set_font("Courier", "", 9)
        for dim, val in final_scores.items():
            label = dim.replace("_", " ").title()
            bar_width = val / 10 * 60
            pdf.set_text_color(82, 82, 91)
            pdf.cell(50, 5, label)
            y = pdf.get_y() + 1
            pdf.set_fill_color(228, 228, 231)
            pdf.rect(60, y, 60, 3, "F")
            pdf.set_fill_color(79, 70, 229)
            pdf.rect(60, y, bar_width, 3, "F")
            pdf.cell(65, 5, "")
            pdf.set_text_color(24, 24, 27)
            pdf.cell(0, 5, str(val), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # Chair synthesis
    if pros:
        _section_title(pdf, "STRENGTHS")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(21, 128, 61)
        for p in pros:
            _bullet(pdf, "+", _sanitize(p))
        pdf.ln(2)

    if cons:
        _section_title(pdf, "CONCERNS")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(185, 28, 28)
        for c in cons:
            _bullet(pdf, "-", _sanitize(c))
        pdf.ln(2)

    # Agent verdicts
    if evaluations:
        _section_title(pdf, "AGENT VERDICTS")
        for ev in evaluations:
            role = ev.get("role", "")
            decision = ev.get("decision", "")
            scores = ev.get("scores", {})
            avg = sum(scores.values()) / len(scores) if scores else 0

            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(24, 24, 27)
            pdf.cell(35, 5, _sanitize(role))

            dr, dg, db = status_colors.get(decision, (113, 113, 122))
            pdf.set_text_color(dr, dg, db)
            pdf.cell(25, 5, decision)

            pdf.set_font("Courier", "", 9)
            pdf.set_text_color(82, 82, 91)
            score_parts = [f"{k.replace('_', ' ')}: {v}" for k, v in scores.items()]
            pdf.cell(
                0,
                5,
                _sanitize(f"avg {avg:.1f} -- {', '.join(score_parts)}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def _section_title(pdf: FPDF, title: str) -> None:
    """Render a section heading."""
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(82, 82, 91)
    pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _bullet(pdf: FPDF, marker: str, text: str) -> None:
    """Render a bulleted line with text wrapping."""
    pdf.cell(6, 5, marker)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(82, 82, 91)
    pdf.multi_cell(0, 4, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
