"""
Agnes Phase 3 Runner -- Reasoning, Optimization & Trust.

Consumes Phase 1 substitution groups and Phase 2 enrichment data to produce
ranked, confidence-scored sourcing proposals, and persists them to the
SourcingProposal table for Phase 4 consumption.

Usage:
    cd agnes/
    python -m backend.run_phase3 [--top-groups N] [--no-persist]
"""

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List

from backend.db.queries import (
    get_all_substitution_groups,
    get_substitution_group_detail,
    create_proposal_tables,
    clear_proposal_tables,
    insert_sourcing_proposal,
)
from backend.phase1_extraction.substitution_groups import (
    SubstitutionGroup, IngredientMember, SupplierInfo,
)
from backend.phase2_enrichment.enrichment_store import (
    get_supplier_info, get_compliance_requirements,
)
from backend.phase3_reasoning.substitution_validator import validate_substitution_group
from backend.phase3_reasoning.compliance_checker import check_compliance, ComplianceResult
from backend.phase3_reasoning.sourcing_optimizer import optimize_sourcing, SourcingProposal
from backend.phase3_reasoning.confidence_scorer import score_proposal_confidence
from backend.phase3_reasoning.verification_agent import verify_proposal, verification_summary
from backend.phase3_reasoning.pareto_engine import compute_pareto_frontier, rank_by_utility


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
    consumers = g_dict.get("Consumers", []) or []
    return SubstitutionGroup(
        id=g_dict["Id"],
        canonical_name=g_dict["CanonicalName"],
        members=members,
        suppliers=suppliers,
        consuming_product_ids=[c["FinishedGoodId"] for c in consumers],
        consuming_product_skus=[c["FinishedGoodSKU"] for c in consumers],
        cross_company_count=g_dict["CrossCompanyCount"],
        similarity_score=g_dict["AvgSimilarity"],
    )


def _persist_proposal(p: SourcingProposal, verifications: dict):
    summary = verification_summary(verifications)
    insert_sourcing_proposal({
        "IngredientGroupId": p.ingredient_group_id,
        "RecommendedSupplierId": p.recommended_supplier_id,
        "RecommendedSupplierName": p.recommended_supplier_name,
        "CompaniesConsolidated": p.companies_consolidated,
        "MembersServed": p.members_served,
        "TotalCompaniesInGroup": p.total_companies_in_group,
        "EstimatedSavingsPct": p.estimated_savings_pct,
        "ComplianceStatus": p.compliance_status,
        "RiskFactorsJson": json.dumps(p.risk_factors),
        "ConfidenceScore": p.confidence_score,
        "Priority": p.priority,
        "EvidenceSummary": p.evidence_summary,
        "VerificationsJson": json.dumps(verifications),
        "VerificationPassed": 1 if summary["passed"] else 0,
        "CreatedAt": datetime.now(timezone.utc).isoformat(),
        # Probabilistic / Pareto fields
        "ComplianceProbability": p.compliance_probability,
        "EvidenceStrength": p.evidence_strength,
        "RiskScore": p.risk_score,
        "UtilityScore": p.utility_score,
        "ParetoRank": p.pareto_rank,
        "IsParetoOptimal": 1 if p.is_pareto_optimal else 0,
        "DominatedByJson": json.dumps(p.dominated_by),
        "VerificationConfidence": p.verification_confidence,
    })


