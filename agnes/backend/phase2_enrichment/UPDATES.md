# Phase 2 Enrichment — Change Log
> Author: Ghassen Zaara  
> Date: 2026-04-18  
> Branch: `Ghassen`  
> Scope: Phase 2 enrichment pipeline upgrade + downstream propagation to Phase 3 & Phase 4

---

## Summary

Replaced brittle HTML scraping and raw LLM-hallucinated supplier guesses with
three deterministic, source-cited API integrations:

| Old approach | New approach | Confidence change |
|---|---|---|
| `BeautifulSoup` scraping iHerb HTML | **Tavily Search API** targeted at `iherb.com` | Scrape fallback unchanged (0.9); LLM fallback remains 5–25 |
| GPT-4o guessing supplier certifications from training data | **Tavily Search API** querying supplier pages first | 30–70 (LLM guess) → **72** (Tavily) |
| No FDA check | **OpenFDA food enforcement API** | New: 0.95 (government source) |
| No entity check | **OpenCorporates business registry API** | New: 0.90 live / 0.70 mock |

All new data flows through the existing `Enrichment` SQLite table with new
`DataType` values, requiring **zero schema changes**.

---

## New Data Types in the `Enrichment` Table

| `EntityType` | `DataType` | Source | Confidence | Added by |
|---|---|---|---|---|
| `"supplier"` | `"supplier_info"` | Tavily (primary) or LLM (fallback) | 0.7 (store wrapper) | `supplier_scraper.py` (existing, upgraded) |
| `"supplier"` | `"fda_risk"` | OpenFDA API | **0.95** | `openfda_api.py` (new) |
| `"supplier"` | `"entity_verification"` | OpenCorporates API or mock | **0.90 / 0.70** | `opencorporates_api.py` (new) |
| `"product"` | `"product_scrape"` | Tavily (primary) or LLM (fallback) | 0.9 (store wrapper) | `iherb_scraper.py` (existing, upgraded) |

---

## Files Changed

### Phase 2 — `agnes/backend/phase2_enrichment/`

---

#### `iherb_scraper.py` — MODIFIED

**Before:** `httpx` + `BeautifulSoup` fetched raw iHerb HTML. LLM fallback fired on any
HTTP error.

**After:** Tavily Search API is the primary path. LLM is last resort only.

| Symbol | Change |
|---|---|
| `import httpx` | **Removed** |
| `from bs4 import BeautifulSoup` | **Removed** |
| `_HEADERS` dict | **Removed** |
| `_parse_iherb_page(soup, result)` | **Removed** — BS4 parser |
| `_tavily_fetch_iherb(iherb_id)` | **Added** — calls `AsyncTavilyClient.search()` with `include_domains=["iherb.com"]`, `search_depth="advanced"`, `max_results=3` |
| `_parse_tavily_iherb(tavily_response, base_result)` | **Added** — regex extraction of certifications/ingredients/price/brand from Tavily content strings |
| `scrape_iherb_product()` | **Modified** — resolution order is now: cache → Tavily → LLM |
| `_llm_fallback_iherb()` | **Modified** — `_inference_note` updated to `"Data inferred by LLM (Tavily also failed)"` |
| `scrape_all_iherb_products()` | **Modified** — log summary now reports Tavily vs LLM split |

**Tavily query string:**
```
"Find the product certifications and ingredients for iHerb product {iherb_id}"
```

**New `scrape_success` logic:**
- `True` only on Tavily success
- LLM fallback leaves `scrape_success=False` (unchanged from before)

---

#### `supplier_scraper.py` — MODIFIED

**Before:** Only data source was `SUPPLIER_INFERENCE_PROMPT` → GPT-4o. No real web lookup.

**After:** Tavily runs first. LLM is demoted to fallback.

