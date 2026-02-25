// ─────────────────────────────────────────────────────────────────────────────
//  Rapport Hebdomadaire — Projet de Recherche
//  Système Multi-Agents pour l'Aide à la Décision en Admission
//  EPFL · Section MTE
// ─────────────────────────────────────────────────────────────────────────────

// ── Configuration ──────────────────────────────────────────────────────────────

#let epfl-red = rgb("#FF0000")
#let epfl-dark = rgb("#1A1A1A")
#let epfl-gray = rgb("#6B7280")
#let epfl-light = rgb("#F8F8F8")
#let epfl-border = rgb("#E5E5E5")
#let epfl-accent-light = rgb("#FFF1F1")

// ── Template Function ──────────────────────────────────────────────────────────

#let weekly-report(
  semaine: 1,
  date: "24 février 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  projet: "Système Multi-Agents pour l'Aide à la Décision en Admission",
  section: "Management of Technology and Entrepreneurship (MTE)",
  resume: [],
  body,
) = {

  // ── Page Setup ─────────────────────────────────────────────────────────────

  set page(
    paper: "a4",
    margin: (top: 2.8cm, bottom: 2.2cm, left: 2.4cm, right: 2.4cm),
    header: context {
      if counter(page).get().first() > 1 {
        set text(size: 8pt, fill: epfl-gray)
        grid(
          columns: (1fr, 1fr),
          align: (left, right),
          [Rapport Semaine #semaine — #date],
          [#etudiant · EPFL],
        )
        v(2pt)
        line(length: 100%, stroke: 0.4pt + epfl-border)
      }
    },
    footer: {
      set text(size: 8pt, fill: epfl-gray)
      line(length: 100%, stroke: 0.4pt + epfl-border)
      v(4pt)
      grid(
        columns: (1fr, 1fr),
        align: (left, right),
        [Section MTE · EPFL],
        context [Page #counter(page).display("1 / 1", both: true)],
      )
    },
  )

  // ── Typography ─────────────────────────────────────────────────────────────

  set text(
    font: "New Computer Modern",
    size: 10.5pt,
    fill: epfl-dark,
    lang: "fr",
  )

  set par(
    justify: true,
    leading: 0.72em,
  )

  set heading(numbering: none)

  show heading.where(level: 1): it => {
    v(0.6em)
    block(width: 100%)[
      #grid(
        columns: (3pt, 1fr),
        column-gutter: 10pt,
        align: (left, left + horizon),
        rect(width: 3pt, height: 1.1em, fill: epfl-red, radius: 1pt),
        text(
          size: 13pt,
          weight: "bold",
          tracking: 0.02em,
          fill: epfl-dark,
          upper(it.body),
        ),
      )
    ]
    v(0.2em)
  }

  show heading.where(level: 2): it => {
    v(0.4em)
    text(
      size: 11pt,
      weight: "semibold",
      fill: epfl-red.darken(15%),
      it.body,
    )
    v(0.1em)
  }

  show heading.where(level: 3): it => {
    v(0.3em)
    text(
      size: 10.5pt,
      weight: "medium",
      style: "italic",
      fill: epfl-gray.darken(20%),
      it.body,
    )
    v(0.05em)
  }

  // Styled lists
  set list(
    indent: 0.8em,
    body-indent: 0.5em,
    marker: text(fill: epfl-red, weight: "bold", size: 8pt)[▸],
  )

  set enum(
    indent: 0.8em,
    body-indent: 0.5em,
  )

  // Links
  show link: it => text(fill: epfl-red.darken(10%), it)

  // Code blocks
  show raw.where(block: true): it => {
    set text(size: 9pt)
    block(
      width: 100%,
      fill: rgb("#F6F6F6"),
      stroke: 0.5pt + epfl-border,
      radius: 4pt,
      inset: 12pt,
      it,
    )
  }

  show raw.where(block: false): it => {
    box(
      fill: rgb("#F0F0F0"),
      outset: (x: 2pt, y: 2pt),
      radius: 2pt,
      text(size: 9.5pt, it),
    )
  }

  // ── Title Block ────────────────────────────────────────────────────────────

  // Top accent line
  place(top + left, dx: -2.4cm, dy: -2.8cm,
    rect(width: 100% + 4.8cm, height: 4pt, fill: epfl-red),
  )

  v(0.3cm)

  // EPFL wordmark
  block(width: 100%)[
    #text(
      size: 11pt,
      weight: "bold",
      tracking: 0.15em,
      fill: epfl-red,
    )[EPFL]
    #h(8pt)
    #text(
      size: 8.5pt,
      fill: epfl-gray,
      tracking: 0.03em,
    )[ÉCOLE POLYTECHNIQUE FÉDÉRALE DE LAUSANNE]
  ]
  v(-4pt)
  block(width: 100%)[
    #text(
      size: 8.5pt,
      fill: epfl-gray,
    )[#section]
  ]

  v(0.8cm)

  // Week badge + date
  grid(
    columns: (auto, 1fr),
    column-gutter: 14pt,
    align: (left, left + horizon),
    {
      box(
        fill: epfl-red,
        radius: 4pt,
        inset: (x: 12pt, y: 7pt),
        text(
          size: 18pt,
          weight: "bold",
          fill: white,
          tracking: 0.05em,
        )[S#semaine],
      )
    },
    {
      text(
        size: 20pt,
        weight: "bold",
        fill: epfl-dark,
        tracking: -0.01em,
      )[Rapport Hebdomadaire]
      v(2pt)
      text(size: 10pt, fill: epfl-gray)[#date]
    },
  )

  v(0.5cm)

  // Project info bar
  block(
    width: 100%,
    fill: epfl-light,
    stroke: (left: 3pt + epfl-red),
    radius: (right: 4pt),
    inset: 14pt,
  )[
    #set text(size: 9.5pt)
    #grid(
      columns: (auto, 1fr),
      row-gutter: 6pt,
      column-gutter: 12pt,
      text(weight: "semibold", fill: epfl-gray)[Projet],
      text(fill: epfl-dark)[#projet],
      text(weight: "semibold", fill: epfl-gray)[Étudiant],
      text(fill: epfl-dark)[#etudiant],
      text(weight: "semibold", fill: epfl-gray)[Superviseur],
      text(fill: epfl-dark)[#superviseur],
    )
  ]

  // ── Résumé de la semaine (if provided) ─────────────────────────────────────

  if resume != [] {
    v(0.5cm)
    block(
      width: 100%,
      fill: epfl-accent-light,
      stroke: 0.5pt + rgb("#FFD4D4"),
      radius: 4pt,
      inset: 14pt,
    )[
      #text(size: 9pt, weight: "semibold", fill: epfl-red, tracking: 0.06em)[RÉSUMÉ DE LA SEMAINE]
      #v(4pt)
      #set text(size: 10pt)
      #resume
    ]
  }

  v(0.4cm)

  // ── Body ───────────────────────────────────────────────────────────────────

  body
}

// ── Utility Components ───────────────────────────────────────────────────────

// Callout / info box
#let callout(titre: none, icon: "ℹ", couleur: epfl-red, body) = {
  block(
    width: 100%,
    fill: couleur.lighten(92%),
    stroke: (left: 3pt + couleur),
    radius: (right: 4pt),
    inset: 12pt,
  )[
    #if titre != none {
      text(size: 9pt, weight: "bold", fill: couleur)[#icon #h(4pt) #upper(titre)]
      v(4pt)
    }
    #set text(size: 10pt)
    #body
  ]
}

// Metric / KPI card
#let metric(label: "", value: "", detail: none) = {
  box(
    width: 100%,
    fill: epfl-light,
    stroke: 0.5pt + epfl-border,
    radius: 4pt,
    inset: (x: 12pt, y: 10pt),
  )[
    #text(size: 8pt, fill: epfl-gray, weight: "semibold", tracking: 0.05em)[#upper(label)]
    #v(2pt)
    #text(size: 18pt, weight: "bold", fill: epfl-dark)[#value]
    #if detail != none {
      v(1pt)
      text(size: 8pt, fill: epfl-gray)[#detail]
    }
  ]
}

// Progress bar
#let progress-bar(pourcentage: 0, label: "") = {
  block(width: 100%)[
    #grid(
      columns: (1fr, auto),
      align: (left, right),
      text(size: 9pt, fill: epfl-dark)[#label],
      text(size: 9pt, weight: "semibold", fill: epfl-gray)[#pourcentage\%],
    )
    #v(3pt)
    #box(
      width: 100%,
      height: 6pt,
      radius: 3pt,
      fill: epfl-border,
      clip: true,
    )[
      #box(
        width: pourcentage * 1%,
        height: 100%,
        radius: 3pt,
        fill: epfl-red,
      )
    ]
  ]
}

