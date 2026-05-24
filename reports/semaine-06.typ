#import "template.typ": *

#show: weekly-report.with(
  semaine: 6,
  date: "24 mars 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Consolidation et durcissement du pipeline d'anonymisation suite à
    l'audit qualitatif de la semaine précédente : reconnaissance
    explicite des passeports, propagation systématique des noms entre
    documents d'un même dossier, hash SHA-256 des chemins (les noms
    de fichiers contenaient encore des PII). Refactorisation de la
    table de mapping (JSON → Parquet) pour absorber la prochaine
    cohorte. Stabilisation CI : tous les hooks ruff / ty passent
    propre sur la base. Conception du dashboard d'aide à la décision
    pour le comité (`docs/plans/2026-03-24-admission-dashboard-design.md`).
  ],
)

// -- Métriques de la semaine ------------------------------------------------

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "PRs mergées",
    value: "2",
    detail: "#6 anonymizer + #9 lint",
  ),
  metric(
    label: "Faux positifs PII",
    value: "−40%",
    detail: "Vs. mesure semaine 5",
  ),
  metric(
    label: "Lint / type",
    value: "0",
    detail: "Erreurs sur `uv run poe lint`",
  ),
)

#v(0.3cm)

#progress-bar(pourcentage: 56, label: "Progression du projet")

// -- Travail effectué -------------------------------------------------------

= Travail effectué

== Audit anonymizer : corrections (PR \#6)

L'audit qualitatif de fin de semaine 5 (relecture manuelle de 30
dossiers anonymisés via le dashboard 3-panneaux) a remonté plusieurs
défauts récurrents :

- *Numéros de passeport non détectés* : GLiNER ne reconnaît pas les
  formats nationaux (8 caractères alphanumériques pour la Suisse,
  9 chiffres pour l'Inde, etc.).
- *Prénoms isolés non masqués* : le nom complet est détecté en
  page 1 du formulaire mais pas la mention isolée dans une
  recommandation (« I taught Maria during ... »).
- *Métadonnées PDF* qui contenaient le nom complet et étaient
  copiées intactes lors de l'extraction de texte.
- *Noms de fichiers* (`Cand. Master Synthese de la candidature_<NOM>_<NUM>.pdf`)
  qui re-divulguaient l'identité dans l'arborescence anonymisée.

Corrections livrées :

+ *Passport recognizer* dédié dans `anonymizer/recognizers.py` :
  patterns regex par pays (CH, IN, FR, IT, plus de 20 nationalités
  observées dans les cohortes historiques), validés contre les
  faux positifs (numéros de cours, codes ECTS).
+ *Injection des noms de métadonnées* : avant d'invoquer GLiNER,
  on extrait les champs Author / Title du PDF et on les ajoute à
  une liste de termes à masquer dans tout le dossier.
+ *Hashing des chemins* (SHA-256, 12 premiers caractères) :
  `Cand. Master Synthese..._F1226945050` devient
  `00a9e4255a5b/`. La table de correspondance `path_mapping` est
  conservée hors du dossier anonymisé.

== Refactor : Parquet path mapping

Le mapping `original_path → hashed_path` était stocké en JSON.
Pour 1 342 candidats × ~10 documents = 13 000+ entrées avec des
champs longs (noms de fichiers, paths absolus, métadonnées), la
lecture devenait lente côté dashboard. Refactor vers Parquet :

- Lecture 8× plus rapide (PyArrow vs `json.load`)
- Schéma typé qui empêche les régressions silencieuses
- Compression : 14 Mo JSON → 2.1 Mo Parquet
- API identique côté caller (`load_path_mapping()` retourne le même `dict`)

== Stabilisation CI (PR \#9)

`ruff check --select=ALL` remontait 90+ erreurs résiduelles sur la
base élargie (anonymizer, dashboard, slurm scripts). Catégorisation
et fix par lots :

- *N806* (variables non snake_case) : 12 occurrences dans
  `dashboard/app.py` (`PII_TYPES`, `BADGE_COLORS`) → renommées
  ou marquées comme constantes (`UPPER_CASE`).
- *SIM102* (collapsable nested if) : 8 occurrences dans
  `presidio_pipeline.py`.
- *ERA001* (commented-out code) : 15 blocs de TODO morts supprimés
  ou convertis en `# TODO(elie): ...`.
- *PLR2004* (magic values) : 30+ seuils déplacés vers des
  constantes nommées (`_GRADE_REGEX_MAX_LEN`, etc.).

Tous les hooks pre-commit (`ruff check`, `ruff format`, `ty check`,
`uv lock --check`) passent désormais propre. Le workflow GitHub
Actions est vert sur `main`.

== Design : dashboard d'aide à la décision

Document `docs/plans/2026-03-24-admission-dashboard-design.md`
finalisé avec le superviseur. Cible : faire évoluer le dossier
viewer Streamlit en outil d'aide à la décision pour le comité.

#callout(titre: "Vision produit", icon: "▶", couleur: rgb("#3B82F6"))[
  Le comité voit une *table de candidats triable / filtrable* avec
  un résumé IA en 3 phrases par dossier. Cliquer ouvre un panneau de
  détail avec : analyse par agent, références cliquables vers les
  documents (PDF / texte / anonymisé), et un *chat* pour interroger
  le dossier.
]

Décisions structurantes :

- *Décision agent* affichée comme badge coloré : Admit (vert) /
  Reject (rouge) / Discuss (ambre) / Pending (gris).
- *Confidence* affichée en italique « Insufficient information »
  quand \< 0.3 plutôt qu'un score à 2.
- *Trois onglets* dans le détail : Analyse agents (par défaut),
  Documents (avec inline links), Chat.
- Réutilisation maximale du dashboard 3-panneaux existant pour
  l'affichage des documents.

// -- Défis et obstacles -----------------------------------------------------

= Défis et obstacles

#callout(titre: "Faux positifs résiduels", icon: "⚠", couleur: rgb("#F59E0B"))[
  Le passport recognizer attrape parfois des codes de cours
  ressemblants (ex. « EE-330H » classé comme passeport US). Mitigé
  par un filtre post-detection qui exclut les tokens commençant par
  un préfixe institutionnel connu (`EE-`, `CS-`, `MATH-`, etc.).
]

