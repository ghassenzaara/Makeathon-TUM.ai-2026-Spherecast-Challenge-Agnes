# agnes_core.py — Retrieval-grounded reasoning engine for Agnes chatbot.
# Replaces the legacy root-level agnes_core.py that relied on ai_context.txt.

import os
import re
import sys
import json
import time
import logging
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# ── Path setup ───────────────────────────────────────────────────
# This file lives at agnes/backend/chatbot/. Adjust sys.path so that:
#   - "backend.*" resolves (parent of backend/ is agnes/)
#   - "scraper" resolves (scraper.py is at the repo root)
_CHATBOT_DIR = Path(__file__).parent
_AGNES_DIR   = _CHATBOT_DIR.parent.parent   # agnes/
_REPO_ROOT   = _AGNES_DIR.parent            # repo root

for _p in (_AGNES_DIR, _REPO_ROOT):
    _p_str = str(_p)
    if _p_str not in sys.path:
        sys.path.insert(0, _p_str)

from backend.phase4_output.retriever import build_or_load_index, RetrievalIndex
from prompts import AGNES_SYSTEM_PROMPT, QUERY_TEMPLATE
import scraper

load_dotenv(_REPO_ROOT / ".env")

logger = logging.getLogger(__name__)

# ── Module-level singletons ──────────────────────────────────────
_CLIENT: Optional[OpenAI]         = None
_INDEX:  Optional[RetrievalIndex] = None

# ── Configuration ────────────────────────────────────────────────
MODEL_NAME        = "gpt-4o-mini"
TEMPERATURE       = 0.1
MAX_OUTPUT_TOKENS = 8192
MAX_RETRIES       = 2
K_PROPOSALS       = 3
K_EVIDENCE        = 5


