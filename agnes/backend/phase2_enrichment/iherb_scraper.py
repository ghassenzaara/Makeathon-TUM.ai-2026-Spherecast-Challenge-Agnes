"""
iHerb Product Scraper -- extracts certifications, ingredients, and pricing.

Primary path: Tavily Search API (targeted query against iherb.com).
Fallbacks:
  1. Group priors (uses sibling products' data when available)
  2. LLM inference with low confidence (last resort)

Results cached in data/enrichment_cache/iherb/.
"""

import asyncio
import json
import logging
import re

from backend.config import (
    SCRAPE_DELAY_SECONDS,
    OPENAI_API_KEY,
    OPENAI_CHAT_MODEL,
    TAVILY_API_KEY,
)
from backend.db.evidence import record_evidence
from backend.phase1_extraction.sku_parser import parse_sku
from backend.phase2_enrichment.enrichment_store import (
    cache_get,
    cache_set,
    store_product_scrape,
)
from backend.phase2_enrichment.group_priors import apply_group_priors_to_scrape
from backend.phase2_enrichment.structured_extractor import (
    extract_product_from_html,
    clean_html,
)

logger = logging.getLogger(__name__)

CERTIFICATION_KEYWORDS = [
    "Non-GMO", "USDA Organic", "Organic", "Kosher", "Halal",
    "Vegan", "Vegetarian", "Gluten-Free", "Gluten Free",
    "GMP Certified", "GMP", "NSF Certified", "NSF",
    "USP Verified", "USP", "Third-Party Tested",
    "Dairy-Free", "Dairy Free", "Soy-Free", "Soy Free",
    "No Artificial Colors", "No Artificial Flavors",
    "No Preservatives", "Sugar-Free", "Sugar Free",
    "Certified B Corporation", "Fair Trade",
    "cGMP", "ISO", "HACCP",
]


async def _tavily_fetch_iherb(iherb_id: str) -> dict | None:
    """
    Queries Tavily Search for iHerb product data.
    Returns raw Tavily response dict on success, None on any failure.
    """
    if not TAVILY_API_KEY:
        logger.debug(f"  iHerb {iherb_id}: TAVILY_API_KEY not set, skipping Tavily")
        return None

    try:
        from tavily import AsyncTavilyClient
        client = AsyncTavilyClient(api_key=TAVILY_API_KEY)
        response = await client.search(
            query=f"Find the product certifications and ingredients for iHerb product {iherb_id}",
            search_depth="advanced",
            include_domains=["iherb.com"],
            max_results=3,
        )
        results = response.get("results", [])
        if not results:
            logger.debug(f"  iHerb {iherb_id}: Tavily returned no results")
            return None
        return response
    except Exception as e:
        logger.warning(f"  iHerb {iherb_id}: Tavily fetch failed - {e}")
        return None


def _parse_tavily_iherb(tavily_response: dict, base_result: dict) -> dict:
    """
    Extracts certifications, ingredients, title, brand, and price from
    Tavily search results by scanning content strings for known keywords.
    """
    results = tavily_response.get("results", [])
    combined_text = " ".join(
        (r.get("content", "") + " " + r.get("raw_content", ""))
        for r in results
    )

    # Title: use first result's title
    if results and results[0].get("title"):
        base_result["title"] = results[0]["title"]

    # URL: use first result's URL
    if results and results[0].get("url"):
        base_result["url"] = results[0]["url"]

    # Brand: look for "Brand:" or "by <Word>" patterns
    brand_match = re.search(r"[Bb]rand[:\s]+([A-Z][A-Za-z0-9& ]{2,40})", combined_text)
    if brand_match:
        base_result["brand"] = brand_match.group(1).strip()

    # Price: look for dollar amounts
    price_match = re.search(r"\$\s*([\d]+\.[\d]{2})", combined_text)
    if price_match:
        try:
            base_result["price_usd"] = float(price_match.group(1))
        except ValueError:
            pass

    # Ingredients: look for "Ingredients:" or "Supplement Facts" section
    ing_match = re.search(
        r"(?:Ingredients?|Supplement Facts)[:\s]+(.{20,500}?)(?:\.|$)",
        combined_text,
        re.IGNORECASE | re.DOTALL,
    )
    if ing_match:
        base_result["ingredients_text"] = ing_match.group(1).strip()[:2000]

    # Certifications: scan for known keywords
    found_certs = set()
    text_lower = combined_text.lower()
    for cert in CERTIFICATION_KEYWORDS:
        if cert.lower() in text_lower:
            found_certs.add(cert)
    base_result["certifications"] = sorted(found_certs)

    base_result["scrape_success"] = True
    base_result["_inference_note"] = "Data sourced via Tavily Search (iherb.com)"
    return base_result


