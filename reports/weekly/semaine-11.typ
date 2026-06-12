#import "template.typ": *

#show: weekly-report.with(
  semaine: 11,
  date: "9 mai 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Pipeline d'évaluation refondu pour les candidats EPFL-internes.
    Quatre composants déterministes ajoutés en amont du LLM : *gate
    GPA* (comparaison note-vs-seuil par institution), *profils
    d'évaluation* (poids différenciés EPFL-interne / externe),
    *mapping bachelor → mineurs* (court-circuit du Minor Advisor pour
    les 16 bachelors EPFL), et *fallback de profil université* (récup
    des métadonnées école quand le parquet ne matche pas). Run complet
    sur la cohorte Spring 2025-26 (128 candidats, dont 28
    EPFL-internes détectés). Tout livré dans une PR unique
    (\#18, squash-mergée sur main).
  ],
)

// -- Métriques de la semaine ------------------------------------------------

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "Cohorte évaluée",
    value: "128/128",
    detail: "Spring 2025-26",
  ),
  metric(
    label: "EPFL-internes",
    value: "28",
    detail: "100% mappés sans LLM",
  ),
  metric(
    label: "Tests ajoutés",
    value: "+22",
    detail: "epfl_minor_map (55 total verts)",
  ),
)

#v(0.3cm)

#progress-bar(pourcentage: 84, label: "Progression du projet")

// -- Travail effectué -------------------------------------------------------

= Travail effectué

== Gate GPA déterministe (`agents/gpa_gate.py`)

Avant : la décision GPA-vs-seuil était laissée à la délibération LLM,
qui faisait de l'arithmétique d'échelle (4/4, 6/6, 100/100, 1.0/1.0
allemand inversé) en interne et se trompait souvent.

Maintenant : un module Python compare la note normalisée au seuil de
l'institution et émet un verdict en 4 niveaux :

- *ABOVE* : note clairement au-dessus du seuil
- *NEAR* : dans une marge de tolérance (± 0.2 sur 4.0)
- *BELOW* : note en-dessous du seuil
- *UNKNOWN* : seuil ou note manquants

Le verdict est injecté dans le contexte du Chair sous forme de
ligne structurée (« GPA Threshold Verdict ») et utilisé pour deux
contraintes :

+ *Clamp* : si BELOW avec confiance d'extraction haute, le score
  `academic_strength` du Chair est plafonné à 4/10.
+ *Hard reject* : si BELOW avec confiance \>= 0.75, la décision
  finale est forcée à *reject*, indépendamment du composite.

Pour les EPFL-internes, la règle du comité est différente : la
moyenne *algèbre + analyse* (par sous-matière) est comparée au seuil
4.5 (ou 4.0 pour les changements de section), pas la moyenne
générale. Le gate utilise `epfl_internal_value(per_subject_averages)`
quand il s'agit d'un dossier interne.

== Profils d'évaluation (`agents/evaluation_profile.py`)

Les poids de scoring étaient globaux. Or 4 dossiers EPFL-internes sur
5 ne soumettent aucune lettre de recommandation, ce qui faisait
chuter leur composite de 25% à cause d'un évaluateur Reference qui
renvoyait `reference_quality=1`.

Solution : deux profils pondérés différemment, sélectionnés par
candidat.

#table(
  columns: (auto, auto, auto),
  align: (left, center, center),
  [*Dimension*], [*Externe*], [*EPFL-interne*],
  [academic_strength], [0.30], [*0.45*],
  [institution_quality], [0.18], [0.10],
  [reference_quality], [0.18], [*0.00*],
  [calibration_confidence], [0.12], [*0.00*],
  [motivation_clarity], [0.06], [0.15],
  [program_fit], [0.06], [0.15],
  [risk_flags], [0.05], [0.075],
  [consistency], [0.05], [0.075],
)

L'évaluateur Reference est court-circuité (sentinel scorecard) pour
les internes, ce qui économise un appel LLM et évite la pénalité.
Une fonction `renormalize_without_reference` couvre aussi les
externes qui n'envoient aucune lettre. Validation à la construction :
les poids doivent sommer à 1.0 (corrige un bug historique où ils
sommaient à 0.85).

