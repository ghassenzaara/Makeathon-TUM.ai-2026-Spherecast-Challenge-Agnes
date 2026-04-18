"""
Supplier Scraper -- enriches supplier records with certifications and location.

Resolution order:
  1. File cache
  2. Tavily Search API (primary — real web lookup of official supplier pages)
  3. Structured LLM extraction via extract_supplier_from_text (fallback, with evidence recording)

Results are cached in data/enrichment_cache/suppliers/.
"""

import asyncio
import logging
import re

from backend.config import TAVILY_API_KEY
from backend.db.queries import get_all_suppliers
from backend.phase2_enrichment.enrichment_store import (
    cache_get,
    cache_set,
    store_supplier_info,
)
from backend.phase2_enrichment.structured_extractor import extract_supplier_from_text

logger = logging.getLogger(__name__)

# Known supplier locations (hardcoded ground-truth; avoids a lookup for the big six)
_KNOWN_LOCATIONS = {
    "ADM": "Chicago, IL, USA",
    "Cargill": "Minneapolis, MN, USA",
    "Ingredion": "Westchester, IL, USA",
    "IFF": "New York, NY, USA",
    "Ashland": "Wilmington, DE, USA",
    "Univar Solutions": "Downers Grove, IL, USA",
}

# Certification keywords to recognise in Tavily content
_CERT_KEYWORDS = [
    "ISO 9001", "ISO 22000", "ISO 14001", "ISO 45001",
    "FSSC 22000", "FSSC22000",
    "GMP", "cGMP",
    "USDA Organic", "Organic",
    "Non-GMO Project Verified", "Non-GMO",
    "Kosher", "Halal",
    "NSF International", "NSF",
    "SQF", "HACCP",
    "BRC", "GFSI",
    "Rainforest Alliance",
]


async def _tavily_enrich_supplier(supplier_name: str) -> dict | None:
    """
    Queries Tavily for real supplier HQ and certification data.

    Returns a partial enrichment dict on success, None on failure.
    Confidence is fixed at 72 for Tavily-sourced data (real web, not hallucinated).
    """
    if not TAVILY_API_KEY:
        logger.debug(f"  Supplier {supplier_name}: TAVILY_API_KEY not set")
        return None

    try:
        from tavily import AsyncTavilyClient
        client = AsyncTavilyClient(api_key=TAVILY_API_KEY)
        response = await client.search(
            query=(
                f"What are the headquarters and official compliance certifications "
                f"(ISO, GMP, etc.) for the supplier {supplier_name}?"
            ),
            search_depth="advanced",
            max_results=5,
        )
        results = response.get("results", [])
        if not results:
            logger.debug(f"  Supplier {supplier_name}: Tavily returned no results")
            return None

        combined_text = " ".join(
            r.get("content", "") + " " + r.get("raw_content", "")
            for r in results
        )

        hq = ""
        hq_match = re.search(
            r"(?:headquartered|based|located)\s+in\s+([A-Z][A-Za-z ,]{5,50}?)(?:\.|,|\s+and)",
            combined_text,
        )
        if hq_match:
            hq = hq_match.group(1).strip().rstrip(",")

        found_certs = []
        text_lower = combined_text.lower()
        for cert in _CERT_KEYWORDS:
            if cert.lower() in text_lower and cert not in found_certs:
                found_certs.append(cert)

        website = results[0].get("url", "") if results else ""

        return {
            "headquarters": hq,
            "certifications": found_certs,
            "website": website,
            "confidence": 72,
            "source": "tavily_search",
        }

    except Exception as e:
        logger.warning(f"  Supplier {supplier_name}: Tavily enrichment failed - {e}")
        return None


async def enrich_supplier(supplier_id: int, supplier_name: str) -> dict:
    """
    Enrich a single supplier with certifications, HQ, and metadata.

    Resolution order:
      1. File cache
      2. Tavily Search API (primary)
      3. Structured LLM extraction via extract_supplier_from_text (fallback)

    Args:
        supplier_id:   DB supplier ID
        supplier_name: Supplier company name

    Returns:
        Dict with enriched supplier data
    """
    cached = cache_get("suppliers", str(supplier_id))
    if cached:
        logger.info(f"  Supplier {supplier_name}: loaded from cache")
        store_supplier_info(
            supplier_id=supplier_id,
            data=cached,
            source_url=cached.get("website", ""),
        )
        return cached

    known_location = _KNOWN_LOCATIONS.get(supplier_name)

    # Primary: Tavily (real web data, confidence=72)
    tavily_data = await _tavily_enrich_supplier(supplier_name)
    if tavily_data:
        result = {
            "supplier_id": supplier_id,
            "name": supplier_name,
            "headquarters": known_location or tavily_data.get("headquarters", ""),
            "region": "",
            "certifications": tavily_data.get("certifications", []),
            "specialties": [],
            "company_size": "unknown",
            "website": tavily_data.get("website", ""),
            "notes": "",
            "confidence": tavily_data["confidence"],
            "source": "tavily_search",
        }
        logger.info(
            f"  Supplier {supplier_name}: Tavily OK - "
            f"{len(result['certifications'])} certs, hq={result['headquarters']}"
        )
        cache_set("suppliers", str(supplier_id), result)
        store_supplier_info(
            supplier_id=supplier_id,
            data=result,
            source_url=result["website"],
        )
        return result

    # Fallback: structured LLM extraction (with evidence recording)
    logger.info(f"  Supplier {supplier_name}: Tavily failed — using LLM structured extractor")
    result = await extract_supplier_from_text(
        text="",
        supplier_name=supplier_name,
        supplier_id=supplier_id,
        source_url="",
    )

    if known_location:
        result["headquarters"] = known_location

    result["supplier_id"] = supplier_id
    result["name"] = supplier_name
    result.setdefault("source", "llm_inference")

    logger.info(
        f"  Supplier {supplier_name}: LLM fallback - "
        f"{len(result.get('certifications', []))} certs, "
        f"location={result.get('headquarters', 'unknown')}"
    )

    cache_set("suppliers", str(supplier_id), result)
    store_supplier_info(
        supplier_id=supplier_id,
        data=result,
        source_url=result.get("website", ""),
    )
    return result


async def enrich_all_suppliers() -> list[dict]:
    """
    Enrich all suppliers with certifications and HQ data.

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

        if i < len(suppliers):
            await asyncio.sleep(0.3)

    total_certs = sum(len(r.get("certifications", [])) for r in results)
    with_location = sum(1 for r in results if r.get("headquarters"))
    tavily_count = sum(1 for r in results if r.get("source") == "tavily_search")
    logger.info(
        f"Supplier enrichment complete: {len(results)} suppliers, "
        f"{total_certs} total certifications, {with_location} with locations, "
        f"{tavily_count} via Tavily"
    )
    return results
