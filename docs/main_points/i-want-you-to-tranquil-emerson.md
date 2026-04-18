# Plan — Phase 1 & Phase 2 Rebuild: Attribute-Rich Ingredients + Evidence-Backed Enrichment

## Context

The current Agnes pipeline treats ingredients as name strings. Phase 1 clusters by SKU-name similarity; Phase 2 fills in supplier/compliance fields via one-shot LLM calls with no structured provenance; Phase 3 is then forced to re-derive attributes from names via token regex ([substitution_validator.py:30-43](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase3_reasoning/substitution_validator.py#L30-L43)) and to match cert synonyms via a hardcoded list ([compliance_checker.py:35-57](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase3_reasoning/compliance_checker.py#L35-L57)). Evidence for every claim is free text; there is no per-field source or confidence.

The hackathon brief rewards "evidence trails," "trustworthiness," "hallucination control," and "quality of reasoning." This rebuild raises the whole pipeline's ceiling by changing the **data model** (attribute-rich ingredients, evidence ledger, shared ontologies) and by inverting the enrichment direction (LLM as form-filler and exception-finder, not fortune-teller).

Intended outcome: every number in the UI can be clicked and traced back to a source snippet; every substitution decision is backed by structured attribute comparison; every compliance recommendation is derived per-ingredient-per-finished-good with documented reasoning.

## Goals (Phase 1 + Phase 2 only)

1. Replace name-string clustering with **structured ingredient cards** (substance + attributes) and attribute-aware two-stage clustering.
2. Introduce a single **Evidence ledger** holding per-field provenance (`value`, `confidence`, `source_url`, `source_snippet`, `extracted_at`) used by both scraping and compliance inference.
3. Externalize two **ontologies** (substance aliases; certification synonyms) as JSON files consumed by Phase 1 clustering and Phase 2 normalization.
4. Refactor the Phase 2 scraper flow to **HTML → cleaned text blocks → LLM-as-form-filler** with JSON-schema output and per-field confidence.
5. Refactor compliance inference to be **ingredient-level**, inheriting constraints from finished goods through substitution groups, with **contradiction detection** between conflicting sources.
6. Keep deterministic rules as a safety net; use the LLM only to refine defaults against retrieved evidence.

## Out of scope

- Phase 3 reasoning changes (sourcing optimizer, savings formula, proposal tradeoffs).
- Phase 4 API/UI changes.
- Replacing SQLite, adding a vector DB, or introducing cognee/Neo4j.
- Changing run-script CLIs or adding new dependencies beyond `beautifulsoup4` (already present) and optionally `tiktoken` for chunking.

---

## Architecture overview

```
Phase 1:
  raw materials
   → SKU parse (existing)
   → AttributeExtractor  (NEW)  ──► IngredientCard + CardCertification + CardAllergen + Evidence
   → SubstanceAlias lookup (NEW ontology)
   → Two-stage clustering (NEW: constraint-aware Union-Find)
        Stage A: same-substance (strict, blocking attributes must agree)
        Stage B: functional-substitute LINKS between clusters (not merges)
   → SubstitutionGroup + UnifiedAttributes + DivergentAttributes

Phase 2:
  product pages / supplier pages
   → HTTP fetch (existing)
   → HTML → text block cleaner (NEW)
   → StructuredExtractor  (NEW: LLM fills a JSON schema, never free text)
   → CertificationOntology normalization (NEW ontology)
   → Per-field evidence written to Evidence ledger

  finished goods
   → BOM resolution
   → Rule-based compliance defaults (existing COMPLIANCE_PROMPT hints, kept as fallback)
   → LLM exception-finder ONLY when scraped evidence contradicts defaults
   → Per-ingredient requirements written, inherited through SubstitutionGroup
   → ContradictionDetector (NEW) flags vegan-label vs gelatin-ingredient etc.
```

---

## Part A — Schema changes

All additions to [agnes/backend/db/queries.py](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/db/queries.py). Follow the existing pattern: `create_*_tables()` + `clear_*_tables()` + `insert_*` + `get_*` helpers.

### New tables

**`IngredientCard`** — one row per raw-material `Product`
```
ProductId INTEGER PRIMARY KEY  (FK -> Product.Id)
Substance TEXT        -- canonical form (e.g., "citric-acid")
Form TEXT             -- powder | oil | isolate | extract | liquid | null
Grade TEXT            -- usp | food | pharma | cosmetic | null
Hydration TEXT        -- anhydrous | monohydrate | ... | null
SaltOrEster TEXT      -- citrate | gluconate | ... | null
Source TEXT           -- plant | animal | microbial | synthetic | null
SourceDetail TEXT     -- lanolin | lichen | corn | null
Chirality TEXT        -- l | d | dl | null
ExtractedAt TEXT
ExtractionMethod TEXT -- "sku-regex" | "llm" | "supplier-page" | "manual"
```

**`CardCertification`** (multi-value)
```
ProductId INTEGER, Certification TEXT (canonical from ontology), EvidenceId INTEGER
```

**`CardAllergen`** (multi-value)
```
ProductId INTEGER, Allergen TEXT, EvidenceId INTEGER
```

**`Evidence`** — the receipts ledger
```
Id INTEGER PRIMARY KEY AUTOINCREMENT
Claim TEXT                 -- e.g., "Supplier 17 holds USDA Organic"
SubjectType TEXT           -- "Product" | "Supplier" | "FinishedGood" | "SubstitutionGroup"
SubjectId INTEGER
FieldName TEXT             -- "certifications.organic", "substance", "source_detail", ...
SourceType TEXT            -- "scrape" | "llm-inference" | "ontology" | "sku-regex" | "mock"
SourceUrl TEXT
SourceSnippet TEXT         -- literal excerpt (max ~500 chars)
Confidence REAL            -- 0-1
ExtractedAt TEXT
```
Indices on `(SubjectType, SubjectId)` and `(FieldName)`.

**`IngredientComplianceRequirement`** — per (finished good, raw material, requirement)
```
Id INTEGER PRIMARY KEY AUTOINCREMENT
FinishedGoodId INTEGER
RawMaterialId INTEGER
Requirement TEXT            -- canonical cert (organic, vegan, non-gmo, ...)
DerivationType TEXT         -- "inherited-from-fg-label" | "inherited-from-group" | "explicit"
Confidence REAL
EvidenceId INTEGER          -- FK -> Evidence.Id
```

**`SubstitutionLink`** — Stage B functional-substitute edges (not merges)
```
FromGroupId INTEGER, ToGroupId INTEGER, Similarity REAL, Caveats TEXT  -- JSON array
```

### Modified tables

**`SubstitutionGroup`** — add columns (alter + migrate):
```
UnifiedAttributesJson TEXT   -- {"substance": "vitamin-d3"}
DivergentAttributesJson TEXT -- {"source_detail": ["lanolin", "lichen"], "certifications": {"organic": 3, "vegan": 2}}
```
Existing columns stay. Dropping and recreating is acceptable (pipeline rewrites them on every run — see [substitution_groups.py:318](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase1_extraction/substitution_groups.py#L318)).

### Relationship with existing `Enrichment` table

Keep the existing `Enrichment` table (used by [enrichment_store.py](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase2_enrichment/enrichment_store.py)) as a **raw-payload archive** (full JSON dumps per scrape). `Evidence` is the **field-level, queryable** ledger on top of it. `Evidence.SourceUrl` can cross-reference back into `Enrichment` for the full raw payload when needed.

---

## Part B — Phase 1 rewrite

### B1. Ontology files (new)

Create a new directory `agnes/backend/ontology/` with:

- **`substances.json`** — canonical substance names + aliases. ~150-300 entries covering the dataset. Structure:
  ```json
  {
    "citric-acid": {"aliases": ["e330", "2-hydroxypropane-1,2,3-tricarboxylic-acid"]},
    "vitamin-d3": {"aliases": ["cholecalciferol", "d3"]},
    "vitamin-d2": {"aliases": ["ergocalciferol", "d2"]},
    "vitamin-c": {"aliases": ["ascorbic-acid", "l-ascorbic-acid"]}
  }
  ```
- **`certifications.json`** — canonical cert names + synonyms. Seed directly from the existing `_SYNONYM_GROUPS` block at [compliance_checker.py:35-57](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase3_reasoning/compliance_checker.py#L35-L57). Extend as scrapers surface new variants.
- **`attributes.json`** — finite value sets for form/grade/hydration/salt/source/chirality (so the attribute extractor can validate LLM output).
- **`loader.py`** — single entry point `get_ontologies()` returning cached dataclasses; handles file-path resolution via `DATA_DIR` / a new `ONTOLOGY_DIR` constant in [config.py](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/config.py).

**Reuse note:** Phase 3's `_SYNONYM_GROUPS` should eventually be deleted and replaced by a call to `ontology.loader.get_certification_ontology()`. Within this plan we leave Phase 3 untouched but read the ontology from the same JSON so the two agree by construction.

### B2. Attribute extractor (new)

New file: `agnes/backend/phase1_extraction/attribute_extractor.py`

Function: `extract_attributes(raw_material: dict, ontologies) -> IngredientCard + list[Evidence]`

Extraction strategy (cheap → expensive):
1. **SKU regex pass** — extract substance/chirality/hydration/form from the SKU ingredient-name tokens. Reuse [sku_parser.py:124-131](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase1_extraction/sku_parser.py#L124-L131) normalization.
2. **Substance alias lookup** — run normalized name through `substances.json`; if an alias matches, set `Substance` to the canonical. Record Evidence with `SourceType="ontology"`, `Confidence=1.0`.
3. **Token axis matching** — reuse the axis logic currently in [substitution_validator.py:30-43](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase3_reasoning/substitution_validator.py#L30-L43) to extract hydration/salt/form/source/chirality. Move that dict into `ontology/attributes.json` so both files use the same vocabulary.
4. **LLM fallback** (only for raw materials whose substance is still unknown after steps 1-3): one batched call with JSON schema output, cached in the existing enrichment cache at `data/enrichment_cache/attributes/` per the dual-persistence pattern in [enrichment_store.py](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase2_enrichment/enrichment_store.py). Confidence 0.5-0.8.

Every field written also writes an `Evidence` row keyed by `(Product, product_id, "card.<field>")`.

### B3. Two-stage clustering

Modify `agnes/backend/phase1_extraction/semantic_matcher.py`:

- Keep `build_ingredient_embeddings()` (cache-friendly, already solid).
- Replace `cluster_ingredients()` with **constraint-aware Union-Find**:
  - Build a `card_lookup: product_id -> IngredientCard`.
  - Compute cosine similarity as today.
  - For each candidate merge `(i, j)` above `SIMILARITY_THRESHOLD`, **also** require:
    - `card[i].Substance == card[j].Substance` (after alias resolution), AND
    - no conflict on blocking axes: `chirality`, `hydration`, `salt_or_ester`, `vit_d_form`, `vit_b12_form` (drawn from the same ontology).
  - Non-blocking differences (source, form, certifications, grade) do NOT prevent merge; they get recorded in `DivergentAttributes` later.
- Add `link_substitution_groups(clusters, cards, threshold_low=0.70) -> list[SubstitutionLink]`: for cluster pairs above a lower threshold but with substance mismatch OR a blocking-axis difference, emit a `SubstitutionLink` with `Caveats=[...]` (e.g., `"allergen: soy→sunflower"`).

### B4. Group-level attribute aggregation

Modify `agnes/backend/phase1_extraction/substitution_groups.py`:

- In the group-assembly loop (around line 236), after collecting members, compute:
  - `unified = {key: single value shared by ALL members}`
  - `divergent = {key: {value: count_of_members, ...}}` — or a list of distinct values for small cardinality.
- Persist both on `SubstitutionGroup` via the new JSON columns.
- Persist `SubstitutionLink` rows using a new `insert_substitution_link()` helper.

Canonical name stays, but prefer the ontology canonical substance over the "shortest member name" heuristic at [semantic_matcher.py:211](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase1_extraction/semantic_matcher.py#L211).

### B5. Runner

Keep [run_phase1.py](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/run_phase1.py) CLI shape (`--no-semantic`, `--force-refresh`). Internally it now calls, in order:
1. `create_ingredient_card_tables()` + `create_evidence_table()`
2. Attribute extraction over all raw materials (writes Cards + Evidence)
3. Two-stage clustering + group persistence

---

## Part C — Phase 2 rewrite

### C1. Structured extractor (new)

New file: `agnes/backend/phase2_enrichment/structured_extractor.py`

Single entry point: `extract_structured(html: str, url: str, schema: dict, source_type: str) -> dict`

Pipeline:
1. **Clean HTML** — strip scripts/styles/navigation; keep headings + paragraphs + lists + tables as labeled text blocks (reuse BeautifulSoup already imported in [iherb_scraper.py](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase2_enrichment/iherb_scraper.py)). Output: list of `{block_type, text, dom_path}`.
2. **LLM form-fill** — prompt supplies the JSON schema and the cleaned blocks; model MUST return a JSON object where every field has shape `{"value": ..., "confidence": 0-1, "source_block_index": int}`. Temperature 0.1, `response_format={"type":"json_object"}`.
3. **Post-process** — for each populated field, look up the cited block's text (bounded to ~500 chars) and emit an `Evidence` row via the new `db.evidence.record_evidence()` helper.
4. **Ontology normalization** — certification values are run through `ontology.loader.get_certification_ontology().canonicalize(raw)`.

This module is used by iHerb scraper, supplier scraper, and compliance inference — same plumbing, different schemas.

### C2. Refactor existing scrapers

**`iherb_scraper.py`** — keep HTTP fetch + cache logic. Replace the BeautifulSoup selector block and the LLM-fallback block with a single call to `structured_extractor.extract_structured(html, url, schema=IHERB_PRODUCT_SCHEMA, source_type="scrape")`. On 403, call it again with the SKU+brand as the only input and `source_type="llm-inference"` — same schema, lower confidence. Cache key unchanged; DB write now goes through `record_evidence()` per field + the existing raw-payload store in `Enrichment`.

**`supplier_scraper.py`** — same refactor. The hardcoded-location dict stays as a seed input into the schema (becomes a `hints` block in the prompt).

### C3. Evidence DB helper (new)

New file: `agnes/backend/db/evidence.py`

- `record_evidence(claim, subject_type, subject_id, field_name, source_type, source_url, source_snippet, confidence) -> evidence_id`
- `get_evidence_for(subject_type, subject_id, field_name=None) -> list[dict]`
- `get_evidence_by_id(evidence_id) -> dict`

All Phase 1 and Phase 2 writes route through this.

### C4. Compliance inference rewrite

Modify `agnes/backend/phase2_enrichment/compliance_inferrer.py`:

New flow for each finished good:

1. **Load FG label evidence** — scraped certs + claims via `get_evidence_for("Product", fg_id)`.
2. **Apply rule-based defaults** — keep the mapping in [COMPLIANCE_PROMPT](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase2_enrichment/compliance_inferrer.py#L34-L75), but extract them into a plain Python dict `LABEL_TO_INGREDIENT_REQUIREMENTS` (no LLM call at this step).
3. **Per-ingredient derivation** — for each BOM ingredient, build a candidate requirement set from (a) defaults from step 2, (b) requirements inherited through the ingredient's `SubstitutionGroup` (any constraint that applies to ≥1 group member applies to all — "group inheritance"), (c) explicit requirements from label scrape.
4. **LLM exception-finder** (optional, gated on API availability; otherwise skipped with note in Evidence) — single call per FG with the candidate requirements + scraped blocks; model may only *remove* or *weaken* a default if it cites a specific block that contradicts it. Output: same JSON envelope (`{value, confidence, source_block_index}`).
5. **Contradiction detection** — new module `phase2_enrichment/contradiction_detector.py`:
   - Known conflict rules: `vegan` label vs allergen/ingredient in `{"gelatin", "whey", "casein", "collagen"}`; `organic` label vs non-organic supplier cert; expired cert dates; source conflicts (`lanolin` in a vegan product).
   - Output: `list[Contradiction]` written to a new `Contradiction` table (Id, SubjectType, SubjectId, Rule, DetailJson, Severity, DetectedAt). Never silently resolves; surfaces for UI/Phase 3.
6. **Write per-ingredient requirements** — one row per (FG, RawMaterial, Requirement) into `IngredientComplianceRequirement`, each with an Evidence ID.

### C5. Mock fallback

[mock_phase2.py](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/mock_phase2.py) must also write through `record_evidence()` with `source_type="mock"` and `confidence=0.2`. Downstream consumers already see low confidence; they additionally can filter on `source_type != "mock"` if needed.

### C6. Runner

Keep `run_phase2.py` CLI (`--skip-iherb`, `--skip-suppliers`, `--skip-compliance`). Add `--skip-contradictions` flag. Internally:
1. Create new tables (`Evidence`, `Contradiction`, `IngredientComplianceRequirement`).
2. Run scrapers (now emit per-field Evidence).
3. Run compliance inference (now ingredient-level).
4. Run contradiction detector across Evidence + label claims.
5. Print summary stats including `contradictions_found`.

---

## Part D — Files to create / modify

### Create
- `agnes/backend/ontology/__init__.py`
- `agnes/backend/ontology/loader.py`
- `agnes/backend/ontology/substances.json`
- `agnes/backend/ontology/certifications.json`
- `agnes/backend/ontology/attributes.json`
- `agnes/backend/phase1_extraction/attribute_extractor.py`
- `agnes/backend/phase2_enrichment/structured_extractor.py`
- `agnes/backend/phase2_enrichment/contradiction_detector.py`
- `agnes/backend/db/evidence.py`

### Modify
- `agnes/backend/db/queries.py` — add table creators + insert/get helpers for `IngredientCard`, `CardCertification`, `CardAllergen`, `Evidence`, `IngredientComplianceRequirement`, `SubstitutionLink`, `Contradiction`; add JSON columns to `SubstitutionGroup`.
- `agnes/backend/config.py` — add `ONTOLOGY_DIR`, `ATTRIBUTE_EXTRACTION_BATCH_SIZE`, `BLOCKING_ATTRIBUTE_AXES` list, `LINK_SIMILARITY_THRESHOLD=0.70`.
- `agnes/backend/phase1_extraction/sku_parser.py` — expose a `tokens_from_ingredient(name)` helper reused by the attribute extractor.
- `agnes/backend/phase1_extraction/semantic_matcher.py` — constraint-aware clustering; new `link_substitution_groups()`; canonical-name sourced from ontology.
- `agnes/backend/phase1_extraction/substitution_groups.py` — invoke attribute extraction before clustering; compute + persist unified/divergent attributes; persist links.
- `agnes/backend/phase2_enrichment/iherb_scraper.py` — route through structured extractor + evidence ledger.
- `agnes/backend/phase2_enrichment/supplier_scraper.py` — same.
- `agnes/backend/phase2_enrichment/compliance_inferrer.py` — rule defaults extracted to Python dict; per-ingredient derivation; group inheritance; LLM as exception-finder only.
- `agnes/backend/phase2_enrichment/enrichment_store.py` — delegate per-field writes to `db/evidence.py` while keeping the raw-payload `Enrichment` archive.
- `agnes/backend/mock_phase2.py` — emit Evidence rows tagged `source_type="mock"`.
- `agnes/backend/run_phase2.py` — new table creation + contradiction step.

### Functions to reuse (do not rewrite)
- Embedding cache: `build_ingredient_embeddings()` at [semantic_matcher.py:101](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase1_extraction/semantic_matcher.py#L101).
- SKU parser: [sku_parser.py:73](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase1_extraction/sku_parser.py#L73).
- Enrichment JSON+SQLite dual cache pattern: [enrichment_store.py](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase2_enrichment/enrichment_store.py) `cache_get` / `cache_set`.
- BOM join query: `get_bom_for_product()` at [queries.py:51](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/db/queries.py#L51).
- Existing synonym groups at [compliance_checker.py:35-57](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase3_reasoning/compliance_checker.py#L35-L57) — seed the new `certifications.json` from this block verbatim.
- Union-Find at [semantic_matcher.py:40-68](d:/Projects/Hackathons/TUM.ai_Makeathon/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes/backend/phase1_extraction/semantic_matcher.py#L40-L68) — keep, wrap with constraint check.

---

## Part E — Verification

End-to-end smoke run, in order:

1. **Phase 1 rebuild**
   ```
   cd agnes/
   python -m backend.run_phase1 --force-refresh
   ```
   - Query `SELECT COUNT(*) FROM IngredientCard` → expect 876.
   - Query `SELECT COUNT(DISTINCT Substance) FROM IngredientCard` → should be ≤ the old 357 unique names (aliases collapse).
   - Query `SELECT * FROM Evidence WHERE SubjectType='Product' LIMIT 5` → every row has `SourceType`, `SourceSnippet`, `Confidence`.
   - Inspect a known case: vitamin D3 group should have `UnifiedAttributesJson.substance = "vitamin-d3"` and `DivergentAttributesJson.source_detail` containing both `lanolin` and `lichen` (if either appears in the data).
   - Inspect `SubstitutionLink` rows — a vegan-sensitive pair (e.g., `soy-lecithin` ↔ `sunflower-lecithin`) should appear as a link, not a merge.

2. **Phase 2 rebuild**
   ```
   python -m backend.run_phase2 --skip-iherb  # run scrapers-free path first with mock
   python -m backend.run_phase2               # full run when API available
   ```
   - Query `SELECT * FROM Evidence WHERE SourceType='scrape' LIMIT 5` → each row has a non-empty `SourceSnippet` and a real URL.
   - Query `IngredientComplianceRequirement` for one known vegan FG → Vitamin D3 ingredient has a `vegan` requirement with `DerivationType='inherited-from-fg-label'`.
   - Query `Contradiction` after seeding a synthetic vegan-FG whose BOM contains gelatin → exactly one contradiction row with `Rule='vegan_vs_animal_ingredient'`.
   - `Evidence` rows with `SourceType='mock'` appear only when the real API path was unavailable.

3. **Regression — existing Phase 3 still runs**
   ```
   python -m backend.run_phase3
   ```
   - Phase 3 reads old tables that remain unchanged in structure; proposals still generate. Confidence scores may shift because the underlying data is cleaner — that's expected and desirable. No crashes.

4. **Unit-level checks** (add under `agnes/tests/`):
   - `test_ontology_loader.py` — alias resolution (`e330` → `citric-acid`).
   - `test_attribute_extractor.py` — SKU-only path extracts `substance="citric-acid"` + `hydration="anhydrous"` from `RM-C01-citric-acid-anhydrous-deadbeef`.
   - `test_constraint_clustering.py` — two D-vitamins with `vit_d_form=d2` and `vit_d_form=d3` do NOT merge even above similarity threshold.
   - `test_structured_extractor.py` — given a fixture HTML block, produces schema-conformant JSON with `source_block_index` pointing at the right block.
   - `test_contradiction_detector.py` — vegan + gelatin → detected.

---

## Execution order (suggested, for a future chat)

1. Ontology files + loader (no DB changes yet).
2. Evidence DB helper + new tables migration.
3. Attribute extractor + IngredientCard population.
4. Constraint-aware clustering + group attribute aggregation.
5. Structured extractor.
6. Refactor iHerb/supplier scrapers onto the structured extractor.
7. Compliance inference rewrite (rule defaults + group inheritance + LLM exception-finder).
8. Contradiction detector.
9. Mock fallback wiring.
10. Tests + end-to-end verification.

Steps 1-4 are the Phase 1 deliverable and can be merged independently. Steps 5-9 are the Phase 2 deliverable and assume 1-4 are in place (because compliance inheritance reads `SubstitutionGroup` and `IngredientCard`).

---

## Open decisions for the user (one-line each)

- **D1**: Keep existing `Enrichment` table as a raw-payload archive alongside the new `Evidence` ledger, rather than consolidating into one? (Plan assumes: yes, keep both.)
- **D2**: Ontologies as JSON files (plan default) vs DB tables? (Plan assumes: JSON for easy editing and version control.)
- **D3**: Is it acceptable to drop+recreate `SubstitutionGroup` on every run to add the new JSON columns, consistent with the existing `clear_substitution_tables()` pattern? (Plan assumes: yes.)
