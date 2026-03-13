"""Typst report generation and PDF compilation.

Aggregates scraped offer records by company, renders a Jinja2 Typst
template, and compiles to PDF via the ``typst`` CLI.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompanyRow:
    name: str
    emails: list[str] = field(default_factory=list)
    location: str = ""
    offers: int = 0
    positions: int = 0


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def build_company_summary(records: list[dict[str, Any]]) -> list[CompanyRow]:
    """Group records by company name and aggregate stats."""
    companies: dict[str, dict[str, Any]] = {}

    for rec in records:
        name = (rec.get("company") or "").strip()
        if not name:
            continue

        if name not in companies:
            companies[name] = {"emails": set(), "location": "", "offers": 0, "positions": 0}

        entry = companies[name]
        email = (rec.get("contact_email") or "").strip()
        if email:
            entry["emails"].add(email)
        if not entry["location"]:
            entry["location"] = (rec.get("location") or "").strip()
        entry["offers"] += 1
        try:
            entry["positions"] += int(rec.get("positions") or 1)
        except (ValueError, TypeError):
            entry["positions"] += 1

    rows = [
        CompanyRow(
            name=name,
            emails=sorted(data["emails"]),
            location=data["location"],
            offers=data["offers"],
            positions=data["positions"],
        )
        for name, data in sorted(companies.items(), key=lambda kv: kv[0].lower())
    ]
    return rows


# ---------------------------------------------------------------------------
# Typst escaping
# ---------------------------------------------------------------------------

_TYPST_ESCAPES = str.maketrans(
    {"@": "\\@", "#": "\\#", "_": "\\_", "*": "\\*", "<": "\\<", ">": "\\>", "$": "\\$"}
)


def _esc(text: str) -> str:
    return text.translate(_TYPST_ESCAPES)


# ---------------------------------------------------------------------------
# Jinja2 template (embedded to avoid file-path issues on Vercel)
# ---------------------------------------------------------------------------

_TYPST_TEMPLATE = r"""// Auto-generated ISA report — {{ date }}
// Compile: typst compile report.typ

#set document(
  title: "EPFL ISA Internship Offers — Company Directory",
  author: "{{ author }}",
)

#set page(
  paper: "a4",
  margin: (top: 2.5cm, bottom: 2cm, left: 2cm, right: 2cm),
  header: context {
    if counter(page).get().first() > 1 [
      #set text(8pt, fill: luma(120))
      #h(1fr) EPFL ISA — Company Directory — {{ date }}
    ]
  },
  footer: context {
    set text(8pt, fill: luma(120))
    h(1fr)
    counter(page).display("1 / 1", both: true)
    h(1fr)
  },
)

#set text(font: "New Computer Modern", size: 9.5pt)
#set par(leading: 0.6em)

// ─── Title page ───

#v(3cm)

#align(center)[
  #block(width: 100%)[
    #set text(fill: rgb("#c4122f"))
    #text(weight: "bold", size: 28pt)[EPFL ISA]
    #v(0.3cm)
    #text(size: 20pt, weight: "regular")[Internship & Project Offers]
    #v(0.2cm)
    #text(size: 14pt, fill: luma(80))[Company Directory — {{ date }}]
    #v(0.4cm)
    #text(size: 11pt, weight: "medium", fill: luma(60))[{{ author }}]
  ]
]

#v(1.5cm)

#align(center)[
  #block(
    width: 80%,
    fill: rgb("#f8f8f8"),
    stroke: (left: 3pt + rgb("#c4122f")),
    inset: (x: 1.2em, y: 1em),
    radius: (right: 4pt),
  )[
    #set text(size: 10.5pt)
    #grid(
      columns: (1fr, 1fr),
      row-gutter: 0.8em,
      [*Companies*], [*{{ n_companies }}*],
      [*Open offers*], [*{{ n_offers }}*],
      [*Total positions*], [*{{ n_positions }}*],
      [*With contact email*], [*{{ n_with_email }} offers ({{ pct_email }}%)*],
    )
  ]
]

#v(1cm)

#align(center)[
  #set text(size: 9pt, fill: luma(100))
  Scraped from #link("https://isa.epfl.ch/imoniteur_ISAP/PORTAL14S.htm#tab290")[isa.epfl.ch] on {{ date }} \
  {{ faculty_label }} — Master internships and projects
]

#pagebreak()

// ─── Table ───

#set text(size: 8pt)

#let accent = rgb("#c4122f")
#let light-bg = rgb("#fafafa")
#let border-color = luma(210)

#let header-cell(body) = table.cell(
  fill: accent,
  text(weight: "bold", fill: white, size: 8pt, body),
)

#table(
  columns: (auto, 1fr, auto, auto, auto),
  inset: (x: 6pt, y: 5pt),
  align: (left, left, left, center, center),
  stroke: (x: none, y: 0.5pt + border-color),
  fill: (_, y) => if calc.odd(y) { light-bg } else { white },

  // Header
  header-cell[Company],
  header-cell[Contact Email],
  header-cell[Location],
  header-cell[Offers],
  header-cell[Pos.],

  {% for c in companies %}
  [{% if c.positions >= 5 %}*{% endif %}{{ c.name_esc }}{% if c.positions >= 5 %}*{% endif %}],
  [{% if c.emails %}{% for e in c.emails %}#link("mailto:{{ e }}")[{{ e | e_esc }}]{% if not loop.last %} #linebreak() {% endif %}{% endfor %}{% else %}---{% endif %}],
  [{{ c.location_esc }}],
  [{% if c.positions >= 5 %}*{% endif %}{{ c.offers }}{% if c.positions >= 5 %}*{% endif %}],
  [{% if c.positions >= 5 %}*{% endif %}{{ c.positions }}{% if c.positions >= 5 %}*{% endif %}],
  {% endfor %}
)

