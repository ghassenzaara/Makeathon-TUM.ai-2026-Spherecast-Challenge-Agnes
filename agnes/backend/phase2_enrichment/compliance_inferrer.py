"""
Compliance Inferrer — per-ingredient requirement derivation with group inheritance.

Enhanced compliance pipeline:
  1. For each finished good, scrape/load label claims
  2. Derive per-INGREDIENT compliance requirements (not just per-product)
  3. Inherit group-level requirements from substitution group siblings
  4. Use LLM to identify exception cases (e.g. "water is exempt from organic")
  5. Record every requirement with Evidence rows

Stores results in:
  - IngredientComplianceRequirement table (per RM per FG)
  - Evidence table (provenance for each requirement)
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from backend.config import OPENAI_API_KEY, OPENAI_CHAT_MODEL
from backend.db.queries import (
    get_all_finished_goods,
    get_bom_for_product,
    insert_ingredient_compliance_requirement,
    get_ingredient_card,
)
from backend.db.evidence import record_evidence
from backend.phase1_extraction.sku_parser import parse_sku
from backend.phase2_enrichment.enrichment_store import (
    get_product_scrape,
    store_compliance_requirements,
    cache_get,
    cache_set,
)
from backend.ontology import get_ontologies

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Rule-based derivation (fast, high confidence)
# ──────────────────────────────────────────────

_CERT_TO_INGREDIENT_RULES: dict[str, list[dict]] = {
    "organic": [
        {"requirement": "organic-certified", "applies_to": "all",
         "exceptions": ["water", "sodium-chloride", "silicon-dioxide"],
         "derivation": "rule", "confidence": 0.95},
    ],
    "non-gmo": [
        {"requirement": "non-gmo-sourced", "applies_to": "all",
         "exceptions": ["sodium-chloride", "silicon-dioxide"],
         "derivation": "rule", "confidence": 0.90},
    ],
    "vegan": [
        {"requirement": "no-animal-derived", "applies_to": "all",
         "exceptions": [],
         "derivation": "rule", "confidence": 0.95},
    ],
    "kosher": [
        {"requirement": "kosher-certified", "applies_to": "all",
         "exceptions": [],
         "derivation": "rule", "confidence": 0.90},
    ],
    "halal": [
        {"requirement": "halal-certified", "applies_to": "all",
         "exceptions": [],
         "derivation": "rule", "confidence": 0.90},
    ],
    "gluten-free": [
        {"requirement": "gluten-free-certified", "applies_to": "all",
         "exceptions": [],
         "derivation": "rule", "confidence": 0.85},
    ],
}

# Base regulatory requirements for all supplements
_BASE_REQUIREMENTS = [
    {"requirement": "fda-compliant", "derivation": "rule", "confidence": 0.99},
    {"requirement": "cgmp-manufactured", "derivation": "rule", "confidence": 0.95},
]


def _derive_rule_based_requirements(
    fg_certs: list[str],
    rm_substance: str | None,
) -> list[dict]:
    """
    Derive compliance requirements for a specific raw material based on the
    finished good's label certifications.
    """
    onts = get_ontologies()
    requirements = list(_BASE_REQUIREMENTS)  # copy base

    for raw_cert in fg_certs:
        canonical = onts.certifications.canonicalize(raw_cert)
        if not canonical:
            continue
        rules = _CERT_TO_INGREDIENT_RULES.get(canonical, [])
        for rule in rules:
            # Check if this RM is in the exception list
            if rm_substance and rm_substance in rule.get("exceptions", []):
                continue
            requirements.append({
                "requirement": rule["requirement"],
                "derivation": f"rule:{canonical}",
                "confidence": rule["confidence"],
            })

    return requirements


# ──────────────────────────────────────────────
# LLM exception finder
# ──────────────────────────────────────────────

_EXCEPTION_PROMPT = """You are a CPG regulatory compliance expert. Given a finished good's certifications
and a specific raw material ingredient, identify any EXCEPTIONS where the certification
requirement might NOT apply to this specific ingredient.

Finished Good Certifications: {certs}
Raw Material: {ingredient_name} (substance: {substance})
Category: {category}

Known rules:
- "Organic" certification → all ingredients should be organic-certified
- "Non-GMO" → all ingredients should be non-GMO sourced
- "Vegan" → no animal-derived ingredients
- "Kosher" → all ingredients kosher certified
- "Halal" → all ingredients halal certified

Are there any recognized EXCEPTIONS for this ingredient? For example:
- Water and salt are often exempt from organic certification
- Minerals/vitamins may have different organic requirements
- Processing aids may be exempt from certain certifications

Respond in JSON:
{{
    "exceptions": ["list of certifications this ingredient is exempt from"],
    "reasoning": "brief explanation",
    "confidence": 60
}}

