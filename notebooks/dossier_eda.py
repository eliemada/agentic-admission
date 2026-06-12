# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo>=0.20.2",
#     "pandas==3.0.1",
# ]
# ///

import marimo

__generated_with = "0.20.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    mo.md(
        """
        # Dossier Inventory — Exploratory Analysis

        Mapping the contents of **student application dossiers** across all
        semesters (2020–2026) in `data/raw/applications/dossiers/`.
        """
    )
    return (mo,)


@app.cell
def _(mo):
    from pathlib import Path

    DOSSIER_ROOT = Path("data/raw/applications/dossiers")
    semesters = sorted([d for d in DOSSIER_ROOT.iterdir() if d.is_dir()])

    candidates = []
    for _sem in semesters:
        for cand in sorted(_sem.iterdir()):
            if cand.is_dir():
                candidates.append((_sem.name, cand))

    mo.md(
        f"Found **{len(semesters)}** semesters and "
        f"**{len(candidates)}** candidate dossiers in `{DOSSIER_ROOT}`"
    )
    return DOSSIER_ROOT, candidates, semesters


@app.cell
def _(mo):
    mo.md("""
    ## 1. File inventory
    """)


@app.cell
def _(candidates, mo):
    import re

    import pandas as pd

    DOC_TYPE_PATTERN = re.compile(r"^\d+ - Cand\. Master (.+?)(?:_[BF]\d+)")

    rows = []
    for semester, cand_dir in candidates:
        candidate = cand_dir.name
        for item in sorted(cand_dir.rglob("*")):
            if not item.is_file():
                continue
            parent = item.parent.name
            m = DOC_TYPE_PATTERN.match(parent)
            doc_type = m.group(1).strip() if m else parent
            rows.append({
                "semester": semester,
                "candidate": candidate,
                "doc_type": doc_type,
                "filename": item.name,
                "extension": item.suffix.lower(),
                "size_kb": round(item.stat().st_size / 1024, 1),
                "rel_path": str(item.relative_to(cand_dir)),
            })

    inventory = pd.DataFrame(rows)
    mo.md(
        f"Scanned **{len(inventory)}** files across "
        f"**{inventory['candidate'].nunique()}** candidates "
        f"in **{inventory['semester'].nunique()}** semesters"
    )
    return inventory, pd


@app.cell
def _(inventory, mo):
    mo.ui.table(inventory, label="Full file inventory")


@app.cell
def _(mo):
    mo.md("""
    ## 2. Candidates and files per semester
    """)


@app.cell
def _(inventory):
    import altair as alt

    sem_stats = (
        inventory.groupby("semester")
        .agg(
            candidates=("candidate", "nunique"),
            files=("filename", "count"),
        )
        .reset_index()
    )

    chart_cands_per_sem = (
        alt.Chart(sem_stats)
        .mark_bar()
        .encode(
            x=alt.X("semester:N", sort=None, title="Semester"),
            y=alt.Y("candidates:Q", title="Number of candidates"),
            tooltip=["semester", "candidates", "files"],
        )
        .properties(width=700, height=350, title="Candidates per semester")
    )
    chart_cands_per_sem
    return alt, sem_stats


@app.cell
def _(alt, sem_stats):
    chart_files_per_sem = (
        alt.Chart(sem_stats)
        .mark_bar()
        .encode(
            x=alt.X("semester:N", sort=None, title="Semester"),
            y=alt.Y("files:Q", title="Number of files"),
            tooltip=["semester", "candidates", "files"],
        )
        .properties(width=700, height=350, title="Total files per semester")
    )
    chart_files_per_sem


@app.cell
def _(mo):
    mo.md("""
    ## 3. Files per candidate (distribution)
    """)


@app.cell
def _(alt, inventory):
    files_per_cand = (
        inventory.groupby(["semester", "candidate"])
        .size()
        .reset_index(name="file_count")
    )

    chart_files_hist = (
        alt.Chart(files_per_cand)
        .mark_bar()
        .encode(
            x=alt.X("file_count:Q", bin=alt.Bin(maxbins=25), title="Files per candidate"),
            y=alt.Y("count():Q", title="Number of candidates"),
            tooltip=["count()"],
        )
        .properties(width=700, height=350, title="Distribution of files per candidate")
    )
    chart_files_hist
    return (files_per_cand,)


@app.cell
def _(alt, files_per_cand):
    chart_files_box = (
        alt.Chart(files_per_cand)
        .mark_boxplot()
        .encode(
            x=alt.X("semester:N", sort=None, title="Semester"),
            y=alt.Y("file_count:Q", title="Files per candidate"),
        )
        .properties(width=700, height=350, title="Files per candidate by semester")
    )
    chart_files_box


@app.cell
def _(mo):
    mo.md("""
    ## 4. Document types across dossiers
    """)


@app.cell
def _(alt, inventory):
    doc_types = inventory["doc_type"].value_counts().reset_index()
    doc_types.columns = ["doc_type", "count"]

    chart_doc_types = (
        alt.Chart(doc_types)
        .mark_bar()
        .encode(
            y=alt.Y("doc_type:N", sort="-x", title="Document type"),
            x=alt.X("count:Q", title="Occurrences"),
            tooltip=["doc_type", "count"],
        )
        .properties(width=600, height=400, title="Document type frequency (all semesters)")
    )
    chart_doc_types


@app.cell
def _(mo):
    mo.md("""
    ## 5. Completeness of required documents
    """)


