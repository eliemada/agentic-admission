# Admission Decision-Support Dashboard — Design

**Date:** 2026-03-24
**Status:** Approved
**Audience:** MTE admission committee (~5-10 academics, internal tool)

## Overview

Evolve the existing Streamlit dossier viewer into an admission decision-support
dashboard. Committee members see pre-computed AI summaries of each candidate, can
expand for full agent analysis with document references, chat about a candidate,
and access the existing PDF/text/anonymized document viewer.

## Main View — Candidate Table

A filterable, sortable table showing all candidates for a selected semester.

| Column     | Content                                                                 |
|------------|-------------------------------------------------------------------------|
| Candidate  | Anonymized name/ID                                                      |
| School     | Origin institution                                                      |
| GPA        | Normalized score                                                        |
| Program    | Study level                                                             |
| AI Summary | 3 sentences — or italic "Insufficient information" when confidence < 0.3 |
| Status     | Badge: Admit (green) / Reject (red) / Discuss (amber) / Pending (gray) |

**Filters:** status, GPA range, school, free-text search across summaries.

Clicking a row expands it inline to reveal the detail panel.

## Expanded Detail Panel — Three Tabs

### Tab 1: Agent Analysis (default)

- Moderator's final synthesis at the top
- Per-agent breakdown: Strict, Holistic, Technical
- Each shows: decision, confidence (0.0–1.0), reasoning
- **Document references are inline links** — e.g., "Strong recommendation from
  Stanford professor" — clicking opens the anonymized document in a slide-over
  panel (no page navigation)

### Tab 2: Chat

- Conversational interface scoped to the selected candidate
- Context injected into each LLM call: anonymized docs + pre-computed evaluations
- System prompt enforces answering only from provided context
- Streamed responses from local Llama on SCITAS
- Chat history persists within the session
- Disclaimer shown when limited documents are available

### Tab 3: Documents (Advanced View)

- Existing PDF / Extracted Text / Anonymized viewer (carried over)
- Same split view, PDF focus, and comparison modes
- Documents listed by type (motivation letter, transcripts, recommendations, etc.)

## Data Flow — Pre-computed Evaluations

```
Anonymized docs (data/processed/anonymized/)
        ↓
Agent panel evaluates each candidate
(Strict, Holistic, Technical → Moderator)
        ↓
JSON per candidate: data/processed/evaluations/{semester}/{candidate_id}.json
        ↓
Dashboard reads and displays
```

### Evaluation JSON Schema

```json
{
  "candidate_id": "string",
  "semester": "string",
  "summary": "string | null",
  "status": "admit | reject | discuss | pending",
  "confidence": 0.0,
  "evaluations": [
    {
      "role": "strict | holistic | technical",
      "decision": "string",
      "confidence": 0.0,
      "reasoning": "string",
      "document_references": [
        {"doc_type": "recommendation_letter", "doc_path": "...", "note": "..."}
      ]
    }
  ],
  "moderator": {
    "final_decision": "string",
    "reasoning": "string",
    "report": "string"
  }
}
```

### Fallback Logic

Summary is set to `null` (and UI shows "Insufficient information to assess this
candidate") when:
- Moderator confidence is below 0.3
- Fewer than 2 documents are available
- Agent panel cannot produce a meaningful consensus

**No hallucinated output.** Honesty over completeness.

## Technology

- **Frontend:** Streamlit (single repo, single language, `uv run poe dashboard`)
- **LLM:** Local Llama-3.1-8B-Instruct on SCITAS via OpenAI-compatible API
- **Chat context:** Anonymized documents + agent evaluations only (no raw PII)
- **Storage:** JSON files for evaluations, existing Parquet for structured data

## Future Phases

### Phase 2: On-demand Re-evaluation (GitHub issue)

Allow committee members to trigger a live re-evaluation of a candidate from the
dashboard. The "Re-evaluate" button runs the agent panel in real-time and updates
the stored JSON.

### Phase 3: RAG Knowledge Base (GitHub issue)

- Embed anonymized documents with local embedding model (e.g., nomic-embed-text)
- Vector store: LanceDB (Parquet-native, file-based, SCITAS-friendly)
- Curated knowledge base: MTE program criteria, admission guidelines, historical
  decision rationale, school rankings
- Enables comparative queries: "How does this GPA compare to last year's admits?"
- Design for this from the start: abstract retrieval behind an interface