| Symbol | Change |
|---|---|
| `_CERT_KEYWORDS` list | **Added** — 20-entry list of certification strings to match in Tavily content |
| `_tavily_enrich_supplier(supplier_name)` | **Added** — calls `AsyncTavilyClient.search()` with `search_depth="advanced"`, `max_results=5`; parses HQ via regex and certs via keyword scan; returns `confidence=72, source="tavily_search"` |
| `enrich_supplier()` | **Modified** — resolution order: cache → Tavily → LLM. `source` field now set to `"tavily_search"` or `"llm_inference"` |
| `SUPPLIER_INFERENCE_PROMPT` | **Kept** — demoted to fallback, not removed |
| Summary log in `enrich_all_suppliers()` | **Modified** — now reports `{tavily_count} via Tavily` |

**Tavily query string:**
```
"What are the headquarters and official compliance certifications (ISO, GMP, etc.) for the supplier {supplier_name}?"
```

**Confidence values by source:**

| Source | `result["confidence"]` |
|---|---|
| Tavily | **72** |
| LLM (major company) | 60–70 (unchanged) |
| LLM (unknown) | 30–40 (unchanged) |
| No API key | 20 (unchanged) |

---

#### `openfda_api.py` — CREATED (new file)

Calls the public FDA food enforcement endpoint. No API key required.

**Endpoint:**
```
GET https://api.fda.gov/food/enforcement.json
    ?search=recalling_firm:"{supplier_name}"&limit=5
```

**Public functions:**

```python
async def check_supplier_fda_risk(supplier_name: str) -> dict
```
Returns one of:
```python
{"status": "Warning", "enforcement_count": int, "latest_recall": str,
 "latest_recall_date": str, "product_description": str, "classification": str}

{"status": "Clear"}

{"status": "Error", "error": str}
```

```python
async def check_all_suppliers_fda(suppliers: list[dict]) -> list[dict]
```
Iterates all suppliers from `get_all_suppliers()`. Calls
`store_enrichment(data_type="fda_risk", confidence=0.95)` for each.
Rate limit: 0.25 s between requests.

**Error handling:**
- HTTP 404 → treated as `"Clear"` (OpenFDA returns 404 for zero results)
- HTTP 429 → respects `Retry-After` header, retries once
- Timeout → `{"status": "Error", "error": "timeout"}`

---

#### `opencorporates_api.py` — CREATED (new file)

Verifies supplier business registration. Uses public OpenCorporates search API.
Falls back to hardcoded mock data when API key is absent and live request fails.

**Endpoint:**
```
GET https://api.opencorporates.com/v0.4/companies/search
    ?q={supplier_name}&jurisdiction_code=us&format=json[&api_token=...]
```

**Public functions:**

```python
async def verify_supplier_entity(supplier_name: str) -> dict
```
Returns:
```python
{"status": "Active" | "Dissolved" | "Unknown",
 "registered_name": str, "jurisdiction": str,
 "company_number": str, "incorporation_date": str,
 "source": "opencorporates_live" | "opencorporates_mock"}
```

```python
async def verify_all_suppliers(suppliers: list[dict]) -> list[dict]
```
Iterates all suppliers. Calls
`store_enrichment(data_type="entity_verification", confidence=0.90|0.70)`.
Rate limit: 0.5 s between requests.

**Mock fallback `_MOCK_ENTITIES`** (used when OPENCORPORATES_API_KEY is absent
and live request fails):

| Supplier | Mock status |
|---|---|
| ADM | Active |
| Cargill | Active |
| Ingredion | Active |
| IFF | Active |
| Ashland | Active |
| Univar Solutions | Active |
| All others | Unknown |

**Confidence:**
- Live result → `0.90`
- Mock result → `0.70`

---

#### `enrichment_store.py` — MODIFIED

Added two read helpers for the new data types:

```python
def get_fda_risk(supplier_id: int) -> Optional[dict]:
    """Get OpenFDA enforcement risk record for a supplier."""

def get_entity_verification(supplier_id: int) -> Optional[dict]:
    """Get OpenCorporates entity verification record for a supplier."""
```

Both are thin wrappers around `get_enrichment()`. No schema changes — the
`Enrichment` table already supports arbitrary `DataType` strings.

---

### Phase 2 — `agnes/backend/`

#### `run_phase2.py` — MODIFIED

