// =============================================================================
//  Agentic Admission — Final Project Report
//  Author: Elie Bruno · Supervisor: Prof. Gaétan de Rassenfosse
//  Spring 2026 · EPFL · College of Management of Technology
// =============================================================================

#import "final_report_template.typ": *

#show: report.with(
  title: "Agentic Admission",
  subtitle: "A multi-agent LLM panel for MTE dossier evaluation at EPFL",
  author: (name: "Elie Bruno", sciper: ""),
  supervisor: "Prof. Gaétan de Rassenfosse",
  course: "Semester Project · CDM-MTE",
  program: "Master in Management, Technology and Entrepreneurship",
  institution: "College of Management of Technology (CDM)",
  semester: "Spring 2026",
  date: "30 May 2026",
  abstract: [
    The MTE admission committee at EPFL processes around 130 dossiers
    per semester and another wave of 100+ in the autumn round. Each
    dossier carries a transcript, two reference letters, a motivation
    letter, a CV, and a heterogeneous bundle of certificates. The
    committee meets for a few hours and decides. This project builds a
    decision-support system that emulates the committee's deliberation
    with four specialist LLM evaluators and a Chair agent, calibrated
    against the committee's own historical verdicts on 1,342 candidates
    from 2020 to 2026. The system normalises Excel inputs that change
    schema every year, anonymises 12,529 dossier documents with a
    Presidio + GLiNER pipeline that reaches 100% coverage on
    high-sensitivity PII, runs a structured-output multi-agent
    deliberation against vLLM-served models, and applies a three-band
    GPA gate that mirrors the rule a former chair documented in 2026.
    On the Spring 2025--26 cohort the system reaches 82% agreement with
    the committee on the 28 EPFL-internal candidates (up from 68% before
    the band rule), with a 5-run majority-vote stability of 76.6% on the
    full cohort. The report tells that story end to end: the engineering
    decisions that made it reproducible, the academic decisions that
    made it falsifiable, what we would have done with more time, and
    what would have to change to port the system to other EPFL
    admission filières.
  ],
  keywords: (
    "LLM-as-judge",
    "multi-agent deliberation",
    "admission decision support",
    "calibration",
    "anonymisation",
    "EPFL MTE",
  ),
)

// =============================================================================
//  1. Introduction
// =============================================================================

= Introduction

== Problem

Every semester the MTE admission committee at EPFL receives around 130
applications in the spring round and a second wave of 100+ in the
autumn round. A dossier is a heterogeneous package: an academic
transcript on whatever scale the home institution uses (US 4.0, French
20, Swiss 6, German 1.0--6.0), two recommendation letters, a motivation
letter, a CV, English-proficiency scores, and a stack of certificates.
Committee members read all of this and meet for two afternoons to
deliver an accept / reject / waitlist verdict for each candidate.

The bottleneck is not the decision itself, it is the reading. A
reasonable reader needs 20--30 minutes to form an opinion on one
dossier. At 130 dossiers per round, two committee members reading every
file means 80--130 hours of reading split across a calendar that
collapses near the deadline. Cases at the boundary get less time than
they need; clear-accept and clear-reject cases get more time than they
need. The committee has asked, for several years, whether a triage
layer could pre-classify dossiers and surface only the borderline ones
for full discussion.

This project is the technical answer to that question. The system does
not decide; the committee still decides. The system reads every
dossier, scores it on eight dimensions, recommends a verdict, and
records its reasoning in a form the committee can audit.

== Research question

#definition([Research question])[
  Can a multi-agent panel of large language models, calibrated against
  the historical decisions of a real admission committee, reach an
  agreement level on a held-out cohort that makes the system useful as
  a triage tool without introducing systematic bias?
]

Three sub-questions sit underneath:

+ *Calibration.* How do we measure agreement when the ground truth is
  itself a noisy panel of humans, and what is a meaningful target?

+ *Stability.* LLMs are stochastic. How much does the same dossier
  move from run to run, and which scoring dimensions are stable enough
  to trust?

+ *Auditability.* The committee will not adopt a system whose
  decisions cannot be challenged in a meeting. What output format
  makes the system's reasoning easy to interrogate?

== Contributions

This report describes four contributions:

+ An *extraction and anonymisation pipeline* that takes six years of
  inconsistent committee Excel exports and 12,529 dossier documents,
  and produces a single canonical Parquet of 1,342 candidates with
  100% coverage on emails, addresses, IBANs, AVS, and 96.1% on names
  (see Section 3).

+ A *multi-agent deliberation architecture* with four specialist
  evaluator personas and one Chair, run under structured outputs,
  costed under \$0.10 per dossier on Gemini Flash and \$0.70 on
  Sonnet 4.6 (Section 4).

+ A *calibration loop* that compares the system against the
  committee's own decisions on Spring 2025--26 across five runs, with
  iterative prompt fixes that moved EPFL-internal agreement from
  50% to 82% in three weeks (Sections 6 and 7).

+ A *spec-first engineering posture* with type checking, ruff
  `ALL`, atomic PRs, and a public changelog of 14 weekly reports.
  Every architectural change is traceable to a design document and a
  PR (Section 5).

== Reading order

Sections 1--4 describe the system. Sections 5 and 6 split the work
into its engineering and academic halves. Section 7 presents results.
Sections 8 and 9 look forward: what we would do with more time, and
what would change to port the system to a different EPFL programme.
Appendices A--C carry the long-form artefacts (full evaluator prompt,
per-cohort agreement table, file inventory).

// =============================================================================
//  2. Background and related work
// =============================================================================

= Background

== Why LLMs

Three properties of recent instruction-tuned LLMs make them a
plausible fit for dossier reading. First, they handle long, mixed-form
text without bespoke parsing. Second, they emit structured outputs
that downstream code can consume. Third, they can be steered with a
prompt that encodes a rubric the committee actually uses, including
edge cases like the EPFL-internal three-band rule (Section 6).

None of this means the LLM is calibrated. The literature on
LLM-as-judge is consistent on one point: zero-shot judgements drift
from human judgements in ways that depend on the model, the prompt,
the domain, and the ground-truth source
@zheng2023judging @gu2024survey. The remedy is to measure
that drift on the target task and then design either the prompt, the
rubric, or the aggregation to close the gap. That measure-and-close
loop is the spine of this project.

== Multi-agent deliberation

