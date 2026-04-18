# AGNES — Master Architecture Blueprint

> **Project:** TUM.ai Spherecast Makeathon 2026
> **System:** Agnes — AI Supply Chain Manager
> **Constraint:** Zero frameworks. Pure Python. Native `google-genai` SDK + BeautifulSoup4.

---

## 1. System Overview

Agnes is a lean, zero-framework AI system that identifies raw material substitution and supplier consolidation opportunities across 61+ CPG companies. It operates on a pre-flattened knowledge file (`ai_context.txt`, 140KB, 1974 lines) containing 150+ Semantic BOM profiles with ingredient-to-supplier mappings.

**Architecture in one sentence:** User query + `ai_context.txt` (Internal Truth) + live-scraped supplier compliance data (External Truth) are concatenated into a single massive prompt sent to Gemini 1.5 Pro, which reasons over the full context and returns structured JSON recommendations with evidence trails.

There is no vector database. No embeddings. No RAG. No chunking. Gemini's 1M-token context window *is* the retrieval engine. The entire knowledge base fits in a single prompt.

```
┌─────────────────────────────────────────────────────────────┐
│                        USER QUERY                           │
│   "Can we consolidate vitamin D3 suppliers across all       │
│    companies? Check organic compliance."                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    agnes_core.py                             │
│                                                              │
│  1. Load ai_context.txt ──────────► INTERNAL TRUTH (140KB)  │
│                                                              │
│  2. Parse query for supplier names                           │
│     └─► Trigger scraper.py ──────► EXTERNAL TRUTH (scraped) │
│                                                              │
│  3. Assemble mega-prompt:                                    │
│     ┌─────────────────────────────────────────────┐          │
│     │ SYSTEM: You are Agnes, a supply chain AI... │          │
│     │ CONTEXT: [Full ai_context.txt]              │          │
│     │ EXTERNAL: [Scraped compliance data]         │          │
│     │ QUERY: [User's question]                    │          │
│     │ FORMAT: [JSON response schema]              │          │
│     └─────────────────────────────────────────────┘          │
│                       │                                      │
│                       ▼                                      │
│  4. google.genai.generate_content() ──► Gemini 1.5 Pro      │
│                       │                                      │
│                       ▼                                      │
│  5. Parse JSON response                                      │
│     └─► Structured recommendation with evidence trails       │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow Architecture

### Step-by-step pipeline for every query:

```
STEP 1: INTAKE
  main.py receives user query string
  │
STEP 2: CONTEXT LOADING
  agnes_core.py reads ai_context.txt into memory (once, cached)
  │
STEP 3: SUPPLIER EXTRACTION
  agnes_core.py extracts supplier names mentioned in the context
  that are relevant to the query (regex + Gemini pre-pass if needed)
  │
STEP 4: EXTERNAL ENRICHMENT (conditional)
  scraper.py receives list of supplier names
  For each supplier:
    ├── Attempts known URL patterns (e.g., supplier homepage)
    ├── Extracts: certifications, organic status, kosher, allergens
    ├── Returns structured dict or SCRAPE_FAILED sentinel
    └── Caches results to avoid re-scraping within session
  │
STEP 5: PROMPT ASSEMBLY
  agnes_core.py builds the mega-prompt:
    Section 1: System instructions (role, output schema, rules)
    Section 2: FULL ai_context.txt (Internal Truth)
    Section 3: Scraped compliance data (External Truth)
    Section 4: User query
    Section 5: Output format enforcement (JSON schema)
  │
STEP 6: LLM CALL
  Single call to Gemini 1.5 Pro via google-genai SDK
  Temperature: 0.1 (deterministic reasoning)
  │
STEP 7: RESPONSE PARSING
  Extract JSON from response
  Validate against expected schema
  │
STEP 8: OUTPUT
  Print formatted recommendation to terminal
  Include: substitution groups, confidence scores, evidence trails,
           risk warnings, estimated consolidation impact
```

---

## 3. Module Breakdown

### `main.py` — Entry Point & CLI Interface

The interactive loop. Keeps it simple: no web server, no UI framework.

```python
# main.py — Entry Point

def main():
    """
    Interactive CLI loop for Agnes.
    Loads context once, accepts queries in a loop.
    """
    pass

