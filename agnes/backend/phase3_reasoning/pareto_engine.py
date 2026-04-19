"""
Pareto frontier engine — 5-objective multi-objective ranking (NSGA-II style).

5 Objectives (aligned with the UI sliders in ParetoChart.tsx):
  1. α Savings (Impact)          — evidence-weighted savings (maximize)
  2. β Compliance Risk           — P(non-compliance), minimize
  3. γ Substitution Risk         — 1 − functional similarity, minimize
  4. δ Supplier Variance         — reliability variance / enforcement, minimize
  5. ε Uncertainty               — 1 − evidence_strength, minimize

Dominance (NSGA-II): A dominates B iff A is ≥ B on every maximize-axis and
≤ B on every minimize-axis, with at least one strictly better. We implement
this by mapping every axis to a *maximize* form (negating minimize axes).

Utility (scalarization): U = α·impact − β·p_risk − γ·s_risk − δ·r_var − ε·u
Composite Risk (UI Y-axis): weighted mean of the four risk axes using the
user-provided β, γ, δ, ε — so the chart reflects whatever the user is
currently optimizing for, rather than a hardcoded 70/30 blend.
"""

import logging
import statistics
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

_SAVINGS_SOURCE_WEIGHT = 0.9   # savings is computed deterministically


@dataclass
class ParetoResult:
    proposal_id: int
    is_pareto_optimal: bool
    pareto_rank: int                      # 1 = frontier, 2+ = dominated layers
    dominated_by: list[int]               # proposal IDs that dominate this one
    objectives: dict[str, float]          # 5-axis vector in maximize form
    impact_confidence: float = 0.0        # evidence_strength × source_weight
    flagged_low_confidence_high_impact: bool = False   # impact > median AND conf < 0.5


def compute_composite_risk(
    p_comp_risk: float,
    p_sub_risk: float,
    p_rel_var: float,
    p_uncertainty: float,
    beta: float = 1.5,
    gamma: float = 1.0,
    delta: float = 0.5,
    epsilon: float = 0.8,
) -> float:
    """
    Weighted mean of the four risk axes.

    Used for the Pareto chart's Y-axis so the displayed "Risk" responds to the
    same coefficients the user is tweaking — no hardcoded 70/30 split.
    """
    total = beta + gamma + delta + epsilon
    if total <= 0:
        return round(
            (p_comp_risk + p_sub_risk + p_rel_var + p_uncertainty) / 4.0, 4
        )
    return round(
        (
            beta * p_comp_risk
            + gamma * p_sub_risk
            + delta * p_rel_var
            + epsilon * p_uncertainty
        )
        / total,
        4,
    )


def _risk_axes(proposal) -> dict[str, float]:
    """Extract the four minimize-form risk scalars from a proposal."""
    risk_obj = getattr(proposal, "compliance_risk", {}) or {}
    p_comp = float(risk_obj.get("probability", 1.0 - getattr(proposal, "compliance_probability", 0.5)))
    ev_strength = float(getattr(proposal, "evidence_strength", 0.5))
    return {
        "compliance_risk": max(0.0, min(1.0, p_comp)),
        "substitution_risk": max(0.0, min(1.0, float(getattr(proposal, "substitution_risk", 0.0)))),
        "reliability_variance": max(0.0, min(1.0, float(getattr(proposal, "reliability_variance", 0.1)))),
        "uncertainty": max(0.0, min(1.0, 1.0 - ev_strength)),
    }


def _dominates(obj_a: dict[str, float], obj_b: dict[str, float]) -> bool:
    """
    A dominates B iff A ≥ B on all maximize-axes and A > B on at least one.
    All axes in `obj_*` are pre-converted to the maximize form.
    """
    at_least_one_better = False
    for k in obj_a:
        if obj_a[k] < obj_b[k]:
            return False
        if obj_a[k] > obj_b[k]:
            at_least_one_better = True
    return at_least_one_better