- *Mapping JSON → Parquet* : la migration a temporairement cassé le
  dashboard pour les anciens runs. Un script `migrate_path_mapping.py`
  convertit les anciens JSON. Inclus dans la PR.
- *Performance GLiNER* : la propagation des noms double le temps
  d'inférence par dossier (2× passes). Acceptable pour une cohorte
  par semestre ; à monitorer si on passe au temps réel.

// -- Fichiers modifiés -----------------------------------------------------

= Fichiers modifiés

#callout(titre: "Résumé des changements", icon: "◆", couleur: rgb("#8B5CF6"))[
  *18 fichiers, ~1 200 lignes ajoutées / supprimées* \
  \
  *Anonymizer (PR \#6) :* \
  `anonymizer/recognizers.py` --- passport recognizers par pays \
  `anonymizer/presidio_pipeline.py` --- métadonnées + propagation \
  `anonymizer/post_filters.py` --- filtres préfixes institutionnels \
  `anonymizer/path_hashing.py` --- SHA-256 path hash + table \
  \
  *Refactor :* \
  `anonymizer/path_mapping.py` --- JSON → Parquet (PyArrow) \
  `scripts/migrate_path_mapping.py` --- migration one-shot \
  \
  *Lint / CI (PR \#9) :* \
  ~90 corrections ruff réparties sur 12 fichiers \
  `pyproject.toml` --- pin Python 3.12 dans pre-commit \
  \
  *Design :* \
  `docs/plans/2026-03-24-admission-dashboard-design.md` (130 lignes)
]

// -- Tâches -----------------------------------------------------------------

= Suivi des tâches

#tache("Passport recognizer (regex multi-pays + filtre préfixes)", statut: "fait")
#tache("Métadonnées PDF injectées comme PII", statut: "fait")
#tache("Propagation des noms entre documents d'un dossier", statut: "fait")
#tache("Hash SHA-256 des chemins (no-PII filenames)", statut: "fait")
#tache("Refactor path_mapping JSON → Parquet", statut: "fait")
#tache("Script de migration one-shot path_mapping", statut: "fait")
#tache("Stabilisation lint (90+ erreurs ruff résolues)", statut: "fait")
#tache("Design doc dashboard d'aide à la décision", statut: "fait")
#tache("Design doc pipeline E2E + calibration", statut: "en cours")
#tache("Implémenter le runner d'évaluation (CLI)", statut: "à faire")
#tache("Calibration culturelle des lettres (zsearch + profils)", statut: "à faire")

// -- Plan semaine prochaine -------------------------------------------------

= Plan pour la semaine prochaine

== Priorité haute
- Finaliser le design doc *E2E evaluation pipeline* :
  charger / enrichir les dossiers, ingérer les lettres historiques
  dans Zero Entropy, générer des profils de calibration par école
  via OpenRouter.
- Démarrer l'implémentation sur une branche dédiée
  (`feat/base-development`) : dossier loader, calibration ingest,
  evaluation runner CLI.
- Définir le format `PanelVerdict` final pour la persistance
  (JSON vs Parquet) et le contrat avec le dashboard.

== Priorité moyenne
- Extracteur GPA cross-système (4.0 / 6.0 / 20 / 100 / lettres) :
  spec et premier prototype.
- Préparer les SLURM scripts pour le runner d'évaluation
  (mode trial 5 candidats / mode full).
- Maquettage de la table candidat du dashboard avec données
  factices (`mock_data.py`).