def display_recommendation(result: dict) -> None:
    """
    Pretty-prints a structured recommendation to the terminal.
    Handles: substitution groups, confidence scores, evidence, risks.
    
    Input:  result dict from agnes_core.ask_agnes()
    Output: Formatted terminal output with color codes (colorama)
    """
    pass

if __name__ == "__main__":
    main()
```

**Dependencies:** `agnes_core`, `colorama` (optional, for terminal colors)

---

### `agnes_core.py` — The Brain

The central orchestrator. Owns prompt construction, LLM calls, and response parsing.

```python
# agnes_core.py — Core Reasoning Engine

import google.genai as genai
from typing import Optional

# Module-level cache
_CONTEXT_CACHE: Optional[str] = None

def load_context(filepath: str = "ai_context.txt") -> str:
    """
    Reads and caches the full ai_context.txt file.
    Called once at startup. Returns the full string.
    
    Input:  filepath (str)
    Output: Full file contents (str, ~140KB)
    Raises: FileNotFoundError if context file missing
    """
    pass

def extract_relevant_suppliers(query: str, context: str) -> list[str]:
    """
    Identifies supplier names from ai_context.txt that are relevant
    to the user's query. Uses simple keyword matching first, then
    falls back to a lightweight Gemini call if needed.
    
    Input:  query (str), context (str)
    Output: List of supplier name strings, e.g. ["Prinova USA", "PureBulk"]
    """
    pass

def build_system_prompt() -> str:
    """
    Returns the hardcoded Agnes system prompt.
    Defines: role, reasoning rules, output schema, hallucination guardrails.
    
    Output: System prompt string
    """
    pass

def build_mega_prompt(
    context: str,
    external_data: dict,
    user_query: str
) -> str:
    """
    Assembles the complete prompt from all three truth sources.
    
    Input:
      - context: Full ai_context.txt content
      - external_data: Dict of {supplier_name: scraped_info_dict}
      - user_query: The user's natural language question
    Output: Complete prompt string ready for Gemini
    """
    pass

def call_gemini(prompt: str, system_prompt: str) -> str:
    """
    Makes a single call to Gemini 1.5 Pro via google-genai SDK.
    
    Input:  prompt (str), system_prompt (str)
    Output: Raw response text from Gemini
    Config:
      - model: "gemini-1.5-pro"
      - temperature: 0.1
      - max_output_tokens: 8192
    Raises: Exception on API failure (with retry logic, max 2 retries)
    """
    pass

def parse_response(raw_response: str) -> dict:
    """
    Extracts and validates JSON from Gemini's response.
    Handles: markdown code fences, partial JSON, validation errors.
    
    Input:  raw_response (str)
    Output: Parsed dict matching the AgnesRecommendation schema
    Raises: ValueError if JSON is unparsable after cleanup attempts
    """
    pass

def ask_agnes(query: str) -> dict:
    """
    PUBLIC API — The single entry point for asking Agnes a question.
    Orchestrates the full pipeline: load → extract → scrape → prompt → call → parse.
    
    Input:  query (str) — Natural language question
    Output: dict with keys:
      {
        "query": str,
        "substitution_groups": [
          {
            "canonical_ingredient": str,
            "companies_using": [str],
            "current_suppliers": [str],
            "recommended_supplier": str,
            "confidence_score": float (0.0-1.0),
            "evidence": [str],
            "risks": [str],
            "estimated_impact": str
          }
        ],
        "consolidation_summary": str,
        "overall_confidence": float,
        "data_gaps": [str],
        "scraper_status": dict
      }
    """
    pass
```

**Dependencies:** `google-genai`, `json`, `re`, `scraper`

---

### `scraper.py` — The Eyes

Lightweight, resilient web scraper. Focused on extracting compliance signals from supplier websites.

```python
# scraper.py — External Compliance Data Scraper

import requests
from bs4 import BeautifulSoup
from typing import Optional

# Session-level cache: {url: response_dict}
_SCRAPE_CACHE: dict = {}

# Known supplier URL patterns
SUPPLIER_URLS: dict[str, str] = {
    "Prinova USA": "https://www.prinovagroup.com",
    "PureBulk": "https://purebulk.com",
    "Jost Chemical": "https://www.jostchemical.com",
    "Ingredion": "https://www.ingredion.com",
    "ADM": "https://www.adm.com",
    "Cargill": "https://www.cargill.com",
    "Ashland": "https://www.ashland.com",
    "Colorcon": "https://www.colorcon.com",
    "Capsuline": "https://capsuline.com",
    "Gold Coast Ingredients": "https://goldcoastinc.com",
    "Balchem": "https://balchem.com",
    "Actus Nutrition": "https://actusnutrition.com",
    "Univar Solutions": "https://www.univarsolutions.com",
    # ... remaining 27+ suppliers
}

