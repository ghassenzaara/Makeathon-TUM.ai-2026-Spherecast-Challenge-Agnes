# Agnes AI Supply Chain Manager — Full Implementation Plan

> Based on [Final_Architecture_Recommendation.md](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/docs/Final_Architecture_Recommendation.md)

## Context & Goal

Build a working prototype of "Agnes" — an AI-powered decision-support system that analyzes fragmented CPG supply chain data, identifies ingredient substitutions, enriches with external compliance data, and produces explainable, evidence-backed sourcing recommendations.

**Database Stats:** 61 companies, 149 finished goods, 876 raw materials, 1,528 BOM components, 40 suppliers, 1,633 supplier-product links. **No prices, no lead times, no certifications exist in the data.**

---

## User Review Required

> [!IMPORTANT]
> **Technology Stack Decision:** This plan uses Python + FastAPI + OpenAI API + a simple HTML/JS frontend. No Cognee, no Dify — keeping it simple to maximize reasoning quality over infrastructure. Please confirm this is acceptable.

> [!IMPORTANT]
> **API Keys Needed:** OpenAI API key (for embeddings + GPT-4o), and optionally a SerpAPI/Tavily key for web search enrichment. Do you have these?

> [!WARNING]
> **Scraping Strategy:** iHerb and supplier website scraping may be rate-limited or blocked. The plan includes fallback strategies (LLM inference when scraping fails), but real-time scraping success is not guaranteed.

## Open Questions

1. **Team context:** How many hours remain in the hackathon? This affects which components to prioritize.
2. **API budget:** Any spending limits on OpenAI API calls? Embedding 876 ingredients + LLM inference calls can add up.
3. **Deployment:** Will this run locally for the demo, or does it need to be deployed somewhere?
4. **Existing work:** Has any team member already started on any component (e.g., Dify workflows)?

---

## Project Structure

```
agnes/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # API keys, settings
│   ├── db/
│   │   ├── connection.py          # SQLite connection helper
│   │   └── queries.py             # All SQL queries as functions
│   ├── phase1_extraction/
│   │   ├── sku_parser.py          # SKU string parsing logic
│   │   ├── semantic_matcher.py    # Embedding-based ingredient grouping
│   │   └── substitution_groups.py # Build & store substitution groups
│   ├── phase2_enrichment/
│   │   ├── iherb_scraper.py       # iHerb product page scraper
│   │   ├── supplier_scraper.py    # Supplier website recon
│   │   ├── compliance_inferrer.py # LLM-based compliance inference
│   │   └── enrichment_store.py    # Store enriched data (JSON/SQLite)
│   ├── phase3_reasoning/
│   │   ├── substitution_validator.py  # Validate substitutions
│   │   ├── compliance_checker.py      # Check compliance constraints
│   │   ├── sourcing_optimizer.py      # Cost/lead-time optimization
│   │   ├── confidence_scorer.py       # Score confidence 0-100%
│   │   └── verification_agent.py      # Hallucination guardrail
│   ├── phase4_output/
│   │   ├── evidence_trail.py      # Build citation chains
│   │   └── recommendation.py      # Format final recommendations
│   └── api/
│       ├── routes.py              # API endpoints
│       └── chat.py                # Chat/conversational endpoint
├── frontend/
│   ├── index.html                 # Dashboard SPA
│   ├── style.css                  # Styling
│   └── app.js                     # Frontend logic
├── data/
│   └── enrichment_cache/          # Cached scraping results
├── db.sqlite                      # Source database (existing)
├── requirements.txt
└── README.md
```

---

## Proposed Changes

### Phase 1: Smart Data Extraction & Semantic Matching (~3 hours)

**Goal:** Parse SKUs, extract canonical ingredient names, and cluster functionally equivalent ingredients into Substitution Groups.

---

#### [NEW] [config.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/config.py)

- Environment variable loading (OpenAI key, model names)
- Constants: similarity threshold (0.85), confidence thresholds, DB path

#### [NEW] [connection.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/db/connection.py)

- SQLite connection factory with context manager
- Row factory for dict-style access

#### [NEW] [queries.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/db/queries.py)

- `get_all_raw_materials()` → returns all 876 raw materials with company info
- `get_all_finished_goods()` → returns 149 finished goods with BOM components
- `get_bom_for_product(product_id)` → returns ingredient list for a finished good
- `get_suppliers_for_product(product_id)` → returns supplier options
- `get_all_suppliers()` → returns all 40 suppliers

