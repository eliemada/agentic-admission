#import "template.typ": *

#show: weekly-report.with(
  semaine: 3,
  date: "8 mars 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Pipeline d'anonymisation PII implémenté (Presidio + GLiNER) et testé
    sur un échantillon avec résultats concluants.
    Cluster SCITAS indisponible depuis vendredi : travail en local.
  ],
)

// ── Métriques de la semaine ──────────────────────────────────────────────────

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "Faux positifs corrigés",
    value: "12+",
    detail: "Allow-list, seuils, filtres",
  ),
  metric(
    label: "Tests unitaires",
    value: "108",
    detail: "Tous passent",
  ),
  metric(
    label: "Avancement global",
    value: "25%",
    detail: "Phase: Anonymisation",
  ),
)

#v(0.3cm)

#progress-bar(pourcentage: 25, label: "Progression du projet")

// ── Travail effectué ─────────────────────────────────────────────────────────

= Travail effectué

== Pipeline d'anonymisation PII

Le pipeline repose sur *Presidio* comme orchestrateur avec *GLiNER*
(`urchade/gliner_multi_pii-v1`, ~500M params) comme backend NER zero-shot
multilingue. Il détecte :
- *PII structurés* (regex) : emails, téléphones, URLs, numéros AVS/AHV, SCIPER
- *PII contextuels* (GLiNER) : noms, adresses, dates de naissance, organisations

Des recognizers personnalisés ont été ajoutés pour les numéros AVS
(`756.XXXX.XXXX.XX`) et SCIPER (6 chiffres avec contexte).

== Réduction des faux positifs

Les premiers tests révélaient de nombreux faux positifs (« I » → `<PERSON>`,
« C++ » → `<PERSON>`, « EPFL » → `<PII>`, coupures de mots comme
« Wit`<PERSON>` »). Trois modules correctifs ont été développés :

- *Allow-lists* : termes sûrs en 5 catégories (institutions, académique,
  pronoms, technique, activités) passés à Presidio
- *Seuils par entité* : seuils différenciés selon l'ambiguïté
  (0.4 pour EMAIL/PHONE, 0.6 pour PERSON, 0.65 pour NRP/organization)
- *Filtres post-analyse* : limites de mots, longueur minimale, mots courants,
  durées vs dates — appliqués séquentiellement après la détection

== Test sur échantillon

Pipeline testé sur `test_tiny` (1 candidat, 2 documents).

#callout(titre: "Avant / Après", icon: "◆", couleur: rgb("#2563EB"))[
  *Avant :* `<PERSON> am writing ... Wit<PERSON> an <PII> ... <PERSON> | Visual Basic`\
  *Après :* `I am writing ... With an ... C++ | Visual Basic`

  Pronoms, EPFL, diplômes, termes techniques préservés.
  Vrais PII (noms, emails, téléphones) toujours anonymisés.
]

// ── Défis et obstacles ───────────────────────────────────────────────────────

= Défis et obstacles

#callout(titre: "Cluster SCITAS indisponible", icon: "⚠", couleur: rgb("#EF4444"))[
  SCITAS est hors service depuis vendredi après-midi. Le développement
  continue en local. La conversion PDF à grande échelle et l'inférence
  LLM nécessitent le retour du cluster.
]

- *Conversion PDF → Markdown* : ~13 600 PDFs à convertir (texte natif + OCR
  pour les scans), bloqué par l'indisponibilité de SCITAS

// ── Tâches ───────────────────────────────────────────────────────────────────

= Suivi des tâches

#tache("Pipeline Presidio + GLiNER fonctionnel", statut: "fait")
#tache("Recognizers personnalisés AVS/AHV et SCIPER", statut: "fait")
#tache("Allow-lists, seuils et filtres post-analyse", statut: "fait")
#tache("Tests unitaires (108 tests)", statut: "fait")
#tache("Test sur échantillon réel (test_tiny)", statut: "fait")
#tache("Conversion PDF → Markdown (13 600 fichiers)", statut: "bloqué")
#tache("Anonymisation à grande échelle", statut: "bloqué")
#tache("Pipeline LLM pour le schéma de décision", statut: "à faire")

// ── Plan semaine prochaine ───────────────────────────────────────────────────

= Plan pour la semaine prochaine

== Priorité haute
- Dès le retour de SCITAS : conversion PDF → Markdown puis anonymisation
  sur l'ensemble des fichiers
- Valider les résultats sur un échantillon plus large (50--100 dossiers)

== Priorité moyenne
- Lier les dossiers anonymisés aux données structurées du Parquet
  (décisions du comité, GPA, université)
- Premiers tests d'évaluation LLM : guidelines en contexte + dossier candidat,
  comparer la décision du modèle avec celle du comité