Single-agent scoring conflates evaluation criteria that have
different evidential bases. A motivation letter and a transcript do
not weigh the same kind of signal. We split the work into four
specialist personas and a Chair, each with its own prompt and its own
narrow scoring task. The Chair does two things: surface meaningful
disagreement between specialists, and synthesise a final
recommendation with explicit weights.

This is a classical separation-of-concerns argument applied to a
prompt design. The benefit shows up in audit: when the system
disagrees with the committee, we can read the four specialist
scorecards side by side and ask which one is wrong. A single-agent
score gives no such handle. Verga et al. report that a jury drawn
from several model families beats a single larger judge
@verga2024poll; our four personas share one model, a limitation the
threats list in Section 6 carries as an open item.

== Calibration against a noisy panel

The committee is the ground truth and the committee is noisy: the
same dossier read by a different pair of committee members on a
different day can produce a different verdict. Section 6 treats each
recorded decision as a point estimate and derives the ceiling that
noise puts on any agreement number.

== Related work

The closest prior systems fall into three groups. First, the
LLM-as-judge frameworks: MT-Bench @zheng2023judging, AlpacaEval
@alpacaeval, and JudgeBench @tan2024judgebench benchmark model
responses against reference answers. The biases this literature
documents in LLM judges (verbosity @saito2023verbosity, position
@wang2023fair, and the wider taxonomy in @ye2024justice) apply to
any system that scores free-form text; Section 6 carries the ones
we have not yet measured as threats.

Second, admission systems trained on committee history. GRADE
@waters2014grade predicted graduate-admission verdicts at UT Austin
from past committee decisions and was retired in 2020 after public
criticism that a model calibrated on historical decisions reproduces
historical bias. The criticism transfers to this project unchanged,
and it is the reason the bias audit ranks first among the open items
in Section 8.

Third, multi-agent deliberation. Debate between LLM agents improves
factuality on reasoning benchmarks @du2023debate, and it also
degenerates: Liang et al. observe agents converging on their first
answers instead of producing new arguments @liang2023debate. Our
debate phase is conditional (it runs only on detected conflicts) and
bounded at two rounds. The 5-run majority vote of Section 6 is
self-consistency @wang2022selfconsistency applied to a three-way
classification.

The regulatory frame is the EU AI Act, which classifies systems that
determine access to education as high-risk @euaiact2024. The
fairness literature and the Act point the same way: we treat the
system as decision-support and not decision-making. Section 6
returns to the design choices that follow from that posture.

// =============================================================================
//  3. Data and anonymisation
// =============================================================================

= Data and anonymisation

== Source corpus

The committee shares two artefacts per round. The *decision Excel*
records one row per evaluator per candidate (so three rows per
candidate for a triple-evaluator design), with the committee's final
column appended at the right. The *dossier zip* contains one
sub-directory per candidate with the transcript PDF, the two
recommendation letters, the motivation letter, the CV, the
English-test certificate, and an IS-Academia synthesis form. The
schema of the Excel changes every year. The internal structure of the
dossier zip changes per dossier.

#figure(
  table(
    columns: (auto, auto, auto, auto),
    align: (left, center, center, left),
    [*Year*], [*Excel sheets*], [*Candidates*], [*Notable schema change*],
    [2020--21], [2], [228], [Triplet evaluators, no GPA column],
    [2021--22], [2], [241], [GPA column added, hidden gender col],
    [2022--23], [2], [233], [Decision column moved],
    [2023--24], [2], [218], [Reference grade scale changed],
    [2024--25], [2], [194], [Two new evaluators rotated in],
    [2025--26], [2], [228], [Section column renamed],
  ),
  caption: [Six years of decision Excels, 1,342 candidates total.
            Each row encodes a vote; the parser groups rows back into
            candidates and detects evaluator triplets.],
)

== Extraction pipeline

The extraction module (`src/agentic_admission/extraction/pipeline.py`,
523 lines) handles the year-to-year drift with three layers:

+ *Fuzzy header matching.* A header rule maps a regular-expression
  pattern to a canonical column name. The same logical column appears
  as `GPA / Average`, `Note moyenne`, `Average grade`, or `Moy. /
  Note` across years.

+ *Multi-row grouping.* The committee writes one row per evaluator.
  The grouper detects triplets by family-name + date proximity and
  collapses them into a single `CandidateRecord` with an evaluator
  list.

+ *Hidden-column detection.* Some years store the candidate's gender
  in a hidden Excel column. The parser reads hidden columns and
  attaches gender as a derived field without exposing it to the
  evaluator agents.

The output is a single Parquet file with 1,342 candidates, 18 fields
per row, and a stable schema. Downstream code never touches the raw
Excels again.

== Anonymisation

Dossier documents arrive with full PII: names, emails, phone numbers,
addresses, AVS / IBAN / SCIPER, passport numbers, dates of birth, and
photos. The anonymiser (`src/agentic_admission/anonymizer/`,
~75 KB of code) is a Presidio @presidio + GLiNER @zaratiana2024gliner
pipeline with:

- Custom recognisers for Swiss-specific PII (AVS, SCIPER) in
  `recognizers.py`.
- A passport-scan stripper in `strip_passports.py` that detects
  passport pages by layout and drops them before text extraction.
- Nine post-filters in `post_filters.py` (excluded entities, per-entity
  thresholds, partial words, length, common words, duration-as-date,
  grade-as-date, numeric IDs, academic codes) that catch false
  positives (academic course codes, matriculation numbers) and false
  negatives (ALL-CAPS names that GLiNER misses, partially-redacted
  name fragments).
- A name-propagation step that injects the candidate's filename-derived
  name as a synthetic recogniser hit before analysis, so the system
  redacts the name even when GLiNER cannot detect it.

A date-of-birth operator (`dob_operator.py`) keeps the year but masks
the month and day, producing `<DOB_1995>`. The year is kept on purpose
so the evaluators can reason about age-typical trajectory.

== Anonymisation audit

We sampled 900 files (50 per type, 18 document classes, stratified
random with seed 42) from the 12,529-file corpus and audited coverage
by hand and by regex.