def compute_pareto_frontier(
    proposals: list,
    beta: float = 1.5,
    gamma: float = 1.0,
    delta: float = 0.5,
    epsilon: float = 0.8,
) -> list[ParetoResult]:
    """
    Assign Pareto ranks using the 5-objective NSGA-II approach and write the
    composite risk_score + impact_score back onto each proposal.

    The risk composite used for the UI Y-axis is parameterized by (β, γ, δ, ε)
    so it tracks the user's current weighting preference — not a hardcoded
    70/30 blend.

    Returns a ParetoResult per proposal, parallel to the input list.
    """
    n = len(proposals)
    if n == 0:
        return []

    results: list[ParetoResult] = []
    for p in proposals:
        risks = _risk_axes(p)
        p_comp_risk = risks["compliance_risk"]
        p_sub_risk = risks["substitution_risk"]
        p_rel_var = risks["reliability_variance"]
        p_uncertainty = risks["uncertainty"]

        # Composite risk (UI Y-axis) — dynamic, weighted by current coefficients.
        risk = compute_composite_risk(
            p_comp_risk, p_sub_risk, p_rel_var, p_uncertainty,
            beta=beta, gamma=gamma, delta=delta, epsilon=epsilon,
        )
        p.risk_score = risk

        ev_strength = getattr(p, "evidence_strength", 0.5)
        savings_norm = min(getattr(p, "estimated_savings_pct", 0.0) / 30.0, 1.0)

        # UI/Metric fields — evidence-weighted impact on the X-axis.
        impact_score = round(savings_norm * ev_strength * _SAVINGS_SOURCE_WEIGHT, 4)
        p.impact_score = impact_score
        impact_confidence = round(ev_strength * _SAVINGS_SOURCE_WEIGHT, 4)

        # Data completeness (retained for downstream consumers / flagging).
        breakdown = getattr(p, "compliance_breakdown", {}) or {}
        total_checks = sum(breakdown.values()) if breakdown else 1
        resolved = breakdown.get("compliant", 0) + breakdown.get("non_compliant", 0)
        coverage_score = resolved / total_checks if total_checks > 0 else 0.0
        data_completeness = round((coverage_score + ev_strength) / 2.0, 4)
        p.data_completeness = data_completeness

        # 5-axis Pareto objective vector in maximize form.
        # savings is maximized directly; risks/uncertainty are negated.
        objectives = {
            "savings": savings_norm,
            "neg_compliance_risk": -p_comp_risk,
            "neg_substitution_risk": -p_sub_risk,
            "neg_reliability_variance": -p_rel_var,
            "neg_uncertainty": -p_uncertainty,
        }

        results.append(ParetoResult(
            proposal_id=p.id,
            is_pareto_optimal=False,
            pareto_rank=0,
            dominated_by=[],
            objectives=objectives,
            impact_confidence=impact_confidence,
        ))

    # Pairwise dominance across the 5-dim objective space.
    dominated_count = [0] * n
    dominates: List[List[int]] = [[] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if _dominates(results[i].objectives, results[j].objectives):
                dominates[i].append(j)
                dominated_count[j] += 1

    # NSGA-II layered assignment.
    current_front = [i for i in range(n) if dominated_count[i] == 0]
    rank = 1
    while current_front:
        for i in current_front:
            results[i].pareto_rank = rank
            if rank == 1:
                results[i].is_pareto_optimal = True
        next_front: List[int] = []
        for i in current_front:
            for j in dominates[i]:
                dominated_count[j] -= 1
                if dominated_count[j] == 0:
                    next_front.append(j)
        current_front = next_front
        rank += 1

    # Fill dominated_by list using proposal IDs.
    for j in range(n):
        for i in range(n):
            if j in dominates[i]:
                results[j].dominated_by.append(proposals[i].id)

    # Flag: high impact AND low confidence.
    impact_values = [p.impact_score for p in proposals]
    median_impact = statistics.median(impact_values) if impact_values else 0.0
    proposal_map = {p.id: p for p in proposals}
    for r in results:
        proposal = proposal_map.get(r.proposal_id)
        if proposal:
            r.flagged_low_confidence_high_impact = (
                proposal.impact_score > median_impact and r.impact_confidence < 0.5
            )
            proposal.flagged_low_confidence_high_impact = r.flagged_low_confidence_high_impact

    frontier_count = sum(1 for r in results if r.is_pareto_optimal)
    logger.info(
        f"Pareto frontier (5D): {frontier_count}/{n} proposals optimal "
        f"[β={beta}, γ={gamma}, δ={delta}, ε={epsilon}]"
    )
    flagged_count = sum(1 for r in results if r.flagged_low_confidence_high_impact)
    if flagged_count:
        logger.info(f"Flagged {flagged_count} high-impact/low-confidence proposals")
    return results


def rank_by_utility(
    proposals: list,
    pareto_results: list[ParetoResult],
    alpha: float = 1.0,
    beta: float = 1.5,
    gamma: float = 1.0,
    delta: float = 0.5,
    epsilon: float = 0.8,
    frontier_only: bool = True,
) -> list[tuple]:
    """
    Scalar utility ranking over the 5 objectives:

        U = α·savings_norm
          − β·compliance_risk
          − γ·substitution_risk
          − δ·reliability_variance
          − ε·uncertainty

    Returns a list of (proposal, utility_score) sorted descending.
    """
    pareto_map: dict[int, ParetoResult] = {r.proposal_id: r for r in pareto_results}

    def _utility(p) -> float:
        savings_norm = min(getattr(p, "estimated_savings_pct", 0.0) / 30.0, 1.0)
        risks = _risk_axes(p)
        return round(
            alpha * savings_norm
            - beta * risks["compliance_risk"]
            - gamma * risks["substitution_risk"]
            - delta * risks["reliability_variance"]
            - epsilon * risks["uncertainty"],
            4,
        )

    if frontier_only:
        pool = [
            p for p in proposals
            if pareto_map.get(p.id) and pareto_map[p.id].is_pareto_optimal
        ]
    else:
        pool = proposals

    ranked = [(p, _utility(p)) for p in pool]
    ranked.sort(key=lambda x: x[1], reverse=True)
    logger.info(
        f"Utility ranking computed with "
        f"α={alpha}, β={beta}, γ={gamma}, δ={delta}, ε={epsilon} "
        f"({len(ranked)} proposals ranked)"
    )
    return ranked
