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
    alpha: float = 1.0
    beta: float = 1.5
    gamma: float = 0.8


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
        }
        for p in proposals
    ]


@app.post("/api/proposals/rerank")
def rerank_proposals(req: RerankRequest):
    """
    Recompute utility in-memory with new alpha/beta/gamma weights.
    Reads from startup cache; no DB writes. Latency < 5 ms for ~150 proposals.
    """
    results = []
    for p in _proposals_cache:
        comp_prob = p.get("ComplianceProbability") or 0.5
        concentration = (p.get("CompaniesConsolidated") or 1) / max(p.get("TotalCompaniesInGroup") or 1, 1)
        ver_conf = p.get("VerificationConfidence") or 0.5
        risk = round(
            0.4 * (1.0 - comp_prob)
            + 0.3 * concentration
            + 0.3 * (1.0 - ver_conf),
            4,
        )
        savings_norm = (p.get("EstimatedSavingsPct") or 0.0) / 30.0
        ev_strength = p.get("EvidenceStrength") or 0.5
        uncertainty = 1.0 - ev_strength
        u = round(req.alpha * savings_norm - req.beta * risk - req.gamma * uncertainty, 4)
        impact_score = p.get("ImpactScore") or round(savings_norm * ev_strength * 0.9, 4)
        impact_confidence = round(ev_strength * 0.9, 4)
        results.append({
            "id": p["Id"],
            "utility_score": u,
            "savings": p.get("EstimatedSavingsPct", 0.0),
            "compliance_probability": comp_prob,
            "risk_score": risk,
            "is_pareto_optimal": bool(p.get("IsParetoOptimal", 0)),
            "dominated_by": json.loads(p.get("DominatedByJson", "[]") or "[]"),
            "recommended_supplier_name": p.get("RecommendedSupplierName", ""),
            "impact_score": impact_score,
            "impact_confidence": impact_confidence,
            "flagged_low_confidence_high_impact": bool(p.get("FlaggedLowConfHighImpact", 0)),
        })
    results.sort(key=lambda x: x["utility_score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1
    return results


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
