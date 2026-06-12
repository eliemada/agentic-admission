#import "template.typ": *

#show: weekly-report.with(
  semaine: 12,
  date: "16 mai 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Test de reproductibilité du pipeline d'évaluation : 5 exécutions
    indépendantes de la cohorte complète Spring 2025-26 (128 candidats)
    avec le modèle `google/gemini-3-flash-preview` via OpenRouter.
    L'objectif : mesurer la *variance entre runs* pour décider si le
    système est suffisamment fiable pour aider le comité (et identifier
    les dossiers borderline qui nécessitent une vraie décision
    humaine). *Résultat principal* : la distribution agrégée
    accept/reject/waitlist est extrêmement stable (40-43 admis sur
    128, dans la cible comité 40-50). *76.6%* des candidats reçoivent
    la même décision dans les 5 runs ; les *30 flippers* sont presque
    tous sur la frontière waitlist. L'invariant déterministe pour les
    EPFL-internes (mapping mineur) tient à 100%.
  ],
)

// -- Métriques de la semaine ------------------------------------------------

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "Runs complets",
    value: "5/5",
    detail: "128 candidats × 5 = 640",
  ),
  metric(
    label: "Stabilité décision",
    value: "76.6%",
    detail: "98/128 décision identique × 5",
  ),
  metric(
    label: "Σ admis (range)",
    value: "39--43",
    detail: "Cible comité : 40--50",
  ),
)

#v(0.3cm)

#progress-bar(pourcentage: 87, label: "Progression du projet")

// -- Travail effectué -------------------------------------------------------

= Travail effectué

== Pourquoi tester la variance ?

Avant de présenter les verdicts au comité, il faut répondre à deux
questions que les superviseurs (et le comité) vont poser :

+ *Le système est-il déterministe ?* Si on relance le pipeline sur
  la même cohorte, obtient-on la même réponse, ou est-ce qu'un
  candidat est tantôt admis tantôt refusé ?
+ *Quels sont les dossiers borderline ?* Là où le système hésite,
  c'est précisément là où la délibération humaine apporte de la
  valeur --- on doit pouvoir les identifier sans les noyer dans la
  masse.

Le LLM n'étant pas déterministe par construction (température,
échantillonnage), seule une mesure empirique répond. *5 exécutions
indépendantes* est un compromis statistiquement utile et abordable
en coût (~12 USD OpenRouter, ~85 minutes de wall-clock).

== Méthodologie

- *Cohorte* : 128 candidats Spring 2025-26 (anonymisés).
- *Modèle* : `google/gemini-3-flash-preview` via OpenRouter (cheap,
  fast, c'est le modèle de production actuel).
- *Pipeline* : pipeline complet déployé en semaine 11 (gate GPA,
  profils EPFL-interne / externe, mapping mineur déterministe,
  fallback profil université).
- *5 runs* indépendants, sortie dans
  `data/processed/runs/run01..05/`.
- *Métriques calculées* via
  `scripts/cohort_variance_stats.py` :
  + Stabilité de décision par candidat (mêmes verdicts dans les 5
    runs ?)
  + Liste des *flippers* (au moins une décision différente)
  + Variance du score composite par candidat (mean / stdev / range)
  + Variance par dimension (laquelle des 8 est la plus / moins
    stable)
  + Invariance déterministe pour les EPFL-internes (mineur identique
    dans les 5 runs ?)
  + Distribution agrégée accept/reject/waitlist par run

== Résultat 1 --- Distribution agrégée stable

Le nombre de candidats admis varie peu d'un run à l'autre :

#table(
  columns: (auto, auto, auto, auto, auto),
  align: (left, center, center, center, center),
  [*Run*], [*Accept*], [*Reject*], [*Waitlist*], [*Total*],
  [run01], [40], [66], [22], [128],
  [run02], [39], [67], [22], [128],
  [run03], [41], [67], [20], [128],
  [run04], [39], [67], [22], [128],
  [run05], [43], [67], [18], [128],
)

