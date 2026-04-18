# Agnes Backend AI Pipeline Analysis

This document provides a detailed end-to-end analysis of the Agnes AI Supply Chain Manager backend pipeline. It maps the implementation found in the `agnes/backend` codebase against the recommended architecture from the `Final_Architecture_Recommendation.md` document, making it easy to compare with alternative approaches.

## Overview

The Agnes backend is orchestrated into four distinct, sequential phases that transform raw data into highly-confident, actionable supply chain consolidation proposals. The pipeline heavily relies on Large Language Models (LLMs) not just for extraction, but crucially for **reasoning, validation, and preventing hallucinations**.

---

## Phase 1: Smart Data Extraction & Semantic Matching
**Implementation:** `run_phase1.py` & `backend/phase1_extraction/`

### Goal
Ingest raw relational data (SKUs, ingredients, companies) and cluster ingredients that are functionally identical across different companies into "Substitution Groups" to find consolidation opportunities.

### Technical Details
1. **Semantic Embeddings:** Uses OpenAI's `text-embedding-3-small` (via `build_substitution_groups`) to map raw SKU strings into high-dimensional vector spaces.
2. **Fuzzy & Semantic Matching:** Bypasses simple string matching by grouping ingredients based on semantic equivalence (e.g., recognizing `vitamin-d3-cholecalciferol` and `VitD3` as the same core ingredient).
3. **Execution Flags:** The pipeline allows skipping semantic matching for rapid testing (`--no-semantic`) or forcing refresh of the embedding cache (`--force-refresh`).

---

## Phase 2: External Enrichment Agent
**Implementation:** `run_phase2.py` & `backend/phase2_enrichment/`

### Goal
Solve the "missing data" problem by autonomously gathering external context required for compliance and sourcing decisions.

### Technical Details
The enrichment runs asynchronously and is divided into three core steps:
1. **iHerb Scraping (`scrape_all_iherb_products`):** Uses embedded `iherb` identifiers in the SKUs to fetch real-world product pages, ingredient lists, and brand positioning (e.g., "Non-GMO certified").
2. **Supplier Recon (`enrich_all_suppliers`):** Automates data gathering on the 40 provided suppliers to extract compliance documents, specification sheets, and corporate locations (which is critical for lead time estimation).
3. **Compliance Inference (`infer_compliance_for_all_products`):** Uses an LLM to infer the compliance requirements of sub-components based on the finished good's label. If a finished product is labeled "Organic Vitamin D", the system deduces that all its raw materials require organic certification.

All enrichment data is persisted to an `enrichment_store` (SQLite) with associated confidence scores.

---

## Phase 3: Reasoning, Optimization & Trust (The Core Intelligence)
**Implementation:** `run_phase3.py` & `backend/phase3_reasoning/`

### Goal
Synthesize Phase 1 and Phase 2 data to generate intelligent sourcing proposals while mathematically penalizing uncertainty and actively guarding against hallucinations.

### Technical Details
This is the most complex phase, executing a 6-step loop for every Substitution Group:
1. **Substitutability Validation (`validate_substitution_group`):** Double-checks if ingredients grouped in Phase 1 are *actually* interchangeable in a real-world manufacturing context.
2. **Supplier Data Loading:** Fetches the enriched Phase 2 data for all potential suppliers in the group.
3. **Compliance Checking (`check_compliance`):** Cross-references the inferred compliance requirements of the finished goods with the extracted certifications of the proposed suppliers.
4. **Sourcing Optimization (`optimize_sourcing`):** Generates concrete proposals by balancing the financial benefits of volume consolidation against logistical risks (e.g., increased lead times from distant suppliers).
5. **Confidence Scoring (`score_proposal_confidence`):** **(Critical Differentiator)** Assigns a strict 0-100% confidence score. Missing external data dynamically lowers the score, ensuring the AI admits uncertainty instead of guessing.
6. **Verification Agent (`verify_proposal`):** A strict, low-temperature LLM guardrail that checks the final proposal against the raw scraped context. If it catches the primary model hallucinating a certification, it aggressively downgrades the confidence score (halves it) and adds a risk factor.

Proposals are persisted to a `SourcingProposal` database table.

---

## Phase 4: Output & Evidence Trail
**Implementation:** `run_phase4.py` & `backend/phase4_output/`

### Goal
Translate complex mathematical optimizations and AI reasoning into transparent, trustworthy outputs for human decision-makers.

### Technical Details
1. **Evidence Trail Builder (`build_all_evidence_trails`):** For every proposal generated in Phase 3, it builds an exact citation list. It links recommendations directly to the source evidence (e.g., "Supplier X website confirms Kosher certification [Link]").
2. **Retrieval Index Generation (`build_or_load_index`):** Compiles the evidence trails into a vector index. This allows the conversational Agent (Chat UI) to answer user questions about the proposals using strictly grounded, pre-verified facts.
3. **Output format:** Exports the final data to `phase4_evidence_trails.json` for frontend consumption.

---

## Key Differentiators & Strengths

If you are comparing this pipeline against another implementation, look for these advanced features that specifically target enterprise readiness:

* **Separation of Reasoning and Verification:** By splitting proposal generation (Phase 3 Optimizer) and validation (Phase 3 Verification Agent), the architecture fundamentally guards against LLM hallucinations.
* **Deterministic Confidence Scoring:** It doesn't just return an answer; it returns an answer with a mathematically derived confidence score based on the *presence* of evidence.
* **Inferred Compliance:** Instead of relying only on explicitly provided rules, it uses LLMs to intelligently infer rules from finished product descriptions (Phase 2).
* **Evidence Trails:** Every decision points to a verifiable source, building user trust.
