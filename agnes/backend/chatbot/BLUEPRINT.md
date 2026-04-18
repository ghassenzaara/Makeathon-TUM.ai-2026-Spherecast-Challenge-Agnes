# Agnes Chatbot — Refactored Architecture Blueprint

> **Branch:** Ghassen
> **Date:** 2026-04-18
> **Scope:** Drop `ai_context.txt` + naïve RAG. Wire the chatbot exclusively
> to the Phase 4 `RetrievalIndex`. The backend pipeline (`agnes/backend/`) is
> **read-only**; only the chatbot layer changes.

---

## 0. File Plan — What Gets Created and What Gets Deleted

> **This is the most important section. Read it before anything else.**

### New files — to be created in this folder

```
agnes/backend/chatbot/agnes_core.py   ← NEW chatbot reasoning engine
agnes/backend/chatbot/prompts.py      ← NEW retrieval-grounded prompt templates
agnes/backend/chatbot/main.py         ← NEW CLI entry point
```

`agnes_core.py` inside this `chatbot/` directory is the **replacement** for the
legacy file. It imports from `backend.phase4_output.retriever` instead of reading
`ai_context.txt`. All chatbot logic lives here going forward.

### Old files — to be deleted from the repo root

```
agnes_core.py    ← DELETE  (legacy flat-file pipeline, replaced by chatbot/agnes_core.py)
prompts.py       ← DELETE  (legacy prompts, replaced by chatbot/prompts.py)
main.py          ← DELETE  (legacy CLI, replaced by chatbot/main.py)
```

Do **not** modify these files — delete them outright once the new `chatbot/`
versions are tested and working.

### Files that stay completely untouched

```
scraper.py              ← kept as-is; imported by chatbot/agnes_core.py as fallback
agnes/backend/**        ← strictly read-only Source of Truth
ai_context.txt          ← no longer read by anything; can be archived
```

---

## 1. The Problem with the Current Architecture

| Layer | Current Behaviour | Problem |
|:---|:---|:---|
| **Data source** | Reads `ai_context.txt` (144 KB flat file) into a single LLM prompt | LLM invents metrics not present in the pipeline's computed data |
| **Retrieval** | Regex supplier extraction + full-text dump to GPT-4o-mini | All 1 974 lines regardless of query relevance — noisy, slow, expensive |
| **Scoring** | LLM computes scores from raw text | Diverges from Phase 3's deterministic `ConfidenceScore` and `EstimatedSavingsPct` |
| **Compliance evidence** | Real-time `scraper.py` during the chat turn | Duplicates Phase 2 enrichment already stored in the `Enrichment` table |
| **Grounding** | None — nothing stops hallucinated supplier names or certifications | Answers are not reproducible against the frontend dashboards |

---

## 2. Target Architecture

```
USER QUERY
    │
    ▼
agnes_core.ask_agnes(query)
    │
    ├─[1] build_or_load_index()              ← Phase 4 retrieval index (cached)
    │      from backend.phase4_output.retriever
    │
    ├─[2] index.retrieve(query,              ← semantic search over two corpora
    │       k_proposals=3, k_evidence=5)
    │      returns {
    │        "proposals": [(Doc, score), ...],   ← SourcingProposal rows
    │        "evidence":  [(Doc, score), ...],   ← Enrichment rows
    │      }
    │
    ├─[3] _format_retrieved(results)         ← render Doc.text blocks for prompt
    │
    ├─[4] build_retrieval_prompt(            ← new prompt template (prompts.py)
    │       proposals_text,
    │       evidence_text,
    │       user_query)
    │
    ├─[5] call_llm(prompt, AGNES_SYSTEM_PROMPT)   ← GPT-4o-mini, temp=0.1
    │
    ├─[6] parse_response(raw)                ← unchanged JSON extraction logic
    │
    └─[7] return structured dict
```

**Scraper fallback (conditional):**
Only fires when ALL of the following are true:
1. `retrieve()` returns zero proposals (`len(results["proposals"]) == 0`)
2. The query explicitly names a supplier not yet in the index
3. A specific supplier URL is known in `scraper.SUPPLIER_URLS`