#### [NEW] [sku_parser.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase1_extraction/sku_parser.py)

Core logic:
```python
import re

def parse_sku(sku: str) -> dict:
    """
    Parse SKU like 'RM-C28-vitamin-d3-cholecalciferol-8956b79c'
    Returns: {
        'type': 'raw-material',       # RM = raw-material, FG = finished-good
        'company_id': 28,
        'ingredient_name': 'vitamin-d3-cholecalciferol',
        'hash': '8956b79c',
        'iherb_id': None               # For FG SKUs like 'FG-iherb-10421'
    }
    """
    # Handle FG-iherb-{id} pattern
    fg_match = re.match(r'FG-iherb-(\d+)', sku)
    if fg_match:
        return {'type': 'finished-good', 'iherb_id': fg_match.group(1), ...}
    
    # Handle RM-C{id}-{name}-{hash} pattern  
    rm_match = re.match(r'RM-C(\d+)-(.+)-([a-f0-9]{8})$', sku)
    if rm_match:
        return {'type': 'raw-material', 'company_id': int(rm_match.group(1)),
                'ingredient_name': rm_match.group(2), 'hash': rm_match.group(3)}
```

#### [NEW] [semantic_matcher.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase1_extraction/semantic_matcher.py)

Two-stage matching strategy:

1. **Exact name match** — group ingredients with identical canonical names (e.g., `vitamin-d3-cholecalciferol` across companies 1, 28, 30)
2. **Semantic similarity** — use OpenAI `text-embedding-3-small` to embed all unique ingredient names, then cluster using cosine similarity > 0.85 to catch near-equivalents (e.g., `sunflower-lecithin` ≈ `soy-lecithin`)

```python
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

async def build_ingredient_embeddings(ingredients: list[str]) -> np.ndarray:
    """Embed all unique ingredient names using OpenAI."""
    client = OpenAI()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=ingredients
    )
    return np.array([e.embedding for e in response.data])

def cluster_ingredients(names, embeddings, threshold=0.85):
    """Group ingredients by cosine similarity."""
    sim_matrix = cosine_similarity(embeddings)
    # Union-Find to merge groups above threshold
    ...
```

#### [NEW] [substitution_groups.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase1_extraction/substitution_groups.py)

- Takes clustered ingredients → builds `SubstitutionGroup` objects
- Each group contains: canonical name, list of (product_id, company_id, sku) tuples, all associated suppliers, all finished goods that consume any member
- Stores results in a new SQLite table `substitution_group` or in-memory dict
- Computes `cross_company_count` (how many distinct companies use this ingredient) — higher = more consolidation potential

**Output data model:**
```python
@dataclass
class SubstitutionGroup:
    id: int
    canonical_name: str              # e.g., "vitamin-d3-cholecalciferol"
    members: list[IngredientMember]  # All product records in this group
    suppliers: list[SupplierInfo]    # All suppliers that can supply any member
    consuming_products: list[int]    # Finished good IDs that use this ingredient
    cross_company_count: int         # Number of distinct companies
    similarity_score: float          # Average pairwise similarity (1.0 = exact match)
```

---

### Phase 2: External Enrichment Agent (~4-5 hours)

**Goal:** Fill missing compliance, pricing, and certification data from external sources.

---

#### [NEW] [iherb_scraper.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase2_enrichment/iherb_scraper.py)

- Finished goods have SKUs like `FG-iherb-10421` → maps to `https://www.iherb.com/pr/p/10421`
- Use `httpx` + `BeautifulSoup` to extract:
  - Product title, brand, description
  - Label claims (Non-GMO, Organic, Kosher, Vegan, etc.)
  - Listed ingredients
  - Price (if visible)
- Rate-limit to 1 req/second, cache results in `data/enrichment_cache/iherb/`
- **Fallback:** If scraping is blocked, use the iHerb ID + product name in an LLM prompt to infer likely certifications

```python
async def scrape_iherb_product(iherb_id: str) -> dict:
    """Scrape product page and extract structured info."""
    url = f"https://www.iherb.com/pr/p/{iherb_id}"
    # ... fetch, parse, extract certifications
    return {
        'iherb_id': iherb_id,
        'title': ...,
        'brand': ...,
        'certifications': ['Non-GMO', 'GMP Certified'],
        'ingredients_text': ...,
        'price_usd': ...,
        'url': url  # For evidence trail
    }
```

#### [NEW] [supplier_scraper.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase2_enrichment/supplier_scraper.py)

