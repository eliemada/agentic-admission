"""Async ISA EPFL internship scraper.

Adapted from the synchronous CLI scraper (``scrape_jobs.py``) for use inside
a FastAPI serverless function on Vercel.  Key changes:

* ``httpx.Client`` → ``httpx.AsyncClient``
* ``time.sleep`` → ``asyncio.sleep``
* ``tqdm`` → ``on_progress(current, total)`` callback
* Concurrent detail fetching with ``asyncio.Semaphore``
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

import httpx
from bs4 import BeautifulSoup
from lxml import etree

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://isa.epfl.ch/imoniteur_ISAP"
LOGIN_URL = f"{BASE_URL}/!logins.tryToConnect"
PORTAL_URL = f"{BASE_URL}/PORTAL14S.htm"
DETAIL_URL_TEMPLATE = (
    f"{BASE_URL}/!PORTAL14S.portalCell?ww_k_cell=2742535167&ww_i_stageview={{row_id}}"
)
ENCODING = "iso-8859-15"
REQUEST_DELAY = 0.25  # seconds between concurrent batches
CONCURRENCY = 5  # parallel detail fetches

# Faculty → ISA portal cell ID
FACULTY_CELLS: dict[str, str] = {"ic": "308197177"}

LISTING_COLUMNS = [
    "title",
    "company",
    "location",
    "sustainability_label",
    "number",
    "format",
    "registered",
    "positions",
    "professor",
    "creation_date",
]

DETAIL_FIELD_MAP: dict[str, str] = {
    "DETSTAGE_ETIQ_DUREE": "length",
    "DET_STAGES_ATT_SALAIRE": "salary",
    "STAT_BEN": "benefits",
    "STAT_DECTRAV": "description",
    "STAT_CONREQ": "required_skills",
    "STAT_REM": "remarks",
    "STCA_ENTRURL": "company_website",
    "DET_STAGE_CC_ENTR_MERE": "parent_company",
    "DET_STAGE_CC_ADRENTR": "company_address",
    "STCA_ENTRZIP": "company_city",
    "DET_STAGE_CC_EMAIL": "contact_email",
    "DET_STAGE_CC_TITRE": "contact_title",
    "STFC_CONT": "contact_name",
    "DET_STAGE_CC_PORTABLE": "contact_phone",
    "DET_STAGE_CC_TELPROF": "contact_pro_phone",
}

HIRING_PERIOD_LABELS = ["DETSTAGE_CHK_P1", "DETSTAGE_CHK_P2", "DETSTAGE_CHK_P3"]
LANGUAGE_MAP: dict[str, str] = {
    "STAGE_ETIQ_LANGUEFRANCAIS": "french_level",
    "STAGE_ETIQ_LANGUEANGLAIS": "english_level",
    "STAGE_ETIQ_LANGUEALLEMAND": "german_level",
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


class LoginError(Exception):
    """Raised when ISA authentication fails."""


async def login(client: httpx.AsyncClient, username: str, password: str) -> None:
    """Authenticate against the ISA portal."""
    resp = await client.post(
        LOGIN_URL,
        data={
            "ww_x_username": username,
            "ww_x_password": password,
            "ww_x_urlAppelant": "PORTAL14S.htm",
        },
    )
    if "ww_x_username" in resp.text:
        msg = "Login failed — check your ISA credentials."
        raise LoginError(msg)
    await client.get(PORTAL_URL)


async def _fetch_page(client: httpx.AsyncClient, url: str) -> str:
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.content.decode(ENCODING)


# ---------------------------------------------------------------------------
# Listing parser (XML)
# ---------------------------------------------------------------------------


def parse_listing(xml_text: str) -> list[dict[str, Any]]:
    """Parse listing XML into a list of row dicts."""
    soup = BeautifulSoup(xml_text, "xml")
    rows: list[dict[str, Any]] = []
    for tr in soup.find_all("tr"):
        row_id = tr.get("id", "")
        if not row_id or not row_id.isdigit():
            continue
        tds = tr.find_all("td")
        if len(tds) < len(LISTING_COLUMNS):
            continue
        record: dict[str, Any] = {"row_id": row_id}
        for col_name, td in zip(LISTING_COLUMNS, tds, strict=False):
            record[col_name] = td.get_text(strip=True)
        rows.append(record)
    return rows


# ---------------------------------------------------------------------------
# Detail parser
# ---------------------------------------------------------------------------


def _detail_value(tree: etree._Element, label: str) -> str:
    elements = tree.xpath(f'//detail[@c_detailmodele="{label}"]')
    if not elements:
        return ""
    el = elements[0]
    valeur = el.find("valeur")
    if valeur is not None and valeur.text:
        return valeur.text.strip()
    text = etree.tostring(el, method="text", encoding="unicode")
    return text.strip() if text else ""


def parse_detail(xml_text: str) -> dict[str, str]:
    """Parse the detail XML for a single offer."""
    result: dict[str, str] = {}
    try:
        tree = etree.fromstring(xml_text.encode(ENCODING))
    except etree.XMLSyntaxError:
        return _parse_detail_bs4(xml_text)

    for xml_label, csv_col in DETAIL_FIELD_MAP.items():
        result[csv_col] = _detail_value(tree, xml_label)

    periods = [_detail_value(tree, lbl) for lbl in HIRING_PERIOD_LABELS if _detail_value(tree, lbl)]
    result["hiring_period"] = "; ".join(periods)

    for xml_label, csv_col in LANGUAGE_MAP.items():
        result[csv_col] = _detail_value(tree, xml_label)

    masters: list[str] = []
    for el in tree.xpath("//detail"):
        code = el.get("c_detailmodele", "")
        if (
            code.startswith("DET_STAGE_")
            and code not in DETAIL_FIELD_MAP
            and code
            not in {
                "DET_STAGE_LAB_SECTIONS",
                "DET_STAGE_LAB_INFOSCONTACT",
                "DET_STAGE_LAB_INFOSENTR",
            }
        ):
            text = etree.tostring(el, method="text", encoding="unicode").strip()
            onglet = el.get("x_onglet", "")
            if text and onglet == "Masters & Domains of activity":
                masters.append(text)
    result["related_masters"] = "; ".join(masters)
    return result


def _parse_detail_bs4(xml_text: str) -> dict[str, str]:
    """Fallback detail parser using BeautifulSoup (for malformed XML)."""
    soup = BeautifulSoup(xml_text, "html.parser")
    result: dict[str, str] = {}

    def _find(label: str) -> str:
        tag = soup.find("detail", attrs={"c_detailmodele": label})
        return tag.get_text(strip=True) if tag else ""

    for xml_label, csv_col in DETAIL_FIELD_MAP.items():
        result[csv_col] = _find(xml_label)
    periods = [_find(lbl) for lbl in HIRING_PERIOD_LABELS if _find(lbl)]
    result["hiring_period"] = "; ".join(periods)
    for xml_label, csv_col in LANGUAGE_MAP.items():
        result[csv_col] = _find(xml_label)

    masters = []
    for tag in soup.find_all("detail"):
        code = tag.get("c_detailmodele", "")
        if code.startswith("DET_STAGE_") and tag.get("x_onglet") == "Masters & Domains of activity":
            text = tag.get_text(strip=True)
            if text:
                masters.append(text)
    result["related_masters"] = "; ".join(masters)
    return result


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def scrape_all(
    client: httpx.AsyncClient,
    faculty: str = "ic",
    on_progress: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Fetch listing then detail pages concurrently and merge results."""
    cell_id = FACULTY_CELLS.get(faculty)
    if not cell_id:
        msg = f"Unknown faculty: {faculty!r}. Available: {list(FACULTY_CELLS)}"
        raise ValueError(msg)

    listing_url = f"{BASE_URL}/!PORTAL14S.portalCell?ww_k_cell={cell_id}"
    listing_xml = await _fetch_page(client, listing_url)
    rows = parse_listing(listing_xml)

    if not rows:
        return []

    total = len(rows)
    results: list[dict[str, Any]] = [{}] * total  # pre-allocate for ordered results
    sem = asyncio.Semaphore(CONCURRENCY)
    done = 0

    async def _fetch_detail(idx: int, row: dict[str, Any]) -> None:
        nonlocal done
        async with sem:
            row_id = row["row_id"]
            detail_url = DETAIL_URL_TEMPLATE.format(row_id=row_id)
            try:
                detail_xml = await _fetch_page(client, detail_url)
                detail_fields = parse_detail(detail_xml)
            except (httpx.HTTPStatusError, httpx.ReadTimeout):
                detail_fields = {}
            results[idx] = {**row, **detail_fields}
            await asyncio.sleep(REQUEST_DELAY)
            done += 1
            if on_progress:
                on_progress(done, total)

    await asyncio.gather(*[_fetch_detail(i, row) for i, row in enumerate(rows)])
    return results