In all other cases `scraper.py` is **not called**.

---

## 3. Files Changed vs. Unchanged

| File | Action | Notes |
|:---|:---|:---|
| `agnes_core.py` | **Rewrite** | Delete `load_context`, `_extract_all_suppliers`, `extract_relevant_suppliers`, `build_mega_prompt`. Add `_build_or_load_index`, `_format_retrieved`, new `build_retrieval_prompt` wrapper, updated `ask_agnes`. |
| `prompts.py` | **Rewrite** | New `AGNES_SYSTEM_PROMPT` + `RETRIEVAL_QUERY_TEMPLATE` replacing the flat-file `QUERY_TEMPLATE`. |
| `main.py` | **Minor edit** | Remove `/fast`, `/scrape`, `/cache` commands. Remove `skip_scraping` param from `ask_agnes` calls. |
| `scraper.py` | **Keep, untouched** | Called only by the fallback branch in `ask_agnes`. |
| `agnes/backend/**` | **No changes** | Source of Truth — strictly read-only. |
| `ai_context.txt` | **No longer used** | May be archived; chatbot never reads it. |
| `clean_data.py` | **No longer used** | Pipeline phases 1-3 replace it. |

---

## 4. Deleted Functions in `agnes_core.py`

```python
# DELETE these entirely — replaced by RetrievalIndex
def load_context(filepath: str = CONTEXT_FILE) -> str: ...
def _extract_all_suppliers(context: str) -> list[str]: ...
def extract_relevant_suppliers(query: str, context: str) -> list[str]: ...
def build_mega_prompt(context: str, external_data: dict, user_query: str) -> str: ...

# DELETE these module-level globals
_CONTEXT_CACHE: Optional[str] = None
_ALL_SUPPLIERS: Optional[list[str]] = None
CONTEXT_FILE = "ai_context.txt"
```

---

## 5. New `agnes_core.py` — Full Specification

### 5.1 Module-level state

```python
# agnes_core.py

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

# Add repo root so "backend.*" imports resolve when running from repo root
sys.path.insert(0, str(Path(__file__).parent / "agnes"))

from backend.phase4_output.retriever import build_or_load_index, RetrievalIndex
from prompts import AGNES_SYSTEM_PROMPT, RETRIEVAL_QUERY_TEMPLATE
import scraper

load_dotenv()

logger = logging.getLogger(__name__)

# ── Module-level singletons ──────────────────────────────────────
_CLIENT:  Optional[OpenAI]          = None
_INDEX:   Optional[RetrievalIndex]  = None   # Phase 4 index cache

# ── Configuration ────────────────────────────────────────────────
MODEL_NAME        = "gpt-4o-mini"
TEMPERATURE       = 0.1
MAX_OUTPUT_TOKENS = 8192
MAX_RETRIES       = 2
K_PROPOSALS       = 3    # top-k proposals returned per query
K_EVIDENCE        = 5    # top-k evidence docs returned per query
```

### 5.2 `_get_client()` — unchanged

```python
def _get_client() -> OpenAI:
    """Lazily initializes and returns the OpenAI client."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY not found in environment.\n"
            "Set it in your .env file."
        )
    _CLIENT = OpenAI(api_key=api_key)
    print("  [AUTH] Connected via OpenAI API key")
    return _CLIENT
```

### 5.3 `_get_index()` — NEW

```python
def _get_index(force_rebuild: bool = False) -> RetrievalIndex:
    """
    Builds (or loads from cache) the Phase 4 RetrievalIndex.
    Cached globally so the heavy embedding step runs only once per session.

    The index is persisted to agnes/data/phase4_index.npz + phase4_docs.json
    by build_or_load_index() itself — no extra persistence needed here.

    Raises RuntimeError if the pipeline has not been run yet (empty corpus).
    """
    global _INDEX
    if _INDEX is not None and not force_rebuild:
        return _INDEX

    print("  [INDEX] Loading Phase 4 retrieval index...")
    _INDEX = build_or_load_index(force_rebuild=force_rebuild)

    if not _INDEX.docs:
        raise RuntimeError(
            "Phase 4 index is empty.\n"
            "Run phases 1-3 first:  python agnes/backend/run_phase1.py  (etc.)"
        )

    proposal_count = sum(1 for d in _INDEX.docs if d.kind == "proposal")
    evidence_count = sum(1 for d in _INDEX.docs if d.kind == "evidence")
    print(
        f"  [INDEX] Ready — {proposal_count} proposals, "
        f"{evidence_count} evidence docs, backend={_INDEX.backend}"
    )
    return _INDEX
```

