#import "template.typ": *

#show: weekly-report.with(
  semaine: 10,
  date: "3 mai 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Migration complète du dashboard Streamlit vers une architecture
    React + FastAPI (4 pages : Review, Cohort, Dossier, Tiers). Le
    client LLM devient résilient : 3 tentatives sur erreurs réseau,
    contenu vide, JSON invalide ou validation Pydantic ratée.
    Routage de fournisseur OpenRouter configurable via `.env`. Filtre
    de semestre ajouté au CLI d'évaluation pour cibler les cohortes
    récentes. Panneau de surcharge du comité (accept/reject/waitlist
    + commentaire) intégré dans le dashboard et exporté en Excel.
  ],
)

// -- Métriques de la semaine ------------------------------------------------

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "Pages dashboard",
    value: "4",
    detail: "Review, Cohort, Dossier, Tiers",
  ),
  metric(
    label: "Tentatives LLM",
    value: "3",
    detail: "Réseau + contenu + validation",
  ),
  metric(
    label: "Lignes ajoutées",
    value: "~5 800",
    detail: "Frontend React + API FastAPI",
  ),
)

#v(0.3cm)

#progress-bar(pourcentage: 78, label: "Progression du projet")

// -- Travail effectué -------------------------------------------------------

= Travail effectué

== Migration React + FastAPI (`dashboard/`)

Le dashboard Streamlit (`dashboard/app.py`, ~400 lignes) est remplacé
par une architecture découplée :

- *Backend FastAPI* (`dashboard/api.py`, ~720 lignes) : endpoints
  REST pour les verdicts, cohorte, dossiers, profils universités,
  exports, et surcharges comité. Sert également les fichiers PDF
  des dossiers.
- *Frontend React + TypeScript + Vite* : 4 pages (Review, Cohort,
  Dossier, Tiers), composants partagés (Confidence, ScoreRow,
  StatusPill, Sidebar, Topbar), routage `react-router-dom`.
- Bénéfices : navigation instantanée entre candidats (pas de
  rechargement Streamlit), affichage parallèle de plusieurs onglets,
  recherche / filtres réactifs côté client.

#callout(titre: "Performance", icon: "▲", couleur: rgb("#10B981"))[
  Temps de navigation entre candidats : *< 100 ms* (React) vs
  *2--5 s* (Streamlit). Le comité peut désormais parcourir une
  cohorte de 128 dossiers en une session continue.
]

== Routage de fournisseur OpenRouter

OpenRouter agrège plusieurs fournisseurs LLM (Anthropic, Google,
DeepSeek, etc.) sous une API unique. Par défaut le routage choisit
automatiquement, mais certains fournisseurs sont moins fiables ou
plus chers. Le pipeline accepte désormais une variable d'environnement
`OPENROUTER_PROVIDER` qui force le routage :

```
OPENROUTER_PROVIDER=anthropic    # latence faible, coût plus élevé
OPENROUTER_PROVIDER=deepinfra    # coût bas, latence variable
```

Ajoutée dans `agents/llm_client.py` via le header `provider` injecté
dans chaque requête HTTP.

== Client LLM résilient (3 tentatives)

L'évaluation par batch tombait régulièrement sur des erreurs
intermittentes (timeouts réseau, réponse JSON tronquée, modèle qui
renvoie une chaîne vide). Le client de complétion fait maintenant 3
tentatives avec back-off exponentiel sur :

+ `httpx.ReadError` / `ConnectError` --- erreurs réseau transitoires
+ Réponse vide ou contenu non-JSON
+ `pydantic.ValidationError` --- structure JSON valide mais champs
  manquants ou types incorrects

Les scores d'évaluateurs sont aussi clampés dans la plage 1--10 (le
modèle renvoie occasionnellement 0 ou 11). Augmentation des
`max_tokens` pour le curriculum matcher (8192) et le Chair (4096) qui
étaient tronqués sur les longues délibérations.

== Filtre de semestre dans le CLI

`run_evaluation.py` accepte un nouveau flag `--semester` :

```
uv run poe run -- --semester 2025-26-spring --limit 128
```

Permet de cibler une cohorte précise sans charger tous les dossiers.
Utilisé pour les premiers runs sur Spring 2025-26.

== Désanonymisation dans le dashboard

Les dossiers sont anonymisés à l'extraction (placeholders
`<PERSON>`, `<EMAIL>`, etc.). Le dashboard relit
`path_mapping.parquet` pour réafficher le nom réel des candidats au
comité, sans modifier les fichiers anonymisés sur le disque.

== Panneau de surcharge du comité

Nouveau composant React qui permet au comité de :

