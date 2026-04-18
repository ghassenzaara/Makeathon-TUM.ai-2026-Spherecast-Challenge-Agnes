"""
Agnes Phase 1 Runner — execute the full Phase 1 pipeline.

Usage:
    cd agnes/
    python -m backend.run_phase1 [--no-semantic] [--no-llm] [--force-refresh]
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


async def run_phase1_async(
    use_semantic: bool = True,
    use_llm: bool = True,
    force_refresh: bool = False,
):
    """Run Phase 1: attribute extraction → substance clustering → group building."""
    from backend.db.queries import (
        get_all_raw_materials,
        create_ingredient_card_tables,
        create_substitution_tables,
        create_substitution_group_v2_tables,
    )
    from backend.db.evidence import create_evidence_table
    from backend.phase1_extraction.attribute_extractor import (
        extract_attributes_for_all,
        persist_all,
    )
    from backend.phase1_extraction.substitution_groups import (
        build_substitution_groups,
        print_summary,
    )

    # Ensure tables exist
    create_evidence_table()
    create_ingredient_card_tables()
    create_substitution_tables()
    create_substitution_group_v2_tables()

    # ── Step A: Attribute Extraction ──
    logger.info("=" * 60)
    logger.info("PHASE 1A: Attribute Extraction")
    logger.info("=" * 60)

    raw_materials = get_all_raw_materials()
    logger.info(f"Extracting attributes for {len(raw_materials)} raw materials...")

    drafts = await extract_attributes_for_all(raw_materials, use_llm=use_llm)

    # Stats
    with_substance = sum(1 for d in drafts if d.substance)
    logger.info(
        f"Attribute extraction complete: {with_substance}/{len(drafts)} "
        f"cards have a canonical substance."
    )

    # Persist cards + evidence
    persist_all(drafts)

    # ── Step B: Substitution Grouping ──
    logger.info("")
    groups = build_substitution_groups(
        use_semantic=use_semantic,
        force_refresh_embeddings=force_refresh,
        use_cards=True,
    )

    # Print results
    print_summary(groups)
    return groups


def main():
    parser = argparse.ArgumentParser(description="Run Agnes Phase 1 pipeline")
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="Skip OpenAI embeddings, use exact name matching only",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM fallback for attribute extraction",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force re-generation of embeddings (ignore cache)",
    )
    args = parser.parse_args()

    start = time.time()

    logger.info("Starting Phase 1 pipeline...")
    asyncio.run(run_phase1_async(
        use_semantic=not args.no_semantic,
        use_llm=not args.no_llm,
        force_refresh=args.force_refresh,
    ))

    elapsed = time.time() - start
    logger.info(f"Phase 1 completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