#figure(
  table(
    columns: (auto, auto, auto, auto),
    align: (left, center, center, center),
    [*PII type*], [*Redactions*], [*Leaks*], [*Coverage*],
    [Emails], [1 499], [0], [100%],
    [Phone numbers], [1 467], [0], [100%],
    [Addresses], [1 841], [0], [100%],
    [URLs], [1 267], [0], [100%],
    [AVS / IBAN / SCIPER], [33], [0], [100%],
    [Person names], [9 442], [35], [96.1%],
    [Passport numbers], [---], [23], [n/a],
  ),
  caption: [Coverage by PII type on a 900-file stratified sample
            (Spring 2026 audit). Emails, addresses, and Swiss IDs are
            fully covered; names leak in 3.9% of files (mostly
            ALL-CAPS variants in foreign diplomas); passport numbers
            appear in 20% of IELTS / TOEFL certificates and were
            added to the recogniser pool in the subsequent fix.],
)

#callout(title: "Note", icon: "i", colour: info-blue)[
  `<DOB_YYYY>` preserves the year of birth on purpose: it lets
  evaluators reason about age-typical trajectories without exposing
  the exact birthdate. It is not a direct identifier.
]

The two fixes (name propagation from filename, passport recogniser
with academic-code filter) added ~70 lines and brought name coverage
above 99% on the next audit pass.

// =============================================================================
//  4. System architecture
// =============================================================================

= System architecture

== End-to-end flow

#figure(
  block(width: 100%, inset: 10pt, [
    #grid(
      columns: (auto, auto, auto, auto, auto, auto, auto),
      column-gutter: 8pt,
      align: horizon,
      dnode([Excel \ Committee]),
      darrow(),
      dnode([Extraction \ pipeline], sub: [523 LOC, \ fuzzy headers]),
      darrow(),
      dnode([Anonymiser], sub: [Presidio + \ GLiNER]),
      darrow(),
      dnode([Dossier loader], sub: [PDF → text \ per candidate]),
    )
    #v(6pt)
    #align(center)[#dvarrow()]
    #v(6pt)
    #grid(
      columns: (auto, auto, auto, auto, auto, auto, auto),
      column-gutter: 8pt,
      align: horizon,
      dnode([Profile \ selector], sub: [EPFL-internal \ vs external]),
      darrow(),
      dnode([Evaluator \ panel (×4)], sub: [Academic, Reference, \ Motivation, Devil's adv.]),
      darrow(),
      dnode([Chair \ synthesis], sub: [composite, \ disagreements]),
      darrow(),
      dnode([GPA gate], sub: [3-band rule for \ EPFL-internals]),
    )
    #v(6pt)
    #align(center)[#dvarrow()]
    #v(6pt)
    #align(center)[
      #dnode(
        [Verdict JSON],
        sub: [accept / reject / waitlist, 8 dimension scores, pros/cons per dimension, recommended minor],
        fill: epfl-red.lighten(85%),
        stroke-colour: epfl-red,
      )
    ]
  ]),
  caption: [End-to-end flow. The extraction pipeline normalises the
            committee Excel into a Parquet; the anonymiser cleans
            dossier text; the dossier loader bundles documents per
            candidate; the profile selector picks the EPFL-internal
            or external rubric; four evaluators score in parallel;
            the Chair synthesises; the GPA gate applies the
            three-band rule for EPFL-internals.],
)

== The four evaluators

Each evaluator is one LLM call with a role-specific system prompt
(`src/agentic_admission/agents/prompts.py`) and a JSON-schema
response model (`models/evaluation.py`). The four roles:

#figure(
  table(
    columns: (auto, auto, auto),
    align: (left, left, left),
    [*Role*], [*Scores*], [*Reads*],
    [Academic], [`academic_strength`, `institution_quality`],
                [Transcript, GPA, institution category],
    [Reference], [`reference_quality`, `calibration_confidence`],
                [2--3 letters + cultural calibration profile],
    [Motivation], [`motivation_clarity`, `program_fit`],
                  [Motivation letter, CV, work history],
    [Devil's adv.], [`risk_flags`, `consistency`],
                    [Full dossier, cross-document check],
  ),
  caption: [Specialist evaluators, their two scored dimensions, and
            the dossier slice each one reads.],
)

== The Chair

The Chair does two jobs in one prompt
(`src/agentic_admission/agents/chair.py`, 705 lines). First, it
detects semantic disagreement between the four scorecards. A score
gap is not a disagreement; a disagreement is when two evaluators
interpret the same evidence differently. For each disagreement the
Chair formulates a debate question; the system can optionally invoke
a second round where the disagreeing evaluators argue and re-score.

Second, the Chair synthesises a final 8-dimension scorecard, computes
the weighted composite, and emits accept / reject / waitlist with
structured pros and cons.

== Weights and profiles

The composite is a weighted sum of the eight dimensions. Two
profiles ship out of the box, defined as immutable dataclasses with
validated weights summing to 1.0
(`src/agentic_admission/agents/evaluation_profile.py`):

#figure(
  table(
    columns: (auto, auto, auto),
    align: (left, center, center),
    [*Dimension*], [*External profile*], [*EPFL-internal profile*],
    [`academic_strength`], [0.30], [0.45],
    [`institution_quality`], [0.18], [0.10],
    [`reference_quality`], [0.18], [0.00],
    [`calibration_confidence`], [0.12], [0.00],
    [`motivation_clarity`], [0.06], [0.15],
    [`program_fit`], [0.06], [0.15],
    [`risk_flags`], [0.05], [0.075],
    [`consistency`], [0.05], [0.075],
    [*Sum*], [*1.00*], [*1.00*],
  ),
  caption: [Composite weights per profile. EPFL-internals do not
            submit recommendation letters in four of five sampled
            dossiers, so the reference weights drop to zero and the
            mass redistributes to academic, motivation, and fit.
            The institution weight also drops because the institution
            is always EPFL and carries no signal.],
)

A historical bug in the original weights summed to 0.85 and capped
the composite at 8.5 / 10. The profile dataclass now validates the
sum at construction time and raises if any profile ever drifts again.

== Decision logic

The Chair recommendation feeds the decision function:

#figure(
  table(
    columns: (auto, auto),
    align: (left, left),
    [*Composite range*], [*Decision (default floors)*],
    [`composite >= 8.0`], [`accept`],
    [`7.0 <= composite < 8.0`], [`waitlist`],
    [`composite < 7.0`], [`reject`],
  ),
  caption: [Default composite floors. These are not free parameters:
            they were tuned in week 11 against the Spring 2024--25
            committee verdicts and held fixed since.],
)

A second decision layer sits on top: the GPA gate, which only fires
for EPFL-internal candidates and is described in Section 6.