- Outrepasser la décision de l'agent (accept / reject / waitlist)
- Ajouter un commentaire libre (ex. : « bourse d'excellence »,
  « attendre référent #2 »)
- Sauvegarder dans un fichier JSON dédié (jamais dans le verdict
  original)
- Voir l'historique des surcharges dans la liste des candidats

Les surcharges sont incluses dans l'export Excel pour transmission
au comité de section.

== Enrichissement des exports Excel

`dashboard/exports.py` exporte chaque cohorte avec :

- Décision de l'agent + composite + 8 dimensions
- Surcharge comité + commentaire
- Mineur primaire recommandé
- Profil université (tier A/B/C/X, seuil GPA)
- Statistiques historiques (taux d'admission par école)

// -- Défis et obstacles -----------------------------------------------------

= Défis et obstacles

#callout(titre: "Coûts LLM", icon: "⚠", couleur: rgb("#F59E0B"))[
  Les retries triplent le coût en cas d'erreurs en cascade. Sur un
  batch de 128 candidats avec un fournisseur instable, observation
  d'un dépassement de budget OpenRouter. Mitigation à venir
  (semaine 11) : router les candidats EPFL sur un chemin
  déterministe sans LLM.
]

- *Streamlit ne supportait pas les états composés* : afficher 5
  candidats côte à côte ou comparer deux verdicts forçait des
  contournements lourds. React résout cela nativement.
- *Erreurs Pydantic silencieuses* : un champ manquant dans la
  réponse LLM levait une exception au milieu d'un batch et
  invalidait tout le `gather`. Les retries + le clamp des scores
  rendent les batchs robustes.
- *Cache navigateur sur le frontend* : les exports Excel étaient
  servis depuis le cache, masquant les changements. Ajout d'un
  paramètre `?t=` pour invalider.

// -- Fichiers modifiés -----------------------------------------------------

= Fichiers modifiés

#callout(titre: "Résumé des changements", icon: "◆", couleur: rgb("#8B5CF6"))[
  *~30 fichiers, ~5 800 lignes ajoutées (incluant `package-lock.json`)* \
  \
  *Backend :* \
  `dashboard/api.py` --- API FastAPI complète (720 lignes) \
  `dashboard/exports.py` --- Excel/CSV avec surcharges (660 lignes) \
  `agents/llm_client.py` --- retry, provider routing (200+ lignes) \
  `agents/run_evaluation.py` --- flag `--semester`, log level \
  \
  *Frontend (nouveau) :* \
  `dashboard/frontend/index.html` + `package.json` + Vite config \
  `dashboard/frontend/src/App.tsx` --- routeur React \
  `dashboard/frontend/src/api.ts` --- client typé \
  `dashboard/frontend/src/pages/{Review,Cohort,Dossier,Tiers}.tsx` \
  `dashboard/frontend/src/components/*.tsx` --- composants partagés \
  \
  *Supprimés :* \
  `dashboard/app.py` (Streamlit, 400 lignes) \
  `dashboard/cohort.py` (Streamlit, 327 lignes)
]

// -- Tâches -----------------------------------------------------------------

= Suivi des tâches

#tache("Migration dashboard Streamlit → React + FastAPI", statut: "fait")
#tache("4 pages : Review, Cohort, Dossier, Tiers", statut: "fait")
#tache("Routage de fournisseur OpenRouter", statut: "fait")
#tache("Client LLM résilient (3 tentatives)", statut: "fait")
#tache("Clamp des scores 1-10 sur les évaluateurs", statut: "fait")
#tache("Augmentation max_tokens (curriculum, chair)", statut: "fait")
#tache("Filtre `--semester` dans le CLI d'évaluation", statut: "fait")
#tache("Désanonymisation au runtime via path_mapping", statut: "fait")
#tache("Panneau de surcharge comité (UI + persistance)", statut: "fait")
#tache("Export Excel enrichi (override + minor + tier)", statut: "fait")
#tache("Évaluer toute la cohorte Spring 2025-26 (128 candidats)", statut: "en cours")
#tache("Réduire le coût LLM pour les EPFL-internes", statut: "à faire")

// -- Plan semaine prochaine -------------------------------------------------

= Plan pour la semaine prochaine

== Priorité haute
- Lancer le batch complet Spring 2025-26 (128 candidats) et
  comparer le taux d'accord avec le comité.
- Pour les EPFL-internes (~25% de la cohorte), court-circuiter
  l'agent Reference (4/5 dossiers ne soumettent pas de lettres) et
  recalibrer le profil de scoring.
- Ajouter un *gate* GPA déterministe : comparer la note extraite au
  seuil de l'institution avant la délibération LLM.

== Priorité moyenne
- Mapping bachelor EPFL → mineurs adjacents (court-circuit du LLM
  pour les internes).
- Fallback de profil université quand le matching parquet rate
  (cohortes 2025-26 sans Excel comité).
- Audit des verdicts en désaccord avec le comité pour identifier
  les biais systématiques.
