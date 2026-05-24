#import "template.typ": *

#show: weekly-report.with(
  semaine: 7,
  date: "7 avril 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Implémentation du pipeline E2E d'évaluation conçu en semaine 6.
    Trois sous-systèmes de calibration culturelle ajoutés : *ingest*
    (upload des lettres historiques anonymisées dans Zero Entropy),
    *profiler* (génération LLM de profils d'attentes par école via
    OpenRouter), *retriever* (récupération de lettres similaires au
    runtime). Le *dossier loader* unifie les fichiers anonymisés en
    un objet `DossierContent` enrichi par les métadonnées Parquet du
    comité. Premier *extracteur GPA* cross-système (4.0 / 6.0 / 20 /
    100). Runner CLI `run_evaluation.py` qui orchestre le pipeline
    sur un batch et compare avec les décisions du comité. Travail
    conduit sur la branche `feat/base-development`, mergée le
    19 avril (PR \#11).
  ],
)

// -- Métriques de la semaine ------------------------------------------------

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "Sous-systèmes",
    value: "3",
    detail: "ingest + profiler + retriever",
  ),
  metric(
    label: "Lettres historiques",
    value: "1 200+",
    detail: "Indexées dans Zero Entropy",
  ),
  metric(
    label: "Profils calibration",
    value: "84",
    detail: "Écoles avec ≥ 3 lettres",
  ),
)

#v(0.3cm)

#progress-bar(pourcentage: 62, label: "Progression du projet")

// -- Travail effectué -------------------------------------------------------

= Travail effectué

== Calibration culturelle (3 sous-systèmes)

Les évaluateurs ne peuvent pas juger une lettre de recommandation
hors contexte : « Excellent student » signifie quelque chose de très
différent à Stanford, à Polytechnique Paris ou à La Sapienza. La
calibration apporte ce contexte au moment de l'évaluation.

=== `calibration/ingest.py` --- Upload des lettres historiques

Toutes les lettres anonymisées des cohortes 2020--2024 sont uploadées
dans une collection Zero Entropy (zsearch) :

- Chunking automatique (paragraphes), embedding, indexation
- Métadonnées attachées : `school_name`, `country`, `school_quality`,
  `committee_decision` (admit / reject)
- Mode incrémental : ne re-uploade que les nouveaux dossiers
- ~1 200 lettres indexées au total

=== `calibration/profiler.py` --- Profils par école via OpenRouter

Pour chaque école avec au moins 3 lettres historiques, un LLM
(claude-sonnet via OpenRouter) génère un *profil de calibration* :

- Tonalité moyenne des lettres (mesurée / enthousiaste / dithyrambique)
- Phrases positives typiques pour cette école
- Signaux d'alerte spécifiques (ex. : « top 10% » mais sans rang)
- Tier estimé (A/B/C/X) confirmé contre les notes du comité

84 profils générés. Cache disque par école (les profils ne changent
pas tant qu'aucune lettre n'est ajoutée). Fallback en cascade si pas
assez de données : `country + tier` → `country` → générique.

=== `calibration/retriever.py` --- Récupération au runtime

Au moment d'évaluer un candidat, le *Reference Evaluator* reçoit :

+ Le profil de l'école du candidat (généré offline)
+ 3--5 lettres historiques *similaires* (recherche zsearch sur
  embedding) avec leur décision finale du comité
+ Le contexte permet une comparaison directe : « cette lettre est
  bien plus enthousiaste que la moyenne pour cette école → signal
  positif fort »

== `agents/dossier_loader.py` --- Chargement unifié

Centralise le parsing des dossiers anonymisés dans un objet
`DossierContent` :

- Charge tous les fichiers `text.md` d'un dossier candidat
- Classifie par type de document (Synthèse, Lettre de motivation,
  Recommandation, CV, Relevé, Diplôme, Autres)
- Concatène par type avec un séparateur structurel
- Enrichit avec les métadonnées Parquet du comité (décision,
  note, école) via le matcher `intake.matcher`

Sortie : un objet immutable utilisable directement par les
évaluateurs.

== `agents/gpa_extractor.py` --- GPA cross-système

Premier extracteur LLM dédié pour la note GPA. Doit gérer une
hétérogénéité massive :

#table(
  columns: (auto, auto, auto),
  align: (left, center, left),
  [*Système*], [*Échelle*], [*Exemples observés*],
  [Suisse], [1--6], [5.4 / 6, 4.75/6],
  [France], [0--20], [14.5/20, 16/20],
  [USA / Canada], [0--4], [3.8/4.0, GPA 3.21],
  [Allemagne], [1--5 inversé], [1.7/1.0 (top), 4.0 (bas)],
  [Italie], [0--30], [108/110, 28/30],
  [Inde / Pakistan], [0--10], [9.2/10 CGPA],
  [%], [0--100], [85.4%, top 5%],
)

L'extracteur produit un `GpaExtraction` structuré :

- `gpa_value` (str), `gpa_scale` (str), `grading_system` (str)
- `gpa_normalized` (float, 0--100) calculé déterministiquement
  côté Python pour éviter les erreurs d'arithmétique du LLM
- `confidence` (float, 0--1) : 1.0 si format clair, 0.3 si
  ambigu (ex. : « 3.21 until 10th semester » sans dénominateur)
- `notable_courses`, `trajectory` (`improving` / `stable` / `declining`)
- `institution_name` réextrait par le LLM (utile en fallback quand
  le matcher parquet rate)

== Runner d'évaluation (`agents/run_evaluation.py`)

CLI complet pour évaluer une cohorte et comparer avec le comité :

```
uv run poe run -- --semester 2024-25-spring --limit 30 --concurrency 4
```

