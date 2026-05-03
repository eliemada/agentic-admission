"""FastAPI backend for the Admission Console.

Serves the React frontend (production build) and provides JSON API endpoints
for candidates, universities, cohort data, dossier documents, and semesters.

Run with:
    uv run uvicorn dashboard.api:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import io
import json
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from dashboard.exports import (
    candidate_to_pdf,
    candidates_to_csv,
    candidates_to_excel,
    cohort_to_csv,
    cohort_to_excel,
    universities_to_csv,
    universities_to_excel,
)
from dashboard.verdict_loader import get_available_semesters, load_all_verdicts

_PROJECT = Path(__file__).resolve().parent.parent
_EVAL_DIR = _PROJECT / "data" / "processed" / "evaluations"
_PARQUET_PATH = _PROJECT / "data" / "processed" / "all_candidates.parquet"
_UNI_PROFILES = _PROJECT / "data" / "reference" / "university_profiles.json"
_UNI_OVERRIDES = _PROJECT / "data" / "reference" / "university_overrides.yaml"
_COHORT_DIR = _PROJECT / "data" / "processed"
_DOSSIER_DIR = _PROJECT / "data" / "processed" / "dossiers"
_TEXT_DIR = _PROJECT / "data" / "processed" / "texts"
_ANON_DIR = _PROJECT / "data" / "processed" / "anonymized"
_FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
_OVERRIDES_PATH = _PROJECT / "data" / "processed" / "committee_overrides.json"

app = FastAPI(title="Admission Console API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Evaluation / Review endpoints
# ---------------------------------------------------------------------------


@app.get("/api/semesters")
def list_semesters() -> list[str]:
    """Return available semesters from verdict files."""
    return get_available_semesters(_EVAL_DIR)


@app.get("/api/candidates")
def list_candidates(semester: str | None = None) -> list[dict]:
    """Return candidates, optionally filtered by semester."""
    verdicts = load_all_verdicts(_EVAL_DIR, parquet_path=_PARQUET_PATH)
    if semester:
        verdicts = [v for v in verdicts if v["semester"] == semester]
    return verdicts


def _enrich_with_overrides(verdicts: list[dict]) -> list[dict]:
    """Merge committee overrides into verdict dicts for export."""
    overrides = _load_overrides()
    return [
        {**v, "_override": overrides.get(v["candidate_id"], {})}
        for v in verdicts
    ]


@app.get("/api/candidates/export.csv")
def export_candidates_csv(semester: str | None = None) -> StreamingResponse:
    """Export candidates as CSV."""
    verdicts = load_all_verdicts(_EVAL_DIR, parquet_path=_PARQUET_PATH)
    if semester:
        verdicts = [v for v in verdicts if v["semester"] == semester]
    data = candidates_to_csv(_enrich_with_overrides(verdicts))
    filename = f"candidates_{semester or 'all'}.csv"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/candidates/export.xlsx")
def export_candidates_excel(semester: str | None = None) -> StreamingResponse:
    """Export candidates as Excel."""
    verdicts = load_all_verdicts(_EVAL_DIR, parquet_path=_PARQUET_PATH)
    if semester:
        verdicts = [v for v in verdicts if v["semester"] == semester]
    data = candidates_to_excel(_enrich_with_overrides(verdicts), semester=semester or "")
    filename = f"candidates_{semester or 'all'}.xlsx"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/candidates/{candidate_id}/report.pdf")
def export_candidate_pdf(candidate_id: str) -> StreamingResponse:
    """Export a single candidate evaluation as a PDF report."""
    verdicts = load_all_verdicts(_EVAL_DIR, parquet_path=_PARQUET_PATH)
    match = [v for v in verdicts if v["candidate_id"] == candidate_id]
    if not match:
        raise HTTPException(status_code=404, detail=f"No evaluation for {candidate_id}")
    data = candidate_to_pdf(match[0])
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{candidate_id}_report.pdf"'},
    )


# ---------------------------------------------------------------------------
# Committee override endpoints
# ---------------------------------------------------------------------------


class CommitteeOverride(BaseModel, frozen=True):
    """A committee member's decision override for a candidate."""

    candidate_id: str
    decision: str  # "accept", "reject", "waitlist", or "pending"
    comment: str = ""