- For each of the 40 suppliers, perform web search (Tavily/SerpAPI or direct Google) for: `"{supplier_name}" certifications specifications`
- Extract from results:
  - Corporate location (→ proxy for lead time estimation)
  - Certifications held (Organic, Kosher, Halal, GMP, ISO)
  - Product catalog info
- Cache results per supplier

#### [NEW] [compliance_inferrer.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase2_enrichment/compliance_inferrer.py)

Uses GPT-4o to infer compliance requirements from finished good context:

```python
COMPLIANCE_PROMPT = """
You are a CPG compliance expert. Given this finished product information, 
infer the compliance requirements that ALL raw material ingredients must satisfy.

Product: {product_name}
Brand: {company_name}
iHerb Labels: {scraped_labels}
Ingredients: {ingredients_list}

Return a JSON object with:
- required_certifications: list of certifications ALL ingredients must have
- inferred_constraints: any quality constraints (e.g., "must be plant-based")
- confidence: 0-100 how confident you are in these requirements
- reasoning: explain your inference chain
"""
```

Key inference rules:
- If finished good is labeled "Organic" → all ingredients need organic certification
- If labeled "Non-GMO" → all ingredients must be non-GMO sourced
- If labeled "Vegan" → no animal-derived ingredients
- If labeled "Kosher" → all ingredients + supplier must be Kosher certified

#### [NEW] [enrichment_store.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase2_enrichment/enrichment_store.py)

- Stores all enrichment data in a new SQLite table or JSON structure
- Schema: `enrichment(entity_type, entity_id, data_type, data_json, source_url, scraped_at, confidence)`
- Provides lookup functions: `get_certifications_for_supplier(supplier_id)`, `get_compliance_requirements_for_product(product_id)`, etc.

---

### Phase 3: Reasoning, Optimization & Trust (~4-5 hours)

**Goal:** Validate substitutions, check compliance, optimize sourcing, score confidence, and guard against hallucinations.

---

#### [NEW] [substitution_validator.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase3_reasoning/substitution_validator.py)

For each substitution group, validates whether members are truly interchangeable:

```python
@dataclass
class SubstitutionValidation:
    group_id: int
    is_valid: bool
    functional_equivalence_score: float   # 0-1
    known_differences: list[str]          # e.g., "source organism differs"
    recommendation: str                   # "safe to substitute" / "review needed"
```

- Uses LLM to analyze whether ingredient variants are functionally equivalent
- Considers form differences (e.g., citric acid anhydrous vs. citric acid monohydrate)

#### [NEW] [compliance_checker.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase3_reasoning/compliance_checker.py)

Cross-references:
1. Finished good's inferred compliance requirements (from Phase 2)
2. Proposed substitute ingredient's certifications (from Phase 2)
3. Proposed supplier's certifications (from Phase 2)

```python
@dataclass 
class ComplianceResult:
    product_id: int
    ingredient_group_id: int
    proposed_supplier_id: int
    checks: list[ComplianceCheck]  # Each certification requirement
    all_passed: bool
    blocking_issues: list[str]
    warnings: list[str]           # e.g., "certificate expires soon"

@dataclass
class ComplianceCheck:
    requirement: str              # e.g., "USDA Organic"
    status: str                   # "PASS" / "FAIL" / "UNKNOWN"
    evidence: str                 # Source of the check
    source_url: str               # Link for evidence trail
```

#### [NEW] [sourcing_optimizer.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase3_reasoning/sourcing_optimizer.py)

Generates consolidation proposals:

- **Input:** Substitution groups + enrichment data + compliance results
- **Logic:**
  1. For each substitution group with `cross_company_count >= 2`, calculate consolidation potential
  2. Rank suppliers by: number of companies they could serve, compliance pass rate, estimated geographic proximity (from supplier location)
  3. Estimate savings: `(num_companies - 1) * base_volume * estimated_discount_rate`
  4. Calculate risk scores: single-point-of-failure risk, lead time increase risk
- **Output:** Ranked list of `SourcingProposal` objects

```python
@dataclass
class SourcingProposal:
    id: int
    ingredient_group: SubstitutionGroup
    current_state: dict          # Current fragmented suppliers
    proposed_state: dict         # Consolidated to recommended supplier
    recommended_supplier: str
    estimated_savings_pct: float
    compliance_status: str       # "ALL_PASS" / "PARTIAL" / "REVIEW_NEEDED"
    risk_factors: list[str]
    confidence_score: float      # 0-100
    priority: str                # "HIGH" / "MEDIUM" / "LOW"
```

