"""
Evidence Trail Builder -- turns a SourcingProposal row into a cited,
human-readable explanation. No LLM; pure joins over Phase 2 enrichment +
Phase 3 verifications.

Output shape (one trail per proposal):
{
  "proposal_id": int,
  "headline": str,
  "claims": [{"claim", "status", "citations": [{label, url, scraped_at,
                                                confidence, snippet}]}],
  "risks": [str],
  "verification_summary": {"counts", "passed", "all_verified"},
}
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.db.queries import (
    get_sourcing_proposal,
    get_all_sourcing_proposals,
    get_substitution_group_detail,
    get_consumer_finished_goods,
)
from backend.phase2_enrichment.enrichment_store import (
    get_supplier_info,
    get_compliance_requirements,
    get_product_scrape,
    get_fda_risk,
    get_entity_verification,
)
from backend.phase3_reasoning.verification_agent import verification_summary

logger = logging.getLogger(__name__)

_SNIPPET_LIMIT = 240
_MAX_COMPLIANCE_CITES = 5


def _truncate(text: str, limit: int = _SNIPPET_LIMIT) -> str:
    if not text:
        return ""
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"


def _clean_url(url: str | None) -> str:
    if not url:
        return ""
    u = str(url).strip()
    if u.lower() in {"unknown", "n/a", "none", "null", "tbd"}:
        return ""
    if not (u.startswith("http://") or u.startswith("https://")):
        return ""
    return u


def _supplier_citation(proposal: dict, supplier_data: dict | None) -> dict | None:
    if not supplier_data:
        return None
    meta = supplier_data.get("_meta") or {}
    url = _clean_url(meta.get("source_url") or supplier_data.get("website"))
    if not url:
        return None
    snippet_bits = []
    certs = supplier_data.get("certifications") or []
    if certs:
        snippet_bits.append("Certifications on record: " + ", ".join(certs))
    if supplier_data.get("headquarters"):
        snippet_bits.append(f"HQ: {supplier_data['headquarters']}")
    if supplier_data.get("notes"):
        snippet_bits.append(supplier_data["notes"])
    return {
        "label": f"{proposal['RecommendedSupplierName']} \u2014 supplier profile",
        "url": url,
        "scraped_at": meta.get("scraped_at", ""),
        "confidence": meta.get("confidence", supplier_data.get("confidence", 0.0)),
        "snippet": _truncate(" \u2022 ".join(snippet_bits)),
    }


def _compliance_citations(consumers: list[dict]) -> list[dict]:
    """Build up to N citations from finished goods with inferred compliance reqs."""
    citations: list[dict] = []
    for c in consumers[:_MAX_COMPLIANCE_CITES * 4]:  # scan a few extras in case some have no data
        fg_id = c["FinishedGoodId"]
        comp = get_compliance_requirements(fg_id)
        if not comp:
            continue
        meta = comp.get("_meta") or {}
        certs = comp.get("required_certifications") or []
        constraints = comp.get("inferred_constraints") or []
        reasoning = comp.get("reasoning") or ""
        bits = []
        if certs:
            bits.append("Required certs inferred: " + ", ".join(certs))
        if constraints:
            bits.append("Constraints: " + ", ".join(constraints))
        if reasoning:
            bits.append(reasoning)
        citations.append({
            "label": f"{c['FinishedGoodSKU']} ({c['CompanyName']}) \u2014 inferred requirements",
            "url": _clean_url(meta.get("source_url")),
            "scraped_at": meta.get("scraped_at", ""),
            "confidence": meta.get("confidence", comp.get("confidence", 0) / 100.0
                                  if isinstance(comp.get("confidence"), (int, float)) else 0.0),
            "snippet": _truncate(" \u2022 ".join(bits)),
        })
        if len(citations) >= _MAX_COMPLIANCE_CITES:
            break
    return citations


def _fda_citation(supplier_id: int) -> dict | None:
    """Build a citation from an OpenFDA enforcement risk record."""
    fda_data = get_fda_risk(supplier_id)
    if not fda_data or fda_data.get("status") == "Error":
        return None
    meta = fda_data.get("_meta") or {}
    source_url = _clean_url(meta.get("source_url") or "")
    status = fda_data.get("status", "Unknown")
    if status == "Warning":
        count = fda_data.get("enforcement_count", 0)
        latest = fda_data.get("latest_recall") or ""
        snippet = f"FDA enforcement records found: {count}. Latest: {latest}"
    else:
        snippet = "No FDA food enforcement records found for this supplier."
    return {
        "label": "OpenFDA Food Enforcement Records",
        "url": source_url,
        "scraped_at": meta.get("scraped_at", ""),
        "confidence": meta.get("confidence", 0.95),
        "snippet": _truncate(snippet),
    }


def _entity_citation(supplier_id: int) -> dict | None:
    """Build a citation from an OpenCorporates entity verification record."""
    entity_data = get_entity_verification(supplier_id)
    if not entity_data:
        return None
    meta = entity_data.get("_meta") or {}
    source = entity_data.get("source", "")
    raw_url = meta.get("source_url") or ""
    url = _clean_url("" if raw_url == "mock" else raw_url)
    bits = [f"Registration status: {entity_data.get('status', 'Unknown')}"]
    if entity_data.get("registered_name"):
        bits.append(f"Registered as: {entity_data['registered_name']}")
    if entity_data.get("jurisdiction"):
        bits.append(f"Jurisdiction: {entity_data['jurisdiction']}")
    label_suffix = "live" if source == "opencorporates_live" else "mock"
    return {
        "label": f"OpenCorporates Entity Verification ({label_suffix})",
        "url": url,
        "scraped_at": meta.get("scraped_at", ""),
        "confidence": meta.get("confidence", 0.70),
        "snippet": _truncate(" \u2022 ".join(bits)),
    }


def _scrape_citations(group_detail: dict) -> list[dict]:
    """Surface any product_scrape evidence for raw materials in the group."""
    citations: list[dict] = []
    seen_urls: set[str] = set()
    for member in group_detail.get("Members", []) or []:
        scrape = get_product_scrape(member["ProductId"])
        if not scrape:
            continue
        meta = scrape.get("_meta") or {}
        url = _clean_url(meta.get("source_url") or scrape.get("url"))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        bits = []
        for k in ("title", "brand", "ingredients", "claims"):
            v = scrape.get(k)
            if v:
                bits.append(f"{k}: {v}" if not isinstance(v, list) else f"{k}: {', '.join(map(str, v))}")
        citations.append({
            "label": f"{member['SKU']} \u2014 scraped product page",
            "url": url,
            "scraped_at": meta.get("scraped_at", ""),
            "confidence": meta.get("confidence", 0.9),
            "snippet": _truncate(" \u2022 ".join(bits)),
        })
        if len(citations) >= 3:
            break
    return citations


def _claim_label(key: str, status: str, proposal: dict) -> str:
    name = proposal["RecommendedSupplierName"]
    if key == "supplier_identity":
        return f"Recommended supplier '{name}' matches the enriched supplier record"
    if key == "compliance_claims":
        return {
            "VERIFIED": f"All inferred compliance requirements are covered by {name}'s certifications",
            "UNVERIFIED": f"Compliance status for {name} could not be fully verified from gathered evidence",
            "CONTRADICTED": f"{name}'s certifications do not cover all inferred compliance requirements",
        }.get(status, f"Compliance status: {status}")
    if key == "consolidation_footprint":
        return (
            f"Consolidation footprint is internally consistent "
            f"({proposal['CompaniesConsolidated']}/{proposal['TotalCompaniesInGroup']} companies)"
        )
    if key == "savings_bounds":
        return f"Estimated savings of {proposal['EstimatedSavingsPct']}% sits within the bounded heuristic range"
    if key == "fda_enforcement_clear":
        return {
            "VERIFIED":     f"{name} has no FDA food enforcement records on file",
            "UNVERIFIED":   f"FDA enforcement status for {name} could not be determined",
            "CONTRADICTED": f"{name} has FDA food enforcement history on record",
        }.get(status, f"FDA enforcement status: {status}")
    if key == "supplier_entity_active":
        return {
            "VERIFIED":     f"{name} is an active registered business entity",
            "UNVERIFIED":   f"Business registration status of {name} could not be verified",
            "CONTRADICTED": f"{name} appears to be a dissolved or inactive business entity",
        }.get(status, f"Entity registration status: {status}")
    return key.replace("_", " ").capitalize()


def build_evidence_trail(proposal_id: int) -> dict | None:
    proposal = get_sourcing_proposal(proposal_id)
    if not proposal:
        return None
    return _build_from_row(proposal)


def _build_from_row(proposal: dict) -> dict:
    group_detail = get_substitution_group_detail(proposal["IngredientGroupId"]) or {}
    canonical = group_detail.get("CanonicalName", f"group {proposal['IngredientGroupId']}")
    supplier_data = get_supplier_info(proposal["RecommendedSupplierId"])
    consumers = get_consumer_finished_goods(proposal["IngredientGroupId"])
    verifications = json.loads(proposal.get("VerificationsJson") or "{}")
    risks = json.loads(proposal.get("RiskFactorsJson") or "[]")
    summary = verification_summary(verifications)

    supplier_id = proposal["RecommendedSupplierId"]
    supplier_cite = _supplier_citation(proposal, supplier_data)
    compliance_cites = _compliance_citations(consumers)
    scrape_cites = _scrape_citations(group_detail)
    fda_cite = _fda_citation(supplier_id)
    entity_cite = _entity_citation(supplier_id)

    headline = (
        f"Recommend consolidating '{canonical}' to {proposal['RecommendedSupplierName']} "
        f"({proposal['CompaniesConsolidated']}/{proposal['TotalCompaniesInGroup']} companies, "
        f"{proposal['EstimatedSavingsPct']:.1f}% est. savings, "
        f"{proposal['ConfidenceScore']:.0f}% confidence, priority {proposal['Priority']})."
    )

    claims: list[dict[str, Any]] = []
    for key, status in verifications.items():
        cites: list[dict] = []
        if key == "supplier_identity" and supplier_cite:
            cites.append(supplier_cite)
        elif key == "compliance_claims":
            cites.extend(compliance_cites)
            if supplier_cite:
                cites.append(supplier_cite)
        elif key in ("consolidation_footprint", "savings_bounds"):
            cites.append({
                "label": "Phase 3 sourcing optimizer (heuristic)",
                "url": "",
                "scraped_at": proposal.get("CreatedAt", ""),
                "confidence": 1.0,
                "snippet": _truncate(proposal.get("EvidenceSummary", "")),
            })
        elif key == "fda_enforcement_clear" and fda_cite:
            cites.append(fda_cite)
        elif key == "supplier_entity_active" and entity_cite:
            cites.append(entity_cite)
        claims.append({
            "claim": _claim_label(key, status, proposal),
            "status": status,
            "citations": cites,
        })

    if scrape_cites:
        claims.append({
            "claim": "Source product pages used while enriching this group",
            "status": "VERIFIED",
            "citations": scrape_cites,
        })

    return {
        "proposal_id": proposal["Id"],
        "ingredient_group_id": proposal["IngredientGroupId"],
        "canonical_name": canonical,
        "recommended_supplier": {
            "id": proposal["RecommendedSupplierId"],
            "name": proposal["RecommendedSupplierName"],
        },
        "headline": headline,
        "metrics": {
            "companies_consolidated": proposal["CompaniesConsolidated"],
            "total_companies_in_group": proposal["TotalCompaniesInGroup"],
            "members_served": proposal["MembersServed"],
            "estimated_savings_pct": proposal["EstimatedSavingsPct"],
            "confidence_score": proposal["ConfidenceScore"],
            "priority": proposal["Priority"],
            "compliance_status": proposal["ComplianceStatus"],
        },
        "claims": claims,
        "risks": risks,
        "verification_summary": summary,
        "created_at": proposal.get("CreatedAt", ""),
    }


def build_all_evidence_trails() -> list[dict]:
    return [_build_from_row(p) for p in get_all_sourcing_proposals()]
