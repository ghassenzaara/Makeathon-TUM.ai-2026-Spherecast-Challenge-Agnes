"""
SQLite connection helper with context manager and dict-style row access.
"""

import sqlite3
from contextlib import contextmanager
from backend.config import DB_PATH


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    """Convert SQLite rows to dictionaries keyed by column name."""
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


@contextmanager
def get_connection(as_dict: bool = True):
    """
    Context manager for SQLite connections.

    Args:
        as_dict: If True, rows are returned as dicts. If False, as tuples.

    Yields:
        sqlite3.Connection with optional dict row factory.
    """
    conn = sqlite3.connect(str(DB_PATH))
    if as_dict:
        conn.row_factory = dict_factory
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(as_dict: bool = True):
    """
    Context manager that yields a cursor (auto-commits on success).

    Yields:
        sqlite3.Cursor
    """
    with get_connection(as_dict=as_dict) as conn:
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
