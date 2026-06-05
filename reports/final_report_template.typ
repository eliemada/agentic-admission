// =============================================================================
//  Final Project Report — Agentic Admission (MTE / EPFL)
//  Author : Elie Bruno · Supervisor : Prof. Gaétan de Rassenfosse
//  Template forked from the HUM-470 EPFL Modern 2026 base, extended with
//  diagram, callout and metric helpers carried over from the weekly-report
//  template used during the semester.
// =============================================================================

// ── EPFL palette ────────────────────────────────────────────────────────────
#let epfl-red       = rgb("#FF0000")
#let epfl-dark      = rgb("#1A1A1A")
#let accent-gray    = rgb("#4A4A4A")
#let light-gray     = rgb("#F5F5F5")
#let medium-gray    = rgb("#E0E0E0")
#let success-green  = rgb("#10B981")
#let warning-amber  = rgb("#F59E0B")
#let info-blue      = rgb("#2563EB")
#let violet-callout = rgb("#7C3AED")

// Page numbering format: roman for front matter, arabic with total in body.
#let page-fmt = state("page-fmt", "i")

#let report(
  title: "",
  subtitle: "",
  author: (name: "", sciper: ""),
  supervisor: "",
  course: "",
  program: "",
  institution: "",
  semester: "",
  date: datetime.today().display("[day] [month repr:long] [year]"),
  abstract: none,
  keywords: (),
  body,
) = {
  set document(title: title, author: author.name, date: datetime.today())

  // ── Page setup ───────────────────────────────────────────────────────────
  set page(
    paper: "a4",
    margin: (top: 2.3cm, bottom: 2cm, left: 2.2cm, right: 2.2cm),
    header: context {
      if counter(page).get().first() > 1 {
        set text(size: 8.5pt, fill: accent-gray)
        grid(
          columns: (1fr, 1fr),
          align: (left, right),
          [#course],
          [#author.name],
        )
        v(-2pt)
        line(length: 100%, stroke: 0.4pt + medium-gray)
      }
    },
    footer: context {
      set text(size: 8.5pt, fill: accent-gray)
      line(length: 100%, stroke: 0.4pt + medium-gray)
      v(2pt)
      let fmt = page-fmt.get()
      let n = counter(page).at(here()).first()
      let display-str = if fmt == "1" {
        [#n / #counter(page).final().first()]
      } else {
        numbering(fmt, n)
      }
      grid(
        columns: (1fr, 1fr),
        align: (left, right),
        [#semester],
        display-str,
      )
    },
  )

  // ── Typography ───────────────────────────────────────────────────────────
  set text(
    font: ("New Computer Modern", "Libertinus Serif", "Palatino"),
    size: 10pt,
    lang: "en",
    region: "gb",
    fill: epfl-dark,
  )

  set par(justify: true, leading: 0.58em, first-line-indent: 0em, spacing: 0.6em)

  // ── Headings ─────────────────────────────────────────────────────────────
  set heading(numbering: "1.1")

  show heading.where(level: 1): it => {
    v(0.7em)
    block(width: 100%)[
      #set text(size: 14pt, weight: "bold", fill: epfl-dark)
      #if it.numbering != none {
        text(fill: epfl-red)[#counter(heading).display() #h(6pt)]
      }
      #it.body
      #v(1pt)
      #line(length: 100%, stroke: 1.2pt + epfl-red)
    ]
    v(0.35em)
  }

  show heading.where(level: 2): it => {
    v(0.45em)
    block[
      #set text(size: 11.5pt, weight: "bold", fill: epfl-dark)
      #if it.numbering != none {
        text(fill: accent-gray)[#counter(heading).display() #h(4pt)]
      }
      #it.body
    ]
    v(0.2em)
  }

  show heading.where(level: 3): it => {
    v(0.3em)
    block[
      #set text(size: 10.5pt, weight: "bold", fill: accent-gray)
      #if it.numbering != none {
        text(fill: accent-gray)[#counter(heading).display() #h(4pt)]
      }
      #it.body
    ]
    v(0.15em)
  }

  // ── Figures and tables ──────────────────────────────────────────────────
  show figure: it => {
    set align(center)
    v(0.3em)
    block(width: 100%, inset: (x: 0pt, y: 4pt))[
      #it.body
      #v(3pt)
      #set text(size: 8.5pt)
      #if it.caption != none { it.caption }
    ]
    v(0.3em)
  }

  show figure.where(kind: table): set figure.caption(position: top)
  set table(
    stroke: none,
    inset: 4pt,
    fill: (_, y) => if y == 0 { light-gray } else { none },
  )
  show table: set text(size: 9pt)

  // ── Equations ───────────────────────────────────────────────────────────
  set math.equation(numbering: "(1)")

  // ── Lists ───────────────────────────────────────────────────────────────
  set enum(indent: 1em, body-indent: 0.5em)
  set list(indent: 1em, body-indent: 0.5em, marker: text(fill: epfl-red)[--])

  // ── Code blocks ─────────────────────────────────────────────────────────
  show raw.where(block: true): it => block(
    width: 100%,
    fill: rgb("#F8F8F8"),
    stroke: 0.4pt + medium-gray,
    radius: 3pt,
    inset: 10pt,
    text(size: 9pt, it),
  )
  show raw.where(block: false): it => box(
    fill: rgb("#F0F0F0"),
    outset: (x: 2pt, y: 2pt),
    radius: 2pt,
    text(size: 9.5pt, it),
  )

  // ── Links ────────────────────────────────────────────────────────────────
  show link: it => {
    set text(fill: rgb("#0066CC"))
    underline(it)
  }

  // === TITLE PAGE =========================================================
  {
    set page(header: none, footer: none)

    v(1fr)

    place(
      left + top,
      dx: -2.5cm,
      dy: -3cm,
      rect(width: 6pt, height: 100% + 5.5cm, fill: epfl-red),
    )

    align(left)[
      #text(size: 28pt, weight: "bold", fill: epfl-red, tracking: 2pt)[EPFL]
      #v(-6pt)
      #text(size: 9pt, fill: accent-gray)[#institution]
    ]

    v(2cm)

    block(width: 100%)[
      #set text(size: 10pt, fill: accent-gray)
      #text(tracking: 1.5pt)[#upper[#course]]
      #v(-2pt)
      #text(size: 9.5pt)[#program]
    ]

    v(0.8cm)

    block(width: 100%)[
      #line(length: 60pt, stroke: 2.5pt + epfl-red)
      #v(8pt)
      #text(size: 26pt, weight: "bold", fill: epfl-dark)[#title]
      #if subtitle != "" {
        v(6pt)
        text(size: 14pt, fill: accent-gray)[#subtitle]
      }
    ]

    v(1.5cm)

    block(
      width: 100%,
      inset: (left: 12pt),
      stroke: (left: 2pt + epfl-red),
    )[
      #set text(size: 11pt)
      #text(weight: "bold")[Author] \
      #author.name #if author.sciper != "" [ \
        #text(fill: accent-gray, size: 9.5pt)[SCIPER #author.sciper] ] \
      \
      #text(weight: "bold")[Supervisor] \
      #supervisor
    ]

    v(2fr)

    align(center)[#text(size: 10pt, fill: accent-gray)[#date]]

    pagebreak()
  }

  // === FRONT MATTER (Roman) ================================================
  set page(numbering: "i")
  counter(page).update(1)
  page-fmt.update("i")

  if abstract != none {
    v(1em)
    block(
      width: 100%,
      inset: (x: 2em, y: 1em),
      stroke: (left: 2pt + epfl-red),
      fill: light-gray,
    )[
      #text(size: 11pt, weight: "bold")[Abstract]
      #v(4pt)
      #set text(size: 10pt)
      #abstract
    ]

    if keywords.len() > 0 {
      v(6pt)
      set text(size: 9.5pt)
      text(weight: "bold")[Keywords: ]
      keywords.join(", ")
    }

    pagebreak()
  }

  {
    show outline.entry.where(level: 1): it => {
      v(4pt)
      strong(it)
    }
    outline(title: [Contents], indent: 1.5em, depth: 3)
    pagebreak()
  }

  // === BODY (Arabic) =======================================================
  set page(numbering: "1")
  counter(page).update(1)
  page-fmt.update("1")
  body
}

// =============================================================================
//  Component helpers
// =============================================================================

// Coloured callout (info, warning, key finding).
#let callout(title: none, icon: "i", colour: epfl-red, body) = {
  block(
    width: 100%,
    fill: colour.lighten(92%),
    stroke: (left: 2.5pt + colour),
    radius: (right: 3pt),
    inset: (x: 9pt, y: 7pt),
  )[
    #if title != none {
      text(size: 8.5pt, weight: "bold", fill: colour)[#icon #h(4pt) #upper(title)]
      v(2pt)
    }
    #set text(size: 9.5pt)
    #body
  ]
}

// Key finding (used for headline results).
#let finding(body) = callout(
  title: "Key finding",
  icon: "*",
  colour: epfl-red,
  body,
)

// Inline definition box.
#let definition(term, body) = {
  block(
    width: 100%,
    inset: (x: 9pt, y: 6pt),
    stroke: (left: 2pt + epfl-red),
    fill: light-gray,
    radius: (right: 3pt),
  )[
    #text(weight: "bold", size: 10pt)[#term] \
    #v(1pt)
    #set text(size: 9.5pt)
    #body
  ]
}

// KPI tile (used in the executive-summary grid on page 1 of the body).
#let metric(label: "", value: "", detail: none) = {
  box(
    width: 100%,
    fill: light-gray,
    stroke: 0.5pt + medium-gray,
    radius: 4pt,
    inset: (x: 12pt, y: 10pt),
  )[
    #text(size: 8pt, fill: accent-gray, weight: "semibold", tracking: 0.05em)[
      #upper(label)
    ]
    #v(2pt)
    #text(size: 18pt, weight: "bold", fill: epfl-dark)[#value]
    #if detail != none {
      v(1pt)
      text(size: 8pt, fill: accent-gray)[#detail]
    }
  ]
}

// Diagram node : a labelled rounded rectangle.
#let dnode(label, sub: none, fill: light-gray, stroke-colour: accent-gray) = {
  box(
    fill: fill,
    stroke: 0.6pt + stroke-colour,
    radius: 4pt,
    inset: (x: 10pt, y: 8pt),
  )[
    #set text(size: 9.5pt, weight: "semibold")
    #align(center)[#label]
    #if sub != none {
      v(1pt)
      set text(size: 8pt, weight: "regular", fill: accent-gray)
      align(center)[#sub]
    }
  ]
}

// Arrow with optional label.
#let darrow(label: none) = {
  set text(size: 8pt, fill: accent-gray)
  if label != none {
    box[
      #align(center)[#label]
      #align(center)[#text(size: 12pt, fill: epfl-red)[→]]
    ]
  } else {
    text(size: 14pt, fill: epfl-red)[→]
  }
}

// Vertical arrow.
#let dvarrow(label: none) = {
  set text(size: 8pt, fill: accent-gray)
  align(center)[
    #text(size: 12pt, fill: epfl-red)[↓]
    #if label != none [ #h(4pt) #label ]
  ]
}
