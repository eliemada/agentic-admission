#import "template.typ": *

#show: weekly-report.with(
  semaine: 4,
  date: "10 mars 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Suite au feedback du Prof. de Rassenfosse, l'anonymisation a été
    calibrée pour préserver les signaux utiles à la décision d'admission
    (année de naissance, localisation, langues, institutions) tout en
    continuant à masquer les vrais PII. Validé sur 6 documents
    (2 candidats, 3 types de documents).
  ],
)

// -- Métriques de la semaine ------------------------------------------------

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "Tests unitaires",
    value: "135",
    detail: "Tous passent",
  ),
  metric(
    label: "Entités exclues",
    value: "4",
    detail: "LOCATION, NRP, ORG, organization",
  ),
  metric(
    label: "Avancement global",
    value: "30%",
    detail: "Phase : Anonymisation v2",
  ),
)

#v(0.3cm)

#progress-bar(pourcentage: 30, label: "Progression du projet")

// -- Travail effectué -------------------------------------------------------

= Travail effectué

== Feedback Prof. de Rassenfosse

L'anonymisation de la semaine 3 était fonctionnelle mais *trop agressive*
pour un usage en décision d'admission. Quatre points spécifiques ont été
soulevés :

+ *Date de naissance* : l'âge est un critère de rejet, il faut garder
  l'année de naissance
+ *Localisation* : permet d'identifier l'expérience internationale
+ *Langues* : compétence importante à conserver
+ *Noms d'institutions* : signal important dans les lettres de référence
  et les CV

== Calibrage de l'anonymisation

Trois mécanismes coordonnés ont été implémentés, chacun ciblant le bon
point d'interception dans le pipeline :

=== 1. Filtre d'exclusion d'entités (post-filtre)

Nouveau filtre `filter_excluded_entities()` placé en *première position*
dans le pipeline de filtres. Il supprime les résultats dont le type
d'entité est dans un ensemble configurable via la variable d'environnement
`ANONYMIZER_EXCLUDED_ENTITIES`.

*Pourquoi un post-filtre ?* Retirer les types de `_ENTITY_PLACEHOLDER_MAP`
ne suffit pas car Presidio les détecterait quand même. Retirer de
`_GLINER_ENTITIES` n'affecterait que GLiNER, pas les recognizers
Presidio intégrés. Le post-filtre agit comme un portail universel
après tous les recognizers.

Entités exclues par défaut : `LOCATION`, `NRP`, `organization`,
`ORGANIZATION`.

#callout(titre: "Point technique", icon: "◆", couleur: rgb("#2563EB"))[
  `organization` (minuscule) vient de GLiNER, `ORGANIZATION` (majuscule)
  vient du recognizer Presidio intégré. Les deux doivent être exclus
  pour éviter les faux positifs sur les noms d'institutions.
  Première version n'excluait que le minuscule --- 26 faux positifs
  sur le Statement of Purpose.
]

=== 2. Allow-list LANGUAGES

Même avec NRP exclu, des noms de langues comme « French » pouvaient être
capturés comme `PERSON` par d'autres recognizers. Un `frozenset` de 75
langues naturelles a été ajouté comme 6#super[e] catégorie d'allow-list
(défense en profondeur).

=== 3. Opérateur DOB personnalisé

Classe `DobYearOperator` (sous-classe de `presidio_anonymizer.Operator`)
qui extrait l'année à 4 chiffres du texte détecté et produit
`<DOB_1995>` au lieu de `<DOB>`. Regex : `\\b((?:19|20)\\d{2})\\b`.
Fallback vers `<DOB>` si aucune année trouvée.
Appliqué uniquement aux entités `"date of birth"` (GLiNER) ;
`DATE_TIME` (Presidio) reste `<DATE>`.

== Validation sur échantillon élargi

Pipeline testé sur `test_anon` (2 candidats, 6 documents : CV, lettre de
motivation, lettre de recommandation).

#callout(titre: "Résultats", icon: "✓", couleur: rgb("#10B981"))[
  *DOB* : `05/08/1984` → `<DOB_1984>` --- année préservée \
  *Locations* : Egypt, Saudi Arabia, Dubai, Switzerland, Lausanne, Beyrouth
  --- toutes préservées \
  *Langues* : Arabic (native), French (beginner), English --- préservées \
  *Institutions* : EPFL, UNESCO, Université Saint Joseph, USJ ESIB,
  British Council, INTERNATIONAL ADVANCED TECHNOLOGY --- préservées \
  *Vrais PII* : noms → `<PERSON>`, emails → `<EMAIL>`, téléphones →
  `<PHONE>`, adresses → `<ADDRESS>` --- toujours anonymisés
]

== Architecture du pipeline d'anonymisation

