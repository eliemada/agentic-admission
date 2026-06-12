#import "template.typ": *

#show: weekly-report.with(
  semaine: 8,
  date: "19 avril 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Quatre modifications au pipeline d'évaluation suite à la réunion avec
    le second superviseur : pondération explicite du score composite
    (académique dominant), format pros/cons à puces, assignation de mineur
    par LLM, et débats pliables dans le dashboard. Un script de démo
    évalue 5 candidats (2 admis, 3 refusés) et compare avec les décisions
    du comité. Premier taux d'accord : 20% --- le calibrage des prompts
    et des seuils de décision est en cours.
  ],
)

// -- Métriques de la semaine ------------------------------------------------

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "Candidats évalués",
    value: "5",
    detail: "2 admis, 3 refusés",
  ),
  metric(
    label: "Accord agent/comité",
    value: "20%",
    detail: "1/5 (avant calibrage)",
  ),
  metric(
    label: "Mineurs EPFL",
    value: "36",
    detail: "Registre complet 2025-26",
  ),
)

#v(0.3cm)

#progress-bar(pourcentage: 65, label: "Progression du projet")

// -- Travail effectué -------------------------------------------------------

= Travail effectué

== Score composite pondéré

Le score composite était calculé par le LLM, sans contrôle. Il est
maintenant déterministe, calculé en Python avec des poids fixes :

- *Académique* (25%) + *institution* (15%) + *référence* (15%) = 55%
  pour les critères primaires
- *Motivation* (5%) + *adéquation* (5%) + *risques* (5%) +
  *cohérence* (5%) = 20% pour les signaux secondaires
- *Confiance calibration* (10%) module la fiabilité des lettres

Le professeur a insisté : une lettre de motivation faible ne doit pas
couler un candidat académiquement fort. Les poids traduisent cette
consigne.

== Format pros/cons à puces

Les justifications textuelles libres ont été remplacées par un format
structuré `{"pros": [...], "cons": [...]}` à tous les niveaux :

- Nouveau modèle `DimensionJustification(pros, cons)` par dimension
- Nouveau modèle `VerdictSummary(pros, cons)` pour le verdict final
- Le dashboard affiche deux colonnes : vert (+) à gauche, rouge (-)
  à droite

Les membres du comité peuvent parcourir un candidat en quelques
secondes au lieu de lire des paragraphes.

== Assignation de mineur par LLM

Un cinquième agent (*Minor Advisor*) recommande les 3 mineurs EPFL
les mieux adaptés au profil du candidat. Il s'exécute en parallèle
avec les 4 évaluateurs pendant la Phase 1.

- `models/minor.py` : registre des 36 mineurs EPFL 2025-26 avec
  codes section, types (disciplinaire/interdisciplinaire) et contacts
- `agents/minor_advisor.py` : classification LLM avec la liste des
  mineurs injectée comme contexte structuré
- Règle par défaut : Industrial Engineering → Systems Engineering
  quand le modèle hésite
- Le dashboard affiche un badge bleu « Minor: X » sur chaque carte
  candidat et des cartes de recommandation classées dans l'onglet
  d'analyse

== Débats pliables dans le dashboard

Les transcriptions de débat entre agents étaient affichées en bloc,
forçant un défilement long. Elles sont maintenant dans un
`st.expander()` fermé par défaut. Un clic suffit pour les consulter.

== Script de démo (`scripts/demo_eval.py`)

Un script évalue 5 candidats pré-sélectionnés et compare les résultats
avec les décisions du comité :

#table(
  columns: (auto, auto, auto, auto),
  [*Candidat*], [*École*], [*Comité*], [*Agent*],
  [Banasevic], [UC San Diego], [Accepté], [Waitlist],
  [Polydorou], [NTUA Athènes], [Accepté], [Waitlist],
  [Atamny], [TU München], [Refusé], [Reject],
  [Boukhabrine], [McGill], [Refusé], [Waitlist],
  [Fukuno], [Kyoto], [Refusé], [Waitlist],
)

Accord : 1/5 (20%). Le système met presque tout le monde en
waitlist. Trois problèmes identifiés et corrigés cette semaine :

+ Les justifications des évaluateurs (format `dict[str, str]`)
  étaient silencieusement rejetées par Pydantic après le changement
  de type vers `DimensionJustification`. Le Chair recevait des
  scorecards vides.
+ `asyncio.gather(return_exceptions=True)` avalait les erreurs
  de validation. Les évaluateurs et le Minor Advisor sont maintenant
  séparés : les évaluateurs échouent bruyamment, le Minor Advisor
  est best-effort.
+ Les agents traitaient les artefacts OCR (caractères illisibles,
  GPA à zéro, champs vides) comme des incohérences réelles. Un
  caveat OCR a été ajouté à tous les prompts.

== Calibrage des prompts (en cours)

