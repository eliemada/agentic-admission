#import "template.typ": *

#show: weekly-report.with(
  semaine: 13,
  date: "23 mai 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Audit comparé comité vs système sur la cohorte Spring 2025-26
    (5 runs agrégés par vote majoritaire). 47 désaccords sur 128
    candidats, dont 19 cas où le système accepte un dossier que le
    comité refuse (universités internationales fortes) et 9 cas où
    le système refuse un dossier que le comité accepte (presque tous
    EPFL-internes en transition de section). Deux itérations de
    prompt sur le bloc EPFL-interne ont fait passer l'accord avec le
    comité de 14/28 à 19/28 pour cette sous-cohorte. Les 5 cas
    restants ont une moyenne algèbre+analyse entre 4.0 et 4.5 :
    Maillard, Hegi, Croisier, Gruber, Kvedarauskaite. Le système les
    refuse car ils sont sous le seuil 4.5 codé en dur ; le comité
    les a admis après examen détaillé. Email à Geraldine pour
    clarifier la règle officielle ; sa réponse arrivera en semaine 14.
  ],
)

// -- Métriques de la semaine ------------------------------------------------

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "Désaccords comité",
    value: "47/128",
    detail: "36.7% sur la cohorte entière",
  ),
  metric(
    label: "EPFL-internes",
    value: "14 → 19 / 28",
    detail: "Accord après 2 itérations prompt",
  ),
  metric(
    label: "Scripts d'analyse",
    value: "5",
    detail: "compare, rerun, before/after, backfill",
  ),
)

#v(0.3cm)

#progress-bar(pourcentage: 90, label: "Progression du projet")

// -- Travail effectué -------------------------------------------------------

= Travail effectué

== Audit comité vs système

Le plan de semaine 12 demandait un audit qualitatif des dossiers où
agent et comité divergent. J'ai écrit `scripts/compare_committee_vs_runs.py`
pour produire une matrice de confusion à partir des 5 runs agrégés
par vote majoritaire. Le résultat sur Spring 2025-26 :

#table(
  columns: (auto, auto, auto, auto, auto),
  align: (left, center, center, center, center),
  [*Comité \\ Système*], [*accept*], [*waitlist*], [*reject*], [*total*],
  [*accept*], [22], [10], [9], [41],
  [*waitlist*], [0], [0], [0], [0],
  [*reject*], [19], [9], [59], [87],
)

Le comité n'utilise jamais la catégorie waitlist en sortie (toutes
les hésitations sont arbitrées en réunion), donc les colonnes
waitlist du système correspondent à des cas que le comité a tranchés
dans un sens ou l'autre. *L'accord brut sort à 81/128 (63.3%).*

Quatre types de désaccord à isoler :

#callout(titre: "Types de désaccord", icon: "◆", couleur: rgb("#8B5CF6"))[
  *Type A. Comité refuse, système accepte (19 cas).* Universités
  internationales reconnues : NUS, Bocconi, RWTH Aachen, Erasmus
  Rotterdam, Duke Kunshan, KCL. Le score composite moyen sur ces 19
  cas est 8.5. Le comité a vu autre chose dans le dossier (lettres
  faibles, parcours discontinu, manque de fit MTE) que le système
  n'a pas capté. À auditer avec le superviseur. \
  \
  *Type B. Comité accepte, système refuse (9 cas).* Composite moyen
  6.7. Sept des neuf sont EPFL-internes (Maillard, Hegi, Croisier,
  Gruber, Kvedarauskaite, Nguyen, Holtz). Un Polytechnico Torino,
  un Ouzbek pour les deux autres. La cause racine pour les
  EPFL-internes est le seuil 4.5 sur la moyenne algèbre+analyse. \
  \
  *Type C. Comité accepte, système waitlist (10 cas).* Huit sont
  EPFL-internes avec composite entre 7.4 et 8.0. Cas frontière où
  la règle de seuil composite hésite. \
  \
  *Type D. Comité refuse, système waitlist (9 cas).* Universités
  borderline, composite 7.4 à 8.1. Le système hésite, le comité
  tranche reject.
]

== Focus sur les EPFL-internes

La cohorte Spring 2025-26 contient 28 EPFL-internes. Le comité en
a admis 27 et refusé 1. Le système, dans son état semaine 12,
n'était d'accord que sur 14/28 (50%). Les autres se décomposaient
en :

- 8 reject erronés (sept cas Type B + un autre)
- 7 waitlist erronés (cas Type C)

J'ai isolé cette sous-cohorte avec
`scripts/rerun_epfl_internals.py` pour itérer rapidement sans
relancer les 128 candidats à chaque essai.

== Itération 1 du prompt EPFL-interne

Hypothèse de départ : le système applique le seuil EPFL par défaut
(4.5/6) alors que les section-switchers ont droit au seuil abaissé
(4.0/6). Le prompt évoquait cette exception mais sans la flécher
explicitement vers les candidats MTE.

