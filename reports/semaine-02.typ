#import "template.typ": *

#show: weekly-report.with(
  semaine: 2,
  date: "26 février 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Réception des premiers dossiers de candidature par le superviseur.
    Extraction, inventaire et analyse exploratoire des dossiers étudiants.
    Conversion des guidelines d'admission en format exploitable pour le futur
    pipeline RAG.
  ],
)

// ── Métriques de la semaine ──────────────────────────────────────────────────

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "Dossiers reçus",
    value: "11",
    detail: "Candidats MTE 2025–26",
  ),
  metric(
    label: "Fichiers extraits",
    value: "~120",
    detail: "PDFs (CV, relevés, lettres, ...)",
  ),
  metric(
    label: "Avancement global",
    value: "12%",
    detail: "Phase: Exploration des dossiers",
  ),
)

#v(0.3cm)

#progress-bar(pourcentage: 12, label: "Progression du projet")

// ── Travail effectué ─────────────────────────────────────────────────────────

= Travail effectué

== Réception et organisation des dossiers

Le superviseur a transmis 11 dossiers de candidature au format zip, chacun
correspondant à un candidat pour le Master MTE 2025--26. Les dossiers ont été
décompressés et organisés dans l'arborescence du projet :

```
data/raw/applications/dossiers/
├── kammoun/        (10 fichiers)
├── khribeche/      (4 fichiers)
├── kurbanzade/     (13 fichiers)
├── nana_davies/    (13 fichiers)
├── oh/             (13 fichiers)
├── papathanasiou/  (12 fichiers)
├── sarin/          (13 fichiers)
├── senger/         (5 fichiers)
├── shreevastava/   (15 fichiers)
├── vejayan/        (10 fichiers)
└── zhang/          (10 fichiers)
```

Le placement dans `data/raw/` suit la convention _cookiecutter-datascience_ :
les données brutes sont immuables et jamais modifiées, seul le dossier
`data/processed/` contient les sorties dérivées.

== Analyse exploratoire des dossiers (EDA)

Un notebook Marimo dédié (`notebooks/dossier_eda.py`) a été créé pour
inventorier et visualiser le contenu des dossiers. L'analyse couvre :

- *Inventaire complet* : chaque fichier est catalogué avec son type de
  document, sa taille et son extension
- *Fichiers par candidat* : de 4 (khribeche) à 15 (shreevastava), avec une
  moyenne d'environ 11 fichiers
- *Types de documents* : 17 catégories identifiées (synthèse, lettre de
  motivation, CV, relevés de notes, lettres de recommandation, passeport,
  certificats linguistiques, résultats GRE, etc.)
- *Matrice de complétude* : vérification de la présence des 5 documents
  obligatoires (synthèse, motivation, CV, relevé de notes, pièce d'identité)
- *Documents optionnels* : couverture des lettres de recommandation, TOEFL/IELTS, GRE
- *Formats* : 100% des fichiers sont au format PDF

== Conversion des guidelines d'admission

Le document interne de guidelines d'admission (`mte_admission_guidelines_2024-04-22.docx`)
a été converti en Markdown structuré. Ce format permet :

- Un découpage naturel par sections pour le futur pipeline RAG
- Une lecture directe par les modèles de langage
- Un versionnement propre dans Git

Les guidelines définissent notamment :
- Les principes généraux de sélection (top candidates, diversité, anti-clusters)
- Les règles pour les doubles diplômes (officiels vs. "cachés")
- Les seuils de GPA recommandés par pays et catégorie d'université (A/B/C/X)
- Les cas particuliers (Polytechnique Paris, ENS Lyon, HES, candidats chinois)

// ── Résultats clés ───────────────────────────────────────────────────────────

= Résultats clés

#callout(titre: "Structure des dossiers", icon: "◆", couleur: rgb("#2563EB"))[
  Les dossiers suivent une convention de nommage cohérente issue de la plateforme
  ISA : `N - Cand. Master <Type de document>_<ID>/<fichier>.pdf`. Cette structure
  permet une extraction automatique du type de document par expression régulière.
]

#callout(titre: "Complétude variable", icon: "◆", couleur: rgb("#F59E0B"))[
  Certains dossiers sont très complets (13--15 fichiers avec recommandations,
  GRE, TOEFL) tandis que d'autres sont minimalistes (4--5 fichiers).
  Cette hétérogénéité devra être prise en compte par le système d'évaluation.
]

// ── Défis et obstacles ───────────────────────────────────────────────────────

= Défis et obstacles

- *Extraction du texte des PDFs* : les fichiers sont des PDFs, certains
  pourraient être des scans (images) nécessitant de l'OCR plutôt qu'une simple
  extraction de texte
- *Données sensibles* : les dossiers contiennent des copies de passeport et
  des informations personnelles --- le pipeline devra intégrer une couche
  d'anonymisation avant tout traitement par LLM
- *Seuils GPA par pays* : les guidelines mentionnent une table de seuils en
  annexe (slides) qui n'est pas incluse dans le document Word --- à obtenir
  séparément

// ── Tâches ───────────────────────────────────────────────────────────────────

= Suivi des tâches

#tache("Décompression et organisation des 11 dossiers", statut: "fait")
#tache("Notebook EDA dossiers (inventaire, complétude, visualisations)", statut: "fait")
#tache("Conversion des guidelines en Markdown", statut: "fait")
#tache("EDA globale des données tabulaires (1 342 candidats)", statut: "fait")
#tache("Extraction de texte des PDFs", statut: "à faire")
#tache("Détection scan vs. texte natif (OCR nécessaire ?)", statut: "à faire")
#tache("Pipeline d'anonymisation des données sensibles", statut: "en cours")
#tache("Connexion et tests sur les clusters HPC SCITAS", statut: "à faire")

// ── Plan semaine prochaine ───────────────────────────────────────────────────

= Plan pour la semaine prochaine

== Priorité haute
- Extraire le texte de tous les PDFs et identifier ceux nécessitant de l'OCR
- Commencer le pipeline de structuration : pour chaque candidat, produire un
  JSON normalisé avec les informations extraites de chaque document
- Obtenir la table de seuils GPA par pays (annexe des guidelines)

== Priorité moyenne
- Premiers tests d'inférence LLM sur les clusters HPC SCITAS
- Définir le schéma Pydantic pour les données structurées d'un dossier candidat
- Prototyper le chunking des guidelines pour le pipeline RAG
