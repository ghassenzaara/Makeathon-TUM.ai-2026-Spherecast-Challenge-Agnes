"""
Confidence Scorer -- calculates a 0-100% confidence score for sourcing proposals.

Factor weights (sum to 100):
  - Ingredient functional equivalence: 25
  - External data coverage (compliance data quality): 25
  - Compliance verification result:    25
  - Supplier data quality (source-aware): 25

Source-Truth weighting (harmonized across phase3):
  - ONTOLOGY / DB (SQLite, rule-based):  1.00  (highest trust)
  - SCRAPING (Tavily / real website):    0.90  (very high trust)
  - LLM INFERENCE / HALLUCINATION:       0.60  (lower trust — unverified prose)
  - UNKNOWN / MOCK / MISSING:            0.20  (near-zero trust)

Post-score regulatory adjustment (multiplier, does not change the 4-factor sum):
  - Entity "Dissolved"  → ×0.10  (effectively disqualifies the proposal)
  - FDA "Warning"       → ×0.75  (25% penalty for enforcement history)
  - Entity "Unknown"    → ×0.90  (10% uncertainty penalty)
"""

import logging

from backend.phase1_extraction.substitution_groups import SubstitutionGroup
from backend.phase3_reasoning.sourcing_optimizer import SourcingProposal
from backend.phase3_reasoning.substitution_validator import SubstitutionValidation

logger = logging.getLogger(__name__)

# Single source of truth for how much we believe each data origin.
# Keep in sync with evidence_model.SOURCE_WEIGHTS.
SOURCE_TRUTH_WEIGHTS: dict[str, float] = {
    "ontology": 1.0,
    "db": 1.0,
    "rule": 1.0,
    "rule+llm": 0.85,            # rule-derived, LLM refined exceptions
    "tavily_search": 0.9,
    "scrape": 0.9,
    "scraping": 0.9,
    "deterministic": 0.9,
    "llm": 0.6,
    "llm_inference": 0.6,
    "llm-fallback": 0.6,
    "llm-inference": 0.6,
    "llm-group-inference": 0.6,
    "embedding": 0.4,
    "fuzzy": 0.4,
    "mock": 0.2,
    "none": 0.2,
    "unknown": 0.2,
    "": 0.2,
}


def _source_weight(raw_source: str | None) -> float:
    """Map a free-form source string to the canonical source-truth weight."""
    key = (raw_source or "").lower().strip()
    return SOURCE_TRUTH_WEIGHTS.get(key, 0.2)


def _is_mock(d: dict) -> bool:
    """
    Returns True if compliance/supplier data is absent, LLM-inferred, or
    explicitly mocked. Deterministic / scraping data is trusted (False).

    Relies on the canonical source-truth weight table: anything mapping to a
    weight ≤ 0.6 (LLM or lower) is considered low-trust — i.e. mock-ish.
    """
    if not d:
        return True
    raw = d.get("source") or ""
    if raw:
        # Trust by source weight first; this is the authoritative check.
        return _source_weight(raw) < 0.85
    # No explicit source: treat prose-only notes as low-trust.
    if d.get("_inference_note") and not d.get("scrape_success"):
        return True
    source = (d.get("source") or "").lower()
    return source in ("mock",)


def _supplier_quality_score(supplier_data: dict) -> float:
    """
    Returns a 0–25 score based on how the supplier data was sourced.
      25 — Tavily Search (real web data, deterministic)
      15 — LLM inference (educated guess, not externally verified)
       5 — No data / unknown source
    """
    if not supplier_data:
        return 5.0
    source = (supplier_data.get("source") or "").lower()
    if source == "tavily_search":
        return 25.0
    if source == "llm_inference":
        return 15.0
    return 5.0


def _regulatory_adjustment(fda_data: dict, entity_data: dict) -> float:
    """
    Post-score multiplier based on FDA enforcement and entity verification data.
    Returns a value 0.0–1.0 to multiply the base score by.
    Called after the 4-factor sum so it doesn't distort individual factor weights.
    """
    multiplier = 1.0

    entity_status = (entity_data or {}).get("status", "Unknown")
    if entity_status == "Dissolved":
        multiplier *= 0.10   # near-disqualification: entity is out of business
    elif entity_status == "Unknown":
        multiplier *= 0.90   # small uncertainty penalty

    fda_status = (fda_data or {}).get("status", "")
    if fda_status == "Warning":
        multiplier *= 0.75   # 25% penalty for FDA enforcement history

    return multiplier


