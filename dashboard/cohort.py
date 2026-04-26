"""MTE Admission — Cohort Viewer.

Dashboard for the admissions committee to browse, search, and filter
candidates parsed from Synthese PDFs.  No Excel needed — data is
extracted directly from application forms.

Run with:
    uv run streamlit run dashboard/cohort.py --server.port 8504
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT = Path(__file__).resolve().parent.parent
_DOSSIER_ROOT = _PROJECT / "data" / "raw" / "applications" / "dossiers"
_PROCESSED = _PROJECT / "data" / "processed"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MTE — Cohort Viewer",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
<style>
    .main .block-container {
        padding-top: 0.5rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
    }
    div[data-testid="stMetric"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
    }
    .candidate-card {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _available_semesters() -> list[str]:
    """Find semesters that have a cohort JSON."""
    return sorted(
        f.stem.removeprefix("cohort_")
        for f in _PROCESSED.glob("cohort_*.json")
    )


@st.cache_data
def _load_cohort(semester: str) -> list[dict]:
    path = _PROCESSED / f"cohort_{semester}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_gpa(raw: str) -> float | None:
    """Best-effort parse of a GPA string to float."""
    if not raw:
        return None
    # Handle comma decimals (European style)
    cleaned = raw.replace(",", ".").strip()
    # Take first numeric-looking token
    for token in cleaned.split():
        try:
            return float(token)
        except ValueError:
            continue
    # Try the whole string
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_gpa(record: dict) -> float | None:
    """Normalize GPA to a 0-4 scale (best effort)."""
    gpa = _parse_gpa(record.get("gpa", ""))
    gpa_max = _parse_gpa(record.get("gpa_max", ""))
    if gpa is None or gpa_max is None or gpa_max == 0:
        return None
    # If scale is inverted (German: 1.0 is best, lower is better)
    german_max_threshold = 1.5
    if gpa_max <= german_max_threshold and gpa >= 1.0:
        return None  # Can't normalize German grades reliably
    return round(gpa / gpa_max * 4.0, 2)


def _dossier_file_count(semester: str, folder_name: str) -> int:
    """Count files in a candidate's dossier folder."""
    dossier = _DOSSIER_ROOT / semester / folder_name
    if not dossier.is_dir():
        return 0
    count = 0
    for item in dossier.iterdir():
        if item.is_dir():
            count += len(list(item.iterdir()))
        else:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Sidebar — filters
# ---------------------------------------------------------------------------


def _render_sidebar(data: list[dict]) -> list[dict]:
    """Render sidebar filters, return filtered data."""
    st.sidebar.header("Filters")

    search = st.sidebar.text_input("Search (name, school)", "")

    # Country filter
    countries = sorted({r["institution_country"] for r in data if r["institution_country"]})
    selected_countries = st.sidebar.multiselect("Country", countries)

    # Gender filter
    genders = sorted({r["gender"] for r in data if r["gender"]})
    selected_genders = st.sidebar.multiselect("Gender", genders)

    # Study level
    levels = sorted({r["study_level"] for r in data if r["study_level"]})
    selected_levels = st.sidebar.multiselect("Study level", levels)

    # GPA range (normalized 0-4)
    gpa_filter = st.sidebar.checkbox("Filter by normalized GPA (0-4 scale)")
    gpa_min, gpa_max = 0.0, 4.0
    if gpa_filter:
        gpa_min, gpa_max = st.sidebar.slider("GPA range", 0.0, 4.0, (0.0, 4.0), 0.1)

    # Apply filters
    filtered = []
    for r in data:
        if search:
            search_lower = search.lower()
            searchable = f"{r['full_name']} {r['institution_name']} {r['field_of_study']}".lower()
            if search_lower not in searchable:
                continue
        if selected_countries and r["institution_country"] not in selected_countries:
            continue
        if selected_genders and r["gender"] not in selected_genders:
            continue
        if selected_levels and r["study_level"] not in selected_levels:
            continue
        if gpa_filter:
            norm = _normalize_gpa(r)
            if norm is None or not (gpa_min <= norm <= gpa_max):
                continue
        filtered.append(r)

    st.sidebar.divider()
    st.sidebar.metric("Showing", f"{len(filtered)} / {len(data)}")
    return filtered


# ---------------------------------------------------------------------------
# Stats row
# ---------------------------------------------------------------------------