== Minor recommendation

Accepted MTE candidates enrol in a disciplinary minor, and the
supervisor asked (meeting of 2026-04-19) that the system recommend
one for every dossier it reads. The recommendation is a first-class
output: `PanelVerdict.minor_recommendation` carries three ranked
minors with a 1--10 fit score and a short justification each, and
the dashboard shows them next to the verdict.

Two paths produce the ranking (`agents/minor_advisor.py`):

+ *EPFL-internal candidates* resolve through a fixed
  section-adjacency table (`agents/epfl_minor_map.py`): 16 EPFL
  bachelor names, detected from the `Domaine principal d'études`
  field of the synthesis form, map to a ranked triple drawn from a
  36-minor registry. The table encodes the committee's
  stay-in-or-near-the-section practice and was confirmed with the
  supervisor on 2026-05-09. Deterministic picks carry fixed scores
  10 / 9 / 8 so the dashboard can tell them apart from LLM fit
  scores. Detection is exact-match on purpose: an OCR-garbled
  bachelor name falls through to the LLM advisor instead of
  routing to the wrong section.

+ *External candidates*, and internals whose bachelor cannot be
  detected, go to an LLM advisor. When the scraped EPFL course
  catalogue is available, a curriculum-match report maps the
  candidate's courses to EPFL equivalents and the advisor grounds
  its ranking in that overlap; otherwise it works from transcript
  and CV alone. The prompt excludes the two minors the CDM committee
  itself runs (the MTE master's mirror minor and Financial
  Engineering, each a dedicated master in its own right), and a
  post-filter drops them anyway if the model recommends one
  regardless.

The advisor runs as a fifth parallel task next to the four
evaluators, and its failure is non-fatal: the verdict ships with an
empty recommendation rather than blocking the panel.

== LLM client

The LLM client (`agents/llm_client.py`, 352 lines) speaks to vLLM
@kwon2023vllm endpoints (Sonnet 4.6 via Anthropic-compatible API,
Gemini Flash via OpenRouter, Llama 3.1 served locally on SCITAS
GPUs). The vLLM build we serve on SCITAS does not expose OpenAI's
`response_format` field, so the client injects the JSON schema into
the system prompt and validates the response with Pydantic. Three retries on empty content, explicit `LLMBillingError`
on HTTP 402, exponential back-off on transport errors. The function
was refactored from a single 18-complexity, 69-statement monster into
a 45-line orchestrator + four named helpers (`_build_payload`,
`_send_request`, `_handle_http_error`, `_extract_raw_content`) during
week 14 cleanup.

// =============================================================================
//  5. Engineering approach
// =============================================================================

= Engineering approach

This section makes the case that the engineering choices on this
project were academically motivated. Spec-first design, lint
hygiene, and atomic PRs sound like industrial good-practice. On a
research project that needs to be reproducible, defensible, and
extended by someone else next year, they are necessary conditions for
the academic claims to hold.

== Spec-first

Every non-trivial change starts as a Markdown design document in
`docs/plans/`. As of week 14 the directory holds eight design docs:

#figure(
  table(
    columns: (auto, auto),
    align: (left, left),
    [*Date*], [*Design document*],
    [2026-03-16], [Multi-agent deliberation design],
    [2026-03-16], [Multi-agent deliberation implementation],
    [2026-03-24], [Admission dashboard design],
    [2026-03-27], [End-to-end evaluation pipeline],
    [2026-04-20], [Curriculum scraper design],
    [2026-05-08], [EPFL-internal branch],
    [2026-05-08], [GPA gate],
    [2026-05-08], [Profile fallback (no-reference handling)],
  ),
  caption: [Design documents shipped before code. Each one frames a
            hypothesis, lists the alternatives considered, fixes the
            chosen approach, and lists the validation criteria.],
)

The benefit shows up in code review: the reviewer reads the design doc
first, then reads the PR, and the PR is small because the doc covered
the rationale.

== Lint as a quality gate

The project runs ruff with `select = ["ALL"]` (over 700 rules) and
the `ty` type checker. Library code in `src/agentic_admission/` is
held to the full rule set. One-shot analysis scripts in `scripts/`,
SLURM launchers in `slurm/`, and exploratory dashboard code in
`dashboard/` are allowed to relax complexity, magic-number, and
docstring rules through a `per-file-ignores` block in
`pyproject.toml`. The distinction between library and script is
explicit, not implicit.

The single hardest rule to satisfy was complexity. The
`llm_client.complete` function carried a Ruff `C901` violation
(complexity 18 > 10) for three weeks while I prioritised feature
work. The cleanup in week 14 split it into four helpers and brought
complexity to 8.

== Atomic PRs

23 PRs landed on `main` during the semester. Each is a self-contained
unit with a passing test suite and a green CI. The largest (PR \#23
in week 14) touched 67 files and added +4,733 / -1,190 lines because
it bundled the band rule, the test cleanup, the `llm_client`
refactor, and the lint cleanup. Splitting that PR would have created
dependency chains across four merge cycles; I judged that the
review-time cost was lower than the coordination cost. The
squash-merge collapses the history.

== Reproducibility

The full pipeline reproduces from a clean checkout in four commands:

#figure(
  table(
    columns: (auto, auto),
    align: (left, left),
    [*Command*], [*What it does*],
    [`uv sync --frozen`], [Installs pinned dependencies from `uv.lock`],
    [`uv run poe extract`], [Builds the 1,342-candidate Parquet from raw Excels],
    [`uv run poe lint`], [Runs the 700+ ruff rules + `ty` type check],
    [`uv run poe test`], [Runs the 519-test suite with coverage gate],
  ),
  caption: [The four commands that recreate the audit-grade state of
            the repository. The lockfile is committed; CI verifies
            that `uv sync --frozen` produces an identical
            environment.],
)

This is the academic argument for the engineering: anyone who clones
the repo, runs four commands, and reads the 14 weekly reports can
reconstruct what was done, why, and in what order. A research
contribution that cannot be re-executed is a research contribution
that cannot be checked.

// =============================================================================
//  6. Academic approach
// =============================================================================

= Academic approach

== Method as a measurement loop

The academic spine of the project is a measure-and-close loop:

