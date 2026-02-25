#import "template.typ": *

#show: weekly-report.with(
  semaine: 1,
  date: "24 février 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  resume: [
    Lancement du projet. Lecture du system design, exploration des données
    d'admission MTE, demande d'accès aux clusters HPC SCITAS, et recherche
    sur les modèles de langage open-source exécutables en local.
  ],
)

// ── Métriques de la semaine ──────────────────────────────────────────────────

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "Heures investies",
    value: "9h",
    detail: "Recherche + Setup",
  ),
  metric(
    label: "Fichiers analysés",
    value: "15",
    detail: "Datasets MTE 2020–2025",
  ),
  metric(
    label: "Avancement global",
    value: "5%",
    detail: "Phase: Exploration",
  ),
)

#v(0.3cm)

#progress-bar(pourcentage: 5, label: "Progression du projet")

// ── Travail effectué ─────────────────────────────────────────────────────────

= Travail effectué

== Exploration des données

- Inventaire complet des fichiers de candidatures MTE disponibles (2020–2025)
- Analyse de la structure des fichiers Excel: colonnes, format des notes, critères d'évaluation
- Identification des champs récurrents: parcours académique, notes, décisions du comité
- Repérage des incohérences de format entre les différentes années

== Recherche sur les modèles open-source

- État de l'art sur les modèles de langage exécutables en local: Llama 3, Mistral, Phi-3, Qwen 3
- Comparaison des performances et des exigences matérielles (GPU vs. CPU-only)
- Revue des approches d'anonymisation des données étudiantes (conformité RGPD)

== Accès aux clusters HPC (SCITAS)

- Demande d'accès au compte master HPC via RITM0504113
- Accès confirmé le 19 février 2026: ajout au groupe `hpc-masters`, compte créé avec accès temporaire pour la durée du semestre
- Prochaine étape: connexion via VPN et premiers tests sur les clusters

== Mise en place technique

- Initialisation du dépôt Git avec structure de projet
- Configuration de l'environnement Python avec `uv`
- Premiers tests de lecture des fichiers Excel avec `openpyxl`

// ── Résultats clés ───────────────────────────────────────────────────────────

= Résultats clés

#callout(titre: "Observation importante", icon: "◆", couleur: rgb("#2563EB"))[
  Les fichiers d'admission couvrent *6 années académiques* avec des structures
  relativement homogènes. Cependant, les critères d'évaluation ont évolué entre
  2020 et 2025, ce qui nécessitera une phase de normalisation des données.
]

Les données disponibles contiennent principalement:
+ *Informations académiques*: université d'origine, programme, GPA/notes
+ *Évaluations du comité*: scores par critère, décision finale, commentaires
+ *Métadonnées*: dates de candidature, round (1er/2ème), statut

// ── Défis et obstacles ───────────────────────────────────────────────────────

= Défis et obstacles

#callout(titre: "Bloquant", icon: "⚠", couleur: rgb("#EF4444"))[
  Les données réelles des étudiants sont nécessaires pour avancer sur le prototype.
  L'obtention de ces données est soumise à l'accord du *Data Protection Officer (DPO)*
  de l'EPFL. En attendant cette autorisation, le développement est bloqué sur la
  partie analyse des dossiers.
]

- *Accès aux données*: en attente de l'accord du DPO pour obtenir les dossiers
  de candidature (même anonymisés)
- *Hétérogénéité des formats*: les fichiers Excel ne suivent pas un schéma
  strictement identique d'une année à l'autre
- *Choix du LLM local*: arbitrage entre performance et capacité à tourner
  sur les clusters HPC

// ── Tâches ───────────────────────────────────────────────────────────────────

= Suivi des tâches

#tache("Inventaire des données d'admission MTE", statut: "fait")
#tache("Analyse de la structure des fichiers Excel", statut: "fait")
#tache("Recherche modèles open-source (Llama, Mistral, Qwen, Phi)", statut: "fait")
#tache("Demande d'accès HPC SCITAS", statut: "fait")
#tache("Mise en place du dépôt Git et environnement", statut: "fait")
#tache("Obtention des données via le DPO", statut: "bloqué")
#tache("Connexion et tests sur les clusters HPC", statut: "à faire")
#tache("Pipeline d'anonymisation des données", statut: "à faire")

// ── Plan semaine prochaine ───────────────────────────────────────────────────

= Plan pour la semaine prochaine

== Priorité haute
- Se connecter aux clusters HPC via VPN et valider l'environnement
- Relancer le DPO pour l'accès aux données de candidature
- Premiers tests d'inférence avec un modèle open-source sur le cluster

== Priorité moyenne
- Avancer sur le pipeline d'anonymisation en utilisant des données synthétiques
- Définir l'architecture détaillée du système multi-agents
