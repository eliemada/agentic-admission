# Reports — deliverables index

Everything submitted for grading lives in this directory. Start with the final report; the
weekly reports document how the project got there, and the calibration notes are the raw
analyses behind the results chapter.

## Final deliverables

| File | What it is |
|---|---|
| [`final_report.pdf`](final_report.pdf) ([source](final_report.typ)) | The semester report — 11 sections, 3 appendices, bibliography ([`references.bib`](references.bib)) |
| [`final_presentation.pptx`](final_presentation.pptx) | 15-slide defence deck with speaker notes |
| [`anonymization-audit.pdf`](anonymization-audit.pdf) ([source](anonymization-audit.typ)) | 900-file stratified anonymisation audit (50 × 18 document types, seed 42) |
| [`architecture-design.pdf`](architecture-design.pdf) | Pre-implementation architecture sketch (week 6) |
| [`figures/`](figures/) | Graphviz deliberation-protocol diagrams + completeness heatmap |

## Weekly progress reports (`weekly/`)

All 14 weeks, in French, PDF + Typst source. One line each:

| Week | Date | Topic |
|---|---|---|
| [01](weekly/semaine-01.pdf) | 24 Feb | Project launch — system-design reading, first data exploration |
| [02](weekly/semaine-02.pdf) | 26 Feb | Dossier archives received (2020–2026), intake and structure analysis |
| [03](weekly/semaine-03.pdf) | 8 Mar | PII anonymisation pipeline implemented (Presidio + GLiNER) |
| [04](weekly/semaine-04.pdf) | 10 Mar | Anonymisation reworked after supervisor feedback |
| [05](weekly/semaine-05.pdf) | 17 Mar | Full PDF → text → anonymisation run; stratified audit |
| [06](weekly/semaine-06.pdf) | 24 Mar | Anonymiser hardening from audit findings; evaluation pipeline design |
| [07](weekly/semaine-07.pdf) | 7 Apr | End-to-end multi-agent evaluation pipeline implemented |
| [08](weekly/semaine-08.pdf) | 19 Apr | Four pipeline changes from the supervisor meeting (incl. minor recommendation) |
| [09](weekly/semaine-09.pdf) | 26 Apr | Spring 2025–26 cohort received; synthèse-PDF parsing (no Excel this year) |
| [10](weekly/semaine-10.pdf) | 3 May | Dashboard migrated from Streamlit to React + FastAPI |
| [11](weekly/semaine-11.pdf) | 9 May | EPFL-internal evaluation branch — deterministic gates ahead of the LLM |
| [12](weekly/semaine-12.pdf) | 16 May | Reproducibility: 5 independent runs on the full 128-candidate cohort |
| [13](weekly/semaine-13.pdf) | 23 May | Committee-vs-system audit — 47 disagreements classified |
| [14](weekly/semaine-14.pdf) | 30 May | The three-band rule (Géraldine, 2026-05-19): 68% → 82% agreement |

## Calibration analyses (`calibration/`)

Raw before/after analyses that feed §6–7 of the final report:

| File | What it measures |
|---|---|
| [`committee-vs-system-policy-v2.md`](calibration/committee-vs-system-policy-v2.md) | Main committee-vs-system disagreement analysis (5-run majority vote) |
| [`committee-vs-system-2026-05-11.md`](calibration/committee-vs-system-2026-05-11.md) | First full-cohort comparison |
| [`cohort-variance-2026-05-09.md`](calibration/cohort-variance-2026-05-09.md) | Run-to-run variance across 5 independent runs |
| [`epfl-internal-fix-2026-05-11.md`](calibration/epfl-internal-fix-2026-05-11.md) | EPFL-internal fix, first measurement |
| [`epfl-internal-fix-run01-only.md`](calibration/epfl-internal-fix-run01-only.md) | Single-run sanity check of the fix |
| [`epfl-internal-fix1+2-vs-baseline.md`](calibration/epfl-internal-fix1+2-vs-baseline.md) | Fix 1 + 2 vs week-12 baseline |
| [`epfl-internal-fix2-incremental.md`](calibration/epfl-internal-fix2-incremental.md) | Incremental effect of fix 2 alone |

## Rebuilding

```bash
cd reports && typst compile final_report.typ          # final report
cd reports && typst compile anonymization-audit.typ   # audit
cd reports/weekly && typst compile semaine-14.typ     # any weekly report
cd reports/figures && dot -Tpng deliberation_protocol.dot -o deliberation_protocol.png
```
