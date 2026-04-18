"""
Attribute Extractor -- turns a raw-material Product into an IngredientCard.

Extraction strategy (cheap → expensive; each tier fills only what the previous
tier left unknown):

  1. SKU regex: parse_sku() already pulled ingredient_name from the SKU.
  2. Substance alias lookup: run name through substances.json.
  3. Token axis matching: reuse ontology/attributes.json to fill
     hydration/salt/chirality/vit-d-form/... from tokens in the name.
  4. LLM fallback (batched + deduplicated + disk-cached): for names whose
     substance is still unknown after 1-3. One API call handles ~25 names.

Every field written emits an Evidence row with a concrete source_type
("sku-regex" | "ontology" | "llm" | ...) and a literal snippet.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

from backend.config import (
    ATTRIBUTE_EXTRACTION_BATCH_SIZE,
    ENRICHMENT_CACHE_DIR,
    MAX_LLM_CALLS_PER_RUN,
    GEMINI_API_KEY,
    GEMINI_CHAT_MODEL,
)
from backend.db.evidence import record_evidence
from backend.db.queries import (
    insert_card_certification,
    upsert_ingredient_card,
)
from backend.ontology import get_ontologies
from backend.phase1_extraction.sku_parser import parse_sku, tokens_from_ingredient
from backend.phase2_enrichment.enrichment_store import cache_get, cache_set

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data model (mirrors the IngredientCard table)
# ──────────────────────────────────────────────

@dataclass
class CardDraft:
    product_id: int
    raw_ingredient_name: str
    substance: Optional[str] = None
    form: Optional[str] = None
    grade: Optional[str] = None
    hydration: Optional[str] = None
    salt_or_ester: Optional[str] = None
    source: Optional[str] = None
    source_detail: Optional[str] = None
    chirality: Optional[str] = None
    vit_d_form: Optional[str] = None
    vit_b12_form: Optional[str] = None
    tocopherol_form: Optional[str] = None
    certifications: list[str] = field(default_factory=list)
    extraction_method: str = "sku-regex"
    # field_name -> (source_type, source_snippet, confidence)
    field_evidence: dict[str, tuple[str, str, float]] = field(default_factory=dict)

    def set_field(self, attr: str, value: Optional[str],
                  source_type: str, snippet: str, confidence: float):
        if not value:
            return
        current = getattr(self, attr)
        if current:
            return  # Don't overwrite a higher-priority value
        setattr(self, attr, value)
        self.field_evidence[f"card.{attr}"] = (source_type, snippet, confidence)

    def to_db_row(self) -> dict:
        return {
            "ProductId": self.product_id,
            "Substance": self.substance,
            "Form": self.form,
            "Grade": self.grade,
            "Hydration": self.hydration,
            "SaltOrEster": self.salt_or_ester,
            "Source": self.source,
            "SourceDetail": self.source_detail,
            "Chirality": self.chirality,
            "VitDForm": self.vit_d_form,
            "VitB12Form": self.vit_b12_form,
            "TocopherolForm": self.tocopherol_form,
            "ExtractedAt": datetime.now(timezone.utc).isoformat(),
            "ExtractionMethod": self.extraction_method,
            "RawIngredientName": self.raw_ingredient_name,
        }


# ──────────────────────────────────────────────
# LLM fallback cache (per normalized name)
# ──────────────────────────────────────────────

_ATTR_CACHE_CATEGORY = "attributes"


def _cache_key_for_name(name: str) -> str:
    """Stable cache key per normalized ingredient name."""
    h = hashlib.md5(name.encode("utf-8")).hexdigest()[:10]
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:80]
    return f"{safe}_{h}"


def _load_cached_llm_attrs(name: str) -> Optional[dict]:
    return cache_get(_ATTR_CACHE_CATEGORY, _cache_key_for_name(name))


def _store_cached_llm_attrs(name: str, data: dict):
    cache_set(_ATTR_CACHE_CATEGORY, _cache_key_for_name(name), data)


# ──────────────────────────────────────────────
# Tiers 1-3: deterministic extraction
# ──────────────────────────────────────────────

def _apply_deterministic_tiers(draft: CardDraft, onts) -> None:
    name = draft.raw_ingredient_name
    tokens = tokens_from_ingredient(name)

    # Tier 2: substance alias lookup.
    canonical = onts.substances.canonicalize(name)
    if not canonical:
        # Try individual tokens (e.g. "vitamin-c-ascorbic-acid" may already be an alias,
        # but "ascorbic-acid" tokenized → "ascorbic" alone won't match. Fall through.)
        for tok in sorted(tokens, key=len, reverse=True):
            hit = onts.substances.canonicalize(tok)
            if hit:
                canonical = hit
                break
    if canonical:
        draft.set_field(
            "substance", canonical,
            source_type="ontology",
            snippet=f"'{name}' → '{canonical}' via substance ontology",
            confidence=1.0,
        )

    # Tier 3: token axis matching.
    axis_hits = onts.attributes.extract_from_tokens(tokens)
    attr_map = {
        "form": "form", "grade": "grade", "hydration": "hydration",
        "salt_or_ester": "salt_or_ester", "source": "source",
        "source_detail": "source_detail", "chirality": "chirality",
        "vit_d_form": "vit_d_form", "vit_b12_form": "vit_b12_form",
        "tocopherol_form": "tocopherol_form",
    }
    for axis, attr in attr_map.items():
        value = axis_hits.get(axis)
        if value:
            draft.set_field(
                attr, value,
                source_type="sku-regex",
                snippet=f"token match on '{axis}' = '{value}' in '{name}'",
                confidence=0.9,
            )


# ──────────────────────────────────────────────
# Tier 4: LLM fallback (batched)
# ──────────────────────────────────────────────

_LLM_SCHEMA_HINT = """Return a JSON object with one key per input name. Each value must have this shape:
{
  "substance": "canonical kebab-case name (e.g. 'vitamin-d3', 'citric-acid')",
  "form": "powder|oil|isolate|extract|liquid|capsule|gel|null",
  "grade": "usp|food|pharma|cosmetic|null",
  "hydration": "anhydrous|monohydrate|dihydrate|null",
  "salt_or_ester": "citrate|gluconate|sulfate|oxide|carbonate|chloride|phosphate|ascorbate|null",
  "source": "plant|animal|microbial|synthetic|mineral|null",
  "source_detail": "lanolin|lichen|corn|soy|sunflower|coconut|bovine|null",
  "chirality": "l|d|dl|null",
  "vit_d_form": "d2|d3|null",
  "vit_b12_form": "cyanocobalamin|methylcobalamin|null",
  "tocopherol_form": "d-alpha|dl-alpha|mixed-tocopherols|null",
  "confidence": 0.0-1.0
}
Use null when unsure. Do not invent certifications or sources you aren't confident about.
For non-ingredient items like 'gummy-base' or 'ferment-media', set substance to the name itself."""


class _LLMBudget:
    """Simple global counter so we can abort if we blow past MAX_LLM_CALLS_PER_RUN."""
    def __init__(self, cap: int):
        self.cap = cap
        self.used = 0

    def consume(self, n: int = 1) -> bool:
        if self.used + n > self.cap:
            return False
        self.used += n
        return True


async def _llm_batch(names: list[str], budget: _LLMBudget) -> dict[str, dict]:
    """
    One OpenAI call for a batch of ingredient names. Returns {name: attrs-dict}.
    On error or budget exhaustion, returns {}.
    """
    if not names or not GEMINI_API_KEY:
        return {}
    if not budget.consume(1):
        logger.warning("LLM budget exhausted (cap=%d). Skipping batch of %d names.",
                       budget.cap, len(names))
        return {}

    from google import genai as _genai
    from google.genai import types as _genai_types
    client = _genai.Client(api_key=GEMINI_API_KEY)

    prompt = (
        "You are a supplement-ingredient chemistry expert. Given these normalized "
        "ingredient names, extract structured attributes per the schema.\n\n"
        f"{_LLM_SCHEMA_HINT}\n\n"
        "Names:\n"
        + "\n".join(f"- {n}" for n in names)
        + "\n\nReturn one top-level JSON object keyed by exact input name."
    )
    try:
        logger.info("  LLM attribute batch: %d names (budget used %d/%d)",
                    len(names), budget.used, budget.cap)
        response = await client.aio.models.generate_content(
            model=GEMINI_CHAT_MODEL,
            contents=prompt,
            config=_genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        payload = json.loads(response.text)
        if not isinstance(payload, dict):
            return {}
        # Sanity filter: keys should overlap with inputs
        return {k: v for k, v in payload.items() if k in names and isinstance(v, dict)}
    except Exception as e:
        logger.error("  LLM batch failed: %s", e)
        return {}


def _apply_llm_attrs(draft: CardDraft, attrs: dict, onts) -> None:
    """Fill draft fields from LLM output, validated against the ontology."""
    if not attrs:
        return
    conf = float(attrs.get("confidence", 0.6))
    snippet = f"LLM: {json.dumps({k: v for k, v in attrs.items() if v is not None})[:300]}"

    # Substance: accept even if ontology-unknown but canonicalize if possible
    subs = attrs.get("substance")
    if isinstance(subs, str):
        canonical = onts.substances.canonicalize(subs) or subs
        draft.set_field("substance", canonical, "llm", snippet, conf)

    # Axis-valued fields with validation
    axis_map = [
        ("form", "form"), ("grade", "grade"), ("hydration", "hydration"),
        ("salt_or_ester", "salt_or_ester"), ("source", "source"),
        ("source_detail", "source_detail"), ("chirality", "chirality"),
        ("vit_d_form", "vit_d_form"), ("vit_b12_form", "vit_b12_form"),
        ("tocopherol_form", "tocopherol_form"),
    ]
    for axis, attr in axis_map:
        v = attrs.get(axis)
        if isinstance(v, str):
            validated = onts.attributes.validate(axis, v)
            if validated:
                draft.set_field(attr, validated, "llm", snippet, conf)

    draft.extraction_method = "llm"


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

async def extract_attributes_for_all(
    raw_materials: list[dict],
    use_llm: bool = True,
) -> list[CardDraft]:
    """
    Extract attributes for every raw material.

    Args:
        raw_materials: list of dicts with keys Id, SKU, CompanyId, CompanyName.
        use_llm: enable tier 4 fallback (requires OPENAI_API_KEY).

    Returns:
        list of CardDraft objects (not yet persisted).
    """
    onts = get_ontologies()
    drafts: list[CardDraft] = []

    # ── Tiers 1-3 (deterministic) ──
    name_to_drafts: dict[str, list[CardDraft]] = {}
    for rm in raw_materials:
        parsed = parse_sku(rm["SKU"])
        name = parsed.ingredient_name or ""
        draft = CardDraft(product_id=rm["Id"], raw_ingredient_name=name)
        if name:
            _apply_deterministic_tiers(draft, onts)
        drafts.append(draft)
        name_to_drafts.setdefault(name, []).append(draft)

    # ── Tier 4: LLM fallback, per unique name, batched, cached ──
    unknown_names = sorted({
        d.raw_ingredient_name
        for d in drafts
        if d.raw_ingredient_name and d.substance is None
    })
    logger.info(
        "Attribute extraction: %d cards built by tiers 1-3, "
        "%d unique names still need LLM fallback.",
        sum(1 for d in drafts if d.substance is not None),
        len(unknown_names),
    )

    # Drain cache first.
    still_unknown: list[str] = []
    cache_hits = 0
    for name in unknown_names:
        cached = _load_cached_llm_attrs(name) if use_llm else None
        if cached:
            cache_hits += 1
            for d in name_to_drafts.get(name, []):
                _apply_llm_attrs(d, cached, onts)
        else:
            still_unknown.append(name)
    logger.info("  LLM cache: %d hits, %d need a live call.",
                cache_hits, len(still_unknown))

    # Live LLM calls in batches.
    if use_llm and still_unknown:
        budget = _LLMBudget(MAX_LLM_CALLS_PER_RUN)
        batches = [
            still_unknown[i:i + ATTRIBUTE_EXTRACTION_BATCH_SIZE]
            for i in range(0, len(still_unknown), ATTRIBUTE_EXTRACTION_BATCH_SIZE)
        ]
        for batch in batches:
            batch_result = await _llm_batch(batch, budget)
            for name in batch:
                attrs = batch_result.get(name)
                if attrs:
                    _store_cached_llm_attrs(name, attrs)
                    for d in name_to_drafts.get(name, []):
                        _apply_llm_attrs(d, attrs, onts)

    return drafts


def persist_card(draft: CardDraft) -> None:
    """Write the draft + per-field Evidence + certifications to the DB."""
    upsert_ingredient_card(draft.to_db_row())

    # Per-field Evidence
    for field_name, (source_type, snippet, confidence) in draft.field_evidence.items():
        attr = field_name.split(".", 1)[1]
        value = getattr(draft, attr, None)
        if value is None:
            continue
        record_evidence(
            claim=f"{attr}={value} for product {draft.product_id}",
            subject_type="Product",
            subject_id=draft.product_id,
            field_name=field_name,
            source_type=source_type,
            source_url="",
            source_snippet=snippet,
            confidence=confidence,
        )

    # Certifications (from LLM cache if any) — ontology-canonicalized.
    onts = get_ontologies()
    for raw_cert in draft.certifications:
        canonical = onts.certifications.canonicalize(raw_cert)
        if not canonical:
            continue
        ev_id = record_evidence(
            claim=f"cert={canonical} on product {draft.product_id}",
            subject_type="Product",
            subject_id=draft.product_id,
            field_name=f"certifications.{canonical}",
            source_type="llm" if draft.extraction_method == "llm" else "ontology",
            source_url="",
            source_snippet=f"raw='{raw_cert}' → canonical='{canonical}'",
            confidence=0.7 if draft.extraction_method == "llm" else 1.0,
        )
        insert_card_certification(draft.product_id, canonical, ev_id)


def persist_all(drafts: list[CardDraft]) -> None:
    for d in drafts:
        persist_card(d)
    logger.info("Persisted %d ingredient cards + evidence.", len(drafts))