# Compliance keywords to search for on pages
COMPLIANCE_SIGNALS: list[str] = [
    "organic", "usda organic", "non-gmo", "non gmo", "kosher",
    "halal", "gluten-free", "gluten free", "vegan", "allergen",
    "gmp", "fda", "iso", "nsf", "usp", "certificate",
    "soy-free", "dairy-free", "nut-free",
]

def scrape_supplier(supplier_name: str) -> dict:
    """
    Scrapes a supplier's website for compliance information.
    Returns a structured dict of findings.
    
    Input:  supplier_name (str) — Must match a key in SUPPLIER_URLS
    Output: {
        "supplier": str,
        "url": str,
        "status": "success" | "failed" | "blocked" | "not_found",
        "certifications_found": [str],
        "compliance_signals": {signal: bool},
        "raw_text_snippet": str (first 500 chars of relevant content),
        "scrape_timestamp": str (ISO format),
        "error": Optional[str]
    }
    """
    pass

def _fetch_page(url: str, timeout: int = 10) -> Optional[requests.Response]:
    """
    Fetches a URL with proper headers and timeout handling.
    
    Input:  url (str), timeout (int, default 10s)
    Output: requests.Response or None on failure
    
    Headers:
      User-Agent: Mozilla/5.0 (compatible; AgnesBot/1.0; research)
      Accept: text/html
    """
    pass

def _extract_compliance_signals(soup: BeautifulSoup) -> dict:
    """
    Scans a parsed HTML page for compliance-related keywords.
    Searches: page title, meta tags, headings, paragraph text.
    
    Input:  BeautifulSoup object
    Output: {
        "certifications_found": ["Organic", "Non-GMO", ...],
        "compliance_signals": {"organic": True, "kosher": False, ...},
        "relevant_snippet": str
    }
    """
    pass

def scrape_multiple(supplier_names: list[str]) -> dict:
    """
    Batch scrapes multiple suppliers. Uses cache to avoid re-fetching.
    
    Input:  List of supplier name strings
    Output: {supplier_name: scrape_result_dict, ...}
    """
    pass

def get_cached_results() -> dict:
    """Returns the current session cache for debugging."""
    pass
```

**Dependencies:** `requests`, `beautifulsoup4`, `datetime`

---

### `prompts.py` — Prompt Templates (Optional but Recommended)

Isolates all prompt engineering into one file for rapid iteration.

```python
# prompts.py — All Prompt Templates

AGNES_SYSTEM_PROMPT = """
You are Agnes, an expert AI Supply Chain Manager for the CPG (Consumer Packaged Goods) industry.

YOUR MISSION: Analyze the provided supply chain data to identify:
1. Raw materials that are functionally identical across different companies
2. Supplier consolidation opportunities that reduce cost via volume leverage
3. Compliance risks when substituting suppliers

CRITICAL RULES:
- NEVER hallucinate certifications. If external data was not scraped or is missing, 
  say "UNVERIFIED" and set confidence_score below 0.5.
- Always cite which companies and products would be affected by a consolidation.
- Quantify impact where possible (number of companies, number of products affected).
- Flag single-source risks (ingredients with only 1 approved supplier).
- When compliance data is missing, explicitly list it under "data_gaps".

OUTPUT FORMAT: You MUST respond with valid JSON matching this exact schema:
{
  "substitution_groups": [
    {
      "canonical_ingredient": "human-readable ingredient name",
      "companies_using": ["Company A", "Company B"],
      "products_affected": ["FG-xxx", "FG-yyy"],
      "current_suppliers": ["Supplier A", "Supplier B"],
      "recommended_supplier": "Supplier X",
      "reasoning": "Why this supplier is recommended",
      "confidence_score": 0.0 to 1.0,
      "evidence": ["Source 1: ...", "Source 2: ..."],
      "risks": ["Risk 1", "Risk 2"],
      "estimated_impact": "Consolidates N suppliers to 1 for M companies"
    }
  ],
  "consolidation_summary": "Executive summary paragraph",
  "overall_confidence": 0.0 to 1.0,
  "data_gaps": ["Missing info 1", "Missing info 2"]
}
"""

