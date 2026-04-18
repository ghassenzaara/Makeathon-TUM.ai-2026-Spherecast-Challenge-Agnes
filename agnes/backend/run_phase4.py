"""
Agnes Phase 4 Runner -- Output & Evidence Trail.

Builds an evidence trail (cited explanation) for every persisted Phase 3
sourcing proposal, prints the top 5, and dumps the full set to JSON.
Also (re)builds the retrieval index used by the chat agent.

Usage:
    cd agnes/
    python -m backend.run_phase4 [--rebuild-index] [--no-index]
"""

from __future__ import annotations

import argparse
import json
import logging
import time

from backend.config import DATA_DIR
from backend.phase4_output.evidence_trail_builder import build_all_evidence_trails
from backend.phase4_output.retriever import build_or_load_index


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


_OUT_PATH = DATA_DIR / "phase4_evidence_trails.json"


def run_phase4(rebuild_index: bool = False, build_index: bool = True) -> list[dict]:
    logger.info("=" * 60)
    logger.info("PHASE 4: Output & Evidence Trail")
    logger.info("=" * 60)

    trails = build_all_evidence_trails()
    logger.info(f"Built evidence trails for {len(trails)} proposals.")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _OUT_PATH.write_text(
        json.dumps(trails, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"Wrote {_OUT_PATH}")

    if build_index:
        idx = build_or_load_index(force_rebuild=rebuild_index)
        logger.info(f"Retrieval index ready ({len(idx.docs)} docs, backend={idx.backend}).")

    print("\n" + "=" * 60)
    print("TOP 5 EVIDENCE TRAILS")
    print("=" * 60)
    for i, trail in enumerate(trails[:5], 1):
        print(f"\n{i}. {trail['headline']}")
        print(f"   verification: {trail['verification_summary']}")
        for claim in trail["claims"]:
            cite_count = len(claim["citations"])
            print(f"   - [{claim['status']}] {claim['claim']} ({cite_count} citation(s))")
            for cite in claim["citations"][:1]:
                src = cite.get("url") or "(no URL)"
                print(f"       -> {cite['label']}: {src}")
        if trail["risks"]:
            print(f"   risks: {', '.join(trail['risks'])}")

    return trails


def main():
    parser = argparse.ArgumentParser(description="Run Agnes Phase 4 pipeline")
    parser.add_argument("--rebuild-index", action="store_true",
                        help="Force-rebuild the retrieval embedding index")
    parser.add_argument("--no-index", action="store_true",
                        help="Skip building the retrieval index")
    args = parser.parse_args()

    start = time.time()
    run_phase4(rebuild_index=args.rebuild_index, build_index=not args.no_index)
    logger.info(f"\nPhase 4 completed in {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
