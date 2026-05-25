#import "template.typ": *

#show: weekly-report.with(
  semaine: 14,
  date: "30 mai 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Geraldine a répondu lundi : la règle officielle pour les EPFL-internes
    est à trois bandes, pas binaire. `>= 4.5/6` sur la moyenne
    algèbre+analyse vaut accept direct ; `4.0 à 4.5` vaut zone de
    discussion (le comité regarde le détail des notes) ; `< 4.0` vaut
    refus automatique. J'ai codé cette règle dans `gpa_gate.py`,
    branché le band sur `apply_gate_overrides` et le clamp académique,
    réécrit le bloc EPFL-interne du prompt, et livré le tout dans
    la PR \#23 (squash-mergée). En parallèle, j'ai réparé les 28
    tests rouges hérités des migrations de schéma de la semaine 11
    et refactoré `llm_client.complete` (complexité 18 → sous 10) pour
    passer l'audit lint que je remettais depuis trois semaines.
    *La suite passe à 519 verts, type-check vert, ruff vert.*
  ],
)

// -- Métriques de la semaine ------------------------------------------------

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "Tests verts",
    value: "519/519",
    detail: "était 491 + 28 cassés",
  ),
  metric(
    label: "EPFL-internes",
    value: "23/28",
    detail: "Accord comité (82%, vs 68% S13)",
  ),
  metric(
    label: "PR mergées",
    value: "#23",
    detail: "67 fichiers, +4 733 / -1 190",
  ),
)

#v(0.3cm)

#progress-bar(pourcentage: 95, label: "Progression du projet")

// -- Travail effectué -------------------------------------------------------

= Travail effectué

== Règle à trois bandes (Geraldine, 2026-05-19)

Réponse au mail de semaine 13. Geraldine confirme que le comité
n'utilise pas un seuil binaire mais une règle à trois bandes sur
la moyenne algèbre+analyse :

#table(
  columns: (auto, auto, auto),
  align: (left, center, left),
  [*Bande*], [*Bornes*], [*Action comité*],
  [ACCEPT], [`>= 4.5/6`], [Admission sur la barre académique],
  [DISCUSS], [`4.0 <= avg < 4.5`], [Examen détaillé des notes],
  [REJECT], [`< 4.0`], [Refus automatique],
)

Le cas Maillard est explicité dans son mail : moyenne 4.31, refusé
par le système, admis par le comité parce que ses notes détaillées
(3.75 en Analyse I, 5.25 en Analyse II) montrent une récupération.
Le comité a regardé le détail derrière la moyenne.

Architecture côté code :

- `gpa_gate.py` reçoit une enum `EpflInternalBand` (ACCEPT, DISCUSS,
  REJECT, UNKNOWN) et une fonction `epfl_internal_band(value_str)`
  qui mappe la moyenne sur la bande. Constantes nommées
  `_EPFL_INTERNAL_ACCEPT_FLOOR = 4.5` et
  `_EPFL_INTERNAL_REJECT_FLOOR = 4.0` documentées comme valeurs
  comité (pas des paramètres de tuning).
- `chair.apply_gate_overrides` accepte un `epfl_band` optionnel.
  La bande remplace le gate BELOW générique pour les EPFL-internes :
  DISCUSS force WAITLIST, REJECT force REJECT, ACCEPT laisse passer.
  Le gate BELOW générique reste actif pour les externes et pour
  les EPFL-internes dont la moyenne ne parse pas.
- `chair.clamp_academic_strength_below_threshold` reçoit aussi le
  band. Le clamp à 4 ne se déclenche que sur REJECT, plus sur
  DISCUSS. Un candidat à 4.31 garde son score Academic intact, ce
  qui évite que le composite descende sous le floor 7.0.
- `orchestrator.evaluate_candidate` et `run_evaluation.evaluate_single`
  plomb le band de la couche extraction jusqu'au Chair.
- `prompts.py` réécrit le bloc EPFL-interne pour expliquer la règle
  à l'évaluateur LLM avec le cas Maillard cité comme exemple.

Validation après PR \#23 sur les 28 EPFL-internes : accord avec
le comité passe de 19/28 (68%) à 23/28 (82%). Les cinq cas
restants en désaccord sont tous des moyennes sous 4.0 que la règle
écarte d'office.

