#import "template.typ": *

#show: weekly-report.with(
  semaine: 2,
  date: "26 février 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Réception des dossiers de candidature (volées 2020--2026).
    Transfert sur le cluster SCITAS et mise en place de l'environnement SSH.
    Extraction, inventaire et analyse exploratoire des dossiers étudiants.
    Conversion des guidelines d'admission en format exploitable pour le futur
    pipeline RAG.
    Suppression des passeports après vérification de complétude via EDA.
    Recherche sur l'état de l'art des outils d'anonymisation de PII.
  ],
)

// ── Métriques de la semaine ──────────────────────────────────────────────────

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "Dossiers reçus",
    value: "2020--26",
    detail: "Toutes les volées MTE",
  ),
  metric(
    label: "Fichiers extraits",
    value: "~13 600",
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

Les dossiers de candidature contenant des données sensibles, le superviseur a
contacté les responsables IT de l'EPFL (Carlos et Jean-François), sur
recommandation de Nicolas Grandjean (AVP-E) et Chiara Tanteri (DPO), afin de
s'assurer des bonnes pratiques pour l'hébergement et l'accès à ces données.
Les directives de leur part sont en attente.

Les archives zip de l'ensemble des dossiers de candidature ont été reçues via
SWITCHdrive pour toutes les années académiques de 2020 à 2026. Les étapes
suivantes ont été réalisées :

- Téléchargement des archives depuis SWITCHdrive
- Décompression de l'ensemble des dossiers
- Transfert sur le cluster Izar (SCITAS) dans le répertoire `home`
- Suppression des fichiers de l'ordinateur personnel

L'ensemble du projet est hébergé sur le `home` du cluster Izar. Le travail
s'effectue désormais intégralement dans un environnement SSH sur le cluster.

À titre d'exemple, les 11 dossiers de la volée MTE 2025--26 sont organisés
comme suit :

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
inventorier et visualiser le contenu des dossiers sur l'ensemble des 11
semestres (2020--2026), soit *1 139 candidats* et *13 646 fichiers*. L'analyse
couvre :

- *Inventaire complet* : chaque fichier est catalogué avec son semestre, son
  type de document, sa taille et son extension
- *Candidats et fichiers par semestre* : de 77 à 122 candidats par semestre
- *Fichiers par candidat* : de 4 à 19, avec une moyenne de 12 fichiers
  (distribution et boxplot par semestre)
- *Types de documents* : 19 catégories identifiées (synthèse, lettre de
  motivation, CV, relevés de notes, lettres de recommandation, passeport,
  certificats linguistiques, résultats GRE, etc.)
- *Matrice de complétude* : vérification de la présence des 5 documents
  obligatoires par semestre (synthèse, motivation, CV, relevé de notes,
  pièce d'identité)
- *Documents optionnels* : couverture des lettres de recommandation, TOEFL/IELTS, GRE
- *Formats* : majorité de PDFs, avec quelques fichiers à extensions
  incorrectes ou tronquées à corriger

== Suppression des documents d'identité

Les copies de passeport présentes dans les dossiers de candidature ont été
supprimées. Avant suppression, une analyse exploratoire (EDA) a été effectuée
pour vérifier la présence de ces documents dans chaque dossier. Les résultats
de cette vérification (liste des candidats, confirmation de présence/absence
du passeport) ont été sauvegardés dans un fichier Parquet
(`data/processed/all_candidates.parquet`) afin de conserver une trace de
complétude sans stocker les documents sensibles eux-mêmes.

== Recherche sur les outils d'anonymisation de PII

Une revue de l'état de l'art des outils de suppression de données personnelles
(PII) a été menée, couvrant les solutions pour le texte, les images et les
documents scannés. L'objectif est de choisir la meilleure approche pour
anonymiser les dossiers de candidature avant tout traitement par LLM.

=== Outils évalués

- *Microsoft Presidio* #footnote[#link("https://github.com/microsoft/presidio")] :
  framework open-source combinant NER, regex et checksums. Bonne base
  extensible, mais précision limitée seul et nécessite un backend NER plus
  puissant pour les cas complexes
- *Private AI* #footnote[#link("https://www.private-ai.com")] :
  solution commerciale la plus complète avec plus de 50 types d'entités,
  52 langues, OCR intégré et déploiement on-premise via conteneur Docker
- *Anonymizer SLM* #footnote[#link("https://huggingface.co/blog/pratyushrt/anonymizerslm")] :
  modèles légers (0.6B à 4B paramètres) atteignant des performances
  comparables à GPT-4 pour l'anonymisation, déployables sur GPU HPC
- *LLM Guard* #footnote[#link("https://appsecsanta.com/llm-guard")] :
  guardrails open-source auto-hébergés avec scanner d'anonymisation intégré
- *John Snow Labs* #footnote[#link("https://www.johnsnowlabs.com/comparing-john-snow-labs-medical-text-de-identification-with-microsoft-presidio/")] :
  spécialisé médical (F1 de 98.6%), intéressant pour la méthodologie
  d'évaluation

=== Approche retenue

L'architecture envisagée pour le pipeline d'anonymisation est un *pipeline
hybride* adapté au déploiement sur SCITAS :

+ *Couche OCR* : extraction de texte depuis les documents scannés (Tesseract,
  EasyOCR ou Surya)
+ *Presidio comme orchestrateur* : framework extensible avec recognizers
  personnalisés
+ *LLM local comme backend NER* : utilisation du modèle Llama déjà prévu dans
  la configuration (`MODEL_NAME`) comme recognizer contextuel pour Presidio,
  afin de détecter les PII que les regex et spaCy manquent
+ *Anonymizer SLM* : modèles légers pour le remplacement des entités détectées

Cette architecture permet un traitement entièrement local (aucune donnée ne
quitte le cluster SCITAS), conformément aux exigences du DPO.

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

#figure(
  image("figures/completeness_matrix.png", width: 100%),
  caption: [Matrice de complétude des documents obligatoires par semestre (2020--2026).],
)

#callout(titre: "Question ouverte", icon: "?", couleur: rgb("#8B5CF6"))[
  Les dossiers incomplets (documents obligatoires manquants) font-ils l'objet
  d'un rejet automatique, ou sont-ils tout de même évalués ?
]

