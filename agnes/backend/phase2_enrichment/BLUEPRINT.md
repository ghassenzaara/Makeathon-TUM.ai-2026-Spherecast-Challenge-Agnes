# Phase 2 Enrichment — API Upgrade Blueprint

> **Status:** PENDING APPROVAL — do not implement until confirmed.
> **Goal:** Replace brittle HTML scraping and LLM-hallucinated guesses with
> deterministic B2B enterprise API calls.

---

## Current State (Problems)

| File | Problem |
|---|---|
| `iherb_scraper.py` | Primary path uses `httpx` + `BeautifulSoup` to parse iHerb HTML — fragile against DOM changes, bot detection, and rate limits. LLM fallback has confidence 5–25 and produces empty arrays by design. |
| `supplier_scraper.py` | `SUPPLIER_INFERENCE_PROMPT` is the **only** data source. GPT-4o guesses certifications from training data (confidence 30–70). No real-world lookup occurs. |
| `run_phase2.py` | No FDA risk check. No entity verification. Steps 4 and 5 don't exist. |

---

## Upgrade 1 — Tavily Search API replaces BeautifulSoup

### 1a. `iherb_scraper.py`

**Removed:**
- `import httpx`
- `from bs4 import BeautifulSoup`
- `_HEADERS` dict
- `_parse_iherb_page(soup, result)` function
- The `httpx.AsyncClient` block inside `scrape_iherb_product()`

**Added:**

```python
from tavily import AsyncTavilyClient
from backend.config import TAVILY_API_KEY
```

**New private functions (replacing `_parse_iherb_page`):**

```python
async def _tavily_fetch_iherb(iherb_id: str) -> dict | None:
    """
    Queries Tavily Search for iHerb product data.
    Returns a raw Tavily response dict, or None on failure.

    SDK call:
        client = AsyncTavilyClient(api_key=TAVILY_API_KEY)
        response = await client.search(
            query=f"Find the product certifications and ingredients for iHerb product {iherb_id}",
            search_depth="advanced",
            include_domains=["iherb.com"],
            max_results=3,
        )
    """

def _parse_tavily_iherb(tavily_results: list[dict], base_result: dict) -> dict:
    """
    Extracts certifications, ingredients, title, and brand from
    Tavily search result content strings using CERTIFICATION_KEYWORDS.
    Returns updated base_result dict.
    Sets base_result["scrape_success"] = True on success.
    """
```

**Modified `scrape_iherb_product()` flow:**

```
1. cache_get("iherb", iherb_id)  → return if hit
2. _tavily_fetch_iherb(iherb_id) → parse with _parse_tavily_iherb()
   └─ success → scrape_success=True, cache_set, return
3. _llm_fallback_iherb()         → last resort, unchanged logic
   └─ cache_set, return
```

**Confidence:** `store_product_scrape()` called unchanged (0.9). LLM fallback confidence stays 5–25.

**`_inference_note` values:**
- Tavily success: `"Data sourced via Tavily Search (iherb.com)"`
- LLM fallback: `"Data inferred by LLM (Tavily also failed)"` ← updated from current string

---

### 1b. `supplier_scraper.py`

**Added:**

```python
from tavily import AsyncTavilyClient
from backend.config import TAVILY_API_KEY
```

**New private function:**

```python
async def _tavily_enrich_supplier(supplier_name: str) -> dict | None:
    """
    Queries Tavily for real supplier HQ and certification data.
    Returns a partial enrichment dict on success, None on failure.

    SDK call:
        client = AsyncTavilyClient(api_key=TAVILY_API_KEY)
        response = await client.search(
            query=f"What are the headquarters and official compliance certifications "
                  f"(ISO, GMP, etc.) for the supplier {supplier_name}?",
            search_depth="advanced",
            max_results=5,
        )

    Parses result content strings for:
      - HQ city/country patterns (regex)
      - Certification keywords from CERTIFICATION_KEYWORDS list in iherb_scraper

    Returns:
        {
            "headquarters": str,
            "certifications": [str],
            "website": str,          # URL of best Tavily result
            "confidence": 72,        # fixed value for Tavily-sourced data
            "source": "tavily_search",
        }
    """
```

**Modified `enrich_supplier()` flow:**

```
1. cache_get("suppliers", supplier_id) → return if hit
2. _tavily_enrich_supplier(supplier_name)
   └─ success → merge into result, source="tavily_search", confidence=72
3. SUPPLIER_INFERENCE_PROMPT / LLM  ← only if Tavily returns None
   └─ source="llm_inference", confidence=30-70 (unchanged)
4. cache_set + store_supplier_info()
```

**`SUPPLIER_INFERENCE_PROMPT` is kept** — demoted to fallback, not deleted.

**Confidence comparison:**

| Source | Confidence |
|---|---|
| Tavily search | 72 (fixed) |
| LLM inference (major company) | ~60–70 (unchanged) |
| LLM inference (unknown company) | ~30–40 (unchanged) |
| No API key, no LLM | 20 (unchanged) |

