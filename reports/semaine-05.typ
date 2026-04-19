#import "template.typ": *

#show: weekly-report.with(
  semaine: 5,
  date: "17 mars 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Le pipeline complet PDF → extraction texte → anonymisation a été exécuté
    de bout en bout sur SCITAS. Les scripts SLURM d'extraction (PyMuPDF +
    RolmOCR) et d'anonymisation (GLiNER sur GPU) sont opérationnels. Un
    dashboard Streamlit interactif permet de visualiser côte à côte le PDF
    original, le texte extrait et la version anonymisée. Le protocole
    de délibération multi-agents en 4 phases a également été conçu et
    implémenté. 260 tests passent.
  ],
)

// -- Métriques de la semaine ------------------------------------------------

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "Tests unitaires",
    value: "260",
    detail: "Tous passent (+125)",
  ),
  metric(
    label: "Pipeline",
    value: "E2E",
    detail: "PDF → Texte → Anonymisé",
  ),
  metric(
    label: "Avancement global",
    value: "50%",
    detail: "Pipeline complet + Agents",
  ),
)

#v(0.3cm)

#progress-bar(pourcentage: 50, label: "Progression du projet")

// -- Travail effectué -------------------------------------------------------

= Travail effectué

== Pipeline de bout en bout sur SCITAS

Le pipeline complet d'ingestion des dossiers est désormais opérationnel
sur le cluster SCITAS de l'EPFL, de l'extraction du texte brut jusqu'à
l'anonymisation des PII. Deux familles de jobs SLURM ont été développées,
chacune déclinée en version *trial* (échantillon rapide, QoS debug) et
*full* (corpus complet) :

=== Extraction texte : deux phases

L'extraction suit une stratégie en deux phases pour optimiser le rapport
qualité/temps :

+ *Phase 1 --- PyMuPDF (CPU)* : extraction directe du texte intégré dans
  les PDF natifs. Rapide (~1 s/fichier) et suffisant pour les documents
  générés numériquement (lettres de motivation tapées, relevés de notes
  exportés)
+ *Phase 2 --- RolmOCR (GPU)* : OCR via un modèle de vision (vLLM) pour
  les documents scannés uniquement. Un heuristique détecte les PDF
  « image-only » (ratio texte/pages sous un seuil) et ne déclenche l'OCR
  que sur ceux-ci

Cette approche en deux phases évite de gaspiller du temps GPU sur les PDF
qui contiennent déjà du texte exploitable.

=== Anonymisation à grande échelle

Les scripts `slurm/anonymize-full.sh` et `slurm/anonymize-trial.sh`
exécutent le pipeline d'anonymisation (GLiNER + Presidio) sur GPU. Le
mode incrémental saute les fichiers déjà traités, et un mode `FORCE`
permet de tout retraiter. Le modèle GLiNER a été mis à jour vers
`knowledgator/gliner-multitask-large-v0.5` pour améliorer la détection
des entités.

Plusieurs corrections ont été nécessaires pour fiabiliser l'anonymisation :
- *Propagation des noms* : les noms détectés dans un document sont
  propagés pour éviter les faux négatifs sur les mentions partielles
- *Filtre de grades* : les notes (« 5.8/6 », « 18/20 ») ne sont plus
  redactées comme des PII
- *Allow-lists étendues* : mots communs et termes académiques ajoutés
  pour réduire la sur-anonymisation
- *Filtre d'identifiants numériques* : les séquences numériques courtes
  (numéros de cours, etc.) ne sont plus masquées

== Dashboard Streamlit

Un *dashboard interactif* (`dashboard/app.py`) a été développé pour
visualiser le pipeline de bout en bout. Accessible via `uv run poe dashboard`,
il permet de naviguer par semestre, candidat et document, puis d'afficher
trois panneaux côte à côte :

+ *PDF original* --- rendu page par page via PyMuPDF, avec zoom 2x pour
  une lecture nette
+ *Texte extrait* --- le Markdown produit par l'extraction, affiché avec
  le rendu Streamlit natif
+ *Version anonymisée* --- le texte avec les tags PII colorés par type
  (`<PERSON>` en rouge, `<EMAIL>` en bleu, `<PHONE>` en violet, etc.)

