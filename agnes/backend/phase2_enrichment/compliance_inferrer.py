"""
Compliance Inferrer -- uses GPT-4o to infer compliance requirements.

Given a finished good's label claims (scraped or inferred), determines
what compliance requirements ALL raw material ingredients must satisfy.

For example:
  - If a finished good is labeled "USDA Organic" -> every ingredient
    must come from an organic-certified supplier
  - If labeled "Non-GMO" -> every ingredient must be non-GMO
  - If labeled "Kosher" -> supplier must be Kosher certified
"""

import asyncio
import json
import logging

from backend.config import OPENAI_API_KEY, OPENAI_CHAT_MODEL
from backend.db.queries import (
    get_all_finished_goods,
    get_bom_for_product,
)
from backend.phase1_extraction.sku_parser import parse_sku
from backend.phase2_enrichment.enrichment_store import (
    get_product_scrape,
    store_compliance_requirements,
    cache_get,
    cache_set,
)

logger = logging.getLogger(__name__)


COMPLIANCE_PROMPT = """You are a CPG compliance and regulatory expert specializing in dietary supplements, sports nutrition, and functional foods.

Given this finished product information, infer the compliance requirements that ALL raw material ingredients must satisfy.

Product SKU: {product_sku}
Brand/Company: {company_name}
Product Type: Dietary Supplement / Functional Food (sold on {retailer})
{scraped_info_section}

Ingredients in the BOM (bill of materials):
{ingredients_list}

Based on the product's label claims, brand positioning, and retail channel, determine:

1. What certifications/standards ALL ingredients must comply with
2. Any ingredient-type constraints (e.g., "no animal-derived ingredients" for vegan products)
3. Quality requirements implied by the retail channel and brand

Respond in JSON format:
{{
    "required_certifications": ["list of certifications ALL ingredients should have"],
    "inferred_constraints": ["list of quality constraints - e.g., 'must be plant-based'"],
    "regulatory_requirements": ["FDA", "cGMP", etc. - standard requirements"],
    "risk_flags": ["any specific compliance risks to watch for"],
    "confidence": 50,
    "reasoning": "explain your inference chain step by step"
}}

Key compliance rules:
- Labeled "Organic" or "USDA Organic" -> all ingredients need organic certification
- Labeled "Non-GMO" -> all ingredients must be non-GMO sourced
- Labeled "Vegan" -> no animal-derived ingredients allowed
- Labeled "Kosher" -> all ingredients + facility must be Kosher certified
- Labeled "Halal" -> all ingredients + facility must be Halal certified
- Labeled "Gluten-Free" -> all ingredients must be certified gluten-free
- Sold at premium retailers (Thrive Market, iHerb) -> likely higher quality standards
- Multiple certifications -> stricter overall compliance profile

Set confidence between 20-90:
- 70+ if scraped label data is available
- 40-70 if inferring from brand/channel only
- 20-40 if very uncertain"""