- Charge les dossiers anonymisés via `load_all_anonymized_dossiers`
- Les enrichit avec les décisions du comité via `enrich_with_parquet`
- Pour chaque dossier : extraction GPA → calibration → orchestrateur
  4-phases → `PanelVerdict` sauvegardé en JSON
- Borne la concurrence avec un `asyncio.Semaphore` (par défaut 4)
- Sauvegarde immédiate par candidat (résilience aux crashes batch)
- Tableau de comparaison final : agent vs comité, taux d'accord
  par cohorte

== Documentation et figures

- Figure du protocole de délibération (`reports/figures/deliberation_protocol.{dot,pdf,svg,png}`)
  produite avec Graphviz pour les rapports.
- 3 plans archivés dans `docs/plans/` : design + implémentation
  multi-agents (mars 16), dashboard (mars 24), E2E pipeline
  (mars 27).
- Prompt structuré pour l'extracteur GPA dans
  `docs/prompts/gpa-extraction-agent.md`.

// -- Défis et obstacles -----------------------------------------------------

= Défis et obstacles

#callout(titre: "Coût de la calibration offline", icon: "⚠", couleur: rgb("#F59E0B"))[
  Génération des 84 profils via claude-sonnet : ~12 USD
  (1 appel/école avec contexte de 5--10 lettres). Acceptable pour
  un run one-shot, mais à re-monitorer si on doit régénérer
  fréquemment. Cache disque pour éviter la double dépense.
]

- *Bruit OCR dans les lettres historiques* : certaines lettres
  scannées de 2020--2021 contiennent du bruit qui pollue les
  embeddings. Filtre minimum-length (300 caractères) avant
  upload zsearch.
- *Profils trop génériques* pour les écoles avec peu de lettres :
  le fallback `country + tier` produit parfois des profils trop
  larges. À monitorer en évaluation réelle.
- *Branche longue* : `feat/base-development` accumule beaucoup
  de changements (\~8 500 lignes). Décision de la merger en un
  seul commit après validation E2E sur quelques candidats
  (planifié semaine 8).

// -- Fichiers modifiés -----------------------------------------------------

= Fichiers modifiés

#callout(titre: "Résumé des changements (branche `feat/base-development`)", icon: "◆", couleur: rgb("#8B5CF6"))[
  *35 fichiers, +8 526 / -214 lignes (mergé semaine 8 via PR \#11)* \
  \
  *Calibration (nouveau) :* \
  `calibration/ingest.py` --- upload zsearch (172 lignes) \
  `calibration/profiler.py` --- profils LLM par école (479 lignes) \
  `calibration/retriever.py` --- query runtime (134 lignes) \
  \
  *Agents (nouveau / étendu) :* \
  `agents/dossier_loader.py` --- chargement unifié (262 lignes) \
  `agents/gpa_extractor.py` --- extracteur cross-système (177 lignes) \
  `agents/run_evaluation.py` --- runner CLI (404 lignes) \
  `agents/chair.py`, `evaluators.py` --- intégration calibration \
  \
  *Dashboard (en parallèle) :* \
  `dashboard/review.py` --- vue verdict (843 lignes) \
  `dashboard/verdict_loader.py` --- parser JSON verdicts (332 lignes) \
  `dashboard/mock_data.py` --- données factices pour design (1 147 lignes) \
  \
  *Tests + figures + docs :* \
  `tests/test_gpa_extractor.py` (168 lignes) \
  `docs/prompts/gpa-extraction-agent.md` (191 lignes) \
  `reports/figures/deliberation_protocol.{dot,pdf,svg,png}`
]

// -- Tâches -----------------------------------------------------------------

= Suivi des tâches

#tache("Design doc E2E evaluation pipeline finalisé", statut: "fait")
#tache("Calibration ingest (zsearch / Zero Entropy)", statut: "fait")
#tache("Calibration profiler (84 profils via OpenRouter)", statut: "fait")
#tache("Calibration retriever (zsearch query runtime)", statut: "fait")
#tache("Dossier loader (DossierContent + enrichissement Parquet)", statut: "fait")
#tache("GPA extractor cross-système (Suisse, FR, US, DE, IT, IN)", statut: "fait")
#tache("Runner CLI run_evaluation.py (batch + concurrency + sauvegarde)", statut: "fait")
#tache("Vue verdict dans le dashboard (review.py)", statut: "fait")
#tache("Mock data pour itération design dashboard", statut: "fait")
#tache("Figure du protocole de délibération (Graphviz)", statut: "fait")
#tache("Tests gpa_extractor (multi-systèmes + edge cases)", statut: "fait")
#tache("Premier run E2E sur 5 candidats + comparaison comité", statut: "à faire")
#tache("Calibrer les seuils de décision (admit / reject / waitlist)", statut: "à faire")

// -- Plan semaine prochaine -------------------------------------------------

= Plan pour la semaine prochaine

== Priorité haute
- *Premier run E2E* : évaluer 5 candidats pré-sélectionnés
  (mix admit / reject / discuss) et comparer avec le comité.
  Objectif : valider que la chaîne complète fonctionne, pas
  encore de calibrer le taux d'accord.
- Merger `feat/base-development` dans `main` après validation
  E2E (PR \#11). Squash pour garder l'historique de `main`
  propre.
- Repenser le score composite : actuellement calculé par le LLM
  sans contrainte. Le superviseur veut une pondération explicite
  (académique dominant) calculée côté Python.

== Priorité moyenne
- Format pros/cons structuré (`{"pros": [...], "cons": [...]}`)
  pour remplacer les justifications en prose libre, plus rapide
  à parcourir pour le comité.
- Ajouter un *Minor Advisor* (5\^e agent) qui recommande des
  mineurs EPFL adaptés au profil du candidat.
- Débats pliables dans le dashboard (actuellement un bloc long
  qui force le défilement).