### 5.4 `_format_retrieved()` — NEW

```python
def _format_retrieved(results: dict) -> tuple[str, str]:
    """
    Converts retrieve() output into two plain-text blocks for the LLM prompt.

    Args:
        results: dict returned by RetrievalIndex.retrieve()
                 {"proposals": [(Doc, float), ...], "evidence": [(Doc, float), ...]}

    Returns:
        (proposals_block, evidence_block) — formatted strings ready for injection
        into RETRIEVAL_QUERY_TEMPLATE.

    The LLM is given doc_id references so it can cite P12, E47, etc.
    Similarity scores are not exposed to the LLM (prevents score anchoring).
    """
    proposal_lines: list[str] = []
    for doc, _score in results["proposals"]:
        proposal_lines.append(f"[{doc.doc_id}] {doc.text}")

    evidence_lines: list[str] = []
    for doc, _score in results["evidence"]:
        url_hint = f" (source: {doc.meta['source_url']})" if doc.meta.get("source_url") else ""
        evidence_lines.append(f"[{doc.doc_id}]{url_hint} {doc.text}")

    proposals_block = (
        "\n".join(proposal_lines)
        if proposal_lines
        else "NO_PROPOSALS_RETRIEVED"
    )
    evidence_block = (
        "\n".join(evidence_lines)
        if evidence_lines
        else "NO_EVIDENCE_RETRIEVED"
    )
    return proposals_block, evidence_block
```

### 5.5 `build_retrieval_prompt()` — NEW (replaces `build_mega_prompt`)

```python
def build_retrieval_prompt(
    proposals_text: str,
    evidence_text: str,
    user_query: str,
    fallback_scrape: dict | None = None,
) -> str:
    """
    Assembles the LLM prompt from retrieved Phase 4 data.

    Args:
        proposals_text:   Formatted SourcingProposal docs from _format_retrieved()
        evidence_text:    Formatted Enrichment docs from _format_retrieved()
        user_query:       The user's natural language question
        fallback_scrape:  Optional live scrape dict (only present when retrieval
                          returned 0 proposals for a named supplier)

    Returns: Complete prompt string for call_llm()
    """
    fallback_section = ""
    if fallback_scrape:
        fallback_section = (
            "\n=== FALLBACK LIVE SCRAPE (retrieval was empty for this supplier) ===\n"
            + scraper.format_for_prompt(fallback_scrape)
            + "\n"
        )

    return RETRIEVAL_QUERY_TEMPLATE.format(
        proposals=proposals_text,
        evidence=evidence_text,
        fallback=fallback_section,
        query=user_query,
    )
```

### 5.6 `call_llm()` — unchanged from current implementation

No changes to signature, retry logic, or error handling.

### 5.7 `parse_response()` — unchanged from current implementation

No changes — the 4-attempt JSON extraction cascade remains identical.

### 5.8 `ask_agnes()` — REWRITTEN

