Here is a detailed breakdown of how the code is implemented across the 4 phases. I have created a carousel with **Mermaid Class Diagrams** to represent the core modules, their methods, and the data models (dataclasses) used in each phase.

### Phase 1: Smart Data Extraction & Semantic Matching

This phase focuses on parsing the raw database SKUs and using OpenAI embeddings to group ingredients that are functionally identical into `SubstitutionGroup` models.

```mermaid
classDiagram
    %% Modules / Services
    class SKUParser {
        +parse_sku(sku: str) dict
    }
    class SemanticMatcher {
        +build_ingredient_embeddings(ingredients: list) ndarray
        +cluster_ingredients(names: list, embeddings: ndarray, threshold: float) dict
    }
    class SubstitutionBuilder {
        +build_groups(clusters: dict) list~SubstitutionGroup~
    }

    %% Data Models
    class SubstitutionGroup {
        <<dataclass>>
        +int id
        +str canonical_name
        +list members
        +list suppliers
        +list consuming_products
        +int cross_company_count
        +float similarity_score
    }
    class ParsedSKU {
        <<dataclass>>
        +str type
        +int company_id
        +str ingredient_name
        +str hash
        +str iherb_id
    }

    %% Relationships
    SKUParser --> ParsedSKU : Returns
    SemanticMatcher --> SubstitutionBuilder : Passes clusters to
    SubstitutionBuilder --> SubstitutionGroup : Creates
```

<!-- slide -->
### Phase 2: External Data Enrichment

This phase uses web scraping and LLMs to infer the compliance requirements (like Non-GMO or Organic) from external sources, filling in the gaps of the internal database.

```mermaid
classDiagram
    %% Modules / Services
    class IHerbScraper {
        +scrape_iherb_product(iherb_id: str) dict
    }
    class SupplierScraper {
        +scrape_supplier_info(supplier_name: str) dict
    }
    class ComplianceInferrer {
        +infer_requirements(product_name, labels, ingredients) InferredCompliance
    }
    class EnrichmentStore {
        +save_enrichment(entity_type, entity_id, data)
        +get_certifications_for_supplier(supplier_id)
        +get_compliance_for_product(product_id)
    }

    %% Data Models
    class ScrapedProductInfo {
        <<dataclass>>
        +str iherb_id
        +str title
        +list certifications
        +float price_usd
        +str url
    }
    class InferredCompliance {
        <<dataclass>>
        +list required_certifications
        +list inferred_constraints
        +int confidence
        +str reasoning
    }

    %% Relationships
    IHerbScraper --> ScrapedProductInfo : Returns
    IHerbScraper --> ComplianceInferrer : Feeds scraped labels
    SupplierScraper --> EnrichmentStore : Saves certs to
    ComplianceInferrer --> InferredCompliance : Returns
    InferredCompliance --> EnrichmentStore : Saved in
```

<!-- slide -->
### Phase 3: Reasoning, Optimization & Trust

The "Brain" of Agnes. It takes the enriched data, validates substitutions, checks for compliance passes/fails, and creates a consolidated sourcing proposal. The `VerificationAgent` acts as a guardrail against AI hallucination.

```mermaid
classDiagram
    %% Modules / Services
    class SubstitutionValidator {
        +validate_group(group: SubstitutionGroup) SubstitutionValidation
    }
    class ComplianceChecker {
        +check_supplier_compliance(product_id, supplier_id) ComplianceResult
    }
    class SourcingOptimizer {
        +generate_proposals(groups, compliance_results) list~SourcingProposal~
    }
    class VerificationAgent {
        +verify_claims(recommendation_text, raw_evidence)
    }
    class ConfidenceScorer {
        +calculate_score(proposal: SourcingProposal) float
    }

    %% Data Models
    class ComplianceResult {
        <<dataclass>>
        +int product_id
        +int proposed_supplier_id
        +list~ComplianceCheck~ checks
        +bool all_passed
        +list blocking_issues
    }
    class ComplianceCheck {
        <<dataclass>>
        +str requirement
        +str status
        +str evidence
        +str source_url
    }
    class SourcingProposal {
        <<dataclass>>
        +int id
        +dict current_state
        +dict proposed_state
        +str recommended_supplier
        +float estimated_savings_pct
        +float confidence_score
    }

    %% Relationships
    ComplianceChecker *-- ComplianceCheck : Contains
    ComplianceChecker --> ComplianceResult : Returns
    SourcingOptimizer --> SourcingProposal : Creates
    SourcingProposal --> ConfidenceScorer : Scored by
    SourcingProposal --> VerificationAgent : Fact-checked by
```

<!-- slide -->
### Phase 4: Output & Evidence Trail

The final phase packages the recommendations along with traceable proof. It creates an `EvidenceTrail` mapped to citations to ensure users can verify the source of truth for the AI's logic.

```mermaid
classDiagram
    %% Modules / Services
    class EvidenceTrailBuilder {
        +build_trail_for_recommendation(proposal_id: int) EvidenceTrail
    }
    class RecommendationFormatter {
        +format_for_api(proposals: list~SourcingProposal~) dict
    }

    %% Data Models
    class EvidenceTrail {
        <<dataclass>>
        +int recommendation_id
        +list~EvidenceCitation~ citations
        +str summary
    }
    class EvidenceCitation {
        <<dataclass>>
        +str claim
        +str source_type
        +str source_url
        +str extracted_text
        +float confidence
        +str timestamp
    }

    %% Relationships
    EvidenceTrailBuilder --> EvidenceTrail : Creates
    EvidenceTrail *-- EvidenceCitation : Contains
    RecommendationFormatter --> EvidenceTrail : Includes in output
```

### Summary of How the Code Links Together

1. **Phase 1** pulls raw rows from SQLite and turns them into `SubstitutionGroup` objects.
2. **Phase 2** kicks off background scrapers to populate the `EnrichmentStore` with external facts (like "Supplier X is Kosher").
3. **Phase 3** runs business logic classes (`ComplianceChecker`, `SourcingOptimizer`) on those grouped objects using the fetched facts, outputting a `SourcingProposal`.
4. **Phase 4** loops over the generated `SourcingProposal` models, attaches an `EvidenceTrail` to each, and serves them to the React frontend via FastAPI endpoints.