// Task status badge
#let badge(texte, couleur: epfl-red) = {
  box(
    fill: couleur.lighten(85%),
    stroke: 0.5pt + couleur.lighten(50%),
    radius: 3pt,
    inset: (x: 6pt, y: 3pt),
    text(size: 8pt, weight: "semibold", fill: couleur.darken(10%))[#texte],
  )
}

// Task item with status
#let tache(nom, statut: "en cours") = {
  let couleur = if statut == "fait" { rgb("#10B981") }
    else if statut == "en cours" { rgb("#F59E0B") }
    else if statut == "bloqué" { epfl-red }
    else { epfl-gray }

  let icone = if statut == "fait" { "✓" }
    else if statut == "en cours" { "◔" }
    else if statut == "bloqué" { "✗" }
    else { "○" }

  block(width: 100%, inset: (y: 2pt))[
    #grid(
      columns: (auto, 1fr, auto),
      column-gutter: 8pt,
      align: (left, left, right),
      text(fill: couleur, weight: "bold", size: 10pt)[#icone],
      text(size: 10pt)[#nom],
      badge(statut, couleur: couleur),
    )
  ]
}

// Divider
#let divider() = {
  v(0.3em)
  line(length: 100%, stroke: 0.4pt + epfl-border)
  v(0.3em)
}