QUERY_TEMPLATE = """
=== INTERNAL SUPPLY CHAIN DATA (GROUND TRUTH) ===
{context}

=== EXTERNAL SUPPLIER COMPLIANCE DATA (SCRAPED) ===
{external_data}

=== USER QUERY ===
{query}

Analyze the above data and respond with the JSON schema specified in your instructions.
"""
```

---

## 4. Edge Case Mitigation

### Scraper Failure Modes

| Failure Mode | Detection | Mitigation |
|:---|:---|:---|
| **Timeout (>10s)** | `requests.Timeout` exception | Return `{"status": "failed", "error": "timeout"}`. Agnes proceeds with internal data only, confidence drops to 0.3-0.5 for affected suppliers. |
| **HTTP 404** | `response.status_code == 404` | Return `{"status": "not_found"}`. Log the URL. Agnes marks supplier compliance as "UNVERIFIED". |
| **HTTP 403 / Bot Block** | `response.status_code == 403` or Cloudflare challenge detected in body | Return `{"status": "blocked"}`. Rotate User-Agent string from a pool of 5. Retry once. If still blocked, return failure. |
| **Connection Error** | `requests.ConnectionError` | Return `{"status": "failed", "error": "connection_refused"}`. No retry — supplier site is down. |
| **SSL Error** | `requests.exceptions.SSLError` | Retry with `verify=False`. Log a warning. |
| **Empty/Garbage HTML** | `len(soup.get_text()) < 100` | Return `{"status": "failed", "error": "empty_page"}`. |
| **Rate Limiting** | `response.status_code == 429` | Sleep `Retry-After` header value or 30s default. Retry once. |

### Gemini API Failure Modes

| Failure Mode | Detection | Mitigation |
|:---|:---|:---|
| **API Key Invalid** | `google.api_core.exceptions.PermissionDenied` | Hard fail with clear error message. |
| **Rate Limit** | `ResourceExhausted` exception | Exponential backoff: 2s → 4s → 8s. Max 3 retries. |
| **Context Too Long** | `InvalidArgument` with token limit message | Truncate external data section first, then trim oldest context entries. Should not happen with 140KB context. |
| **Malformed JSON Output** | `json.JSONDecodeError` | Attempt regex extraction of JSON from markdown fences. Retry the call once with a stricter "respond ONLY with JSON, no markdown" instruction appended. |
| **Empty Response** | `len(response.text.strip()) == 0` | Retry once. If still empty, return error dict. |

### Data Integrity Guards

- **ai_context.txt missing:** Hard fail at startup with actionable error message.
- **ai_context.txt corrupted:** Validate that file contains at least 10 `Company:` blocks on load.
- **Supplier not in SUPPLIER_URLS:** Skip scraping for unknown suppliers. Log them. Agnes still reasons using internal data.
- **Gemini hallucinates a certification:** The system prompt mandates "UNVERIFIED" for any claim not backed by scraped data. The `confidence_score` field forces Gemini to self-assess.

---

## 5. Execution Roadmap

### Phase 0: Environment Setup (5 minutes)
```
1. pip install google-genai requests beautifulsoup4 colorama
2. Verify GEMINI_API_KEY in .env
3. Verify ai_context.txt exists and is ~140KB
```

### Phase 1: Build `prompts.py` (10 minutes)
```
1. Create prompts.py with AGNES_SYSTEM_PROMPT and QUERY_TEMPLATE
2. This is pure text — no logic, just string templates
3. Iterate on the system prompt wording (this is the highest-leverage work)
```

### Phase 2: Build `scraper.py` (30 minutes)
```
1. Implement _fetch_page() with proper headers, timeout, error handling
2. Implement _extract_compliance_signals() — keyword search in soup
3. Implement scrape_supplier() — full pipeline for one supplier
4. Implement scrape_multiple() with caching
5. Test against 3 known supplier URLs manually
6. Fill in SUPPLIER_URLS dict for all 40 suppliers in the dataset
```

### Phase 3: Build `agnes_core.py` (30 minutes)
```
1. Implement load_context() with file caching
2. Implement extract_relevant_suppliers() — regex for supplier names
3. Implement build_mega_prompt() using prompts.py templates
4. Implement call_gemini() with google-genai SDK
5. Implement parse_response() with JSON extraction
6. Wire it all together in ask_agnes()
7. Test with: "What vitamin D3 suppliers are shared across the most companies?"
```

### Phase 4: Build `main.py` (15 minutes)
```
1. Implement the interactive CLI loop
2. Implement display_recommendation() with formatted output
3. Add startup banner, help text, exit handling
4. Test full end-to-end flow
```

### Phase 5: Demo Hardening (20 minutes)
```
1. Prepare 3 canned demo queries that showcase Agnes's capabilities:
   a. "Identify the top 5 supplier consolidation opportunities across all companies"
   b. "Which raw materials have single-source risk (only 1 approved supplier)?"
   c. "Can Prinova USA replace PureBulk for all vitamin products? Check compliance."
