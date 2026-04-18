# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Agnes** is an AI supply chain decision-support system for the TUM.AI Makeathon 2026 / Spherecast Challenge. It identifies substitutable raw material ingredients across CPG company BOMs, verifies compliance constraints, and produces sourcing consolidation proposals with full evidence trails.

Judging emphasis: **reasoning quality and evidence trails**, not UI polish.

## Running the Pipeline

All commands run from `agnes/` (where `requirements.txt` lives). `db.sqlite` is expected at `database/db.sqlite` relative to repo root.

```bash
cd agnes

# Install dependencies
pip install -r requirements.txt

# Copy and fill in API keys
cp .env.example .env

# Run phases sequentially
python -m backend.run_phase1                  # Extract + cluster ingredients
python -m backend.run_phase1 --no-semantic    # Skip OpenAI (exact-match only)

python -m backend.run_phase2                  # Scrape + enrich external data
python -m backend.run_phase2 --skip-iherb     # Skip iHerb scraping
python -m backend.run_phase2 --skip-suppliers # Skip supplier enrichment

python -m backend.run_phase3                  # Reason, validate, score proposals
python -m backend.run_phase3 --top-groups 20  # Limit to top N substitution groups
python -m backend.run_phase3 --no-persist     # Dry run

python -m backend.run_phase4                  # Build evidence trails + retrieval index
python -m backend.run_phase4 --rebuild-index

# Start the API server
uvicorn backend.phase4_output.api:app --reload --port 8000

# Run tests
python -m pytest tests/
python -m pytest tests/test_phase1.py -v

# Frontend (from agnes/frontend/)
npm install
npm run dev   # Runs on localhost:3000
```

If OpenAI quota is exhausted, use `backend/mock_phase2.py` to generate plausible mock enrichment data. Mock records are marked `source: "mock"` and scored lower by the confidence scorer.

## Architecture

Four sequential phases, each producing persisted output consumed by the next:

```
SQLite DB
  └─ Phase 1: Extraction      (sku_parser → semantic_matcher → substitution_groups)
       └─ Phase 2: Enrichment  (iherb_scraper + supplier_scraper + compliance_inferrer)
            └─ Phase 3: Reasoning (substitution_validator → compliance_checker →
                                   sourcing_optimizer → confidence_scorer → verification_agent)
                 └─ Phase 4: Output (evidence_trail_builder → retriever → api + chat_agent)
```

### Phase 1 — Extraction
- **SKU format for raw materials:** `RM-C{company_id}-{ingredient-name}-{8-char-hash}`
- `sku_parser.py` extracts `ingredient_name` from every SKU; also parses 14 retailer formats for finished goods (iHerb, Walmart, Amazon, Target, Costco, etc.)
- `semantic_matcher.py` clusters ingredient names using OpenAI `text-embedding-3-small` + Union-Find; similarity threshold is `0.85` (env: `SIMILARITY_THRESHOLD`). Embeddings are cached in `ingredient_embeddings.npz` to avoid re-fetching.
- A **SubstitutionGroup** is the core output: canonical ingredient name, all member SKUs, available suppliers, consuming finished goods, and whether cross-company consolidation is possible.

### Phase 2 — Enrichment
- **iHerb scraper** fetches product pages for finished goods with iHerb SKUs, extracting certifications (Non-GMO, Organic, Kosher, Halal, Vegan, GMP, NSF, USP…). Rate-limited to 1 req/sec; results cached to `enrichment_cache/`.
- **Supplier scraper** uses GPT-4o (JSON mode) to infer supplier location, certifications, and specialties from supplier names. Hardcoded known-location overrides for major suppliers (ADM, Cargill, Ingredion, IFF…).
- **Compliance inferrer** uses GPT-4o to derive what certifications ALL ingredients in a finished good must carry (e.g., "USDA Organic" label → every ingredient must be organic-certified). Confidence is 70+ when scraped data is available, lower otherwise.
- All enrichment records stored in an `Enrichment` SQLite table (EntityType, EntityId, DataType, DataJson, SourceUrl, Confidence).

### Phase 3 — Reasoning
- **`substitution_validator.py`** is entirely rule-based (no LLM). Checks 11 chemistry axes (hydration state, source animal/plant, salt form, extraction method, stereochemistry, vitamin form variants). Subtracts 0.15 per flagged axis; score < 0.55 = do not substitute.
- **`compliance_checker.py`** cross-references supplier certifications against product requirements. Organic/Kosher/Halal/Vegan are *blocking* — missing them is a hard FAIL. Others are UNKNOWN (warning only).
- **`sourcing_optimizer.py`** ranks suppliers by "reach" (how many companies in the group they can serve), generates up to 3 proposals per group, estimates savings heuristically (max 30%).
- **`confidence_scorer.py`** scores 0–100 from four 25-pt factors: functional equivalence, external data quality (real=25, mock=5), compliance status, supplier data quality.
- **`verification_agent.py`** is a hallucination guardrail — purely rule-based cross-referencing of proposal claims against evidence records. Any CONTRADICTED claim fails the proposal.

### Phase 4 — Output
- **`evidence_trail_builder.py`** builds citations by joining proposals with enrichment records — no LLM involved. Each claim has status VERIFIED/UNVERIFIED/CONTRADICTED with source URL and snippet.
- **`retriever.py`** builds an embedding index over two corpora: proposals (`P{n}` doc IDs) and enrichment records (`E{n}` doc IDs). Falls back to character-trigram TF-IDF if no API key.
- **`api.py`** (FastAPI): `GET /api/health`, `GET /api/stats`, `GET /api/proposals`, `POST /api/chat`. CORS is open to `localhost:3000`.
- **`chat_agent.py`** grounds answers in retrieved evidence; uses bracketed citation tags `[P12]`/`[E47]`; has a rule-based fallback when no LLM key is available.

## Database Schema

```
Company(Id, Name)                                   — 61 rows
Product(Id, SKU, CompanyId, Type)                   — 1025 rows (876 raw, 149 finished)
BOM(Id, ProducedProductId)                          — 149 rows
BOM_Component(BOMId, ConsumedProductId)             — 1528 rows
Supplier(Id, Name)                                  — 40 rows
Supplier_Product(SupplierId, ProductId)             — 1633 rows
Enrichment(EntityType, EntityId, DataType, DataJson, SourceUrl, Confidence)  — written by Phase 2
```

Phase 1 also writes substitution group tables; Phase 3 writes `SourcingProposal` tables.

## Key Design Decisions

- **No Cognee/Dify**: The original proposal used GraphRAG + Dify orchestration. The actual build is a self-contained Python pipeline — simpler to debug under hackathon time pressure.
- **LLM-free hot path**: Phases 1 (with `--no-semantic`), 3, and 4 evidence building all run without any LLM calls. The system degrades gracefully when quota runs out.
- **Mock data path**: `mock_phase2.py` lets Phase 3+ run even with zero API calls. Mock data is identifiable by `source: "mock"` and confidence-scored down automatically.
- **Similarity threshold 0.85** is intentionally high to avoid merging chemically distinct compounds (e.g., magnesium-citrate vs. magnesium-stearate) that share a keyword but are NOT substitutable.