async def infer_compliance_for_product(
    product_id: int,
    product_sku: str,
    company_name: str,
) -> dict:
    """
    Infer compliance requirements for a single finished good.

    Args:
        product_id: DB product ID
        product_sku: Product SKU string
        company_name: Brand/company name

    Returns:
        Dict with compliance requirements
    """
    # Check cache (re-store in DB to cover the case where the cache exists
    # but the DB row was wiped)
    cache_key = f"compliance_{product_id}"
    cached = cache_get("compliance", cache_key)
    if cached:
        logger.info(f"  Product {product_sku}: compliance loaded from cache")
        store_compliance_requirements(product_id, cached)
        return cached

    parsed = parse_sku(product_sku)
    retailer = parsed.retailer or "unknown"

    # Get scraped product data if available
    scraped = get_product_scrape(product_id)
    if scraped:
        scraped_info_section = f"""
Scraped Product Info:
  Title: {scraped.get('title', 'N/A')}
  Brand: {scraped.get('brand', 'N/A')}
  Label Claims/Certifications Found: {', '.join(scraped.get('certifications', [])) or 'None found'}
  Listed Ingredients: {scraped.get('ingredients_text', 'N/A')[:500]}
  Price: ${scraped.get('price_usd', 'N/A')}
"""
    else:
        scraped_info_section = "\n(No scraped product data available - infer from brand and channel only)\n"

    # Get BOM ingredients
    bom = get_bom_for_product(product_id)
    ingredients = []
    for component in bom:
        rm_parsed = parse_sku(component["RawMaterialSKU"])
        if rm_parsed.ingredient_name:
            name = rm_parsed.ingredient_name.replace("-", " ")
            ingredients.append(f"  - {name} (from {component['CompanyName']})")

    ingredients_list = "\n".join(ingredients) if ingredients else "(No BOM data)"

    result = {
        "product_id": product_id,
        "product_sku": product_sku,
        "company_name": company_name,
        "retailer": retailer,
        "required_certifications": [],
        "inferred_constraints": [],
        "regulatory_requirements": ["FDA Compliance", "cGMP"],
        "risk_flags": [],
        "confidence": 20,
        "reasoning": "",
        "source": "llm_inference",
    }

    if not OPENAI_API_KEY:
        logger.warning(f"  Product {product_sku}: no API key for compliance inference")
        result["reasoning"] = "No API key available for LLM inference"
        cache_set("compliance", cache_key, result)
        return result

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    try:
        prompt = COMPLIANCE_PROMPT.format(
            product_sku=product_sku,
            company_name=company_name,
            retailer=retailer,
            scraped_info_section=scraped_info_section,
            ingredients_list=ingredients_list,
        )
        response = await client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        inferred = json.loads(response.choices[0].message.content)

        result["required_certifications"] = inferred.get("required_certifications", [])
        result["inferred_constraints"] = inferred.get("inferred_constraints", [])
        result["regulatory_requirements"] = inferred.get("regulatory_requirements", ["FDA Compliance", "cGMP"])
        result["risk_flags"] = inferred.get("risk_flags", [])
        result["confidence"] = inferred.get("confidence", 40)
        result["reasoning"] = inferred.get("reasoning", "")

        logger.info(
            f"  Product {product_sku}: inferred "
            f"{len(result['required_certifications'])} required certs, "
            f"confidence={result['confidence']}"
        )

    except Exception as e:
        logger.error(f"  Product {product_sku}: compliance inference failed - {e}")
        result["reasoning"] = f"LLM inference failed: {e}"

    # Cache and store
    cache_set("compliance", cache_key, result)
    store_compliance_requirements(product_id, result)
    return result


async def infer_compliance_for_all_products() -> list[dict]:
    """
    Infer compliance requirements for all 149 finished goods.

    Returns:
        List of compliance requirement dicts.
    """
    finished_goods = get_all_finished_goods()
    logger.info(f"Inferring compliance for {len(finished_goods)} finished goods...")

    results = []
    for i, fg in enumerate(finished_goods, 1):
        logger.info(
            f"  [{i}/{len(finished_goods)}] Inferring compliance: "
            f"{fg['SKU']} ({fg['CompanyName']})"
        )
        data = await infer_compliance_for_product(
            product_id=fg["Id"],
            product_sku=fg["SKU"],
            company_name=fg["CompanyName"],
        )
        results.append(data)

        # Small delay between API calls
        if i < len(finished_goods):
            await asyncio.sleep(0.2)

    # Summary
    avg_confidence = (
        sum(r["confidence"] for r in results) / len(results) if results else 0
    )
    total_certs = sum(len(r.get("required_certifications", [])) for r in results)
    total_flags = sum(len(r.get("risk_flags", [])) for r in results)
    logger.info(
        f"Compliance inference complete: {len(results)} products, "
        f"avg confidence={avg_confidence:.0f}, "
        f"{total_certs} total cert requirements, "
        f"{total_flags} risk flags"
    )
    return results
