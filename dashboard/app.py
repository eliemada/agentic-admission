"""MTE Admission Pipeline — Dossier Viewer.

Interactive dashboard showing the PDF → Markdown → Anonymized pipeline
for MTE admission dossiers at EPFL.

Run with:
    uv run streamlit run dashboard/app.py
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT = Path(__file__).resolve().parent.parent
_PDF_ROOT = _PROJECT / "data" / "raw" / "applications" / "dossiers"
_TEXT_ROOT = _PROJECT / "data" / "processed" / "texts"
_ANON_ROOT = _PROJECT / "data" / "processed" / "anonymized"

# ---------------------------------------------------------------------------
# PII tag styling
# ---------------------------------------------------------------------------

_PII_COLORS: dict[str, str] = {
    "PERSON": "#ef4444",
    "EMAIL": "#3b82f6",
    "PHONE": "#8b5cf6",
    "DATE": "#f59e0b",
    "DOB": "#f97316",
    "ADDRESS": "#10b981",
    "AVS": "#ec4899",
    "SCIPER": "#6366f1",
    "ORG": "#14b8a6",
    "URL": "#64748b",
    "IBAN": "#e11d48",
    "PII": "#6b7280",
    "LOCATION": "#22c55e",
}


def _highlight_pii(text: str) -> str:
    """Replace <TAG> and <TAG_detail> placeholders with colored HTML spans."""

    def _replace(match: re.Match[str]) -> str:
        tag = match.group(1)
        # Strip detail suffix (e.g., DOB_1995 → DOB)
        base_tag = tag.split("_")[0] if "_" in tag else tag
        color = _PII_COLORS.get(base_tag, _PII_COLORS["PII"])
        return (
            f'<span style="background-color:{color};color:white;'
            f'padding:2px 6px;border-radius:4px;font-size:0.85em;'
            f'font-weight:600;letter-spacing:0.02em;">'
            f"&lt;{tag}&gt;</span>"
        )

    return re.sub(r"<([A-Z][A-Z0-9_]*)>", _replace, text)


def _count_pii_tags(text: str) -> dict[str, int]:
    """Count PII placeholder occurrences by type."""
    tags = re.findall(r"<([A-Z][A-Z0-9_]*)>", text)
    counts: dict[str, int] = {}
    for tag in tags:
        base = tag.split("_")[0] if "_" in tag else tag
        counts[base] = counts.get(base, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def _list_semesters() -> list[str]:
    """Return sorted semester directories present in the text root."""
    if not _TEXT_ROOT.exists():
        return []
    return sorted(d.name for d in _TEXT_ROOT.iterdir() if d.is_dir())


def _list_candidates(semester: str) -> list[str]:
    """Return sorted candidate directories for a semester."""
    sem_dir = _TEXT_ROOT / semester
    if not sem_dir.exists():
        return []
    return sorted(d.name for d in sem_dir.iterdir() if d.is_dir())


def _list_documents(semester: str, candidate: str) -> list[str]:
    """Return sorted document directories for a candidate."""
    cand_dir = _TEXT_ROOT / semester / candidate
    if not cand_dir.exists():
        return []
    return sorted(d.name for d in cand_dir.iterdir() if d.is_dir())


def _find_file(root: Path, semester: str, candidate: str, document: str, ext: str) -> Path | None:
    """Find first file with given extension in the document directory."""
    doc_dir = root / semester / candidate / document
    if not doc_dir.exists():
        return None
    files = list(doc_dir.glob(f"*{ext}"))
    return files[0] if files else None


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MTE Admission — Dossier Viewer",
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
    /* Clean header */
    .main .block-container { padding-top: 2rem; max-width: 100%; }

    /* Sidebar styling */
    [data-testid="stSidebar"] { background-color: #0f172a; }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    [data-testid="stSidebar"] .stSelectbox label { color: #94a3b8 !important; font-weight: 600; }

    /* Panel headers */
    .panel-header {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #64748b;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e2e8f0;
        margin-bottom: 1rem;
    }

    /* Markdown panel */
    .md-panel {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1.5rem;
        height: 75vh;
        overflow-y: auto;
        font-size: 0.9rem;
        line-height: 1.7;
    }

    /* Stat cards */
    .stat-card {
        background: linear-gradient(135deg, #1e293b, #334155);
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        color: white;
    }
    .stat-card .number {
        font-size: 2rem;
        font-weight: 800;
        line-height: 1;
    }
    .stat-card .label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #94a3b8;
        margin-top: 0.3rem;
    }

    /* PII legend */
    .pii-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 0.5rem;
    }
    .pii-badge {
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        color: white;
    }

    /* Hide Streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar — Navigation
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## 🎓 MTE Admission")
    st.markdown("##### Dossier Pipeline Viewer")
    st.markdown("---")

    semesters = _list_semesters()
    if not semesters:
        st.error("No data found. Check `data/processed/texts/`.")
        st.stop()

    semester = st.selectbox("Semester", semesters, index=0)

    candidates = _list_candidates(semester)
    if not candidates:
        st.warning("No candidates for this semester.")
        st.stop()

    candidate = st.selectbox(
        "Candidate",
        candidates,
        index=0,
        format_func=lambda x: x.replace("_", " ").title(),
    )

    documents = _list_documents(semester, candidate)
    if not documents:
        st.warning("No documents for this candidate.")
        st.stop()

    # Clean up document names for display
    def _doc_label(name: str) -> str:
        """Strip the hash suffix for cleaner display."""
        match = re.match(r"(\d+ - .+?)_[BF]\d+$", name)
        return match.group(1) if match else name

    document = st.selectbox(
        "Document",
        documents,
        index=0,
        format_func=_doc_label,
    )

    st.markdown("---")

    # Quick stats
    text_count = sum(1 for _ in _TEXT_ROOT.rglob("*.md")) if _TEXT_ROOT.exists() else 0
    anon_count = sum(1 for _ in _ANON_ROOT.rglob("*.md")) if _ANON_ROOT.exists() else 0

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f'<div class="stat-card"><div class="number">{text_count:,}</div>'
            f'<div class="label">Extracted</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="stat-card"><div class="number">{anon_count:,}</div>'
            f'<div class="label">Anonymized</div></div>',
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Resolve files
# ---------------------------------------------------------------------------

pdf_path = _find_file(_PDF_ROOT, semester, candidate, document, ".pdf")
text_path = _find_file(_TEXT_ROOT, semester, candidate, document, ".md")
anon_path = _find_file(_ANON_ROOT, semester, candidate, document, ".md")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    f"### {candidate.replace('_', ' ').title()} — "
    f"*{_doc_label(document)}*"
)

# ---------------------------------------------------------------------------
# Three-column layout
# ---------------------------------------------------------------------------

col_pdf, col_text, col_anon = st.columns([1, 1, 1], gap="medium")

# --- PDF column ---
with col_pdf:
    st.markdown('<div class="panel-header">📄 Original PDF</div>', unsafe_allow_html=True)
    if pdf_path and pdf_path.exists():
        pdf_bytes = pdf_path.read_bytes()
        b64 = base64.b64encode(pdf_bytes).decode()
        pdf_html = (
            f'<iframe src="data:application/pdf;base64,{b64}" '
            f'width="100%" height="75vh" style="border:1px solid #e2e8f0;'
            f'border-radius:8px;" type="application/pdf"></iframe>'
        )
        st.markdown(pdf_html, unsafe_allow_html=True)
    else:
        st.info("PDF not available locally. Sync from cluster to view.")

# --- Markdown column ---
with col_text:
    st.markdown(
        '<div class="panel-header">📝 Extracted Markdown</div>',
        unsafe_allow_html=True,
    )
    if text_path and text_path.exists():
        text_content = text_path.read_text(encoding="utf-8")
        st.markdown(
            f'<div class="md-panel">{text_content}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("Text not extracted for this document.")

# --- Anonymized column ---
with col_anon:
    st.markdown(
        '<div class="panel-header">🔒 Anonymized</div>',
        unsafe_allow_html=True,
    )
    if anon_path and anon_path.exists():
        anon_content = anon_path.read_text(encoding="utf-8")
        highlighted = _highlight_pii(anon_content)
        st.markdown(
            f'<div class="md-panel">{highlighted}</div>',
            unsafe_allow_html=True,
        )

        # PII statistics
        pii_counts = _count_pii_tags(anon_content)
        if pii_counts:
            st.markdown("---")
            total = sum(pii_counts.values())
            st.markdown(f"**{total} PII entities** detected:")
            legend_html = '<div class="pii-legend">'
            for tag, count in pii_counts.items():
                color = _PII_COLORS.get(tag, _PII_COLORS["PII"])
                legend_html += (
                    f'<span class="pii-badge" style="background:{color};">'
                    f"{tag}: {count}</span>"
                )
            legend_html += "</div>"
            st.markdown(legend_html, unsafe_allow_html=True)
    else:
        st.info("Not yet anonymized. Run the anonymization pipeline on the cluster.")