Corrections appliquées après analyse des 5 premiers verdicts :

- *Ancres de scoring* pour l'évaluateur académique : GPA top 5% →
  score 9-10, top 25% → 7-8, sous la médiane → 3-5
- *Seuils de décision* pour le Chair : `academic >= 7` et
  `institution >= 6` → accept ; `academic <= 4` → reject ;
  waitlist réservé aux cas limites
- *Caveat OCR* dans tous les agents : ne pas pénaliser les
  candidats pour du bruit d'extraction PDF
- *Devil's Advocate* recentré sur les risques substantiels (fraude,
  contradictions entre documents) plutôt que les erreurs de forme

// -- Défis et obstacles -----------------------------------------------------

= Défis et obstacles

#callout(titre: "Taux d'accord faible", icon: "⚠", couleur: rgb("#EF4444"))[
  20% d'accord avec le comité. Le système est trop indécis : 4
  candidats sur 5 reçoivent un « waitlist ». Le calibrage des
  seuils et des poids est la priorité immédiate.
]

- *Scorecards vides* : le bug `return_exceptions=True` a masqué
  des erreurs de validation pendant toute la première série de
  tests. Les verdicts reposaient uniquement sur le Chair sans
  input des évaluateurs.
- *Motivation trop pénalisante* : une lettre de motivation
  générique faisait chuter le composite d'un candidat à 9.02/10
  de GPA vers un « waitlist ».
- *Données manquantes du fichier interne* : le document
  `Internal guidelines for master applications` contient des
  seuils GPA par pays et des catégories d'universités (A/B/C/X)
  qui ne sont pas encore encodés dans les prompts.

// -- Fichiers modifiés -----------------------------------------------------

= Fichiers modifiés

#callout(titre: "Résumé des changements", icon: "◆", couleur: rgb("#8B5CF6"))[
  *10 fichiers créés ou modifiés, ~900 lignes ajoutées* \
  \
  *Nouveaux fichiers :* \
  `models/minor.py` --- 36 mineurs EPFL avec codes section (240 lignes) \
  `agents/minor_advisor.py` --- classification LLM de mineur (130 lignes) \
  `scripts/demo_eval.py` --- évaluation de 5 candidats (190 lignes) \
  \
  *Fichiers modifiés :* \
  `agents/chair.py` --- poids, `compute_composite()`, pros/cons \
  `agents/prompts.py` --- ancres de scoring, seuils, caveat OCR \
  `agents/evaluators.py` --- parsing `DimensionJustification` \
  `agents/orchestrator.py` --- 5 tâches parallèles, gather séparé \
  `models/evaluation.py` --- `DimensionJustification`, `VerdictSummary`, `MinorRecommendation` \
  `dashboard/review.py` --- colonnes pros/cons, débats pliables, badge mineur \
  `dashboard/verdict_loader.py` --- parsing justifications structurées
]

// -- Tâches -----------------------------------------------------------------

= Suivi des tâches

#tache("Score composite pondéré (Python, poids fixes)", statut: "fait")
#tache("Format pros/cons structuré (modèles + prompts + dashboard)", statut: "fait")
#tache("Registre des 36 mineurs EPFL 2025-26", statut: "fait")
#tache("Minor Advisor agent (LLM + parallèle Phase 1)", statut: "fait")
#tache("Débats pliables dans le dashboard", statut: "fait")
#tache("Script demo_eval.py (5 candidats)", statut: "fait")
#tache("Fix bug scorecards vides (return_exceptions)", statut: "fait")
#tache("Ancres de scoring + seuils de décision", statut: "fait")
#tache("Caveat OCR dans tous les prompts", statut: "fait")
#tache("Encoder les seuils GPA par pays (guidelines internes)", statut: "à faire")
#tache("Encoder les catégories d'universités A/B/C/X", statut: "à faire")
#tache("Évaluer sur 20-50 candidats pour mesurer l'accord", statut: "à faire")

// -- Plan semaine prochaine -------------------------------------------------

= Plan pour la semaine prochaine

== Priorité haute
- Relancer le demo après calibrage et mesurer le taux d'accord sur
  les 5 candidats. Objectif : >= 60%.
- Encoder les seuils GPA par pays et les catégories d'universités
  (A/B/C/X) du document « Internal guidelines for master
  applications » dans les prompts des agents.
- Étendre l'évaluation à 20-50 candidats pour obtenir un taux
  d'accord statistiquement significatif.

== Priorité moyenne
- Traitement léger des candidats EPFL internes (réduire le poids
  de la qualité institutionnelle et des lettres de recommandation).
- Ajouter le mapping bachelor → mineur comme prior pour le Minor
  Advisor (au-delà de la règle Industrial Engineering → Systems
  Engineering).
- Explorer la distribution des scores par dimension pour détecter
  les agents trop conservateurs ou trop généreux.