Trois modes de visualisation sont proposés :
- *Split View* : les trois panneaux en colonnes égales
- *PDF Focus* : le PDF occupe 60% de l'écran, texte et anonymisé en onglets
- *Comparison* : texte original vs anonymisé côte à côte

Sous chaque document anonymisé, un compteur affiche le nombre total
d'entités PII détectées, ventilé par type avec des badges colorés. Ce
dashboard est un outil essentiel pour la validation qualitative de
l'anonymisation : il permet de repérer immédiatement les faux positifs
(sur-anonymisation) et les faux négatifs (PII non détectés).

== Architecture multi-agents

Le coeur du système d'évaluation a été implémenté sous forme d'un
*protocole de délibération en 4 phases*, inspiré du fonctionnement
d'un comité d'admission réel. Cinq agents LLM spécialisés collaborent
pour produire un verdict structuré par candidat.

#figure(
  image("figures/deliberation_protocol.pdf", width: 88%),
  caption: [Protocole de délibération multi-agents en 4 phases.],
)

== Phase 1 --- Évaluation indépendante (parallèle)

Quatre agents évaluateurs s'exécutent en parallèle via `asyncio.gather()`,
chacun analysant un aspect spécifique du dossier sans voir les résultats
des autres :

+ *Academic Evaluator* --- évalue la solidité académique et la qualité
  de l'institution, en normalisant les différentes échelles de notation
  (GPA 4.0, système français sur 20, etc.)
+ *Reference Evaluator* --- analyse les lettres de recommandation avec
  calibration culturelle et comparaison à des lettres historiques
+ *Motivation Evaluator* --- évalue la clarté de la motivation et
  l'adéquation au programme MTE, en pénalisant les formulations génériques
+ *Devil's Advocate* --- examen critique du dossier complet : lacunes
  dans l'emploi, notes en baisse, incohérences entre documents

Chaque agent produit un `AgentScorecard` avec des scores par dimension
(1--10) et des justifications textuelles.

== Phase 2 --- Détection de désaccords

Le *Chair Agent* analyse l'ensemble des 4 scorecards pour identifier
les *conflits sémantiques* --- non pas de simples écarts de scores,
mais des interprétations divergentes d'un même élément de preuve. Pour
chaque conflit détecté, il formule une question de débat ciblée.

== Phase 3 --- Débat ciblé (conditionnel)

Si des conflits existent, un *débat en 2 rounds* est mené pour chacun :
- *Round 1* : chaque agent impliqué présente sa position
- *Round 2* : chaque agent répond aux arguments des autres

Si le panel est unanime, cette phase est entièrement sautée.

== Phase 4 --- Synthèse finale

Le Chair produit le `PanelVerdict` final en pondérant les avis par
domaine d'expertise. Le verdict contient 8 scores dimensionnels (1--10),
un score composite pondéré, une décision (ACCEPT / REJECT / WAITLIST)
et une justification en 2--3 phrases.

== Client LLM robuste

Le client LLM (`llm_client.py`) communique avec un endpoint
OpenAI-compatible (vLLM) et utilise le *JSON Schema mode* pour
garantir des réponses structurées validées par Pydantic :

- *Retry automatique* avec backoff exponentiel (1--30 s, 3 tentatives)
  sur erreurs 429, 502/503/504 et timeouts
- *Client HTTP partagé* (`httpx.AsyncClient`) réutilisé à travers
  toutes les phases pour minimiser l'overhead réseau
- *Hiérarchie d'erreurs* explicite : `LLMConnectionError` (transitoire)
  vs `LLMResponseError` (réponse invalide)

== Modèles d'évaluation immutables

Tous les modèles Pydantic (`AgentScorecard`, `Conflict`, `DebateEntry`,
`DebateTranscript`, `PanelVerdict`) sont *frozen* avec des dictionnaires
gelés via `types.MappingProxyType`. La validation garantit que tous les
scores sont dans l'intervalle 1--10.

// -- Défis et obstacles -----------------------------------------------------

= Défis et obstacles

