# Phase 3 — Uncertainty-Aware Evidence Aggregation

## Context

Phase 3 today emits final analytics (compliance %, Pareto frontier, scoring) as **scalar values with no uncertainty metadata**. [compliance_checker.py](agnes/backend/phase3_reasoning/compliance_checker.py) collapses every requirement into a single `compliance_probability` via geometric mean — which hides *unknowns* inside an average (exactly what the spec forbids). [pareto_engine.py](agnes/backend/phase3_reasoning/pareto_engine.py) ranks on raw `(savings, compliance_probability, 1−risk)` without weighting by evidence source. `SourcingProposal.confidence_score` in [sourcing_optimizer.py](agnes/backend/phase3_reasoning/sourcing_optimizer.py) is a single number with no drivers, weak-signals, or coverage breakdown.

The jury will push on *how we justify recommendations when we have no ground truth*. The answer needs to be: **every number we show carries `value + confidence + coverage + source_distribution`**, and low-confidence + high-impact items are explicitly flagged, not hidden.

Scope of this change: **Phase 3 final-layer analytics only** (compliance scoring, Pareto, final proposal score, DB persistence, API, and the two frontend components that render them). Phase 1/Phase 2 extraction stays as-is — we consume their existing per-record `confidence` and `source_type` from the Evidence table, we don't rework scraping here.

## Non-goals