2. Pre-cache scraper results for demo suppliers to avoid live failures
3. Add a --demo flag to main.py that runs the 3 canned queries sequentially
4. Record a backup terminal session (script or asciinema)
```

---

## 6. File Tree (Final State)

```
Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/
├── ai_context.txt          # 140KB — Semantic BOM knowledge base (EXISTING)
├── db.sqlite               # Original relational DB (EXISTING, reference only)
├── .env                    # GEMINI_API_KEY (EXISTING)
├── CLAUDE.md               # This document (EXISTING)
├── clean_data.py           # Data extraction script (EXISTING, completed)
├── main.py                 # CLI entry point (TO BUILD)
├── agnes_core.py           # Core reasoning engine (TO BUILD)
├── scraper.py              # Web scraper for compliance (TO BUILD)
├── prompts.py              # Prompt templates (TO BUILD)
├── docs/                   # Documentation (EXISTING)
└── venv/                   # Virtual environment (EXISTING)
```

---

## 7. Key Design Decisions & Rationale

| Decision | Rationale |
|:---|:---|
| **No RAG / No vector DB** | At 140KB, the entire context fits trivially inside Gemini 1.5 Pro's 1M-token window. Chunking would *lose* cross-company relationships that are the entire point of the analysis. |
| **No LangChain / No LlamaIndex** | Framework overhead adds failure modes, debugging complexity, and abstraction fog. A single `genai.generate_content()` call is all we need. |
| **Scraper returns structured dicts, not raw HTML** | Agnes needs *signals* (organic: yes/no), not web pages. Pre-processing at the scraper layer keeps the prompt clean. |
| **JSON output schema enforced in prompt** | Gemini reliably produces structured JSON when the schema is explicit. No need for function calling or tool-use complexity. |
| **Confidence scoring as first-class output** | The judges explicitly grade on "handling uncertainty." Every recommendation carries a confidence score that degrades when external data is missing. |
| **Session-level scrape cache** | Suppliers appear across many products. Scraping Prinova USA once (not 50 times) saves minutes of wall-clock time in the demo. |
| **Temperature 0.1** | We want deterministic, citation-grounded reasoning. Not creative writing. |

---

## 8. Dependency Manifest

```
google-genai>=1.0.0        # Native Gemini SDK (NOT the deprecated google-generativeai)
requests>=2.31.0            # HTTP client for scraping
beautifulsoup4>=4.12.0      # HTML parser
python-dotenv>=1.0.0        # .env file loading
colorama>=0.4.6             # Terminal color output (optional)
```

---

## 9. Scalability Roadmap (The "Enterprise" Story)

While the current prototype uses **Long-Context Prompting** for maximum accuracy on the hackathon dataset, it is designed to transition to a massive enterprise scale as follows:

| Scale | Architecture | Rationale |
|:---|:---|:---|
| **S (Hackathon)** | **Long-Context** | < 1M tokens. Fits in Gemini's window. 100% retrieval accuracy. |
| **M (Regional)** | **GraphRAG** | 1M - 100M tokens. Use a Knowledge Graph (Neo4j) to retrieve relevant "supply chain neighborhoods" instead of random text chunks. |
| **L (Global)** | **Federated Agents** | > 100M tokens. Multi-agent "Swarm" where specialized agents analyze specific commodity classes (e.g., Chemicals, Logistics, Raw Materials). |

**Why not RAG now?**
Standard RAG (Vector DBs) often breaks "relational" integrity. In supply chains, you need to see the *entire* network to find consolidation wins. Current RAG methods "lose the forest for the trees." Agnes keeps the forest.
