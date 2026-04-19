"""
Phase 4 FastAPI service -- powers the Agnes dashboard + chat UI.

Run from agnes/:
    uvicorn backend.phase4_output.api:app --reload --port 8000
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.db.queries import (
    get_all_sourcing_proposals,
    get_sourcing_proposal,
    get_substitution_group_detail,
)
from backend.phase3_reasoning.pareto_engine import compute_composite_risk
from backend.phase4_output.evidence_trail_builder import build_evidence_trail
from backend.phase4_output.retriever import build_or_load_index
from backend.phase4_output.chat_agent import answer as chat_answer

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_state: dict[str, Any] = {"index": None}
_proposals_cache: list[dict] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _proposals_cache
    logger.info("Phase 4 API starting up -- building retrieval index...")
    _state["index"] = build_or_load_index(force_rebuild=False)
    logger.info(f"Index ready ({len(_state['index'].docs)} docs).")
    _proposals_cache = get_all_sourcing_proposals()
    logger.info(f"Loaded {len(_proposals_cache)} proposals into rerank cache.")
    yield


app = FastAPI(title="Agnes Phase 4 API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    proposal_id: int | None = None


class RerankRequest(BaseModel):
    alpha: float = 1.0  # Savings/Cost weight
    beta: float = 1.5   # Compliance Risk penalty
    gamma: float = 1.0  # Substitution Risk penalty
    delta: float = 0.5  # Reliability Variance penalty
    epsilon: float = 0.8 # Uncertainty (Evidence Strength) weight


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "docs_indexed": len(_state["index"].docs) if _state.get("index") else 0}


@app.get("/api/stats")
def stats():
    proposals = get_all_sourcing_proposals()
    if not proposals:
        return {"proposal_count": 0}
    avg_conf = sum(p["ConfidenceScore"] for p in proposals) / len(proposals)
    avg_savings = sum(p["EstimatedSavingsPct"] for p in proposals) / len(proposals)
    by_priority = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    by_compliance: dict[str, int] = {}
    verified = 0
    for p in proposals:
        by_priority[p["Priority"]] = by_priority.get(p["Priority"], 0) + 1
        by_compliance[p["ComplianceStatus"]] = by_compliance.get(p["ComplianceStatus"], 0) + 1
        if p["VerificationPassed"]:
            verified += 1
    return {
        "proposal_count": len(proposals),
        "verified_count": verified,
        "avg_confidence": round(avg_conf, 1),
        "avg_savings_pct": round(avg_savings, 1),
        "by_priority": by_priority,
        "by_compliance": by_compliance,
    }


@app.get("/api/proposals")
def list_proposals():
    proposals = get_all_sourcing_proposals()
    return [
        {
            "id": p["Id"],
            "ingredient_group_id": p["IngredientGroupId"],
            "recommended_supplier_id": p["RecommendedSupplierId"],
            "recommended_supplier_name": p["RecommendedSupplierName"],
            "companies_consolidated": p["CompaniesConsolidated"],
            "members_served": p["MembersServed"],
            "total_companies_in_group": p["TotalCompaniesInGroup"],
            "estimated_savings_pct": p["EstimatedSavingsPct"],
            "compliance_status": p["ComplianceStatus"],
            "confidence_score": p["ConfidenceScore"],
            "priority": p["Priority"],
            "verification_passed": bool(p["VerificationPassed"]),
            "canonical_name": _canonical_for_group(p["IngredientGroupId"]),
            # Probabilistic / Pareto fields
            "compliance_probability": p.get("ComplianceProbability", 0.5),
            "evidence_strength": p.get("EvidenceStrength", 0.5),
            "risk_score": p.get("RiskScore", 0.0),
            "utility_score": p.get("UtilityScore", 0.0),
            "pareto_rank": p.get("ParetoRank", 0),
            "is_pareto_optimal": bool(p.get("IsParetoOptimal", 0)),
            "dominated_by": json.loads(p.get("DominatedByJson", "[]") or "[]"),
            "verification_confidence": p.get("VerificationConfidence", 0.5),
            # Uncertainty-aware fields
            "score_breakdown": json.loads(p.get("ScoreBreakdownJson", "null") or "null"),
            "compliance_breakdown": json.loads(p.get("ComplianceBreakdownJson", "{}") or "{}"),
            "impact_score": p.get("ImpactScore", 0.0),
            "flagged_low_confidence_high_impact": bool(p.get("FlaggedLowConfHighImpact", 0)),
            # Fix 3: New Multi-Objective Axes
            "compliance_risk": json.loads(p.get("ComplianceRiskJson", "{}") or "{}"),
            "substitution_risk": p.get("SubstitutionRisk", 0.0),
            "cost_score": p.get("CostScore", 1.0),
            "reliability_variance": p.get("ReliabilityVariance", 0.1),
        }
        for p in proposals
    ]


@app.post("/api/proposals/rerank")
def rerank_proposals(req: RerankRequest):
    """
    Recompute utility + Pareto frontier in-memory with new α/β/γ/δ/ε weights.

    Utility: U = α·savings − β·comp_risk − γ·sub_risk − δ·rel_var − ε·uncertainty
    Risk (Y-axis): weighted mean of the four risk axes using the same β/γ/δ/ε,
    so the chart tracks the user's current preference dynamically.
    Dominance: 5D NSGA-II style (A dominates B iff ≥ on all and > on one).

    Reads from startup cache; no DB writes. Latency < 5 ms for ~150 proposals.
    """
    rows = []
    for p in _proposals_cache:
        savings_norm = min((p.get("EstimatedSavingsPct") or 0.0) / 30.0, 1.0)

        # Prefer the stored compliance_risk vector when present; otherwise
        # fall back to (1 − compliance_probability).
        try:
            risk_vec = json.loads(p.get("ComplianceRiskJson") or "{}") or {}
        except (ValueError, TypeError):
            risk_vec = {}
        c_risk = (
            risk_vec.get("probability")
            if risk_vec.get("probability") is not None
            else 1.0 - (p.get("ComplianceProbability") or 0.5)
        )
        s_risk = p.get("SubstitutionRisk") or 0.0
        r_var = p.get("ReliabilityVariance") or 0.1
        ev_strength = p.get("EvidenceStrength") or 0.5
        uncertainty = 1.0 - ev_strength

        # Dynamic composite risk driven by the current coefficients.
        risk_score = compute_composite_risk(
            c_risk, s_risk, r_var, uncertainty,
            beta=req.beta, gamma=req.gamma, delta=req.delta, epsilon=req.epsilon,
        )

        u = round(
            req.alpha * savings_norm
            - req.beta * c_risk
            - req.gamma * s_risk
            - req.delta * r_var
            - req.epsilon * uncertainty,
            4,
        )

        rows.append({
            "id": p["Id"],
            "utility_score": u,
            "savings": p.get("EstimatedSavingsPct", 0.0),
            "compliance_probability": p.get("ComplianceProbability", 0.5),
            "risk_score": risk_score,
            "substitution_risk": s_risk,
            "reliability_variance": r_var,
            "recommended_supplier_name": p.get("RecommendedSupplierName", ""),
            "companies_consolidated": p.get("CompaniesConsolidated", 2),
            "canonical_name": _canonical_for_group(p["IngredientGroupId"]),
            "impact_score": p.get("ImpactScore") or round(savings_norm * ev_strength * 0.9, 4),
            "impact_confidence": round(ev_strength * 0.9, 4),
            "flagged_low_confidence_high_impact": bool(p.get("FlaggedLowConfHighImpact", 0)),
            # 5D maximize-form objective vector for dominance.
            "_obj": (
                savings_norm,
                -max(0.0, min(1.0, c_risk)),
                -max(0.0, min(1.0, s_risk)),
                -max(0.0, min(1.0, r_var)),
                -max(0.0, min(1.0, uncertainty)),
            ),
        })

    # 5D Pareto dominance — recomputed so the frontier responds to new weights
    # only through the Y-axis composite; the frontier itself is weight-free
    # (NSGA-II on the raw 5-axis vector).
    n = len(rows)
    for i in range(n):
        rows[i]["is_pareto_optimal"] = True
        rows[i]["dominated_by"] = []
    for i in range(n):
        a = rows[i]["_obj"]
        for j in range(n):
            if i == j:
                continue
            b = rows[j]["_obj"]
            # j dominates i iff b ≥ a on all axes and > on at least one.
            better_or_equal = all(bv >= av for bv, av in zip(b, a))
            strictly_better = any(bv > av for bv, av in zip(b, a))
            if better_or_equal and strictly_better:
                rows[i]["is_pareto_optimal"] = False
                rows[i]["dominated_by"].append(rows[j]["id"])

    for r in rows:
        r.pop("_obj", None)

    rows.sort(key=lambda x: x["utility_score"], reverse=True)
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


_canonical_cache: dict[int, str] = {}


def _canonical_for_group(group_id: int) -> str:
    if group_id in _canonical_cache:
        return _canonical_cache[group_id]
    g = get_substitution_group_detail(group_id) or {}
    name = g.get("CanonicalName", f"group {group_id}")
    _canonical_cache[group_id] = name
    return name


@app.get("/api/proposals/{proposal_id}")
def get_proposal(proposal_id: int):
    p = get_sourcing_proposal(proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    trail = build_evidence_trail(proposal_id)
    trail["score_breakdown"] = json.loads(p.get("ScoreBreakdownJson", "null") or "null")
    trail["compliance_breakdown"] = json.loads(p.get("ComplianceBreakdownJson", "{}") or "{}")
    trail["impact_score"] = p.get("ImpactScore", 0.0)
    trail["flagged_low_confidence_high_impact"] = bool(p.get("FlaggedLowConfHighImpact", 0))
    return trail


@app.post("/api/chat")
def chat(req: ChatRequest):
    index = _state.get("index")
    if not index:
        raise HTTPException(status_code=503, detail="Retrieval index not ready")
    msgs = [m.model_dump() for m in req.messages]
    return chat_answer(msgs, index, proposal_id=req.proposal_id)
