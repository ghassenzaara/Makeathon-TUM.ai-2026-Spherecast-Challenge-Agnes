"""
Sourcing Optimizer -- generates consolidation proposals.

For a given substitution group, rank candidate suppliers by how many of the
group's companies they could serve, then compute per-supplier savings,
compliance status, and risk factors.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List
import logging

from backend.phase1_extraction.substitution_groups import SubstitutionGroup
from backend.phase3_reasoning.compliance_checker import ComplianceResult

logger = logging.getLogger(__name__)


@dataclass
class SourcingProposal:
    id: int
    ingredient_group_id: int
    recommended_supplier_id: int
    recommended_supplier_name: str
    companies_consolidated: int       # # of companies this supplier could serve
    members_served: int               # # of raw-material products covered
    total_companies_in_group: int     # group's full footprint (for context)
    estimated_savings_pct: float
    compliance_status: str            # "ALL_PASS" | "PARTIAL" | "REVIEW_NEEDED" | "NO_DATA"
    risk_factors: List[str]
    confidence_score: float           # set later by confidence_scorer
    priority: str                     # "HIGH" | "MEDIUM" | "LOW"
    evidence_summary: str = ""


def _supplier_reach(group: SubstitutionGroup) -> Dict[int, dict]:
    """
    Build {supplier_id: {name, member_product_ids, company_ids}} from the
    group's supplier relationships. A supplier's "reach" is measured in
    distinct company_ids it could serve within this group.
    """
    member_to_company = {m.product_id: m.company_id for m in group.members}
    reach: Dict[int, dict] = defaultdict(
        lambda: {"name": "", "member_product_ids": set(), "company_ids": set()}
    )
    for s in group.suppliers:
        bucket = reach[s.supplier_id]
        bucket["name"] = s.supplier_name
        company_id = member_to_company.get(s.product_id)
        if company_id is not None:
            bucket["company_ids"].add(company_id)
            bucket["member_product_ids"].add(s.product_id)
    return reach


def _compliance_status_for_supplier(
    supplier_id: int,
    group_product_ids: set,
    compliance_results: Dict[int, ComplianceResult],
) -> str:
    """
    Aggregate compliance results across members of THIS group only.
    """
    relevant = [
        r for r in compliance_results.values()
        if r.proposed_supplier_id == supplier_id
        and r.product_id in group_product_ids
    ]
    if not relevant:
        return "NO_DATA"
    if all(r.all_passed for r in relevant):
        return "ALL_PASS"
    passing = sum(1 for r in relevant if r.all_passed)
    if passing == 0:
        return "REVIEW_NEEDED"
    return "PARTIAL"


def optimize_sourcing(
    group: SubstitutionGroup,
    supplier_data: Dict[int, dict],
    compliance_results: Dict[int, ComplianceResult],
    top_n: int = 3,
) -> List[SourcingProposal]:
    """
    Generate sourcing proposals for a given substitution group.
    Only groups with consolidation potential (>=2 companies) produce proposals.
    """
    proposals: List[SourcingProposal] = []
    if not group.has_consolidation_potential:
        return proposals

    reach = _supplier_reach(group)
    if not reach:
        return proposals

    total_companies = len(set(m.company_id for m in group.members))
    group_product_ids = {m.product_id for m in group.members}

    # Rank suppliers by the distinct-company footprint they cover within the group
    ranked = sorted(
        reach.items(),
        key=lambda item: (len(item[1]["company_ids"]), len(item[1]["member_product_ids"])),
        reverse=True,
    )

    for i, (sid, info) in enumerate(ranked[:top_n]):
        companies_served = len(info["company_ids"])
        members_served = len(info["member_product_ids"])
        if companies_served < 2:
            # Not actually consolidating anything; skip
            continue

        status = _compliance_status_for_supplier(
            sid, group_product_ids, compliance_results
        )

        # Savings heuristic: scale with share of the group's companies this
        # supplier can serve. Max 30% when the supplier covers every company.
        coverage_ratio = companies_served / max(total_companies, 1)
        savings_pct = round(min(30.0, (companies_served - 1) * 5.0 * coverage_ratio + 5.0), 1)

        risk_factors: List[str] = []
        if coverage_ratio >= 0.8:
            risk_factors.append("Single-supplier concentration risk")
        if status in ("PARTIAL", "REVIEW_NEEDED"):
            risk_factors.append("Compliance gaps require review")
        if status == "NO_DATA":
            risk_factors.append("No compliance data available")
        sdata = supplier_data.get(sid, {}) or {}
        if not sdata.get("certifications"):
            risk_factors.append("Supplier certifications unverified")

        if status == "ALL_PASS" and coverage_ratio >= 0.5:
            priority = "HIGH"
        elif status in ("ALL_PASS", "PARTIAL") and coverage_ratio >= 0.3:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        hq = sdata.get("headquarters", "")
        evidence = (
            f"{info['name']} can serve {companies_served} of "
            f"{total_companies} companies in the '{group.canonical_name}' "
            f"group ({members_served} SKUs)."
        )
        if hq:
            evidence += f" HQ: {hq}."

        proposals.append(SourcingProposal(
            id=(group.id or 0) * 100 + i,
            ingredient_group_id=group.id or 0,
            recommended_supplier_id=sid,
            recommended_supplier_name=info["name"],
            companies_consolidated=companies_served,
            members_served=members_served,
            total_companies_in_group=total_companies,
            estimated_savings_pct=savings_pct,
            compliance_status=status,
            risk_factors=risk_factors,
            confidence_score=0.0,
            priority=priority,
            evidence_summary=evidence,
        ))

    return proposals
