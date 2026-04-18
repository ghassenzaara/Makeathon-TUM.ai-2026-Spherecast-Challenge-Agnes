"""
Enrichment Store -- persists all externally-gathered enrichment data.

Central storage for scraped / inferred data from Phase 2:
  - iHerb product info (certifications, ingredients, prices)
  - Supplier info (location, certifications, catalog)
  - Compliance requirements inferred by LLM

Uses both SQLite (structured queries) and JSON file cache (raw payloads).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.config import ENRICHMENT_CACHE_DIR
from backend.db.connection import get_cursor

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# SQLite table setup
# ──────────────────────────────────────────────

def create_enrichment_tables():
    """Create the enrichment storage tables if they don't exist."""
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Enrichment (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                EntityType TEXT NOT NULL,
                EntityId TEXT NOT NULL,
                DataType TEXT NOT NULL,
                DataJson TEXT NOT NULL,
                SourceUrl TEXT,
                ScrapedAt TEXT NOT NULL,
                Confidence REAL DEFAULT 0.5,
                UNIQUE(EntityType, EntityId, DataType)
            )
        """)


def clear_enrichment_tables():
    """Drop and recreate enrichment tables."""
    with get_cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS Enrichment")
    create_enrichment_tables()


# ──────────────────────────────────────────────
# Write helpers
# ──────────────────────────────────────────────

def store_enrichment(
    entity_type: str,
    entity_id: str,
    data_type: str,
    data: dict,
    source_url: str = "",
    confidence: float = 0.5,
):
    """
    Store enrichment data for an entity (upsert).

    Args:
        entity_type: 'product', 'supplier', or 'ingredient'
        entity_id:   Product ID, supplier ID, or ingredient name
        data_type:   'iherb_scrape', 'supplier_info', 'compliance_requirements',
                     'llm_inference', etc.
        data:        Dict of enrichment data
        source_url:  Where the data came from (for evidence trail)
        confidence:  0.0-1.0 reliability of this data
    """
    now = datetime.now(timezone.utc).isoformat()
    data_json = json.dumps(data, ensure_ascii=False)

    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO Enrichment
                (EntityType, EntityId, DataType, DataJson, SourceUrl, ScrapedAt, Confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(EntityType, EntityId, DataType)
            DO UPDATE SET
                DataJson = excluded.DataJson,
                SourceUrl = excluded.SourceUrl,
                ScrapedAt = excluded.ScrapedAt,
                Confidence = excluded.Confidence
        """, (entity_type, str(entity_id), data_type, data_json, source_url, now, confidence))

    logger.debug(
        f"Stored enrichment: {entity_type}/{entity_id}/{data_type} "
        f"(confidence={confidence:.2f})"
    )


def store_product_scrape(product_id: int, data: dict, source_url: str = ""):
    """Store scraped product data (iHerb, Amazon, etc.)."""
    store_enrichment(
        entity_type="product",
        entity_id=str(product_id),
        data_type="product_scrape",
        data=data,
        source_url=source_url,
        confidence=0.9,  # Scraped data is high confidence
    )


def store_supplier_info(supplier_id: int, data: dict, source_url: str = ""):
    """Store supplier enrichment data."""
    store_enrichment(
        entity_type="supplier",
        entity_id=str(supplier_id),
        data_type="supplier_info",
        data=data,
        source_url=source_url,
        confidence=0.7,  # LLM-inferred supplier data is medium-high
    )


def store_compliance_requirements(product_id: int, data: dict):
    """Store LLM-inferred compliance requirements for a finished good."""
    store_enrichment(
        entity_type="product",
        entity_id=str(product_id),
        data_type="compliance_requirements",
        data=data,
        source_url="",
        confidence=data.get("confidence", 50) / 100.0,
    )


# ──────────────────────────────────────────────
# Read helpers
# ──────────────────────────────────────────────

def get_enrichment(
    entity_type: str,
    entity_id: str,
    data_type: str,
) -> Optional[dict]:
    """Retrieve a single enrichment record."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT DataJson, SourceUrl, ScrapedAt, Confidence
            FROM Enrichment
            WHERE EntityType = ? AND EntityId = ? AND DataType = ?
        """, (entity_type, str(entity_id), data_type))
        row = cur.fetchone()

    if not row:
        return None

    result = json.loads(row["DataJson"])
    result["_meta"] = {
        "source_url": row["SourceUrl"],
        "scraped_at": row["ScrapedAt"],
        "confidence": row["Confidence"],
    }
    return result


def get_product_scrape(product_id: int) -> Optional[dict]:
    """Get scraped product data."""
    return get_enrichment("product", str(product_id), "product_scrape")


def get_supplier_info(supplier_id: int) -> Optional[dict]:
    """Get supplier enrichment data."""
    return get_enrichment("supplier", str(supplier_id), "supplier_info")


def get_compliance_requirements(product_id: int) -> Optional[dict]:
    """Get LLM-inferred compliance requirements for a finished good."""
    return get_enrichment("product", str(product_id), "compliance_requirements")


def get_fda_risk(supplier_id: int) -> Optional[dict]:
    """Get OpenFDA enforcement risk record for a supplier."""
    return get_enrichment("supplier", str(supplier_id), "fda_risk")


def get_entity_verification(supplier_id: int) -> Optional[dict]:
    """Get OpenCorporates entity verification record for a supplier."""
    return get_enrichment("supplier", str(supplier_id), "entity_verification")


def get_certifications_for_supplier(supplier_id: int) -> list[str]:
    """Get list of certifications for a supplier."""
    info = get_supplier_info(supplier_id)
    if info:
        return info.get("certifications", [])
    return []


def get_all_enrichments_for_entity(
    entity_type: str, entity_id: str
) -> list[dict]:
    """Get all enrichment records for a given entity."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT DataType, DataJson, SourceUrl, ScrapedAt, Confidence
            FROM Enrichment
            WHERE EntityType = ? AND EntityId = ?
        """, (entity_type, str(entity_id)))
        rows = cur.fetchall()

    results = []
    for row in rows:
        data = json.loads(row["DataJson"])
        data["_data_type"] = row["DataType"]
        data["_meta"] = {
            "source_url": row["SourceUrl"],
            "scraped_at": row["ScrapedAt"],
            "confidence": row["Confidence"],
        }
        results.append(data)
    return results


def get_enrichment_stats() -> dict:
    """Return summary statistics about enrichment data."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT EntityType, DataType, COUNT(*) as Count,
                   AVG(Confidence) as AvgConfidence
            FROM Enrichment
            GROUP BY EntityType, DataType
        """)
        rows = cur.fetchall()

    return {
        "records": rows,
        "total": sum(r["Count"] for r in rows),
    }


# ──────────────────────────────────────────────
# JSON file cache (for raw scrape payloads)
# ──────────────────────────────────────────────

def _cache_path(category: str, key: str) -> Path:
    """Get the file path for a cached item."""
    cache_dir = ENRICHMENT_CACHE_DIR / category
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{key}.json"


def cache_get(category: str, key: str) -> Optional[dict]:
    """Read from file cache."""
    path = _cache_path(category, key)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def cache_set(category: str, key: str, data: dict):
    """Write to file cache."""
    path = _cache_path(category, key)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
