"""MTE Admission Pipeline — Dossier Viewer.

Interactive dashboard showing the PDF → Markdown → Anonymized pipeline
for MTE admission dossiers at EPFL.

Run with:
    uv run poe dashboard
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
        base_tag = tag.split("_")[0] if "_" in tag else tag
        color = _PII_COLORS.get(base_tag, _PII_COLORS["PII"])
        return (
            f'<span style="background-color:{color};color:white;'
            f"padding:2px 6px;border-radius:4px;font-size:0.85em;"
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
    if not _TEXT_ROOT.exists():
        return []
    return sorted(d.name for d in _TEXT_ROOT.iterdir() if d.is_dir())


def _list_candidates(semester: str) -> list[str]:
    sem_dir = _TEXT_ROOT / semester
    if not sem_dir.exists():
        return []
    return sorted(d.name for d in sem_dir.iterdir() if d.is_dir())


def _list_documents(semester: str, candidate: str) -> list[str]:
    cand_dir = _TEXT_ROOT / semester / candidate
    if not cand_dir.exists():
        return []
    return sorted(d.name for d in cand_dir.iterdir() if d.is_dir())


def _find_file(root: Path, semester: str, candidate: str, document: str, ext: str) -> Path | None:
    doc_dir = root / semester / candidate / document
    if not doc_dir.exists():
        return None
    files = list(doc_dir.glob(f"*{ext}"))
    return files[0] if files else None


def _doc_label(name: str) -> str:
    """Strip the hash suffix for cleaner display."""
    match = re.match(r"(\d+ - .+?)_[BF]\d+$", name)
    return match.group(1) if match else name


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MTE Admission — Dossier Viewer",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
<style>
    .main .block-container {
        padding-top: 1rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
        max-width: 100%;
    }

    /* Navigation bar */
    .nav-bar {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 0.8rem 1.2rem;
        background: linear-gradient(135deg, #0f172a, #1e293b);
        border-radius: 12px;
        margin-bottom: 1rem;
        flex-wrap: wrap;
    }
    .nav-bar .brand {
        font-size: 1.1rem;
        font-weight: 800;
        color: white;
        white-space: nowrap;
        margin-right: 0.5rem;
    }

    /* Panel headers */
    .panel-header {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #64748b;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e2e8f0;
        margin-bottom: 0.75rem;
    }

    /* Text panels */
    .md-panel {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1.5rem;
        height: 800px;
        overflow-y: auto;
        font-size: 0.9rem;
        line-height: 1.7;
    }

    /* PII legend */
    .pii-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin-top: 0.5rem;
    }
    .pii-badge {
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
        color: white;
    }

    /* Hide Streamlit chrome */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }

    /* Make selectboxes inline-friendly */
    .stSelectbox { min-width: 0; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Top navigation bar (replaces sidebar)
# ---------------------------------------------------------------------------

semesters = _list_semesters()
if not semesters:
    st.error("No data found. Check `data/processed/texts/`.")
    st.stop()

nav_cols = st.columns([2, 2, 4, 2])

with nav_cols[0]:
    semester = st.selectbox("Semester", semesters, index=0, label_visibility="collapsed")

candidates = _list_candidates(semester)
if not candidates:
    st.warning("No candidates for this semester.")
    st.stop()

with nav_cols[1]:
    candidate = st.selectbox(
        "Candidate",
        candidates,
        index=0,
        format_func=lambda x: x.replace("_", " ").title(),
        label_visibility="collapsed",
    )

documents = _list_documents(semester, candidate)
if not documents:
    st.warning("No documents for this candidate.")
    st.stop()

with nav_cols[2]:
    document = st.selectbox(
        "Document",
        documents,
        index=0,
        format_func=_doc_label,
        label_visibility="collapsed",
    )

# Title
with nav_cols[3]:
    st.markdown(
        f"**{candidate.replace('_', ' ').title()}**",
        help=f"{semester} — {_doc_label(document)}",
    )

# ---------------------------------------------------------------------------
# Resolve files
# ---------------------------------------------------------------------------

pdf_path = _find_file(_PDF_ROOT, semester, candidate, document, ".pdf")
text_path = _find_file(_TEXT_ROOT, semester, candidate, document, ".md")
anon_path = _find_file(_ANON_ROOT, semester, candidate, document, ".md")

# ---------------------------------------------------------------------------
# View mode selector
# ---------------------------------------------------------------------------

view_mode = st.radio(
    "View",
    ["Split View", "PDF Focus", "Comparison"],
    horizontal=True,
    label_visibility="collapsed",
)

# ---------------------------------------------------------------------------
# PDF rendering helper
# ---------------------------------------------------------------------------


def _render_pdf(path: Path) -> None:
    """Render PDF pages as images using PyMuPDF for reliable display."""
    import fitz  # PyMuPDF

    doc = fitz.open(str(path))
    for i, page in enumerate(doc):
        # Render at 2x for crisp display
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("png")
        st.image(img_bytes, use_container_width=True, caption=f"Page {i + 1} of {len(doc)}")
    doc.close()


def _render_text(path: Path) -> None:
    """Render a markdown file using native Streamlit markdown in a scrollable container."""
    content = path.read_text(encoding="utf-8")
    with st.container(height=810):
        st.markdown(content)


def _render_anon(path: Path) -> None:
    """Render an anonymized markdown file with PII highlighting."""
    content = path.read_text(encoding="utf-8")
    highlighted = _highlight_pii(content)
    with st.container(height=810):
        st.markdown(highlighted, unsafe_allow_html=True)

    # PII stats
    pii_counts = _count_pii_tags(content)
    if pii_counts:
        total = sum(pii_counts.values())
        legend = f'<div style="margin-top:0.5rem;font-size:0.8rem;color:#475569;"><strong>{total} PII entities</strong></div>'
        legend += '<div class="pii-legend">'
        for tag, count in pii_counts.items():
            color = _PII_COLORS.get(tag, _PII_COLORS["PII"])
            legend += f'<span class="pii-badge" style="background:{color};">{tag}: {count}</span>'
        legend += "</div>"
        st.markdown(legend, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Layout rendering
# ---------------------------------------------------------------------------

if view_mode == "Split View":
    col_pdf, col_text, col_anon = st.columns([1, 1, 1], gap="medium")

    with col_pdf:
        st.markdown('<div class="panel-header">📄 Original PDF</div>', unsafe_allow_html=True)
        if pdf_path and pdf_path.exists():
            with st.container(height=810):
                _render_pdf(pdf_path)
        else:
            st.info("PDF not available locally.")

    with col_text:
        st.markdown('<div class="panel-header">📝 Extracted Text</div>', unsafe_allow_html=True)
        if text_path and text_path.exists():
            _render_text(text_path)
        else:
            st.info("Text not extracted.")

    with col_anon:
        st.markdown('<div class="panel-header">🔒 Anonymized</div>', unsafe_allow_html=True)
        if anon_path and anon_path.exists():
            _render_anon(anon_path)
        else:
            st.info("Not yet anonymized.")

elif view_mode == "PDF Focus":
    col_pdf, col_right = st.columns([3, 2], gap="medium")

    with col_pdf:
        st.markdown('<div class="panel-header">📄 Original PDF</div>', unsafe_allow_html=True)
        if pdf_path and pdf_path.exists():
            with st.container(height=810):
                _render_pdf(pdf_path)
        else:
            st.info("PDF not available locally.")

    with col_right:
        tab_text, tab_anon = st.tabs(["📝 Extracted Text", "🔒 Anonymized"])
        with tab_text:
            if text_path and text_path.exists():
                _render_text(text_path)
            else:
                st.info("Text not extracted.")
        with tab_anon:
            if anon_path and anon_path.exists():
                _render_anon(anon_path)
            else:
                st.info("Not yet anonymized.")

elif view_mode == "Comparison":
    col_left, col_right = st.columns([1, 1], gap="medium")

    with col_left:
        st.markdown(
            '<div class="panel-header">📝 Extracted Text (Original)</div>',
            unsafe_allow_html=True,
        )
        if text_path and text_path.exists():
            _render_text(text_path)
        else:
            st.info("Text not extracted.")

    with col_right:
        st.markdown(
            '<div class="panel-header">🔒 Anonymized (PII Redacted)</div>',
            unsafe_allow_html=True,
        )
        if anon_path and anon_path.exists():
            _render_anon(anon_path)
        else:
            st.info("Not yet anonymized.")