@app.cell
def _(alt, inventory, pd):
    EXPECTED_DOCS = [
        "Synthese de la candidature",
        "Lettre de motivation",
        "CV",
        "Releve de notes institution #1",
        "Copie de passeport ou carte d'identite",
    ]

    # Per-semester completeness rate for each required doc
    completeness_rows = []
    for _sem in sorted(inventory["semester"].unique()):
        _sem_inv = inventory[inventory["semester"] == _sem]
        _sem_cands = _sem_inv["candidate"].unique()
        for doc in EXPECTED_DOCS:
            cands_with = _sem_inv[_sem_inv["doc_type"] == doc]["candidate"].nunique()
            completeness_rows.append({
                "semester": _sem,
                "doc_type": doc,
                "pct": round(cands_with / len(_sem_cands) * 100, 1),
            })

    completeness = pd.DataFrame(completeness_rows)

    chart_completeness = (
        alt.Chart(completeness)
        .mark_rect()
        .encode(
            x=alt.X("semester:N", sort=None, title="Semester"),
            y=alt.Y("doc_type:N", sort=EXPECTED_DOCS, title="Required document"),
            color=alt.Color(
                "pct:Q",
                scale=alt.Scale(scheme="redyellowgreen", domain=[0, 100]),
                title="% present",
            ),
            tooltip=["semester", "doc_type", "pct"],
        )
        .properties(width=700, height=250, title="Required document completeness by semester")
    )
    chart_completeness


@app.cell
def _(mo):
    mo.md("""
    ## 6. Optional documents
    """)


@app.cell
def _(alt, inventory):
    OPTIONAL_TYPES = [
        "Referent #1 Lettre de recommandation",
        "Referent #2 Lettre de recommandation",
        "Referent #3 Lettre de recommandation",
        "Diplome institution #1",
        "Certificat linguistique (TOEFL ou autres)",
        "Resultats GRE",
        "Autres documents",
    ]

    optional_counts = (
        inventory[inventory["doc_type"].isin(OPTIONAL_TYPES)]
        .groupby("doc_type")["candidate"]
        .nunique()
        .reset_index(name="candidates_with")
    )

    total_cand = inventory["candidate"].nunique()
    optional_counts["pct"] = (optional_counts["candidates_with"] / total_cand * 100).round(1)

    chart_optional = (
        alt.Chart(optional_counts)
        .mark_bar()
        .encode(
            y=alt.Y("doc_type:N", sort="-x", title="Document type"),
            x=alt.X("pct:Q", title="% of candidates with this doc", scale=alt.Scale(domain=[0, 100])),
            tooltip=["doc_type", "candidates_with", "pct"],
        )
        .properties(width=600, height=300, title="Optional document coverage (all semesters)")
    )
    chart_optional


@app.cell
def _(mo):
    mo.md("""
    ## 7. File sizes
    """)


@app.cell
def _(alt, inventory):
    chart_sizes = (
        alt.Chart(inventory)
        .mark_circle(opacity=0.5, size=15)
        .encode(
            x=alt.X("semester:N", sort=None, title="Semester"),
            y=alt.Y("size_kb:Q", title="File size (KB)", scale=alt.Scale(type="log")),
            color=alt.Color("doc_type:N", title="Document type"),
            tooltip=["semester", "candidate", "doc_type", "filename", "size_kb"],
        )
        .properties(width=700, height=400, title="File size distribution by semester (log scale)")
    )
    chart_sizes


@app.cell
def _(mo):
    mo.md("""
    ## 8. File format breakdown
    """)


@app.cell
def _(alt, inventory):
    ext_counts = inventory["extension"].value_counts().reset_index()
    ext_counts.columns = ["extension", "count"]

    chart_ext = (
        alt.Chart(ext_counts)
        .mark_arc(innerRadius=50)
        .encode(
            theta=alt.Theta("count:Q"),
            color=alt.Color("extension:N", title="Extension"),
            tooltip=["extension", "count"],
        )
        .properties(width=350, height=300, title="File format distribution")
    )
    chart_ext


@app.cell
def _(inventory, mo):
    files_per = inventory.groupby(["semester", "candidate"]).size()

    summary_by_sem = inventory.groupby("semester").agg(
        candidates=("candidate", "nunique"),
        files=("filename", "count"),
        total_kb=("size_kb", "sum"),
    ).reset_index()
    summary_by_sem["total_mb"] = (summary_by_sem["total_kb"] / 1024).round(1)

    total_files = inventory.shape[0]
    total_cands = inventory.groupby(["semester", "candidate"]).ngroup().max() + 1
    total_mb = summary_by_sem["total_mb"].sum()

    mo.md(f"""
    ## Summary

    | Metric | Value |
    |--------|-------|
    | Semesters | {inventory['semester'].nunique()} |
    | Candidates (total) | {total_cands} |
    | Total files | {total_files} |
    | Total size | {total_mb:.1f} MB |
    | Avg files/candidate | {files_per.mean():.1f} |
    | Min files/candidate | {files_per.min()} |
    | Max files/candidate | {files_per.max()} |
    | All PDFs | {'Yes' if (inventory['extension'] == '.pdf').all() else 'No'} |
    """)


@app.cell
def _(mo):
    mo.md("""
    ---
    *Generated from `data/raw/applications/dossiers/` — run with `uv run marimo run notebooks/dossier_eda.py`*
    """)


@app.cell
def _():
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
