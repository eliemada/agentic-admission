# Multi-Agent Deliberation System for MTE Admissions

## Overview

5-agent deliberation system with structured protocol for evaluating MTE admission dossiers.
Mimics a real admissions committee with distinct roles, cultural calibration for reference
letters, and targeted debate on disagreements.

## System Architecture

### Non-Agentic Pre-Processing (hand-coded)

- PDF-to-markdown extraction
- PII anonymization (already built via Presidio pipeline)
- Zero-entropy chunking + embedding of historical reference letters (offline, run once)
- Calibration profile generation: cluster historical letters by origin region/institution

### Calibration Pipeline

Built offline from the historical corpus (~1,342 candidates, 2020-2026):

1. Extract all historical reference letters to markdown
2. Zero-entropy chunk each letter at semantic boundaries
3. Embed chunks, store in local file-based vector DB (LanceDB or ChromaDB)
4. Cluster by origin region/institution using metadata from `all_candidates.parquet`
5. Generate calibration profiles (e.g., avg sentiment, language intensity by region)
6. At evaluation time: retrieve top-5 chunks by similarity, rerank for relevance

### Agent Roles

**Agent 1 -- Academic Evaluator**
- Inputs: transcripts, GPA, university ranking/reputation, GRE scores if available
- Scores: `academic_strength` (1-10), `institution_quality` (1-10)

**Agent 2 -- Reference Letter Specialist**
- Inputs: reference letters (markdown), calibration profile, 3-5 retrieved historical letter chunks with outcomes
- Scores: `reference_quality` (1-10), `calibration_confidence` (1-10)

**Agent 3 -- Motivation & Fit Evaluator**
- Inputs: motivation letter, CV, work experience
- Scores: `motivation_clarity` (1-10), `program_fit` (1-10)

**Agent 4 -- Devil's Advocate**
- Inputs: all dossier documents
- Scores: `risk_flags` (1-10, inverse: 10 = no concerns), `consistency` (1-10)

**Agent 5 -- Chair/Synthesizer**
- Inputs: all 4 agent scorecards + debate transcript (if any)
- Produces: final scorecard, composite score, recommendation, justification

### Structured Deliberation Protocol

```
Phase 1 -- Independent Evaluation
    4 specialist agents receive candidate dossier + calibration context
    Run in parallel (async)
    Each returns a Pydantic scorecard:
        - scores: dict of dimension -> 1-10
        - justification: 2-3 sentences per dimension

Phase 2 -- Disagreement Detection (Chair, LLM call)
    Chair receives all 4 scorecards + justifications
    Identifies semantic contradictions, not just score gaps
    Outputs:
        - conflicts: list of {dimension, agents_involved, nature_of_conflict}
        - debate_questions: specific question per conflict
        - or: "no meaningful disagreements" -> skip to Phase 4

Phase 3 -- Targeted Debate (max 2 rounds)
    For each conflict:
        - Only the involved agents participate
        - Round 1: each agent defends their position given Chair's question
        - Round 2: each agent responds to the other's defense

Phase 4 -- Final Ruling (Chair, LLM call)
    Chair receives all original scorecards + debate transcript (if any)
    Outputs final scorecard:
        - 8 dimension scores (1-10)
        - composite_score (weighted average)
        - recommendation: accept | reject | waitlist
        - justification: 2-3 sentences
```

### Output

Per candidate:
- 8 dimension scores (1-10)
- Weighted composite score
- Recommendation: accept / reject / waitlist
- 2-3 sentence justification

Stored in `evaluations.parquet` (one row per candidate).
Debate logs stored as JSON per candidate for auditability.

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| LLM | Qwen 2.5 on SCITAS (vLLM) | Local, no cloud dependency |
| Orchestration | Python asyncio + httpx | Simple, no heavy framework |
| Structured output | Pydantic models + JSON mode | Type-safe scorecards |
| Chunking | Zero-entropy chunking | Semantic boundary splits |
| Embeddings | Sentence-transformer (local) | CPU-friendly, offline |
| Reranking | Rerank retrieved chunks | Better relevance than raw cosine |
| Vector DB | LanceDB or ChromaDB (file-based) | No server, local on SCITAS |
| Storage | Parquet + JSON | Dashboard-friendly + auditable |

## Data Flow

```
Raw dossier PDFs
    -> PDF-to-markdown extraction (hand-coded)
    -> PII anonymization (Presidio, already built)
    -> Zero-entropy chunking + embedding of historical letters (offline, once)
    -> Calibration profile generation (offline, once)

New candidate evaluation:
    -> Retrieve top-5 reranked letter chunks from same region/tier
    -> Fan out to 4 agents in parallel (Qwen on SCITAS)
    -> Collect 4 scorecards (Pydantic models)
    -> Chair detects disagreements (LLM call)
    -> If conflicts: targeted debate (2-round cap, only involved agents)
    -> Chair produces final scorecard
    -> Write to evaluations.parquet + debate log JSON
```
