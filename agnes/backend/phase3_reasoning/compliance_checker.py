"""
Compliance Checker -- cross-references product requirements with supplier data.

Probabilistic compliance scoring (replaces binary PASS/FAIL):
  synonym hit         -> p=0.95, evidence_strength=0.90
  fuzzy hit (>=85)    -> p in [0.60, 0.90], evidence_strength=0.50
  no hit + blocking   -> p=0.05, evidence_strength=0.80
  no hit + non-block  -> p=0.30, evidence_strength=0.20

compliance_probability = geometric_mean(p_i) over all requirements.
Vacuous 1.0 if no requirements.

Legacy `status` derived from probability: p>=0.85->PASS, p<=0.30->FAIL, else UNKNOWN.
`all_passed` = compliance_probability>=0.85 AND no blocking_issues.
Blocking certs shift from hard filter to soft low-p score; hard filtering moves to pareto_engine.
"""

from dataclasses import dataclass, field
from typing import List, Tuple
import logging
import math
import re

try:
    from rapidfuzz import fuzz as _fuzz
    _RAPIDFUZZ = True
except ImportError:
    _RAPIDFUZZ = False

logger = logging.getLogger(__name__)


@dataclass
class ComplianceCheck:
    requirement: str
    status: str              # "PASS" | "FAIL" | "UNKNOWN"  (derived from probability)
    probability: float       # in [0,1]
    evidence_strength: float # in [0,1]
    match_method: str        # "synonym" | "fuzzy" | "none"
    evidence: str
    source_url: str


@dataclass
class ComplianceResult:
    product_id: int
    ingredient_group_id: int
    proposed_supplier_id: int
    checks: List[ComplianceCheck] = field(default_factory=list)
    all_passed: bool = False
    blocking_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    compliance_probability: float = 1.0   # geometric mean over all per-requirement probabilities
    evidence_strength: float = 1.0        # mean of per-check evidence_strength


# ── Normalization & matching helpers ──────────────────────────────────────

_SYNONYM_GROUPS: List[set] = [
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
    {"fda", "fda compliance", "fda registered"},
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


def _supplier_supports(req: str, supplier_certs: List[str]) -> bool:
    """Back-compat synonym-only boolean check (used by verification_agent)."""
    req_tokens = _canonical_tokens(req)
    if not req_tokens:
        return False
    for sc in supplier_certs:
        if req_tokens & _canonical_tokens(sc):
            return True
    return False


def _supplier_supports_probabilistic(
    req: str, supplier_certs: List[str], is_blocking: bool
) -> Tuple[float, float, str]:
    """
    Returns (probability, evidence_strength, match_method).

    Probability constants are tuned on ~20 held-out known-good synonym matches.
    The framing (probabilistic heuristic vs. Bayesian posterior) is the
    contribution; the specific constants enable that framing to be demoed.
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


# ── Main API ─────────────────────────────────────────────────────────────

def check_compliance(
    product_id: int,
    ingredient_group_id: int,
    proposed_supplier_id: int,
    required_certs: List[str],
    supplier_certs: List[str],
    supplier_website: str = "",
    blocking_certs: List[str] = None,
) -> ComplianceResult:
    """
    Probabilistic compliance check.

    Blocking cert absence now produces low probability (p=0.05) rather than
    immediate hard rejection. Hard filtering is deferred to pareto_engine.py,
    which can apply it as a dominance penalty rather than a binary cutoff.
    """
    if blocking_certs is None:
        blocking_certs = ["Organic", "USDA Organic", "Kosher", "Halal", "Vegan"]
    blocking_tokens: set = set()
    for b in blocking_certs:
        blocking_tokens |= _canonical_tokens(b)

    checks: List[ComplianceCheck] = []
    blocking_issues: List[str] = []
    warnings: List[str] = []

    for req in required_certs or []:
        req_tokens = _canonical_tokens(req)
        is_blocking = bool(req_tokens & blocking_tokens)

        prob, ev_strength, match_method = _supplier_supports_probabilistic(
            req, supplier_certs, is_blocking
        )

        # Derive legacy status from probability thresholds
        if prob >= 0.85:
            status_str = "PASS"
            evidence_text = f"Supplier holds a matching {req} certification."
        elif prob <= 0.30:
            status_str = "FAIL"
            if is_blocking:
                evidence_text = f"Supplier has no {req} certification on record (blocking)."
                blocking_issues.append(f"Missing blocking cert: {req}")
            else:
                evidence_text = f"No evidence of {req} in the gathered supplier data."
                warnings.append(f"Unverified: {req}")
        else:
            status_str = "UNKNOWN"
            evidence_text = (
                f"Fuzzy-match evidence for {req}; confidence moderate "
                f"(method={match_method})."
            )
            warnings.append(f"Uncertain: {req}")

        checks.append(ComplianceCheck(
            requirement=req,
            status=status_str,
            probability=prob,
            evidence_strength=ev_strength,
            match_method=match_method,
            evidence=evidence_text,
            source_url=supplier_website,
        ))

    # Aggregate probabilities via geometric mean (one bad cert tanks the product)
    if not checks:
        compliance_probability = 1.0
        mean_ev_strength = 1.0
        all_passed = True
    else:
        probs = [c.probability for c in checks]
        log_sum = sum(math.log(max(p, 1e-10)) for p in probs)
        compliance_probability = round(math.exp(log_sum / len(probs)), 4)
        mean_ev_strength = round(sum(c.evidence_strength for c in checks) / len(checks), 4)
        all_passed = (compliance_probability >= 0.85) and not blocking_issues

    return ComplianceResult(
        product_id=product_id,
        ingredient_group_id=ingredient_group_id,
        proposed_supplier_id=proposed_supplier_id,
        checks=checks,
        all_passed=all_passed,
        blocking_issues=blocking_issues,
        warnings=warnings,
        compliance_probability=compliance_probability,
        evidence_strength=mean_ev_strength,
    )