#### [NEW] [confidence_scorer.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase3_reasoning/confidence_scorer.py)

Assigns confidence score (0-100%) based on data completeness:

| Factor | Weight | Score Logic |
|--------|--------|-------------|
| Ingredient match quality | 25% | Exact name = 100, semantic > 0.95 = 80, > 0.85 = 60 |
| External data coverage | 25% | All certs verified = 100, partial = 50, none = 10 |
| Compliance verification | 25% | All checks PASS = 100, UNKNOWN present = 40, FAIL = 0 |
| Supplier data quality | 25% | Location + certs + specs = 100, partial = 50, name only = 10 |

- If score < 50 → flag for human review (do NOT auto-recommend)
- If score 50-75 → recommend with warnings
- If score > 75 → high confidence recommendation

#### [NEW] [verification_agent.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase3_reasoning/verification_agent.py)

Secondary LLM check (hallucination guardrail):

```python
VERIFICATION_PROMPT = """
You are a strict fact-checker for supply chain recommendations.
You must ONLY confirm claims that are directly supported by the provided evidence.

PROPOSED RECOMMENDATION:
{recommendation_text}

RAW EVIDENCE (scraped data):
{raw_evidence}

For each factual claim in the recommendation, respond:
- VERIFIED: if the raw evidence directly supports it
- UNVERIFIED: if there is no evidence for or against
- CONTRADICTED: if the evidence contradicts it

Be extremely strict. If a certification is claimed but not found in evidence, mark UNVERIFIED.
"""
```

- Uses low temperature (0.1) for maximum precision
- Any CONTRADICTED claim → reject the recommendation
- UNVERIFIED claims → reduce confidence score, add warning

---

### Phase 4: Output & Evidence Trail (~3 hours)

**Goal:** Present findings in an explainable, business-centric format with full citations.

---

#### [NEW] [evidence_trail.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase4_output/evidence_trail.py)

Builds citation chains for every recommendation:

```python
@dataclass
class EvidenceCitation:
    claim: str                    # What is being claimed
    source_type: str              # "iherb_scrape" / "supplier_website" / "llm_inference" / "database"
    source_url: str               # Clickable link
    extracted_text: str           # Exact text that supports the claim
    confidence: float             # How reliable this source is
    timestamp: str                # When the data was retrieved

@dataclass
class EvidenceTrail:
    recommendation_id: int
    citations: list[EvidenceCitation]
    summary: str                  # Human-readable summary
    # e.g., "Recommending consolidation to Supplier X. Evidence: 
    #  Supplier X website confirms Kosher certification [Link], 
    #  meeting the requirement inferred from Finished Good Y's label [Link]."
```

#### [NEW] [recommendation.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase4_output/recommendation.py)

Formats final output combining all Phase 3 results:

- Prioritized list of consolidation opportunities
- Each with: savings estimate, compliance status, risk flags, confidence score, evidence trail
- Export capability (JSON for API, formatted text for presentation)

#### [NEW] [routes.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/api/routes.py)