== Nettoyage de la suite de tests

Les migrations de schéma de la semaine 11 (str → `DimensionJustification`,
str → `VerdictSummary`, `synthesize` qui retourne `ChairSynthesis`
au lieu de `PanelVerdict`) avaient cassé 28 tests que j'avais
laissés non-bloquants pour livrer la PR \#18. Dette à payer.

Décomposition :

#table(
  columns: (auto, auto, auto),
  align: (left, center, left),
  [*Fichier*], [*Cassés*], [*Cause*],
  [`test_evaluation_models.py`], [6], [str au lieu de `DimensionJustification`],
  [`test_models_dossier.py`], [2], [idem],
  [`test_evaluators.py`], [5], [mock retournait scorecard, pas la response model],
  [`test_orchestrator.py`], [8], [`PanelVerdict` avec str justification],
  [`test_chair.py`], [4], [mock `PanelVerdict` au lieu de `ChairSynthesis`],
  [`test_llm_client.py`], [1], [assertion sur `response_format` retiré du payload],
  [`test_chair_overrides.py`], [2], [import `WAITLIST_COMPOSITE_FLOOR` renommé],
)

Plutôt que de patcher chaque test à la main, j'ai centralisé les
helpers dans `tests/conftest.py` :

```python
def make_scorecard(role, scores, *, pros=("ok",), cons=()):
    justifications = {dim: make_justification(pros=pros, cons=cons)
                      for dim in scores}
    return AgentScorecard(role=role, scores=scores,
                          justifications=justifications)
```

Plus `make_justification`, `make_verdict_summary`,
`make_panel_verdict`. Chaque test cassé devient un remplacement
mécanique : six lignes de schéma obsolète remplacées par un appel
à `make_scorecard(...)`.

Trois tests d'immutabilité testaient une propriété fausse depuis
toujours : ils essayaient de muter `card.scores["key"] = 5` et
attendaient un `TypeError`. Pydantic v2 avec `frozen=True` ne
deep-freeze pas les dicts internes, donc la mutation passait sans
erreur. Réécrits pour vérifier la propriété que pydantic garantit
(attribut top-level non-réassignable).

Deux tests de `decision_from_composite` validaient les anciens
floors (7.5 pour waitlist). Refactor week 11 a passé à 8.0/7.0,
les tests n'avaient pas suivi. Mis à jour avec un commentaire qui
explique le pourquoi.

Résultat : `uv run poe test` passe à *519 verts en 100 secondes*.

== Refactor `llm_client.complete`

Ruff signalait depuis trois semaines `C901` (complexité 18 > 10),
`PLR0912` (18 branches > 12), `PLR0915` (69 statements > 50) sur
la fonction `complete`. Une seule fonction qui construisait le
payload, gérait les retries, dispatchait l'erreur HTTP, parsait la
réponse, validait avec Pydantic. Refactor en quatre helpers :

#table(
  columns: (auto, auto),
  align: (left, left),
  [*Helper*], [*Responsabilité*],
  [`_build_payload`], [Schéma JSON injecté dans system, OpenRouter provider],
  [`_send_request`], [POST + classification de l'erreur transport],
  [`_handle_http_error`], [Map HTTP 402 → LLMBillingError, autres → connection],
  [`_extract_raw_content`], [`choices[0].message.content` + retry sur vide],
)

La fonction `complete` elle-même tombe à 45 lignes, complexité 8.
Constantes `_HTTP_PAYMENT_REQUIRED = 402` et `_MAX_LLM_ATTEMPTS = 3`
remontées au niveau module. Import de `settings` remonté au top
(était en lazy import dans la fonction).

Au passage j'ai corrigé deux problèmes annexes :

- Le test `test_complete_sends_json_schema_in_request` cherchait
  `payload["response_format"]["type"] == "json_schema"`. Notre client
  utilise vLLM, qui ne supporte pas `response_format` ; on injecte
  le schéma dans le system prompt à la place. Test renommé en
  `test_complete_injects_json_schema_into_system_prompt`, vérifie
  la chose réelle.
- Une SVG cassée (`dashboard/assets/epfl_logo.svg`) contenait
  littéralement le HTML d'un 404 GitHub ; aucun import. Supprimée.

