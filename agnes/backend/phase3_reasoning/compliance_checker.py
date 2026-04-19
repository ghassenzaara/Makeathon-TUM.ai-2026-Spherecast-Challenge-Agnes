"""
Uncertainty-aware compliance scoring:
  synonym hit         -> COMPLIANT, confidence=0.95, source=DETERMINISTIC
  fuzzy hit (>=85)    -> COMPLIANT, confidence=ratio-scaled 0.60–0.90, source=EMBEDDING
  no hit + blocking   -> NON_COMPLIANT, confidence=0.80, source=DETERMINISTIC
  no hit + non-block  -> UNKNOWN (not FAIL) — unknown != non-compliant

Aggregation rule (Fix 1):
  uncertainty_penalty = 1 / (1 + n_unknown + missing_req_weight)
  compliance_probability = geometric_mean(check_probs) * uncertainty_penalty
  (where check_probs are 1.0 for COMPLIANT, 0.0 for NON_COMPLIANT, 0.5 for UNKNOWN)
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import re
import math

try:
    from rapidfuzz import fuzz as _fuzz
    _RAPIDFUZZ = True
except ImportError:
    _RAPIDFUZZ = False

from backend.phase3_reasoning.evidence_model import (
    AggregatedMetric, Signal, SourceType, SOURCE_WEIGHTS,
)

logger = logging.getLogger(__name__)


# ── ComplianceState ──────────────────────────────────────────────────────────

class ComplianceState(Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNKNOWN = "unknown"


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class ComplianceCheck:
    requirement: str
    # First-class fields
    state: ComplianceState
    confidence: float      # 0–1
    source_type: SourceType
    importance: float      # 1.0 blocking, 0.6 standard
    evidence: str
    source_url: str
    # Legacy compat (populated from new fields)
    status: str = ""           # "PASS" | "FAIL" | "UNKNOWN"
    probability: float = 0.0   # mirrors confidence for old consumers
    evidence_strength: float = 0.0
    match_method: str = ""     # "synonym" | "fuzzy" | "none"


@dataclass
class ComplianceResult:
    product_id: int
    ingredient_group_id: int
    proposed_supplier_id: int
    checks: list[ComplianceCheck] = field(default_factory=list)
    all_passed: bool = False
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # New uncertainty-aware fields
    compliance_score: AggregatedMetric | None = None
    breakdown: dict[str, int] = field(
        default_factory=lambda: {"compliant": 0, "non_compliant": 0, "unknown": 0}
    )
    # Legacy compat — populated from compliance_score
    compliance_probability: float = 0.5
    evidence_strength: float = 0.0
    # Fix 2: Compliance Risk Vector
    compliance_risk: dict[str, float] = field(default_factory=dict)


# ── Normalization & matching helpers ─────────────────────────────────────────

_SYNONYM_GROUPS: list[set] = [
    {"non-gmo", "non gmo", "non-gmo project verified", "ngmo"},
    {"organic", "usda organic", "certified organic", "eu organic"},
    {"kosher", "ou kosher", "kof-k", "star-k"},
    {"halal", "ifanca", "halal certified"},
    {"vegan", "certified vegan", "vegan action"},
    {"vegetarian"},
    {"gluten-free", "gluten free", "gfco"},
    {"gmp", "gmp certified", "cgmp", "current gmp"},
    {"nsf", "nsf certified", "nsf international"},
    {"usp", "usp verified"},
    {"iso 9001"},
    {"iso 22000"},
    {"iso 14001"},
    {"fssc 22000"},
    {"sqf", "safe quality food"},
    {"fair trade", "fair-trade certified"},
    {"haccp"},
    {"fda", "fda compliance", "fda registered", "fda-compliant", "fda compliant"},
    {"dairy-free", "dairy free"},
    {"soy-free", "soy free"},
    {"sugar-free", "sugar free"},
]

_WORD_RE = re.compile(r"[a-z0-9]+")


def _normalize_cert(raw: str) -> str:
    if not raw:
        return ""
    s = raw.lower().strip()
    s = s.replace("_", "-")
    s = re.sub(r"\s+", " ", s)
    return s


def _canonical_tokens(raw: str) -> set:
    """Return the canonical synonym-group representatives a cert belongs to."""
    norm = _normalize_cert(raw)
    if not norm:
        return set()
    hits = set()
    for group in _SYNONYM_GROUPS:
        if norm in group:
            hits.add(next(iter(group)))
            continue
        for term in group:
            pat = r"\b" + re.escape(term) + r"\b"
            if re.search(pat, norm):
                hits.add(next(iter(group)))
                break
    if not hits:
        hits.add(norm)
    return hits


def _supplier_supports(req: str, supplier_certs: list[str]) -> bool:
    """Back-compat synonym-only boolean check (used by verification_agent)."""
    req_tokens = _canonical_tokens(req)
    if not req_tokens:
        return False
    for sc in supplier_certs:
        if req_tokens & _canonical_tokens(sc):
            return True
    return False


def _supplier_supports_probabilistic(
    req: str, supplier_certs: list[str], is_blocking: bool
) -> tuple[float, float, str]:
    """
    Returns (probability, evidence_strength, match_method).
    Kept as-is for the matching logic; output is adapted in check_compliance().
    """
    req_tokens = _canonical_tokens(req)

    # 1. Synonym hit — highest confidence
    for sc in supplier_certs:
        if req_tokens & _canonical_tokens(sc):
            return 0.95, 0.90, "synonym"

    # 2. Fuzzy hit via rapidfuzz token_set_ratio
    if _RAPIDFUZZ and supplier_certs:
        req_norm = _normalize_cert(req)
        best_ratio = 0
        for sc in supplier_certs:
            ratio = _fuzz.token_set_ratio(req_norm, _normalize_cert(sc))
            if ratio > best_ratio:
                best_ratio = ratio
        if best_ratio >= 85:
            p = 0.60 + 0.30 * (best_ratio - 85) / 15.0
            return round(min(p, 0.90), 4), 0.50, "fuzzy"

    # 3. No hit
    if is_blocking:
        return 0.05, 0.80, "none"
    return 0.30, 0.20, "none"


# ── Main API ──────────────────────────────────────────────────────────────────

def check_compliance(
    product_id: int,
    ingredient_group_id: int,
    proposed_supplier_id: int,
    required_certs: list[str],
    supplier_certs: list[str],
    supplier_website: str = "",
    blocking_certs: list[str] = None,
) -> ComplianceResult:
    """
    Uncertainty-aware compliance check.

    Returns ComplianceResult with first-class ComplianceState per requirement,
    an AggregatedMetric (compliance_score), and breakdown counts.
    Legacy compliance_probability and evidence_strength are populated from the
    AggregatedMetric for backward compat.
    """
    if blocking_certs is None:
        blocking_certs = ["Organic", "USDA Organic", "Kosher", "Halal", "Vegan"]
    blocking_tokens: set = set()
    for b in blocking_certs:
        blocking_tokens |= _canonical_tokens(b)

    checks: list[ComplianceCheck] = []
    blocking_issues: list[str] = []
    warnings: list[str] = []

    for req in required_certs or []:
        req_tokens = _canonical_tokens(req)
        is_blocking = bool(req_tokens & blocking_tokens)
        importance = 1.0 if is_blocking else 0.6

        prob, ev_strength, match_method = _supplier_supports_probabilistic(
            req, supplier_certs, is_blocking
        )

        # Output adapter: map (prob, match_method) → (ComplianceState, confidence, SourceType)
        # Source-truth mapping (harmonized with confidence_scorer):
        #   synonym hit → ONTOLOGY   (1.0) — curated synonym table
        #   fuzzy hit   → EMBEDDING  (0.4) — approximate match
        #   hard miss   → DETERMINISTIC (0.9) — real evidence of absence from scrape
        #   unverified  → LLM        (0.6) — no evidence; inference-only judgment
        if match_method == "synonym":
            state = ComplianceState.COMPLIANT
            confidence = 0.95
            source_type = SourceType.ONTOLOGY
            evidence_text = f"Supplier holds matching {req} certification."
        elif match_method == "fuzzy":
            state = ComplianceState.COMPLIANT
            confidence = prob  # ratio-scaled 0.60–0.90
            source_type = SourceType.EMBEDDING
            evidence_text = (
                f"Fuzzy match found for {req} in supplier certifications "
                f"(confidence={confidence:.2f})."
            )
        elif is_blocking:
            state = ComplianceState.NON_COMPLIANT
            confidence = 0.80
            source_type = SourceType.DETERMINISTIC
            evidence_text = f"Supplier has no {req} certification (blocking requirement)."
            blocking_issues.append(f"Missing blocking cert: {req}")
        else:
            state = ComplianceState.UNKNOWN
            # Coverage shortfall: supplier has no cert data at all → lower confidence
            confidence = 0.15 if not supplier_certs else prob
            # Unverified requirements are an LLM-level judgement (no direct evidence).
            source_type = SourceType.LLM
            if not supplier_certs:
                evidence_text = f"No supplier certification data available to verify {req}."
            else:
                evidence_text = (
                    f"No matching evidence for {req} in supplier certifications — "
                    f"requirement unverified (not confirmed absent)."
                )
            warnings.append(f"Unverified: {req}")

        # Legacy status derived from state
        status_map = {
            ComplianceState.COMPLIANT: "PASS",
            ComplianceState.NON_COMPLIANT: "FAIL",
            ComplianceState.UNKNOWN: "UNKNOWN",
        }
        legacy_ev_strength = {
            "synonym": 0.90,
            "fuzzy": 0.50,
            "none": ev_strength,
        }.get(match_method, ev_strength)

        checks.append(ComplianceCheck(
            requirement=req,
            state=state,
            confidence=confidence,
            source_type=source_type,
            importance=importance,
            evidence=evidence_text,
            source_url=supplier_website,
            status=status_map[state],
            probability=confidence,
            evidence_strength=legacy_ev_strength,
            match_method=match_method,
        ))

    # ── Empty case: no requirements ────────────────────────────────────────
    if not checks:
        empty_metric = AggregatedMetric(
            value=1.0,
            confidence=1.0,
            coverage=1.0,
            source_distribution={st.value: 0.0 for st in SourceType},
        )
        return ComplianceResult(
            product_id=product_id,
            ingredient_group_id=ingredient_group_id,
            proposed_supplier_id=proposed_supplier_id,
            checks=[],
            all_passed=True,
            compliance_score=empty_metric,
            breakdown={"compliant": 0, "non_compliant": 0, "unknown": 0},
            compliance_probability=1.0,
            evidence_strength=1.0,
            compliance_risk={
                "probability": 0.0,
                "uncertainty": 0.0,
                "missing_data_ratio": 1.0,
            },
        )

    # ── Compliance aggregation (Fix 1: Robust Scoring) ────────────────────────
    # Neutral prior for probability: 0.5 if no checks, otherwise geometric mean
    # Penalty weight for missing metadata/requirements:
    MISSING_REQ_WEIGHT = 0.5  
    
    check_probs = []
    unknown_count = 0
    for c in checks:
        if c.state == ComplianceState.COMPLIANT:
            # We use high probability for pass, but limited by confidence
            check_probs.append(0.5 + (0.5 * c.confidence))
        elif c.state == ComplianceState.NON_COMPLIANT:
            # Low probability for fail
            check_probs.append(0.5 * (1 - c.confidence))
        else:
            # Unknowns are neutral but increase the uncertainty penalty
            check_probs.append(0.5)
            unknown_count += 1

    # Geometric mean of check probabilities
    if not check_probs:
        base_p = 0.5
    else:
        # Use log-space for geometric mean stability (add small epsilon to avoid log(0))
        eps = 1e-6
        base_p = math.exp(sum(math.log(max(eps, p)) for p in check_probs) / len(check_probs))

    # Uncertainty penalty (Fix 1)
    # Penalizes lack of evidence (unknowns) and empty requirements
    penalty_denom = 1.0 + unknown_count + (MISSING_REQ_WEIGHT if not required_certs else 0.0)
    uncertainty_penalty = 1.0 / penalty_denom
    
    compliance_value = round(base_p * uncertainty_penalty, 4)

    # Metric confidence = mean(check.confidence × source_weight)
    weights = SOURCE_WEIGHTS
    metric_confidence = round(
        sum(c.confidence * weights[c.source_type] for c in checks) / len(checks) if checks else 0.0, 4
    )

    # Coverage = fraction with actual match (compliant or non_compliant vs. unknown)
    resolved = sum(1 for c in checks if c.state != ComplianceState.UNKNOWN)
    coverage = round(resolved / len(checks), 4)

    # Source distribution
    type_weights_sum: dict[str, float] = {st.value: 0.0 for st in SourceType}
    for c in checks:
        type_weights_sum[c.source_type.value] += weights[c.source_type]
    total_w = sum(type_weights_sum.values()) or 1.0
    source_distribution = {k: round(v / total_w, 4) for k, v in type_weights_sum.items()}

    # Drivers = top-3 COMPLIANT checks by (confidence × source_weight × importance)
    compliant_checks = [c for c in checks if c.state == ComplianceState.COMPLIANT]
    top_compliant = sorted(
        compliant_checks,
        key=lambda c: c.confidence * weights[c.source_type] * c.importance,
        reverse=True,
    )[:3]
    driver_signals = [
        Signal(
            value=1.0, confidence=c.confidence, source_type=c.source_type,
            importance=c.importance, label=c.requirement,
        )
        for c in top_compliant
    ]

    # Weak signals = high-importance UNKNOWN checks (blocking reqs we can't verify)
    high_imp_unknown = [
        c for c in checks
        if c.state == ComplianceState.UNKNOWN and c.importance > 0.6
    ]
    weak_signals = [
        Signal(
            value=0.0, confidence=c.confidence, source_type=c.source_type,
            importance=c.importance, label=c.requirement,
        )
        for c in high_imp_unknown
    ]

    # Uncertainty sources
    unknown_count = sum(1 for c in checks if c.state == ComplianceState.UNKNOWN)
    uncertainty_sources: list[str] = []
    if unknown_count > 0:
        uncertainty_sources.append(f"{unknown_count} requirement(s) unverified")
    if not supplier_certs:
        uncertainty_sources.append("No supplier certification data available")
    if any(c.source_type == SourceType.EMBEDDING for c in checks):
        uncertainty_sources.append(
            "Some certifications matched via fuzzy-match (lower confidence)"
        )
    if coverage < 0.5:
        uncertainty_sources.append(f"Low coverage ({coverage:.0%} of requirements resolved)")

    compliance_metric = AggregatedMetric(
        value=compliance_value,
        confidence=metric_confidence,
        coverage=coverage,
        source_distribution=source_distribution,
        drivers=driver_signals,
        weak_signals=weak_signals,
        uncertainty_sources=uncertainty_sources,
    )

    breakdown = {
        "compliant": sum(1 for c in checks if c.state == ComplianceState.COMPLIANT),
        "non_compliant": sum(1 for c in checks if c.state == ComplianceState.NON_COMPLIANT),
        "unknown": sum(1 for c in checks if c.state == ComplianceState.UNKNOWN),
    }

    all_passed = (compliance_value >= 0.85) and not blocking_issues

    return ComplianceResult(
        product_id=product_id,
        ingredient_group_id=ingredient_group_id,
        proposed_supplier_id=proposed_supplier_id,
        checks=checks,
        all_passed=all_passed,
        blocking_issues=blocking_issues,
        warnings=warnings,
        compliance_score=compliance_metric,
        breakdown=breakdown,
        # Legacy compat
        compliance_probability=compliance_value,
        evidence_strength=metric_confidence,
        # Fix 2: Risk Vector
        compliance_risk={
            "probability": round(1.0 - compliance_value, 4),
            "uncertainty": round(1.0 - metric_confidence, 4),
            "missing_data_ratio": round(unknown_count / len(checks), 4) if checks else 1.0,
        }
    )
