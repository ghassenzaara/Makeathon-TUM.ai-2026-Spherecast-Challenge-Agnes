"""
Substitution Groups — builds, stores, and queries substitution groups.

Orchestrates the full Phase 1 pipeline:
  1. Loads all raw materials from DB
  2. Parses SKUs to extract ingredient names
  3. Clusters ingredients by semantic similarity
  4. Cross-references with BOM and supplier data
  5. Stores results in the SubstitutionGroup tables
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from backend.config import OPENAI_API_KEY
from backend.phase1_extraction.sku_parser import parse_sku, ParsedSKU
from backend.phase1_extraction.semantic_matcher import (
    build_ingredient_embeddings,
    cluster_ingredients,
    cluster_ingredients_exact_only,
    IngredientCluster,
)
from backend.db.queries import (
    get_all_raw_materials,
    get_bom_components_with_suppliers,
    create_substitution_tables,
    clear_substitution_tables,
    insert_substitution_group,
    insert_group_members,
    insert_group_suppliers,
    insert_group_consumers,
    get_all_substitution_groups,
    get_substitution_group_detail,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data models
# ──────────────────────────────────────────────

@dataclass
class IngredientMember:
    """One raw material product that belongs to a substitution group."""
    product_id: int
    sku: str
    company_id: int
    company_name: str
    ingredient_name: str


@dataclass
class SupplierInfo:
    """A supplier that can provide a member of a substitution group."""
    supplier_id: int
    supplier_name: str
    product_id: int  # Which product this supplier can supply


@dataclass
class SubstitutionGroup:
    """
    A group of functionally equivalent ingredients across companies.

    This is the core Phase 1 output — each group represents a
    consolidation opportunity.
    """
    id: Optional[int] = None
    canonical_name: str = ""
    members: list[IngredientMember] = field(default_factory=list)
    suppliers: list[SupplierInfo] = field(default_factory=list)
    consuming_product_ids: list[int] = field(default_factory=list)
    consuming_product_skus: list[str] = field(default_factory=list)
    cross_company_count: int = 0
    similarity_score: float = 1.0

    @property
    def has_consolidation_potential(self) -> bool:
        """True if this group spans multiple companies."""
        return self.cross_company_count >= 2

    @property
    def member_count(self) -> int:
        return len(self.members)

    def summary(self) -> str:
        """One-line human-readable summary."""
        return (
            f"[{self.canonical_name}] "
            f"{self.cross_company_count} companies, "
            f"{len(self.members)} variants, "
            f"{len(self.suppliers)} suppliers, "
            f"{len(self.consuming_product_ids)} finished goods | "
            f"similarity={self.similarity_score:.2f}"
        )


# ──────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────

def build_substitution_groups(
    use_semantic: bool = True,
    force_refresh_embeddings: bool = False,
) -> list[SubstitutionGroup]:
    """
    Full Phase 1 pipeline: parse → cluster → enrich → store.

    Args:
        use_semantic: Whether to use OpenAI embeddings for clustering.
                      Falls back to exact-match if False or no API key.
        force_refresh_embeddings: If True, re-generate embeddings.

    Returns:
        List of SubstitutionGroup objects, sorted by consolidation potential.
    """
    logger.info("=" * 60)
    logger.info("PHASE 1: Building Substitution Groups")
    logger.info("=" * 60)

    # ── Step 1: Load raw materials ──
    logger.info("Step 1: Loading raw materials from database...")
    raw_materials = get_all_raw_materials()
    logger.info(f"  Loaded {len(raw_materials)} raw materials")

    # ── Step 2: Parse SKUs ──
    logger.info("Step 2: Parsing SKUs...")
    parsed_materials = []
    ingredient_names_set = set()

    for rm in raw_materials:
        parsed = parse_sku(rm["SKU"])
        if parsed.ingredient_name:
            parsed_materials.append({
                "product_id": rm["Id"],
                "sku": rm["SKU"],
                "company_id": rm["CompanyId"],
                "company_name": rm["CompanyName"],
                "ingredient_name": parsed.ingredient_name,
            })
            ingredient_names_set.add(parsed.ingredient_name)
        else:
            logger.warning(f"  Could not parse ingredient from SKU: {rm['SKU']}")

    unique_names = sorted(ingredient_names_set)
    logger.info(
        f"  Parsed {len(parsed_materials)} materials -> "
        f"{len(unique_names)} unique ingredient names"
    )

    # ── Step 3: Cluster ingredients ──
    logger.info("Step 3: Clustering ingredients...")

    if use_semantic and OPENAI_API_KEY:
        logger.info("  Using semantic (embedding-based) clustering...")
        embeddings = build_ingredient_embeddings(
            unique_names, force_refresh=force_refresh_embeddings
        )
        clusters = cluster_ingredients(unique_names, embeddings)
    else:
        if use_semantic and not OPENAI_API_KEY:
            logger.warning(
                "  No OPENAI_API_KEY set — falling back to exact-match clustering"
            )
        logger.info("  Using exact-match clustering...")
        clusters = cluster_ingredients_exact_only(unique_names)

    logger.info(f"  Formed {len(clusters)} clusters")

    # ── Step 4: Build name → cluster mapping ──
    name_to_cluster: dict[str, IngredientCluster] = {}
    for cluster in clusters:
        for name in cluster.member_names:
            name_to_cluster[name] = cluster

    # ── Step 5: Load BOM + supplier data ──
    logger.info("Step 4: Loading BOM and supplier relationships...")
    bom_data = get_bom_components_with_suppliers()
    logger.info(f"  Loaded {len(bom_data)} BOM+supplier records")

    # Build lookup: product_id → list of (supplier_id, supplier_name)
    product_suppliers: dict[int, list[dict]] = defaultdict(list)
    # Build lookup: product_id → list of (finished_good_id, finished_good_sku)
    product_consumers: dict[int, list[dict]] = defaultdict(list)

    for row in bom_data:
        rm_id = row["RawMaterialId"]
        if row["SupplierId"] is not None:
            product_suppliers[rm_id].append({
                "SupplierId": row["SupplierId"],
                "SupplierName": row["SupplierName"],
                "ProductId": rm_id,
            })
        product_consumers[rm_id].append({
            "FinishedGoodId": row["FinishedGoodId"],
            "FinishedGoodSKU": row["FinishedGoodSKU"],
        })

    # Deduplicate suppliers per product
    for rm_id in product_suppliers:
        seen = set()
        deduped = []
        for s in product_suppliers[rm_id]:
            key = (s["SupplierId"], s["ProductId"])
            if key not in seen:
                seen.add(key)
                deduped.append(s)
        product_suppliers[rm_id] = deduped

    # Deduplicate consumers per product
    for rm_id in product_consumers:
        seen = set()
        deduped = []
        for c in product_consumers[rm_id]:
            key = c["FinishedGoodId"]
            if key not in seen:
                seen.add(key)
                deduped.append(c)
        product_consumers[rm_id] = deduped

    # ── Step 6: Assemble SubstitutionGroup objects ──
    logger.info("Step 5: Assembling substitution groups...")

    # Group parsed materials by cluster canonical name
    cluster_materials: dict[str, list[dict]] = defaultdict(list)
    for mat in parsed_materials:
        cluster = name_to_cluster.get(mat["ingredient_name"])
        if cluster:
            cluster_materials[cluster.canonical_name].append(mat)

    groups: list[SubstitutionGroup] = []

    for cluster in clusters:
        materials = cluster_materials.get(cluster.canonical_name, [])
        if not materials:
            continue

        # Collect members
        members = [
            IngredientMember(
                product_id=m["product_id"],
                sku=m["sku"],
                company_id=m["company_id"],
                company_name=m["company_name"],
                ingredient_name=m["ingredient_name"],
            )
            for m in materials
        ]

        # Collect all suppliers across all members
        all_suppliers: list[SupplierInfo] = []
        seen_supplier_keys = set()
        for m in materials:
            for s in product_suppliers.get(m["product_id"], []):
                key = (s["SupplierId"], s["ProductId"])
                if key not in seen_supplier_keys:
                    seen_supplier_keys.add(key)
                    all_suppliers.append(SupplierInfo(
                        supplier_id=s["SupplierId"],
                        supplier_name=s["SupplierName"],
                        product_id=s["ProductId"],
                    ))

        # Collect all consuming finished goods
        all_consumer_ids = set()
        all_consumer_skus = set()
        for m in materials:
            for c in product_consumers.get(m["product_id"], []):
                all_consumer_ids.add(c["FinishedGoodId"])
                all_consumer_skus.add(c["FinishedGoodSKU"])

        # Count distinct companies
        distinct_companies = len(set(m.company_id for m in members))

        group = SubstitutionGroup(
            canonical_name=cluster.canonical_name,
            members=members,
            suppliers=all_suppliers,
            consuming_product_ids=sorted(all_consumer_ids),
            consuming_product_skus=sorted(all_consumer_skus),
            cross_company_count=distinct_companies,
            similarity_score=cluster.avg_similarity,
        )
        groups.append(group)

    # Sort by consolidation potential
    groups.sort(
        key=lambda g: (g.cross_company_count, g.member_count),
        reverse=True,
    )

    logger.info(f"  Built {len(groups)} substitution groups")
    consolidation_candidates = sum(
        1 for g in groups if g.has_consolidation_potential
    )
    logger.info(
        f"  {consolidation_candidates} groups span multiple companies "
        f"(consolidation candidates)"
    )

    # ── Step 7: Store in database ──
    logger.info("Step 6: Storing results in database...")
    _store_groups(groups)

    logger.info("=" * 60)
    logger.info("PHASE 1 COMPLETE")
    logger.info("=" * 60)

    return groups


def _store_groups(groups: list[SubstitutionGroup]):
    """Persist substitution groups to the database."""
    # Clear previous results and create tables
    clear_substitution_tables()

    for group in groups:
        # Insert the group
        group_id = insert_substitution_group(
            canonical_name=group.canonical_name,
            cross_company_count=group.cross_company_count,
            member_count=group.member_count,
            avg_similarity=group.similarity_score,
        )
        group.id = group_id

        # Insert members
        member_dicts = [
            {
                "ProductId": m.product_id,
                "SKU": m.sku,
                "CompanyId": m.company_id,
                "CompanyName": m.company_name,
                "IngredientName": m.ingredient_name,
            }
            for m in group.members
        ]
        insert_group_members(group_id, member_dicts)

        # Insert suppliers
        supplier_dicts = [
            {
                "SupplierId": s.supplier_id,
                "SupplierName": s.supplier_name,
                "ProductId": s.product_id,
            }
            for s in group.suppliers
        ]
        if supplier_dicts:
            insert_group_suppliers(group_id, supplier_dicts)

        # Insert consumers
        consumer_dicts = [
            {"FinishedGoodId": fgid, "FinishedGoodSKU": fgsku}
            for fgid, fgsku in zip(
                group.consuming_product_ids, group.consuming_product_skus
            )
        ]
        if consumer_dicts:
            insert_group_consumers(group_id, consumer_dicts)

    logger.info(f"  Stored {len(groups)} groups in database")


# ──────────────────────────────────────────────
# Convenience functions
# ──────────────────────────────────────────────

def get_top_consolidation_opportunities(limit: int = 20) -> list[dict]:
    """
    Return the top substitution groups ranked by consolidation potential.
    Quick read from stored results.
    """
    all_groups = get_all_substitution_groups()
    return all_groups[:limit]


def get_group_details(group_id: int) -> Optional[dict]:
    """Return full details for a substitution group from the database."""
    return get_substitution_group_detail(group_id)


def print_summary(groups: list[SubstitutionGroup]):
    """Print a human-readable summary of substitution groups."""
    print(f"\n{'='*70}")
    print(f"SUBSTITUTION GROUPS SUMMARY")
    print(f"{'='*70}")
    print(f"Total groups: {len(groups)}")

    consolidation = [g for g in groups if g.has_consolidation_potential]
    print(f"Groups with consolidation potential (>=2 companies): {len(consolidation)}")

    print(f"\n{'-'*70}")
    print(f"TOP 20 CONSOLIDATION OPPORTUNITIES:")
    print(f"{'-'*70}")

    for i, g in enumerate(consolidation[:20], 1):
        print(f"\n  {i}. {g.summary()}")
        companies = sorted(set(m.company_name for m in g.members))
        print(f"     Companies: {', '.join(companies)}")
        if g.suppliers:
            supplier_names = sorted(set(s.supplier_name for s in g.suppliers))
            print(f"     Suppliers: {', '.join(supplier_names)}")
        print(f"     Finished goods affected: {len(g.consuming_product_ids)}")