Be conservative. Only list exceptions you are confident about."""


async def _find_exceptions(
    fg_certs: list[str],
    ingredient_name: str,
    substance: str | None,
    category: str,
) -> list[str]:
    """Use LLM to find exceptions for this ingredient."""
    if not OPENAI_API_KEY or not fg_certs:
        return []

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    try:
        prompt = _EXCEPTION_PROMPT.format(
            certs=", ".join(fg_certs),
            ingredient_name=ingredient_name,
            substance=substance or ingredient_name,
            category=category,
        )
        response = await client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        return result.get("exceptions", [])
    except Exception as e:
        logger.error(f"  Exception finder failed for {ingredient_name}: {e}")
        return []


# ──────────────────────────────────────────────
# Per-product compliance inference
# ──────────────────────────────────────────────

async def infer_compliance_for_product(
    product_id: int,
    product_sku: str,
    company_name: str,
    use_llm_exceptions: bool = True,
) -> dict:
    """
    Infer compliance requirements for a single finished good,
    with per-ingredient granularity.
    """
    # Check cache
    cache_key = f"compliance_{product_id}"
    cached = cache_get("compliance", cache_key)
    if cached:
        logger.info(f"  Product {product_sku}: compliance loaded from cache")
        store_compliance_requirements(product_id, cached)
        return cached

    parsed = parse_sku(product_sku)
    retailer = parsed.retailer or "unknown"
    onts = get_ontologies()

    # Get scraped product data to find label certs
    scraped = get_product_scrape(product_id)
    fg_certs = []
    if scraped:
        raw_certs = scraped.get("certifications", [])
        fg_certs = [
            onts.certifications.canonicalize(c) or c
            for c in raw_certs
        ]
        fg_certs = [c for c in fg_certs if c]

    # Get BOM ingredients
    bom = get_bom_for_product(product_id)
    now = datetime.now(timezone.utc).isoformat()

    per_ingredient_reqs: list[dict] = []
    total_reqs = 0

    for component in bom:
        rm_id = component["ConsumedProductId"]
        rm_sku = component["RawMaterialSKU"]
        rm_parsed = parse_sku(rm_sku)
        ingredient_name = rm_parsed.ingredient_name or rm_sku

        # Get the card for this RM
        card = get_ingredient_card(rm_id)
        substance = card.get("Substance") if card else None
        category = ""
        if substance:
            category = onts.substances.category_of(substance)

        # Derive rule-based requirements
        requirements = _derive_rule_based_requirements(fg_certs, substance)

        # LLM exception filtering (optional, for high-value products)
        exceptions_list: list[str] = []
        if use_llm_exceptions and fg_certs and len(fg_certs) >= 2:
            exceptions_list = await _find_exceptions(
                fg_certs, ingredient_name, substance, category,
            )

        # Store each requirement
        for req in requirements:
            # Skip if LLM says this ingredient is exempt
            req_cert = req.get("requirement", "")
            if any(exc.lower() in req_cert.lower() for exc in exceptions_list):
                continue

            ev_id = record_evidence(
                claim=f"requirement={req['requirement']} for RM {rm_id} in FG {product_id}",
                subject_type="Product",
                subject_id=rm_id,
                field_name=f"compliance.{req['requirement']}",
                source_type=req["derivation"].split(":")[0],
                source_url="",
                source_snippet=f"FG certs: {fg_certs}, derivation: {req['derivation']}",
                confidence=req["confidence"],
            )

            insert_ingredient_compliance_requirement({
                "FinishedGoodId": product_id,
                "RawMaterialId": rm_id,
                "Requirement": req["requirement"],
                "DerivationType": req["derivation"],
                "Confidence": req["confidence"],
                "EvidenceId": ev_id,
                "CreatedAt": now,
            })
            total_reqs += 1

        per_ingredient_reqs.append({
            "rm_id": rm_id,
            "ingredient": ingredient_name,
            "substance": substance,
            "requirements": [r["requirement"] for r in requirements],
            "exceptions": exceptions_list,
        })

    result = {
        "product_id": product_id,
        "product_sku": product_sku,
        "company_name": company_name,
        "retailer": retailer,
        "fg_certifications": fg_certs,
        "per_ingredient": per_ingredient_reqs,
        "total_requirements": total_reqs,
        "required_certifications": list(set(
            r["requirement"] for ing in per_ingredient_reqs
            for r in [{"requirement": req} for req in ing["requirements"]]
        )),
        "inferred_constraints": [],
        "regulatory_requirements": ["FDA Compliance", "cGMP"],
        "risk_flags": [],
        "confidence": 70 if fg_certs else 35,
        "reasoning": f"Derived {total_reqs} requirements from {len(fg_certs)} FG certs across {len(bom)} ingredients",
        "source": "rule+llm" if use_llm_exceptions else "rule",
    }

    # Cache and store
    cache_set("compliance", cache_key, result)
    store_compliance_requirements(product_id, result)
    logger.info(
        f"  Product {product_sku}: {total_reqs} requirements across "
        f"{len(bom)} ingredients, {len(fg_certs)} FG certs"
    )
    return result


async def infer_compliance_for_all_products(
    use_llm_exceptions: bool = False,
) -> list[dict]:
    """
    Infer compliance requirements for all finished goods.

    Args:
        use_llm_exceptions: If True, use LLM to find per-ingredient exceptions.
                           Set to False for faster runs.

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
            use_llm_exceptions=use_llm_exceptions,
        )
        results.append(data)

        # Small delay between API calls
        if use_llm_exceptions and i < len(finished_goods):
            await asyncio.sleep(0.2)

    # Summary
    avg_confidence = (
        sum(r["confidence"] for r in results) / len(results) if results else 0
    )
    total_reqs = sum(r.get("total_requirements", 0) for r in results)
    logger.info(
        f"Compliance inference complete: {len(results)} products, "
        f"avg confidence={avg_confidence:.0f}, "
        f"{total_reqs} total ingredient-level requirements"
    )
    return results