#figure(
  block(width: 100%, inset: 10pt, [
    #grid(
      columns: (auto, auto, auto, auto, auto, auto, auto),
      column-gutter: 6pt,
      align: horizon,
      dnode([Run system], sub: [128 candidates × 5 seeds]),
      darrow(),
      dnode([Aggregate], sub: [majority vote]),
      darrow(),
      dnode([Compare to \ committee], sub: [confusion matrix]),
      darrow(),
      dnode([Identify \ disagreement \ class], sub: [type A, B, C, D]),
    )
    #v(8pt)
    #align(center)[#dvarrow()]
    #v(8pt)
    #grid(
      columns: (auto, auto, auto, auto, auto, auto, auto),
      column-gutter: 6pt,
      align: horizon,
      dnode([Form \ hypothesis], sub: [why this class \ disagrees]),
      darrow(),
      dnode([Edit prompt / \ rubric / gate], sub: [smallest change]),
      darrow(),
      dnode([Re-run \ sub-cohort], sub: [28 EPFL-internals, \ ≈ 6 min, \$2]),
      darrow(),
      dnode([Measure delta], sub: [before / after], fill: epfl-red.lighten(85%), stroke-colour: epfl-red),
    )
  ]),
  caption: [The calibration loop. Each iteration costs about \$2 and
            six minutes on the EPFL-internal sub-cohort; the full
            128-candidate run costs \$10 and 30 minutes. The
            before-after script aligns two verdict sets on the same
            sub-cohort and prints a structured diff.],
)

The loop is the academic contribution as much as the system is. Each
iteration is a small, falsifiable claim: changing this paragraph of
the prompt should move these candidates in this direction. If the
claim fails the candidates do not move, or they move in the wrong
direction, and the iteration teaches us something about the rubric
the LLM is actually applying.

== Ground truth

The ground truth is the committee's recorded decision: one of accept,
reject, waitlist. The Spring 2025--26 cohort holds 128 candidates,
matched against 127 anonymised verdicts (one candidate, Farrel Gamma,
appears in the Excel but not in the anonymised corpus). The committee
uses `accept` and `reject` only; `waitlist` is a system-side category
that maps to the committee's in-meeting discussion.

The ground truth is noisy. Different committee pairs reading the same
dossier on a different day can produce a different verdict. We do not
have inter-rater data so we treat each recorded decision as a point
estimate. The implication: agreement above ~85% on a sub-cohort
where the rule is clear is probably the ceiling, because any pair of
human readers would not agree more often than that with each other.

== The Maillard case as a falsification event

In week 12 the system rejected eight EPFL-internal candidates;
seven of those rejections were committee accepts (the eighth lined
up with the cohort's single committee reject and was the only
agreement on the reject row). Five of the seven mis-rejected
candidates had an algebra + analysis average between 4.0 and 4.5 / 6.
The system's GPA gate (week-11 design) was a binary threshold:
`avg < 4.5 → reject`. The committee, on the same five files, looked
at the detailed grades behind the average and admitted.

#callout(title: "Maillard 2025-26", icon: "*", colour: violet-callout)[
  Etienne Maillard's algebra + analysis average is 4.31, below 4.5.
  Behind that average: Analyse I = 3.75 (a fail-and-retake), Analyse
  II = 5.25 (a strong recovery). The committee accepted on the
  recovery trajectory. The system's binary threshold could not see
  the trajectory and rejected.
]

This is a falsification event. The system's rule was wrong because
the system's rule was simpler than the committee's rule. I wrote to
Geraldine, the chair who had codified the historical practice, with
a single question: is 4.5 a hard floor, or a discussion zone?

== The three-band rule

Geraldine's answer, received on 2026-05-19, is the rule the system
now applies:

#figure(
  table(
    columns: (auto, auto, auto),
    align: (left, center, left),
    [*Band*], [*Algebra + analysis avg*], [*Committee action*],
    [`ACCEPT`], [`>= 4.5 / 6`], [Admit on the academic bar],
    [`DISCUSS`], [`4.0 <= avg < 4.5`], [Read the detailed grades],
    [`REJECT`], [`< 4.0`], [Automatic reject],
  ),
  caption: [The three-band rule for EPFL-internals, as the chair of
            the historical committee specified it. The DISCUSS band
            is the lever that handles the Maillard case.],
)

The system now plumbs an `EpflInternalBand` enum from extraction
through to the Chair (`gpa_gate.py` adds 58 lines; `chair.py` adds
89 / -19 to handle the band in `apply_gate_overrides` and
`clamp_academic_strength_below_threshold`). The constants
`_EPFL_INTERNAL_ACCEPT_FLOOR` (4.5) and
`_EPFL_INTERNAL_REJECT_FLOOR` (4.0) are documented as committee
values, not tuning parameters.

The agreement on the 28-candidate EPFL-internal sub-cohort moved
from 19 / 28 (68%) to 23 / 28 (82%) after the rule shipped in
PR \#23.

== Threats to validity

+ *Calibration set size.* 128 Spring 2025--26 candidates is small;
  sub-cohort results (28 EPFL-internals) are tighter.

+ *Development-set tuning.* Every prompt and gate edit between
  weeks 12 and 14 was selected against the same 28 EPFL-internal
  candidates the 82% is reported on. The number is a
  calibration-set fit; the held-out test is the Fall 2025--26
  cohort listed in Section 8.

+ *Class imbalance.* The committee accepted 27 of the 28
  EPFL-internals, so an accept-everyone rule scores 96.4% raw
  agreement and the system's 82% sits below it. Raw agreement is
  the wrong lens on this sub-cohort; the five disagreements are the
  informative read: one hard reject the committee overrode as an
  exception, three discuss-band waitlists, and one committee reject
  the system routed to discussion instead of admitting.

+ *Single LLM family.* All headline numbers come from one model
  family. A Gemini Flash vs Sonnet 4.6 comparison is in the
  future-work list.

+ *Prompt sensitivity.* The agreement number moves with paragraph-level
  prompt edits. The 5-run majority vote dampens this; per-run stdev
  on composite is 0.175.

+ *Judge biases.* Verbosity and position effects are documented for
  LLM judges @saito2023verbosity @wang2023fair. We neither shuffle
  document order inside the dossier prompt nor control for letter
  length; each probe costs one cohort run on the existing corpus.

+ *Selection on the committee.* The committee's recorded decision
  is itself a noisy estimate. Any agreement number is bounded above
  by the committee's self-agreement, which we have not measured.

+ *No bias audit yet.* Section 8 lists this as the highest-priority
  next step.

// =============================================================================
//  7. Results
// =============================================================================