#callout(titre: "Sortie structurée des LLM locaux", icon: "⚠", couleur: rgb("#EF4444"))[
  Les modèles locaux (Qwen 2.5 via vLLM) ne respectent pas toujours
  le schéma JSON demandé, surtout pour les structures imbriquées comme
  `PanelVerdict`. La validation Pydantic rattrape ces cas, mais le taux
  de retry augmente. À évaluer avec des modèles plus grands sur SCITAS.
]

- *Calibration des prompts* : les system prompts des évaluateurs doivent
  être suffisamment précis pour produire des scores cohérents entre
  exécutions, sans être trop rigides
- *Coût en tokens* : un dossier complet (4 évaluations + détection +
  débat + synthèse) requiert ~7 appels LLM minimum, davantage si des
  conflits déclenchent des débats

// -- Fichiers modifiés -----------------------------------------------------

= Fichiers modifiés

#callout(titre: "Résumé des changements", icon: "◆", couleur: rgb("#8B5CF6"))[
  *18 fichiers créés ou modifiés, ~2 800 lignes ajoutées* \
  \
  *Pipeline SCITAS :* \
  `slurm/extract-text.sh` --- extraction deux phases PyMuPDF + RolmOCR \
  `slurm/ocr-trial.sh`, `ocr-full.sh` --- jobs OCR GPU (trial + full) \
  `slurm/anonymize-trial.sh`, `anonymize-full.sh` --- anonymisation GPU \
  \
  *Dashboard :* \
  `dashboard/app.py` --- dashboard Streamlit 3 panneaux (397 lignes) \
  \
  *Anonymisation :* \
  `anonymizer/presidio_pipeline.py` --- propagation noms, filtre grades \
  `anonymizer/post_filters.py` --- filtre mots communs, IDs numériques \
  `anonymizer/allow_lists.py` --- allow-lists étendues \
  \
  *Agents :* \
  `agents/prompts.py` --- 5 system prompts spécialisés (95 lignes) \
  `agents/llm_client.py` --- client async avec retry et parsing JSON (182 lignes) \
  `agents/evaluators.py` --- 4 fonctions d'évaluation spécialisées (185 lignes) \
  `agents/chair.py` --- détection, débat, synthèse (259 lignes) \
  `agents/orchestrator.py` --- orchestrateur 4 phases (137 lignes) \
  `models/evaluation.py` --- 7 modèles Pydantic frozen (160 lignes)
]

// -- Tâches -----------------------------------------------------------------

= Suivi des tâches

#tache("Extraction texte deux phases (PyMuPDF + RolmOCR)", statut: "fait")
#tache("Scripts SLURM extraction + anonymisation (trial & full)", statut: "fait")
#tache("Anonymisation corpus complet sur GPU (GLiNER v0.5)", statut: "fait")
#tache("Corrections sur-anonymisation (grades, noms, allow-lists)", statut: "fait")
#tache("Dashboard Streamlit (3 vues, PII colorés)", statut: "fait")
#tache("Modèles d'évaluation Pydantic (frozen, validés)", statut: "fait")
#tache("System prompts pour 5 agents", statut: "fait")
#tache("Client LLM async (JSON Schema + retry)", statut: "fait")
#tache("4 évaluateurs spécialisés (parallèles)", statut: "fait")
#tache("Chair agent (détection, débat, synthèse)", statut: "fait")
#tache("Orchestrateur 4 phases", statut: "fait")
#tache("Tests unitaires (260 tests, couverture ≥ 40%)", statut: "fait")
#tache("Évaluation end-to-end sur dossiers réels", statut: "à faire")

// -- Plan semaine prochaine -------------------------------------------------

= Plan pour la semaine prochaine

== Priorité haute
- Premier test end-to-end du pipeline complet : dossier anonymisé →
  agents → `PanelVerdict`, comparaison avec la décision du comité réel
- Lier les dossiers anonymisés aux données structurées Parquet
  (décisions du comité, GPA, université)
- Ajuster les prompts sur la base des premiers résultats

== Priorité moyenne
- Évaluer la qualité des verdicts sur un échantillon de 20--50 candidats
- Explorer des modèles plus grands (70B) sur SCITAS pour améliorer
  la fiabilité du JSON Schema mode
- Ajouter des métriques au dashboard (taux d'anonymisation, distribution
  des types de PII par cohorte)