def _load_overrides() -> dict[str, dict]:
    """Load committee overrides from JSON file."""
    if not _OVERRIDES_PATH.exists():
        return {}
    try:
        return json.loads(_OVERRIDES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_overrides(overrides: dict[str, dict]) -> None:
    """Save committee overrides to JSON file."""
    _OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OVERRIDES_PATH.write_text(
        json.dumps(overrides, indent=2, ensure_ascii=False), encoding="utf-8",
    )


@app.get("/api/overrides")
def list_overrides() -> dict[str, dict]:
    """Return all committee overrides."""
    return _load_overrides()


@app.put("/api/overrides/{candidate_id}")
def set_override(candidate_id: str, override: CommitteeOverride) -> dict:
    """Set or update a committee override for a candidate."""
    from datetime import datetime, timezone

    overrides = _load_overrides()
    overrides[candidate_id] = {
        "decision": override.decision,
        "comment": override.comment,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    _save_overrides(overrides)
    return overrides[candidate_id]


@app.delete("/api/overrides/{candidate_id}")
def delete_override(candidate_id: str) -> dict:
    """Remove a committee override."""
    overrides = _load_overrides()
    removed = overrides.pop(candidate_id, None)
    if removed is None:
        raise HTTPException(status_code=404, detail="No override for this candidate")
    _save_overrides(overrides)
    return {"deleted": candidate_id}


# ---------------------------------------------------------------------------
# University endpoints
# ---------------------------------------------------------------------------


def _load_university_profiles() -> list[dict]:
    """Load university profiles dict and convert to list with overrides applied."""
    if not _UNI_PROFILES.exists():
        return []

    raw = json.loads(_UNI_PROFILES.read_text(encoding="utf-8"))

    # Profiles file is a dict keyed by university name
    profiles: list[dict] = []
    if isinstance(raw, dict):
        for name, data in raw.items():
            entry = {"name": name, **data} if isinstance(data, dict) else {"name": name}
            profiles.append(entry)
    elif isinstance(raw, list):
        profiles = raw

    # Apply board overrides
    if _UNI_OVERRIDES.exists():
        overrides = yaml.safe_load(_UNI_OVERRIDES.read_text(encoding="utf-8")) or {}
        if isinstance(overrides, dict):
            override_lookup = overrides
            for uni in profiles:
                name = uni.get("name", "")
                if name in override_lookup:
                    uni.update(override_lookup[name])

    return profiles


@app.get("/api/universities")
def list_universities() -> list[dict]:
    """Return university profiles with tier overrides applied."""
    return _load_university_profiles()


@app.put("/api/universities/{name}/tier")
def update_university_tier(name: str, tier: str) -> dict:
    """Update a university's tier in the overrides file."""
    if tier not in ("A", "B", "C", "X"):
        raise HTTPException(status_code=400, detail=f"Invalid tier: {tier}")

    overrides: dict = {}
    if _UNI_OVERRIDES.exists():
        overrides = yaml.safe_load(_UNI_OVERRIDES.read_text(encoding="utf-8")) or {}

    if name not in overrides:
        overrides[name] = {}
    overrides[name]["tier"] = tier

    _UNI_OVERRIDES.write_text(yaml.dump(overrides, allow_unicode=True), encoding="utf-8")
    return {"name": name, "tier": tier}


@app.get("/api/universities/export.csv")
def export_universities_csv() -> StreamingResponse:
    """Export universities as CSV."""
    data = universities_to_csv(_load_university_profiles())
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="universities.csv"'},
    )


@app.get("/api/universities/export.xlsx")
def export_universities_excel() -> StreamingResponse:
    """Export universities as Excel."""
    data = universities_to_excel(_load_university_profiles())
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="universities.xlsx"'},
    )


# ---------------------------------------------------------------------------
# Cohort endpoints
# ---------------------------------------------------------------------------


@app.get("/api/cohort/semesters")
def list_cohort_semesters() -> list[str]:
    """Return available cohort semesters from cohort JSON files."""
    semesters = sorted(
        p.stem.removeprefix("cohort_")
        for p in _COHORT_DIR.glob("cohort_*.json")
    )
    return semesters


@app.get("/api/cohort/{semester}")
def get_cohort(semester: str) -> list[dict]:
    """Return cohort data for a semester."""
    cohort_path = _COHORT_DIR / f"cohort_{semester}.json"
    if not cohort_path.exists():
        raise HTTPException(status_code=404, detail=f"No cohort data for {semester}")
    return json.loads(cohort_path.read_text(encoding="utf-8"))


@app.get("/api/cohort/{semester}/export.csv")
def export_cohort_csv(semester: str) -> StreamingResponse:
    """Export cohort as CSV."""
    cohort_path = _COHORT_DIR / f"cohort_{semester}.json"
    if not cohort_path.exists():
        raise HTTPException(status_code=404, detail=f"No cohort data for {semester}")
    cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
    data = cohort_to_csv(cohort)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="cohort_{semester}.csv"'},
    )