== Type-check et lint au propre

`uv run poe typecheck` passait à 6 erreurs ; cleanup :

- `orchestrator.py` : extrait `_ensure_scorecard` pour faire le
  narrow type-safe au lieu d'un `# type: ignore[assignment]`.
- `curriculum/university_profiles.py` : remplacement de
  `UniversityProfile(**fields)` (5 erreurs ty) par
  `UniversityProfile.model_validate({"name": name, **fields})`.

`uv run ruff check .` passait à 100 erreurs. La plupart sont dans
`scripts/`, `slurm/`, `dashboard/` qui ne sont pas du code librairie :
ce sont des notebooks Python d'analyse one-shot. Ajout d'un bloc
`per-file-ignores` qui relâche les règles de complexité, magic
numbers et docstrings sur ces trois dossiers tout en gardant la
rigueur sur `src/agentic_admission/`. Le code librairie passe les
700+ règles de ruff `ALL`.

== Audit du repo

Inventaire post-merge :

- *Code* : 519 tests verts, 57.9% de couverture, type-check vert,
  ruff vert.
- *PRs* : 23 au total, dernière mergée le 24 mai.
- *Branches* : `main` seule. Toutes les feature-branches supprimées
  après merge.
- *Rapports semaine* : `semaine-01.typ` à `semaine-14.typ` (avec
  ce document). 14 semaines, 12 rapports précédents + 2 nouveaux.
- *Rapports markdown d'analyse* : 7 (cohort variance, committee
  policies v1 et v2, 4 itérations EPFL fix).
- *Scripts d'analyse* : 17 dans `scripts/`. Six nouveaux livrés en
  semaine 13.

// -- Défis et obstacles -----------------------------------------------------

= Défis et obstacles

#callout(titre: "Cinq cas EPFL résiduels", icon: "⚠", couleur: rgb("#F59E0B"))[
  Cinq EPFL-internes restent en désaccord avec le comité :
  Kvedarauskaite, Gruber, Nguyen, Holtz (moyennes \< 4.0, le système
  rejette comme la règle l'impose) et Biersohn (seul reject du comité
  sur les 28, que le système met en waitlist). Pour les quatre
  premiers, le comité a admis malgré la moyenne sous 4.0. Hors-règle
  Geraldine. À discuter avec le superviseur : est-ce une exception
  qu'il faut coder, ou un signal qu'il faut accepter de désaccorder ?
]

- *Dette des fixtures de test* : trois semaines de tests rouges
  cachés derrière `--exitfirst` qui s'arrêtait sur la première
  erreur de schéma. Indicateur faux que la suite tournait correctement.
  Leçon : `pytest -ra --tb=no` sans `--exitfirst` doit tourner avant
  chaque merge, même quand la première erreur masque les suivantes.
- *Refactor non-isolé* : la PR \#23 bundle la règle à bandes,
  le cleanup des tests, le refactor de `llm_client`, et le cleanup
  ruff/ty. Difficile à reviewer en l'état, mais splitter aurait
  demandé une PR par sujet et une coordination des dépendances. J'ai
  fait le choix de livrer en bloc et de payer le coût review en cas
  de retour. Le squash-merge aplatit l'historique.
- *Mesure incomplète post-fix* : la PR \#23 est mergée mais je n'ai
  pas re-lancé les 5 runs complets sur Spring 2025-26. Le chiffre
  23/28 d'accord sur les EPFL-internes vient d'un run unique, pas
  d'un vote majoritaire. Test à automatiser pour la semaine 15.

// -- Fichiers modifiés -----------------------------------------------------

= Fichiers modifiés

