"""
Agnes Phase 2 Runner -- execute the full enrichment pipeline.

Usage:
    cd agnes/
    python -m backend.run_phase2 [--skip-iherb] [--skip-suppliers] [--skip-compliance]
"""

import argparse
import asyncio
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


async def run_phase2(
    skip_iherb: bool = False,
    skip_suppliers: bool = False,
    skip_fda: bool = False,
    skip_opencorporates: bool = False,
    skip_compliance: bool = False,
    skip_contradictions: bool = False,
    use_mock: bool = False,
):
    """Run the full Phase 2 enrichment pipeline."""
    from backend.db.queries import (
        get_all_finished_goods,
        get_all_suppliers,
        create_ingredient_compliance_tables,
        create_contradiction_tables,
    )
    from backend.db.evidence import create_evidence_table
    from backend.phase2_enrichment.enrichment_store import (
        create_enrichment_tables,
        get_enrichment_stats,
    )

    logger.info("=" * 60)
    logger.info("PHASE 2: External Enrichment")
    logger.info("=" * 60)

    create_enrichment_tables()
    create_evidence_table()
    create_ingredient_compliance_tables()
    create_contradiction_tables()

    # ── Step 0: Mock data (if requested) ──
    if use_mock:
        from backend.mock_phase2 import mock_iherb, mock_suppliers, mock_compliance
        logger.info("\n--- Step 0: Filling gaps with mock data ---")
        mock_iherb()
        mock_suppliers()
        mock_compliance()

    # ── Step 1: iHerb Product Scraping (Tavily) ──
    if not skip_iherb:
        from backend.phase2_enrichment.iherb_scraper import scrape_all_iherb_products

        logger.info("\n--- Step 1: iHerb Product Scraping (Tavily) ---")
        finished_goods = get_all_finished_goods()
        iherb_results = await scrape_all_iherb_products(finished_goods)
        logger.info(f"iHerb: {len(iherb_results)} products processed")
    else:
        logger.info("\n--- Step 1: iHerb scraping SKIPPED ---")

    # ── Step 2: Supplier Enrichment (Tavily + LLM fallback) ──
    if not skip_suppliers:
        from backend.phase2_enrichment.supplier_scraper import enrich_all_suppliers

        logger.info("\n--- Step 2: Supplier Enrichment (Tavily + LLM fallback) ---")
        supplier_results = await enrich_all_suppliers()
        logger.info(f"Suppliers: {len(supplier_results)} enriched")
    else:
        logger.info("\n--- Step 2: Supplier enrichment SKIPPED ---")

    # ── Step 3: OpenFDA Risk Check ──
    suppliers = None  # lazy-load once if needed by step 3 or 4
    if not skip_fda:
        from backend.phase2_enrichment.openfda_api import check_all_suppliers_fda

        logger.info("\n--- Step 3: OpenFDA Enforcement Risk Check ---")
        suppliers = get_all_suppliers()
        fda_results = await check_all_suppliers_fda(suppliers)
        warnings = sum(1 for r in fda_results if r.get("status") == "Warning")
        logger.info(
            f"FDA: {len(fda_results)} suppliers checked, "
            f"{warnings} with enforcement history"
        )
    else:
        logger.info("\n--- Step 3: FDA check SKIPPED ---")

    # ── Step 4: OpenCorporates Entity Verification ──
    if not skip_opencorporates:
        from backend.phase2_enrichment.opencorporates_api import verify_all_suppliers

        logger.info("\n--- Step 4: OpenCorporates Entity Verification ---")
        if suppliers is None:
            suppliers = get_all_suppliers()
        oc_results = await verify_all_suppliers(suppliers)
        dissolved = sum(1 for r in oc_results if r.get("status") == "Dissolved")
        logger.info(
            f"OpenCorporates: {len(oc_results)} verified, "
            f"{dissolved} dissolved entities"
        )
    else:
        logger.info("\n--- Step 4: Entity verification SKIPPED ---")

    # ── Step 5: Compliance Inference ──
    if not skip_compliance:
        from backend.phase2_enrichment.compliance_inferrer import (
            infer_compliance_for_all_products,
        )

        logger.info("\n--- Step 5: Compliance Inference ---")
        compliance_results = await infer_compliance_for_all_products()
        logger.info(f"Compliance: {len(compliance_results)} products inferred")
    else:
        logger.info("\n--- Step 5: Compliance inference SKIPPED ---")

    # ── Step 6: Contradiction Detection ──
    if not skip_contradictions:
        from backend.phase2_enrichment.contradiction_detector import (
            detect_all_contradictions,
        )

        logger.info("\n--- Step 6: Contradiction Detection ---")
        n_contradictions = detect_all_contradictions()
        logger.info(f"Contradictions: {n_contradictions} found")
    else:
        logger.info("\n--- Step 6: Contradiction detection SKIPPED ---")

    # ── Summary ──
    stats = get_enrichment_stats()
    from backend.db.evidence import count_evidence, get_evidence_stats
    from backend.db.queries import count_contradictions

    logger.info("\n" + "=" * 60)
    logger.info("PHASE 2 COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total enrichment records: {stats['total']}")
    for rec in stats["records"]:
        logger.info(
            f"  {rec['EntityType']}/{rec['DataType']}: "
            f"{rec['Count']} records, "
            f"avg confidence={rec['AvgConfidence']:.2f}"
        )
    logger.info(f"Evidence ledger: {count_evidence()} rows")
    ev_stats = get_evidence_stats()
    for ev in ev_stats:
        logger.info(
            f"  {ev['SourceType']}: {ev['Count']} rows, "
            f"avg conf={ev['AvgConfidence']:.2f}"
        )
    logger.info(f"Contradictions: {count_contradictions()}")


def main():
    parser = argparse.ArgumentParser(description="Run Agnes Phase 2 enrichment pipeline")
    parser.add_argument(
        "--skip-iherb", action="store_true",
        help="Skip iHerb product scraping",
    )
    parser.add_argument(
        "--skip-suppliers", action="store_true",
        help="Skip supplier enrichment",
    )
    parser.add_argument(
        "--skip-fda", action="store_true",
        help="Skip OpenFDA enforcement risk checks",
    )
    parser.add_argument(
        "--skip-opencorporates", action="store_true",
        help="Skip OpenCorporates entity verification",
    )
    parser.add_argument(
        "--skip-compliance", action="store_true",
        help="Skip compliance inference",
    )
    parser.add_argument(
        "--skip-contradictions", action="store_true",
        help="Skip contradiction detection",
    )
    parser.add_argument(
        "--use-mock", action="store_true",
        help="Fill missing data with mocks before enrichment",
    )
    args = parser.parse_args()

    start = time.time()
    asyncio.run(run_phase2(
        skip_iherb=args.skip_iherb,
        skip_suppliers=args.skip_suppliers,
        skip_fda=args.skip_fda,
        skip_opencorporates=args.skip_opencorporates,
        skip_compliance=args.skip_compliance,
        skip_contradictions=args.skip_contradictions,
        use_mock=args.use_mock,
    ))
    elapsed = time.time() - start
    logger.info(f"\nPhase 2 completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