```
Texte brut
  │
  ▼
Presidio AnalyzerEngine (GLiNER + recognizers custom)
  │
  ├─ Allow-list (6 catégories : institutions, académique,
  │  pronoms, technique, activités, LANGUES)
  │
  ▼
Post-filtres (appliqués séquentiellement) :
  1. filter_excluded_entities  ← NOUVEAU (LOCATION, NRP, ORG)
  2. filter_by_entity_threshold
  3. filter_partial_words
  4. filter_by_length
  5. filter_common_words
  6. filter_duration_as_date
  │
  ▼
Presidio AnonymizerEngine
  ├─ DobYearOperator          ← NOUVEAU (date of birth → <DOB_YYYY>)
  └─ replace operator          (tous les autres types)
  │
  ▼
Texte anonymisé
```

// -- Défis et obstacles -----------------------------------------------------

= Défis et obstacles

#callout(titre: "Non-déterminisme GLiNER", icon: "⚠", couleur: rgb("#EF4444"))[
  Le modèle GLiNER produit parfois des entités différentes entre deux
  exécutions sur le même texte. Observé : un span de texte détecté
  comme `EPFL_SCIPER` lors d'une exécution mais pas la suivante, alors
  qu'aucun nombre à 6 chiffres n'était présent. Le pipeline de filtres
  gère ces cas, mais cela implique une légère variabilité des résultats.
]

- *Extraction PDF lente sur CPU* : Docling met ~25 min par PDF en local.
  La conversion à grande échelle nécessite SCITAS (GPU).
- *Docling instable sur certains scans* : crash sur une lettre de
  recommandation scannée (bug PIL/image de taille nulle)

// -- Tâches -----------------------------------------------------------------

= Suivi des tâches

#tache("Filtre d'exclusion d'entités (LOCATION, NRP, ORG)", statut: "fait")
#tache("Allow-list LANGUAGES (75 langues)", statut: "fait")
#tache("Opérateur DOB personnalisé (<DOB_YYYY>)", statut: "fait")
#tache("Tests unitaires (135 tests, couverture ≥ 40%)", statut: "fait")
#tache("Validation sur 2 candidats (6 documents)", statut: "fait")
#tache("Documentation logique d'anonymisation", statut: "fait")
#tache("Modèles Dossier, DocumentType, AgentEvaluation", statut: "fait")
#tache("Scanner + matcher dossiers ↔ Parquet (89,6 %)", statut: "fait")
#tache("Adaptateur intake ZIP/TAR/dir + path traversal", statut: "fait")
#tache("Triage reject-first (CV, motivation, relevé)", statut: "fait")
#tache("Conversion PDF → Markdown à grande échelle", statut: "bloqué")
#tache("Anonymisation corpus complet", statut: "à faire")
#tache("Pipeline LLM : évaluation vs décision comité", statut: "à faire")

== Modèle de données Dossier et matching Parquet

SCITAS étant indisponible, le travail s'est concentré sur la couche de
données en amont du pipeline LLM.

*Modèles créés* (`src/agentic_admission/models/`) :
- `DocumentType` --- 11 types de documents (CV, relevé de notes, lettre de
  motivation, recommandation, etc.), classifiés automatiquement à partir
  des noms de dossiers numérotés
- `Dossier` --- relie un dossier candidat (dossier physique) à son
  `CandidateRecord` Parquet, avec un `ProcessingStage`
  (RAW → NORMALIZED → EXTRACTED → ANONYMIZED → EVALUATED)
- `AgentEvaluation` / `PanelVerdict` --- modèles pour le panel
  multi-agent (strict, holistic, technical, moderator)

*Module intake* (`src/agentic_admission/intake/`) :
- `scanner.py` --- parcourt l'arborescence `{semestre}/{candidat}/`
  et construit des objets `Dossier` avec documents classifiés
- `matcher.py` --- apparie dossiers ↔ Parquet par semestre
  (`round1`→`fall`, `round2`→`spring`) et nom (génération de clés
  multiples pour noms composés, particules, accents)

*Résultat* : *1 021 / 1 139 dossiers appariés (89,6 %)*.
Les ~30 non-appariés sont des cas limites (apostrophes, particules
multi-mots). 41 tests, lint propre.

== Adaptateur d'intake et triage

- `adapter.py` --- détection automatique du format (ZIP, TAR/GZ,
  répertoire, répertoire de ZIPs) via magic bytes, extraction vers
  un répertoire de staging avec protection path traversal
- `validator.py` --- pré-screening reject-first : dossier incomplet
  (CV, lettre de motivation ou relevé de notes manquant)
  → `auto_reject=True`. Le panel d'agents peut outrepasser si le
  reste du dossier est exceptionnel
- Trois verdicts : `COMPLETE`, `INCOMPLETE`, `EMPTY` + score de
  complétude (0.0--1.0)
- CLI : `uv run poe ingest <source>`
- 67 tests au total, lint propre

// -- Plan semaine prochaine -------------------------------------------------

= Plan pour la semaine prochaine

== Priorité haute
- Conversion PDF → Markdown sur SCITAS (GPU) pour les ~13 600 fichiers
- Anonymisation à grande échelle et validation sur 50--100 dossiers

== Priorité moyenne
- Architecture des agents : prompts et rôles (strict, holistic,
  technical, moderator) basés sur les guidelines d'admission MTE
- Orchestrateur : fan-out vers 3 évaluateurs + modérateur,
  concurrence configurable pour batch de 200 dossiers
