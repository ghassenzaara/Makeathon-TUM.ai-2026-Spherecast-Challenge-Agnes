"""
Pareto frontier engine — multi-objective ranking for sourcing proposals.

Objectives (all to maximize):
  savings    = estimated_savings_pct / 30.0
  compliance = compliance_probability
  neg_risk   = 1 - risk_score

Dominance: A dominates B iff A >= B on all objectives AND A > B on >= 1.
Layering: NSGA-II style, O(N^2). N ~ 150 proposals at demo scale.

Utility: U = alpha*savings_norm - beta*risk_score - gamma*uncertainty
  uncertainty = 1 - evidence_strength
  (chosen over entropy: directly interpretable, no information-theoretic prereqs)

Risk model (structured heuristic decomposition, weights are design choices):
  risk = 0.4*(1 - compliance_probability)
       + 0.3*concentration_risk          (= companies_consolidated / total_companies)
       + 0.3*(1 - verification_confidence)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ParetoResult:
    proposal_id: int
    is_pareto_optimal: bool
    pareto_rank: int                      # 1 = frontier, 2+ = dominated layers
    dominated_by: List[int]               # proposal IDs that dominate this one
    objectives: Dict[str, float]          # {"savings", "compliance", "neg_risk"}


def _compute_risk_score(proposal) -> float:
    """
    Structured decomposition into three interpretable risk factors.
    All inputs are in [0,1]; result is in [0,1].
    """
    compliance_prob = getattr(proposal, "compliance_probability", 0.5)
    concentration = proposal.companies_consolidated / max(proposal.total_companies_in_group, 1)
    verification_conf = getattr(proposal, "verification_confidence", 0.5)
    return round(
        0.4 * (1.0 - compliance_prob)
        + 0.3 * concentration
        + 0.3 * (1.0 - verification_conf),
        4,
    )


def _dominates(obj_a: Dict[str, float], obj_b: Dict[str, float]) -> bool:
    """A dominates B iff A >= B on all objectives AND A > B on at least one."""
    at_least_one_better = False
    for k in obj_a:
        if obj_a[k] < obj_b[k]:
            return False
        if obj_a[k] > obj_b[k]:
            at_least_one_better = True
    return at_least_one_better


def compute_pareto_frontier(proposals: List) -> List[ParetoResult]:
    """
    Assign Pareto ranks to all proposals and write risk_score back onto each.

    Returns a ParetoResult per proposal, parallel to the input list.
    """
    n = len(proposals)
    if n == 0:
        return []

    # Compute risk_score and build objective vectors
    results: List[ParetoResult] = []
    for p in proposals:
        risk = _compute_risk_score(p)
        p.risk_score = risk  # write back so utility + DB persistence can use it
        comp_prob = getattr(p, "compliance_probability", 0.5)
        objectives = {
            "savings": p.estimated_savings_pct / 30.0,
            "compliance": comp_prob,
            "neg_risk": 1.0 - risk,
        }
        results.append(ParetoResult(
            proposal_id=p.id,
            is_pareto_optimal=False,
            pareto_rank=0,
            dominated_by=[],
            objectives=objectives,
        ))

    # Compute pairwise dominance
    dominated_count = [0] * n
    dominates: List[List[int]] = [[] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if _dominates(results[i].objectives, results[j].objectives):
                dominates[i].append(j)
                dominated_count[j] += 1

    # NSGA-II layered assignment
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

    # Fill dominated_by (list of proposal IDs that dominate each proposal)
    for j in range(n):
        for i in range(n):
            if j in dominates[i]:
                results[j].dominated_by.append(proposals[i].id)

    frontier_count = sum(1 for r in results if r.is_pareto_optimal)
    logger.info(f"Pareto frontier: {frontier_count}/{n} proposals optimal")
    return results


def rank_by_utility(
    proposals: List,
    pareto_results: List[ParetoResult],
    alpha: float = 1.0,
    beta: float = 1.5,
    gamma: float = 0.8,
    frontier_only: bool = True,
) -> List[Tuple]:
    """
    Sort proposals by utility score with the given weights.

    uncertainty = 1 - evidence_strength (avoids entropy; directly interpretable).
    Returns list of (proposal, utility_score) sorted descending.
    """
    pareto_map: Dict[int, ParetoResult] = {r.proposal_id: r for r in pareto_results}

    def _utility(p) -> float:
        savings_norm = p.estimated_savings_pct / 30.0
        risk = getattr(p, "risk_score", 0.0)
        ev_strength = getattr(p, "evidence_strength", 0.5)
        uncertainty = 1.0 - ev_strength
        return round(alpha * savings_norm - beta * risk - gamma * uncertainty, 4)

    if frontier_only:
        pool = [p for p in proposals if pareto_map.get(p.id) and pareto_map[p.id].is_pareto_optimal]
    else:
        pool = proposals

    ranked = [(p, _utility(p)) for p in pool]
    ranked.sort(key=lambda x: x[1], reverse=True)
    logger.info(
        f"Utility ranking computed with α={alpha}, β={beta}, γ={gamma} "
        f"({len(ranked)} proposals ranked)"
    )
    return ranked