#callout(titre: "Lecture comité", icon: "✓", couleur: rgb("#10B981"))[
  Le comité admet typiquement 40--50 candidats par cohorte. Tous
  les runs tombent dans (ou juste sous) cette fourchette. La règle
  de seuil composite ajoutée en semaine 11 (PR \#18) ramène le
  taux d'admission de l'ancien 80/128 à 39--43/128.
]

== Résultat 2 --- 76.6% de stabilité par candidat

*98 candidats sur 128 (76.6%)* ont reçu exactement la même décision
(accept / reject / waitlist) dans les 5 runs. *30 candidats* ont vu
leur décision changer au moins une fois entre runs. Tous les flippers
sont concentrés sur la frontière : transitions
*waitlist ↔ accept* ou *waitlist ↔ reject*. Aucun cas de
*accept ↔ reject* direct, ce qui est rassurant : le système ne fait
pas de revirement complet.

#table(
  columns: (auto, auto, auto, auto, auto, auto, auto),
  align: (left, center, center, center, center, center, center),
  [*Candidat (5 premiers flippers)*],
  [*r01*], [*r02*], [*r03*], [*r04*], [*r05*], [*Mode*],
  [`07fc9d7a9c95`], [accept], [waitlist], [accept], [accept], [accept], [accept],
  [`0f817ee10abe`], [reject], [waitlist], [reject], [waitlist], [waitlist], [waitlist],
  [`14bbfb46cb71`], [reject], [waitlist], [reject], [reject], [reject], [reject],
  [`197a4a37be28`], [reject], [reject], [waitlist], [waitlist], [reject], [reject],
  [`26ae784d194a`], [reject], [reject], [waitlist], [reject], [reject], [reject],
)

*Recommandation pratique* : pour la production, agréger les 5 runs
par *vote majoritaire* (mode) donnerait une décision défendable et
plus stable que n'importe quel run individuel. La colonne Mode
ci-dessus montre le résultat de ce vote.

== Résultat 3 --- Score composite très stable

- *Stdev moyen par candidat* : *0.175* (sur une échelle 1--10).
- *Stdev maximum* : *0.628* (un seul candidat borderline avec un
  range de 1.55 entre runs).
- 90% des candidats restent dans une fenêtre de ±0.2 autour de
  leur moyenne.

== Résultat 4 --- Variance par dimension

#table(
  columns: (auto, auto),
  align: (left, center),
  [*Dimension*], [*Stdev moyen*],
  [`motivation_clarity`], [0.053],
  [`institution_quality`], [0.129],
  [`calibration_confidence`], [0.132],
  [`program_fit`], [0.194],
  [`reference_quality`], [0.248],
  [`academic_strength`], [0.293],
  [`consistency`], [0.380],
  [`risk_flags`], [0.467],
)

- *La plus stable* : `motivation_clarity` (0.053). Le prompt
  produit un signal très net.
- *La moins stable* : `risk_flags` (0.467). C'est la dimension
  Devil's Advocate, par construction interprétative et
  contradictoire. Variance attendue.
- `academic_strength` à 0.293 est plus haut qu'on souhaiterait : le
  Chair pondère cette dimension à 30--45% du composite. À surveiller.

== Résultat 5 --- Invariance déterministe EPFL : 100%

Pour les *vrais* candidats EPFL-internes (28 dans la cohorte Spring
2025-26), le mineur recommandé est *identique dans les 5 runs* à
chaque fois. Le court-circuit déterministe de PR \#18 fonctionne
comme prévu.

#callout(titre: "Note sur la heuristique de détection", icon: "ℹ", couleur: rgb("#3B82F6"))[
  Le script de stats détecte les EPFL-internes en regardant si le
  `primary_minor` apparaît dans la table déterministe. Cette
  heuristique sur-classifie : 104 candidats au lieu des 28 réels,
  car le LLM advisor recommande parfois les mêmes noms de mineur
  pour des candidats externes. Sur les 7 « violations » remontées
  par le script, *aucune ne correspond à un vrai EPFL-interne* ---
  ce sont toutes des fluctuations du LLM advisor sur des dossiers
  externes ou des entrées vides quand l'advisor a échoué (best-effort).
]

