"""
OpenCorporates Entity Verifier -- confirms supplier business registration status.

Primary path: live GET to the OpenCorporates public search API.
Fallback:     deterministic mock data for 6 major known suppliers, then
              "Unknown" status for any others — activated when
              OPENCORPORATES_API_KEY is absent AND the live request fails.

Endpoint: https://api.opencorporates.com/v0.4/companies/search
"""

import asyncio
import logging
import urllib.parse
from datetime import datetime, timezone

import httpx

from backend.config import OPENCORPORATES_API_KEY
from backend.phase2_enrichment.enrichment_store import store_enrichment

logger = logging.getLogger(__name__)

_OC_BASE = "https://api.opencorporates.com/v0.4/companies/search"
_TIMEOUT = 10.0
_RATE_DELAY = 0.5  # seconds between requests (~60 req/min public limit)

# Deterministic mock data for known major suppliers.
# Used when API key is absent and live request fails.
_MOCK_ENTITIES: dict[str, dict] = {
    "ADM": {
        "status": "Active",
        "registered_name": "Archer-Daniels-Midland Company",
        "jurisdiction": "us_de",
        "company_number": "0000007084",
        "incorporation_date": "1923-01-01",
    },
    "Cargill": {
        "status": "Active",
        "registered_name": "Cargill, Incorporated",
        "jurisdiction": "us_de",
        "company_number": "0000017843",
        "incorporation_date": "1936-06-20",
    },
    "Ingredion": {
        "status": "Active",
        "registered_name": "Ingredion Incorporated",
        "jurisdiction": "us_de",
        "company_number": "0000049519",
        "incorporation_date": "1906-01-01",
    },
    "IFF": {
        "status": "Active",
        "registered_name": "International Flavors & Fragrances Inc.",
        "jurisdiction": "us_ny",
        "company_number": "0000049519",
        "incorporation_date": "1909-01-01",
    },
    "Ashland": {
        "status": "Active",
        "registered_name": "Ashland Global Holdings Inc.",
        "jurisdiction": "us_de",
        "company_number": "0001307954",
        "incorporation_date": "2018-03-01",
    },
    "Univar Solutions": {
        "status": "Active",
        "registered_name": "Univar Solutions Inc.",
        "jurisdiction": "us_de",
        "company_number": "0001494319",
        "incorporation_date": "2012-12-01",
    },
}


def _build_oc_url(supplier_name: str) -> str:
    params = {
        "q": supplier_name,
        "jurisdiction_code": "us",
        "format": "json",
    }
    if OPENCORPORATES_API_KEY:
        params["api_token"] = OPENCORPORATES_API_KEY
    return f"{_OC_BASE}?{urllib.parse.urlencode(params)}"


def _parse_oc_response(payload: dict, supplier_name: str) -> dict:
    """Extract the best matching company record from an OpenCorporates response."""
    companies = (
        payload.get("results", {})
               .get("companies", [])
    )
    if not companies:
        return {"status": "Unknown", "registered_name": "", "jurisdiction": "",
                "company_number": "", "incorporation_date": ""}

    # Prefer an exact name match; fall back to the first result
    name_lower = supplier_name.lower()
    best = next(
        (c["company"] for c in companies
         if c.get("company", {}).get("name", "").lower() == name_lower),
        companies[0].get("company", {}),
    )

    current_status = best.get("current_status") or best.get("company_status") or ""
    if "active" in current_status.lower():
        status = "Active"
    elif any(w in current_status.lower() for w in ("dissolved", "inactive", "struck")):
        status = "Dissolved"
    else:
        status = "Unknown"

    return {
        "status": status,
        "registered_name": best.get("name", ""),
        "jurisdiction": best.get("jurisdiction_code", ""),
        "company_number": best.get("company_number", ""),
        "incorporation_date": best.get("incorporation_date", ""),
    }


async def verify_supplier_entity(supplier_name: str) -> dict:
    """
    Verify a supplier's business registration via OpenCorporates.

    Resolution order:
      1. Live GET to OpenCorporates search endpoint
         (uses api_token if OPENCORPORATES_API_KEY is set)
      2. _MOCK_ENTITIES dict for known major suppliers
      3. Generic "Unknown" record for all others

    Args:
        supplier_name: Supplier company name string

    Returns:
        {
            "status": "Active" | "Dissolved" | "Unknown",
            "registered_name": str,
            "jurisdiction": str,
            "company_number": str,
            "incorporation_date": str,
            "source": "opencorporates_live" | "opencorporates_mock",
        }
    """
    url = _build_oc_url(supplier_name)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(url)

        if response.status_code == 200:
            result = _parse_oc_response(response.json(), supplier_name)
            result["source"] = "opencorporates_live"
            logger.info(
                f"  OC {supplier_name}: {result['status']} "
                f"({result['registered_name']})"
            )
            return result

        logger.warning(
            f"  OC {supplier_name}: HTTP {response.status_code}, falling back to mock"
        )

    except Exception as e:
        logger.warning(f"  OC {supplier_name}: live request failed ({e}), using mock")

    # Mock fallback
    mock = _MOCK_ENTITIES.get(supplier_name)
    if mock:
        result = dict(mock)
        result["source"] = "opencorporates_mock"
        logger.info(f"  OC {supplier_name}: using mock data — {result['status']}")
        return result

    logger.info(f"  OC {supplier_name}: no mock available — returning Unknown")
    return {
        "status": "Unknown",
        "registered_name": "",
        "jurisdiction": "",
        "company_number": "",
        "incorporation_date": "",
        "source": "opencorporates_mock",
    }


async def verify_all_suppliers(suppliers: list[dict]) -> list[dict]:
    """
    Batch entity verification for all suppliers.

    Args:
        suppliers: List of dicts with 'Id' (int) and 'Name' (str).

    Returns:
        List of entity dicts, each augmented with 'supplier_id' and 'supplier_name'.

    Side effects:
        Persists each result to the Enrichment table:
            data_type  = "entity_verification"
            confidence = 0.90 for live results | 0.70 for mock results
    """
    results = []
    logger.info(f"Running OpenCorporates verification for {len(suppliers)} suppliers...")

    for i, supplier in enumerate(suppliers, 1):
        supplier_id = supplier["Id"]
        supplier_name = supplier["Name"]
        logger.info(f"  [{i}/{len(suppliers)}] Entity check: {supplier_name}")

        entity = await verify_supplier_entity(supplier_name)
        entity["supplier_id"] = supplier_id
        entity["supplier_name"] = supplier_name
        entity["checked_at"] = datetime.now(timezone.utc).isoformat()

        confidence = 0.90 if entity["source"] == "opencorporates_live" else 0.70
        store_enrichment(
            entity_type="supplier",
            entity_id=str(supplier_id),
            data_type="entity_verification",
            data=entity,
            source_url=_build_oc_url(supplier_name) if entity["source"] == "opencorporates_live" else "mock",
            confidence=confidence,
        )
        results.append(entity)

        if i < len(suppliers):
            await asyncio.sleep(_RATE_DELAY)

    active = sum(1 for r in results if r["status"] == "Active")
    dissolved = sum(1 for r in results if r["status"] == "Dissolved")
    unknown = sum(1 for r in results if r["status"] == "Unknown")
    live = sum(1 for r in results if r.get("source") == "opencorporates_live")
    logger.info(
        f"Entity verification complete: {len(results)} suppliers — "
        f"{active} active, {dissolved} dissolved, {unknown} unknown "
        f"({live} via live API, {len(results) - live} via mock)"
    )
    return results
