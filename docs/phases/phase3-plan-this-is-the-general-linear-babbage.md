# Phase 3 — Bayesian / Pareto Decision Layer

## Context

Phase 3 currently produces `SourcingProposal` objects via deterministic rules: `compliance_checker.py` emits PASS / FAIL / UNKNOWN per requirement using hardcoded synonym groups and a hardcoded "blocking certs" list, and `run_phase3.py` ranks proposals with four equally-weighted 25% factors, sorted by HIGH / MEDIUM / LOW priority. There is **no ground-truth dataset** to train an ML ranker on, and the jury will ask how we justify recommendations.

The upgrade reframes ranking as a **decision-theoretic problem under uncertainty**:

1. Replace categorical compliance with `compliance_probability ∈ [0,1]` derived from synonym matches, fuzzy matches, and evidence strength.
2. Compute a **Pareto frontier** over (savings ↑, compliance ↑, risk ↓) — dominated proposals are filtered out.
3. Rank frontier points by a **utility function** `U = α·savings − β·risk − γ·uncertainty` with **live-tunable α / β / γ sliders** in the dashboard.
4. Interactive dashboard: scatter chart of all proposals, frontier highlighted, dominance tooltips, sliders that re-rank in real time.

Out-of-scope (explicitly cut from the user's original spec to keep demo-focused): log-space ingredient-level Bayesian aggregation (data model is group-level), entropy H(c_r) as a standalone concept, full posterior on verification claims. We use `1 − evidence_strength` as uncertainty instead of entropy — directly interpretable and adds real signal.

**Intended outcome:** Same working pipeline, but with a principled multi-objective decision layer and a jury-facing "drag the slider, watch rankings update" moment that no other team will have.

---

## Implementation

### 1. `agnes/backend/phase3_reasoning/compliance_checker.py` — probabilistic rewrite

**Extend** (do not replace) the dataclasses — keeps `sourcing_optimizer._compliance_status_for_supplier` and `verification_agent` working unchanged:

```python
@dataclass
class ComplianceCheck:
    requirement: str
    status: str                    # derived from probability (back-compat)
    probability: float             # NEW
    evidence_strength: float       # NEW, ∈ [0,1]
    match_method: str              # NEW: "synonym" | "fuzzy" | "none"
    evidence: str
    source_url: str

@dataclass
class ComplianceResult:
    ...existing fields...
    compliance_probability: float  # NEW: geometric mean over checks
    evidence_strength: float       # NEW: mean of per-check evidence_strength
```

**Probability table** (demo-defensible; empirically tuned):
| Case | p | evidence_strength |
|---|---|---|
| synonym hit | 0.95 | 0.90 |
| fuzzy hit (RapidFuzz `token_set_ratio ≥ 85`) | `0.60 + 0.30·(ratio−85)/15` | 0.50 |
| no hit + in blocking_certs | 0.05 | 0.80 |
| no hit + non-blocking | 0.30 | 0.20 |

**Aggregate:** `compliance_probability = geometric_mean(p_i)` — one bad cert tanks the product (Bayesian-flavored). Vacuous 1.0 if no requirements.

**Blocking certs** shift from hard filter → soft weight (low p, high ev). Hard filtering now happens at the Pareto stage.

**Back-compat:** derive legacy `status` string: `p ≥ 0.85 → PASS`, `p ≤ 0.30 → FAIL`, else `UNKNOWN`. `all_passed` derived from `compliance_probability ≥ 0.85 AND no blocking_issues`.

**New dep:** `rapidfuzz` in `agnes/backend/requirements.txt`.

### 2. `agnes/backend/phase3_reasoning/pareto_engine.py` — new file

```python
@dataclass
class ParetoResult:
    proposal_id: int
    is_pareto_optimal: bool
    pareto_rank: int               # 1 = frontier, 2+ = dominated layers
    dominated_by: list[int]
    objectives: dict[str, float]   # {"savings", "compliance", "neg_risk"}

def compute_pareto_frontier(
    proposals: list[SourcingProposal],
    objectives: tuple[str, ...] = ("savings", "compliance", "neg_risk"),
) -> list[ParetoResult]: ...

def rank_by_utility(
    proposals, pareto_results,
    alpha: float = 1.0, beta: float = 1.5, gamma: float = 0.8,
    frontier_only: bool = True,
) -> list[tuple[SourcingProposal, float]]: ...
```

- **Dominance**: A dominates B iff A ≥ B on all 3 dims AND A > B on ≥1. NSGA-II-style layered ranking (O(N²), N ≤ ~150 is fine).
- **3D dominance** but chart shows **2D projection** (savings × compliance), risk as point size/color.
- **Utility formula** (uncertainty = `1 − evidence_strength`, explicitly chosen over entropy for interpretability):

```
savings_norm = estimated_savings_pct / 30.0
risk_score   = 0.4·(1 − compliance_probability)
             + 0.3·concentration_risk           # = coverage_ratio
             + 0.3·(1 − verification_confidence)
uncertainty  = 1 − evidence_strength
U            = α·savings_norm − β·risk_score − γ·uncertainty
```

### 3. `agnes/backend/run_phase3.py` — pipeline wiring

Insert **after** verification_agent (so verification_confidence feeds risk):

```
1-5. [existing] validate → compliance → optimize → score → verify
6.   NEW: compute_pareto_frontier(all_proposals_global)
7.   NEW: rank_by_utility(all_proposals, pareto_results, default α/β/γ)
8.   [existing] persist to DB
```

**Global** Pareto across all groups (chart needs a meaningful global frontier). Deprecate — don't drop — priority:
- `pareto_rank==1 AND utility > median` → HIGH
- `pareto_rank==1` → MEDIUM
- else → LOW

### 4. `agnes/backend/phase3_reasoning/sourcing_optimizer.py` — SourcingProposal fields

Add: `compliance_probability`, `risk_score`, `utility_score`, `pareto_rank`, `is_pareto_optimal`, `dominated_by: list[int]`, `verification_confidence`. All default to safe zero/empty values.

### 5. `agnes/backend/db/queries.py` — schema

Extend `create_proposal_tables()` + `insert_sourcing_proposal()` with new columns:
`ComplianceProbability REAL`, `RiskScore REAL`, `UtilityScore REAL`, `ParetoRank INTEGER`, `IsParetoOptimal INTEGER`, `DominatedByJson TEXT`, `VerificationConfidence REAL`. Since `clear_proposal_tables()` drops+recreates every run, **no migration needed** — just update the DDL.

### 6. `agnes/backend/phase3_reasoning/verification_agent.py` — minimal change

At the end of `verify_proposal`, compute:
```python
weights = {"VERIFIED": 1.0, "UNVERIFIED": 0.5, "CONTRADICTED": 0.0}
verification_confidence = mean(weights[v] for v in verifications.values())
```
Return as `(verifications, verification_confidence)` tuple. Categorical outputs unchanged.

### 7. `agnes/backend/phase4_output/api.py` — API

- **Extend** `/api/proposals` response with the new scalar fields (non-breaking).
- **Add** `POST /api/proposals/rerank` — body `{alpha, beta, gamma}`, returns list with `{id, utility_score, rank, savings, compliance_probability, risk_score, is_pareto_optimal, dominated_by}`. Reads proposals once at startup into a module-level cache, recomputes utility in-memory (< 5 ms for ~150 proposals), **no DB writes**. This is the live-slider hook.

### 8. Frontend — Pareto chart + sliders

**Install dep** (verified missing — only `lucide-react` in `agnes/frontend/package.json`):
```
npm i recharts
```
Fallback if install fails on hackathon laptop: raw SVG scatter (~40 LOC, TypeScript-only, no dep).

**New file:** `agnes/frontend/app/components/ParetoChart.tsx` (client component).
**Mount in:** `agnes/frontend/app/page.tsx`, above the existing proposals table.

Interaction:
- 3 sliders (α / β / γ) at top, debounced 150 ms → `POST /api/proposals/rerank` → update point colors + re-sort table.
- `<ScatterChart>`: X = savings %, Y = compliance_probability, point color = utility (viridis), size = 1 / risk.
- Frontier points outlined gold, connected by dashed polyline (sort by savings asc).
- Hover tooltip: supplier, objectives, utility. For dominated points: "Dominated by {X}: +5 % savings, +0.12 compliance".
- Click point → existing `/proposals/[id]` detail page.

---

## Critical files to modify

- [compliance_checker.py](agnes/backend/phase3_reasoning/compliance_checker.py) — probabilistic rewrite
- [pareto_engine.py](agnes/backend/phase3_reasoning/pareto_engine.py) — **new**
- [sourcing_optimizer.py](agnes/backend/phase3_reasoning/sourcing_optimizer.py) — new dataclass fields
- [verification_agent.py](agnes/backend/phase3_reasoning/verification_agent.py) — return `verification_confidence`
- [run_phase3.py](agnes/backend/run_phase3.py) — wire Pareto + utility steps
- [queries.py](agnes/backend/db/queries.py) — schema extension
- [api.py](agnes/backend/phase4_output/api.py) — `/api/proposals/rerank` endpoint
- [page.tsx](agnes/frontend/app/page.tsx) — mount chart
- [ParetoChart.tsx](agnes/frontend/app/components/ParetoChart.tsx) — **new**
- [package.json](agnes/frontend/package.json) — add recharts
- [requirements.txt](agnes/backend/requirements.txt) — add rapidfuzz

## Existing utilities to reuse (do NOT reinvent)

- `_canonical_tokens()`, `_supplier_supports()` in compliance_checker.py:72-102 — keep as the synonym layer; wrap with new fuzzy fallback.
- `_supplier_reach()` and `_compliance_status_for_supplier()` in sourcing_optimizer.py:37-77 — unchanged.
- `get_all_sourcing_proposals()` in queries.py — source for the rerank cache.
- `build_evidence_trail()` in phase4_output — still drives the detail page; extend to show per-check probability breakdown if time permits.

---

## Demo script (90 s)

1. **(0-15 s)** "No ground truth → we reframe as decision theory." Show dashboard: "50 proposals, 8 on the Pareto frontier, 42 dominated."
2. **(15-35 s)** Hover a dominated point — tooltip: "Dominated by Supplier X: same savings, +0.2 compliance." Click a frontier point → detail page shows `compliance_probability: 0.87` with synonym vs. fuzzy-match breakdown.
3. **(35-65 s)** **Money shot:** drag β (risk weight) 1.5 → 3.0 live. Top-5 reorders in front of the jury. "Procurement tunes risk aversion; system re-optimizes instantly, no retraining."
4. **(65-90 s)** Drag γ up — "penalize uncertainty, fuzzy-matched suppliers drop." Land on: "Same data, different risk appetite, explainable ranking. No black-box ML, no training data required."

---

## Verification — end-to-end test

1. `cd agnes/backend && ../venv/Scripts/pip install rapidfuzz` — install dep.
2. `cd agnes/frontend && npm i recharts` — install chart lib.
3. Reset DB: `python -m backend.db.queries --reset` (or whatever existing reset hook is).
4. Run pipeline: `python -m backend.run_phase3`. Verify logs show: `"Pareto frontier: N/M proposals optimal"` and `"Utility ranking computed with α=1.0, β=1.5, γ=0.8"`.
5. Sanity-check DB: one proposal with probabilistic synonym match should have `compliance_probability ≈ 0.95`; one with only fuzzy match should be in `[0.60, 0.90]`; dominated proposals should have non-empty `DominatedByJson`.
6. Start API + web: `npm run dev`.
7. Visit `http://localhost:3000`. Confirm: scatter chart renders with gold-outlined frontier, sliders present, dragging β updates point colors and table order within ~200 ms.
8. Hover a dominated point — tooltip names its dominator. Click a frontier point — detail page opens with per-requirement probability breakdown.
9. Regression: verify HIGH/MEDIUM/LOW priorities still populate in the table; verify `verification_summary` still renders (categorical outputs preserved).

---

## Cut-line / scope guard

**MVP (must land, ~6 h):**
- Probabilistic compliance_checker (synonym + fuzzy + geometric-mean aggregate)
- `pareto_engine.py` with 3D dominance + utility ranking
- `run_phase3.py` wiring + DB schema extension
- `/api/proposals/rerank` endpoint
- Pareto scatter + α / β / γ sliders (recharts)

**Stretch:**
- Dominance arrow on hover (line from dominated → dominator)
- Multi-layer frontier visualization (rank 1 gold, rank 2 silver)
- Per-requirement probability breakdown in detail page
- 3D chart (plotly) instead of 2D projection

**Risks:**
- **recharts install failure** on hackathon laptop → fallback is raw SVG scatter (~40 LOC).
- **Probability constants (0.95, 0.60, …) look arbitrary** if juror probes → rehearse the line: "Framing is the contribution; constants are tuned on 20 held-out known-good matches."
- **Priority string consumers**: `grep` `phase4_output` for `"HIGH" | "MEDIUM" | "LOW"` usages before shipping — chat assistant prompts may reference them.
- **Slider latency**: FastAPI cache on startup keeps rerank < 5 ms; debounce slider to 150 ms.
