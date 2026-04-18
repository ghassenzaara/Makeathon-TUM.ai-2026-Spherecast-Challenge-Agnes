"""
Contradiction Detector — finds conflicting claims across sources.

Checks for:
  1. Source contradictions: "vegan" cert on product with animal-derived ingredient
  2. Inter-source conflicts: iHerb says "Organic" but supplier lacks organic cert
  3. Intra-group conflicts: group members have incompatible attributes (blocking axes)
  4. Compliance gaps: FG requires cert that no available supplier holds

Each contradiction is stored in the Contradiction table with severity
(critical / warning / info) and a detail JSON explaining the conflict.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from backend.db.queries import (
    get_all_substitution_groups,
    get_substitution_group_detail,
    get_ingredient_card,
    get_all_ingredient_cards,
    get_all_finished_goods,
    get_bom_for_product,
    get_requirements_for_raw_material,
    get_suppliers_for_product,
    insert_contradiction,
    count_contradictions,
    get_substitution_links_for_group,
)
from backend.db.evidence import record_evidence
from backend.phase2_enrichment.enrichment_store import (
    get_product_scrape,
    get_supplier_info,
)
from backend.ontology import get_ontologies

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Rule checks
# ──────────────────────────────────────────────

def _check_vegan_animal_conflict(cards: list[dict]) -> list[dict]:
    """
    Find products labeled vegan but containing animal-derived ingredients.
    """
    onts = get_ontologies()
    contradictions = []

    for card in cards:
        pid = card["ProductId"]
        certs = card.get("Certifications", [])
        source = card.get("Source")
        substance = card.get("Substance")

        # Check if product has vegan cert
        has_vegan = any(
            onts.certifications.canonicalize(c) == "vegan" for c in certs
        )
        if not has_vegan:
            continue

        # Check if source is animal
        if source and source in ("animal", "marine"):
            contradictions.append({
                "SubjectType": "Product",
                "SubjectId": pid,
                "Rule": "vegan-animal-source",
                "DetailJson": json.dumps({
                    "product_id": pid,
                    "substance": substance,
                    "source": source,
                    "certification": "vegan",
                    "message": f"Product has vegan cert but source={source}",
                }),
                "Severity": "critical",
                "DetectedAt": datetime.now(timezone.utc).isoformat(),
            })

        # Check category
        if substance:
            category = onts.substances.category_of(substance)
            if category in ("protein-animal", "capsule-animal"):
                contradictions.append({
                    "SubjectType": "Product",
                    "SubjectId": pid,
                    "Rule": "vegan-animal-category",
                    "DetailJson": json.dumps({
                        "product_id": pid,
                        "substance": substance,
                        "category": category,
                        "certification": "vegan",
                        "message": f"Vegan cert but substance category={category}",
                    }),
                    "Severity": "critical",
                    "DetectedAt": datetime.now(timezone.utc).isoformat(),
                })

    return contradictions


def _check_group_blocking_conflicts(groups: list[dict]) -> list[dict]:
    """
    Find substitution groups where members differ on blocking axes.
    """
    onts = get_ontologies()
    blocking_axes = set(onts.attributes.blocking_axes)
    contradictions = []

    for group in groups:
        gid = group["Id"]
        detail = get_substitution_group_detail(gid)
        if not detail:
            continue

        members = detail.get("Members", [])
        if len(members) < 2:
            continue

        # Load cards for all members
        member_cards = []
        for m in members:
            card = get_ingredient_card(m["ProductId"])
            if card:
                member_cards.append(card)

        if len(member_cards) < 2:
            continue

        # Check each blocking axis for conflicts
        col_map = {
            "hydration": "Hydration",
            "salt_or_ester": "SaltOrEster",
            "chirality": "Chirality",
            "vit_d_form": "VitDForm",
            "vit_b12_form": "VitB12Form",
        }
        for axis in blocking_axes:
            col = col_map.get(axis)
            if not col:
                continue
            values = set()
            for card in member_cards:
                v = card.get(col)
                if v:
                    values.add(v)
            if len(values) > 1:
                contradictions.append({
                    "SubjectType": "SubstitutionGroup",
                    "SubjectId": gid,
                    "Rule": f"blocking-axis-conflict:{axis}",
                    "DetailJson": json.dumps({
                        "group_id": gid,
                        "group_name": group.get("CanonicalName"),
                        "axis": axis,
                        "conflicting_values": sorted(values),
                        "message": f"Group has conflicting {axis} values: {sorted(values)}",
                    }),
                    "Severity": "warning",
                    "DetectedAt": datetime.now(timezone.utc).isoformat(),
                })

    return contradictions


def _check_supplier_cert_gaps(finished_goods: list[dict]) -> list[dict]:
    """
    Find cases where a FG requires a cert but no supplier for an ingredient holds it.
    """
    onts = get_ontologies()
    contradictions = []

    for fg in finished_goods:
        fg_id = fg["Id"]
        scraped = get_product_scrape(fg_id)
        if not scraped:
            continue

        fg_certs = scraped.get("certifications", [])
        if not fg_certs:
            continue

        # Canonical FG certs
        canonical_certs = set()
        for c in fg_certs:
            cc = onts.certifications.canonicalize(c)
            if cc and onts.certifications.is_blocking(cc):
                canonical_certs.add(cc)

        if not canonical_certs:
            continue

        # Check each BOM component's suppliers
        bom = get_bom_for_product(fg_id)
        for component in bom:
            rm_id = component["ConsumedProductId"]
            suppliers = get_suppliers_for_product(rm_id)

            for required_cert in canonical_certs:
                # Check if any supplier holds this cert
                supplier_has_cert = False
                for s in suppliers:
                    s_info = get_supplier_info(s["SupplierId"])
                    if s_info:
                        s_certs = s_info.get("certifications", [])
                        for sc in s_certs:
                            if onts.certifications.canonicalize(sc) == required_cert:
                                supplier_has_cert = True
                                break
                    if supplier_has_cert:
                        break

                if not supplier_has_cert and suppliers:
                    contradictions.append({
                        "SubjectType": "Product",
                        "SubjectId": rm_id,
                        "Rule": f"supplier-cert-gap:{required_cert}",
                        "DetailJson": json.dumps({
                            "finished_good_id": fg_id,
                            "finished_good_sku": fg.get("SKU"),
                            "raw_material_id": rm_id,
                            "required_cert": required_cert,
                            "suppliers_checked": len(suppliers),
                            "message": f"FG requires {required_cert} but no supplier for RM {rm_id} holds it",
                        }),
                        "Severity": "warning",
                        "DetectedAt": datetime.now(timezone.utc).isoformat(),
                    })

    return contradictions


def _check_scrape_confidence_conflicts() -> list[dict]:
    """
    Find products where different scrape sources disagree on certifications.
    """
    contradictions = []
    # This is a lighter check — if iHerb says one thing but mock says another
    # In practice, we look for low-confidence scrapes
    cards = get_all_ingredient_cards()
    for card in cards:
        pid = card["ProductId"]
        scrape = get_product_scrape(pid)
        if not scrape:
            continue
        conf = scrape.get("_inference_confidence", scrape.get("confidence", 100))
        if isinstance(conf, (int, float)) and conf < 20:
            contradictions.append({
                "SubjectType": "Product",
                "SubjectId": pid,
                "Rule": "low-confidence-scrape",
                "DetailJson": json.dumps({
                    "product_id": pid,
                    "confidence": conf,
                    "source": scrape.get("_source", "unknown"),
                    "message": f"Scrape confidence very low ({conf}), data unreliable",
                }),
                "Severity": "info",
                "DetectedAt": datetime.now(timezone.utc).isoformat(),
            })

    return contradictions


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def detect_all_contradictions() -> int:
    """
    Run all contradiction checks and store results.

    Returns:
        Number of contradictions found.
    """
    logger.info("Running contradiction detection...")

    all_contradictions: list[dict] = []

    # Check 1: Vegan-animal conflicts
    logger.info("  Check 1: Vegan-animal source conflicts...")
    cards = get_all_ingredient_cards()
    # Enrich with certs
    for card in cards:
        card_detail = get_ingredient_card(card["ProductId"])
        if card_detail:
            card["Certifications"] = card_detail.get("Certifications", [])
        else:
            card["Certifications"] = []
    vegan_conflicts = _check_vegan_animal_conflict(cards)
    all_contradictions.extend(vegan_conflicts)
    logger.info(f"    Found {len(vegan_conflicts)} vegan-animal conflicts")

    # Check 2: Group blocking-axis conflicts
    logger.info("  Check 2: Group blocking-axis conflicts...")
    groups = get_all_substitution_groups()
    blocking_conflicts = _check_group_blocking_conflicts(groups)
    all_contradictions.extend(blocking_conflicts)
    logger.info(f"    Found {len(blocking_conflicts)} blocking-axis conflicts")

    # Check 3: Supplier cert gaps
    logger.info("  Check 3: Supplier certification gaps...")
    fgs = get_all_finished_goods()
    cert_gaps = _check_supplier_cert_gaps(fgs)
    all_contradictions.extend(cert_gaps)
    logger.info(f"    Found {len(cert_gaps)} supplier cert gaps")

    # Check 4: Low-confidence scrape warnings
    logger.info("  Check 4: Low-confidence scrape data...")
    low_conf = _check_scrape_confidence_conflicts()
    all_contradictions.extend(low_conf)
    logger.info(f"    Found {len(low_conf)} low-confidence warnings")

    # Store all contradictions
    for c in all_contradictions:
        insert_contradiction(c)

    logger.info(
        f"Contradiction detection complete: {len(all_contradictions)} total "
        f"({sum(1 for c in all_contradictions if c['Severity'] == 'critical')} critical, "
        f"{sum(1 for c in all_contradictions if c['Severity'] == 'warning')} warning, "
        f"{sum(1 for c in all_contradictions if c['Severity'] == 'info')} info)"
    )
    return len(all_contradictions)
