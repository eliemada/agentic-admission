"""MTE Admission — University Profiles Editor.

Dashboard for the admissions board to view, search, and edit
university tier assignments and notes.

Run with:
    uv run streamlit run dashboard/universities.py --server.port 8503
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

_PROJECT = Path(__file__).resolve().parent.parent
_AUTO_PATH = _PROJECT / "data" / "reference" / "university_profiles.json"
_OVERRIDES_PATH = _PROJECT / "data" / "reference" / "university_overrides.yaml"

TIERS = ("A", "B", "C", "X")
TIER_LABELS = {
    "A": "A — Priority",
    "B": "B — Good",
    "C": "C — Low interest",
    "X": "X — Unknown",
}
_TIER_ICONS = {"A": "🟢", "B": "🟡", "C": "🔴", "X": "⚪"}

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MTE — University Profiles",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Data I/O
# ---------------------------------------------------------------------------


@st.cache_data
def _load_auto_profiles() -> dict:
    if not _AUTO_PATH.exists():
        return {}
    return json.loads(_AUTO_PATH.read_text(encoding="utf-8"))


def _load_overrides() -> dict:
    if not _OVERRIDES_PATH.exists():
        return {}
    try:
        import yaml  # noqa: PLC0415

        raw = yaml.safe_load(_OVERRIDES_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        return {str(k): v for k, v in raw.items() if isinstance(v, dict)}
    except ImportError:
        st.error("PyYAML not installed")
        return {}


def _save_overrides(overrides: dict) -> None:
    import yaml  # noqa: PLC0415

    _OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _OVERRIDES_PATH.open("w", encoding="utf-8") as f:
        yaml.dump(overrides, f, default_flow_style=False, allow_unicode=True, sort_keys=True)


def _merge(auto: dict, overrides: dict) -> dict:
    merged = {name: {**data} for name, data in auto.items()}
    for name, fields in overrides.items():
        if name in merged:
            merged[name].update({k: v for k, v in fields.items() if v is not None})
        else:
            merged[name] = {"name": name, **fields}
    return merged


# ---------------------------------------------------------------------------
# UI components
# ---------------------------------------------------------------------------


def _render_sidebar(merged: dict) -> tuple[dict, dict]:
    """Render sidebar filters, return (filtered, overrides)."""
    overrides = _load_overrides()

    st.sidebar.header("Filters")
    search = st.sidebar.text_input("Search university", "")
    tier_filter = st.sidebar.multiselect("Tier", TIERS, default=list(TIERS))
    min_applicants = st.sidebar.slider("Min applicants", 0, 50, 0)
    only_overrides = st.sidebar.checkbox("Show only board-edited", value=False)

    filtered = {}
    for name, data in merged.items():
        if data.get("tier", "X") not in tier_filter:
            continue
        if data.get("applicants", 0) < min_applicants:
            continue
        if search and search.lower() not in name.lower():
            continue
        if only_overrides and name not in overrides:
            continue
        filtered[name] = data

    st.sidebar.metric("Showing", f"{len(filtered)} / {len(merged)}")
    return filtered, overrides


def _render_stats(merged: dict, overrides: dict) -> None:
    """Render summary metrics."""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total universities", len(merged))
    c2.metric("Board overrides", len(overrides))
    c3.metric("Tier A", sum(1 for d in merged.values() if d.get("tier") == "A"))
    c4.metric("With data", sum(1 for d in merged.values() if d.get("applicants", 0) > 0))


def _render_university_row(name: str, data: dict, overrides: dict) -> None:
    """Render one expandable university row with edit controls."""
    tier = data.get("tier", "X")
    applicants = data.get("applicants", 0)
    accept_rate = data.get("accept_rate", 0)
    country = data.get("country", "")
    board_notes = data.get("board_notes", "")
    icon = _TIER_ICONS.get(tier, "⚪")
    badge = " ✏️" if name in overrides else ""

    with st.expander(
        f"{icon} **{name}** — {country} | "
        f"Tier {tier} | {applicants} applicants | "
        f"{accept_rate:.0%} accept{badge}"
    ):
        col_info, col_edit = st.columns(2)

        with col_info:
            st.markdown(
                f"**Country:** {country}  \n"
                f"**Accepts:** {data.get('accepts', 0)} | "
                f"**Rejects:** {data.get('rejects', 0)} | "
                f"**Total:** {applicants}"
            )
            if board_notes:
                st.info(board_notes)

        with col_edit:
            current = overrides.get(name, {})
            new_tier = st.selectbox(
                "Tier", TIERS,
                index=TIERS.index(current.get("tier", tier)),
                key=f"tier_{name}",
                format_func=lambda t: TIER_LABELS[t],
            )
            new_notes = st.text_area(
                "Notes",
                value=current.get("board_notes", board_notes),
                key=f"notes_{name}",
                height=68,
            )
            if st.button("Save", key=f"save_{name}"):
                overrides[name] = {"tier": new_tier, "board_notes": new_notes}
                if country:
                    overrides[name]["country"] = country
                _save_overrides(overrides)
                st.success(f"Saved {name}")
                st.rerun()


def _render_add_form(overrides: dict) -> None:
    """Render form to add a new university."""
    st.divider()
    st.subheader("Add university")
    with st.form("add_university"):
        new_name = st.text_input("University name")
        c1, c2 = st.columns(2)
        new_country = c1.text_input("Country")
        new_tier = c2.selectbox("Tier", TIERS, format_func=lambda t: TIER_LABELS[t])
        new_notes = st.text_area("Board notes")

        if st.form_submit_button("Add") and new_name.strip():
            overrides[new_name.strip()] = {
                "tier": new_tier,
                "country": new_country,
                "board_notes": new_notes,
            }
            _save_overrides(overrides)
            st.success(f"Added {new_name}")
            st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Render the university profiles dashboard."""
    st.title("🏛️ University Profiles")
    st.caption("View historical acceptance data and manage tier assignments.")

    auto = _load_auto_profiles()
    overrides = _load_overrides()
    merged = _merge(auto, overrides)

    if not merged:
        st.warning("No profiles found. Run `uv run poe mine-universities` first.")
        return

    filtered, overrides = _render_sidebar(merged)
    _render_stats(merged, overrides)

    st.subheader(f"Universities ({len(filtered)})")
    sorted_names = sorted(filtered, key=lambda n: filtered[n].get("applicants", 0), reverse=True)
    for name in sorted_names:
        _render_university_row(name, filtered[name], overrides)

    _render_add_form(overrides)


if __name__ == "__main__":
    main()
