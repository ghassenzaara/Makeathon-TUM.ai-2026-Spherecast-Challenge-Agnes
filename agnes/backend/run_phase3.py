"""
Agnes Phase 3 Runner -- execute the reasoning, optimization & trust pipeline.

Usage:
    cd agnes/
    python -m backend.run_phase3
"""

import logging
import time

from backend.db.queries import get_all_substitution_groups, get_substitution_group_detail
from backend.phase1_extraction.substitution_groups import SubstitutionGroup, IngredientMember, SupplierInfo
from backend.phase2_enrichment.enrichment_store import get_supplier_info, get_compliance_requirements
from backend.phase3_reasoning.substitution_validator import validate_substitution_group
from backend.phase3_reasoning.compliance_checker import check_compliance
from backend.phase3_reasoning.sourcing_optimizer import optimize_sourcing
from backend.phase3_reasoning.confidence_scorer import score_proposal_confidence
from backend.phase3_reasoning.verification_agent import verify_proposal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)

def dict_to_group(g_dict: dict) -> SubstitutionGroup:
    members = [
        IngredientMember(
            product_id=m["ProductId"],
            sku=m["SKU"],
            company_id=m["CompanyId"],
            company_name=m["CompanyName"],
            ingredient_name=m["IngredientName"],
        ) for m in g_dict.get("Members", [])
    ]
    suppliers = [
        SupplierInfo(
            supplier_id=s["SupplierId"],
            supplier_name=s["SupplierName"],
            product_id=s["ProductId"],
        ) for s in g_dict.get("Suppliers", [])
    ]
    return SubstitutionGroup(
        id=g_dict["Id"],
        canonical_name=g_dict["CanonicalName"],
        members=members,
        suppliers=suppliers,
        cross_company_count=g_dict["CrossCompanyCount"],
        similarity_score=g_dict["AvgSimilarity"]
    )

def run_phase3():
    logger.info("=" * 60)
    logger.info("PHASE 3: Reasoning, Optimization & Trust")
    logger.info("=" * 60)
    
    # 1. Get all substitution groups
    groups_data = get_all_substitution_groups()
    logger.info(f"Loaded {len(groups_data)} substitution groups")
    
    all_proposals = []
    
    # Let's process the top 20 consolidation opportunities
    for i, g_meta in enumerate(groups_data[:20]):
        group_id = g_meta["Id"]
        g_detail = get_substitution_group_detail(group_id)
        if not g_detail: continue
        
        group = dict_to_group(g_detail)
        logger.info(f"Processing group: {group.canonical_name}")
        
        # 2. Validation
        member_names = [m.ingredient_name for m in group.members]
        validation = validate_substitution_group(group.id, group.canonical_name, member_names)
        
        if not validation.is_valid:
            logger.warning(f"  Validation failed for {group.canonical_name}: {validation.recommendation}")
            continue
            
        # 3. Compliance Checking & Supplier Data Loading
        compliance_results = {}
        supplier_data_map = {}
        
        # Load all supplier data for this group
        unique_supplier_ids = set(s.supplier_id for s in group.suppliers)
        for sid in unique_supplier_ids:
            sdata = get_supplier_info(sid) or {}
            supplier_data_map[sid] = sdata
            
        # Check compliance for each product -> supplier combo
        for member in group.members:
            reqs = get_compliance_requirements(member.product_id) or {}
            required_certs = reqs.get("required_certifications", [])
            
            for sid in unique_supplier_ids:
                sdata = supplier_data_map.get(sid, {})
                supplier_certs = sdata.get("certifications", [])
                supplier_website = sdata.get("website", "")
                
                res = check_compliance(
                    product_id=member.product_id,
                    ingredient_group_id=group.id,
                    proposed_supplier_id=sid,
                    required_certs=required_certs,
                    supplier_certs=supplier_certs,
                    supplier_website=supplier_website
                )
                compliance_results[member.product_id * 1000 + sid] = res # Unique key
                
        # 4. Optimization
        proposals = optimize_sourcing(group, supplier_data_map, compliance_results)
        
        # 5. Confidence Scoring & Verification
        for prop in proposals:
            sdata = supplier_data_map.get(prop.recommended_supplier_id, {})
            
            # Simple aggregation of compliance data for the scorer
            comp_data_agg = {"source": "mock" if sdata.get("source") == "mock" else "real"} 
            
            score = score_proposal_confidence(prop, group, validation, sdata, comp_data_agg)
            prop.confidence_score = score
            
            # Verify
            raw_evidence = {"supplier_name": sdata.get("name", "")}
            verification = verify_proposal(prop, raw_evidence)
            
            all_proposals.append(prop)
            logger.info(f"  Created proposal: {prop.recommended_supplier_name} -> {prop.companies_consolidated} companies (Confidence: {score:.1f}%)")

    logger.info("=" * 60)
    logger.info(f"PHASE 3 COMPLETE: Generated {len(all_proposals)} viable proposals")
    logger.info("=" * 60)
    
    # Print Top 5 Proposals
    all_proposals.sort(key=lambda p: (p.priority == "HIGH", p.estimated_savings_pct, p.confidence_score), reverse=True)
    
    print("\n" + "="*60)
    print("TOP 5 CONSOLIDATION PROPOSALS")
    print("="*60)
    for i, p in enumerate(all_proposals[:5]):
        print(f"\n{i+1}. Group ID: {p.ingredient_group_id} | Supplier: {p.recommended_supplier_name}")
        print(f"   Companies consolidated: {p.companies_consolidated}")
        print(f"   Estimated Savings: {p.estimated_savings_pct:.1f}%")
        print(f"   Confidence Score: {p.confidence_score:.1f}%")
        print(f"   Priority: {p.priority}")
        print(f"   Compliance Status: {p.compliance_status}")

if __name__ == "__main__":
    start = time.time()
    run_phase3()
    elapsed = time.time() - start
    logger.info(f"\nPhase 3 completed in {elapsed:.1f}s")