// ── Défis et obstacles ───────────────────────────────────────────────────────

= Défis et obstacles

- *Extraction du texte des PDFs* : les fichiers sont des PDFs, certains
  pourraient être des scans (images) nécessitant de l'OCR plutôt qu'une simple
  extraction de texte
- *Données sensibles* : les copies de passeport ont été supprimées après
  vérification de complétude, mais les PDFs restants contiennent encore des
  informations personnelles (noms, adresses, dates de naissance). Le pipeline
  d'anonymisation hybride (Presidio + LLM local) devra être implémenté avant
  tout traitement par LLM
- *Seuils GPA par pays* : la table de seuils par pays et catégorie d'université
  (A/B/C/X) a été extraite des slides et intégrée dans le Markdown des guidelines

// ── Tâches ───────────────────────────────────────────────────────────────────

= Suivi des tâches

#tache("Décompression et organisation de l'ensemble des dossiers (2020–2026)", statut: "fait")
#tache("Notebook EDA dossiers (inventaire, complétude, visualisations)", statut: "fait")
#tache("Conversion des guidelines en Markdown (incl. seuils GPA)", statut: "fait")
#tache("EDA globale des données tabulaires (1 342 candidats)", statut: "fait")
#tache("Transfert des données et mise en place de l'environnement SSH sur SCITAS", statut: "fait")
#tache("Vérification de complétude des passeports et sauvegarde en Parquet", statut: "fait")
#tache("Suppression des copies de passeport des dossiers", statut: "fait")
#tache("Recherche état de l'art : outils d'anonymisation de PII", statut: "fait")
#tache("Extraction de texte des PDFs", statut: "à faire")
#tache("Détection scan vs. texte natif (OCR nécessaire ?)", statut: "à faire")
#tache("Mise en place de Presidio avec recognizers personnalisés", statut: "à faire")
#tache("Intégration d'un LLM local comme backend NER pour Presidio", statut: "à faire")
#tache("Tests des modèles Anonymizer SLM sur SCITAS", statut: "à faire")
#tache("Pipeline d'anonymisation des données sensibles", statut: "en cours")

// ── Plan semaine prochaine ───────────────────────────────────────────────────

= Plan pour la semaine prochaine

== Priorité haute
- Extraire le texte de tous les PDFs et identifier ceux nécessitant de l'OCR
- Mettre en place le pipeline d'anonymisation : installer Presidio, configurer
  les recognizers personnalisés, et tester sur un échantillon de dossiers
- Commencer le pipeline de structuration : pour chaque candidat, produire un
  JSON normalisé avec les informations extraites de chaque document
- Vérifier l'exhaustivité des seuils GPA intégrés (pays manquants ?)

== Priorité moyenne
- Premiers tests d'inférence LLM sur les clusters HPC SCITAS
- Évaluer les modèles Anonymizer SLM (1.7B--4B) sur les GPU SCITAS pour
  le remplacement contextuel des PII
- Définir le schéma Pydantic pour les données structurées d'un dossier candidat
- Prototyper le chunking des guidelines pour le pipeline RAG
