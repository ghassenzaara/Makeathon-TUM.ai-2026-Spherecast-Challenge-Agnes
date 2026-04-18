"""
Evidence ledger -- per-field provenance for every claim in the pipeline.

Every structured value in Phase 1 / Phase 2 (substance, cert, allergen,
compliance requirement, contradiction detail, ...) is paired with one
Evidence row that records:
    - what the claim is (field_name + value snippet)
    - where it came from (source_type + source_url)
    - the literal text we extracted from (source_snippet)
    - how confident we are (0-1)

Judges can click any number in the UI and get back to the source chunk.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from backend.db.connection import get_cursor


# ──────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────

def create_evidence_table():
    """Create the Evidence ledger + indexes."""
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Evidence (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                Claim TEXT NOT NULL,
                SubjectType TEXT NOT NULL,
                SubjectId INTEGER NOT NULL,
                FieldName TEXT NOT NULL,
                SourceType TEXT NOT NULL,
                SourceUrl TEXT DEFAULT '',
                SourceSnippet TEXT DEFAULT '',
                Confidence REAL NOT NULL DEFAULT 0.5,
                ExtractedAt TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_evidence_subject
            ON Evidence (SubjectType, SubjectId)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_evidence_field
            ON Evidence (FieldName)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_evidence_source_type
            ON Evidence (SourceType)
        """)


def clear_evidence_table():
    """Drop + recreate the Evidence ledger (used on --force-refresh runs)."""
    with get_cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS Evidence")
    create_evidence_table()


# ──────────────────────────────────────────────
# Write
# ──────────────────────────────────────────────

_MAX_SNIPPET_LEN = 500


def record_evidence(
    claim: str,
    subject_type: str,           # "Product" | "Supplier" | "FinishedGood" | "SubstitutionGroup"
    subject_id: int,
    field_name: str,             # dotted path, e.g. "card.substance", "certifications.organic"
    source_type: str,            # "scrape" | "llm-inference" | "llm-group-inference" | "ontology" | "sku-regex" | "mock" | "rule"
    source_url: str = "",
    source_snippet: str = "",
    confidence: float = 0.5,
) -> int:
    """
    Insert a single Evidence row. Returns the new Evidence.Id.

    `source_snippet` is truncated to _MAX_SNIPPET_LEN chars.
    """
    snippet = (source_snippet or "")[:_MAX_SNIPPET_LEN]
    now = datetime.now(timezone.utc).isoformat()
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO Evidence (
                Claim, SubjectType, SubjectId, FieldName,
                SourceType, SourceUrl, SourceSnippet,
                Confidence, ExtractedAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            claim, subject_type, int(subject_id), field_name,
            source_type, source_url or "", snippet,
            float(confidence), now,
        ))
        return cur.lastrowid


# ──────────────────────────────────────────────
# Read
# ──────────────────────────────────────────────

def get_evidence_for(
    subject_type: str,
    subject_id: int,
    field_name: Optional[str] = None,
) -> list[dict]:
    with get_cursor() as cur:
        if field_name:
            cur.execute("""
                SELECT * FROM Evidence
                WHERE SubjectType = ? AND SubjectId = ? AND FieldName = ?
                ORDER BY Confidence DESC, ExtractedAt DESC
            """, (subject_type, int(subject_id), field_name))
        else:
            cur.execute("""
                SELECT * FROM Evidence
                WHERE SubjectType = ? AND SubjectId = ?
                ORDER BY FieldName, Confidence DESC
            """, (subject_type, int(subject_id)))
        return cur.fetchall()


def get_evidence_by_id(evidence_id: int) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM Evidence WHERE Id = ?", (int(evidence_id),))
        return cur.fetchone()


def count_evidence(source_type: Optional[str] = None) -> int:
    with get_cursor() as cur:
        if source_type:
            cur.execute("SELECT COUNT(*) AS c FROM Evidence WHERE SourceType = ?",
                        (source_type,))
        else:
            cur.execute("SELECT COUNT(*) AS c FROM Evidence")
        return cur.fetchone()["c"]


def get_evidence_stats() -> list[dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT SourceType, COUNT(*) AS Count, AVG(Confidence) AS AvgConfidence
            FROM Evidence
            GROUP BY SourceType
            ORDER BY Count DESC
        """)
        return cur.fetchall()