Modification : j'ai ajouté un paragraphe qui dit que *tout candidat
EPFL-interne en MTE est par construction un section-switcher* (il
n'existe pas de bachelor MTE), donc le seuil 4.0 s'applique.

Résultat sur la sous-cohorte de 28 :

#table(
  columns: (auto, auto, auto, auto),
  align: (left, center, center, center),
  [*Run*], [*Accept*], [*Reject*], [*Waitlist*],
  [Comité], [27], [1], [0],
  [Avant fix 1 (mode 5 runs)], [13], [8], [7],
  [Après fix 1 (run unique)], [15], [7], [6],
)

Accord avec le comité : 14/28 → 15/28 (54%). Trois cas
flippés vers accept (Ta, Tirot, Décréau) ; deux régressions
(Biersohn classé en waitlist au lieu de reject, Gousset en
waitlist au lieu d'accept).

Bilan mitigé. Le prompt change la décision sur les bords
mais ne dégage pas le bloc Maillard + Hegi + Croisier + Gruber
+ Kvedarauskaite qui reste en reject.

== Itération 2 du prompt EPFL-interne

Inspection des composites : les cinq cas refusés ont un composite
6.34 à 7.45, juste sous le seuil reject_floor de la semaine 11.
L'Academic Evaluator clampe leur `academic_strength` à 5/10 parce
que le verdict GPA est BELOW (moyenne algèbre+analyse 4.0-4.5 contre
seuil 4.5).

Modification 2 : interdiction explicite dans le prompt de citer
"4.33 sous le standard de 4.5" comme contre-argument pour un
candidat MTE, et rappel que le standard MTE est 4.0/6.

Résultat sur la sous-cohorte de 28 :

#table(
  columns: (auto, auto, auto, auto),
  align: (left, center, center, center),
  [*Run*], [*Accept*], [*Reject*], [*Waitlist*],
  [Comité], [27], [1], [0],
  [Avant fix 2 (mode 5 runs)], [15], [5], [8],
  [Après fix 2 (run unique)], [19], [4], [5],
)

Accord avec le comité : 15/28 → 19/28 (68%). Quatre flips vers
accept (Jariod, Cunningham, Gousset, Tekaya), zéro régression.

Les huit cas restants en désaccord :

#table(
  columns: (auto, auto, auto, auto),
  align: (left, center, center, center),
  [*Candidat*], [*Comité*], [*Système*], [*Composite*],
  [Maillard Etienne], [accept], [waitlist], [7.60],
  [Hegi Sébastien], [accept], [waitlist], [7.90],
  [Croisier Noé], [accept], [waitlist], [7.92],
  [Haenni Clement], [accept], [waitlist], [7.75],
  [Kvedarauskaite Ieva], [accept], [reject], [7.44],
  [Gruber Max], [accept], [reject], [7.31],
  [Nguyen Thi Thu Tra], [accept], [reject], [7.20],
  [Holtz Sophie], [accept], [reject], [7.17],
)

Les quatre en reject ont une moyenne algèbre+analyse strictement
sous 4.5. Le hard-reject du gate GPA tire la décision malgré la
hausse du composite. Les quatre en waitlist sont entre 4.0 et 4.5
exact : le clamp à 5 du score Academic les pénalise mais sans
déclencher le reject hard.

== Communication avec le superviseur

J'ai écrit à Geraldine pour clarifier la règle officielle. Question
posée : *le seuil 4.5 sur algèbre+analyse est-il un hard floor, ou
une zone d'examen détaillé ?* Le cas Maillard suggère que le comité
applique une règle plus fine que le seuil binaire ; il faut savoir
laquelle avant de la coder.

== Backfill des recommandations de mineur

Le pipeline ajouté en semaine 11 calcule un `MinorRecommendation`
pour les EPFL-internes via mapping déterministe. Les 5 runs de
semaine 12 datent d'avant ce calcul ; les verdicts JSON n'ont pas
le champ rempli. `scripts/backfill_minor_recs.py` parcourt les
verdicts existants, identifie les EPFL-internes, applique le mapping
bachelor → mineurs, et patche les fichiers en place. Évite de
relancer 640 évaluations LLM (économie : ~12 USD et 85 minutes).

== Comparaison before/after automatisée

`scripts/before_after_epfl.py` aligne deux jeux de verdicts JSON
(avant et après une modification) sur la même sous-cohorte et
produit le tableau before/after vu plus haut. Utilisé pour les
deux itérations de prompt. Réutilisable pour toute modification
future qui doit être mesurée.

// -- Défis et obstacles -----------------------------------------------------

= Défis et obstacles

#callout(titre: "Le mur du seuil 4.5", icon: "⚠", couleur: rgb("#F59E0B"))[
  Cinq cas EPFL-internes restent en désaccord après deux itérations
  de prompt parce que leur moyenne algèbre+analyse est sous 4.5.
  La règle codée en dur (seuil unique 4.0 pour les section-switchers)
  force soit un reject, soit un clamp d'academic_strength qui tire
  le composite sous le floor 7.0. Le comité, lui, regarde le détail
  des notes (Maillard : 3.75 Analyse I mais 5.25 Analyse II) avant
  de trancher. Le système n'a pas ce levier ; il faut une règle à
  bandes, pas un seuil binaire.
]