```python
def ask_agnes(query: str) -> dict:
    """
    PUBLIC API — entry point for every chatbot query.
    Orchestrates: index → retrieve → format → prompt → LLM → parse.

    The skip_scraping parameter is REMOVED. Scraping is an automatic fallback
    triggered only when retrieve() returns no proposals for a named supplier.

    Args:
        query: Natural language question about the supply chain.

    Returns: Structured recommendation dict with keys:
        {
          "query": str,
          "substitution_groups": [...],
          "consolidation_summary": str,
          "overall_confidence": float,
          "data_gaps": [...],
          "_meta": {
              "model": str,
              "proposals_retrieved": int,
              "evidence_retrieved": int,
              "index_backend": str,
              "fallback_scrape_triggered": bool,
              "response_time_s": float,
          }
        }
    """
    t_start = time.time()

    # Step 1: Load Phase 4 index
    print("  [1/5] Loading Phase 4 retrieval index...")
    index = _get_index()

    # Step 2: Semantic retrieval
    print(f"  [2/5] Retrieving top proposals + evidence for query...")
    results = index.retrieve(query, k_proposals=K_PROPOSALS, k_evidence=K_EVIDENCE)
    n_proposals = len(results["proposals"])
    n_evidence  = len(results["evidence"])
    print(f"     Retrieved {n_proposals} proposals, {n_evidence} evidence docs")

    # Step 3: Scraper fallback — only when retrieval returns nothing AND
    # a known supplier name appears in the query
    fallback_scrape: dict | None = None
    fallback_triggered = False
    if n_proposals == 0:
        mentioned_suppliers = [
            name for name in scraper.SUPPLIER_URLS
            if name.lower() in query.lower()
        ]
        if mentioned_suppliers:
            print(
                f"  [3/5] Retrieval empty — running fallback scrape for: "
                f"{mentioned_suppliers}"
            )
            fallback_scrape = scraper.scrape_multiple(mentioned_suppliers)
            fallback_triggered = True
        else:
            print("  [3/5] Retrieval empty and no known supplier mentioned — skipping scrape")
    else:
        print("  [3/5] Retrieval populated — scraper not needed")

    # Step 4: Assemble prompt
    print("  [4/5] Building retrieval-grounded prompt...")
    proposals_text, evidence_text = _format_retrieved(results)
    prompt = build_retrieval_prompt(
        proposals_text, evidence_text, query, fallback_scrape
    )
    prompt_tokens_est = len(prompt) // 4
    print(f"     Estimated prompt size: ~{prompt_tokens_est:,} tokens")

    # Step 5: Call LLM + parse
    print(f"  [5/5] Calling {MODEL_NAME}...")
    raw_response = call_llm(prompt, AGNES_SYSTEM_PROMPT)
    t_elapsed = time.time() - t_start
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
        "model": MODEL_NAME,
        "proposals_retrieved": n_proposals,
        "evidence_retrieved": n_evidence,
        "index_backend": index.backend,
        "fallback_scrape_triggered": fallback_triggered,
        "prompt_tokens_est": prompt_tokens_est,
        "response_time_s": round(t_elapsed, 1),
    }
    return result
```

---

## 6. New `prompts.py` — Full Specification

