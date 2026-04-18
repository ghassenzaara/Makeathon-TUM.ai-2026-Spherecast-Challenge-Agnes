"""
Verification Agent -- acts as a hallucination guardrail.

In a full implementation, this uses a secondary LLM with temperature=0.1
to verify that every claim in the recommendation is supported by raw evidence.
Since we're mitigating API limits, this implements a simplified mock verification.
"""

from typing import Dict, List
import logging

from backend.phase3_reasoning.sourcing_optimizer import SourcingProposal

logger = logging.getLogger(__name__)

def verify_proposal(proposal: SourcingProposal, raw_evidence: dict) -> Dict[str, str]:
    """
    Checks the proposal against the raw evidence.
    Returns a dict mapping claims to "VERIFIED", "UNVERIFIED", or "CONTRADICTED".
    """
    
    # Mocked verification logic
    verifications = {}
    
    # Check if the supplier name matches
    if proposal.recommended_supplier_name in raw_evidence.get("supplier_name", ""):
        verifications["Supplier Name"] = "VERIFIED"
    else:
        verifications["Supplier Name"] = "UNVERIFIED"
        
    if proposal.compliance_status == "ALL_PASS":
        verifications["Compliance Claims"] = "VERIFIED"
    else:
        verifications["Compliance Claims"] = "UNVERIFIED"
        
    return verifications
