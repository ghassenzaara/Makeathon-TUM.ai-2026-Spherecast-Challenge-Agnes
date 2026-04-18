"""
Chat Agent -- LLM-powered Q&A grounded in retrieved Phase 3 proposals
+ Phase 2 enrichment evidence.

Returns the assistant's answer plus the citations it could have used. The
model is instructed to cite via stable [P12]/[E47] tags; we then map those
tags back to URL/label pairs.

If OPENAI_API_KEY is missing, falls back to a rule-based answer so the
demo still works.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.config import OPENAI_API_KEY, OPENAI_CHAT_MODEL
from backend.phase4_output.retriever import RetrievalIndex, Doc

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"\[(P\d+|E\d+)\]")


SYSTEM_PROMPT = """You are Agnes, an AI supply-chain analyst. You answer
questions about ingredient sourcing consolidation opportunities for a set of
nutraceutical companies.

Ground rules (non-negotiable):
1. Only use facts present in the CONTEXT block below. If the context does
   not answer the question, say so explicitly. Do not invent suppliers,
   certifications, savings figures, or URLs.
2. When stating a fact taken from the context, cite it inline using the
   bracketed tag of the source doc, e.g. "Prinova USA can serve 21 of 21
   companies [P1]." or "Vitamin D3 supplements typically require non-GMO
   certification [E118]."
3. Prefer concise answers (2-5 sentences). If the user asks for a list,
   use a short bulleted list with a citation per bullet.
4. Reason about tradeoffs (savings vs. concentration risk, compliance gaps,
   confidence) when relevant.
"""


def _format_context(retrieved: dict[str, list[tuple[Doc, float]]]) -> str:
    lines = ["CONTEXT:"]
    lines.append("\nProposals:")
    for doc, score in retrieved.get("proposals", []):
        lines.append(f"[{doc.doc_id}] (score={score:.2f}) {doc.text}")
    lines.append("\nEvidence:")
    for doc, score in retrieved.get("evidence", []):
        url = doc.meta.get("source_url", "")
        suffix = f" url={url}" if url else ""
        lines.append(f"[{doc.doc_id}] (score={score:.2f}){suffix} {doc.text}")
    return "\n".join(lines)


def _citations_for(retrieved: dict[str, list[tuple[Doc, float]]]) -> dict[str, dict]:
    """Map doc_id -> {label, url, kind, meta} for every retrieved doc."""
    out: dict[str, dict] = {}
    for doc, _ in retrieved.get("proposals", []):
        out[doc.doc_id] = {
            "doc_id": doc.doc_id,
            "kind": doc.kind,
            "label": f"Proposal #{doc.meta.get('proposal_id')} \u2014 {doc.meta.get('supplier_name')}",
            "url": "",
            "proposal_id": doc.meta.get("proposal_id"),
            "meta": doc.meta,
        }
    for doc, _ in retrieved.get("evidence", []):
        et = doc.meta.get("entity_type", "")
        eid = doc.meta.get("entity_id", "")
        dt = doc.meta.get("data_type", "")
        out[doc.doc_id] = {
            "doc_id": doc.doc_id,
            "kind": doc.kind,
            "label": f"Evidence ({et} {eid}, {dt})",
            "url": doc.meta.get("source_url", "") or "",
            "meta": doc.meta,
        }
    return out


def _fallback_answer(question: str, retrieved: dict[str, list[tuple[Doc, float]]]) -> str:
    """No-LLM rule-based answer that still cites the top retrieved proposals."""
    props = retrieved.get("proposals", [])
    if not props:
        return ("I could not find any matching sourcing proposals in the current "
                "Phase 3 output. Try asking about a specific ingredient or supplier.")
    bullets = []
    for doc, _ in props[:3]:
        m = doc.meta
        bullets.append(
            f"- [{doc.doc_id}] {m['supplier_name']} could serve "
            f"{m.get('savings_pct', 0):.1f}% est. savings, confidence "
            f"{m.get('confidence', 0):.0f}% (priority {m.get('priority')})."
        )
    return (
        "Based on the current Phase 3 proposals, here are the closest matches:\n"
        + "\n".join(bullets)
        + "\n\n(LLM unavailable -- showing top retrieved proposals verbatim.)"
    )


def _llm_answer(messages: list[dict], context: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    convo = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context}]
    convo.extend(messages)
    resp = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=convo,
        temperature=0.1,
    )
    return resp.choices[0].message.content or ""


def answer(messages: list[dict], index: RetrievalIndex) -> dict[str, Any]:
    """
    messages: full chat history, OpenAI format ({"role": "...", "content": "..."}).
    Returns:
        {
          "answer": str,
          "citations": [{doc_id, label, url, kind, ...}],   # only those actually cited
          "retrieved": [{doc_id, score, ...}],              # everything that was offered to the LLM
        }
    """
    user_messages = [m for m in messages if m.get("role") == "user"]
    if not user_messages:
        return {"answer": "", "citations": [], "retrieved": []}
    query = user_messages[-1]["content"]

    retrieved = index.retrieve(query)
    context = _format_context(retrieved)
    citation_pool = _citations_for(retrieved)

    if OPENAI_API_KEY:
        try:
            text = _llm_answer(messages, context)
        except Exception as e:
            logger.warning(f"LLM call failed, using fallback: {e}")
            text = _fallback_answer(query, retrieved)
    else:
        text = _fallback_answer(query, retrieved)

    cited_ids = list(dict.fromkeys(_TAG_RE.findall(text)))
    citations = [citation_pool[d] for d in cited_ids if d in citation_pool]
    retrieved_summary = []
    for kind in ("proposals", "evidence"):
        for doc, score in retrieved.get(kind, []):
            retrieved_summary.append({
                "doc_id": doc.doc_id,
                "kind": doc.kind,
                "score": round(score, 4),
                "label": citation_pool.get(doc.doc_id, {}).get("label", doc.doc_id),
                "url": citation_pool.get(doc.doc_id, {}).get("url", ""),
                "proposal_id": doc.meta.get("proposal_id"),
            })

    return {
        "answer": text,
        "citations": citations,
        "retrieved": retrieved_summary,
    }
