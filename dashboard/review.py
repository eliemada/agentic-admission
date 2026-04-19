"""MTE Admission Dashboard — Decision Support.

Interactive dashboard for reviewing AI-generated candidate evaluations,
exploring agent reasoning, and discussing candidates via chat.

Run with:
    uv run streamlit run dashboard/review.py
"""

from __future__ import annotations

import html as _html_mod
import sys
from pathlib import Path

# Streamlit runs from project root — add dashboard/ to import path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from mock_data import (
    DEFAULT_CHAT_RESPONSE,
    MOCK_CHAT_RESPONSES,
    MOCK_EVALUATIONS,
    NO_DATA_CHAT_RESPONSE,
)
from mock_data import SEMESTERS as MOCK_SEMESTERS
from verdict_loader import get_available_semesters, load_all_verdicts

# ---------------------------------------------------------------------------
# Paths (for document viewer)
# ---------------------------------------------------------------------------

_PROJECT = Path(__file__).resolve().parent.parent
_PDF_ROOT = _PROJECT / "data" / "raw" / "applications" / "dossiers"
_TEXT_ROOT = _PROJECT / "data" / "processed" / "texts"
_ANON_ROOT = _PROJECT / "data" / "processed" / "anonymized"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MTE Admission — Decision Support",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
<style>
    /* Global */
    .main .block-container {
        padding-top: 0.5rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
        max-width: 100%;
    }

    /* Hide Streamlit chrome */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }

    /* Stats cards */
    .stat-card {
        background: linear-gradient(135deg, #f8fafc, #f1f5f9);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        text-align: center;
    }
    .stat-number {
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.2;
    }
    .stat-label {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748b;
        margin-top: 0.2rem;
    }

    /* Candidate card */
    .candidate-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 0.75rem;
        transition: all 0.2s ease;
    }
    .candidate-card:hover {
        border-color: #94a3b8;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .candidate-card.selected {
        border-color: #3b82f6;
        border-width: 2px;
        box-shadow: 0 2px 12px rgba(59,130,246,0.15);
    }

    /* Status badges */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-admit { background: #dcfce7; color: #166534; }
    .badge-reject { background: #fee2e2; color: #991b1b; }
    .badge-discuss { background: #fef3c7; color: #92400e; }
    .badge-pending { background: #f1f5f9; color: #475569; }

    /* Confidence bar */
    .confidence-bar {
        height: 6px;
        border-radius: 3px;
        background: #e2e8f0;
        margin-top: 0.3rem;
        overflow: hidden;
    }
    .confidence-fill {
        height: 100%;
        border-radius: 3px;
        transition: width 0.5s ease;
    }

    /* Agent evaluation card */
    .agent-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.75rem;
    }
    .agent-role {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748b;
    }

    /* Moderator panel */
    .moderator-panel {
        background: linear-gradient(135deg, #eff6ff, #dbeafe);
        border: 1px solid #93c5fd;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
    }

    /* Document reference links */
    .doc-ref {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 6px;
        padding: 2px 8px;
        font-size: 0.8rem;
        color: #1d4ed8;
        text-decoration: none;
        margin: 2px 0;
    }

    /* Score grid */
    .score-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.5rem;
        margin-top: 0.5rem;
    }
    .score-item {
        text-align: center;
        padding: 0.4rem;
        background: white;
        border-radius: 6px;
        border: 1px solid #e2e8f0;
    }
    .score-value {
        font-size: 1.2rem;
        font-weight: 700;
    }
    .score-label {
        font-size: 0.65rem;
        color: #64748b;
        text-transform: uppercase;
    }

    /* Insufficient info message */
    .insufficient-info {
        color: #64748b;
        font-style: italic;
        padding: 0.5rem 0;
    }

    /* Section header */
    .section-header {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #64748b;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e2e8f0;
        margin-bottom: 0.75rem;
    }

    /* PII tag styling (from existing viewer) */
    .pii-tag {
        background-color: #ef4444;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: 600;
    }

    /* Debate transcript */
    .debate-section {
        margin-top: 1.5rem;
    }
    .debate-topic {
        background: linear-gradient(135deg, #faf5ff, #ede9fe);
        border: 1px solid #ddd6fe;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
    }
    .debate-topic-header {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #7c3aed;
        margin-bottom: 0.75rem;
    }
    .debate-entry {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
    }
    .debate-entry-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.4rem;
    }
    .debate-role {
        font-size: 0.75rem;
        font-weight: 700;
        color: #1e40af;
    }
    .debate-round {
        font-size: 0.65rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
    }
    .debate-argument {
        font-size: 0.85rem;
        color: #334155;
        line-height: 1.55;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _html_escape(text: str) -> str:
    """Escape HTML special characters in text."""
    return _html_mod.escape(text, quote=False)


def _badge_html(status: str) -> str:
    """Return an HTML badge for the given status."""
    css_class = f"badge-{status}"
    label = status.upper()
    return f'<span class="badge {css_class}">{label}</span>'


def _confidence_color(confidence: float) -> str:
    """Return a CSS color for a confidence value (0-1)."""
    if confidence >= 0.75:
        return "#10b981"  # green
    if confidence >= 0.50:
        return "#f59e0b"  # amber
    return "#ef4444"  # red


def _confidence_bar_html(confidence: float) -> str:
    """Return an HTML confidence bar."""
    color = _confidence_color(confidence)
    pct = int(confidence * 100)
    return (
        f'<div class="confidence-bar">'
        f'<div class="confidence-fill" style="width:{pct}%;background:{color};"></div>'
        f"</div>"
    )


def _score_grid_html(scores: dict[str, int | float]) -> str:
    """Return an HTML grid of scores."""
    if not scores:
        return ""
    html = '<div class="score-grid">'
    for label, value in scores.items():
        color = _confidence_color(value / 10.0)
        html += (
            f'<div class="score-item">'
            f'<div class="score-value" style="color:{color};">{value}</div>'
            f'<div class="score-label">{label}</div>'
            f"</div>"
        )
    html += "</div>"
    return html


def _doc_type_label(doc_type: str) -> str:
    """Human-readable label for a document type."""
    labels = {
        "application_summary": "Application Summary",
        "motivation_letter": "Motivation Letter",
        "recommendation_letter": "Recommendation Letter",
        "referent_summary": "Referent Summary",
        "transcript": "Transcript",
        "diploma": "Diploma",
        "cv": "CV",
        "language_certificate": "Language Certificate",
        "gre_results": "GRE Results",
        "other": "Other",
    }
    return labels.get(doc_type, doc_type.replace("_", " ").title())


def _doc_type_icon(doc_type: str) -> str:
    """Emoji icon for a document type."""
    icons = {
        "application_summary": "📋",
        "motivation_letter": "✉️",
        "recommendation_letter": "📨",
        "referent_summary": "📝",
        "transcript": "📊",
        "diploma": "🎓",
        "cv": "📄",
        "language_certificate": "🌐",
        "gre_results": "📈",
    }
    return icons.get(doc_type, "📎")


def _role_icon(role: str) -> str:
    """Emoji icon for an agent role."""
    icons = {
        "Academic": "📊",
        "Reference": "📨",
        "Motivation": "✉️",
        "Devil's Advocate": "⚖️",
        "Chair": "👨‍⚖️",
    }
    return icons.get(role, "🤖")


def _mock_chat_response(candidate: dict, user_message: str) -> str:
    """Generate a mock chat response based on keywords."""
    if not candidate.get("verdict_pros") and not candidate.get("evaluations"):
        return NO_DATA_CHAT_RESPONSE

    msg_lower = user_message.lower()
    for keyword, response in MOCK_CHAT_RESPONSES.items():
        if keyword in msg_lower:
            return response
    return DEFAULT_CHAT_RESPONSE


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


_EVAL_DIR = _PROJECT / "data" / "processed" / "evaluations"


_PARQUET_PATH = _PROJECT / "data" / "processed" / "all_candidates.parquet"


@st.cache_data
def load_evaluations(semester: str) -> list[dict]:
    """Load evaluations for a semester from real verdicts, with mock fallback."""
    real = [
        v
        for v in load_all_verdicts(_EVAL_DIR, parquet_path=_PARQUET_PATH)
        if v["semester"] == semester
    ]
    if real:
        return real
    # Fall back to mock data for demo semesters
    return [e for e in MOCK_EVALUATIONS if e["semester"] == semester]


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

if "selected_candidate" not in st.session_state:
    st.session_state.selected_candidate = None
if "chat_histories" not in st.session_state:
    st.session_state.chat_histories = {}


# ---------------------------------------------------------------------------
# Sidebar — Filters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 🎓 MTE Admissions")
    st.markdown("---")

    real_semesters = get_available_semesters(_EVAL_DIR)
    all_semesters = sorted({*real_semesters, *MOCK_SEMESTERS})
    semester = st.selectbox("Semester", all_semesters, index=0)

    st.markdown("#### Filters")
    status_filter = st.multiselect(
        "Status",
        ["admit", "reject", "discuss", "pending"],
        default=["admit", "reject", "discuss", "pending"],
        format_func=lambda x: x.upper(),
    )

    search_query = st.text_input("Search", placeholder="Search candidates...")

    st.markdown("---")
    st.markdown(
        '<div style="font-size:0.75rem;color:#94a3b8;">'
        "Decision support dashboard for MTE admission committee. "
        "AI evaluations are advisory — final decisions rest with the committee."
        "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Load & filter data
# ---------------------------------------------------------------------------

all_candidates = load_evaluations(semester)

filtered_candidates = [
    c
    for c in all_candidates
    if c["status"] in status_filter
    and (
        not search_query
        or search_query.lower() in c.get("school", "").lower()
        or search_query.lower() in c.get("candidate_id", "").lower()
        or search_query.lower() in " ".join(c.get("verdict_pros", [])).lower()
    )
]


# ---------------------------------------------------------------------------
# Header & Stats
# ---------------------------------------------------------------------------

st.markdown(
    '<div style="font-size:1.5rem;font-weight:800;margin-bottom:0.5rem;">'
    "Candidate Review"
    "</div>",
    unsafe_allow_html=True,
)

stat_cols = st.columns(5)

total = len(all_candidates)
admits = sum(1 for c in all_candidates if c["status"] == "admit")
rejects = sum(1 for c in all_candidates if c["status"] == "reject")
discusses = sum(1 for c in all_candidates if c["status"] == "discuss")
pending = sum(1 for c in all_candidates if c["status"] == "pending")

with stat_cols[0]:
    st.markdown(
        f'<div class="stat-card">'
        f'<div class="stat-number" style="color:#1e293b;">{total}</div>'
        f'<div class="stat-label">Total</div></div>',
        unsafe_allow_html=True,
    )
with stat_cols[1]:
    st.markdown(
        f'<div class="stat-card">'
        f'<div class="stat-number" style="color:#16a34a;">{admits}</div>'
        f'<div class="stat-label">Admit</div></div>',
        unsafe_allow_html=True,
    )
with stat_cols[2]:
    st.markdown(
        f'<div class="stat-card">'
        f'<div class="stat-number" style="color:#dc2626;">{rejects}</div>'
        f'<div class="stat-label">Reject</div></div>',
        unsafe_allow_html=True,
    )
with stat_cols[3]:
    st.markdown(
        f'<div class="stat-card">'
        f'<div class="stat-number" style="color:#d97706;">{discusses}</div>'
        f'<div class="stat-label">Discuss</div></div>',
        unsafe_allow_html=True,
    )
with stat_cols[4]:
    st.markdown(
        f'<div class="stat-card">'
        f'<div class="stat-number" style="color:#64748b;">{pending}</div>'
        f'<div class="stat-label">Pending</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("")

# ---------------------------------------------------------------------------
# Candidate list
# ---------------------------------------------------------------------------

if not filtered_candidates:
    st.info("No candidates match the current filters.")
    st.stop()

for candidate in filtered_candidates:
    cid = candidate["candidate_id"]
    is_selected = st.session_state.selected_candidate == cid
    display_name = cid.replace("_", " ").title()
    badge = _badge_html(candidate["status"])
    conf = candidate["confidence"]
    conf_pct = int(conf * 100)
    conf_color = _confidence_color(conf)
    gpa_raw = candidate.get("gpa", "")
    gpa_max = candidate.get("gpa_max", "")
    gpa_normalized = candidate.get("gpa_normalized", 0.0)
    _has_gpa = gpa_raw and gpa_raw != "N/A" and gpa_raw != "n/a"
    _has_max = gpa_max and gpa_max != "N/A" and gpa_max != "n/a"
    _has_norm = isinstance(gpa_normalized, (int, float)) and gpa_normalized > 0
    if _has_gpa and _has_max and _has_norm:
        gpa_display = f"GPA: {gpa_raw}/{gpa_max} ({gpa_normalized:.0f}/100)"
    elif _has_gpa and _has_max:
        gpa_display = f"GPA: {gpa_raw}/{gpa_max}"
    elif _has_gpa:
        gpa_display = f"GPA: {gpa_raw}"
    else:
        gpa_display = ""
    committee = candidate.get("committee_decision", "")
    committee_badge = (
        f' <span style="font-size:0.7rem;color:#6b7280;">Committee: {committee}</span>'
        if committee
        else ""
    )

    verdict_pros = candidate.get("verdict_pros", [])
    verdict_cons = candidate.get("verdict_cons", [])

    # Card header (HTML only — no markdown content here)
    border_style = "border-color:#3b82f6;border-width:2px;" if is_selected else ""
    school_span = (
        f'<span style="color:#64748b;font-size:0.85rem;">{candidate["school"]}</span>'
        if candidate.get("school")
        else ""
    )
    gpa_span = (
        f'<span style="color:#64748b;font-size:0.8rem;">{gpa_display}</span>'
        if gpa_display
        else ""
    )
    # Minor recommendation badge
    minor_rec = candidate.get("minor_recommendation")
    minor_badge = ""
    if minor_rec and isinstance(minor_rec, dict):
        primary = minor_rec.get("primary_minor", "")
        if primary:
            minor_badge = (
                f'<span style="background:#dbeafe;color:#1e40af;padding:2px 8px;'
                f'border-radius:12px;font-size:0.7rem;font-weight:600;">'
                f"Minor: {_html_escape(primary)}</span>"
            )

    card_header = (
        f'<div class="candidate-card" style="{border_style}">'
        f'<div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;">'
        f'<strong style="font-size:1.05rem;">{display_name}</strong>'
        f"{badge}"
        f"{minor_badge}"
        f"{school_span}"
        f"{gpa_span}"
        f"{committee_badge}"
        f'<span style="margin-left:auto;font-size:0.8rem;color:{conf_color};font-weight:600;">'
        f"Confidence: {conf_pct}%</span>"
        f"</div>"
        f"</div>"
    )
    st.markdown(card_header, unsafe_allow_html=True)

    # Pros/cons summary
    if verdict_pros or verdict_cons:
        pros_col, cons_col = st.columns(2)
        with pros_col:
            for pro in verdict_pros:
                st.markdown(f":green[+] {pro}")
        with cons_col:
            for con in verdict_cons:
                st.markdown(f":red[-] {con}")

    # View details button
    col_btn, col_spacer = st.columns([1, 5])
    with col_btn:
        if is_selected:
            if st.button("Close Details", key=f"close_{cid}", type="secondary"):
                st.session_state.selected_candidate = None
                st.rerun()
        elif st.button("View Details", key=f"view_{cid}", type="primary"):
            st.session_state.selected_candidate = cid
            st.rerun()

    # ---------------------------------------------------------------------------
    # Expanded detail panel
    # ---------------------------------------------------------------------------

    if is_selected:
        st.markdown("---")

        tab_analysis, tab_chat, tab_docs = st.tabs(
            ["🔍 Agent Analysis", "💬 Chat", "📁 Documents"],
        )

        # ---- Tab 1: Agent Analysis ----
        with tab_analysis:
            moderator = candidate.get("moderator", {})
            mod_pros = moderator.get("pros", [])
            mod_cons = moderator.get("cons", [])
            mod_decision = moderator.get("decision", "")
            mod_composite = moderator.get("composite", 0.0)

            # Moderator synthesis — pros/cons layout
            st.markdown(
                '<div class="moderator-panel">'
                '<div style="font-size:0.8rem;font-weight:700;color:#1e40af;'
                'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.5rem;">'
                f"Chair Synthesis &mdash; {mod_decision} "
                f"(composite: {mod_composite:.1f}/10)</div>"
                "</div>",
                unsafe_allow_html=True,
            )
            mod_pro_col, mod_con_col = st.columns(2)
            with mod_pro_col:
                st.markdown("**Strengths**")
                for pro in mod_pros:
                    st.markdown(f":green[+] {_html_escape(pro)}")
            with mod_con_col:
                st.markdown("**Concerns**")
                for con in mod_cons:
                    st.markdown(f":red[-] {_html_escape(con)}")
                if not mod_cons:
                    st.markdown("_None identified_")

            # Minor recommendation
            if minor_rec and isinstance(minor_rec, dict):
                recommended = minor_rec.get("recommended", [])
                if recommended:
                    st.markdown("**Recommended Minors**")
                    minor_cols = st.columns(len(recommended))
                    for j, rec in enumerate(recommended):
                        with minor_cols[j]:
                            m_name = rec.get("minor_name", "")
                            m_section = rec.get("section_code", "")
                            m_score = rec.get("fit_score", 0)
                            m_reason = rec.get("reasoning", "")
                            rank_label = ["1st", "2nd", "3rd"][j] if j < 3 else f"{j + 1}th"
                            score_color = _confidence_color(m_score / 10.0)
                            st.markdown(
                                f'<div class="agent-card">'
                                f'<div class="agent-role">{rank_label} choice</div>'
                                f'<div style="margin:0.4rem 0;">'
                                f'<strong>{_html_escape(m_name)}</strong> '
                                f'<span style="color:#64748b;">({m_section})</span>'
                                f"</div>"
                                f'<div style="font-size:0.85rem;">Fit: '
                                f'<span style="color:{score_color};font-weight:700;">'
                                f"{m_score}/10</span></div>"
                                f'<div style="font-size:0.8rem;color:#475569;'
                                f'margin-top:0.3rem;">{_html_escape(m_reason)}</div>'
                                f"</div>",
                                unsafe_allow_html=True,
                            )

            # Per-agent evaluations
            agent_cols = st.columns(len(candidate.get("evaluations", [])) or 1)

            for i, evaluation in enumerate(candidate.get("evaluations", [])):
                with agent_cols[i]:
                    role = evaluation["role"]
                    decision = evaluation["decision"]
                    conf = evaluation["confidence"]
                    conf_pct = int(conf * 100)
                    conf_color = _confidence_color(conf)

                    # Decision color
                    dec_colors = {
                        "ACCEPT": "#16a34a",
                        "REJECT": "#dc2626",
                        "DISCUSS": "#d97706",
                        "WAITLIST": "#d97706",
                    }
                    dec_color = dec_colors.get(decision, "#64748b")

                    st.markdown(
                        f'<div class="agent-card">'
                        f'<div class="agent-role">{_role_icon(role)} {role}</div>'
                        f'<div style="margin:0.5rem 0;">'
                        f'<span style="font-size:1.1rem;font-weight:700;color:{dec_color};">'
                        f"{decision}</span>"
                        f'<span style="font-size:0.8rem;color:{conf_color};margin-left:0.5rem;">'
                        f"{conf_pct}%</span>"
                        f"</div>"
                        f"{_confidence_bar_html(conf)}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                    # Pros/cons per dimension
                    dim_justifications = evaluation.get("justifications", {})
                    for dim_name, dim_j in dim_justifications.items():
                        dim_label = dim_name.replace("_", " ").title()
                        st.markdown(f"**{dim_label}**")
                        if isinstance(dim_j, dict):
                            for pro in dim_j.get("pros", []):
                                st.markdown(f":green[+] {pro}")
                            for con in dim_j.get("cons", []):
                                st.markdown(f":red[-] {con}")
                        else:
                            st.markdown(str(dim_j))

                    # Scores
                    scores = evaluation.get("scores", {})
                    if scores:
                        st.markdown(
                            _score_grid_html(scores), unsafe_allow_html=True,
                        )

                    # Document references
                    refs = evaluation.get("document_references", [])
                    if refs:
                        st.markdown(
                            '<div style="margin-top:0.75rem;font-size:0.75rem;'
                            'font-weight:600;color:#64748b;text-transform:uppercase;">'
                            "Referenced Documents</div>",
                            unsafe_allow_html=True,
                        )
                        for ref in refs:
                            icon = _doc_type_icon(ref["doc_type"])
                            label = _doc_type_label(ref["doc_type"])
                            st.markdown(
                                f'<div class="doc-ref">'
                                f"{icon} {label}"
                                f"</div>"
                                f'<div style="font-size:0.8rem;color:#475569;'
                                f'margin-left:0.5rem;margin-bottom:0.5rem;">'
                                f'{ref["note"]}</div>',
                                unsafe_allow_html=True,
                            )

            # ---- Debate transcripts (collapsible) ----
            debates = candidate.get("debates", [])
            if debates:
                n_debates = len(debates)
                with st.expander(
                    f"View Deliberation Debates ({n_debates} conflict{'s' if n_debates > 1 else ''})",
                    expanded=False,
                ):
                    for debate in debates:
                        dimension = debate.get("conflict_dimension", "unknown")
                        dim_label = _html_escape(dimension.replace("_", " ").title())
                        entries = debate.get("entries", [])

                        entry_parts: list[str] = []
                        for entry in entries:
                            role = entry.get("role", "")
                            round_num = entry.get("round_number", 0)
                            argument = _html_escape(entry.get("argument", ""))
                            icon = _role_icon(role)
                            entry_parts.append(
                                f'<div class="debate-entry">'
                                f'<div class="debate-entry-header">'
                                f'<span class="debate-role">{icon} {_html_escape(role)}</span>'
                                f'<span class="debate-round">Round {round_num}</span>'
                                f"</div>"
                                f'<div class="debate-argument">{argument}</div>'
                                f"</div>",
                            )

                        st.markdown(
                            f'<div class="debate-topic">'
                            f'<div class="debate-topic-header">Conflict: {dim_label}</div>'
                            + "".join(entry_parts)
                            + "</div>",
                            unsafe_allow_html=True,
                        )

        # ---- Tab 2: Chat ----
        with tab_chat:
            chat_key = cid

            # Initialize chat history for this candidate
            if chat_key not in st.session_state.chat_histories:
                st.session_state.chat_histories[chat_key] = []

                # Add welcome message
                if not candidate.get("verdict_pros") and not candidate.get("evaluations"):
                    welcome = (
                        "⚠️ **Limited information available for this candidate.** "
                        "The evaluation was incomplete due to missing documents. "
                        "Answers may be very limited."
                    )
                else:
                    welcome = (
                        f"Hello! I can answer questions about **{display_name}** "
                        f"based on their anonymized documents and agent evaluations. "
                        f"Try asking about their academic record, motivation, "
                        f"recommendations, or technical skills."
                    )
                st.session_state.chat_histories[chat_key].append(
                    {"role": "assistant", "content": welcome},
                )

            # Display chat history
            for message in st.session_state.chat_histories[chat_key]:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Chat input
            user_input = st.chat_input(
                f"Ask about {display_name}...", key=f"chat_input_{cid}",
            )

            if user_input:
                # Add user message
                st.session_state.chat_histories[chat_key].append(
                    {"role": "user", "content": user_input},
                )
                with st.chat_message("user"):
                    st.markdown(user_input)

                # Generate mock response
                response = _mock_chat_response(candidate, user_input)
                st.session_state.chat_histories[chat_key].append(
                    {"role": "assistant", "content": response},
                )
                with st.chat_message("assistant"):
                    st.markdown(response)

        # ---- Tab 3: Documents (Advanced View) ----
        with tab_docs:
            available_docs = candidate.get("documents", [])

            if not available_docs:
                st.info("No documents available for this candidate.")
            else:
                st.markdown(
                    '<div class="section-header">Available Documents</div>',
                    unsafe_allow_html=True,
                )

                doc_cols = st.columns(min(len(available_docs), 4))
                for i, doc_type in enumerate(available_docs):
                    with doc_cols[i % 4]:
                        icon = _doc_type_icon(doc_type)
                        label = _doc_type_label(doc_type)
                        st.markdown(
                            f'<div style="background:#f8fafc;border:1px solid #e2e8f0;'
                            f"border-radius:8px;padding:0.8rem;text-align:center;"
                            f'margin-bottom:0.5rem;">'
                            f'<div style="font-size:1.5rem;">{icon}</div>'
                            f'<div style="font-size:0.8rem;font-weight:600;'
                            f'color:#334155;margin-top:0.3rem;">{label}</div>'
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                st.markdown("")
                st.info(
                    "📌 **Document viewer integration coming soon.** "
                    "This tab will display the full PDF, extracted text, and "
                    "anonymized versions using the existing document pipeline. "
                    "For now, use the legacy viewer (`uv run poe dashboard`) "
                    "to inspect individual documents.",
                )

        st.markdown("---")
