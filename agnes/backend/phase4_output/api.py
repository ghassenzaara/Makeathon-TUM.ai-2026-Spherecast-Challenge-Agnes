"""
Phase 4 FastAPI service -- powers the Agnes dashboard + chat UI.

Run from agnes/:
    uvicorn backend.phase4_output.api:app --reload --port 8000
"""

from __future__ import annotations

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Phase 4 API starting up -- building retrieval index...")
    _state["index"] = build_or_load_index(force_rebuild=False)
    logger.info(f"Index ready ({len(_state['index'].docs)} docs).")
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
        }
        for p in proposals
    ]


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
    return trail


@app.post("/api/chat")
def chat(req: ChatRequest):
    index = _state.get("index")
    if not index:
        raise HTTPException(status_code=503, detail="Retrieval index not ready")
    msgs = [m.model_dump() for m in req.messages]
    return chat_answer(msgs, index, proposal_id=req.proposal_id)
