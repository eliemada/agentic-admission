# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo>=0.20.2",
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
        # MTE Admission Data — Exploratory Analysis

        Exploring **1,342 candidates** across 13 admission files (2020–2026),
        extracted from the normalised Parquet dataset.
        """
    )
    return (mo,)


@app.cell
def _(mo):
    import pyarrow.parquet as pq

    table = pq.read_table("data/processed/all_candidates.parquet")
    df = table.to_pandas()
    mo.md(f"Loaded **{len(df):,}** rows × **{len(df.columns)}** columns from `all_candidates.parquet`")
    return df, pq, table


@app.cell
def _(mo):
    mo.md("## 1. Dataset overview")


@app.cell
def _(df, mo):
    mo.ui.table(df.head(20), label="First 20 candidates")


@app.cell
def _(df, mo):
    mo.md(f"""
### Column summary

| Metric | Value |
|--------|-------|
| Total candidates | {len(df):,} |
| Source files | {df['source_file'].nunique()} |
| Academic years | {df['academic_year'].nunique()} |
| Columns | {len(df.columns)} |
| Non-null name | {df['name'].notna().sum():,} / {len(df):,} |
| Has decision_section | {(df['decision_section'] != '').sum():,} / {len(df):,} |
| Has committee_evaluations | {(df['committee_evaluations'] != '').sum():,} / {len(df):,} |
| Has gender | {(df['gender'] != '').sum():,} / {len(df):,} |
""")


@app.cell
def _(mo):
    mo.md("## 2. Candidates per file")


@app.cell
def _(df):
    import altair as alt

    counts = (
        df.groupby(["academic_year", "admission_round"])
        .size()
        .reset_index(name="candidates")
    )
    counts["label"] = counts["academic_year"] + " " + counts["admission_round"]

    chart_per_file = (
        alt.Chart(counts)
        .mark_bar()
        .encode(
            x=alt.X("label:N", sort=None, title="Year / Round"),
            y=alt.Y("candidates:Q", title="Candidates"),
            color=alt.Color("admission_round:N", title="Round"),
            tooltip=["academic_year", "admission_round", "candidates"],
        )
        .properties(width=700, height=350, title="Candidates per admission round")
    )
    chart_per_file
    return alt, chart_per_file, counts


@app.cell
def _(mo):
    mo.md("## 3. Decision distribution")


@app.cell
def _(alt, df):
    decisions = df[df["decision_section"] != ""].copy()
    decision_map = {
        "Refusé": "Refused",
        "NO": "Refused",
        "Accepté": "Accepted",
        "OK": "Accepted",
        "YES": "Accepted",
        "Admis": "Accepted",
        "Accepté / bourse": "Accepted (scholarship)",
        "YES - BOURSE": "Accepted (scholarship)",
        "A discuter": "Discuss",
    }
    decisions["decision_norm"] = decisions["decision_section"].map(decision_map).fillna("Other")

    dec_counts = decisions["decision_norm"].value_counts().reset_index()
    dec_counts.columns = ["decision", "count"]

    chart_decisions = (
        alt.Chart(dec_counts)
        .mark_arc(innerRadius=60)
        .encode(
            theta=alt.Theta("count:Q"),
            color=alt.Color(
                "decision:N",
                scale=alt.Scale(
                    domain=["Accepted", "Refused", "Accepted (scholarship)", "Discuss", "Other"],
                    range=["#2ecc71", "#e74c3c", "#27ae60", "#f39c12", "#95a5a6"],
                ),
                title="Decision",
            ),
            tooltip=["decision", "count"],
        )
        .properties(width=400, height=350, title="Aggregate decisions (where available)")
    )
    chart_decisions
    return chart_decisions, dec_counts, decision_map, decisions


@app.cell
def _(alt, decision_map, df):
    year_decisions = df[df["decision_section"] != ""].copy()
    year_decisions["decision_norm"] = year_decisions["decision_section"].map(decision_map).fillna("Other")

    year_dec_counts = (
        year_decisions.groupby(["academic_year", "decision_norm"])
        .size()
        .reset_index(name="count")
    )

    chart_year_decisions = (
        alt.Chart(year_dec_counts)
        .mark_bar()
        .encode(
            x=alt.X("academic_year:N", sort=None, title="Academic year"),
            y=alt.Y("count:Q", title="Candidates"),
            color=alt.Color(
                "decision_norm:N",
                scale=alt.Scale(
                    domain=["Accepted", "Refused", "Accepted (scholarship)", "Discuss", "Other"],
                    range=["#2ecc71", "#e74c3c", "#27ae60", "#f39c12", "#95a5a6"],
                ),
                title="Decision",
            ),
            tooltip=["academic_year", "decision_norm", "count"],
        )
        .properties(width=700, height=350, title="Decision breakdown by academic year")
    )
    chart_year_decisions
    return chart_year_decisions, year_dec_counts, year_decisions


@app.cell
def _(mo):
    mo.md("## 4. School quality ratings")


@app.cell
def _(alt, df):
    quality = df[df["school_quality"] != ""].copy()
    quality["rating"] = quality["school_quality"].str.extract(r"^([A-X])\)")
    quality["rating"] = quality["rating"].fillna("?")

    rating_counts = quality["rating"].value_counts().reset_index()
    rating_counts.columns = ["rating", "count"]

    rating_labels = {"A": "A) Priority", "B": "B) Good", "C": "C) Low interest", "X": "X) Unknown", "?": "Unparsed"}
    rating_counts["label"] = rating_counts["rating"].map(rating_labels).fillna(rating_counts["rating"])

    chart_quality = (
        alt.Chart(rating_counts)
        .mark_bar()
        .encode(
            x=alt.X("label:N", sort=["A) Priority", "B) Good", "C) Low interest", "X) Unknown", "Unparsed"], title="School quality"),
            y=alt.Y("count:Q", title="Candidates"),
            color=alt.Color(
                "label:N",
                scale=alt.Scale(
                    domain=["A) Priority", "B) Good", "C) Low interest", "X) Unknown", "Unparsed"],
                    range=["#2ecc71", "#3498db", "#e67e22", "#95a5a6", "#bdc3c7"],
                ),
            ),
            tooltip=["label", "count"],
        )
        .properties(width=500, height=300, title="School quality distribution")
    )
    chart_quality
    return chart_quality, quality, rating_counts, rating_labels


@app.cell
def _(mo):
    mo.md("## 5. Top countries")


@app.cell
def _(alt, df):
    countries = df[df["school_country"] != ""]["school_country"].value_counts().head(20).reset_index()
    countries.columns = ["country", "count"]

    chart_countries = (
        alt.Chart(countries)
        .mark_bar()
        .encode(
            y=alt.Y("country:N", sort="-x", title="Country"),
            x=alt.X("count:Q", title="Candidates"),
            tooltip=["country", "count"],
        )
        .properties(width=600, height=450, title="Top 20 countries of origin")
    )
    chart_countries
    return chart_countries, countries


@app.cell
def _(mo):
    mo.md("## 6. Gender distribution (where available)")


@app.cell
def _(alt, df):
    gendered = df[df["gender"] != ""].copy()

    gender_year = (
        gendered.groupby(["academic_year", "gender"])
        .size()
        .reset_index(name="count")
    )

    chart_gender = (
        alt.Chart(gender_year)
        .mark_bar()
        .encode(
            x=alt.X("academic_year:N", sort=None, title="Academic year"),
            y=alt.Y("count:Q", title="Candidates"),
            color=alt.Color(
                "gender:N",
                scale=alt.Scale(domain=["M", "F"], range=["#3498db", "#e74c3c"]),
            ),
            tooltip=["academic_year", "gender", "count"],
        )
        .properties(width=500, height=300, title="Gender split (files with gender data)")
    )
    chart_gender
    return chart_gender, gender_year, gendered


@app.cell
def _(mo):
    mo.md("## 7. Top schools")


@app.cell
def _(alt, df):
    schools = df[df["school_name"] != ""]["school_name"].value_counts().head(15).reset_index()
    schools.columns = ["school", "count"]

    chart_schools = (
        alt.Chart(schools)
        .mark_bar()
        .encode(
            y=alt.Y("school:N", sort="-x", title="School"),
            x=alt.X("count:Q", title="Applications"),
            tooltip=["school", "count"],
        )
        .properties(width=600, height=400, title="Top 15 schools by application count")
    )
    chart_schools
    return chart_schools, schools


@app.cell
def _(mo):
    mo.md("## 8. Acceptance rate by school quality")


@app.cell
def _(alt, decision_map, df):
    qualified = df[(df["school_quality"] != "") & (df["decision_section"] != "")].copy()
    qualified["rating"] = qualified["school_quality"].str.extract(r"^([A-X])\)")
    qualified["rating"] = qualified["rating"].fillna("?")
    qualified["decision_norm"] = qualified["decision_section"].map(decision_map).fillna("Other")
    qualified["accepted"] = qualified["decision_norm"].str.contains("Accepted").astype(int)

    acceptance = qualified.groupby("rating").agg(
        total=("accepted", "count"),
        accepted=("accepted", "sum"),
    ).reset_index()
    acceptance["rate"] = (acceptance["accepted"] / acceptance["total"] * 100).round(1)

    rating_order = {"A": 0, "B": 1, "C": 2, "X": 3, "?": 4}
    acceptance["sort_key"] = acceptance["rating"].map(rating_order)
    acceptance = acceptance.sort_values("sort_key")

    labels = {"A": "A) Priority", "B": "B) Good", "C": "C) Low interest", "X": "X) Unknown", "?": "Unparsed"}
    acceptance["label"] = acceptance["rating"].map(labels)

    chart_acceptance = (
        alt.Chart(acceptance)
        .mark_bar()
        .encode(
            x=alt.X("label:N", sort=list(labels.values()), title="School quality"),
            y=alt.Y("rate:Q", title="Acceptance rate (%)"),
            color=alt.Color("label:N", legend=None, scale=alt.Scale(
                domain=list(labels.values()),
                range=["#2ecc71", "#3498db", "#e67e22", "#95a5a6", "#bdc3c7"],
            )),
            tooltip=["label", "total", "accepted", "rate"],
        )
        .properties(width=500, height=300, title="Acceptance rate by school quality rating")
    )
    chart_acceptance
    return acceptance, chart_acceptance, labels, qualified, rating_order


@app.cell
def _(mo):
    mo.md("## 9. Committee evaluation word cloud (most frequent terms)")


@app.cell
def _(df, mo):
    import re
    from collections import Counter

    all_evals = " ".join(df[df["committee_evaluations"] != ""]["committee_evaluations"].tolist())
    all_evals = re.sub(r"\[.*?\]", "", all_evals)
    words = re.findall(r"[a-zA-ZéèêëàâäùûüôöîïçÉÈ]{4,}", all_evals.lower())

    stopwords = {
        "good", "student", "from", "school", "university", "gpa", "below",
        "above", "very", "strong", "weak", "competitive", "enough", "engineering",
        "bachelor", "with", "that", "this", "they", "their", "have", "been",
        "will", "would", "could", "should", "also", "than", "more", "other",
        "some", "into", "over", "such", "only", "about", "after", "before",
        "most", "well", "refusé", "accepté", "discuter", "pour", "dans",
        "barême", "note", "candidatures",
    }
    filtered = [w for w in words if w not in stopwords]
    top_words = Counter(filtered).most_common(30)

    word_table = "| Term | Frequency |\n|------|----------|\n"
    for word, freq in top_words:
        bar = "█" * min(freq // 10, 40)
        word_table += f"| {word} | {freq} {bar} |\n"

    mo.md(f"### Top 30 terms in committee evaluations\n\n{word_table}")
    return Counter, all_evals, filtered, re, stopwords, top_words, word_table, words


@app.cell
def _(mo):
    mo.md("## 10. Data completeness heatmap")


@app.cell
def _(alt, df):
    import pandas as pd

    fields = [
        "name", "school_country", "school_name", "school_quality",
        "spe_remarks", "gpa_scale", "study_level", "gpa_candidate",
        "gpa_max", "gender", "committee_evaluations",
        "decision_section", "decision_permanent_member", "decision_final",
    ]
    completeness_rows = []
    for src in sorted(df["source_file"].unique()):
        subset = df[df["source_file"] == src]
        for field in fields:
            filled = (subset[field] != "").sum()
            pct = round(filled / len(subset) * 100, 1)
            completeness_rows.append({
                "file": src.replace("mte_applications_", "").replace(".xlsx", ""),
                "field": field,
                "pct": pct,
            })

    completeness_df = pd.DataFrame(completeness_rows)

    chart_completeness = (
        alt.Chart(completeness_df)
        .mark_rect()
        .encode(
            x=alt.X("file:N", sort=None, title="File"),
            y=alt.Y("field:N", title="Field"),
            color=alt.Color(
                "pct:Q",
                scale=alt.Scale(scheme="redyellowgreen", domain=[0, 100]),
                title="% filled",
            ),
            tooltip=["file", "field", "pct"],
        )
        .properties(width=700, height=400, title="Data completeness across files")
    )
    chart_completeness
    return chart_completeness, completeness_df, completeness_rows, fields, pd


@app.cell
def _(mo):
    mo.md(
"""
---
*Generated from `data/processed/all_candidates.parquet` — run with `uv run marimo run notebooks/eda.py`*
"""
    )


if __name__ == "__main__":
    app.run()