Added Steps 3 & 4, two new CLI flags, and shared `suppliers` variable to avoid
re-fetching between steps.

| Change | Detail |
|---|---|
| `--skip-fda` flag | Skips Step 3 (OpenFDA) |
| `--skip-opencorporates` flag | Skips Step 4 (OpenCorporates) |
| Step 3: OpenFDA Risk Check | Calls `check_all_suppliers_fda(get_all_suppliers())` |
| Step 4: OpenCorporates Entity Verification | Calls `verify_all_suppliers(suppliers)`, reuses supplier list from Step 3 if it ran |
| Compliance inference | Renumbered from Step 3 → **Step 5** (logic unchanged) |
| `import sys` | Removed (was unused) |

**Full step sequence after upgrade:**

| Step | Name | Skip flag |
|---|---|---|
| 1 | iHerb Product Scraping (Tavily) | `--skip-iherb` |
| 2 | Supplier Enrichment (Tavily + LLM fallback) | `--skip-suppliers` |
| 3 | OpenFDA Enforcement Risk Check | `--skip-fda` |
| 4 | OpenCorporates Entity Verification | `--skip-opencorporates` |
| 5 | Compliance Inference (LLM) | `--skip-compliance` |

---

### Project-level files

#### `agnes/backend/config.py` — MODIFIED

```python
# Added:
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
OPENCORPORATES_API_KEY = os.getenv("OPENCORPORATES_API_KEY", "")
```

#### `agnes/requirements.txt` — MODIFIED

```
# Added:
tavily-python>=0.3.0
```

Note: `httpx` and `beautifulsoup4` are retained because other modules may
depend on them. Safe to remove from `requirements.txt` only after a full
grep confirms no other imports.

---

## Downstream Propagation — Phase 3

These changes were required to consume the new enrichment data types in the
reasoning pipeline.

---

#### `phase3_reasoning/confidence_scorer.py` — MODIFIED

**Problem:** `_is_mock()` could not distinguish `source="tavily_search"` from
`source="llm_inference"` — both got the same 25-point supplier quality score.
No FDA or entity risk was factored into confidence at all.

**Changes:**

| Symbol | Change |
|---|---|
| `_is_mock(d)` | **Modified** — now only returns `False` for `source="tavily_search"`; LLM inference is treated as lower quality |
| `_supplier_quality_score(supplier_data)` | **Added** — returns 25 (Tavily) / 15 (LLM) / 5 (none) |
| `_regulatory_adjustment(fda_data, entity_data)` | **Added** — post-score multiplier: Dissolved→×0.10, FDA Warning→×0.75, Unknown entity→×0.90 |
| `score_proposal_confidence()` signature | **Modified** — added `fda_data=None, entity_data=None` params |
| Factor 4 scoring | **Modified** — now calls `_supplier_quality_score()` instead of binary `_is_mock()` check |
| Final score | **Modified** — multiplied by `_regulatory_adjustment()` after 4-factor sum |

**Score impact examples:**

| Scenario | Before | After |
|---|---|---|
| Tavily supplier, ALL_PASS compliance | 100% | 100% |
| LLM-inferred supplier, ALL_PASS compliance | 85% | **75%** |
| Tavily supplier, FDA Warning | 100% | **75%** |
| Any supplier, entity Dissolved | any | **×0.10** |

---

#### `phase3_reasoning/sourcing_optimizer.py` — MODIFIED

**Problem:** Risk factors in proposals were blind to FDA enforcement history
and entity registration status. Dissolved suppliers could receive HIGH priority.

**Changes:**

| Symbol | Change |
|---|---|
| `optimize_sourcing()` signature | **Modified** — added `fda_data_map=None, entity_data_map=None` |
| FDA risk injection | **Added** — if `fda.status == "Warning"`, appends `"FDA enforcement history: N record(s). Latest: ..."` to `risk_factors` |
| Entity risk injection | **Added** — Dissolved appends blocking risk factor; Unknown appends uncertainty risk factor |
| Priority logic | **Modified** — `entity_status == "Dissolved"` forces `priority = "LOW"` regardless of compliance status |

