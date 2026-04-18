"""
Supplier Scraper -- enriches supplier records with certifications and location.

Uses the structured_extractor for uniform LLM-based extraction and records
every field with Evidence rows. Falls back to group priors when possible.

Results are cached in data/enrichment_cache/suppliers/.
"""

import asyncio
import json
import logging

from backend.config import OPENAI_API_KEY, OPENAI_CHAT_MODEL
from backend.db.queries import get_all_suppliers
from backend.db.evidence import record_evidence
from backend.phase2_enrichment.enrichment_store import (
    cache_get,
    cache_set,
    store_supplier_info,
)
from backend.phase2_enrichment.structured_extractor import extract_supplier_from_text

logger = logging.getLogger(__name__)

# Known supplier locations (hardcoded for speed; LLM fills the rest)
_KNOWN_LOCATIONS = {
    "ADM": "Chicago, IL, USA",
    "Cargill": "Minneapolis, MN, USA",
    "Ingredion": "Westchester, IL, USA",
    "IFF": "New York, NY, USA",
    "Ashland": "Wilmington, DE, USA",
    "Univar Solutions": "Downers Grove, IL, USA",
}


async def enrich_supplier(supplier_id: int, supplier_name: str) -> dict:
    """
    Enrich a single supplier with inferred certifications and location.

    Args:
        supplier_id: DB supplier ID
        supplier_name: Supplier company name

    Returns:
        Dict with enriched supplier data
    """
    # Check cache
    cached = cache_get("suppliers", str(supplier_id))
    if cached:
        logger.info(f"  Supplier {supplier_name}: loaded from cache")
        store_supplier_info(
            supplier_id=supplier_id,
            data=cached,
            source_url=cached.get("website", ""),
        )
        return cached

    # Use hardcoded location if available
    known_location = _KNOWN_LOCATIONS.get(supplier_name)

    # Use structured extractor (LLM-based, with evidence recording)
    result = await extract_supplier_from_text(
        text="",  # No page text — uses LLM knowledge
        supplier_name=supplier_name,
        supplier_id=supplier_id,
        source_url="",
    )

    # Override with known data
    if known_location:
        result["headquarters"] = known_location

    result["supplier_id"] = supplier_id
    result["name"] = supplier_name
    result["source"] = "llm_inference"

    logger.info(
        f"  Supplier {supplier_name}: inferred "
        f"{len(result.get('certifications', []))} certs, "
        f"location={result.get('headquarters', 'unknown')}"
    )

    # Cache and store
    cache_set("suppliers", str(supplier_id), result)
    store_supplier_info(
        supplier_id=supplier_id,
        data=result,
        source_url=result.get("website", ""),
    )
    return result


async def enrich_all_suppliers() -> list[dict]:
    """
    Enrich all 40 suppliers with inferred data.

    Returns:
        List of enriched supplier data dicts.
    """
    suppliers = get_all_suppliers()
    logger.info(f"Enriching {len(suppliers)} suppliers...")

    results = []
    for i, supplier in enumerate(suppliers, 1):
        logger.info(
            f"  [{i}/{len(suppliers)}] Enriching supplier: {supplier['Name']}"
        )
        data = await enrich_supplier(supplier["Id"], supplier["Name"])
        results.append(data)

        # Small delay to avoid rate limits
        if i < len(suppliers):
            await asyncio.sleep(0.3)

    # Summary
    total_certs = sum(len(r.get("certifications", [])) for r in results)
    with_location = sum(1 for r in results if r.get("headquarters"))
    logger.info(
        f"Supplier enrichment complete: {len(results)} suppliers, "
        f"{total_certs} total certifications, {with_location} with locations"
    )
    return results
