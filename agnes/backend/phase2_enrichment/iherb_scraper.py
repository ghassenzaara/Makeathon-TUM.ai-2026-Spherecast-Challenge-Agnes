"""
iHerb Product Scraper -- extracts certifications, ingredients, and pricing.

Resolution order:
  1. File cache
  2. Tavily Search API (primary — targeted query against iherb.com)
  3. Group priors (if Tavily fails — uses sibling products' data)
  4. LLM inference with low confidence (last resort)

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
from backend.phase1_extraction.sku_parser import parse_sku
from backend.phase2_enrichment.enrichment_store import (
    cache_get,
    cache_set,
    store_product_scrape,
)
from backend.phase2_enrichment.group_priors import apply_group_priors_to_scrape

logger = logging.getLogger(__name__)

# Canonical certification vocabulary the LLM is guided to emit. It is a hint,
# not a hard filter — the LLM may emit other certifications from the prose.
CERTIFICATION_VOCABULARY = [
    "Non-GMO", "USDA Organic", "Organic", "Kosher", "Halal",
    "Vegan", "Vegetarian", "Gluten-Free",
    "GMP Certified", "NSF Certified", "USP Verified", "Third-Party Tested",
    "Dairy-Free", "Soy-Free",
    "No Artificial Colors", "No Artificial Flavors",
    "No Preservatives", "Sugar-Free",
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


async def _parse_tavily_iherb(tavily_response: dict, base_result: dict) -> dict:
    """
    Context-aware extraction of certifications, ingredients, title, brand, and
    price from Tavily search results.

    Rather than relying on brittle regex + keyword presence (which mis-classifies
    negations like "no gluten-free claim" as "Gluten-Free"), this asks an LLM to
    read the prose and emit a structured JSON record. The certification list is
    treated as semantic evidence — the LLM only includes a cert if the text
    actually asserts the product carries it.

    Falls back to the legacy regex path only if no OpenAI key is configured.
    """
    results = tavily_response.get("results", [])
    combined_text = " ".join(
        (r.get("content", "") + " " + r.get("raw_content", ""))
        for r in results
    ).strip()

    # Always prefer the first result's title/url as metadata.
    if results and results[0].get("title"):
        base_result["title"] = results[0]["title"]
    if results and results[0].get("url"):
        base_result["url"] = results[0]["url"]

    if not combined_text:
        base_result["certifications"] = []
        base_result["scrape_success"] = False
        base_result["_inference_note"] = "Tavily returned empty content"
        return base_result

    # Trim text to stay within a reasonable prompt budget while keeping
    # enough prose for context-aware claim extraction.
    prose = combined_text[:8000]

    if OPENAI_API_KEY:
        try:
            parsed = await _llm_extract_product_fields(prose)
            if parsed.get("title") and not base_result.get("title"):
                base_result["title"] = parsed["title"]
            if parsed.get("brand"):
                base_result["brand"] = parsed["brand"]
            if parsed.get("price_usd") is not None:
                try:
                    base_result["price_usd"] = float(parsed["price_usd"])
                except (TypeError, ValueError):
                    pass
            if parsed.get("ingredients_text"):
                base_result["ingredients_text"] = str(
                    parsed["ingredients_text"]
                )[:2000]
            certs = parsed.get("certifications") or []
            if isinstance(certs, list):
                base_result["certifications"] = sorted(
                    {str(c).strip() for c in certs if str(c).strip()}
                )
            else:
                base_result["certifications"] = []
            base_result["scrape_success"] = True
            base_result["_inference_note"] = (
                "Data sourced via Tavily Search (iherb.com), parsed by LLM "
                "with context-aware extraction"
            )
            base_result["_source"] = "tavily_search"
            return base_result
        except Exception as e:
            logger.warning(
                f"  iHerb parse: LLM extraction failed ({e}); "
                "falling back to regex parser"
            )

    # Regex fallback (only when no key, or LLM failed).
    return _parse_tavily_iherb_regex(combined_text, base_result)


async def _llm_extract_product_fields(prose: str) -> dict:
    """
    Ask the LLM to pull out structured product fields from Tavily prose.

    The prompt explicitly instructs the model to reject negated claims and
    unrelated brand mentions — the whole point of the context-aware upgrade.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    cert_hint = ", ".join(CERTIFICATION_VOCABULARY)

    system_msg = (
        "You are a strict supplement-industry data extractor. "
        "Given web-search snippets about a SINGLE iHerb product, return one "
        "JSON object with the product's attributes. "
        "Only assert a certification if the prose CLAIMS the product carries "
        "it. Reject negations (e.g. 'no gluten-free claim', 'not kosher', "
        "'does not contain organic'), comparisons ('unlike organic brands'), "
        "and unrelated mentions. If a field is not stated, leave it empty / "
        "null. Never invent a brand or price."
    )

    user_msg = f"""Extract the following fields from the iHerb search snippets below.
Respond ONLY with a JSON object of this exact shape (no markdown):

{{
  "title": "<product title as advertised, or empty string>",
  "brand": "<brand name, or empty string>",
  "price_usd": <number in USD or null>,
  "ingredients_text": "<ingredients / supplement facts text, or empty string>",
  "certifications": ["<cert 1>", "<cert 2>", ...]
}}

Guidance for certifications:
- Include only certifications the product is explicitly described as having.
- Preferred canonical labels (use these spellings when the claim matches):
  {cert_hint}
- You MAY include other clearly stated certifications not in that list.
- Do NOT include a cert the text denies, qualifies away, or attributes to a
  different product/brand.

SNIPPETS:
\"\"\"
{prose}
\"\"\""""

    response = await client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def _parse_tavily_iherb_regex(combined_text: str, base_result: dict) -> dict:
    """Legacy regex-based parser; retained as a last-resort fallback only."""
    brand_match = re.search(
        r"[Bb]rand[:\s]+([A-Z][A-Za-z0-9& ]{2,40})", combined_text
    )
    if brand_match:
        base_result["brand"] = brand_match.group(1).strip()

    price_match = re.search(r"\$\s*([\d]+\.[\d]{2})", combined_text)
    if price_match:
        try:
            base_result["price_usd"] = float(price_match.group(1))
        except ValueError:
            pass

    ing_match = re.search(
        r"(?:Ingredients?|Supplement Facts)[:\s]+(.{20,500}?)(?:\.|$)",
        combined_text,
        re.IGNORECASE | re.DOTALL,
    )
    if ing_match:
        base_result["ingredients_text"] = ing_match.group(1).strip()[:2000]

    found_certs = set()
    text_lower = combined_text.lower()
    for cert in CERTIFICATION_VOCABULARY:
        if cert.lower() in text_lower:
            found_certs.add(cert)
    base_result["certifications"] = sorted(found_certs)

    base_result["scrape_success"] = True
    base_result["_inference_note"] = (
        "Data sourced via Tavily Search (iherb.com); regex fallback parser"
    )
    base_result["_source"] = "tavily_search"
    return base_result