```python
# prompts.py — Prompt templates for retrieval-grounded chatbot

AGNES_SYSTEM_PROMPT = """You are Agnes, an AI Supply Chain Interface for CPG companies.

YOUR ROLE:
You surface and explain Sourcing Proposals and Compliance Evidence that have already
been computed by a deterministic backend pipeline (Phases 1-4).
You do NOT invent data. You do NOT recalculate scores.

CRITICAL CONSTRAINTS:
- ONLY use data present in the "RETRIEVED SOURCING PROPOSALS" and "RETRIEVED EVIDENCE"
  sections of the user message. Nothing else is ground truth.
- NEVER invent supplier names, certifications, savings percentages, or confidence scores.
  If a metric is not in the retrieved text, say "NOT IN RETRIEVED DATA".
- When citing figures (EstimatedSavingsPct, ConfidenceScore), copy them verbatim from
  the retrieved proposal text — never compute or estimate them yourself.
- Cite the doc_id (e.g. [P12], [E47]) for every factual claim you make.
- If no proposals were retrieved, say so explicitly and advise the user to refine
  the query or rebuild the pipeline index.
- Compliance status comes from the retrieved evidence docs. If evidence shows a
  compliance gap, flag it as a risk; if absent, mark as "UNVERIFIED — not in index".

SCORING MODEL:
The backend uses this formula (already computed — DO NOT recompute):

  FINAL_SCORE = (0.35 × compliance_score)
              + (0.25 × coverage_score)
              + (0.25 × savings_score)
              + (0.15 × data_quality_score)

Report these values from the proposal's ConfidenceScore field. Do not derive them.

OUTPUT FORMAT (strict JSON — no text outside the JSON block):
{
  "substitution_groups": [
    {
      "canonical_ingredient": "string — from retrieved proposal",
      "companies_using": ["Company A", ...],
      "products_affected": ["FG-xxx", ...],
      "current_suppliers": ["Supplier A", ...],
      "recommended_supplier": "string — from retrieved proposal",
      "reasoning": "string — explain which doc IDs support this",
      "feature_scores": {
        "compliance_score": 0.0,
        "coverage_score": 0.0,
        "savings_score": 0.0,
        "data_quality_score": 0.0
      },
      "weights": { "compliance": 0.35, "coverage": 0.25, "savings": 0.25, "data_quality": 0.15 },
      "weighted_contributions": { "compliance": 0.0, "coverage": 0.0, "savings": 0.0, "data_quality": 0.0 },
      "final_score": 0.0,
      "confidence_score": 0.0,
      "evidence": [
        {
          "source_id": "E12",
          "type": "pipeline_enrichment",
          "url": "string or empty",
          "snippet": "verbatim text from the retrieved evidence doc",
          "relevance": 0.0
        }
      ],
      "risks": ["string"],
      "estimated_impact": "string — from retrieved proposal EstimatedSavingsPct"
    }
  ],
  "consolidation_summary": "string",
  "overall_confidence": 0.0,
  "data_gaps": ["string"]
}
"""


RETRIEVAL_QUERY_TEMPLATE = """\
=== RETRIEVED SOURCING PROPOSALS (Phase 4 Index — Ground Truth) ===
{proposals}

=== RETRIEVED COMPLIANCE EVIDENCE (Phase 4 Index — Ground Truth) ===
{evidence}
{fallback}
=== USER QUERY ===
{query}

INSTRUCTIONS:
- Answer using ONLY the retrieved data above.
- Cite [doc_id] for every factual claim.
- Copy numeric metrics verbatim from the retrieved text.
- If a field cannot be filled from retrieved data, write "NOT IN RETRIEVED DATA".
- Return ONLY valid JSON matching the schema in your system instructions.
- Do NOT include any text outside the JSON block.
"""
```

---

## 7. `main.py` — Required Changes

Three commands become invalid once `skip_scraping` is removed from `ask_agnes()`:

```python
# REMOVE these command branches from the main() loop:
elif user_input == "/fast":   ...    # no longer meaningful
elif user_input == "/scrape": ...    # no longer meaningful
elif user_input == "/cache":  ...    # scraper.get_cached_results() no longer called

# UPDATE the help text in print_banner() to remove those commands

# UPDATE the demo runner — remove the skip_scraping= kwarg:
# Before:
result = ask_agnes(demo_query, skip_scraping=fast_mode)
# After:
result = ask_agnes(demo_query)

# ADD a new /rebuild command to allow hot-reloading the index:
elif user_input == "/rebuild":
    print("  Rebuilding Phase 4 index from database...")
    _INDEX = None                          # clear the global cache in agnes_core
    agnes_core._INDEX = None
    agnes_core._get_index(force_rebuild=True)
    print("  Index rebuilt.")
```

---

## 8. Scraper Policy (Decision Record)

| Scenario | Behaviour | Rationale |
|:---|:---|:---|
| Query matches ≥1 proposal in index | Scraper **not called** | Phase 2 enrichment already captured compliance; Phase 4 indexed it |
| Query matches 0 proposals, named supplier is known | Scraper called **once** for that supplier | Edge case: user asks about a supplier added after last pipeline run |
| Query matches 0 proposals, no known supplier | Scraper **not called** | Nothing to scrape; LLM told index has no data |
| Scraper fails (timeout / 403 / SSL) | Error recorded in `_meta.fallback_scrape_triggered`; LLM prompt includes `NO_FALLBACK_DATA` | Non-blocking; never raises to the user |

---

## 9. Error Handling for Empty Retrieval

When `n_proposals == 0` and no fallback scrape was possible, `_format_retrieved()`
returns `"NO_PROPOSALS_RETRIEVED"` as the proposals block. The LLM is instructed
(via `AGNES_SYSTEM_PROMPT`) to respond:

