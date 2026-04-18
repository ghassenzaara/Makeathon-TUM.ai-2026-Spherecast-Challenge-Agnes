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
    fda_data: dict = None,
    entity_data: dict = None,
) -> Dict[str, str]:
    """
    Args:
        supplier_evidence:    Phase 2 supplier record for the proposed supplier.
        compliance_evidence:  Phase 2 compliance-requirement records for the
                              finished goods that consume this group.
        fda_data:             OpenFDA enforcement risk record (optional).
        entity_data:          OpenCorporates entity verification record (optional).

    Returns:
        {claim_label: status} where status ∈ {VERIFIED, UNVERIFIED, CONTRADICTED}.
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

    # Claim 5: FDA enforcement — no active recalls/enforcement actions
    fda_status = (fda_data or {}).get("status", "")
    if fda_status == "Clear":
        verifications["fda_enforcement_clear"] = "VERIFIED"
    elif fda_status == "Warning":
        verifications["fda_enforcement_clear"] = "CONTRADICTED"
    else:
        verifications["fda_enforcement_clear"] = "UNVERIFIED"

    # Claim 6: supplier is an active registered business entity
    entity_status = (entity_data or {}).get("status", "")
    if entity_status == "Active":
        verifications["supplier_entity_active"] = "VERIFIED"
    elif entity_status == "Dissolved":
        verifications["supplier_entity_active"] = "CONTRADICTED"
    else:
        verifications["supplier_entity_active"] = "UNVERIFIED"

    return verifications


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
