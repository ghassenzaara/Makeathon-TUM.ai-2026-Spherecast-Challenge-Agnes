"""
Agnes Phase 1 Runner — execute the full Phase 1 pipeline.

Usage:
    cd agnes/
    python -m backend.run_phase1 [--no-semantic] [--force-refresh]
"""

import argparse
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


def main():
    parser = argparse.ArgumentParser(description="Run Agnes Phase 1 pipeline")
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="Skip OpenAI embeddings, use exact name matching only",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force re-generation of embeddings (ignore cache)",
    )
    args = parser.parse_args()

    from backend.phase1_extraction.substitution_groups import (
        build_substitution_groups,
        print_summary,
    )

    start = time.time()

    logger.info("Starting Phase 1 pipeline...")
    groups = build_substitution_groups(
        use_semantic=not args.no_semantic,
        force_refresh_embeddings=args.force_refresh,
    )

    elapsed = time.time() - start
    logger.info(f"Phase 1 completed in {elapsed:.1f}s")

    # Print results
    print_summary(groups)


if __name__ == "__main__":
    main()