---

## Upgrade 2 — New file `openfda_api.py`

**Location:** `agnes/backend/phase2_enrichment/openfda_api.py`

**No API key required.** OpenFDA is a public government endpoint.

**Endpoint:**
```
GET https://api.fda.gov/food/enforcement.json
    ?search=recalling_firm:"{supplier_name}"
    &limit=5
```

**Functions:**

```python
async def check_supplier_fda_risk(supplier_name: str) -> dict:
    """
    Queries OpenFDA food enforcement endpoint for a single supplier.

    Args:
        supplier_name: Exact supplier name string (e.g. "Cargill")

    Returns on results found:
        {
            "status": "Warning",
            "enforcement_count": int,        # total_results from FDA meta
            "latest_recall": str,            # reason_for_recall of first result
            "latest_recall_date": str,       # report_date of first result (YYYYMMDD)
            "product_description": str,      # product_description of first result
            "classification": str,           # "Class I" | "Class II" | "Class III"
        }

    Returns on zero results:
        {"status": "Clear"}

    Returns on API failure:
        {"status": "Error", "error": str}

    HTTP config:
        timeout: 10s
        retries: 1 (on 429 or 5xx only)
        delay on retry: Retry-After header or 5s default
    """

async def check_all_suppliers_fda(suppliers: list[dict]) -> list[dict]:
    """
    Batch FDA check for all suppliers.

    Args:
        suppliers: List of dicts with keys 'Id' (int) and 'Name' (str),
                   as returned by get_all_suppliers().

    Returns:
        List of risk dicts (one per supplier), each augmented with
        'supplier_id' and 'supplier_name' keys.

    Side effects:
        Calls store_enrichment() for each supplier:
            entity_type = "supplier"
            entity_id   = str(supplier["Id"])
            data_type   = "fda_risk"
            confidence  = 0.95  (government API, authoritative)
            source_url  = full request URL used

    Rate limit: 0.25s sleep between requests (FDA public limit ~240 req/min).
    """
```

**Storage call (inside `check_all_suppliers_fda`):**
```python
store_enrichment(
    entity_type="supplier",
    entity_id=str(supplier_id),
    data_type="fda_risk",
    data=risk_obj,
    source_url="https://api.fda.gov/food/enforcement.json?search=recalling_firm:\"...\"",
    confidence=0.95,
)
```

---

## Upgrade 3 — New file `opencorporates_api.py`

**Location:** `agnes/backend/phase2_enrichment/opencorporates_api.py`

**Public endpoint (no key):**
```
GET https://api.opencorporates.com/v0.4/companies/search
    ?q={supplier_name}
    &jurisdiction_code=us
    &format=json
```

**With API key (higher rate limits):**
```
    &api_token={OPENCORPORATES_API_KEY}
```

**Mock fallback dict (used when API key is absent AND live request fails):**

```python
_MOCK_ENTITIES: dict[str, dict] = {
    "ADM":               {"status": "Active", "registered_name": "Archer-Daniels-Midland Company", "jurisdiction": "us_de", "company_number": "0000007084", "incorporation_date": "1923-01-01"},
    "Cargill":           {"status": "Active", "registered_name": "Cargill, Incorporated",           "jurisdiction": "us_de", "company_number": "0000017843", "incorporation_date": "1936-06-20"},
    "Ingredion":         {"status": "Active", "registered_name": "Ingredion Incorporated",          "jurisdiction": "us_de", "company_number": "0000049519", "incorporation_date": "1906-01-01"},
    "IFF":               {"status": "Active", "registered_name": "International Flavors & Fragrances Inc.", "jurisdiction": "us_ny", "company_number": "0000049519", "incorporation_date": "1909-01-01"},
    "Ashland":           {"status": "Active", "registered_name": "Ashland Global Holdings Inc.",   "jurisdiction": "us_de", "company_number": "0001307954", "incorporation_date": "2018-03-01"},
    "Univar Solutions":  {"status": "Active", "registered_name": "Univar Solutions Inc.",          "jurisdiction": "us_de", "company_number": "0001494319", "incorporation_date": "2012-12-01"},
}
```

**Functions:**