---

#### `phase3_reasoning/verification_agent.py` — MODIFIED

**Problem:** Only 4 claims were verified per proposal. Two new verifiable facts
(FDA clean record, active entity) had no corresponding verification claims.

**Changes:**

| Symbol | Change |
|---|---|
| `verify_proposal()` signature | **Modified** — added `fda_data=None, entity_data=None` |
| Claim 5: `"fda_enforcement_clear"` | **Added** — `VERIFIED` if Clear, `CONTRADICTED` if Warning, `UNVERIFIED` if missing |
| Claim 6: `"supplier_entity_active"` | **Added** — `VERIFIED` if Active, `CONTRADICTED` if Dissolved, `UNVERIFIED` if Unknown |

**Impact on downstream confidence:** If either new claim is `CONTRADICTED`,
the existing logic in `run_phase3.py` (line 181) applies the ×0.5 confidence
downgrade and appends `"Verification agent flagged contradicted claims"` to
`risk_factors`.

---

#### `run_phase3.py` — MODIFIED

**Problem:** `fda_data_map` and `entity_data_map` were never built or passed
to any downstream function.

**Changes:**

| Location | Change |
|---|---|
| Imports | Added `get_fda_risk`, `get_entity_verification` |
| Step 2 (supplier loading loop) | **Added** — builds `fda_data_map: Dict[int, dict]` and `entity_data_map: Dict[int, dict]` per group alongside `supplier_data_map` |
| Step 4 call to `optimize_sourcing()` | **Modified** — passes `fda_data_map=`, `entity_data_map=` |
| Step 5 call to `score_proposal_confidence()` | **Modified** — passes `fda_data=fda_data_map.get(sid)`, `entity_data=entity_data_map.get(sid)` |
| Step 5 call to `verify_proposal()` | **Modified** — passes same FDA and entity dicts |

---

## Downstream Propagation — Phase 4

---

#### `phase4_output/evidence_trail_builder.py` — MODIFIED

**Problem:** Evidence trails contained no citations for FDA enforcement history
or entity registration status. The two new verification claims (added in
`verification_agent.py`) had no corresponding `_claim_label()` entries and no
citation-building logic, which would have caused them to appear in trails as
raw key strings with empty citations.

**Changes:**

| Symbol | Change |
|---|---|
| Imports | Added `get_fda_risk`, `get_entity_verification` from `enrichment_store` |
| `_fda_citation(supplier_id)` | **Added** — loads `fda_risk` record, builds citation with OpenFDA URL and snippet |
| `_entity_citation(supplier_id)` | **Added** — loads `entity_verification` record, builds citation with OpenCorporates URL (or empty if mock); labels as `live` or `mock` |
| `_claim_label()` | **Modified** — added `"fda_enforcement_clear"` and `"supplier_entity_active"` label maps (one string per VERIFIED/UNVERIFIED/CONTRADICTED status) |
| `_build_from_row()` | **Modified** — calls `_fda_citation()` and `_entity_citation()` after loading `supplier_data`; routes them into the claims loop via two new `elif` branches |

**No changes to `retriever.py`:** The retriever already embeds all records
from the `Enrichment` table without filtering by `DataType`, so `fda_risk`
and `entity_verification` records are automatically included in the search
index when it is rebuilt.

**No changes to `api.py` or `chat_agent.py`:** Both consume evidence trails
and the retrieval index — both of which are already updated above.

---

## Interface Contracts — What Your Coworkers Must Know

### Data your code now writes (Phase 2 outputs)

If any coworker reads from the `Enrichment` table, they should be aware of
these new rows:

```sql
-- New rows written per supplier after Phase 2 runs:
SELECT * FROM Enrichment
WHERE DataType IN ('fda_risk', 'entity_verification');
```

**`fda_risk` payload shape:**
```json
{
  "status": "Warning | Clear | Error",
  "enforcement_count": 3,
  "latest_recall": "Undeclared allergen: peanut",
  "latest_recall_date": "20240315",
  "product_description": "Vitamin D3 supplement...",
  "classification": "Class II",
  "supplier_id": 7,
  "supplier_name": "Cargill",
  "checked_at": "2026-04-18T..."
}
```