- *Cohérence inter-runs* : la variance individuelle reste sous 0.3
  de stdev sur le composite (mesuré en semaine 12), donc les
  changements de prompt produisent un signal lisible. Si la variance
  était plus haute, distinguer un vrai gain d'un bruit de run
  demanderait plus de 5 runs.
- *Coût des itérations* : un run sur 28 EPFL-internes coûte ~2 USD
  et prend ~6 minutes. Cinq itérations dans la semaine sans
  surveillance directe demandées avant chaque modification. Le
  smoke-test à 1 candidat (~10 secondes) reste utile pour catcher
  les erreurs grossières de prompt.
- *Régression Biersohn* : le fix 1 a déplacé Biersohn (committee
  reject) de reject à waitlist. Le fix 2 a annulé cette régression
  sans intervention spécifique. Cohérence du signal sur ce cas,
  mais le système reste fragile aux retouches de prompt.

// -- Fichiers modifiés -----------------------------------------------------

= Fichiers modifiés

#callout(titre: "Nouveaux scripts et rapports", icon: "◆", couleur: rgb("#8B5CF6"))[
  *Scripts d'audit (5) :* \
  `scripts/compare_committee_vs_runs.py` (295 l.) \
  `scripts/rerun_epfl_internals.py` (121 l.) \
  `scripts/rerun_matched_only.py` (90 l.) \
  `scripts/before_after_epfl.py` (207 l.) \
  `scripts/backfill_minor_recs.py` (216 l.) \
  \
  *Rapports markdown générés :* \
  `reports/committee-vs-system-2026-05-11.md` \
  `reports/committee-vs-system-policy-v2.md` \
  `reports/epfl-internal-fix-2026-05-11.md` \
  `reports/epfl-internal-fix-run01-only.md` \
  `reports/epfl-internal-fix1+2-vs-baseline.md` \
  `reports/epfl-internal-fix2-incremental.md` \
  \
  *Code modifié :* \
  `src/agentic_admission/agents/prompts.py` (bloc EPFL-internal,
  deux passes) \
  \
  *Aucune modification d'API ni de modèle.* Toutes les retouches
  passent par le prompt et la mesure.
]

// -- Tâches -----------------------------------------------------------------

= Suivi des tâches

#tache("Script compare_committee_vs_runs.py + matrice de confusion", statut: "fait")
#tache("Script rerun_epfl_internals.py (boucle 28 internes)", statut: "fait")
#tache("Script rerun_matched_only.py (filtrer par matching parquet)", statut: "fait")
#tache("Script before_after_epfl.py (diff structurée 2 runs)", statut: "fait")
#tache("Script backfill_minor_recs.py (patch mineurs sur verdicts)", statut: "fait")
#tache("Itération 1 du prompt EPFL-interne (+1 accord)", statut: "fait")
#tache("Itération 2 du prompt EPFL-interne (+4 accords)", statut: "fait")
#tache("Email à Geraldine sur la règle officielle du seuil 4.5", statut: "fait")
#tache("Réponse Geraldine + spec de la règle à bandes", statut: "en cours")
#tache("Audit qualitatif des 19 type-A avec le superviseur", statut: "à faire")
#tache("Corriger fixtures obsolètes test_chair.py / test_orchestrator.py", statut: "à faire")

// -- Plan semaine prochaine -------------------------------------------------

= Plan pour la semaine prochaine

== Priorité haute
- Appliquer la règle à bandes que Geraldine va spécifier : `>=4.5`
  accept, `4.0 - 4.5` discuss, `<4.0` reject. Doit débloquer Maillard,
  Hegi, Croisier, Haenni en waitlist et garder Kvedarauskaite, Gruber,
  Nguyen, Holtz en reject (puisqu'ils sont sous 4.0).
- Réparer la suite de tests cassée par les migrations de schéma
  (28 tests rouges depuis la semaine 11 que j'ai laissés non-bloquants).
  Cible : `uv run poe test` revient vert.
- Splitter le bloc 80→40 résiduel (Type A) en deux sous-questions
  avec Gaétan : (a) est-ce un biais de prompt évaluateur, (b) ou un
  désaccord légitime entre le système et le comité sur des dossiers
  ambigus ?

== Priorité moyenne
- Étendre l'audit comité vs système à Fall 2025-26 dès que la
  cohorte sera anonymisée.
- Mesurer la latence par candidat sur Fall 2025-26 ; viser
  \<30 secondes par dossier pour un usage interactif au comité.
- Réfléchir à un format d'export que le comité peut annoter
  pendant la réunion (PDF imprimable ou tableau Excel pré-rempli).