```python
async def verify_supplier_entity(supplier_name: str) -> dict:
    """
    Verifies supplier business registration via OpenCorporates.

    Resolution order:
      1. Check _MOCK_ENTITIES for exact name match → return mock (if OPENCORPORATES_API_KEY absent)
      2. Live GET to OpenCorporates search endpoint
         → pick top result where current_status matches "Active" or "Dissolved"
      3. On HTTP failure or zero results → return Unknown dict

    Returns:
        {
            "status": "Active" | "Dissolved" | "Unknown",
            "registered_name": str,
            "jurisdiction": str,           # e.g. "us_de"
            "company_number": str,
            "incorporation_date": str,     # ISO date or empty string
            "source": "opencorporates_live" | "opencorporates_mock",
        }

    HTTP config:
        timeout: 10s
        no retries (public endpoint is stable)
    """

async def verify_all_suppliers(suppliers: list[dict]) -> list[dict]:
    """
    Batch entity verification for all suppliers.

    Args:
        suppliers: List of dicts with 'Id' (int) and 'Name' (str).

    Returns:
        List of entity dicts, each augmented with 'supplier_id' and 'supplier_name'.

    Side effects:
        Calls store_enrichment() for each supplier:
            entity_type = "supplier"
            entity_id   = str(supplier["Id"])
            data_type   = "entity_verification"
            confidence  = 0.90 for live results | 0.70 for mock results
            source_url  = full OpenCorporates request URL (or "mock" for mocks)

    Rate limit: 0.5s sleep between requests (OpenCorporates public limit ~60 req/min).
    """
```

---

## Upgrade 4 — `run_phase2.py` orchestration

**New CLI flags added to `argparse`:**

```python
parser.add_argument("--skip-fda",             action="store_true", help="Skip OpenFDA risk checks")
parser.add_argument("--skip-opencorporates",  action="store_true", help="Skip OpenCorporates entity verification")
```

**New Steps 4 & 5 inserted after existing Step 2 (supplier enrichment), before Step 3 (compliance):**

```python
# ── Step 4: FDA Risk Check ──
if not skip_fda:
    from backend.phase2_enrichment.openfda_api import check_all_suppliers_fda
    logger.info("\n--- Step 4: OpenFDA Risk Check ---")
    suppliers = get_all_suppliers()
    fda_results = await check_all_suppliers_fda(suppliers)
    warnings = sum(1 for r in fda_results if r.get("status") == "Warning")
    logger.info(f"FDA: {len(fda_results)} suppliers checked, {warnings} with enforcement history")
else:
    logger.info("\n--- Step 4: FDA check SKIPPED ---")

# ── Step 5: Entity Verification ──
if not skip_opencorporates:
    from backend.phase2_enrichment.opencorporates_api import verify_all_suppliers
    logger.info("\n--- Step 5: OpenCorporates Entity Verification ---")
    suppliers = suppliers if not skip_fda else get_all_suppliers()   # reuse if already fetched
    oc_results = await verify_all_suppliers(suppliers)
    dissolved = sum(1 for r in oc_results if r.get("status") == "Dissolved")
    logger.info(f"OpenCorporates: {len(oc_results)} verified, {dissolved} dissolved entities")
else:
    logger.info("\n--- Step 5: Entity verification SKIPPED ---")
```

**Step numbering shift:** Compliance inference moves from Step 3 to Step 6. Only the log header string changes — the import and logic are identical.

**`get_all_suppliers()` import** is moved to the top of `run_phase2()` (currently it is imported inside the iHerb step and will now be shared).

---

## New entries required in `backend/config.py`

```python
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
OPENCORPORATES_API_KEY: str = os.getenv("OPENCORPORATES_API_KEY", "")
# OpenFDA requires no key
```

And in `.env`:
```
TAVILY_API_KEY=tvly-...
OPENCORPORATES_API_KEY=         # leave blank for mock fallback
```

---

## New entries required in `requirements.txt` / `pyproject.toml`

```
tavily-python>=0.3.0
```

`httpx` and `beautifulsoup4` can be **removed** from requirements once iherb_scraper is migrated (verify no other file imports them first).

---

## Enrichment DB — New `DataType` values

After these upgrades the `Enrichment` table will contain five distinct `DataType` values for suppliers:

| DataType | Source | Confidence |
|---|---|---|
| `supplier_info` | Tavily search (new primary) | 0.7 (store_supplier_info wrapper) |
| `supplier_info` | LLM inference (fallback) | 0.7 (same wrapper, lower internal `confidence` field) |
| `fda_risk` | OpenFDA API | 0.95 |
| `entity_verification` | OpenCorporates live | 0.90 |
| `entity_verification` | OpenCorporates mock | 0.70 |

No schema changes are needed — `store_enrichment()` already handles arbitrary `data_type` strings.

---

## File Change Summary

| File | Action |
|---|---|
| `phase2_enrichment/iherb_scraper.py` | Modify — replace httpx/BS4 with Tavily |
| `phase2_enrichment/supplier_scraper.py` | Modify — add Tavily as primary, demote LLM to fallback |
| `phase2_enrichment/openfda_api.py` | **Create** |
| `phase2_enrichment/opencorporates_api.py` | **Create** |
| `run_phase2.py` | Modify — add Steps 4 & 5, two new CLI flags |
| `backend/config.py` | Modify — add `TAVILY_API_KEY`, `OPENCORPORATES_API_KEY` |
| `.env` | Modify — add two new key entries |
| `requirements.txt` | Modify — add `tavily-python`, remove `beautifulsoup4`/`httpx` if unused |

**Total new files: 2. Modified files: 6.**
