#import "template.typ": *

#show: weekly-report.with(
  semaine: 9,
  date: "26 avril 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Réception des 119 dossiers de la cohorte 2025--26 (round 1). Pas
    de fichier Excel cette année : les informations candidat sont
    extraites directement des PDF « Synthèse de la candidature » via
    PyMuPDF. Un parseur bilingue (FR/EN), un batch builder, et un
    dashboard Streamlit de visualisation de cohorte ont été
    développés. Enrichissement des prompts évaluateurs avec le seuil
    GPA et la catégorie institutionnelle du SPE. Préparation du
    pipeline d'anonymisation pour la nouvelle cohorte.
  ],
)

// -- Métriques de la semaine ------------------------------------------------

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "Candidats parsés",
    value: "119/119",
    detail: "0 échec, FR + EN",
  ),
  metric(
    label: "Pays d'origine",
    value: "28",
    detail: "Inde 15, Italie 12, Turquie 12",
  ),
  metric(
    label: "Répartition",
    value: "78M / 41F",
    detail: "34% femmes",
  ),
)

#v(0.3cm)

#progress-bar(pourcentage: 72, label: "Progression du projet")

// -- Travail effectué -------------------------------------------------------

= Travail effectué

== Parseur de Synthèse PDF (`synthese_parser.py`)

Le fichier Excel du comité n'est pas disponible cette année. Les
données structurées sont extraites directement depuis le PDF
« Synthèse de la candidature » présent dans chaque dossier.

Le formulaire EPFL existe en deux langues (français et anglais) avec
des labels différents et une mise en page décalée (section études en
page 3 en FR, page 2 en EN). Le parseur gère les deux variantes :

- *Page 1* : nom, prénoms, sexe, nationalité, numéro de candidature
- *Page études* (détection dynamique) : institution, pays, domaine,
  niveau d'étude, GPA, barème maximal
- Extraction par recherche de labels dans le texte brut PyMuPDF
  (pas de dépendance OCR, pas de LLM)
- Labels configurés dans un dictionnaire bilingue `_LABELS` avec
  gestion des lignes de continuation (e.g. « Prénoms (tels
  qu'indiqués sur papiers d'identité) »)

== Batch builder (`cohort_builder.py`)

Script batch qui itère les 119 dossiers, localise le PDF Synthèse,
appelle le parseur, et produit un fichier JSON consolidé :

- `data/processed/cohort_2025-26-fall.json` : 119 enregistrements
- Taux de succès : 100% (0 échec, 0 champ vide critique)
- Exécution en ~1.5 secondes pour les 119 dossiers
- CLI : `uv run poe build-cohort`

== Dashboard cohorte (`dashboard/cohort.py`)

Interface Streamlit pour le comité de lecture, accessible sans Excel :

- *Filtres latéraux* : recherche texte (nom, école), pays,
  genre, niveau d'étude, plage GPA normalisée (0--4)
- *Tri* : par nom, GPA, pays, institution
- *Métriques* : total, répartition genre, nombre de pays,
  nombre d'institutions, GPA moyen normalisé
- *Cartes candidat dépliables* : toutes les données extraites,
  nombre de fichiers dans le dossier
- Normalisation GPA : conversion automatique vers une échelle
  0--4 (exclusion des barèmes allemands inversés)
- CLI : `uv run poe cohort` (port 8504)

== Enrichissement des prompts évaluateurs

Le seuil GPA de la fiche SPE et la catégorie institutionnelle
(A/B/C/X) sont désormais injectés dans le contexte de chaque
évaluateur (`run_evaluation.py`). Cela permet aux agents de
calibrer leur scoring par rapport aux attentes du comité.

== Dashboard universités (`dashboard/universities.py`)

Nouveau dashboard pour visualiser et éditer les profils
d'universités (tier A/B/C/X, statistiques historiques, notes du
comité). Les overrides du comité sont sauvegardés en YAML.

== Curriculum scraper et matcher

Scraper du catalogue EPFL pour les cursus bachelor et master,
avec un matcher de curriculum par similarité pour le Minor Advisor.
Design documenté dans `docs/plans/2026-04-20-curriculum-scraper-design.md`.

