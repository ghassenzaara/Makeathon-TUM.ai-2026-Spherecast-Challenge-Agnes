"""
Confidence Scorer -- calculates a 0-100% confidence score for sourcing proposals.
"""

from typing import List, Dict
import logging

from backend.phase1_extraction.substitution_groups import SubstitutionGroup
from backend.phase3_reasoning.sourcing_optimizer import SourcingProposal
from backend.phase3_reasoning.substitution_validator import SubstitutionValidation

logger = logging.getLogger(__name__)

def score_proposal_confidence(
    proposal: SourcingProposal,
    group: SubstitutionGroup,
    validation: SubstitutionValidation,
    supplier_data: dict,
    compliance_data: dict
) -> float:
    """
    Assigns confidence score (0-100%) based on data completeness and validation.
    
    Factor weights:
    - Ingredient match quality: 25%
    - External data coverage: 25%
    - Compliance verification: 25%
    - Supplier data quality: 25%
    """
    
    # 1. Ingredient match quality (25%)
    match_score = validation.functional_equivalence_score * 25.0
    
    # 2. External data coverage (25%)
    # Do we have scraped data for the products?
    ext_score = 15.0 if compliance_data.get("source") != "mock" else 5.0
    
    # 3. Compliance verification (25%)
    if proposal.compliance_status == "ALL_PASS":
        comp_score = 25.0
    elif proposal.compliance_status == "REVIEW_NEEDED":
        comp_score = 10.0
    else:
        comp_score = 0.0
        
    # 4. Supplier data quality (25%)
    supp_score = 25.0 if supplier_data.get("source") != "mock" else 10.0
    if not supplier_data.get("certifications"):
        supp_score -= 5.0
        
    total_score = min(max(match_score + ext_score + comp_score + supp_score, 0.0), 100.0)
    
    return total_score