def _get_client() -> OpenAI:
    """Lazily initializes and returns the OpenAI client."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY not found in environment.\n"
            "Set it in your .env file at the repo root."
        )
    _CLIENT = OpenAI(api_key=api_key)
    print("  [AUTH] Connected via OpenAI API key")
    return _CLIENT


def _get_index(force_rebuild: bool = False) -> RetrievalIndex:
    """
    Builds (or loads from cache) the Phase 4 RetrievalIndex.
    Cached globally so the embedding step runs only once per session.
    Raises RuntimeError if phases 1-3 have not been run yet.
    """
    global _INDEX
    if _INDEX is not None and not force_rebuild:
        return _INDEX

    print("  [INDEX] Loading Phase 4 retrieval index...")
    _INDEX = build_or_load_index(force_rebuild=force_rebuild)

    if not _INDEX.docs:
        raise RuntimeError(
            "Phase 4 index is empty.\n"
            "Run the pipeline first:\n"
            "  python agnes/backend/run_phase1.py\n"
            "  python agnes/backend/run_phase2.py\n"
            "  python agnes/backend/run_phase3.py\n"
            "  python agnes/backend/run_phase4.py"
        )

    proposal_count = sum(1 for d in _INDEX.docs if d.kind == "proposal")
    evidence_count = sum(1 for d in _INDEX.docs if d.kind == "evidence")
    print(
        f"  [INDEX] Ready — {proposal_count} proposals, "
        f"{evidence_count} evidence docs, backend={_INDEX.backend}"
    )
    return _INDEX


def _get_group_companies(group_id: int) -> list[str]:
    """Returns distinct company names belonging to a SubstitutionGroup."""
    try:
        from backend.db.connection import get_cursor
        with get_cursor() as cur:
            cur.execute(
                "SELECT DISTINCT CompanyName FROM SubstitutionGroupMember WHERE GroupId = ? ORDER BY CompanyName",
                (group_id,),
            )
            return [row["CompanyName"] for row in cur.fetchall()]
    except Exception:
        return []


def _get_group_suppliers(group_id: int) -> list[str]:
    """Returns distinct current supplier names for a SubstitutionGroup."""
    try:
        from backend.db.connection import get_cursor
        with get_cursor() as cur:
            cur.execute(
                "SELECT DISTINCT SupplierName FROM SubstitutionGroupSupplier WHERE GroupId = ? ORDER BY SupplierName",
                (group_id,),
            )
            return [row["SupplierName"] for row in cur.fetchall()]
    except Exception:
        return []


def _format_retrieved(results: dict) -> tuple[str, str]:
    """
    Converts retrieve() output into two plain-text blocks for the LLM prompt.
    Enriches each proposal with real company and supplier names from the DB so
    the LLM never has to guess them.
    Similarity scores are hidden to prevent the LLM from anchoring on them.
    """
    proposal_lines: list[str] = []
    for doc, _score in results["proposals"]:
        group_id   = doc.meta.get("ingredient_group_id")
        companies  = _get_group_companies(group_id)  if group_id else []
        suppliers  = _get_group_suppliers(group_id)  if group_id else []

        companies_str = ", ".join(companies) if companies else "NOT_AVAILABLE"
        suppliers_str = ", ".join(suppliers) if suppliers else "NOT_AVAILABLE"

        proposal_lines.append(
            f"[{doc.doc_id}] {doc.text}"
            f" Companies in this group: {companies_str}."
            f" Current suppliers in this group: {suppliers_str}."
        )

    evidence_lines: list[str] = []
    for doc, _score in results["evidence"]:
        url_hint = f" (source: {doc.meta['source_url']})" if doc.meta.get("source_url") else ""
        evidence_lines.append(f"[{doc.doc_id}]{url_hint} {doc.text}")

    proposals_block = "\n".join(proposal_lines) if proposal_lines else "NO_PROPOSALS_RETRIEVED"
    evidence_block  = "\n".join(evidence_lines)  if evidence_lines  else "NO_EVIDENCE_RETRIEVED"
    return proposals_block, evidence_block


def build_retrieval_prompt(
    proposals_text: str,
    evidence_text: str,
    user_query: str,
    fallback_scrape: dict | None = None,
) -> str:
    """
    Assembles the LLM prompt from retrieved Phase 4 data.
    fallback_scrape is only present when retrieval returned 0 proposals for
    a supplier that was explicitly named in the query.
    """
    if fallback_scrape:
        evidence_text += (
            "\n\n=== FALLBACK LIVE SCRAPE (retrieval was empty for this supplier) ===\n"
            + scraper.format_for_prompt(fallback_scrape)
        )

    return QUERY_TEMPLATE.format(
        proposals=proposals_text,
        evidence=evidence_text,
        query=user_query,
    )


def call_llm(prompt: str, system_prompt: str) -> str:
    """Makes a single call to GPT-4o-mini with exponential-backoff retry."""
    client = _get_client()

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_OUTPUT_TOKENS,
            )
            text = response.choices[0].message.content
            if text and text.strip():
                return text
            raise ValueError("Empty response from LLM")

        except Exception as e:
            error_str  = str(e).lower()
            error_type = type(e).__name__
            print(f"  [DEBUG] {error_type}: {str(e)[:200]}")

            is_rate_limit = any(kw in error_str for kw in [
                "rate_limit", "429", "rate", "quota", "too many requests",
            ])
            if is_rate_limit:
                wait = (2 ** attempt) * 5
                print(f"  [WAIT] Rate limited. Retrying in {wait}s...")
                time.sleep(wait)
                continue
            elif attempt < MAX_RETRIES:
                print(f"  [WARN] {error_type}: {str(e)[:150]}. Retrying...")
                time.sleep(2)
                continue
            else:
                raise RuntimeError(
                    f"LLM API failed after {MAX_RETRIES + 1} attempts ({error_type}): {e}"
                )

    raise RuntimeError("LLM API failed: exhausted all retries")


def parse_response(raw_response: str) -> dict:
    """
    Extracts and validates JSON from the LLM response.
    Tries four strategies: direct parse, markdown fence strip,
    first-brace extraction, trailing-comma cleanup.
    """
    text = raw_response.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    brace_start = text.find('{')
    brace_end   = text.rfind('}')
    if brace_start != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            candidate = re.sub(r',\s*([}\]])', r'\1', text[brace_start:brace_end + 1])
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    raise ValueError(f"Could not parse JSON from LLM response.\nFirst 500 chars: {text[:500]}")


def ask_agnes(query: str) -> dict:
    """
    PUBLIC API — entry point for every chatbot query.
    Pipeline: index → retrieve → format → prompt → LLM → parse.

    Returns a structured dict with keys:
      query, substitution_groups, consolidation_summary,
      overall_confidence, data_gaps, _meta
    """
    t_start = time.time()

    # Step 1: Load Phase 4 index
    print("  [1/5] Loading Phase 4 retrieval index...")
    index = _get_index()

    # Step 2: Semantic retrieval
    print("  [2/5] Retrieving top proposals + evidence for query...")
    results     = index.retrieve(query, k_proposals=K_PROPOSALS, k_evidence=K_EVIDENCE)
    n_proposals = len(results["proposals"])
    n_evidence  = len(results["evidence"])
    print(f"     Retrieved {n_proposals} proposals, {n_evidence} evidence docs")

    # Step 3: Scraper fallback — only when retrieval is empty AND a known
    # supplier is explicitly mentioned in the query
    fallback_scrape: dict | None = None
    fallback_triggered = False
    if n_proposals == 0:
        mentioned = [
            name for name in scraper.SUPPLIER_URLS
            if name.lower() in query.lower()
        ]
        if mentioned:
            print(f"  [3/5] Retrieval empty — fallback scrape for: {mentioned}")
            fallback_scrape    = scraper.scrape_multiple(mentioned)
            fallback_triggered = True
        else:
            print("  [3/5] Retrieval empty, no known supplier mentioned — skipping scrape")
    else:
        print("  [3/5] Retrieval populated — scraper not needed")

    # Step 4: Assemble prompt
    print("  [4/5] Building retrieval-grounded prompt...")
    proposals_text, evidence_text = _format_retrieved(results)
    prompt = build_retrieval_prompt(proposals_text, evidence_text, query, fallback_scrape)
    prompt_tokens_est = len(prompt) // 4
    print(f"     Estimated prompt size: ~{prompt_tokens_est:,} tokens")

    # Step 5: Call LLM + parse
    print(f"  [5/5] Calling {MODEL_NAME}...")
    raw_response = call_llm(prompt, AGNES_SYSTEM_PROMPT)
    t_elapsed    = time.time() - t_start
    print(f"     Response received in {t_elapsed:.1f}s ({len(raw_response):,} chars)")

    try:
        result = parse_response(raw_response)
    except ValueError as e:
        result = {
            "raw_response": raw_response,
            "parse_error": str(e),
            "substitution_groups": [],
            "consolidation_summary": "Failed to parse structured response. See raw_response.",
            "overall_confidence": 0.0,
            "data_gaps": ["Response parsing failed"],
        }

    result["query"] = query
    result["_meta"] = {
        "model":                    MODEL_NAME,
        "proposals_retrieved":      n_proposals,
        "evidence_retrieved":       n_evidence,
        "index_backend":            index.backend,
        "fallback_scrape_triggered": fallback_triggered,
        "prompt_tokens_est":        prompt_tokens_est,
        "response_time_s":          round(t_elapsed, 1),
    }
    return result