**`entity_verification` payload shape:**
```json
{
  "status": "Active | Dissolved | Unknown",
  "registered_name": "Cargill, Incorporated",
  "jurisdiction": "us_de",
  "company_number": "0000017843",
  "incorporation_date": "1936-06-20",
  "source": "opencorporates_live | opencorporates_mock",
  "supplier_id": 7,
  "supplier_name": "Cargill",
  "checked_at": "2026-04-18T..."
}
```

### `supplier_info` payload — new `source` field

The `supplier_info` payload now always includes a `source` key:

| Value | Meaning |
|---|---|
| `"tavily_search"` | Data came from a real Tavily web search |
| `"llm_inference"` | Data was hallucinated by GPT-4o |
| `"none"` | No enrichment was possible (no API keys) |

**Any code that reads `supplier_info` and makes decisions based on data
quality must check `source`.**  The confidence scorer in Phase 3 has been
updated. If your code also does quality-gating on this field, use the same
mapping: `tavily_search` = high quality, `llm_inference` = medium, `none`
= low.

### `verification_agent` — 2 new claim keys

After these changes, `VerificationsJson` in the `SourcingProposal` table can
contain two additional keys:

```json
{
  "supplier_identity": "VERIFIED",
  "compliance_claims": "VERIFIED",
  "consolidation_footprint": "VERIFIED",
  "savings_bounds": "VERIFIED",
  "fda_enforcement_clear": "VERIFIED | CONTRADICTED | UNVERIFIED",
  "supplier_entity_active": "VERIFIED | CONTRADICTED | UNVERIFIED"
}
```

Any code that iterates `VerificationsJson` should handle these keys. The
`verification_summary()` function is unchanged — it already handles arbitrary
claim keys by design.

### Function signatures changed (breaking if called externally)

| Function | New parameters |
|---|---|
| `optimize_sourcing(...)` | `fda_data_map=None, entity_data_map=None` |
| `score_proposal_confidence(...)` | `fda_data=None, entity_data=None` |
| `verify_proposal(...)` | `fda_data=None, entity_data=None` |

All new parameters are **keyword-only with `None` defaults** — existing
callers without the new arguments will continue to work without modification.
The new data simply won't be applied (equivalent to the pre-upgrade behaviour).

---

## Environment Variables Required

| Variable | Required | Default | Used by |
|---|---|---|---|
| `TAVILY_API_KEY` | Yes for Tavily path | `""` (falls back to LLM) | `iherb_scraper.py`, `supplier_scraper.py` |
| `OPENCORPORATES_API_KEY` | No | `""` (falls back to mock) | `opencorporates_api.py` |
| `OPENAI_API_KEY` | Only for LLM fallback | `""` | `iherb_scraper.py`, `supplier_scraper.py` |

Add to `.env`:
```
TAVILY_API_KEY=tvly-...
OPENCORPORATES_API_KEY=          # leave blank to use mock fallback
```

---

## Potential Conflicts to Check Against Coworkers' Branches

| Area | Risk | How to verify |
|---|---|---|
| `Enrichment` table reads | If a coworker added reads for `supplier_info` and checks `source`, their logic may conflict with the new `"tavily_search"` value | Grep for `get_supplier_info` and any `source` field checks |
| `VerificationsJson` parsing | If a coworker iterates the verification dict and hard-codes expected keys, the two new keys may cause unexpected behaviour | Grep for `VerificationsJson` |
| `run_phase2.py` step numbering | If a coworker's branch references Step 3 as compliance inference, it is now Step 5 | Check their `run_phase2.py` diff |
| `confidence_scorer.py` factor weights | If a coworker modified the 4-factor scoring, their changes will conflict with `_supplier_quality_score()` and `_regulatory_adjustment()` | Merge both sets of changes; ensure total base score still sums to 100 before the multiplier |
| `requirements.txt` | If a coworker also added packages, merge both additions | Simple line-level merge |
