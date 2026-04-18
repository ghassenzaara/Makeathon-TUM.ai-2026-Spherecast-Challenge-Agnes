"""
Agnes Phase 2 Runner -- execute the full enrichment pipeline.

Usage:
    cd agnes/
    python -m backend.run_phase2 [--skip-iherb] [--skip-suppliers] [--skip-compliance]
"""

import argparse
import asyncio
import logging
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


async def run_phase2(
    skip_iherb: bool = False,
    skip_suppliers: bool = False,
    skip_compliance: bool = False,
):
    """Run the full Phase 2 enrichment pipeline."""
    from backend.db.queries import get_all_finished_goods
    from backend.phase2_enrichment.enrichment_store import (
        create_enrichment_tables,
        get_enrichment_stats,
    )

    logger.info("=" * 60)
    logger.info("PHASE 2: External Enrichment")
    logger.info("=" * 60)

    # Ensure tables exist
    create_enrichment_tables()

    # ── Step 1: iHerb Scraping ──
    if not skip_iherb:
        from backend.phase2_enrichment.iherb_scraper import scrape_all_iherb_products

        logger.info("\n--- Step 1: iHerb Product Scraping ---")
        finished_goods = get_all_finished_goods()
        iherb_results = await scrape_all_iherb_products(finished_goods)
        logger.info(f"iHerb: {len(iherb_results)} products processed")
    else:
        logger.info("\n--- Step 1: iHerb scraping SKIPPED ---")

    # ── Step 2: Supplier Enrichment ──
    if not skip_suppliers:
        from backend.phase2_enrichment.supplier_scraper import enrich_all_suppliers

        logger.info("\n--- Step 2: Supplier Enrichment ---")
        supplier_results = await enrich_all_suppliers()
        logger.info(f"Suppliers: {len(supplier_results)} enriched")
    else:
        logger.info("\n--- Step 2: Supplier enrichment SKIPPED ---")

    # ── Step 3: Compliance Inference ──
    if not skip_compliance:
        from backend.phase2_enrichment.compliance_inferrer import (
            infer_compliance_for_all_products,
        )

        logger.info("\n--- Step 3: Compliance Inference ---")
        compliance_results = await infer_compliance_for_all_products()
        logger.info(f"Compliance: {len(compliance_results)} products inferred")
    else:
        logger.info("\n--- Step 3: Compliance inference SKIPPED ---")

    # ── Summary ──
    stats = get_enrichment_stats()
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
        "--skip-compliance", action="store_true",
        help="Skip compliance inference",
    )
    args = parser.parse_args()

    start = time.time()
    asyncio.run(run_phase2(
        skip_iherb=args.skip_iherb,
        skip_suppliers=args.skip_suppliers,
        skip_compliance=args.skip_compliance,
    ))
    elapsed = time.time() - start
    logger.info(f"\nPhase 2 completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
