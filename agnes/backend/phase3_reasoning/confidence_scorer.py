"""
Confidence Scorer -- calculates a 0-100% confidence score for sourcing proposals.

Factor weights (sum to 100):
  - Ingredient functional equivalence: 25
  - External data coverage (compliance data quality): 25
  - Compliance verification result:    25
  - Supplier data quality (source-aware): 25

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


def _is_mock(d: dict) -> bool:
    """Returns True if compliance data is absent or LLM-inferred (not scraped/real)."""
    if not d:
        return True
    if d.get("_inference_note"):
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

    # 2. External data coverage (0-25) -- quality of compliance inference
    if _is_mock(compliance_data):
        ext_score = 5.0
    elif compliance_data.get("required_certifications"):
        ext_score = 25.0
    else:
        ext_score = 15.0

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
