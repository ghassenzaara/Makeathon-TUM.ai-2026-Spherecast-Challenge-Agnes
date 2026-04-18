"""
Supplier Scraper -- enriches supplier records with certifications and location.

Primary path: Tavily Search API (real web lookup of official supplier pages).
Fallback:     GPT-4o inference when Tavily is unavailable or returns no content.

Results are cached in data/enrichment_cache/suppliers/.
"""

import asyncio
import json
import logging
import re

from backend.config import OPENAI_API_KEY, OPENAI_CHAT_MODEL, TAVILY_API_KEY
from backend.db.queries import get_all_suppliers
from backend.phase2_enrichment.enrichment_store import (
    cache_get,
    cache_set,
    store_supplier_info,
)

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

# LLM prompt kept as last-resort fallback (not deleted)
SUPPLIER_INFERENCE_PROMPT = """You are a CPG supply chain expert with deep knowledge of ingredient suppliers.

Given this supplier name, provide structured information based on your knowledge:

Supplier: {supplier_name}

Respond in JSON format:
{{
    "name": "{supplier_name}",
    "headquarters": "City, State/Province, Country",
    "region": "North America" | "Europe" | "Asia" | "Other",
    "certifications": ["list of likely certifications they hold"],
    "specialties": ["what ingredient categories they specialize in"],
    "company_size": "large" | "medium" | "small" | "unknown",
    "website": "likely website URL",
    "notes": "any relevant notes about this supplier",
    "confidence": 50
}}

For certifications, consider common ones like:
- ISO 9001, ISO 22000, ISO 14001
- FSSC 22000
- GMP / cGMP
- USDA Organic
- Non-GMO Project Verified
- Kosher, Halal
- NSF International
- SQF (Safe Quality Food)

Be conservative -- only include certifications you are fairly confident about.
Set confidence between 30-70 based on how well you know this company.
Major well-known companies should be higher confidence."""


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

        # HQ: look for "headquartered in", "based in", "located in" patterns
        hq = ""
        hq_match = re.search(
            r"(?:headquartered|based|located)\s+in\s+([A-Z][A-Za-z ,]{5,50}?)(?:\.|,|\s+and)",
            combined_text,
        )
        if hq_match:
            hq = hq_match.group(1).strip().rstrip(",")

        # Certifications
        found_certs = []
        text_lower = combined_text.lower()
        for cert in _CERT_KEYWORDS:
            if cert.lower() in text_lower and cert not in found_certs:
                found_certs.append(cert)

        # Website: first result URL
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
      3. LLM inference (fallback)

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

    result = {
        "supplier_id": supplier_id,
        "name": supplier_name,
        "headquarters": known_location or "",
        "region": "",
        "certifications": [],
        "specialties": [],
        "company_size": "unknown",
        "website": "",
        "notes": "",
        "confidence": 20,
        "source": "none",
    }

    # Primary: Tavily
    tavily_data = await _tavily_enrich_supplier(supplier_name)
    if tavily_data:
        result["headquarters"] = known_location or tavily_data.get("headquarters", "")
        result["certifications"] = tavily_data.get("certifications", [])
        result["website"] = tavily_data.get("website", "")
        result["confidence"] = tavily_data["confidence"]
        result["source"] = "tavily_search"
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

    # Fallback: LLM
    if not OPENAI_API_KEY:
        logger.warning(f"  Supplier {supplier_name}: no API key, skipping enrichment")
        cache_set("suppliers", str(supplier_id), result)
        return result

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    try:
        prompt = SUPPLIER_INFERENCE_PROMPT.format(supplier_name=supplier_name)
        response = await client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        inferred = json.loads(response.choices[0].message.content)

        result["headquarters"] = known_location or inferred.get("headquarters", "")
        result["region"] = inferred.get("region", "")
        result["certifications"] = inferred.get("certifications", [])
        result["specialties"] = inferred.get("specialties", [])
        result["company_size"] = inferred.get("company_size", "unknown")
        result["website"] = inferred.get("website", "")
        result["notes"] = inferred.get("notes", "")
        result["confidence"] = inferred.get("confidence", 40)
        result["source"] = "llm_inference"

        logger.info(
            f"  Supplier {supplier_name}: LLM fallback - "
            f"{len(result['certifications'])} certs, hq={result['headquarters']}"
        )

    except Exception as e:
        logger.error(f"  Supplier {supplier_name}: enrichment failed - {e}")
        result["notes"] = f"Enrichment failed: {e}"

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