async def scrape_iherb_product(iherb_id: str, product_id: int = 0) -> dict:
    """
    Fetch structured product info for an iHerb product ID.

    Resolution order:
      1. File cache
      2. Tavily Search API (primary)
      3. LLM inference (last resort)

    Args:
        iherb_id: The iHerb product ID (e.g., '10421')
        product_id: DB product ID (for evidence recording)

    Returns:
        Dict with: iherb_id, title, brand, description, certifications,
                   ingredients_text, price_usd, url, scrape_success
    """
    # Check cache first
    cached = cache_get("iherb", iherb_id)
    if cached:
        logger.info(f"  iHerb {iherb_id}: loaded from cache")
        return cached

    url = f"https://www.iherb.com/pr/p/{iherb_id}"
    result = {
        "iherb_id": iherb_id,
        "url": url,
        "title": "",
        "brand": "",
        "description": "",
        "certifications": [],
        "ingredients_text": "",
        "allergens": [],
        "price_usd": None,
        "scrape_success": False,
    }

    # Primary: Tavily
    tavily_response = await _tavily_fetch_iherb(iherb_id)
    if tavily_response:
        result = _parse_tavily_iherb(tavily_response, result)
        logger.info(
            f"  iHerb {iherb_id}: Tavily OK - "
            f"{result['title'][:50]} | {len(result['certifications'])} certs"
        )
        cache_set("iherb", iherb_id, result)
        return result

    # Fallback: group priors then LLM
    logger.info(f"  iHerb {iherb_id}: Tavily failed — applying group priors")
    result = apply_group_priors_to_scrape(result, product_id)
    if not result.get("certifications"):
        logger.info(f"  iHerb {iherb_id}: falling back to LLM inference")
        result = await _llm_fallback_iherb(iherb_id, result)
    cache_set("iherb", iherb_id, result)
    return result


async def _llm_fallback_iherb(iherb_id: str, result: dict) -> dict:
    """Use LLM to infer likely product data when Tavily fails."""
    if not OPENAI_API_KEY:
        logger.warning(f"  iHerb {iherb_id}: no API key for LLM fallback")
        result["certifications"] = []
        result["_inference_note"] = "Both Tavily and LLM unavailable (no API keys)"
        return result

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""You are a supplement industry analyst. An iHerb product page at
https://www.iherb.com/pr/p/{iherb_id} could not be retrieved.

You only have the numeric iHerb ID. Do NOT invent specific certifications,
brand names, or ingredients. If you do not have verified knowledge about THIS
specific product, return empty arrays and set confidence low.

Respond in JSON:
{{
    "title": "<only if you are confident; else empty string>",
    "brand": "<only if you are confident; else empty string>",
    "certifications": [],
    "ingredients_text": "",
    "confidence": 15
}}

Set confidence between 5-25 since we cannot verify the page content."""

    try:
        response = await client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        inferred = json.loads(response.choices[0].message.content)
        result["title"] = inferred.get("title", "")
        result["brand"] = inferred.get("brand", "")
        result["certifications"] = inferred.get("certifications", [])
        result["ingredients_text"] = inferred.get("ingredients_text", "")
        result["_inference_note"] = "Data inferred by LLM (Tavily also failed)"
        result["_inference_confidence"] = inferred.get("confidence", 25)
        result["_source"] = "llm-fallback"
        logger.info(
            f"  iHerb {iherb_id}: LLM fallback - "
            f"inferred {len(result['certifications'])} certs"
        )
    except Exception as e:
        logger.error(f"  iHerb {iherb_id}: LLM fallback also failed - {e}")
        result["_inference_note"] = f"Both Tavily and LLM failed: {e}"

    return result


async def scrape_all_iherb_products(product_rows: list[dict]) -> list[dict]:
    """
    Scrape all iHerb finished goods.

    Args:
        product_rows: List of dicts with 'Id' and 'SKU' from the Product table.

    Returns:
        List of scraped/inferred product info dicts.
    """
    results = []

    iherb_products = []
    for p in product_rows:
        parsed = parse_sku(p["SKU"])
        if parsed.retailer == "iherb" and parsed.retailer_product_id:
            iherb_products.append({
                "product_id": p["Id"],
                "iherb_id": parsed.retailer_product_id,
                "sku": p["SKU"],
            })

    logger.info(f"Scraping {len(iherb_products)} iHerb products via Tavily...")

    for i, product in enumerate(iherb_products, 1):
        logger.info(
            f"  [{i}/{len(iherb_products)}] Fetching iHerb ID {product['iherb_id']}..."
        )
        data = await scrape_iherb_product(
            product["iherb_id"],
            product_id=product["product_id"],
        )
        data["product_id"] = product["product_id"]
        data["sku"] = product["sku"]

        store_product_scrape(
            product_id=product["product_id"],
            data=data,
            source_url=data["url"],
        )
        results.append(data)

        if i < len(iherb_products):
            await asyncio.sleep(SCRAPE_DELAY_SECONDS)

    tavily_ok = sum(1 for r in results if r.get("scrape_success"))
    logger.info(
        f"iHerb fetch complete: {len(results)} products, "
        f"{tavily_ok} via Tavily, {len(results) - tavily_ok} used LLM fallback"
    )
    return results
