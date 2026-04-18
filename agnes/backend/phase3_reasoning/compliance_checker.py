"""
Compliance Checker -- cross-references product requirements with supplier data.
"""

from dataclasses import dataclass, field
from typing import List
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class ComplianceCheck:
    requirement: str
    status: str       # "PASS" | "FAIL" | "UNKNOWN"
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


# ── Normalization & matching helpers ──────────────────────────────────────

# Canonical synonym groups. Matching is case-insensitive on normalized tokens.
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
    """Lowercase, collapse whitespace, strip punctuation-ish characters."""
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
            # Word-boundary contains match (so "gmp" doesn't match "cgmp" and vice-versa
            # unless both are in the same synonym group)
            pat = r"\b" + re.escape(term) + r"\b"
            if re.search(pat, norm):
                hits.add(next(iter(group)))
                break
    if not hits:
        # Fall back to the normalized cert itself as its own identity
        hits.add(norm)
    return hits


def _supplier_supports(req: str, supplier_certs: List[str]) -> bool:
    req_tokens = _canonical_tokens(req)
    if not req_tokens:
        return False
    for sc in supplier_certs:
        if req_tokens & _canonical_tokens(sc):
            return True
    return False


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
    Validates if a proposed supplier meets the compliance requirements of the
    finished good.

    Args:
        blocking_certs: certs whose absence is a *blocking* failure (not a warning).
                        Defaults to the strict subset: organic, kosher, halal, vegan.
    """
    if blocking_certs is None:
        blocking_certs = ["Organic", "USDA Organic", "Kosher", "Halal", "Vegan"]
    blocking_tokens = set()
    for b in blocking_certs:
        blocking_tokens |= _canonical_tokens(b)

    checks: List[ComplianceCheck] = []
    blocking_issues: List[str] = []
    warnings: List[str] = []

    for req in required_certs or []:
        if _supplier_supports(req, supplier_certs):
            checks.append(ComplianceCheck(
                requirement=req,
                status="PASS",
                evidence=f"Supplier holds a matching {req} certification.",
                source_url=supplier_website,
            ))
            continue

        req_tokens = _canonical_tokens(req)
        if req_tokens & blocking_tokens:
            checks.append(ComplianceCheck(
                requirement=req,
                status="FAIL",
                evidence=f"Supplier has no {req} certification on record (blocking).",
                source_url=supplier_website,
            ))
            blocking_issues.append(f"Missing blocking cert: {req}")
        else:
            checks.append(ComplianceCheck(
                requirement=req,
                status="UNKNOWN",
                evidence=f"No evidence of {req} in the gathered supplier data.",
                source_url=supplier_website,
            ))
            warnings.append(f"Unverified: {req}")

    # all_passed = every required cert verifiably PASSES (UNKNOWN is not a pass)
    all_passed = (
        bool(checks)
        and all(c.status == "PASS" for c in checks)
        and not blocking_issues
    )
    # If there were no requirements, treat as vacuously passed (nothing to check)
    if not checks:
        all_passed = True

    return ComplianceResult(
        product_id=product_id,
        ingredient_group_id=ingredient_group_id,
        proposed_supplier_id=proposed_supplier_id,
        checks=checks,
        all_passed=all_passed,
        blocking_issues=blocking_issues,
        warnings=warnings,
    )