- Rewriting Phase 1/Phase 2 scraping or per-field confidence extraction.
- Training an ML ranker (we have no ground truth — this is the whole reason we're going uncertainty-first).
- Changing the substitution-group clustering or verification agent.

## Key concepts (from the spec)

Every computed metric at the Phase 3 boundary must emit:
```
value          # the number
confidence     # 0–1, how sure are we
coverage       # 0–1, fraction of expected signals we actually have
source_distribution  # {ontology: x, deterministic: y, llm: z, embedding: w}
```

Source weights (fixed constants):
- ontology: `1.0`
- deterministic (synonym/regex/exact): `0.9`
- llm: `0.6` (mid of 0.5–0.8 range)
- embedding/fuzzy: `0.4` (mid of 0.2–0.6 range)

## Architecture changes

### 1. New: unified Signal/Evidence model — [agnes/backend/phase3_reasoning/evidence_model.py](agnes/backend/phase3_reasoning/evidence_model.py) *(new file)*

```python
class SourceType(Enum): ONTOLOGY, DETERMINISTIC, LLM, EMBEDDING
SOURCE_WEIGHTS = {ONTOLOGY: 1.0, DETERMINISTIC: 0.9, LLM: 0.6, EMBEDDING: 0.4}

@dataclass
class Signal:
    value: float           # 0–1 normalized
    confidence: float      # 0–1
    source_type: SourceType
    importance: float      # 0–1 (how important this attribute is)
    label: str             # "Organic", "non-GMO", etc. — for drivers/weak-signals

@dataclass
class AggregatedMetric:
    value: float
    confidence: float
    coverage: float
    source_distribution: Dict[str, float]
    drivers: List[Signal]        # top contributors to value
    weak_signals: List[Signal]   # low-confidence but high-importance
    uncertainty_sources: List[str]  # human-readable reasons
```

Core helper: `aggregate(signals, expected_count) -> AggregatedMetric`, using the spec formula:
```
final_metric = Σ(value × confidence × source_weight × importance) / Σ(confidence × source_weight × importance)
coverage     = len(signals) / expected_count
confidence   = mean(signal.confidence × source_weight)
```

### 2. Rewrite: compliance scoring — [compliance_checker.py](agnes/backend/phase3_reasoning/compliance_checker.py)

Replace the three-way derived `status` string (PASS/FAIL/UNKNOWN from threshold) with a first-class classification:

```python
class ComplianceState(Enum): COMPLIANT, NON_COMPLIANT, UNKNOWN

@dataclass
class ComplianceCheck:
    requirement: str
    state: ComplianceState   # first-class, NOT derived from probability
    confidence: float
    source_type: SourceType
    importance: float        # derived from is_blocking (1.0 blocking, 0.6 standard)
    evidence: str
    source_url: str
```

Mapping (keeps existing matcher `_supplier_supports_probabilistic` logic, changes the output shape):
- synonym hit  → `COMPLIANT`, confidence=0.95, source=DETERMINISTIC (will use ONTOLOGY once we wire synonym groups to that tag)
- fuzzy hit    → `COMPLIANT`, confidence=ratio-scaled 0.60–0.90, source=EMBEDDING
- no hit + required + blocking → `NON_COMPLIANT`, confidence=0.80, source=DETERMINISTIC
- no hit + required + non-blocking, supplier has *some* certs → `UNKNOWN` (not FAIL)
- no hit + required + no supplier cert data at all → `UNKNOWN` (coverage shortfall)

Aggregation uses spec formula (replaces the current geometric-mean collapse at lines 233–236):
```
compliance_score =
  Σ (compliant_confidence × importance)  /
  Σ ((compliant + non_compliant + 0.3×unknown) × importance)
```

Return `ComplianceResult` extended with:
```python
compliance_score: AggregatedMetric  # value, confidence, coverage, breakdown
breakdown: Dict[str, int]            # {compliant: n, non_compliant: n, unknown: n}
```

Keep legacy `compliance_probability` and `evidence_strength` fields for backward compat with [sourcing_optimizer.py](agnes/backend/phase3_reasoning/sourcing_optimizer.py) lines 158–161 and [run_phase3.py](agnes/backend/run_phase3.py) line 202 logging — populate them from `AggregatedMetric.value` / `.confidence`.

### 3. Rewrite: Pareto impact — [pareto_engine.py](agnes/backend/phase3_reasoning/pareto_engine.py)

Replace objective vector `{savings, compliance, neg_risk}` with evidence-weighted impact:

```python
impact_score = Σ (value × confidence × source_weight × importance)
```

applied to the savings axis, giving `impact_score` not `savings_norm`. Objectives become:
```
{impact, compliance_score.value, 1 − risk_score}
```

with confidence attached to each axis for downstream display. `ParetoResult` gains:
```python
impact_confidence: float
flagged_low_confidence_high_impact: bool  # impact > median AND confidence < 0.5
```

Risk decomposition stays (it's already a documented structured heuristic), but its weights become tunable via the existing α/β/γ sliders in `rank_by_utility`. Utility formula stays — uncertainty term `(1 − evidence_strength)` already satisfies the spec.

### 4. Proposal model — [sourcing_optimizer.py](agnes/backend/phase3_reasoning/sourcing_optimizer.py)

Extend `SourcingProposal` (lines 22–44) with a single `score_breakdown: AggregatedMetric` field that captures the final recommendation's value / confidence / coverage / drivers / weak_signals / uncertainty_sources. Drop reliance on the scalar-only `confidence_score` for display — keep the field for legacy DB rows but compute it from `score_breakdown.value × score_breakdown.confidence`.

### 5. Persistence — [agnes/backend/db/queries.py](agnes/backend/db/queries.py) line 624

Add one column to `SourcingProposal`:
```sql
ScoreBreakdownJson TEXT   -- serialized AggregatedMetric
```
Single JSON blob avoids a schema migration for every field. Also add `ComplianceBreakdownJson TEXT` with the {compliant, non_compliant, unknown} counts. Update `insert_proposal` at line 671 and the run_phase3.py persist block at lines 98–106.

### 6. API — [agnes/backend/phase4_output/api.py](agnes/backend/phase4_output/api.py) lines 130+

Surface the new fields in the `/api/proposals` and `/api/proposals/rerank` responses:
```
score: { value, confidence, coverage, source_distribution, drivers[], weak_signals[], uncertainty_sources[] }
compliance: { value, confidence, coverage, breakdown: {compliant, non_compliant, unknown} }
impact: { value, confidence, flagged_low_confidence_high_impact }
```

### 7. Frontend

**[ParetoChart.tsx](agnes/frontend/app/components/ParetoChart.tsx)** — switch X-axis from `savings` to `impact`, switch Y-axis to `compliance.value`, encode `confidence` as **point opacity** (low conf = translucent), and render a red ring around points with `flagged_low_confidence_high_impact=true`. Tooltip shows value + confidence + coverage explicitly.

**[agnes/frontend/app/proposals/[id]/page.tsx](agnes/frontend/app/proposals/[id]/page.tsx)** — replace the single `confidence_score` number (line ~144) with a three-field card: `value ± (1−confidence) band`, `coverage bar`, `source distribution stacked bar`. Add two lists below: *Main drivers* (top-3 signals by `value × confidence × weight`) and *Weak signals / uncertainty sources*.

### 8. What we're explicitly NOT doing

- **Not** removing the geometric-mean helper entirely — it's still useful as a comparison baseline for the jury demo. Keep it, but don't use it as the primary aggregation.
- **Not** touching verification_agent — its `verification_confidence` already feeds `risk_score`.
- **Not** changing `SubstitutionGroup` validation — Phase 1 concern.

## Critical files

| File | Change |
|------|--------|
| [agnes/backend/phase3_reasoning/evidence_model.py](agnes/backend/phase3_reasoning/evidence_model.py) | **NEW** — Signal, SourceType, AggregatedMetric, aggregate() |
| [agnes/backend/phase3_reasoning/compliance_checker.py](agnes/backend/phase3_reasoning/compliance_checker.py) | Replace status derivation with `ComplianceState`; rewrite aggregation at lines 227–249 |
| [agnes/backend/phase3_reasoning/pareto_engine.py](agnes/backend/phase3_reasoning/pareto_engine.py) | Add `impact_score`; extend `ParetoResult` with confidence + flag |
| [agnes/backend/phase3_reasoning/sourcing_optimizer.py](agnes/backend/phase3_reasoning/sourcing_optimizer.py) | Add `score_breakdown: AggregatedMetric` to `SourcingProposal` (lines 22–44) |
| [agnes/backend/run_phase3.py](agnes/backend/run_phase3.py) | Populate `score_breakdown` after Pareto (after line 224); persist JSON blob (lines 98–106) |
| [agnes/backend/db/queries.py](agnes/backend/db/queries.py) | Add `ScoreBreakdownJson`, `ComplianceBreakdownJson` columns at line 624 CREATE; update INSERT at line 671 |
| [agnes/backend/phase4_output/api.py](agnes/backend/phase4_output/api.py) | Surface new fields in `/api/proposals` (lines 130+) and `/api/proposals/rerank` |
| [agnes/frontend/app/components/ParetoChart.tsx](agnes/frontend/app/components/ParetoChart.tsx) | Use `impact` axis + confidence opacity + low-conf-high-impact flag |
| [agnes/frontend/app/proposals/[id]/page.tsx](agnes/frontend/app/proposals/[id]/page.tsx) | Replace scalar confidence with value±band + coverage + source distribution + drivers/weak signals |

## Reused utilities (don't reimplement)

- `_canonical_tokens`, `_SYNONYM_GROUPS` in [compliance_checker.py](agnes/backend/phase3_reasoning/compliance_checker.py) lines 59–112 — feed these into `SourceType.ONTOLOGY` signals.
- `_supplier_supports_probabilistic` at [compliance_checker.py:126](agnes/backend/phase3_reasoning/compliance_checker.py#L126) — keep as the matcher, only change the output adapter.
- `compute_pareto_frontier` NSGA-II code at [pareto_engine.py:65](agnes/backend/phase3_reasoning/pareto_engine.py#L65) — reuse; only swap the objective vector.
- `Evidence` table + `SourceType` enum in [agnes/backend/db/evidence.py](agnes/backend/db/evidence.py) — map the existing source strings (`"scrape"`, `"llm-inference"`, `"ontology"`, `"sku-regex"`, `"rule"`, `"mock"`) to the new 4-bucket `SourceType`.

## Verification

End-to-end:
```bash
cd agnes
../venv/Scripts/python -m backend.run_phase3
```
Expected: logs now show `compliance_score=0.82 (conf=0.71, cov=0.50)` instead of `compliance_p=0.823`. Printed top-5 proposals show value/confidence/coverage triples, drivers, and weak signals.

Spot checks:
1. A proposal with **no supplier cert data at all** should produce `compliance_score.value ≈ ` (low, via unknown penalty), `confidence` low, `coverage` near 0 — NOT a vacuous 1.0.
2. A proposal with one synonym hit and three unknowns should show `breakdown={compliant:1, non_compliant:0, unknown:3}`, not a hidden-in-average compliance figure.
3. ParetoChart should visibly flag at least one high-impact-low-confidence point with a red ring on a fresh Phase 3 run.

Unit tests *(add to [agnes/tests/test_phase3_uncertainty.py](agnes/tests/test_phase3_uncertainty.py) — new file)*:
- `aggregate()` with empty signals returns `coverage=0`, not vacuous 1.0.
- `aggregate()` with all-LLM signals has `source_distribution["llm"]=1.0`.
- compliance with all-unknowns → unknown penalty applies, score ≠ 1.0.
- Pareto with two proposals equal on value but different on confidence: higher-confidence dominates.

Frontend check: `cd agnes/frontend && npm run dev`, open `/proposals/<id>`, verify value±band + coverage bar + source distribution + drivers list render. Open `/` (Pareto chart), verify low-confidence points are translucent and flagged points have red rings.
