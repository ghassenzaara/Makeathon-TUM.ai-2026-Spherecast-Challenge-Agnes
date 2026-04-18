"""
Confidence Scorer -- calculates a 0-100% confidence score for sourcing proposals.

Factor weights (sum to 100):
  - Ingredient functional equivalence: 25
  - External data coverage (is data real vs mock): 25
  - Compliance verification result:    25
  - Supplier data quality:             25
"""

import logging

from backend.phase1_extraction.substitution_groups import SubstitutionGroup
from backend.phase3_reasoning.sourcing_optimizer import SourcingProposal
from backend.phase3_reasoning.substitution_validator import SubstitutionValidation

logger = logging.getLogger(__name__)


def _is_mock(d: dict) -> bool:
    if not d:
        return True
    source = (d.get("source") or "").lower()
    if source == "mock":
        return True
    # Inference notes added by Phase 2 fallbacks also indicate mock-ish data
    if d.get("_inference_note"):
        return True
    return False


def score_proposal_confidence(
    proposal: SourcingProposal,
    group: SubstitutionGroup,
    validation: SubstitutionValidation,
    supplier_data: dict,
    compliance_data: dict,
) -> float:
    """
    Assigns confidence score (0-100%) based on data completeness and validation.
    """
    # 1. Ingredient functional equivalence (0-25)
    match_score = max(0.0, min(1.0, validation.functional_equivalence_score)) * 25.0

    # 2. External data coverage (0-25) -- do we have REAL scraped/inferred data?
    if _is_mock(compliance_data):
        ext_score = 5.0
    elif compliance_data.get("required_certifications"):
        ext_score = 25.0
    else:
        # Real data but no certs surfaced -- partial coverage
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

    # 4. Supplier data quality (0-25)
    if _is_mock(supplier_data):
        supp_score = 10.0
    else:
        supp_score = 25.0
    if not supplier_data.get("certifications"):
        supp_score = max(0.0, supp_score - 5.0)

    total = match_score + ext_score + comp_score + supp_score
    return round(max(0.0, min(100.0, total)), 1)