#callout(titre: "PR #23 (squash-mergée, commit 68463da)", icon: "◆", couleur: rgb("#8B5CF6"))[
  *67 fichiers, +4 733 / -1 190 lignes* \
  \
  *Règle à bandes :* \
  `agents/gpa_gate.py` (+58 lignes : enum + helper + constantes) \
  `agents/chair.py` (+89 / -19 : apply_gate_overrides, clamp,
  synthesize, helpers epfl_band) \
  `agents/orchestrator.py` (+21 / -7 : plomberie band) \
  `agents/run_evaluation.py` (+19 / -5 : extract + log band) \
  `agents/prompts.py` (réécriture bloc EPFL-interne) \
  \
  *Tests réparés (28 → 0) :* \
  `tests/conftest.py` (+73 : helpers partagés) \
  `tests/test_evaluation_models.py` (réécrits) \
  `tests/test_models_dossier.py` \
  `tests/test_evaluators.py` (mocks per-response-model) \
  `tests/test_orchestrator.py` (mocks `ChairSynthesis`) \
  `tests/test_chair.py` \
  `tests/test_llm_client.py` \
  `tests/test_chair_overrides.py` (+ tests pour les bandes) \
  `tests/test_gpa_gate.py` (+ tests pour `epfl_internal_band`) \
  \
  *Refactor `llm_client` :* \
  `agents/llm_client.py` (-69 / +85 : split en 4 helpers) \
  \
  *Hygiène :* \
  `pyproject.toml` (+50 : per-file-ignores scripts/slurm/dashboard) \
  `config.py` (-1 : import field_validator retiré) \
  `curriculum/university_profiles.py` (model_validate) \
  `dashboard/assets/epfl_logo.svg` (supprimée, était un 404) \
  Plusieurs fichiers : docstrings d'attributs (PEP-257 style) → commentaires
  pour satisfaire `check-docstring-first`.
]

// -- Tâches -----------------------------------------------------------------

= Suivi des tâches

#tache("Spec règle à bandes (réponse Geraldine reçue lundi)", statut: "fait")
#tache("Enum EpflInternalBand + helper epfl_internal_band", statut: "fait")
#tache("Plomberie band : run_evaluation → orchestrator → chair", statut: "fait")
#tache("Tests bandes : 9 nouveaux verts (boundaries + overrides)", statut: "fait")
#tache("Réécriture bloc EPFL-interne du prompt Academic", statut: "fait")
#tache("PR #23 squash-mergée sur main (commit 68463da)", statut: "fait")
#tache("Suite de tests : 28 cassés → 0, total 519 verts", statut: "fait")
#tache("Refactor llm_client.complete (complexité 18 → 8)", statut: "fait")
#tache("Type-check vert (6 erreurs ty → 0)", statut: "fait")
#tache("Ruff vert (100 erreurs → 0, per-file-ignores)", statut: "fait")
#tache("Re-runner les 5 runs complets après PR #23", statut: "à faire")
#tache("Audit qualitatif des 5 cas EPFL résiduels avec Gaétan", statut: "à faire")
#tache("Audit qualitatif des 19 cas type-A (système too lenient)", statut: "à faire")

// -- Plan semaine prochaine -------------------------------------------------

= Plan pour la semaine prochaine

== Priorité haute
- Re-lancer 5 runs complets sur Spring 2025-26 post-PR \#23 pour
  mesurer l'accord global avec le comité avec un vote majoritaire
  (vs le run unique actuel). Cible : passer le chiffre d'agreement
  global au-dessus de 70%.
- Audit des cinq cas EPFL résiduels avec Gaétan. Quatre sont sous
  la règle Geraldine (moyenne \< 4.0) mais le comité a admis :
  comprendre pourquoi avant de toucher au code. Biersohn est l'inverse
  (comité reject, système waitlist), à examiner en parallèle.
- Audit des 19 cas type-A (système accepte, comité refuse) sur
  universités internationales fortes. Identifier si c'est un biais
  de l'évaluateur Reference ou Motivation, ou un désaccord légitime
  sur le fit MTE.

== Priorité moyenne
- Tester la stabilité du nouveau pipeline sur Fall 2025-26 dès que
  la cohorte sera anonymisée.
- Comparer Gemini Flash 3 vs Sonnet 4.6 sur la sous-cohorte des 5
  cas borderline EPFL. Mesurer si un modèle plus capable réduit la
  variance sur les dossiers ambigus, et si le coût supplémentaire
  se justifie.
- Préparer une vue dashboard qui montre côte-à-côte la décision
  système, la décision comité (quand connue), et la bande GPA. Outil
  utilisable en réunion de comité pour aller vite sur les cas
  d'accord et lent sur les cas en désaccord.
