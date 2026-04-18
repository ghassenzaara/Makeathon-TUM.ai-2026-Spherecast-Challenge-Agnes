"""
iHerb Product Scraper -- extracts certifications, ingredients, and pricing.

Scrapes iHerb product pages for finished goods with FG-iherb-{id} SKUs.
Falls back to:
  1. Structured LLM extraction (if page is parseable but messy)
  2. Group priors (if 403/blocked — uses sibling products' data)
  3. LLM inference with low confidence (last resort)

Rate-limited to 1 request/second. Results cached in data/enrichment_cache/iherb/.
Every extracted field emits an Evidence row.
"""

import asyncio
import json
import logging
import re

import httpx
from bs4 import BeautifulSoup

from backend.config import SCRAPE_DELAY_SECONDS, OPENAI_API_KEY, OPENAI_CHAT_MODEL
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

# Common certification keywords to look for on product pages
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

# Headers to mimic a real browser
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


async def scrape_iherb_product(iherb_id: str, product_id: int = 0) -> dict:
    """
    Scrape an iHerb product page and extract structured info.

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

    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, follow_redirects=True, timeout=15.0
        ) as client:
            response = await client.get(url)

            if response.status_code == 403:
                logger.warning(f"  iHerb {iherb_id}: 403 blocked — using group priors")
                result = apply_group_priors_to_scrape(result, product_id)
                result["_source"] = "group-prior-403"
                if not result.get("certifications"):
                    result = await _llm_fallback_iherb(iherb_id, result)
                cache_set("iherb", iherb_id, result)
                return result

            if response.status_code != 200:
                logger.warning(
                    f"  iHerb {iherb_id}: HTTP {response.status_code}"
                )
                result = await _llm_fallback_iherb(iherb_id, result)
                cache_set("iherb", iherb_id, result)
                return result

            # Try structured extraction first for better quality
            raw_html = response.text
            structured = await extract_product_from_html(
                raw_html, url, product_id,
                context_hints="iHerb supplement product page",
            )

            if structured.get("confidence", 0) > 30:
                # Use structured extraction result
                result.update({
                    "title": structured.get("title", ""),
                    "brand": structured.get("brand", ""),
                    "description": structured.get("description", ""),
                    "certifications": structured.get("certifications", []),
                    "ingredients_text": structured.get("ingredients_text", ""),
                    "allergens": structured.get("allergens", []),
                    "price_usd": structured.get("price_usd"),
                    "scrape_success": True,
                    "_source": "structured-extractor",
                })
            else:
                # Fall back to classic parsing
                soup = BeautifulSoup(raw_html, "html.parser")
                result = _parse_iherb_page(soup, result)
                result["scrape_success"] = True
                result["_source"] = "html-parser"

            logger.info(
                f"  iHerb {iherb_id}: scraped OK - "
                f"{result['title'][:50]}... | "
                f"{len(result['certifications'])} certs"
            )

    except Exception as e:
        logger.warning(f"  iHerb {iherb_id}: scrape failed - {e}")
        result = apply_group_priors_to_scrape(result, product_id)
        if not result.get("certifications"):
            result = await _llm_fallback_iherb(iherb_id, result)

    # Cache and return
    cache_set("iherb", iherb_id, result)
    return result


def _parse_iherb_page(soup: BeautifulSoup, result: dict) -> dict:
    """Extract structured data from an iHerb product page."""

    # Title
    title_el = soup.select_one("h1") or soup.select_one("[itemprop='name']")
    if title_el:
        result["title"] = title_el.get_text(strip=True)

    # Brand
    brand_el = (
        soup.select_one("[itemprop='brand']")
        or soup.select_one(".brand-name")
        or soup.select_one("span.brand a")
    )
    if brand_el:
        result["brand"] = brand_el.get_text(strip=True)

    # Description
    desc_el = (
        soup.select_one("[itemprop='description']")
        or soup.select_one("#product-summary-description")
        or soup.select_one(".product-overview")
    )
    if desc_el:
        result["description"] = desc_el.get_text(strip=True)[:1000]

    # Price
    price_el = (
        soup.select_one("[itemprop='price']")
        or soup.select_one(".price")
        or soup.select_one("#price")
    )
    if price_el:
        price_text = price_el.get_text(strip=True)
        price_match = re.search(r"\$?([\d,.]+)", price_text)
        if price_match:
            try:
                result["price_usd"] = float(
                    price_match.group(1).replace(",", "")
                )
            except ValueError:
                pass

    # Ingredients
    ingredients_el = (
        soup.select_one("#supplement-facts")
        or soup.select_one(".supplement-facts")
        or soup.select_one("[class*='ingredient']")
    )
    if ingredients_el:
        result["ingredients_text"] = ingredients_el.get_text(
            separator=", ", strip=True
        )[:2000]

    # Certifications -- scan the entire page text
    page_text = soup.get_text()
    found_certs = set()
    for cert in CERTIFICATION_KEYWORDS:
        if cert.lower() in page_text.lower():
            found_certs.add(cert)

    # Also look for certification badges/icons
    cert_images = soup.select("img[alt*='Certified'], img[alt*='Organic'], "
                               "img[alt*='Non-GMO'], img[alt*='Kosher'], "
                               "img[alt*='Vegan'], img[alt*='GMP']")
    for img in cert_images:
        alt = img.get("alt", "")
        if alt:
            found_certs.add(alt.strip())

    result["certifications"] = sorted(found_certs)

    return result


async def _llm_fallback_iherb(iherb_id: str, result: dict) -> dict:
    """
    Use LLM to infer likely certifications when scraping fails.
    """
    if not OPENAI_API_KEY:
        logger.warning(f"  iHerb {iherb_id}: no API key for LLM fallback")
        result["certifications"] = []
        result["_inference_note"] = "Scraping failed and no API key for LLM fallback"
        return result

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""You are a supplement industry analyst. An iHerb product page at
https://www.iherb.com/pr/p/{iherb_id} could not be scraped.

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
        result["_inference_note"] = "Data inferred by LLM (scraping failed)"
        result["_inference_confidence"] = inferred.get("confidence", 25)
        result["_source"] = "llm-fallback"
        logger.info(
            f"  iHerb {iherb_id}: LLM fallback - "
            f"inferred {len(result['certifications'])} certs"
        )
    except Exception as e:
        logger.error(f"  iHerb {iherb_id}: LLM fallback also failed - {e}")
        result["_inference_note"] = f"Both scraping and LLM failed: {e}"

    return result


async def scrape_all_iherb_products(
    product_rows: list[dict],
) -> list[dict]:
    """
    Scrape all iHerb finished goods.

    Args:
        product_rows: List of dicts with 'Id' and 'SKU' from the Product table.

    Returns:
        List of scraped/inferred product info dicts.
    """
    results = []

    # Filter to iHerb products only
    iherb_products = []
    for p in product_rows:
        parsed = parse_sku(p["SKU"])
        if parsed.retailer == "iherb" and parsed.retailer_product_id:
            iherb_products.append({
                "product_id": p["Id"],
                "iherb_id": parsed.retailer_product_id,
                "sku": p["SKU"],
            })

    logger.info(f"Scraping {len(iherb_products)} iHerb products...")

    for i, product in enumerate(iherb_products, 1):
        logger.info(
            f"  [{i}/{len(iherb_products)}] Scraping iHerb ID {product['iherb_id']}..."
        )
        data = await scrape_iherb_product(
            product["iherb_id"],
            product_id=product["product_id"],
        )
        data["product_id"] = product["product_id"]
        data["sku"] = product["sku"]

        # Store in DB
        store_product_scrape(
            product_id=product["product_id"],
            data=data,
            source_url=data["url"],
        )
        results.append(data)

        # Rate limit
        if i < len(iherb_products):
            await asyncio.sleep(SCRAPE_DELAY_SECONDS)

    logger.info(
        f"iHerb scraping complete: {len(results)} products, "
        f"{sum(1 for r in results if r.get('scrape_success'))} scraped OK, "
        f"{sum(1 for r in results if not r.get('scrape_success'))} used fallback"
    )
    return results