def _supplier_quality_score(supplier_data: dict) -> float:
    """
    Returns a 0–25 score based on how the supplier data was sourced.

    Scaled directly off the canonical source-truth weights so that DB/ontology
    data contributes the full 25 points, scraping 22.5, LLM inference 15, and
    missing/mocked data bottoms out near zero — preventing LLM guesses from
    impersonating verified evidence in the final confidence score.
    """
    if not supplier_data:
        return 5.0
    w = _source_weight(supplier_data.get("source"))
    return round(25.0 * w, 1)


def _regulatory_adjustment(fda_data: dict, entity_data: dict) -> float:
    """
    Post-score multiplier based on FDA enforcement and entity verification data.
    Returns a value 0.0–1.0 to multiply the base score by.
    Called after the 4-factor sum so it doesn't distort individual factor weights.
    """
    multiplier = 1.0

    entity_status = (entity_data or {}).get("status", "Unknown")
    if entity_status == "Dissolved":
        multiplier *= 0.10   # near-disqualification: entity is out of business
    elif entity_status == "Unknown":
        multiplier *= 0.90   # small uncertainty penalty

    fda_status = (fda_data or {}).get("status", "")
    if fda_status == "Warning":
        multiplier *= 0.75   # 25% penalty for FDA enforcement history

    return multiplier


def score_proposal_confidence(
    proposal: SourcingProposal,
    group: SubstitutionGroup,
    validation: SubstitutionValidation,
    supplier_data: dict,
    compliance_data: dict,
    fda_data: dict = None,
    entity_data: dict = None,
) -> float:
    """
    Assigns confidence score (0–100%) based on data completeness and validation.

    Args:
        fda_data:     OpenFDA risk record for the recommended supplier (optional).
        entity_data:  OpenCorporates entity record for the recommended supplier (optional).
    """
    # 1. Ingredient functional equivalence (0-25)
    match_score = max(0.0, min(1.0, validation.functional_equivalence_score)) * 25.0

    # 2. External data coverage (0-25) -- quality of compliance inference.
    #    Weighted by the source that produced the requirements: DB-derived
    #    rules earn the full 25, LLM exceptions are capped mid-range, missing
    #    / mocked data near-zero.
    if not compliance_data:
        ext_score = 5.0
    else:
        comp_weight = _source_weight(compliance_data.get("source"))
        has_reqs = bool(compliance_data.get("required_certifications"))
        if _is_mock(compliance_data):
            ext_score = round(25.0 * max(comp_weight, 0.2) * 0.5, 1)
        elif has_reqs:
            ext_score = round(25.0 * comp_weight, 1)
        else:
            ext_score = round(15.0 * comp_weight, 1)

    # 3. Compliance verification (0-25)
    if proposal.compliance_status == "ALL_PASS":
        comp_score = 25.0
    elif proposal.compliance_status == "PARTIAL":
        comp_score = 15.0
    elif proposal.compliance_status == "REVIEW_NEEDED":
        comp_score = 10.0
    else:
        comp_score = 0.0

    # 4. Supplier data quality (0-25) -- source-aware
    supp_score = _supplier_quality_score(supplier_data)
    if not (supplier_data or {}).get("certifications"):
        supp_score = max(0.0, supp_score - 5.0)

    base = round(max(0.0, min(100.0, match_score + ext_score + comp_score + supp_score)), 1)

    # Regulatory adjustment (post-score multiplier, does not alter factor weights)
    adjustment = _regulatory_adjustment(fda_data or {}, entity_data or {})
    final = round(max(0.0, min(100.0, base * adjustment)), 1)

    if adjustment < 1.0:
        logger.debug(
            f"  Regulatory adjustment ×{adjustment:.2f} applied "
            f"({base:.1f} → {final:.1f})"
        )

    return final