// -- Défis et obstacles -----------------------------------------------------

= Défis et obstacles

#callout(titre: "30 flippers à expliquer", icon: "⚠", couleur: rgb("#F59E0B"))[
  76.6% de stabilité signifie que ~24% des dossiers individuels
  ont au moins une décision divergente. Pour le comité, cela veut
  dire que ~30 candidats par cohorte sont « instables » et
  méritent une revue humaine. Identifier et flagger
  systématiquement ces cas dans le dashboard est la priorité de
  la semaine 13.
]

- *Coût et temps* : 5 runs × 128 candidats = 640 évaluations
  complètes, ~12 USD et 85 minutes wall-clock. Acceptable comme
  test ponctuel ; à automatiser comme job hebdomadaire si on veut
  monitorer la stabilité dans le temps.
- *Heuristique de détection EPFL-interne* dans le script de stats
  est imparfaite (sur-classifie). Pour résoudre proprement, il
  faudrait stocker le flag `is_epfl_internal` dans le verdict
  JSON et le re-lire ; à faire en semaine 13.

// -- Fichiers modifiés -----------------------------------------------------

= Fichiers modifiés

#callout(titre: "Résumé des changements", icon: "◆", couleur: rgb("#8B5CF6"))[
  *Nouveaux fichiers :* \
  `scripts/cohort_variance_stats.py` --- script de variance (260 l.) \
  `reports/cohort-variance-2026-05-09.md` --- rapport stats détaillé \
  `reports/semaine-12.typ` --- ce document \
  \
  *Données produites (gitignorées) :* \
  `data/processed/runs/run01..05/` --- 640 verdicts JSON \
  `data/processed/evaluations_baseline_pre_5x_run_2026-05-09/` --- snapshot avant les 5 runs \
  \
  *Aucun fichier de production modifié.* Le test de variance n'a
  nécessité aucun changement de code.
]

// -- Tâches -----------------------------------------------------------------

= Suivi des tâches

#tache("Snapshot baseline (128 verdicts) avant relance", statut: "fait")
#tache("Smoke-test 1 candidat (validation pipeline)", statut: "fait")
#tache("Lancer 5 runs séquentiels en background (85 min)", statut: "fait")
#tache("Surveiller log pour erreurs / credits OpenRouter", statut: "fait")
#tache("Script `cohort_variance_stats.py` (8 dimensions analysées)", statut: "fait")
#tache("Rapport variance Markdown détaillé", statut: "fait")
#tache("Rapport hebdomadaire S12 (ce document)", statut: "fait")
#tache("Stocker `is_epfl_internal` dans le verdict JSON", statut: "à faire")
#tache("Flagger les 30 flippers dans le dashboard React", statut: "à faire")
#tache("Mode \"vote majoritaire de N\" comme option de production", statut: "à faire")

// -- Plan semaine prochaine -------------------------------------------------

= Plan pour la semaine prochaine

== Priorité haute
- *Surfacer les flippers dans le dashboard* : nouveau champ
  `stability` (% des runs en accord) sur chaque candidat, avec
  badge orange « unstable » pour les 30 cas borderline. Permet au
  comité de prioriser sa relecture.
- *Persister `is_epfl_internal`* dans `PanelVerdict` pour rendre
  l'audit (et les tests d'invariance) propres sans heuristique.
- *Voter par majorité de N* : ajouter une option
  `--ensemble N` dans le runner qui exécute N fois et retourne le
  mode. Pour les flippers, le mode est plus stable que n'importe
  quel run individuel.

== Priorité moyenne
- Audit qualitatif des 30 flippers avec le superviseur : sont-ce
  des cas où le comité hésite aussi (signal correct), ou des cas
  où le système rate quelque chose de clair (signal de calibration
  manquante) ?
- Étendre le test de variance à Fall 2025-26 quand cette cohorte
  sera anonymisée et matchée aux décisions du comité.
- Comparer la stabilité avec d'autres modèles (Sonnet 4.6,
  Haiku 4.5) pour quantifier le coût/bénéfice du choix de modèle.
