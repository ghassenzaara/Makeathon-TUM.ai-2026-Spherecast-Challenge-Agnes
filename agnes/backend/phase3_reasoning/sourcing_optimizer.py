"""
Sourcing Optimizer -- generates consolidation proposals.

Ranks suppliers for a substitution group based on how many companies they
could serve, their compliance pass rate, and basic heuristics.
"""

from dataclasses import dataclass, field
from typing import List, Dict
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
    companies_consolidated: int
    estimated_savings_pct: float
    compliance_status: str       # "ALL_PASS" / "PARTIAL" / "REVIEW_NEEDED"
    risk_factors: List[str]
    confidence_score: float      # 0-100
    priority: str                # "HIGH" / "MEDIUM" / "LOW"
    evidence_summary: str = ""

def optimize_sourcing(
    group: SubstitutionGroup,
    supplier_data: Dict[int, dict],
    compliance_results: Dict[int, ComplianceResult]
) -> List[SourcingProposal]:
    """
    Generate sourcing proposals for a given substitution group.
    """
    proposals = []
    
    if not group.has_consolidation_potential:
        return proposals
        
    # Count how many products each supplier in the group can supply
    supplier_counts = {}
    for s in group.suppliers:
        supplier_counts[s.supplier_id] = supplier_counts.get(s.supplier_id, 0) + 1
        
    # Rank suppliers
    ranked_suppliers = sorted(supplier_counts.keys(), key=lambda sid: supplier_counts[sid], reverse=True)
    
    for i, sid in enumerate(ranked_suppliers[:3]): # Top 3 proposals max
        # Check overall compliance status for this supplier across products
        relevant_compliance = [res for key, res in compliance_results.items() if res.proposed_supplier_id == sid]
        
        all_passed = all(r.all_passed for r in relevant_compliance) if relevant_compliance else False
        status = "ALL_PASS" if all_passed else "REVIEW_NEEDED"
        
        # Estimate savings: simple heuristic -> 5% per consolidated company
        companies_served = len(set(m.company_id for m in group.members))
        savings_pct = min((companies_served - 1) * 5.0, 30.0) # Cap at 30%
        
        # Determine priority
        priority = "HIGH" if savings_pct >= 15 and all_passed else "MEDIUM"
        if not all_passed:
            priority = "LOW"
            
        supplier_name = next(s.supplier_name for s in group.suppliers if s.supplier_id == sid)
        
        proposals.append(SourcingProposal(
            id=group.id * 100 + i, # Simple ID scheme
            ingredient_group_id=group.id,
            recommended_supplier_id=sid,
            recommended_supplier_name=supplier_name,
            companies_consolidated=companies_served,
            estimated_savings_pct=savings_pct,
            compliance_status=status,
            risk_factors=["Single supplier dependency"] if companies_served > 3 else [],
            confidence_score=0.0, # Will be set by confidence_scorer
            priority=priority,
            evidence_summary=f"Supplier {supplier_name} can potentially serve {companies_served} different companies."
        ))
        
    return proposals
