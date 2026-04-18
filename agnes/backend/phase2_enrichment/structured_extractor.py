"""
Structured Extractor — clean HTML → LLM form-fill → Evidence.

Shared extraction layer for Phase 2 scrapers (iHerb, supplier sites).
Takes raw HTML, cleans it, feeds a structured LLM prompt, and records
every extracted field with an Evidence row.

This replaces the ad-hoc parsing in each scraper with a uniform pipeline.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from backend.config import GEMINI_API_KEY, GEMINI_CHAT_MODEL
from backend.db.evidence import record_evidence

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# HTML cleaning
# ──────────────────────────────────────────────

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_html(raw_html: str, max_chars: int = 8000) -> str:
    """Strip tags, collapse whitespace, truncate for LLM context."""
    text = _TAG_RE.sub(" ", raw_html)
    text = _WS_RE.sub(" ", text).strip()
    return text[:max_chars]


# ──────────────────────────────────────────────
# Extraction schema definitions
# ──────────────────────────────────────────────

PRODUCT_SCHEMA = {
    "title": "string — product display title",
    "brand": "string — brand name",
    "description": "string — product description (max 500 chars)",
    "certifications": "list[string] — certification labels found on page",
    "ingredients_text": "string — raw ingredients list from label",
    "allergens": "list[string] — allergens called out (e.g. soy, dairy, gluten)",
    "serving_size": "string — serving size text",
    "price_usd": "number|null — price in USD if visible",
    "dosage_form": "string|null — tablet, capsule, softgel, powder, gummy, liquid",
    "count": "integer|null — number of servings/units in container",
    "confidence": "integer 0-100 — how confident are you in this extraction",
}

SUPPLIER_SCHEMA = {
    "name": "string — supplier company name",
    "headquarters": "string — city, state/province, country",
    "region": "string — North America|Europe|Asia|Other",
    "certifications": "list[string] — certifications the supplier holds",
    "specialties": "list[string] — ingredient categories they specialize in",
    "company_size": "string — large|medium|small|unknown",
    "website": "string — company website URL",
    "notes": "string — relevant notes",
    "confidence": "integer 0-100",
}


def _schema_to_prompt(schema: dict) -> str:
    lines = ["{"]
    for k, v in schema.items():
        lines.append(f'  "{k}": {v},')
    lines.append("}")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# LLM extraction
# ──────────────────────────────────────────────

async def extract_product_from_html(
    html_text: str,
    source_url: str,
    product_id: int,
    context_hints: str = "",
) -> dict:
    """
    Extract structured product data from cleaned HTML via LLM.

    Args:
        html_text: Raw or cleaned HTML/text from the product page.
        source_url: URL the HTML was scraped from.
        product_id: DB product ID (for evidence recording).
        context_hints: Extra context (e.g. "This is an iHerb supplement").

    Returns:
        dict matching PRODUCT_SCHEMA keys.
    """
    cleaned = clean_html(html_text)
    if not cleaned or len(cleaned) < 20:
        logger.warning("  Product %d: HTML too short to extract (%d chars)",
                       product_id, len(cleaned))
        return _empty_product_result()

    if not GEMINI_API_KEY:
        return _empty_product_result()

    from google import genai as _genai
    from google.genai import types as _genai_types
    client = _genai.Client(api_key=GEMINI_API_KEY)

    schema_str = _schema_to_prompt(PRODUCT_SCHEMA)
    prompt = (
        "You are a supplement label data extraction expert. "
        "Extract structured product info from this page text.\n\n"
        f"Context: {context_hints}\n"
        f"Source URL: {source_url}\n\n"
        f"Page text (truncated):\n{cleaned}\n\n"
        f"Return a JSON object with this schema:\n{schema_str}\n\n"
        "Rules:\n"
        "- Only include certifications you actually see on the page\n"
        "- Set confidence 0-100 based on data quality\n"
        "- Use null for fields you cannot determine\n"
    )

    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_CHAT_MODEL,
            contents=prompt,
            config=_genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        result = json.loads(response.text)
        if not isinstance(result, dict):
            return _empty_product_result()

        # Record evidence for key fields
        conf = result.get("confidence", 50) / 100.0
        for fld in ["title", "certifications", "ingredients_text", "allergens"]:
            val = result.get(fld)
            if val and val != [] and val != "":
                record_evidence(
                    claim=f"{fld}={json.dumps(val)[:200]}",
                    subject_type="Product",
                    subject_id=product_id,
                    field_name=f"scrape.{fld}",
                    source_type="scrape",
                    source_url=source_url,
                    source_snippet=cleaned[:300],
                    confidence=conf,
                )

        return result
    except Exception as e:
        logger.error("  Product %d: structured extraction failed: %s", product_id, e)
        return _empty_product_result()


async def extract_supplier_from_text(
    text: str,
    supplier_name: str,
    supplier_id: int,
    source_url: str = "",
) -> dict:
    """
    Extract structured supplier data from text (page content or LLM knowledge).
    """
    if not GEMINI_API_KEY:
        return _empty_supplier_result(supplier_name, supplier_id)

    from google import genai as _genai
    from google.genai import types as _genai_types
    client = _genai.Client(api_key=GEMINI_API_KEY)

    schema_str = _schema_to_prompt(SUPPLIER_SCHEMA)
    cleaned = clean_html(text) if text else ""

    prompt = (
        "You are a CPG supply chain expert. Extract structured supplier info.\n\n"
        f"Supplier name: {supplier_name}\n"
        f"Source URL: {source_url}\n\n"
    )
    if cleaned:
        prompt += f"Page text:\n{cleaned[:4000]}\n\n"
    else:
        prompt += "No page text available — use your knowledge of this company.\n\n"

    prompt += (
        f"Return a JSON object:\n{schema_str}\n\n"
        "Be conservative — only include certifications you're fairly confident about.\n"
    )

    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_CHAT_MODEL,
            contents=prompt,
            config=_genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        result = json.loads(response.text)
        if not isinstance(result, dict):
            return _empty_supplier_result(supplier_name, supplier_id)

        # Record evidence
        conf = result.get("confidence", 40) / 100.0
        for fld in ["certifications", "headquarters", "specialties"]:
            val = result.get(fld)
            if val and val != [] and val != "":
                record_evidence(
                    claim=f"supplier.{fld}={json.dumps(val)[:200]}",
                    subject_type="Supplier",
                    subject_id=supplier_id,
                    field_name=f"supplier.{fld}",
                    source_type="scrape" if cleaned else "llm-inference",
                    source_url=source_url,
                    source_snippet=cleaned[:300] if cleaned else f"LLM knowledge for {supplier_name}",
                    confidence=conf,
                )

        result["supplier_id"] = supplier_id
        result["name"] = supplier_name
        return result
    except Exception as e:
        logger.error("  Supplier %s: extraction failed: %s", supplier_name, e)
        return _empty_supplier_result(supplier_name, supplier_id)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _empty_product_result() -> dict:
    return {
        "title": "",
        "brand": "",
        "description": "",
        "certifications": [],
        "ingredients_text": "",
        "allergens": [],
        "serving_size": "",
        "price_usd": None,
        "dosage_form": None,
        "count": None,
        "confidence": 0,
    }


def _empty_supplier_result(name: str, supplier_id: int) -> dict:
    return {
        "supplier_id": supplier_id,
        "name": name,
        "headquarters": "",
        "region": "",
        "certifications": [],
        "specialties": [],
        "company_size": "unknown",
        "website": "",
        "notes": "",
        "confidence": 0,
    }
