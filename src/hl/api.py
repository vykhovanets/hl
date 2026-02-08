"""Core API — shared between CLI and MCP."""

from __future__ import annotations

from dataclasses import dataclass

from .db import get_conn


# =============================================================================
# Entry dataclass
# =============================================================================


@dataclass
class Entry:
    id: int
    content: str
    source: str
    author: str
    created_at: str


def _row_to_entry(row) -> Entry:
    return Entry(**dict(row))


# =============================================================================
# CRUD operations
# =============================================================================


def add(*, content: str, author: str, source: str = "") -> Entry:
    """Add a new entry. Caller must specify author."""
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO entries (content, source, author) VALUES (?, ?, ?)",
        (content.strip(), source.strip(), author),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM entries WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_entry(row)


def search(query: str, *, limit: int = 20) -> list[Entry]:
    """Full-text search across content and source."""
    conn = get_conn()
    safe_query = '"' + query.replace('"', '""') + '"'
    rows = conn.execute(
        """SELECT e.* FROM entries e
           JOIN entries_fts f ON e.id = f.rowid
           WHERE entries_fts MATCH ?
           ORDER BY f.rank
           LIMIT ?""",
        (safe_query, limit),
    ).fetchall()
    return [_row_to_entry(r) for r in rows]


def recent(*, limit: int = 20, author: str | None = None) -> list[Entry]:
    """List recent entries, optionally filtered by author."""
    conn = get_conn()
    sql = "SELECT * FROM entries"
    params: list = []
    if author:
        sql += " WHERE author = ?"
        params.append(author)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_entry(r) for r in rows]


def get(entry_id: int) -> Entry | None:
    """Get a single entry by ID."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    return _row_to_entry(row) if row else None


def update(entry_id: int, *, content: str | None = None, source: str | None = None) -> Entry | None:
    """Update an existing entry."""
    entry = get(entry_id)
    if entry is None:
        return None

    conn = get_conn()
    conn.execute(
        "UPDATE entries SET content = ?, source = ? WHERE id = ?",
        (
            content.strip() if content is not None else entry.content,
            source.strip() if source is not None else entry.source,
            entry_id,
        ),
    )
    conn.commit()
    return get(entry_id)


def delete(entry_id: int) -> bool:
    """Delete an entry by ID."""
    conn = get_conn()
    cur = conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()
    return cur.rowcount > 0


# =============================================================================
# Formatting
# =============================================================================


def format_short(entry: Entry, *, color: bool = True) -> str:
    """One-line summary for list views."""
    source_str = f"  {entry.source}" if entry.source else ""
    author_mark = " (claude)" if entry.author == "claude" else ""
    preview = entry.content.split("\n")[0][:60]
    if color:
        import typer

        id_part = typer.style(f"[{entry.id}]", bold=True)
        meta = typer.style(f"{entry.created_at}{author_mark}{source_str}", dim=True)
        return f"{id_part} {meta}\n     {preview}"
    return f"[{entry.id}] {entry.created_at}{author_mark}{source_str}\n     {preview}"


def format_full(entry: Entry) -> str:
    """Full display of an entry."""
    lines = [
        f"id: {entry.id}",
        f"author: {entry.author}",
        f"created: {entry.created_at}",
    ]
    if entry.source:
        lines.append(f"source: {entry.source}")
    lines += ["", entry.content]
    return "\n".join(lines)
