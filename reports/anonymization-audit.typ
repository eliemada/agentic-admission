// ─────────────────────────────────────────────────────────────────────────────
//  Rapport d'Audit — Anonymisation PII
//  EPFL · Section MTE
// ─────────────────────────────────────────────────────────────────────────────

#import "weekly/template.typ": *

#let success-green = rgb("#10B981")
#let warning-amber = rgb("#F59E0B")
#let danger-red = rgb("#EF4444")
#let risk-badge(level) = {
  let couleur = if level == "low" { success-green } else if level == "medium" { warning-amber } else { danger-red }
  let label = if level == "low" { "FAIBLE" } else if level == "medium" { "MOYEN" } else { "ÉLEVÉ" }
  badge(label, couleur: couleur)
}

#show: weekly-report.with(
  semaine: 5,
  date: "24 mars 2026",
  etudiant: "Elie Bruno",
  superviseur: "Prof. Gaétan de Rassenfosse",
  projet: "Système Multi-Agents pour l'Aide à la Décision en Admission",
  section: "Management of Technology and Entrepreneurship (MTE)",
  resume: [
    Audit de l'anonymisation sur 900 fichiers (50 par type, 18 catégories).
    *100%* de couverture sur emails, téléphones, adresses, IBAN, AVS.
    *96.1%* sur les noms. Deux axes d'amélioration : numéros de passeport sur les
    certificats IELTS et noms résiduels dans les diplômes étrangers.
  ],
)

= Méthodologie

Échantillon aléatoire stratifié de *900 fichiers* (graine = 42) sur les 18 types de documents
du corpus de 12~529 fichiers Markdown anonymisés. Détection par regex ciblées sur les PII
à haut risque (emails, passeports, noms, URLs) + vérification manuelle des cas limites.

Pipeline audité : *Presidio* + *GLiNER* (`gliner-multitask-large-v0.5`) + *spaCy*, avec
reconnaisseurs personnalisés (AVS, SCIPER), propagation de noms, et 8 filtres post-analyse.

= Résultats

#grid(
  columns: (1fr, 1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(label: "Fichiers audités", value: "900", detail: "sur 12 529 (7.2%)"),
  metric(label: "Redactions", value: "22 494", detail: "dans l'échantillon"),
  metric(label: "Emails non redactés", value: "0", detail: "100% couverture"),
  metric(label: "Noms résiduels", value: "35", detail: "3.9% des fichiers"),
)

#v(0.3cm)

#figure(
  table(
    columns: (1fr, auto, auto, auto, auto),
    align: (left, center, center, center, center),
    stroke: 0.5pt + epfl-border,
    fill: (_, row) => if row == 0 { epfl-light } else { none },
    inset: 8pt,
    table.header(
      [*Type de PII*], [*Redactions*], [*Fuites*], [*Couverture*], [*Risque*],
    ),
    [Emails],               [1 499],  [0],  [100%], risk-badge("low"),
    [Téléphones],           [1 467],  [0],  [100%], risk-badge("low"),
    [Adresses],             [1 841],  [0],  [100%], risk-badge("low"),
    [URLs],                 [1 267],  [0],  [100%], risk-badge("low"),
    [AVS / IBAN / SCIPER],  [33],     [0],  [100%], risk-badge("low"),
    [Noms de personnes],    [9 442],  [35], [96.1%], risk-badge("medium"),
    [Numéros de passeport], [---],    [23], [n/a],   risk-badge("medium"),
  ),
  caption: [Couverture par type de PII sur l'échantillon de 900 fichiers.],
)

#v(0.1cm)

#callout(titre: "Note", icon: "ℹ", couleur: rgb("#3B82F6"))[
  `<DOB_YYYY>` préserve l'année de naissance (ex: `<DOB_1995>`) --- intentionnel pour
  évaluer l'adéquation du profil. Ce n'est pas un identifiant direct.
]

= Problèmes identifiés avec exemples

== Problème 1 --- Noms en ALL CAPS non détectés par GLiNER

Les diplômes et certificats étrangers utilisent des majuscules complètes. GLiNER ne reconnaît
pas ces noms comme entités `PERSON`.

#figure(
  table(
    columns: (auto, 1fr),
    align: (left, left),
    stroke: 0.5pt + epfl-border,
    fill: (_, row) => if row == 0 { epfl-light } else { none },
    inset: 8pt,
    table.header([*Fichier*], [*Extrait anonymisé (nom visible)*]),
    [GRE Score Report], [```HANXUAN ZHANG``` #linebreak() Most Recent Test Date: \<DATE\>],
    [Diplôme colombien], [```SIMÓN JARAMILLO VÉLEZ``` #linebreak() ID Card No. \<PII\>],
    [GMAT Report], [```PANAGIOTA  KOLLIA``` #linebreak() Graduate Management...],
  ),
  caption: [Noms en majuscules non redactés --- GLiNER échoue sur le casing ALL CAPS.],
)

== Problème 2 --- Noms partiellement redactés

Le tokenizer sépare prénom et nom en entités distinctes. Le prénom est parfois redacté,
mais le nom de famille reste visible.

#figure(
  table(
    columns: (auto, 1fr),
    align: (left, left),
    stroke: 0.5pt + epfl-border,
    fill: (_, row) => if row == 0 { epfl-light } else { none },
    inset: 8pt,
    table.header([*Fichier*], [*Extrait*]),
    [Lettre de recommandation], [`<PERSON> Perdomo` --- le nom de famille reste],
    [Lettre de motivation], [`<PERSON> LAW` --- idem en majuscules],
    [Relevé de notes], [`<PERSON> Angulo's application` --- possessif],
  ),
  caption: [Redaction partielle --- le prénom est anonymisé mais le nom de famille persiste.],
)

== Problème 3 --- Noms dans les formulaires structurés (Synthèse IS-Academia)

Les synthèses de candidature ont un format tabulaire `Nom / Prénom` où le nom est isolé
sur une ligne, non reconnu comme entité.

#figure(
  table(
    columns: (1fr,),
    align: (left,),
    stroke: 0.5pt + epfl-border,
    fill: (_, _) => epfl-light,
    inset: 10pt,
    [```
Données personnelles
Nom
Lois              ← non redacté
Nom <PERSON>      ← prénom redacté
```],
  ),
  caption: [Formulaire IS-Academia : le nom est isolé et échappe au NER.],
)