== Mapping bachelor → mineurs (`agents/epfl_minor_map.py`)

Pour les 28 candidats EPFL-internes de Spring 2025-26, le Minor
Advisor LLM était à la fois inutile (le comité applique une règle
section-adjacence) et coûteux. Remplacé par une table déterministe
de 16 bachelors EPFL → 3 mineurs classés.

Détection : le formulaire EPFL « Synthèse de la candidature »
contient toujours un champ « Domaine principal d'études ». Une
regex extrait le bachelor ; si présent dans la table, retour direct
d'un `MinorRecommendation` avec scores fixes 10 / 9 / 8 et un
raisonnement déterministe. Sinon fallback vers le LLM advisor.

#callout(titre: "Validation sur Spring 2025-26", icon: "✓", couleur: rgb("#10B981"))[
  *28 candidats EPFL-internes détectés, 28 mappés sans LLM* (100%) : \
  Génie mécanique × 8, Sciences du vivant × 7, Microtechnique × 5,
  Systèmes de communication × 3, Physique × 2, Chimie × 1,
  Mathématiques × 1, Informatique × 1.
]

Validation à l'import : tous les noms de mineurs de la table doivent
exister dans `models.minor.ALL_MINORS` --- empêche une faute de
frappe de passer en production.

== Fallback de profil université

Quand le matcher parquet ne trouve pas le candidat (cas systématique
pour les nouvelles cohortes sans Excel comité), le pipeline utilisait
des champs école vides et n'appliquait pas le seuil GPA.

Le fallback `_fill_school_metadata_from_history` :

+ Lit le nom d'institution extrait par le LLM (`gpa_extractor`)
+ Cherche dans la table historique des profils universités
  (`curriculum/university_profiles.py`)
+ Restaure `school_quality` (tier A/B/C/X), `gpa_threshold`,
  `is_epfl_internal`
+ À défaut, détecte EPFL-interne directement par pattern matching
  sur le nom

== Surcharges Chair (clamps + hard-reject)

Test suite (`tests/test_chair_overrides.py`) qui vérifie :

- Le clamp `academic_strength <= 4` quand verdict GPA = BELOW et
  confiance \>= 0.75
- Le hard-reject post-synthèse dans les mêmes conditions
- L'absence d'effet quand la confiance est faible (le LLM garde la
  main)
- L'absence d'effet pour ABOVE / NEAR / UNKNOWN

== Tweaks dashboard

- Hauteur des lignes Excel ajustée pour afficher tout le contenu
  des cellules (retour comité semaine 10 : « on doit pouvoir lire
  sans cliquer »).
- Polish App / Dossier / Review.

== Infrastructure

- `llm_client.py` : routage de fournisseur OpenRouter consolidé,
  retries plus robustes sur 5xx transitoires.
- `prompts.py` + `evaluators.py` : ajustements mineurs cohérents
  avec les nouveaux profils.

// -- Défis et obstacles -----------------------------------------------------

= Défis et obstacles

#callout(titre: "Périmètre de la PR", icon: "⚠", couleur: rgb("#F59E0B"))[
  La PR \#18 bundle 7 thèmes (gate GPA, profils, mineurs, fallback,
  Chair, dashboard, infra) car les changements étaient interdépendants
  --- le mapping mineurs déterministe utilise le profil interne, qui
  utilise le gate GPA, qui utilise le fallback. Splitter en 4 PRs
  aurait créé des dépendances circulaires entre branches. Squash-merge
  pour aplatir l'historique sur `main`.
]

- *Détection EPFL-interne* : le matcher parquet ne fonctionne pas
  pour Spring 2025-26 (pas de fichier comité). Sans le fallback
  `_fill_school_metadata_from_history`, tous les internes étaient
  classés externes et perdaient 25% de composite.
- *Fixtures de test obsolètes* : `tests/test_chair.py` et
  `test_orchestrator.py` utilisent encore des chaînes là où le
  modèle attend `DimensionJustification` (régression d'un changement
  de modèle non couvert). Hors-scope de cette PR ; à corriger en
  semaine 12.
