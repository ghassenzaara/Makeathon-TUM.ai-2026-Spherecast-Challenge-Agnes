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
    get_fda_risk, get_entity_verification,
)
from backend.phase3_reasoning.substitution_validator import validate_substitution_group
from backend.phase3_reasoning.compliance_checker import check_compliance, ComplianceResult
from backend.phase3_reasoning.sourcing_optimizer import optimize_sourcing, SourcingProposal
from backend.phase3_reasoning.confidence_scorer import score_proposal_confidence
from backend.phase3_reasoning.verification_agent import verify_proposal, verification_summary
from backend.phase3_reasoning.pareto_engine import compute_pareto_frontier, rank_by_utility
from backend.phase3_reasoning.evidence_model import AggregatedMetric, Signal, SourceType, aggregate


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


def _build_score_breakdown(p: SourcingProposal) -> AggregatedMetric:
    """
    Aggregate compliance, savings, and risk signals into the proposal's
    final uncertainty-aware score breakdown.
    """
    savings_norm = min(p.estimated_savings_pct / 30.0, 1.0)
    signals = [
        Signal(
            value=p.compliance_probability,
            confidence=p.evidence_strength,
            source_type=SourceType.DETERMINISTIC,
            importance=0.6,
            label="Compliance",
        ),
        Signal(
            value=savings_norm,
            confidence=0.80,
            source_type=SourceType.DETERMINISTIC,
            importance=0.8,
            label="Savings Potential",
        ),
        Signal(
            value=max(0.0, 1.0 - p.risk_score),
            confidence=p.verification_confidence,
            source_type=SourceType.DETERMINISTIC,
            importance=0.7,
            label="Risk Profile",
        ),
    ]
    metric = aggregate(signals, expected_count=3)

    # Override uncertainty_sources with domain-specific reasons
    reasons = []
    if p.evidence_strength < 0.5:
        reasons.append("Compliance evidence uncertain — limited supplier cert data")
    if p.verification_confidence < 0.5:
        reasons.append("Verification confidence below threshold")
    if any("certifications unverified" in r for r in p.risk_factors):
        reasons.append("Supplier certifications not verified externally")
    if any("FDA enforcement" in r for r in p.risk_factors):
        reasons.append("FDA enforcement history detected — review required")
    if any("Dissolved" in r for r in p.risk_factors):
        reasons.append("Supplier entity status flagged as Dissolved")
    metric.uncertainty_sources = reasons or metric.uncertainty_sources
    return metric


def _persist_proposal(p: SourcingProposal, verifications: dict):
    summary = verification_summary(verifications)
    score_bd = p.score_breakdown.to_dict() if p.score_breakdown else None
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
        # Uncertainty-aware fields
        "ScoreBreakdownJson": json.dumps(score_bd),
        "ComplianceBreakdownJson": json.dumps(p.compliance_breakdown),
        "ImpactScore": p.impact_score,
        "FlaggedLowConfHighImpact": 1 if p.flagged_low_confidence_high_impact else 0,
        "ComplianceRiskJson": json.dumps(p.compliance_risk),
        "SubstitutionRisk": p.substitution_risk,
        "CostScore": p.cost_score,
        "ReliabilityVariance": p.reliability_variance,
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
        supplier_ids = {s.supplier_id for s in group.suppliers}
        supplier_data_map: Dict[int, dict] = {}
        fda_data_map: Dict[int, dict] = {}
        entity_data_map: Dict[int, dict] = {}
        for sid in supplier_ids:
            supplier_data_map[sid] = get_supplier_info(sid) or {}
            fda_data_map[sid] = get_fda_risk(sid) or {}
            entity_data_map[sid] = get_entity_verification(sid) or {}

        # 3. Compliance check per (member product, supplier) pair.
        #
        # FIX: compliance_requirements are stored for FG (finished-good) product
        # IDs, NOT for RM (raw-material) IDs used in SubstitutionGroupMember.
        # We take the UNION of required certs across every FG that consumes
        # this group (conservative: if any FG needs Organic, we require it).
        compliance_results: Dict[int, ComplianceResult] = {}
        compliance_evidence: List[dict] = []

        fg_required_certs: set = set()
        for fg_id in (group.consuming_product_ids or []):
            fg_reqs = get_compliance_requirements(fg_id) or {}
            if fg_reqs:
                compliance_evidence.append(fg_reqs)
            fg_required_certs.update(fg_reqs.get("required_certifications", []))
        required_certs = sorted(fg_required_certs)
        for member in group.members:
            for sid, sdata in supplier_data_map.items():
                fda = fda_data_map.get(sid) or {}
                # Derive fda-compliant from enforcement data: every supplier is
                # presumed FDA-registered unless they carry an active Warning.
                # This turns the always-UNKNOWN "fda-compliant" requirement into
                # a real differentiating signal without inventing certifications.
                inferred_certs = list(sdata.get("certifications", []))
                if fda.get("status") != "Warning":
                    inferred_certs.append("fda-compliant")

                res = check_compliance(
                    product_id=member.product_id,
                    ingredient_group_id=group.id,
                    proposed_supplier_id=sid,
                    required_certs=required_certs,
                    supplier_certs=inferred_certs,
                    supplier_website=sdata.get("website", ""),
                )
                compliance_results[member.product_id * 1_000_000 + sid] = res

        # 4. Optimize sourcing
        proposals = optimize_sourcing(
            group, supplier_data_map, compliance_results,
            fda_data_map=fda_data_map,
            entity_data_map=entity_data_map,
        )

        # 5. Score + verify (collect; do NOT persist yet — Pareto runs globally after)
        for prop in proposals:
            sdata = supplier_data_map.get(prop.recommended_supplier_id, {}) or {}
            cdata_agg = compliance_evidence[0] if compliance_evidence else {}
            sid = prop.recommended_supplier_id
            prop.confidence_score = score_proposal_confidence(
                prop, group, validation, sdata, cdata_agg,
                fda_data=fda_data_map.get(sid),
                entity_data=entity_data_map.get(sid),
            )
            verifications, ver_conf = verify_proposal(
                prop, sdata, compliance_evidence,
                fda_data=fda_data_map.get(sid),
                entity_data=entity_data_map.get(sid),
            )
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
        for r in pareto_results:
            for p in all_proposals:
                if p.id == r.proposal_id:
                    p.pareto_rank = r.pareto_rank
                    p.is_pareto_optimal = r.is_pareto_optimal
                    p.dominated_by = r.dominated_by
                    break

        # Build score_breakdown for each proposal (requires Pareto fields to be set)
        for p in all_proposals:
            p.score_breakdown = _build_score_breakdown(p)

        # 7. Utility ranking (all proposals, not just frontier) — 5 coefficients
        ranked_pairs = rank_by_utility(
            all_proposals, pareto_results,
            alpha=1.0, beta=1.5, gamma=1.0, delta=0.5, epsilon=0.8,
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
        print(f"   Est. savings: {p.estimated_savings_pct:.1f}% | Impact: {p.impact_score:.3f}")
        bd = p.score_breakdown
        if bd:
            print(
                f"   Score: value={bd.value:.3f} conf={bd.confidence:.3f} "
                f"cov={bd.coverage:.2f}"
            )
            print(f"   compliance_score={p.compliance_probability:.3f} "
                  f"(conf={p.evidence_strength:.3f}, "
                  f"breakdown={p.compliance_breakdown})")
        else:
            print(f"   Confidence: {p.confidence_score:.1f}%")
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
