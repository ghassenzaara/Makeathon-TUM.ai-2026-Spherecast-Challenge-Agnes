"""
Supplier Scraper -- enriches supplier records with certifications and location.

Uses GPT-4o to infer supplier certifications, headquarters location, and
specialties based on the supplier name and publicly known information.

For a hackathon, this is more reliable than actual web scraping (which would
require handling dozens of different website formats). The LLM has strong
prior knowledge about major ingredient suppliers.

Results are cached in data/enrichment_cache/suppliers/.
"""

import asyncio
import json
import logging

from backend.config import OPENAI_API_KEY, OPENAI_CHAT_MODEL
from backend.db.queries import get_all_suppliers
from backend.phase2_enrichment.enrichment_store import (
    cache_get,
    cache_set,
    store_supplier_info,
)

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


async def enrich_supplier(supplier_id: int, supplier_name: str) -> dict:
    """
    Enrich a single supplier with inferred certifications and location.

    Args:
        supplier_id: DB supplier ID
        supplier_name: Supplier company name

    Returns:
        Dict with enriched supplier data
    """
    # Check cache (still re-stores in DB on cache hit, in case the DB row is missing)
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
        "source": "llm_inference",
    }

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

        # Merge with result
        result["headquarters"] = known_location or inferred.get("headquarters", "")
        result["region"] = inferred.get("region", "")
        result["certifications"] = inferred.get("certifications", [])
        result["specialties"] = inferred.get("specialties", [])
        result["company_size"] = inferred.get("company_size", "unknown")
        result["website"] = inferred.get("website", "")
        result["notes"] = inferred.get("notes", "")
        result["confidence"] = inferred.get("confidence", 40)

        logger.info(
            f"  Supplier {supplier_name}: inferred "
            f"{len(result['certifications'])} certs, "
            f"location={result['headquarters']}"
        )

    except Exception as e:
        logger.error(f"  Supplier {supplier_name}: enrichment failed - {e}")
        result["notes"] = f"Enrichment failed: {e}"

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
