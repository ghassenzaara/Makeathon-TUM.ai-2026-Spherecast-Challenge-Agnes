# Agnes Backend AI Pipeline Analysis (Current Branch)

This document provides a detailed analysis of the Agnes AI backend pipeline as it is currently implemented on this branch. It compares the existing codebase against the intended architecture outlined in the `Final_Architecture_Recommendation.md` document.

## Overview

Unlike the complete architecture, this branch currently only implements **Phase 1: Smart Data Extraction & Semantic Matching**. Phases 2, 3, and 4—which handle external enrichment, reasoning/trust, and output generation—are completely missing from the `agnes/backend` codebase. 

---

## Implemented: Phase 1 (Smart Data Extraction & Semantic Matching)
**Implementation:** `run_phase1.py` & `backend/phase1_extraction/`

### Goal
Ingest raw relational data (SKUs, ingredients, companies), parse the SKUs, and group identical/functionally equivalent ingredients across different companies into "Substitution Groups" to find consolidation opportunities.

### Technical Details
1. **SKU Parsing (`sku_parser.py`):** Uses Regex patterns to parse complex SKUs (e.g., `RM-C28-vitamin-d3-cholecalciferol-8956b79c`) and extract the canonical ingredient name (`vitamin-d3-cholecalciferol`), company ID, and product type.
2. **Semantic Matching (`semantic_matcher.py`):**
    - Uses OpenAI's `text-embedding-3-small` to generate vector embeddings for the extracted ingredient names.
    - Implements a **Union-Find** (Disjoint Set) algorithm combined with cosine similarity to cluster near-equivalent ingredients (e.g., 'sunflower-lecithin' ≈ 'soy-lecithin').
    - Includes a fallback mechanism (`cluster_ingredients_exact_only`) to group items purely by exact name if the OpenAI API is unavailable.
3. **Orchestration (`substitution_groups.py`):** Connects the parsed SKUs to the generated clusters, integrates Supplier and Bill of Materials (BOM) data from the database, and stores the final "Substitution Groups" into the `SubstitutionGroup` database tables.

---

## Missing Components (Gaps vs. Final Architecture)

When compared to the `Final_Architecture_Recommendation.md`, the following critical phases are **not implemented** in this branch:

### ❌ Missing: Phase 2 (External Enrichment Agent)
The codebase lacks the `backend/phase2_enrichment/` logic.
*   **Gap:** There is no mechanism to scrape iHerb product pages, scrape supplier specification sheets, or infer compliance requirements using LLMs. The pipeline relies solely on the raw database inputs and cannot fill the "missing data" gaps.

### ❌ Missing: Phase 3 (Reasoning, Optimization & Trust)
The codebase lacks the `backend/phase3_reasoning/` logic.
*   **Gap:** The core intelligence is missing. There is no substitution validation, compliance checking against external data, or sourcing optimization.
*   **Trust Gap:** The highly critical **Confidence Scorer** and **Verification Agent** (designed to prevent AI hallucinations) are absent. The system cannot currently score proposals or flag uncertainty.

### ❌ Missing: Phase 4 (Output & Evidence Trail)
The codebase lacks the `backend/phase4_output/` logic.
*   **Gap:** The system does not build verifiable evidence trails or prepare retrieval vector indexes for the Chat UI. Outputs are limited to raw database tables populated by Phase 1.

---

## Conclusion
This branch successfully establishes the foundation by building semantic substitution groups (Phase 1). However, to meet the Spherecast judging criteria for handling uncertainty, explaining tradeoffs, and preventing hallucinations, the pipeline must be expanded to include the missing enrichment, reasoning, and verification layers (Phases 2-4) that are present in the full architecture.