= Results

== Headline numbers

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  metric(
    label: "EPFL-internal agreement",
    value: "82%",
    detail: "23 / 28 after PR #23, up from 50%",
  ),
  metric(
    label: "Decision stability",
    value: "76.6%",
    detail: "98 / 128 same decision across 5 runs",
  ),
  metric(
    label: "Anonymisation coverage",
    value: "100%",
    detail: "emails, phones, addresses, AVS, IBAN",
  ),
)

== Full-cohort comparison

On Spring 2025--26 with five independent runs aggregated by majority
vote, the confusion matrix against the committee is:

#figure(
  table(
    columns: (auto, auto, auto, auto, auto),
    align: (left, center, center, center, center),
    [], [*System: accept*], [*System: waitlist*], [*System: reject*], [*Total*],
    [*Committee: accept*], [34], [6], [1], [41],
    [*Committee: reject*], [20], [46], [20], [86],
  ),
  caption: [Confusion matrix, Spring 2025--26, mode of 5 runs,
            127 / 128 matched. The committee uses two output
            categories (accept, reject); the system uses three
            (accept, reject, waitlist). The waitlist column captures
            the cases where the system hesitates and the committee
            commits.],
)

Mode-of-5 agreement on the full cohort is 54 / 127 (42.5%), which is
the wrong number to report alone. Two corrections matter:

+ The committee's reject row contains 46 cases the system marked
  waitlist. These are not flat misses; they are cases where the
  system surfaced the dossier for discussion and the committee
  closed it.

+ If we count waitlist as "agree-with-doubt" the agreement rises to
  (34 + 46 + 20) / 127 = 78.7%.

== Disagreement classes

The 73 disagreements (every candidate where the two verdicts differ)
split into four classes:

#figure(
  table(
    columns: (auto, auto, auto, auto),
    align: (left, center, center, left),
    [*Class*], [*N*], [*Mean composite*], [*Pattern*],
    [Type A: committee reject, system accept], [20], [8.5],
      [Strong international universities (NUS, Bocconi, RWTH, Erasmus,
       Duke Kunshan, KCL). The committee saw something in the dossier
       (weak letters, discontinuous path, MTE-fit mismatch) the system
       did not surface.],
    [Type B: committee accept, system reject], [1], [6.7],
      [The pre-PR \#23 system rejected nine such cases (seven were
       EPFL-internals); the band rule collapses the group to a single
       residual.],
    [Type C: committee accept, system waitlist], [6], [7.7],
      [Borderline composites between 7.4 and 8.0; the threshold
       hesitates and the committee admits.],
    [Type D: committee reject, system waitlist], [46], [6.9],
      [System surfaces the dossier for discussion; the committee
       closes it.],
  ),
  caption: [The four classes of disagreement and the dominant
            pattern in each. Type B is the addressable class and is
            what the EPFL-internal rule rewrite targeted; the band
            rule has already eliminated most of it.],
)

== Stability across runs

Five independent runs of the full Spring 2025--26 cohort produced
matching decisions for 98 / 128 candidates (76.6%). 30 candidates
flipped between at least two categories across runs; majority vote
collapses these to a single decision. Per-dimension score stability:

#figure(
  table(
    columns: (auto, auto),
    align: (left, center),
    [*Dimension*], [*Mean stdev across 5 runs*],
    [`motivation_clarity`], [0.053],
    [`institution_quality`], [0.129],
    [`calibration_confidence`], [0.132],
    [`program_fit`], [0.194],
    [`reference_quality`], [0.248],
    [`academic_strength`], [0.293],
    [`consistency`], [0.380],
    [`risk_flags`], [0.467],
  ),
  caption: [Per-dimension run-to-run standard deviation, averaged
            across 128 candidates and 5 runs. Motivation clarity is
            the most stable; risk flags is the least. The composite
            stdev is 0.175.],
)

The risk-flags volatility (0.467) is the LLM picking up different
secondary signals on each pass. We treat this dimension as a tiebreaker
in the composite (weight 0.05 in the external profile) and read the
pros / cons text rather than the score in audit.

== EPFL-internal sub-cohort, before and after the band rule

#figure(
  table(
    columns: (auto, auto, auto, auto, auto),
    align: (left, center, center, center, center),
    [*Run*], [*Accept*], [*Reject*], [*Waitlist*], [*Agreement / 28*],
    [Committee], [27], [1], [0], [reference],
    [Week 12 baseline], [13], [8], [7], [14 / 28 (50%)],
    [Week 13 fix 1 (single-rule)], [15], [7], [6], [15 / 28 (54%)],
    [Week 13 fix 2 (prompt re-write)], [19], [4], [5], [19 / 28 (68%)],
    [Week 14 PR \#23 (band rule + code)], [23], [1], [4], [23 / 28 (82%)],
  ),
  caption: [Three weeks of iteration on the EPFL-internal sub-cohort.
            Each row is a measured before-after on the same 28
            candidates. The week-14 number is from a single run
            after the band rule shipped; the next step is a 5-run
            majority-vote re-measurement (Section 8).],
)

The five remaining disagreements break down as follows. One
candidate sits below the band rule's `< 4.0` floor: the system
rejects, the committee admitted as an exception. Three candidates
sit in the `DISCUSS` band (`4.0 <= avg < 4.5`) where the committee
admitted on the detailed-grades trajectory and the system held back
to waitlist. The fifth case is Biersohn, whom the committee rejected
and the system put on waitlist. The below-4.0 exception is outside
Geraldine's documented rule and needs a supervisor conversation
before any code change; the three discuss-band waitlists are exactly
what the band was designed to do --- surface for committee
discussion --- so they are not a bug, they are the rule working as
specified.

== Cost

#figure(
  table(
    columns: (auto, auto, auto, auto),
    align: (left, center, center, center),
    [*Mode*], [*Per dossier*], [*Per cohort (128)*], [*5-run cohort*],
    [Gemini Flash], [\$0.08], [\$10], [\$50],
    [Sonnet 4.6], [\$0.70], [\$90], [\$450],
    [Local Llama 3.1 8B on SCITAS], [\~0 (compute)], [\~0], [\~0],
  ),
  caption: [Cost per dossier and per cohort by serving choice. Local
            Llama on SCITAS is free at the API layer; the cost is
            cluster-hours and queue latency.],
)

// =============================================================================
//  8. What we would do with more time
// =============================================================================