@app.get("/api/cohort/{semester}/export.xlsx")
def export_cohort_excel(semester: str) -> StreamingResponse:
    """Export cohort as Excel."""
    cohort_path = _COHORT_DIR / f"cohort_{semester}.json"
    if not cohort_path.exists():
        raise HTTPException(status_code=404, detail=f"No cohort data for {semester}")
    cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
    data = cohort_to_excel(cohort, semester=semester)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="cohort_{semester}.xlsx"'},
    )


# ---------------------------------------------------------------------------
# Dossier endpoints
# ---------------------------------------------------------------------------


@app.get("/api/dossier/semesters")
def list_dossier_semesters() -> list[str]:
    """Return semesters that have dossier data."""
    if not _DOSSIER_DIR.exists():
        return []
    return sorted(d.name for d in _DOSSIER_DIR.iterdir() if d.is_dir())


@app.get("/api/dossier/{semester}/candidates")
def list_dossier_candidates(semester: str) -> list[str]:
    """Return candidate folder names for a semester."""
    sem_dir = _DOSSIER_DIR / semester
    if not sem_dir.exists():
        return []
    return sorted(d.name for d in sem_dir.iterdir() if d.is_dir())


@app.get("/api/dossier/{semester}/{candidate}/documents")
def list_candidate_documents(semester: str, candidate: str) -> list[dict]:
    """Return list of documents for a candidate with their types."""
    candidate_dir = _DOSSIER_DIR / semester / candidate
    if not candidate_dir.exists():
        return []

    docs = []
    for doc_dir in sorted(candidate_dir.iterdir()):
        if not doc_dir.is_dir():
            continue
        doc_name = doc_dir.name

        # Detect document type from naming convention
        doc_type = _classify_document(doc_name)

        # Check what files exist
        has_pdf = any(f.suffix.lower() == ".pdf" for f in doc_dir.iterdir())
        has_text = (_TEXT_DIR / semester / candidate / doc_name).exists()
        has_anon = (_ANON_DIR / semester / candidate / doc_name).exists()

        docs.append({
            "folder": doc_name,
            "type": doc_type,
            "label": _doc_type_label(doc_type),
            "has_pdf": has_pdf,
            "has_text": has_text,
            "has_anonymized": has_anon,
        })

    return docs


@app.get("/api/dossier/{semester}/{candidate}/{doc_folder}/pdf")
def get_document_pdf(semester: str, candidate: str, doc_folder: str) -> FileResponse:
    """Serve the PDF file for a document."""
    doc_dir = _DOSSIER_DIR / semester / candidate / doc_folder
    if not doc_dir.exists():
        raise HTTPException(status_code=404, detail="Document folder not found")

    pdfs = [f for f in doc_dir.iterdir() if f.suffix.lower() == ".pdf"]
    if not pdfs:
        raise HTTPException(status_code=404, detail="No PDF found")

    return FileResponse(pdfs[0], media_type="application/pdf")


@app.get("/api/dossier/{semester}/{candidate}/{doc_folder}/text")
def get_document_text(semester: str, candidate: str, doc_folder: str) -> dict:
    """Return extracted markdown text for a document."""
    text_dir = _TEXT_DIR / semester / candidate / doc_folder
    if not text_dir.exists():
        raise HTTPException(status_code=404, detail="No extracted text")

    md_files = list(text_dir.glob("*.md"))
    if not md_files:
        raise HTTPException(status_code=404, detail="No markdown files")

    content = md_files[0].read_text(encoding="utf-8")
    return {"filename": md_files[0].name, "content": content}


@app.get("/api/dossier/{semester}/{candidate}/{doc_folder}/anonymized")
def get_document_anonymized(semester: str, candidate: str, doc_folder: str) -> dict:
    """Return anonymized markdown text for a document."""
    anon_dir = _ANON_DIR / semester / candidate / doc_folder
    if not anon_dir.exists():
        raise HTTPException(status_code=404, detail="No anonymized text")

    md_files = list(anon_dir.glob("*.md"))
    if not md_files:
        raise HTTPException(status_code=404, detail="No markdown files")

    content = md_files[0].read_text(encoding="utf-8")
    return {"filename": md_files[0].name, "content": content}


