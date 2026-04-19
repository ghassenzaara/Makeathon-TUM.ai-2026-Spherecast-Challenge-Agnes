# Objective: Modernize Agnes Logic — Context-Aware Scraping & 5-Objective Pareto Optimization

The supply chain sourcing logic in the Agnes system is currently "corrupted" or incomplete. I want to refactor the core pipeline to be context-aware, source-reliable, and dynamically weighted.

## 1. Context-Aware Scraping (Logic Update)
Refactor `agnes/backend/phase2_enrichment/iherb_scraper.py` (specifically `_parse_tavily_iherb`):
- **Current Issue**: It uses rigid regex and keyword lists (`CERTIFICATION_KEYWORDS`) which fails to understand context (e.g., negations like "No Gluten-Free" might be parsed as "Gluten-Free").
- **Fix**: Replace the regex/keyword matching with an LLM call (use the existing `AsyncOpenAI` client pattern). Pass the raw `combined_text` from Tavily results to a prompt that extracts: `title`, `brand`, `price_usd`, `ingredients_text`, and a specific list of `certifications`.
- **Constraint**: It shouldn't be "string sensitive"—it should understand if a certification is present based on the prose, not just the word's existence.

## 2. Harmonized Data-Source Weighting (Consistency)
Ensure `agnes/backend/phase3_reasoning/confidence_scorer.py` and `compliance_checker.py` use a consistent weighting system for "Source Truth":
- **Source Weights**: 
  - `ONTOLOGY/DB (SQLite)`: 1.0 (Highest trust)
  - `SCRAPING (Tavily/Real Website)`: 0.9 (Very high trust)
  - `LLM INFERENCE/HALLUCINATION`: 0.6 (Lower trust)
- **Fix**: Data originated from the DB or Scraping MUST contribute significantly more to the final `confidence_score` and `impact_score` than LLM-generated fallbacks. Re-check the logic in `_supplier_quality_score` and `_is_mock` to ensure this is enforced across the board.

## 3. 5-Objective Dynamic Pareto & Utility (Algorithm Fix)
Refactor `agnes/backend/phase3_reasoning/pareto_engine.py` and synchronize it with the 5 sliders in `agnes/frontend/app/components/ParetoChart.tsx`:
- **5 Objectives**: 
  1. `α Savings` (Impact)
  2. `β Compliance Risk` (P_Risk)
  3. `γ Substitution Risk` (1 - similarity)
  4. `δ Supplier Variance` (Reliability/Enforcement)
  5. `ε Uncertainty` (1 - Evidence Strength)
- **Fix Pareto Axis**: The `risk_score` (Y-axis) in the chart and Pareto logic is currently a hardcoded 70/30 split. Make it a weighted composite of ALL risk types (Compliance, Substitution, Reliability, Uncertainty) based on the user-provided coefficients.
- **Algorithm**: Ensure `rank_by_utility` (backend) uses all 5 coefficients (`alpha`, `beta`, `gamma`, `delta`, `epsilon`) to calculate the final `utility_score`.
- **References**: Use the "Uncertainty-Aware" plan described in `agnes/backend/phase3_reasoning/step-1-product-peaceful-crab.md` to ensure the Pareto algorithm (NSGA-II style dominance) is correctly handling these 5 dimensions.

## Files to Modify:
- `agnes/backend/phase2_enrichment/iherb_scraper.py`: Update parser to be context-aware.
- `agnes/backend/phase3_reasoning/confidence_scorer.py`: Enforce source-truth weighting.
- `agnes/backend/phase3_reasoning/pareto_engine.py`: Update multiobjective vector and utility formula.
- `agnes/backend/phase4_output/api.py`: Ensure `rerank_proposals` correctly applies all 5 coefficients.
- `agnes/frontend/app/components/ParetoChart.tsx`: Verify the sliders send the correct coefficients to the API.

Please ensure the Pareto graph in the UI correctly shows which proposals are non-dominated based on these 5 dimensions.