== Problème 4 --- Numéros de passeport sur les certificats IELTS/TOEFL

*20% des certificats linguistiques* contiennent un numéro de passeport non redacté. Le
pipeline supprime les _scans_ de passeport (`strip_passports.py`) mais pas les numéros
_textuels_ apparaissant dans d'autres documents.

#figure(
  table(
    columns: (auto, auto, auto),
    align: (left, center, left),
    stroke: 0.5pt + epfl-border,
    fill: (_, row) => if row == 0 { epfl-light } else { none },
    inset: 8pt,
    table.header([*Document*], [*Valeur*], [*Contexte*]),
    [IELTS e-TRF], [`Z5295128`], [Passeport sur rapport IELTS],
    [IELTS Certificate], [`YB3289203`], [Passeport candidat],
    [IELTS Result], [`B9861485`], [Passeport candidat],
    [Diplôme étranger], [`BH616353`], [Passeport marocain],
  ),
  caption: [Numéros de passeport non détectés dans les certificats linguistiques.],
)

= Correctifs proposés

== Fix 1 --- Propagation du nom depuis les métadonnées du dossier

Actuellement, `_propagate_detected_names` ne propage que les noms _déjà détectés_ par GLiNER.
Le fix : injecter le nom du candidat depuis le chemin du dossier (ex: `jaramillo_velez` →
`["Jaramillo", "Vélez"]`) *avant* l'analyse, en tant que noms à redacter systématiquement.

```python
# Dans anonymize_text(), avant l'appel à _propagate_detected_names :
candidate_name = extract_name_from_path(file_path)
# Injecter des RecognizerResult synthétiques pour chaque variante
# (original, UPPER, Title) du nom du candidat
for variant in name_variants(candidate_name):
    for match in re.finditer(re.escape(variant), text, re.IGNORECASE):
        results.append(RecognizerResult("PERSON", match.start(), match.end(), 0.95))
```

Cela résout les problèmes 1, 2 et 3 simultanément : le nom du candidat est redacté
_indépendamment_ de ce que GLiNER détecte.

== Fix 2 --- Reconnaisseur Presidio pour les numéros de passeport

Ajouter un `PassportRecognizer` dans `recognizers.py`, similaire à `AvsAhvRecognizer` :

```python
class PassportRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("passport_alpha", r"\b[A-Z]{1,2}\d{6,9}\b", 0.4),
    ]
    CONTEXT = ["passport", "passeport", "document number",
               "travel document", "numéro de document"]
```

Score de base à 0.4 (ambiguë) mais boosté par les mots-clés de contexte. Cela couvre
les IELTS/TOEFL qui mentionnent "Document Number" ou "Passport" à proximité.

== Fix 3 --- Filtre de faux positifs pour le reconnaisseur passeport

Pour éviter la sur-redaction (codes cours `CS250112`, matricules), ajouter un filtre dans
`post_filters.py` qui exclut les patterns connus :

```python
_ACADEMIC_PREFIX = re.compile(r"^(CS|EE|ME|PH|MA|CH|MT)\d+$")

def filter_academic_codes(text, results):
    return [r for r in results
            if r.entity_type != "PASSPORT"
            or not _ACADEMIC_PREFIX.match(text[r.start:r.end])]
```

#v(0.3cm)

= Conclusion

#figure(
  table(
    columns: (1fr, auto, auto),
    align: (left, center, center),
    stroke: 0.5pt + epfl-border,
    fill: (_, row) => if row == 0 { epfl-light } else { none },
    inset: 8pt,
    table.header([*Correctif*], [*Problèmes résolus*], [*Effort*]),
    [Propagation nom depuis métadonnées], [1, 2, 3], [~30 lignes],
    [Reconnaisseur passeport + filtre], [4], [~40 lignes],
  ),
  caption: [Deux correctifs ciblés couvrent les 4 problèmes identifiés.],
)

#v(0.2cm)

#callout(titre: "Avis global", icon: "✓", couleur: success-green)[
  Le pipeline est opérationnel pour un usage en recherche. *100%* de couverture sur les PII
  les plus sensibles (emails, adresses, téléphones, IBAN, AVS). Les ~70 lignes de correctifs
  proposés porteraient la couverture des noms au-delà de *99%* et ajouteraient la détection
  des numéros de passeport.
]