def _classify_document(folder_name: str) -> str:
    """Classify document type from its folder name."""
    lower = folder_name.lower()
    if "synthese" in lower or "synthèse" in lower:
        return "application_summary"
    if "lettre de motivation" in lower or "motivation" in lower:
        return "motivation_letter"
    if "recommandation" in lower or "recommendation" in lower:
        return "recommendation_letter"
    if "referent" in lower and "synthese" in lower.replace("è", "e"):
        return "referent_summary"
    if "releve" in lower or "relevé" in lower or "transcript" in lower:
        return "transcript"
    if "diplome" in lower or "diploma" in lower:
        return "diploma"
    if "cv" in lower or "curriculum" in lower:
        return "cv"
    if "langue" in lower or "language" in lower or "certificate" in lower:
        return "language_certificate"
    if "gre" in lower:
        return "gre_results"
    return "other"


def _doc_type_label(doc_type: str) -> str:
    """Human-readable label for a document type."""
    labels = {
        "application_summary": "Application Summary",
        "motivation_letter": "Motivation Letter",
        "recommendation_letter": "Recommendation Letter",
        "referent_summary": "Referent Summary",
        "transcript": "Transcript",
        "diploma": "Diploma",
        "cv": "CV",
        "language_certificate": "Language Certificate",
        "gre_results": "GRE Results",
        "other": "Other",
    }
    return labels.get(doc_type, doc_type.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Chat endpoint (LLM-powered Q&A per candidate)
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Incoming chat message from the frontend."""

    candidate_id: str
    message: str
    history: list[dict[str, str]] = []


def _load_university_context(school_name: str) -> str:
    """Load university profile, historical stats, and board notes for context."""
    if not school_name:
        return ""

    profiles = _load_university_profiles()
    # Fuzzy match: check if school_name is a substring of any profile name or vice versa
    school_lower = school_name.lower()
    match = None
    for p in profiles:
        p_name = p.get("name", "").lower()
        if p_name == school_lower or school_lower in p_name or p_name in school_lower:
            match = p
            break

    if not match:
        return f"=== UNIVERSITY PROFILE ===\nNo profile found for '{school_name}'.\n"

    lines = [
        "=== UNIVERSITY PROFILE ===",
        f"Name: {match['name']}",
        f"Country: {match.get('country', 'Unknown')}",
        f"Tier: {match.get('tier', 'X')} (A=priority/top, B=good, C=low interest, X=unknown)",
        f"Historical applicants: {match.get('applicants', 0)}",
        f"Historical accepts: {match.get('accepts', 0)}",
        f"Historical rejects: {match.get('rejects', 0)}",
        f"Accept rate: {match.get('accept_rate', 0):.0%}",
    ]
    notes = match.get("board_notes", "")
    if notes:
        lines.append(f"Board notes: {notes}")

    # Load GPA threshold from parquet for candidates from this school
    try:
        import pyarrow.parquet as pq

        if _PARQUET_PATH.exists():
            table = pq.read_table(_PARQUET_PATH)
            rows = table.to_pydict()
            school_gpas: list[str] = []
            school_thresholds: list[str] = []
            school_decisions: list[str] = []
            for i in range(table.num_rows):
                s = str(rows.get("school_name", [""])[i] or "")
                if s.lower() == school_lower or school_lower in s.lower():
                    gpa = str(rows.get("gpa_candidate", [""])[i] or "")
                    gpa_max = str(rows.get("gpa_max", [""])[i] or "")
                    threshold = str(rows.get("gpa_scale", [""])[i] or "")
                    quality = str(rows.get("school_quality", [""])[i] or "")
                    decision = str(rows.get("decision_final", [""])[i] or rows.get("decision_section", [""])[i] or "")
                    if gpa:
                        school_gpas.append(f"{gpa}/{gpa_max}" if gpa_max else gpa)
                    if threshold:
                        school_thresholds.append(threshold)
                    if decision:
                        school_decisions.append(decision)
                    if quality and "Tier" not in lines[-1]:
                        lines.append(f"SPE institution category: {quality}")

            if school_thresholds:
                unique_thresholds = sorted(set(school_thresholds))
                lines.append(f"GPA thresholds (from SPE): {', '.join(unique_thresholds)}")
            if school_gpas:
                lines.append(f"Historical GPAs from this school: {', '.join(school_gpas[:10])}")
            if school_decisions:
                lines.append(f"Historical decisions: {', '.join(school_decisions[:10])}")
    except Exception:
        pass

    return "\n".join(lines)


def _load_candidate_context(candidate_id: str) -> str:
    """Build LLM context from anonymized docs + evaluation verdict + university data."""
    parts: list[str] = []

    # Load evaluation verdict if it exists
    eval_path = _EVAL_DIR / f"{candidate_id}.json"
    school_name = ""
    if eval_path.exists():
        verdict = json.loads(eval_path.read_text(encoding="utf-8"))
        parts.append("=== EVALUATION VERDICT ===")
        parts.append(json.dumps(verdict, indent=2, ensure_ascii=False)[:6000])
        # Extract school name from GPA data
        school_name = verdict.get("gpa", {}).get("institution_name", "")

    # Load university profile + historical stats
    uni_context = _load_university_context(school_name)
    if uni_context:
        parts.append(uni_context)

    # Load anonymized documents
    # candidate_id format: "2020-21-fall_atamny" → semester="2020-21-fall", folder="atamny"
    underscore_idx = candidate_id.rfind("_")
    if underscore_idx > 0:
        semester = candidate_id[:underscore_idx]
        folder = candidate_id[underscore_idx + 1 :]
        anon_dir = _ANON_DIR / semester / folder
        if anon_dir.exists():
            for doc_dir in sorted(anon_dir.iterdir()):
                if not doc_dir.is_dir():
                    continue
                md_files = list(doc_dir.glob("*.md"))
                if md_files:
                    doc_type = _classify_document(doc_dir.name)
                    label = _doc_type_label(doc_type)
                    content = md_files[0].read_text(encoding="utf-8")[:3000]
                    parts.append(f"=== {label.upper()} ===")
                    parts.append(content)

    return "\n\n".join(parts) if parts else "No documents available for this candidate."


def _load_llm_settings() -> tuple[str, str, str]:
    """Load LLM settings from .env file.

    Returns (model_name, base_url, api_key).
    """
    from agentic_admission.config import settings

    # Use OpenRouter settings if configured, otherwise fall back to model settings
    if settings.openrouter_api_key:
        return settings.openrouter_model, settings.openrouter_base_url, settings.openrouter_api_key
    return settings.model_name, settings.model_base_url, ""


async def _stream_chat(
    system_prompt: str,
    messages: list[dict[str, str]],
) -> AsyncGenerator[str, None]:
    """Stream chat completion tokens from the LLM."""
    model, base_url, api_key = _load_llm_settings()

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "temperature": 0.3,
        "max_tokens": 1024,
        "stream": True,
    }

    if "openrouter" in base_url:
        from agentic_admission.config import settings as _settings

        if _settings.openrouter_provider:
            payload["provider"] = {"order": [_settings.openrouter_provider]}

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        yield token
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue


@app.post("/api/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    """Stream a chat response about a candidate using their anonymized dossier as context."""
    context = _load_candidate_context(req.candidate_id)

    system_prompt = (
        "You are an expert admission assistant for the EPFL Master's in Management, "
        "Technology, and Entrepreneurship (MTE) program. You help committee members "
        "understand candidate dossiers and make informed decisions.\n\n"
        "You have access to:\n"
        "- The candidate's anonymized dossier documents (transcripts, letters, CV, motivation)\n"
        "- The AI evaluation verdict with scores and justifications\n"
        "- The university profile: tier, historical accept/reject rates, board notes\n"
        "- GPA thresholds from EPFL SPE and historical GPAs from the same institution\n\n"
        f"Candidate: {req.candidate_id}\n\n{context}\n\n"
        "When asked about GPA thresholds or whether a candidate meets requirements, "
        "compare their GPA against the SPE threshold and historical data for their "
        "institution. Explain the grading system context (e.g. Dutch /10, Swiss /6, "
        "Chinese /4.0). Cite specific numbers. Be concise and direct."
    )

    # Build message list: history + new user message
    messages = [*req.history, {"role": "user", "content": req.message}]

    return StreamingResponse(
        _stream_chat(system_prompt, messages),
        media_type="text/plain",
    )


@app.post("/api/chat/sync")
async def chat_sync(req: ChatRequest) -> dict:
    """Non-streaming fallback: returns complete response as JSON."""
    context = _load_candidate_context(req.candidate_id)

    system_prompt = (
        "You are an expert admission assistant for the EPFL MTE program. "
        "You help committee members understand candidate dossiers.\n\n"
        f"Candidate: {req.candidate_id}\n\n{context}\n\n"
        "Answer based on the evidence. Cite documents and scores. Be concise."
    )

    messages = [*req.history, {"role": "user", "content": req.message}]
    tokens: list[str] = []
    async for token in _stream_chat(system_prompt, messages):
        tokens.append(token)

    return {"role": "assistant", "content": "".join(tokens)}


# ---------------------------------------------------------------------------
# Static frontend (production)
# ---------------------------------------------------------------------------

if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        """Serve the React SPA for all non-API routes."""
        file_path = _FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_FRONTEND_DIST / "index.html")