FastAPI endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/opportunities` | GET | List all consolidation opportunities, ranked |
| `/api/opportunities/{id}` | GET | Deep dive into one opportunity with evidence |
| `/api/ingredients` | GET | All substitution groups |
| `/api/ingredients/{group_id}` | GET | Details of a substitution group |
| `/api/suppliers` | GET | All suppliers with enrichment data |
| `/api/compliance/{product_id}` | GET | Compliance requirements for a finished good |
| `/api/pipeline/run` | POST | Trigger full pipeline execution |
| `/api/pipeline/status` | GET | Pipeline execution status |
| `/api/chat` | POST | Conversational query endpoint |

#### [NEW] [chat.py](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/api/chat.py)

Simple conversational interface using GPT-4o with function calling:

- System prompt includes context about all substitution groups and recommendations
- Functions available: `search_ingredients`, `get_recommendation`, `check_compliance`, `get_evidence`
- Enables ad-hoc queries like "What are the top 3 savings opportunities for vitamin ingredients?"

---

### Frontend (Simple but Functional)

#### [NEW] [index.html](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/frontend/index.html)

Three-panel layout matching the [UI spec](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/docs/step-by-step%20experience%20with%20the%20UI.md):

1. **Opportunities Inbox** — Cards ranked by value/confidence, color-coded by priority
2. **Deep Dive View** — Before/after supplier comparison, substitution logic visualization
3. **Trust & Evidence Panel** — Compliance checks with green ✅ / yellow ⚠️ / red ❌, clickable evidence links

Plus a collapsible chat sidebar for ad-hoc queries.

#### [NEW] [requirements.txt](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/requirements.txt)

```
fastapi>=0.110.0
uvicorn>=0.29.0
openai>=1.14.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
scikit-learn>=1.4.0
numpy>=1.26.0
python-dotenv>=1.0.0
```

---

## Execution Order & Time Estimates

| Step | Component | Time | Dependencies | Priority |
|------|-----------|------|-------------|----------|
| 1 | `config.py` + `db/` + `requirements.txt` | 30 min | None | 🔴 |
| 2 | `sku_parser.py` | 30 min | Step 1 | 🔴 |
| 3 | `semantic_matcher.py` | 1.5 hr | Step 2 + OpenAI key | 🔴 |
| 4 | `substitution_groups.py` | 1 hr | Step 3 | 🔴 |
| 5 | `iherb_scraper.py` | 1.5 hr | Step 2 (for iHerb IDs) | 🔴 |
| 6 | `supplier_scraper.py` | 1.5 hr | Step 1 | 🟡 |
| 7 | `compliance_inferrer.py` | 1 hr | Steps 4 + 5 | 🔴 |
| 8 | `enrichment_store.py` | 30 min | Steps 5-7 | 🔴 |
| 9 | `substitution_validator.py` | 1 hr | Step 4 | 🔴 |
| 10 | `compliance_checker.py` | 1 hr | Steps 7 + 8 | 🔴 |
| 11 | `sourcing_optimizer.py` | 1.5 hr | Steps 9 + 10 | 🔴 |
| 12 | `confidence_scorer.py` | 45 min | Step 11 | 🟡 |
| 13 | `verification_agent.py` | 45 min | Step 11 | 🟡 |
| 14 | `evidence_trail.py` + `recommendation.py` | 1 hr | Steps 11-13 | 🔴 |
| 15 | `routes.py` + `chat.py` + `main.py` | 1.5 hr | Step 14 | 🔴 |
| 16 | Frontend (`index.html`, `style.css`, `app.js`) | 2 hr | Step 15 | 🟡 |

**Total estimated: ~16-18 hours**

**If time-constrained (8-10 hours), cut:** Steps 6 (supplier scraping → use LLM inference only), 13 (verification agent), and simplify Step 16 (minimal frontend).

---

## Verification Plan

### Automated Tests

```bash
# 1. Verify SKU parsing covers all patterns in DB
python -c "from phase1_extraction.sku_parser import parse_sku; ..."

# 2. Run the full pipeline
python -m backend.main --run-pipeline

# 3. Start server and test endpoints
uvicorn backend.main:app --reload
curl http://localhost:8000/api/opportunities
curl http://localhost:8000/api/ingredients
```

### Manual Verification

1. **Phase 1 sanity check:** Verify that `vitamin-d3-cholecalciferol` from companies 1, 28, 30 lands in the same substitution group
2. **Phase 2 spot check:** Manually visit an iHerb page (e.g., `/pr/p/10421`) and compare scraped data to actual page
3. **Phase 3 logic check:** Take one high-confidence recommendation and manually verify the compliance logic chain
4. **End-to-end demo:** Walk through the "Sarah the sourcing manager" scenario from the [UI doc](file:///d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/docs/step-by-step%20experience%20with%20the%20UI.md)

### Browser Testing

- Open dashboard, verify opportunities load and are ranked
- Click an opportunity card → verify deep dive shows before/after + evidence
- Click compliance checkmarks → verify evidence modal shows source citations
- Test chat: "What substitutes exist for magnesium stearate?"

---

## Judging Criteria Coverage Map

| Criteria | Component(s) | Confidence |
|----------|-------------|------------|
| **Substitution Logic** | `sku_parser` + `semantic_matcher` + `substitution_groups` | ✅ Strong |
| **Missing External Info** | `iherb_scraper` + `supplier_scraper` + `compliance_inferrer` | ✅ Strong |
| **Handling Uncertainty** | `confidence_scorer` (flags low-data items for human review) | ✅ Strong |
| **Tradeoff Explanations** | `sourcing_optimizer` (cost vs lead time vs risk) | ✅ Strong |
| **Trust & Hallucination Control** | `verification_agent` + `evidence_trail` | ✅ Strong |
| **Scalability** | HITL feedback loop in architecture diagram (presentation talking point) | 🟡 Mentioned |