def _render_stats(data: list[dict]) -> None:
    """Render summary metrics."""
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total candidates", len(data))

    males = sum(1 for r in data if r["gender"] == "M")
    females = sum(1 for r in data if r["gender"] == "F")
    c2.metric("Gender", f"{males}M / {females}F")

    countries = len({r["institution_country"] for r in data if r["institution_country"]})
    c3.metric("Countries", countries)

    institutions = len({r["institution_name"] for r in data if r["institution_name"]})
    c4.metric("Institutions", institutions)

    gpas = [_normalize_gpa(r) for r in data]
    valid_gpas = [g for g in gpas if g is not None]
    avg = sum(valid_gpas) / len(valid_gpas) if valid_gpas else 0
    c5.metric("Avg GPA (norm)", f"{avg:.2f}")


# ---------------------------------------------------------------------------
# Sort helpers
# ---------------------------------------------------------------------------

_SORT_OPTIONS = {
    "Name (A-Z)": lambda r: r["full_name"].lower(),
    "Name (Z-A)": lambda r: r["full_name"].lower(),
    "GPA (high → low)": lambda r: _normalize_gpa(r) or 0,
    "GPA (low → high)": lambda r: _normalize_gpa(r) or 0,
    "Country": lambda r: r["institution_country"],
    "Institution": lambda r: r["institution_name"],
}

_SORT_REVERSE = {
    "Name (A-Z)": False,
    "Name (Z-A)": True,
    "GPA (high → low)": True,
    "GPA (low → high)": False,
    "Country": False,
    "Institution": False,
}


# ---------------------------------------------------------------------------
# Candidate row
# ---------------------------------------------------------------------------


def _render_candidate(record: dict, semester: str) -> None:
    """Render one expandable candidate row."""
    norm_gpa = _normalize_gpa(record)
    gpa_display = f"{record['gpa']}/{record['gpa_max']}"
    if norm_gpa is not None:
        gpa_display += f" (norm: {norm_gpa:.2f}/4)"

    gender_icon = {"M": "♂", "F": "♀"}.get(record["gender"], "?")
    label = (
        f"**{record['full_name']}** {gender_icon} — "
        f"{record['institution_name']} ({record['institution_country']}) — "
        f"GPA {gpa_display}"
    )

    with st.expander(label):
        col_info, col_details = st.columns(2)

        with col_info:
            st.markdown(
                f"**Application ID:** {record['application_id']}  \n"
                f"**Nationality:** {record['nationality']}  \n"
                f"**Gender:** {record['gender']}  \n"
                f"**Study level:** {record['study_level']}  \n"
                f"**Field of study:** {record['field_of_study']}"
            )

        with col_details:
            st.markdown(
                f"**Institution:** {record['institution_name']}  \n"
                f"**Country:** {record['institution_country']}  \n"
                f"**GPA:** {record['gpa']} / {record['gpa_max']}  \n"
                f"**Folder:** `{record['folder_name']}`"
            )

            n_files = _dossier_file_count(semester, record["folder_name"])
            st.caption(f"Dossier files: {n_files}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Render the cohort viewer dashboard."""
    st.title("📋 Cohort Viewer")
    st.caption(
        "Browse candidates extracted from Synthese PDFs. "
        "No Excel needed — data is parsed directly from application forms."
    )

    semesters = _available_semesters()
    if not semesters:
        st.warning(
            "No cohort data found. Run:\n\n"
            "```\nuv run python -m agentic_admission.extraction.cohort_builder\n```"
        )
        return

    semester = st.selectbox("Semester", semesters, index=len(semesters) - 1)
    data = _load_cohort(semester)
    if not data:
        st.warning(f"No data for semester {semester}")
        return

    filtered = _render_sidebar(data)
    _render_stats(filtered)

    # Sort
    col_sort, _ = st.columns([1, 3])
    with col_sort:
        sort_by = st.selectbox("Sort by", list(_SORT_OPTIONS.keys()))

    sorted_data = sorted(
        filtered,
        key=_SORT_OPTIONS[sort_by],
        reverse=_SORT_REVERSE[sort_by],
    )

    st.subheader(f"Candidates ({len(sorted_data)})")
    for record in sorted_data:
        _render_candidate(record, semester)


if __name__ == "__main__":
    main()
