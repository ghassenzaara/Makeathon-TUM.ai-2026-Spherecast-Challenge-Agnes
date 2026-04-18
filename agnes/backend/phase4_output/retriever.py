"""
Phase 4 Retriever -- in-memory embedding index over sourcing proposals
and Phase 2 enrichment records, used to ground chat answers.

Two corpora:
  * proposals: one doc per SourcingProposal (with evidence summary, risks, etc.).
  * evidence:  one doc per Enrichment row (supplier_info, compliance_requirements,
               product_scrape).

Embeddings persist to agnes/data/phase4_index.npz alongside a sidecar JSON
listing each doc's text/metadata. Pass force_rebuild=True to refresh.

If OPENAI_API_KEY is missing, falls back to a deterministic
character-trigram TF-IDF-style sparse index so the system still demos.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from backend.config import (
    DATA_DIR,
    GEMINI_API_KEY,
    GEMINI_EMBEDDING_MODEL,
    EMBEDDING_BATCH_SIZE,
)
from backend.db.connection import get_cursor
from backend.db.queries import get_all_sourcing_proposals

logger = logging.getLogger(__name__)

_INDEX_PATH = DATA_DIR / "phase4_index.npz"
_DOCS_PATH = DATA_DIR / "phase4_docs.json"


@dataclass
class Doc:
    doc_id: str            # "P12" or "E47"
    kind: str              # "proposal" | "evidence"
    text: str
    meta: dict             # arbitrary lookup data (proposal_id, supplier_id, url, etc.)


# ──────────────────────────────────────────────
# Document construction
# ──────────────────────────────────────────────

def _proposal_text(p: dict) -> str:
    return (
        f"Sourcing proposal for ingredient group {p['IngredientGroupId']}. "
        f"Recommended supplier: {p['RecommendedSupplierName']}. "
        f"Consolidates {p['CompaniesConsolidated']} of {p['TotalCompaniesInGroup']} companies "
        f"({p['MembersServed']} SKUs). "
        f"Estimated savings: {p['EstimatedSavingsPct']:.1f}%. "
        f"Confidence: {p['ConfidenceScore']:.0f}%. "
        f"Priority: {p['Priority']}. "
        f"Compliance status: {p['ComplianceStatus']}. "
        f"Risks: {p['RiskFactorsJson']}. "
        f"Evidence: {p['EvidenceSummary']}"
    )


def _enrichment_text(row: dict, data: dict) -> str:
    bits = [f"{row['EntityType']} {row['EntityId']} ({row['DataType']})."]
    for k, v in data.items():
        if k.startswith("_"):
            continue
        if isinstance(v, list):
            v = ", ".join(map(str, v))
        bits.append(f"{k}: {v}")
    return " ".join(bits)


def _load_corpus() -> list[Doc]:
    docs: list[Doc] = []
    proposals = get_all_sourcing_proposals()
    for p in proposals:
        docs.append(Doc(
            doc_id=f"P{p['Id']}",
            kind="proposal",
            text=_proposal_text(p),
            meta={
                "proposal_id": p["Id"],
                "ingredient_group_id": p["IngredientGroupId"],
                "supplier_id": p["RecommendedSupplierId"],
                "supplier_name": p["RecommendedSupplierName"],
                "priority": p["Priority"],
                "confidence": p["ConfidenceScore"],
                "savings_pct": p["EstimatedSavingsPct"],
            },
        ))
    with get_cursor() as cur:
        cur.execute("""
            SELECT Id, EntityType, EntityId, DataType, DataJson, SourceUrl, Confidence
            FROM Enrichment
        """)
        rows = cur.fetchall()
    for r in rows:
        try:
            data = json.loads(r["DataJson"])
        except Exception:
            data = {}
        docs.append(Doc(
            doc_id=f"E{r['Id']}",
            kind="evidence",
            text=_enrichment_text(r, data),
            meta={
                "enrichment_id": r["Id"],
                "entity_type": r["EntityType"],
                "entity_id": r["EntityId"],
                "data_type": r["DataType"],
                "source_url": r["SourceUrl"] or "",
                "confidence": r["Confidence"],
            },
        ))
    return docs


# ──────────────────────────────────────────────
# Embedding backends
# ──────────────────────────────────────────────

def _openai_embed(texts: list[str]) -> np.ndarray:
    from openai import OpenAI, RateLimitError
    import time
    client = OpenAI(api_key=OPENAI_API_KEY)
    out = []
    # Force a smaller batch size to avoid exceeding TPM limit in a single request
    actual_batch_size = min(EMBEDDING_BATCH_SIZE, 25) 
    for i in range(0, len(texts), actual_batch_size):
        batch = texts[i : i + actual_batch_size]
        while True:
            try:
                resp = client.embeddings.create(model=OPENAI_EMBEDDING_MODEL, input=batch)
                out.extend([e.embedding for e in resp.data])
                break
            except RateLimitError as e:
                logger.warning(f"OpenAI TPM limit hit. Sleeping for 20 seconds... ({e})")
                time.sleep(20)
    arr = np.array(out, dtype=np.float32)
    # L2-normalize so cosine = dot product
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def _trigrams(text: str) -> list[str]:
    t = " " + text.lower() + " "
    return [t[i:i + 3] for i in range(len(t) - 2)]


def _hash_embed(texts: list[str], dim: int = 512) -> np.ndarray:
    """Cheap, deterministic fallback. Hashes character trigrams into a fixed
    dim, L2-normalized. Good enough to demo retrieval without an API key."""
    out = np.zeros((len(texts), dim), dtype=np.float32)
    for i, txt in enumerate(texts):
        counts = Counter(_trigrams(txt))
        for tri, c in counts.items():
            h = hash(tri) % dim
            out[i, h] += float(c)
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return out / norms


def _embed(texts: list[str], using_gemini: bool) -> np.ndarray:
    if using_gemini:
        return _gemini_embed(texts)
    return _hash_embed(texts)


# ──────────────────────────────────────────────
# Index lifecycle
# ──────────────────────────────────────────────

class RetrievalIndex:
    def __init__(self, docs: list[Doc], embeddings: np.ndarray, backend: str):
        self.docs = docs
        self.embeddings = embeddings
        self.backend = backend
        self._id_to_doc = {d.doc_id: d for d in docs}

    def get(self, doc_id: str) -> Optional[Doc]:
        return self._id_to_doc.get(doc_id)

    def search(self, query: str, k: int = 8, kind: Optional[str] = None, proposal_id: Optional[int] = None, ingredient_group_id: Optional[int] = None, supplier_id: Optional[str] = None) -> list[tuple[Doc, float]]:
        if not self.docs:
            return []
        q_vec = _embed([query], using_gemini=(self.backend == "gemini"))[0]
        sims = self.embeddings @ q_vec
        
        if proposal_id or ingredient_group_id or supplier_id:
            for i, d in enumerate(self.docs):
                boost = 0.0
                if d.kind == "proposal" and proposal_id is not None:
                    if d.meta.get("proposal_id") == proposal_id:
                        boost += 0.5
                elif d.kind == "evidence":
                    et = d.meta.get("entity_type")
                    eid = d.meta.get("entity_id")
                    if supplier_id and et == "SUPPLIER" and str(eid) == str(supplier_id):
                        boost += 0.5
                    if ingredient_group_id and et == "INGREDIENT_GROUP" and str(eid) == str(ingredient_group_id):
                        boost += 0.5
                sims[i] += boost
                
        order = np.argsort(-sims)
        results: list[tuple[Doc, float]] = []
        for idx in order:
            d = self.docs[int(idx)]
            if kind and d.kind != kind:
                continue
            results.append((d, float(sims[int(idx)])))
            if len(results) >= k:
                break
        return results

    def retrieve(self, query: str, k_proposals: int = 5, k_evidence: int = 8, proposal_id: Optional[int] = None, ingredient_group_id: Optional[int] = None, supplier_id: Optional[str] = None) -> dict[str, list[tuple[Doc, float]]]:
        return {
            "proposals": self.search(query, k=k_proposals, kind="proposal", proposal_id=proposal_id, ingredient_group_id=ingredient_group_id, supplier_id=supplier_id),
            "evidence": self.search(query, k=k_evidence, kind="evidence", proposal_id=proposal_id, ingredient_group_id=ingredient_group_id, supplier_id=supplier_id),
        }


def _save(docs: list[Doc], embeddings: np.ndarray, backend: str):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(str(_INDEX_PATH), embeddings=embeddings)
    payload = {
        "backend": backend,
        "docs": [
            {"doc_id": d.doc_id, "kind": d.kind, "text": d.text, "meta": d.meta}
            for d in docs
        ],
    }
    _DOCS_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _try_load() -> Optional[RetrievalIndex]:
    if not (_INDEX_PATH.exists() and _DOCS_PATH.exists()):
        return None
    try:
        npz = np.load(str(_INDEX_PATH))
        embeddings = npz["embeddings"]
        payload = json.loads(_DOCS_PATH.read_text(encoding="utf-8"))
        docs = [Doc(**d) for d in payload["docs"]]
        if len(docs) != embeddings.shape[0]:
            return None
        return RetrievalIndex(docs, embeddings, payload.get("backend", "hash"))
    except Exception as e:
        logger.warning(f"Failed to load cached Phase 4 index: {e}")
        return None


def build_or_load_index(force_rebuild: bool = False) -> RetrievalIndex:
    if not force_rebuild:
        cached = _try_load()
        if cached:
            logger.info(
                f"Loaded Phase 4 retrieval index from cache "
                f"({len(cached.docs)} docs, backend={cached.backend})"
            )
            return cached

    docs = _load_corpus()
    if not docs:
        logger.warning("Phase 4 corpus is empty -- did you run phases 1-3?")
        return RetrievalIndex([], np.zeros((0, 0), dtype=np.float32), "hash")

    using_gemini = bool(GEMINI_API_KEY)
    backend = "gemini" if using_gemini else "hash"
    logger.info(
        f"Building Phase 4 retrieval index: {len(docs)} docs, backend={backend}"
    )
    embeddings = _embed([d.text for d in docs], using_gemini=using_gemini)
    _save(docs, embeddings, backend)
    return RetrievalIndex(docs, embeddings, backend)