```json
{
  "substitution_groups": [],
  "consolidation_summary": "No sourcing proposals were found for this query in the Phase 4 index. Try rephrasing with a specific ingredient name or supplier, or run /rebuild to refresh the index.",
  "overall_confidence": 0.0,
  "data_gaps": ["No proposals retrieved for query"]
}
```

This prevents hallucination when the index is stale or the query is too narrow.

---

## 10. Import Path Setup

`agnes_core.py` lives at the repo root. The Phase 4 retriever is at
`agnes/backend/phase4_output/retriever.py`. The import chain requires
`backend.config`, `backend.db.*`, and `backend.db.queries` to resolve.

The `sys.path.insert` at the top of `agnes_core.py` handles this:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "agnes"))
```

This makes `from backend.phase4_output.retriever import build_or_load_index` resolve
correctly without modifying `agnes/backend/` or installing the package.

Verify the path resolves correctly:
```bash
cd /c/TU/Projects/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes
python -c "
import sys; sys.path.insert(0, 'agnes')
from backend.phase4_output.retriever import build_or_load_index, RetrievalIndex
print('Import OK')
"
```

---

## 11. Migration Checklist

```
[ ] 1. Verify Phase 1-3 pipeline has been run and DB has data
       python agnes/backend/run_phase1.py
       python agnes/backend/run_phase2.py
       python agnes/backend/run_phase3.py

[ ] 2. Build the Phase 4 index (generates phase4_index.npz + phase4_docs.json)
       python agnes/backend/run_phase4.py

[ ] 3. Rewrite prompts.py — replace QUERY_TEMPLATE with RETRIEVAL_QUERY_TEMPLATE,
       update AGNES_SYSTEM_PROMPT with retrieval-grounding rules

[ ] 4. Rewrite agnes_core.py:
       - Delete: load_context, _extract_all_suppliers, extract_relevant_suppliers,
                 build_mega_prompt, _CONTEXT_CACHE, _ALL_SUPPLIERS, CONTEXT_FILE
       - Add: _get_index, _format_retrieved, build_retrieval_prompt
       - Rewrite: ask_agnes (remove skip_scraping param, add retrieval pipeline)
       - Keep unchanged: _get_client, call_llm, parse_response

[ ] 5. Update main.py:
       - Remove /fast, /scrape, /cache commands
       - Remove skip_scraping= kwarg from ask_agnes calls
       - Add /rebuild command

[ ] 6. Smoke test:
       python main.py
       > What are the top consolidation opportunities?
       (Should cite [P1], [P2] etc. with real ConfidenceScore values)