async def scrape_iherb_product(iherb_id: str, product_id: int = 0) -> dict:
    """
    Fetch structured product info for an iHerb product ID.

    Args:
        iherb_id:   The iHerb numeric product ID (e.g. '10421')
        product_id: DB product ID (for group-prior lookups)

    Returns:
        Dict with: iherb_id, title, brand, description, certifications,
                   ingredients_text, price_usd, url, scrape_success
    """
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
        result = await _parse_tavily_iherb(tavily_response, result)
        logger.info(
            f"  iHerb {iherb_id}: Tavily OK - "
            f"{result['title'][:50]} | {len(result['certifications'])} certs"
        )
        cache_set("iherb", iherb_id, result)
        return result

    # Fallback 1: group priors (sibling products in the same ingredient group)
    logger.info(f"  iHerb {iherb_id}: Tavily failed — trying group priors")
    result = apply_group_priors_to_scrape(result, product_id)
    result["_source"] = "group-prior"

    # Fallback 2: LLM inference (last resort — low confidence)
    if not result.get("certifications"):
        logger.info(f"  iHerb {iherb_id}: no group priors — falling back to LLM")
        result = await _llm_fallback_iherb(iherb_id, result)

    cache_set("iherb", iherb_id, result)
    return result


async def _llm_fallback_iherb(iherb_id: str, result: dict) -> dict:
    """Use LLM to infer likely product data when Tavily and group priors both fail."""
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
        result["_inference_note"] = "Data inferred by LLM (Tavily and group priors also failed)"
        result["_inference_confidence"] = inferred.get("confidence", 25)
        result["_source"] = "llm-fallback"
        logger.info(
            f"  iHerb {iherb_id}: LLM fallback - "
            f"inferred {len(result['certifications'])} certs"
        )
    except Exception as e:
        logger.error(f"  iHerb {iherb_id}: LLM fallback also failed - {e}")
        result["_inference_note"] = f"All enrichment paths failed: {e}"

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
        f"{tavily_ok} via Tavily, {len(results) - tavily_ok} used group priors/LLM fallback"
    )
    return results