// -- Défis et obstacles -----------------------------------------------------

= Défis et obstacles

#callout(titre: "Dossiers incomplets", icon: "⚠", couleur: rgb("#EF4444"))[
  119 dossiers extraits sur les ~220 attendus. Les 119 restants sont
  encore sous forme de fichiers ZIP non décompressés. En attente de
  la livraison complète pour traiter l'ensemble de la cohorte.
]

- *Labels de formulaire multilingues* : le formulaire EPFL peut être
  en français ou en anglais. Les labels de champs diffèrent et la
  section « Études » n'est pas sur la même page. Résolu par une
  détection dynamique de la page et un dictionnaire bilingue.
- *Champs GPA hétérogènes* : les candidats saisissent le GPA sous
  des formes variées (« 3.21 until the 10th Semester », « 7,75 »,
  « 1.9/1.0 »). La normalisation best-effort fonctionne pour ~90%
  des cas mais les barèmes allemands inversés sont exclus.
- *Pas de fichier Excel* : contrairement aux années précédentes, le
  comité ne dispose pas de fichier Excel pré-rempli. Le dashboard
  cohorte remplace ce workflow.

// -- Fichiers modifiés -----------------------------------------------------

= Fichiers modifiés

#callout(titre: "Résumé des changements", icon: "◆", couleur: rgb("#8B5CF6"))[
  *8+ fichiers créés ou modifiés, ~700 lignes ajoutées* \
  \
  *Nouveaux fichiers :* \
  `extraction/synthese_parser.py` --- parseur bilingue FR/EN (200 lignes) \
  `extraction/cohort_builder.py` --- batch processing 119 dossiers (120 lignes) \
  `dashboard/cohort.py` --- dashboard cohorte Streamlit (320 lignes) \
  `dashboard/universities.py` --- dashboard profils universités (230 lignes) \
  `curriculum/` --- scraper et matcher de curriculum EPFL \
  \
  *Fichiers modifiés :* \
  `agents/run_evaluation.py` --- injection seuil GPA et catégorie SPE \
  `agents/orchestrator.py` --- Minor Advisor best-effort séparé \
  `pyproject.toml` --- tâches poe `cohort`, `build-cohort`, `universities`
]

// -- Tâches -----------------------------------------------------------------

= Suivi des tâches

#tache("Parseur Synthèse PDF bilingue (FR + EN)", statut: "fait")
#tache("Batch builder → cohort JSON (119/119)", statut: "fait")
#tache("Dashboard cohorte Streamlit (filtres, tri, cartes)", statut: "fait")
#tache("Dashboard profils universités (tier, historique, overrides)", statut: "fait")
#tache("Injection seuil GPA + catégorie SPE dans évaluateurs", statut: "fait")
#tache("Curriculum scraper EPFL (bachelor + master)", statut: "fait")
#tache("Curriculum matcher pour Minor Advisor", statut: "fait")
#tache("Design doc scraper curriculum", statut: "fait")
#tache("Décompresser les 119 ZIP restants", statut: "à faire")
#tache("Anonymiser la cohorte 2025-26", statut: "à faire")
#tache("Évaluer la cohorte complète avec le pipeline agent", statut: "à faire")

// -- Plan semaine prochaine -------------------------------------------------

= Plan pour la semaine prochaine

== Priorité haute
- Recevoir et décompresser les dossiers manquants (objectif : 220+
  candidats).
- Lancer le pipeline d'anonymisation sur la cohorte 2025--26 :
  `normalize-files` → `strip-passports` → `extract-text` →
  `anonymize`.
- Évaluer un premier lot de 20--30 candidats avec le pipeline
  agent et mesurer le taux d'accord avec le comité.

== Priorité moyenne
- Améliorer le parseur GPA pour gérer les cas limites (barèmes
  inversés allemands, pourcentages, GPA textuels).
- Ajouter l'export CSV/Excel depuis le dashboard cohorte pour
  le comité qui préfère travailler hors ligne.
- Intégrer le curriculum matcher dans le Minor Advisor pour des
  recommandations basées sur le contenu des cours.