[ ] 7. Regression test: ensure _meta.proposals_retrieved > 0 for standard queries
```

---

## 12. What Does NOT Change

- `scraper.py` — full file preserved; called only in the fallback branch
- `agnes/backend/**` — zero changes; strictly the Source of Truth
- `call_llm()` — retry logic, model name, temperature all unchanged
- `parse_response()` — 4-attempt JSON extraction cascade unchanged
- `display_recommendation()` in `main.py` — output rendering unchanged
- `run_demo()` in `main.py` — demo queries unchanged (just drop `skip_scraping=`)
- `.env` — same `OPENAI_API_KEY` used for both chat LLM and embeddings

---

## 13. Doc Schema Reference (Phase 4 `Doc` Dataclass)

```
Doc.doc_id  : str   — "P{proposal_id}" or "E{enrichment_id}"
Doc.kind    : str   — "proposal" | "evidence"
Doc.text    : str   — pre-formatted searchable string (used in prompt directly)
Doc.meta    : dict

  Proposal meta keys:
    proposal_id         int
    ingredient_group_id int
    supplier_id         int
    supplier_name       str
    priority            str   — "HIGH" | "MEDIUM" | "LOW"
    confidence          float — 0–100 scale (pipeline output)
    savings_pct         float — 0–100 scale (pipeline output)

  Evidence meta keys:
    enrichment_id   int
    entity_type     str   — "supplier" | "product" | ...
    entity_id       int
    data_type       str   — "supplier_info" | "compliance_requirements" | "product_scrape"
    source_url      str   — empty string if not available
    confidence      float
```

Proposal `Doc.text` format (verbatim from `_proposal_text()`):
```
Sourcing proposal for ingredient group {IngredientGroupId}.
Recommended supplier: {RecommendedSupplierName}.
Consolidates {CompaniesConsolidated} of {TotalCompaniesInGroup} companies ({MembersServed} SKUs).
Estimated savings: {EstimatedSavingsPct:.1f}%.
Confidence: {ConfidenceScore:.0f}%.
Priority: {Priority}.
Compliance status: {ComplianceStatus}.
Risks: {RiskFactorsJson}.
Evidence: {EvidenceSummary}
```

The LLM is instructed to extract numeric values verbatim from this text string
and copy them into its JSON output — never to recompute them.

---

## 14. Key Design Decisions

| Decision | Rationale |
|:---|:---|
| `k_proposals=3, k_evidence=5` | Enough context for a focused answer; keeps prompt under 4K tokens even with long Doc.text strings |
| Similarity scores hidden from LLM | Prevents the LLM from anchoring on retrieval scores instead of the pipeline's `ConfidenceScore` |
| Scraper as last-resort fallback only | Phase 2 `iherb_scraper.py` + `supplier_scraper.py` already collected compliance data; re-scraping live is redundant and slow |
| `sys.path.insert` instead of package install | Zero-config for hackathon; no `pip install -e agnes/` needed |
| `force_rebuild=False` in `_get_index()` | Cold start uses cached `.npz`; `/rebuild` command forces refresh when pipeline data changes |
| Remove `skip_scraping` param | The parameter existed only to skip real-time scraping; with retrieval-grounded prompts, scraping is already conditional — no flag needed |

---

## 15. Known Gotchas — Do Not Repeat

### 15.1 Confidence Score Scale Mismatch (recurring bug)

**Root cause:** The Phase 3 `confidence_scorer.py` returns values on a **0-100 scale** (four
components each capped at 25, summing to 100). `_proposal_text()` in the retriever embeds
this as `"Confidence: 75%."`. The LLM reads that and copies `75` verbatim into
`confidence_score` in its JSON output instead of normalising to `0.75`.

Meanwhile `prompts.py` defines `feature_scores` as 0-1, so `overall_confidence` ends up on
the 0-1 scale while `confidence_score` per group stays on 0-100. The display code uses
`:.0%` which multiplies by 100 → `7500%`.

**Fix applied in `main.py` (permanent guard — do not remove):**

```python
# Normalize: LLM sometimes copies the 0-100 backend value verbatim instead of 0-1
if conf > 1:
    conf = conf / 100
```

This guard is applied to both `overall_conf` and the per-group `conf` before any formatting.

**Rule:** Never use `:.0%` on a confidence value without first running it through this guard.
Never change the guard to a hard threshold without also changing `confidence_scorer.py`.

### 15.2 Risk Objects Rendered as Raw Dicts

**Root cause:** `prompts.py` updated the `risks` field from `["string"]` to structured objects
`{"factor", "impact", "mitigation"}`, but `display_recommendation()` in `main.py` was still
doing `print(f"[!] {r}")` which printed the raw Python dict.

**Fix applied in `main.py`:** The risk rendering block now checks `isinstance(r, dict)` and
prints `factor`, `impact`, and `mitigation` on separate labelled lines. Always keep this
`isinstance` guard so the display degrades gracefully if the LLM outputs a plain string.

### 15.3 Company Names Shown as Single Letters

**Root cause:** `_proposal_text()` in `retriever.py` only embeds company **counts**
(`CompaniesConsolidated`, `TotalCompaniesInGroup`), never actual names. The LLM had nothing
to populate `companies_using` with, so it copied the schema placeholders ("Company A") or
abbreviated them to single letters.

**Fix applied in `agnes_core.py`:** `_format_retrieved()` calls `_get_group_companies()` and
`_get_group_suppliers()` which query `SubstitutionGroupMember` and `SubstitutionGroupSupplier`
directly and append real names to each proposal's text block before the LLM sees it.

**Rule:** If `_proposal_text()` in the backend is ever updated to include company names
natively, remove the two helper functions from `agnes_core.py` to avoid duplication.