= What we would do with more time

The system is usable as a triage tool today on the EPFL-internal
sub-cohort and as a discussion-surfacer on the broader cohort. Eight
items would close the remaining gap between research prototype and
committee-grade decision support.

#figure(
  table(
    columns: (auto, 1fr, auto),
    align: (left, left, center),
    [*Item*], [*What it adds*], [*Priority*],
    [5-run vote post-PR \#23],
      [The 82% EPFL-internal agreement comes from a single post-merge
       run; a 5-run majority vote on the same 28 candidates removes
       the run-to-run draw. Cost: ~\$50 on Sonnet 4.6, 3 hours wall.],
      [High],
    [Bias audit],
      [Stratify the verdict-vs-committee disagreement by gender,
       nationality, and institution category. Output: a bias report
       the committee can either trust or reject the system on.],
      [High],
    [Model comparison],
      [Run Gemini Flash and Sonnet 4.6 head-to-head on the five
       remaining EPFL-internal disagreements and the twenty Type-A
       cases. Does a stronger model resolve Type-A without a prompt
       change?],
      [High],
    [Committee dashboard],
      [Side-by-side viewer (committee decision, system decision, GPA
       band, four scorecards, Chair synthesis). Scaffold exists in
       `dashboard/`; click-to-expand evaluator debate is the missing
       UI piece.],
      [Medium],
    [Active-learning loop],
      [Every committee-vs-system disagreement is a labelled example.
       Feed back as few-shot anchors and re-measure.],
      [Medium],
    [Fall 2025--26 cohort],
      [Extend the validation set from 128 to ~230 candidates. Requires
       anonymisation and matching; the extraction pipeline handles
       the schema already.],
      [Medium],
    [SCITAS deployment],
      [Move from API serving to a local Llama 3.1 on the HPC cluster.
       Removes per-dossier API cost and the data-sovereignty concern.],
      [Low],
    [Latency for live use],
      [End-to-end currently ~30 s per dossier. Target under 10 s for
       interactive committee use. Levers: smaller first-pass models,
       KV-cache reuse, Chair only on disagreement.],
      [Low],
  ),
  caption: [Eight items that close the gap between research prototype
            and committee-grade decision support, in priority order.
            All depend on existing infrastructure; none require new
            architecture.],
)

// =============================================================================
//  9. Portability to other admission filières
// =============================================================================

= Portability to other admission filières

The system was built for MTE. The architecture is portable; the
content is not. This section names what would have to change to use
the same code on a different EPFL programme.

== The portability manifest

#figure(
  table(
    columns: (auto, auto, auto),
    align: (left, left, left),
    [*Layer*], [*Stays*], [*Must be retuned*],
    [Extraction pipeline],
    [Fuzzy header engine, multi-row grouper, hidden-column detector],
    [The header rules (`_HEADER_RULES`) per filière Excel schema],
    [Anonymiser],
    [Presidio + GLiNER pipeline, post-filters, name propagation],
    [Allow-lists, filière-specific PII (visa fields for international
     PhD; legal names on transcripts for Bachelor)],
    [Evaluator personas],
    [Four-role separation, structured outputs, JSON schema],
    [Rubric weights, scoring anchors, system prompts per role],
    [Chair],
    [Disagreement detection, weighted synthesis, decision logic],
    [Decision thresholds (composite floors) per filière],
    [Gate rules],
    [`gpa_gate.py` mechanism, band enum plumbing],
    [Threshold values (4.5 / 4.0 for MTE EPFL-internals; different
     for Bachelor; not applicable for PhD)],
    [Prompts],
    [Schema-injection scaffold, OCR caveat, output-format directive],
    [Filière-specific exception blocks (e.g. the EPFL-internal block
     for MTE)],
    [Calibration set],
    [Verdict-vs-system diff structure, before-after script,
     5-run aggregator],
    [Historical decisions per filière (typically 1--3 years of
     committee Excels)],
    [Composite weights],
    [Profile dataclass, validation, renormalisation],
    [Per-filière weights for the eight dimensions],
  ),
  caption: [The portability manifest. The left column is the
            generic substrate; the middle column lists what is
            programme-agnostic; the right column lists what must be
            adapted to each new filière. The right column is the
            engineering cost of a port.],
)

== Worked examples

*EPFL Bachelor admission.* Grade-heavy, two-step (Maturité or
equivalent + EPFL CMS). Reference letters rare, motivation letter
shorter. Adaptations: drop the reference evaluator using the existing
`renormalize_without_reference` helper, push `academic_strength` to
~0.55, drop `program_fit`. The GPA gate becomes a Maturité-grade
gate with its own threshold table. Cost: ~7 dev-days.

*Executive MBA.* Work-experience heavy, no GPA gate, leadership
stories dominate. Adaptations: add a fifth evaluator persona (Career
Trajectory) that scores work history; expand the Devil's Advocate to
check claim consistency across LinkedIn, CV, and letters; skew the
composite toward leadership. The anonymiser needs a company-name
recogniser if the programme blinds institutions. Cost: ~8 dev-days,
mostly evaluator rubric.

*Doctoral admission.* Research statement and publication record
dominate. The motivation letter becomes a research statement and
needs a domain-aware evaluator. References carry more weight than in
any other programme. GPA gate is irrelevant; `publication_record`
and `research_fit` replace it. The Chair must match the candidate's
stated interest against a target lab's recent papers, which is a
retrieval layer the current system does not have. Cost: ~15 dev-days,
half on the lab-fit retriever.

== What does not port

Three things are MTE-specific and would not transfer at all:

+ The *EPFL-internal three-band rule.* The 4.5 / 4.0 thresholds on
  algebra + analysis are the MTE committee's documented practice.
  Other programmes do not have this rule.

+ The *culture-of-letters calibration profile.* The Reference
  evaluator's calibration data is tied to MTE's historical letter
  pool. Each programme would need to build its own.

+ The *minor recommendation logic.* The `epfl_minor_map.py`
  module maps EPFL bachelors to recommended MTE minors. It is
  meaningful only for MTE.

== Out-of-the-box wins

Three things port for free:

+ The *extraction pipeline* tolerates schema drift by design. A new
  filière's Excel needs new header rules, not a new parser.

+ The *anonymiser* is filière-agnostic. The only adaptation is the
  allow-list for filière-specific tokens.