def run_phase3(top_groups: int = 50, persist: bool = True) -> List[SourcingProposal]:
    logger.info("=" * 60)
    logger.info("PHASE 3: Reasoning, Optimization & Trust")
    logger.info("=" * 60)

    if persist:
        clear_proposal_tables()
    else:
        create_proposal_tables()

    groups_data = get_all_substitution_groups()
    logger.info(f"Loaded {len(groups_data)} substitution groups")

    all_proposals: List[SourcingProposal] = []
    all_verifications: Dict[int, dict] = {}  # proposal.id -> verifications dict
    skipped_invalid = 0
    skipped_no_consolidation = 0

    for g_meta in groups_data[:top_groups]:
        g_detail = get_substitution_group_detail(g_meta["Id"])
        if not g_detail:
            continue
        group = dict_to_group(g_detail)

        if not group.has_consolidation_potential:
            skipped_no_consolidation += 1
            continue

        logger.info(f"Processing group: {group.canonical_name}")

        # 1. Validate substitutability (do not skip on 'review needed' -- let
        #    the confidence scorer downgrade instead, per architecture doc.)
        validation = validate_substitution_group(
            group.id, group.canonical_name,
            [m.ingredient_name for m in group.members],
        )
        if not validation.is_valid:
            logger.warning(
                f"  Skipping {group.canonical_name}: "
                f"{validation.recommendation} "
                f"(score={validation.functional_equivalence_score})"
            )
            skipped_invalid += 1
            continue

        # 2. Load supplier evidence for every supplier in the group
        supplier_data_map: Dict[int, dict] = {}
        for sid in {s.supplier_id for s in group.suppliers}:
            supplier_data_map[sid] = get_supplier_info(sid) or {}

        # 3. Compliance check per (member product, supplier) pair
        compliance_results: Dict[int, ComplianceResult] = {}
        compliance_evidence: List[dict] = []
        for member in group.members:
            reqs = get_compliance_requirements(member.product_id) or {}
            if reqs:
                compliance_evidence.append(reqs)
            required_certs = reqs.get("required_certifications", [])
            for sid, sdata in supplier_data_map.items():
                res = check_compliance(
                    product_id=member.product_id,
                    ingredient_group_id=group.id,
                    proposed_supplier_id=sid,
                    required_certs=required_certs,
                    supplier_certs=sdata.get("certifications", []),
                    supplier_website=sdata.get("website", ""),
                )
                compliance_results[member.product_id * 1_000_000 + sid] = res

        # 4. Optimize sourcing
        proposals = optimize_sourcing(group, supplier_data_map, compliance_results)

        # 5. Score + verify (collect; do NOT persist yet — Pareto runs globally after)
        for prop in proposals:
            sdata = supplier_data_map.get(prop.recommended_supplier_id, {}) or {}
            cdata_agg = compliance_evidence[0] if compliance_evidence else {}
            prop.confidence_score = score_proposal_confidence(
                prop, group, validation, sdata, cdata_agg,
            )
            verifications, ver_conf = verify_proposal(prop, sdata, compliance_evidence)
            prop.verification_confidence = ver_conf
            v_summary = verification_summary(verifications)
            # Downgrade confidence if any claim was contradicted
            if not v_summary["passed"]:
                prop.confidence_score = round(prop.confidence_score * 0.5, 1)
                prop.risk_factors.append("Verification agent flagged contradicted claims")

            all_proposals.append(prop)
            all_verifications[prop.id] = verifications
            logger.info(
                f"  {prop.recommended_supplier_name} -> "
                f"{prop.companies_consolidated}/{prop.total_companies_in_group} companies"
                f" | savings={prop.estimated_savings_pct:.1f}%"
                f" | compliance_p={prop.compliance_probability:.3f}"
            )

    # 6. Global Pareto frontier (across ALL groups — chart needs a meaningful frontier)
    if all_proposals:
        pareto_results = compute_pareto_frontier(all_proposals)
        pareto_map = {r.proposal_id: r for r in pareto_results}
        for r in pareto_results:
            for p in all_proposals:
                if p.id == r.proposal_id:
                    p.pareto_rank = r.pareto_rank
                    p.is_pareto_optimal = r.is_pareto_optimal
                    p.dominated_by = r.dominated_by
                    break

        # 7. Utility ranking (all proposals, not just frontier)
        ranked_pairs = rank_by_utility(
            all_proposals, pareto_results,
            alpha=1.0, beta=1.5, gamma=0.8,
            frontier_only=False,
        )
        for p, u in ranked_pairs:
            p.utility_score = u

        # Update priority: pareto_rank==1 + above-median utility -> HIGH
        utilities = sorted(p.utility_score for p in all_proposals)
        median_u = utilities[len(utilities) // 2] if utilities else 0.0
        for p in all_proposals:
            if p.pareto_rank == 1 and p.utility_score > median_u:
                p.priority = "HIGH"
            elif p.pareto_rank == 1:
                p.priority = "MEDIUM"
            else:
                p.priority = "LOW"

    # 8. Persist all proposals (now that Pareto fields are populated)
    if persist:
        for p in all_proposals:
            _persist_proposal(p, all_verifications.get(p.id, {}))

    logger.info("=" * 60)
    logger.info(
        f"PHASE 3 COMPLETE: {len(all_proposals)} proposals "
        f"(skipped: {skipped_invalid} invalid, "
        f"{skipped_no_consolidation} no-consolidation)"
    )
    logger.info("=" * 60)

    # Print top 5
    priority_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    all_proposals.sort(
        key=lambda p: (priority_rank.get(p.priority, 0),
                       p.confidence_score, p.estimated_savings_pct),
        reverse=True,
    )
    print("\n" + "=" * 60)
    print("TOP 5 CONSOLIDATION PROPOSALS")
    print("=" * 60)
    for i, p in enumerate(all_proposals[:5], 1):
        print(f"\n{i}. Group {p.ingredient_group_id} | {p.recommended_supplier_name}")
        print(f"   Consolidates {p.companies_consolidated}/{p.total_companies_in_group} companies ({p.members_served} SKUs)")
        print(f"   Est. savings: {p.estimated_savings_pct:.1f}% | Confidence: {p.confidence_score:.1f}%")
        print(f"   Priority: {p.priority} | Compliance: {p.compliance_status}")
        if p.risk_factors:
            print(f"   Risks: {', '.join(p.risk_factors)}")
        print(f"   Evidence: {p.evidence_summary}")

    return all_proposals


def main():
    parser = argparse.ArgumentParser(description="Run Agnes Phase 3 pipeline")
    parser.add_argument("--top-groups", type=int, default=50,
                        help="Number of top substitution groups to process")
    parser.add_argument("--no-persist", action="store_true",
                        help="Don't persist proposals to DB (dry run)")
    args = parser.parse_args()

    start = time.time()
    run_phase3(top_groups=args.top_groups, persist=not args.no_persist)
    logger.info(f"\nPhase 3 completed in {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
