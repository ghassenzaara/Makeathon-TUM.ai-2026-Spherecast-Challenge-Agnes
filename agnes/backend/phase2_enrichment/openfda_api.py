"""
OpenFDA Risk Engine -- checks suppliers for FDA food enforcement history.

Queries the public OpenFDA food enforcement endpoint (no API key required).
A result count > 0 means the supplier has had at least one recall or
enforcement action on record.

Endpoint: https://api.fda.gov/food/enforcement.json
"""

import asyncio
import logging
import urllib.parse
from datetime import datetime, timezone

import httpx

from backend.phase2_enrichment.enrichment_store import store_enrichment

logger = logging.getLogger(__name__)

_FDA_BASE = "https://api.fda.gov/food/enforcement.json"
_TIMEOUT = 10.0
_RATE_DELAY = 0.25  # seconds between requests (~240 req/min public limit)


def _build_fda_url(supplier_name: str) -> str:
    encoded = urllib.parse.quote(f'"{supplier_name}"')
    return f"{_FDA_BASE}?search=recalling_firm:{encoded}&limit=5"


async def check_supplier_fda_risk(supplier_name: str) -> dict:
    """
    Query OpenFDA food enforcement endpoint for a single supplier.

    Args:
        supplier_name: Exact supplier name string (e.g. "Cargill")

    Returns:
        On results found:
            {
                "status": "Warning",
                "enforcement_count": int,
                "latest_recall": str,
                "latest_recall_date": str,
                "product_description": str,
                "classification": str,
            }
        On zero results:
            {"status": "Clear"}
        On API failure:
            {"status": "Error", "error": str}
    """
    url = _build_fda_url(supplier_name)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(url)

        if response.status_code == 404:
            # 404 from OpenFDA means zero results — this is normal
            logger.info(f"  FDA {supplier_name}: Clear (no enforcement records)")
            return {"status": "Clear"}

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "5"))
            logger.warning(f"  FDA {supplier_name}: rate limited, waiting {retry_after}s")
            await asyncio.sleep(retry_after)
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(url)

        if response.status_code != 200:
            logger.warning(f"  FDA {supplier_name}: HTTP {response.status_code}")
            return {"status": "Error", "error": f"HTTP {response.status_code}"}

        payload = response.json()
        total = payload.get("meta", {}).get("results", {}).get("total", 0)

        if total == 0:
            logger.info(f"  FDA {supplier_name}: Clear (0 enforcement records)")
            return {"status": "Clear"}

        # Extract details from first (most recent) result
        first = payload.get("results", [{}])[0]
        risk = {
            "status": "Warning",
            "enforcement_count": total,
            "latest_recall": first.get("reason_for_recall", ""),
            "latest_recall_date": first.get("report_date", ""),
            "product_description": first.get("product_description", "")[:200],
            "classification": first.get("classification", ""),
        }
        logger.warning(
            f"  FDA {supplier_name}: WARNING — {total} enforcement record(s), "
            f"latest: {risk['latest_recall'][:80]}"
        )
        return risk

    except httpx.TimeoutException:
        logger.warning(f"  FDA {supplier_name}: request timed out")
        return {"status": "Error", "error": "timeout"}
    except Exception as e:
        logger.error(f"  FDA {supplier_name}: unexpected error - {e}")
        return {"status": "Error", "error": str(e)}


async def check_all_suppliers_fda(suppliers: list[dict]) -> list[dict]:
    """
    Batch FDA enforcement check for all suppliers.

    Args:
        suppliers: List of dicts with 'Id' (int) and 'Name' (str),
                   as returned by get_all_suppliers().

    Returns:
        List of risk dicts, each augmented with 'supplier_id' and 'supplier_name'.

    Side effects:
        Persists each result to the Enrichment table with data_type="fda_risk",
        confidence=0.95 (authoritative government source).
    """
    results = []
    logger.info(f"Running OpenFDA checks for {len(suppliers)} suppliers...")

    for i, supplier in enumerate(suppliers, 1):
        supplier_id = supplier["Id"]
        supplier_name = supplier["Name"]
        logger.info(f"  [{i}/{len(suppliers)}] FDA check: {supplier_name}")

        risk = await check_supplier_fda_risk(supplier_name)
        risk["supplier_id"] = supplier_id
        risk["supplier_name"] = supplier_name
        risk["checked_at"] = datetime.now(timezone.utc).isoformat()

        store_enrichment(
            entity_type="supplier",
            entity_id=str(supplier_id),
            data_type="fda_risk",
            data=risk,
            source_url=_build_fda_url(supplier_name),
            confidence=0.95,
        )
        results.append(risk)

        if i < len(suppliers):
            await asyncio.sleep(_RATE_DELAY)

    warnings = sum(1 for r in results if r["status"] == "Warning")
    clear = sum(1 for r in results if r["status"] == "Clear")
    errors = sum(1 for r in results if r["status"] == "Error")
    logger.info(
        f"FDA checks complete: {len(results)} suppliers — "
        f"{warnings} warnings, {clear} clear, {errors} errors"
    )
    return results
