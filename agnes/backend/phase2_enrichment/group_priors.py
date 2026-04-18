"""
Group Priors — group-aware fallback for enrichment.

When a scraper gets 403'd or a supplier page is unavailable, we can still
infer likely certifications and attributes for a product by looking at
what other members of the same SubstitutionGroup already have.

Example: if 5/6 members of the "ascorbic-acid" group are certified
Non-GMO, the 6th member very likely is too.
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from typing import Optional

from backend.db.queries import (
    get_all_substitution_groups,
    get_substitution_group_detail,
    get_ingredient_card,
)

logger = logging.getLogger(__name__)


def get_group_for_product(product_id: int) -> Optional[dict]:
    """Find the substitution group that contains this product."""
    from backend.db.connection import get_cursor
    with get_cursor() as cur:
        cur.execute("""
            SELECT GroupId FROM SubstitutionGroupMember
            WHERE ProductId = ?
        """, (product_id,))
        row = cur.fetchone()
    if not row:
        return None
    return get_substitution_group_detail(row["GroupId"])


def get_group_priors(product_id: int) -> dict:
    """
    Compute prior probabilities for a product's attributes based on
    its substitution group siblings.

    Returns:
        {
            "certifications": {"Non-GMO": 0.83, "Kosher": 0.50, ...},
            "form": {"powder": 0.67, "capsule": 0.33},
            "source": {"plant": 1.0},
            ...
            "group_size": 6,
            "group_name": "ascorbic-acid",
        }
    """
    group = get_group_for_product(product_id)
    if not group:
        return {"group_size": 0, "group_name": None}

    members = group.get("Members", [])
    if len(members) <= 1:
        return {"group_size": len(members), "group_name": group.get("CanonicalName")}

    # Collect cards for all group members
    sibling_cards = []
    for m in members:
        pid = m["ProductId"]
        if pid == product_id:
            continue
        card = get_ingredient_card(pid)
        if card:
            sibling_cards.append(card)

    if not sibling_cards:
        return {"group_size": len(members), "group_name": group.get("CanonicalName")}

    n = len(sibling_cards)
    priors: dict = {
        "group_size": len(members),
        "group_name": group.get("CanonicalName"),
    }

    # Certification priors
    cert_counter: Counter = Counter()
    for card in sibling_cards:
        for cert in card.get("Certifications", []):
            cert_counter[cert] += 1
    if cert_counter:
        priors["certifications"] = {
            cert: round(count / n, 2) for cert, count in cert_counter.most_common()
        }

    # Attribute priors (form, source, grade, etc.)
    for attr in ["Form", "Grade", "Source", "SourceDetail", "Hydration",
                  "SaltOrEster", "Chirality", "VitDForm", "VitB12Form"]:
        counter: Counter = Counter()
        for card in sibling_cards:
            val = card.get(attr)
            if val:
                counter[val] += 1
        if counter:
            key = _camel_to_snake(attr)
            priors[key] = {
                v: round(c / n, 2) for v, c in counter.most_common()
            }

    return priors


def apply_group_priors_to_scrape(
    scrape_result: dict,
    product_id: int,
    min_prior: float = 0.6,
) -> dict:
    """
    Augment a scrape result with group priors where data is missing.

    Only fills in certifications/attributes if the group prior ≥ min_prior.
    Tags filled fields with "_from_group_prior" so Evidence can note the source.
    """
    priors = get_group_priors(product_id)
    if priors.get("group_size", 0) < 2:
        return scrape_result

    # Fill certifications if scrape returned empty/few
    existing_certs = set(scrape_result.get("certifications", []))
    prior_certs = priors.get("certifications", {})
    added_certs = []
    for cert, prob in prior_certs.items():
        if prob >= min_prior and cert not in existing_certs:
            added_certs.append(cert)

    if added_certs:
        scrape_result.setdefault("certifications", [])
        scrape_result["certifications"].extend(added_certs)
        scrape_result["_group_prior_certs"] = added_certs
        logger.info(
            "  Product %d: added %d certs from group priors (group=%s)",
            product_id, len(added_certs), priors.get("group_name"),
        )

    return scrape_result


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    import re
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return s