- *Désaccord comité sur le run complet* : 80 admis sur 128 sortis
  par l'agent, alors que le comité admet typiquement 40-50.
  Calibrage des seuils de décision à revoir avant le prochain run.

// -- Fichiers modifiés -----------------------------------------------------

= Fichiers modifiés

#callout(titre: "Résumé des changements (PR \#18)", icon: "◆", couleur: rgb("#8B5CF6"))[
  *29 fichiers, +4 448 / -123 lignes* \
  \
  *Nouveaux modules :* \
  `agents/gpa_gate.py` --- verdict ABOVE/NEAR/BELOW/UNKNOWN (568 l.) \
  `agents/evaluation_profile.py` --- profils Externe / EPFL-interne (228 l.) \
  `agents/epfl_minor_map.py` --- table 16 bachelors → 3 mineurs (291 l.) \
  \
  *Tests (4 nouvelles suites) :* \
  `tests/test_gpa_gate.py` (295 l.) \
  `tests/test_evaluation_profile.py` (199 l.) \
  `tests/test_chair_overrides.py` (249 l.) \
  `tests/test_epfl_minor_map.py` (300 l., 22 tests verts) \
  \
  *Modifiés :* \
  `agents/chair.py` --- clamps, hard-reject, sentinel reference \
  `agents/orchestrator.py` --- `_select_profile`, threading verdict GPA \
  `agents/run_evaluation.py` --- fallback profil + gate input EPFL \
  `agents/dossier_loader.py` --- `is_epfl_internal`, `has_meaningful_letters` \
  `agents/minor_advisor.py` --- court-circuit déterministe \
  `agents/gpa_extractor.py` --- per-subject averages \
  `curriculum/university_profiles.py` --- loader + finder + EPFL pattern \
  `dashboard/exports.py` --- hauteur ligne Excel \
  \
  *Documentation :* \
  `docs/plans/2026-05-08-{epfl-internal-branch,gpa-gate,profile-fallback}.md` \
  `docs/unofficial-guidelines.md` --- règles comité (banner INTERNAL ONLY)
]

// -- Tâches -----------------------------------------------------------------

= Suivi des tâches

#tache("Gate GPA déterministe (verdict 4 niveaux + EPFL per-subject)", statut: "fait")
#tache("Profils d'évaluation Externe / EPFL-interne (poids validés)", statut: "fait")
#tache("Mapping bachelor → mineurs (16 bachelors, 100% Spring 25-26)", statut: "fait")
#tache("Fallback profil université (matcher parquet manquant)", statut: "fait")
#tache("Surcharges Chair (clamps + hard-reject sous seuil)", statut: "fait")
#tache("Run complet Spring 2025-26 (128/128 candidats)", statut: "fait")
#tache("PR \#18 squash-mergée sur main (commit 0bff3a1)", statut: "fait")
#tache("22 nouveaux tests epfl_minor_map verts", statut: "fait")
#tache("Recalibrer les seuils de décision (80 admis vs 40-50 attendus)", statut: "à faire")
#tache("Corriger fixtures obsolètes test_chair.py / test_orchestrator.py", statut: "à faire")
#tache("Audit des dossiers où agent et comité divergent", statut: "à faire")

// -- Plan semaine prochaine -------------------------------------------------

= Plan pour la semaine prochaine

== Priorité haute
- Réduire le taux d'admission de 80/128 à 40--50/128 en
  resserrant les seuils du Chair (composite \>= 7.0 au lieu de
  6.5 pour `accept`, par exemple).
- Audit comparé sur les ~30 candidats où agent et comité
  divergent : identifier les biais (motivation trop indulgente,
  references trop sévères, gate GPA mal calibré sur certaines
  échelles).
- Corriger les fixtures de tests régressées (`test_chair.py`,
  `test_orchestrator.py`) pour rétablir la couverture complète.

== Priorité moyenne
- Évaluer Fall 2025-26 (la deuxième moitié de l'année) avec les
  paramètres recalibrés.
- Étendre la table mapping bachelor → mineurs aux bachelors plus
  rares (architecture, environnement, sciences humaines) si des
  dossiers en demandent.
- Ajouter une vue « différences agent vs comité » dans le
  dashboard pour faciliter l'audit.