#v(1cm)

// ─── Top Employers ───

#heading(level: 2, numbering: none)[Top Employers by Open Positions]

#v(0.3cm)

#{
  let data = (
    {% for name, pos, color in top_employers %}
    ("{{ name | e_esc }}", {{ pos }}, rgb("{{ color }}")),
    {% endfor %}
  )

  for (name, pos, color) in data {
    let bar-width = calc.min(pos * 8, 320)
    grid(
      columns: (9em, auto, auto),
      column-gutter: 0.5em,
      align: (right + horizon, left + horizon, left + horizon),
      text(size: 8pt, weight: "medium")[#name],
      box(
        width: bar-width * 1pt,
        height: 10pt,
        fill: color,
        radius: 2pt,
      ),
      text(size: 7.5pt, fill: luma(100))[ #pos positions],
    )
    v(3pt)
  }
}

#v(0.8cm)

#align(center)[
  #set text(size: 7.5pt, fill: luma(140))
  _All emails are clickable `mailto:` links in the PDF version._ \
  Source: ISA EPFL Portal — {{ faculty_label }} — scraped {{ date }}
]
"""

# Colour palette for the bar chart
_BAR_COLORS = [
    "#c4122f",
    "#5851db",
    "#00b8a9",
    "#f6a623",
    "#7b61ff",
    "#e84393",
    "#2d3436",
    "#006039",
    "#0984e3",
    "#00cec9",
]


# ---------------------------------------------------------------------------
# Render + compile
# ---------------------------------------------------------------------------


def render_typst(
    companies: list[CompanyRow], *, faculty: str = "ic", author: str = "", date: str = ""
) -> str:
    """Render the Typst source string from company data."""
    n_offers = sum(c.offers for c in companies)
    n_positions = sum(c.positions for c in companies)
    n_with_email = sum(c.offers for c in companies if c.emails)
    pct_email = round(n_with_email / n_offers * 100) if n_offers else 0

    faculty_labels = {"ic": "IC Faculty"}
    faculty_label = faculty_labels.get(faculty, faculty.upper() + " Faculty")

    # Top employers by positions (top 10)
    top = sorted(companies, key=lambda c: c.positions, reverse=True)[:10]
    top_employers = [
        (c.name, c.positions, _BAR_COLORS[i % len(_BAR_COLORS)]) for i, c in enumerate(top)
    ]

    # Prepare template context — pre-escape Typst-unsafe chars
    ctx_companies = [
        {
            "name_esc": _esc(c.name),
            "emails": c.emails,
            "location_esc": _esc(c.location),
            "offers": c.offers,
            "positions": c.positions,
        }
        for c in companies
    ]

    env = Environment(autoescape=False)  # noqa: S701 — Typst, not HTML
    env.filters["e_esc"] = _esc
    template = env.from_string(_TYPST_TEMPLATE)

    return template.render(
        date=date,
        author=author,
        n_companies=len(companies),
        n_offers=n_offers,
        n_positions=n_positions,
        n_with_email=n_with_email,
        pct_email=pct_email,
        faculty_label=faculty_label,
        companies=ctx_companies,
        top_employers=top_employers,
    )


_TYPST_VERSION = "v0.13.0"
_TYPST_TMP = "/tmp/typst"  # noqa: S108 — Vercel writable dir


def _download_typst() -> str:
    """Download the typst binary to /tmp/ (Vercel functions can write there)."""
    import urllib.request  # noqa: PLC0415

    url = (
        f"https://github.com/typst/typst/releases/download/{_TYPST_VERSION}"
        f"/typst-x86_64-unknown-linux-musl.tar.xz"
    )
    archive_path = "/tmp/typst.tar.xz"  # noqa: S108
    urllib.request.urlretrieve(url, archive_path)  # noqa: S310
    subprocess.run(  # noqa: S603
        ["tar", "xJf", archive_path, "--strip-components=1", "-C", "/tmp"],  # noqa: S108, S607
        check=True,
        capture_output=True,
    )
    Path(_TYPST_TMP).chmod(0o755)
    return _TYPST_TMP


def _find_typst_binary() -> str:
    """Locate the typst binary: bundled, system PATH, or download to /tmp/."""
    # 1. Bundled in api/_bin/ (local install)
    bundled = Path(__file__).parent / ".." / "_bin" / "typst"
    if bundled.is_file():
        return str(bundled)
    # 2. System PATH
    system = shutil.which("typst")
    if system:
        return system
    # 3. Already downloaded to /tmp/
    if Path(_TYPST_TMP).is_file():
        return _TYPST_TMP
    # 4. Download on-demand (Vercel serverless)
    return _download_typst()


def compile_pdf(typst_source: str) -> bytes:
    """Write Typst source to a temp file, compile to PDF, return bytes."""
    typst_bin = _find_typst_binary()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        src_path = tmp / "report.typ"
        pdf_path = tmp / "report.pdf"
        src_path.write_text(typst_source, encoding="utf-8")
        subprocess.run(  # noqa: S603
            [typst_bin, "compile", str(src_path), str(pdf_path)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return pdf_path.read_bytes()
