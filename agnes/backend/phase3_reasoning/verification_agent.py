"""
Verification Agent -- hallucination guardrail.

Cross-references each claim in a sourcing proposal against the raw evidence
gathered in Phase 2 (supplier info + compliance inference). Purely
rule-based: no LLM, no nondeterminism, cheap to run on every proposal.

Returns a dict mapping claim-keys to one of:
    "VERIFIED"    -- evidence supports the claim
    "UNVERIFIED"  -- evidence is silent on the claim
    "CONTRADICTED"-- evidence directly contradicts the claim
"""

from typing import Dict, List
import logging

from backend.phase3_reasoning.sourcing_optimizer import SourcingProposal
from backend.phase3_reasoning.compliance_checker import _canonical_tokens

logger = logging.getLogger(__name__)


def verify_proposal(
    proposal: SourcingProposal,
    supplier_evidence: dict,
    compliance_evidence: List[dict] = None,
) -> tuple:
    """
    Args:
        supplier_evidence:    The Phase 2 supplier record for the proposed supplier.
        compliance_evidence:  List of Phase 2 compliance-requirement records for
                              the finished goods that consume this group.

    Returns:
        (verifications, verification_confidence) where:
        - verifications: {claim_label: status}, status in {VERIFIED, UNVERIFIED, CONTRADICTED}
        - verification_confidence: float in [0,1], weighted mean (VERIFIED=1.0, UNVERIFIED=0.5, CONTRADICTED=0.0)
    """
    supplier_evidence = supplier_evidence or {}
    compliance_evidence = compliance_evidence or []

    verifications: Dict[str, str] = {}

    # Claim 1: recommended supplier name is the one in the evidence record
    expected_name = (supplier_evidence.get("name") or "").strip().lower()
    claimed_name = (proposal.recommended_supplier_name or "").strip().lower()
    if expected_name and claimed_name:
        if expected_name == claimed_name:
            verifications["supplier_identity"] = "VERIFIED"
        elif expected_name in claimed_name or claimed_name in expected_name:
            verifications["supplier_identity"] = "VERIFIED"
        else:
            verifications["supplier_identity"] = "CONTRADICTED"
    else:
        verifications["supplier_identity"] = "UNVERIFIED"

    # Claim 2: supplier certification claim matches the compliance status
    supplier_certs = supplier_evidence.get("certifications") or []
    supplier_cert_tokens = set()
    for c in supplier_certs:
        supplier_cert_tokens |= _canonical_tokens(c)

    required_tokens = set()
    for comp in compliance_evidence:
        for req in comp.get("required_certifications") or []:
            required_tokens |= _canonical_tokens(req)

    if proposal.compliance_status == "ALL_PASS":
        # Every required token should be present in supplier certs
        if not required_tokens:
            # Claim of ALL_PASS with no requirements is vacuous -> UNVERIFIED
            verifications["compliance_claims"] = "UNVERIFIED"
        elif required_tokens.issubset(supplier_cert_tokens):
            verifications["compliance_claims"] = "VERIFIED"
        else:
            verifications["compliance_claims"] = "CONTRADICTED"
    elif proposal.compliance_status in ("PARTIAL", "REVIEW_NEEDED"):
        # Partial/review-needed is inherently honest about gaps
        verifications["compliance_claims"] = "VERIFIED"
    else:  # NO_DATA or other
        verifications["compliance_claims"] = "UNVERIFIED"

    # Claim 3: consolidation footprint is internally consistent
    if proposal.companies_consolidated <= proposal.total_companies_in_group \
            and proposal.companies_consolidated >= 2:
        verifications["consolidation_footprint"] = "VERIFIED"
    else:
        verifications["consolidation_footprint"] = "CONTRADICTED"

    # Claim 4: savings claim is within the bounded heuristic range
    if 0.0 <= proposal.estimated_savings_pct <= 30.0:
        verifications["savings_bounds"] = "VERIFIED"
    else:
        verifications["savings_bounds"] = "CONTRADICTED"

    _weights = {"VERIFIED": 1.0, "UNVERIFIED": 0.5, "CONTRADICTED": 0.0}
    verification_confidence = round(
        sum(_weights.get(v, 0.5) for v in verifications.values()) / max(len(verifications), 1),
        4,
    )
    return verifications, verification_confidence


def verification_summary(verifications: Dict[str, str]) -> dict:
    """Roll up a set of verification outcomes into summary counts + pass flag."""
    counts = {"VERIFIED": 0, "UNVERIFIED": 0, "CONTRADICTED": 0}
    for v in verifications.values():
        counts[v] = counts.get(v, 0) + 1
    return {
        "counts": counts,
        "passed": counts["CONTRADICTED"] == 0,
        "all_verified": counts["UNVERIFIED"] == 0 and counts["CONTRADICTED"] == 0,
    }