+ The *5-run majority-vote calibration loop* is a generic protocol
  for measuring LLM agreement with a noisy human panel. It applies
  unchanged to any new filière.

== Estimated port effort

#figure(
  table(
    columns: (auto, auto, auto),
    align: (left, center, left),
    [*Target programme*], [*Engineering cost*], [*Critical dependency*],
    [EPFL Bachelor (MTE-like rubric)], [~7 dev-days],
      [Federal Maturité grade-conversion table],
    [EPFL Master in DS / CS], [~6 dev-days],
      [Programme-specific motivation prompt],
    [Executive MBA], [~8 dev-days], [Career-trajectory evaluator],
    [Doctoral admission], [~15 dev-days],
      [Lab-fit retrieval layer over recent papers],
    [Bachelor admission cross-section], [~10 dev-days],
      [Maturité gate + multi-cantonal grade scales],
  ),
  caption: [Rough engineering-effort estimates for porting the
            architecture to four neighbouring admission filières.
            None of these estimates include the calibration cost
            (committee data acquisition, anonymisation, validation
            runs).],
)

// =============================================================================
//  10. Conclusion
// =============================================================================

= Conclusion

The system reads every MTE dossier the committee receives, scores it
on eight dimensions through a panel of four specialist LLM
evaluators, applies the chair's documented three-band rule on
algebra + analysis grades, and emits an auditable accept / reject /
waitlist verdict. On the Spring 2025--26 cohort it reaches 82%
agreement with the committee on the 28 EPFL-internal candidates and
surfaces the right dossiers for discussion on the broader 128-candidate
cohort.

The system is not, and was never intended to be, a decision-maker.
The committee still decides. The system is a triage tool: it reads
fast, scores consistently, and explains itself in the same vocabulary
the committee uses. The remaining 18% disagreement on EPFL-internals
is the most interesting part of the project, because every
disagreement is a hypothesis about the system's rule or the
committee's rule, and every iteration of the loop in Section 6 has
moved the agreement number in one direction.

The engineering posture (spec-first, atomic PRs, ruff `ALL`)
exists in service of the academic claim. A research contribution
that cannot be reproduced is a research contribution that cannot be
checked. The four-command reproduction in Section 5 is the test of
that claim.

The next semester's work is named in Section 8: a 5-run majority
vote on the post-PR \#23 state, a bias audit on the existing verdict
corpus, a Sonnet-vs-Flash comparison on the borderline cases, and a
committee-side dashboard that puts the system's reasoning next to
the committee's own. None of these requires new architecture. All of
them require the careful, falsifiable measurement loop the project
has built.

// =============================================================================
//  References
// =============================================================================

#pagebreak()

#bibliography("references.bib", style: "ieee", title: "References")

// =============================================================================
//  Appendices
// =============================================================================

#pagebreak()

= Appendix A — Evaluator prompt (Academic, abridged)

```
You are the Academic Evaluator on an MTE admissions panel at EPFL.
Score two dimensions on 1-10:
- academic_strength: grades, coursework relevance, trajectory.
- institution_quality: reputation and rigour of the institution.

EPFL SPE THRESHOLD: if the candidate's GPA is BELOW the EPFL SPE
threshold for their institution category (A/B/C/X), cap
academic_strength at 5.

SCORING ANCHORS for academic_strength:
  9-10: Top 5%, GPA well above threshold.
  7-8:  Top 10-25%, at or above threshold.
  5-6:  Near threshold, some gaps.
  3-4:  Below threshold, weak core subjects.
  1-2:  Far below threshold, multiple failures.

## EPFL-internal candidates (3-band rule, Geraldine 2026-05-19)
- Decision signal is the algebra + analysis average.
- avg >= 4.5/6      -> accept on the academic bar
- 4.0 <= avg < 4.5  -> discuss zone (read detailed grades)
- avg <  4.0        -> automatic reject
A candidate at 4.31 is in the discuss zone, not a reject.

## Output format
For each dimension, emit {"pros": [...], "cons": [...]}.
Concrete facts, active voice, no adverbs, no filler.
```

= Appendix B — Per-cohort agreement summary

#figure(
  table(
    columns: (auto, auto, auto, auto, auto),
    align: (left, center, center, center, center),
    [*Cohort*], [*Candidates*], [*5-run stability*], [*Agreement*], [*Notes*],
    [Spring 2025--26 (full)], [128], [76.6%], [78.7% (with waitlist as doubt)],
      [Single LLM family],
    [Spring 2025--26 (EPFL-internal, week 12)], [28], [n/a (1 run)], [50%],
      [Pre-band-rule baseline],
    [Spring 2025--26 (EPFL-internal, week 13 fix 2)], [28], [n/a (1 run)], [68%],
      [After two prompt iterations],
    [Spring 2025--26 (EPFL-internal, week 14 PR \#23)], [28], [n/a (1 run)], [82%],
      [After band rule + code; 5-run vote pending],
    [Fall 2025--26], [~100], [---], [---],
      [Pending anonymisation],
  ),
  caption: [Agreement by cohort and milestone. The single LLM family
            and the pending 5-run vote on the post-PR \#23 state are
            the two open measurement items for Spring 2025--26.],
)

= Appendix C — Repository state

#figure(
  table(
    columns: (auto, auto),
    align: (left, left),
    [*Item*], [*Value*],
    [Lines of source (`src/agentic_admission/`)], [12 319 LOC (55 modules)],
    [Test count], [519 passing],
    [Coverage], [57.7% (line)],
    [Ruff rules enforced on `src/`], [~700 (rule set `ALL`)],
    [Type checker], [`ty` (zero errors)],
    [Pull requests merged on `main`], [23],
    [Weekly reports], [14 (`semaine-01.typ` .. `semaine-14.typ`)],
    [Design docs in `docs/plans/`], [8],
    [Analysis reports in `reports/`], [7 Markdown + 2 Typst],
    [Anonymisation corpus], [12 529 files],
    [Sampled audit set], [900 files (50 × 18 types, seed 42)],
    [Candidates in canonical Parquet], [1 342 (2020--2026)],
  ),
  caption: [Repository state at submission. The full audit trail
            (commits, PR descriptions, weekly reports, design docs)
            is on the `main` branch.],
)

#v(1cm)

#align(center)[
  #text(size: 9pt, fill: accent-gray)[
    Report compiled on #datetime.today().display("[day] [month repr:long] [year]")
    · Typst source: `reports/final_report.typ`
  ]
]
