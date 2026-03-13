"""FastAPI application for the ISA Internship Report webapp.

Routes
------
GET  /api/public-key   → NaCl public key for client-side encryption
POST /api/generate     → decrypt creds, scrape ISA, compile PDF, return bytes
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure _lib is importable on Vercel (function root = api/)
sys.path.insert(0, str(Path(__file__).parent))

from _lib.crypto import decrypt_credentials, get_public_key_b64, load_or_generate_keypair
from _lib.report import build_company_summary, compile_pdf, render_typst
from _lib.scraper import LoginError, scrape_all
from _lib.scraper import login as isa_login

logger = logging.getLogger(__name__)

app = FastAPI(title="ISA Internship Report", docs_url=None, redoc_url=None)

# Load keypair once at module level (cold start)
_private_key = load_or_generate_keypair()

# Serve static files in local dev (Vercel serves public/ automatically)
_public_dir = Path(__file__).parent.parent / "public"
if _public_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_public_dir)), name="static")

    @app.get("/")
    async def serve_index() -> FileResponse:
        """Serve the main index.html page."""
        return FileResponse(str(_public_dir / "index.html"))


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    """Request body for the /api/generate endpoint."""

    encrypted: str  # base64-encoded sealed box
    faculty: str = "ic"


class PublicKeyResponse(BaseModel):
    """Response body containing the NaCl public key."""

    public_key: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/public-key")
async def get_public_key() -> PublicKeyResponse:
    """Return the NaCl public key for client-side credential encryption."""
    return PublicKeyResponse(public_key=get_public_key_b64(_private_key))


@app.post("/api/generate")
async def generate(req: GenerateRequest) -> Response:
    """Decrypt credentials, scrape ISA, build PDF, return it."""
    # 1. Decrypt
    try:
        username, password = decrypt_credentials(req.encrypted, _private_key)
    except Exception as err:
        raise HTTPException(status_code=400, detail="Failed to decrypt credentials.") from err

    # 2. Scrape
    try:
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            await isa_login(client, username, password)
            records = await scrape_all(client, faculty=req.faculty)
    except LoginError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Scraping failed")
        raise HTTPException(status_code=502, detail=f"Scraping error: {exc}") from exc

    if not records:
        raise HTTPException(status_code=404, detail="No offers found for this faculty.")

    # 3. Build report
    companies = build_company_summary(records)
    today = datetime.now(tz=UTC).strftime("%B %d, %Y")

    typst_source = render_typst(
        companies,
        faculty=req.faculty,
        author=username.split("@")[0] if "@" in username else username,
        date=today,
    )

    try:
        pdf_bytes = compile_pdf(typst_source)
    except FileNotFoundError:
        # Typst not installed — return the .typ source instead
        return Response(
            content=typst_source.encode("utf-8"),
            media_type="text/plain",
            headers={
                "Content-Disposition": "attachment; filename=isa-report.typ",
                "X-Fallback": "typst-not-installed",
            },
        )
    except Exception as exc:
        logger.exception("PDF compilation failed")
        raise HTTPException(status_code=500, detail=f"PDF compilation error: {exc}") from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=isa-report.pdf"},
    )
