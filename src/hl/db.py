"""Database layer — SQLite + FTS5 for highlight storage."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_DIR = Path.home() / ".local" / "state" / "hl"
DB_PATH = DB_DIR / "highlights.db"

_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    """Get or create the database connection."""
    global _conn
    if _conn is not None:
        return _conn

    DB_DIR.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(str(DB_PATH))
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entries (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            content    TEXT NOT NULL,
            source     TEXT NOT NULL DEFAULT '',
            author     TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
            content, source,
            content='entries',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
            INSERT INTO entries_fts(rowid, content, source)
            VALUES (new.id, new.content, new.source);
        END;

        CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
            INSERT INTO entries_fts(entries_fts, rowid, content, source)
            VALUES ('delete', old.id, old.content, old.source);
        END;

        CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
            INSERT INTO entries_fts(entries_fts, rowid, content, source)
            VALUES ('delete', old.id, old.content, old.source);
            INSERT INTO entries_fts(rowid, content, source)
            VALUES (new.id, new.content, new.source);
        END;
    """)
