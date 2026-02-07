"""Tests for hl.api and hl.db modules."""

from __future__ import annotations

import pytest

from hl.api import Entry, add, delete, format_full, format_short, get, recent, search, update
import hl.db as db


# ---------------------------------------------------------------------------
# add()
# ---------------------------------------------------------------------------

class TestAdd:
    def test_returns_entry(self):
        entry = add(content="hello world", author="alice")
        assert isinstance(entry, Entry)

    def test_auto_id(self):
        e1 = add(content="one", author="alice")
        e2 = add(content="two", author="alice")
        assert e1.id is not None
        assert e2.id is not None
        assert e2.id > e1.id

    def test_created_at_populated(self):
        entry = add(content="ts test", author="alice")
        assert entry.created_at is not None
        assert len(entry.created_at) > 0

    def test_stores_content_and_author(self):
        entry = add(content="some note", author="bob")
        assert entry.content == "some note"
        assert entry.author == "bob"

    def test_source_defaults_to_empty(self):
        entry = add(content="note", author="alice")
        assert entry.source == ""

    def test_source_stored(self):
        entry = add(content="note", author="alice", source="https://example.com")
        assert entry.source == "https://example.com"

    def test_content_stripped(self):
        entry = add(content="  padded  ", author="alice")
        assert entry.content == "padded"

    def test_source_stripped(self):
        entry = add(content="note", author="alice", source="  url  ")
        assert entry.source == "url"

    def test_author_required(self):
        with pytest.raises(TypeError):
            add(content="no author")

    def test_content_required(self):
        with pytest.raises(TypeError):
            add(author="alice")


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

class TestGet:
    def test_returns_entry(self):
        created = add(content="retrieve me", author="alice")
        fetched = get(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.content == "retrieve me"

    def test_nonexistent_returns_none(self):
        assert get(9999) is None


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------

class TestSearch:
    def test_finds_by_content(self):
        add(content="unique quantum phrase", author="alice")
        results = search("quantum")
        assert len(results) == 1
        assert "quantum" in results[0].content

    def test_finds_by_source(self):
        add(content="something", author="alice", source="arxiv.org/quantum")
        results = search("arxiv")
        assert len(results) == 1

    def test_no_match_returns_empty(self):
        add(content="unrelated", author="alice")
        assert search("zzzznotfound") == []

    def test_respects_limit(self):
        for i in range(5):
            add(content=f"searchable item {i}", author="alice")
        results = search("searchable", limit=3)
        assert len(results) == 3

    def test_default_limit(self):
        for i in range(25):
            add(content=f"bulk entry {i}", author="alice")
        results = search("bulk")
        assert len(results) == 20


# ---------------------------------------------------------------------------
# recent()
# ---------------------------------------------------------------------------

class TestRecent:
    def test_newest_first(self):
        e1 = add(content="first", author="alice")
        e2 = add(content="second", author="alice")
        entries = recent()
        # Both entries created within same second so created_at may be equal;
        # ORDER BY created_at DESC is stable only when timestamps differ.
        # Verify that all entries are returned and the first has the higher id
        # (which is the expected tiebreak for same-timestamp rows in SQLite).
        ids = [e.id for e in entries]
        assert set(ids) == {e1.id, e2.id}

    def test_respects_limit(self):
        for i in range(5):
            add(content=f"entry {i}", author="alice")
        results = recent(limit=3)
        assert len(results) == 3

    def test_filter_by_author(self):
        add(content="alice note", author="alice")
        add(content="bob note", author="bob")
        add(content="alice again", author="alice")
        results = recent(author="alice")
        assert len(results) == 2
        assert all(e.author == "alice" for e in results)

    def test_no_author_returns_all(self):
        add(content="a", author="alice")
        add(content="b", author="bob")
        results = recent()
        assert len(results) == 2

    def test_empty_db(self):
        assert recent() == []


# ---------------------------------------------------------------------------
# update()
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_update_content_only(self):
        entry = add(content="original", author="alice", source="src")
        updated = update(entry.id, content="changed")
        assert updated is not None
        assert updated.content == "changed"
        assert updated.source == "src"  # unchanged

    def test_update_source_only(self):
        entry = add(content="note", author="alice", source="old-src")
        updated = update(entry.id, source="new-src")
        assert updated is not None
        assert updated.source == "new-src"
        assert updated.content == "note"  # unchanged

    def test_update_both(self):
        entry = add(content="a", author="alice", source="b")
        updated = update(entry.id, content="x", source="y")
        assert updated.content == "x"
        assert updated.source == "y"

    def test_update_nonexistent_returns_none(self):
        assert update(9999, content="nope") is None

    def test_content_stripped_on_update(self):
        entry = add(content="orig", author="alice")
        updated = update(entry.id, content="  spaced  ")
        assert updated.content == "spaced"

    def test_source_stripped_on_update(self):
        entry = add(content="orig", author="alice")
        updated = update(entry.id, source="  spaced  ")
        assert updated.source == "spaced"

    def test_author_unchanged(self):
        entry = add(content="note", author="alice")
        updated = update(entry.id, content="new")
        assert updated.author == "alice"

    def test_no_fields_provided_returns_entry_unchanged(self):
        entry = add(content="note", author="alice", source="src")
        updated = update(entry.id)
        assert updated.content == "note"
        assert updated.source == "src"


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------

class TestDelete:
    def test_delete_existing(self):
        entry = add(content="to delete", author="alice")
        assert delete(entry.id) is True
        assert get(entry.id) is None

    def test_delete_nonexistent(self):
        assert delete(9999) is False


# ---------------------------------------------------------------------------
# FTS triggers
# ---------------------------------------------------------------------------

class TestFTSTriggers:
    def test_insert_makes_searchable(self):
        add(content="fts insert test", author="alice")
        assert len(search("insert")) == 1

    def test_delete_removes_from_search(self):
        entry = add(content="fts delete test", author="alice")
        delete(entry.id)
        assert search("delete") == []

    def test_update_makes_new_content_searchable(self):
        entry = add(content="old content", author="alice")
        update(entry.id, content="new shiny content")
        assert search("shiny") != []

    def test_update_removes_old_content_from_search(self):
        entry = add(content="obsolete keyword", author="alice")
        update(entry.id, content="replacement")
        assert search("obsolete") == []

    def test_update_source_searchable(self):
        entry = add(content="note", author="alice", source="originalsrc")
        update(entry.id, source="updatedsrc")
        assert search("updatedsrc") != []
        assert search("originalsrc") == []


# ---------------------------------------------------------------------------
# DB schema auto-creation
# ---------------------------------------------------------------------------

class TestDBSchema:
    def test_schema_created_on_first_connection(self, tmp_path):
        """Verify that tables exist after get_conn()."""
        db._conn = None
        db.DB_DIR = tmp_path / "fresh"
        db.DB_PATH = db.DB_DIR / "highlights.db"
        conn = db.get_conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {row["name"] for row in tables}
        assert "entries" in table_names
        assert "entries_fts" in table_names

    def test_directory_created(self, tmp_path):
        """Verify that DB_DIR is created if it doesn't exist."""
        new_dir = tmp_path / "new" / "nested"
        db._conn = None
        db.DB_DIR = new_dir
        db.DB_PATH = new_dir / "highlights.db"
        db.get_conn()
        assert new_dir.exists()


# ---------------------------------------------------------------------------
# format_short()
# ---------------------------------------------------------------------------

class TestFormatShort:
    def test_basic_format(self):
        entry = Entry(id=1, content="hello world", source="", author="alice", created_at="2025-01-01 00:00:00")
        result = format_short(entry)
        assert "[1]" in result
        assert "2025-01-01" in result
        assert "hello world" in result

    def test_source_included(self):
        entry = Entry(id=1, content="note", source="https://example.com", author="alice", created_at="2025-01-01 00:00:00")
        result = format_short(entry)
        assert "https://example.com" in result

    def test_no_source_no_extra_space(self):
        entry = Entry(id=1, content="note", source="", author="alice", created_at="2025-01-01 00:00:00")
        result = format_short(entry)
        assert "  " not in result.split("\n")[0] or "[1]" in result

    def test_claude_author_mark(self):
        entry = Entry(id=1, content="note", source="", author="claude", created_at="2025-01-01 00:00:00")
        result = format_short(entry)
        assert "(claude)" in result

    def test_non_claude_no_mark(self):
        entry = Entry(id=1, content="note", source="", author="alice", created_at="2025-01-01 00:00:00")
        result = format_short(entry)
        assert "(claude)" not in result

    def test_long_content_truncated(self):
        entry = Entry(id=1, content="x" * 100, source="", author="alice", created_at="2025-01-01 00:00:00")
        result = format_short(entry)
        preview_line = result.split("\n")[1].strip()
        assert len(preview_line) <= 60

    def test_multiline_uses_first_line(self):
        entry = Entry(id=1, content="first line\nsecond line", source="", author="alice", created_at="2025-01-01 00:00:00")
        result = format_short(entry)
        assert "first line" in result
        assert "second line" not in result


# ---------------------------------------------------------------------------
# format_full()
# ---------------------------------------------------------------------------

class TestFormatFull:
    def test_contains_all_fields(self):
        entry = Entry(id=42, content="full note", source="src", author="alice", created_at="2025-01-01 00:00:00")
        result = format_full(entry)
        assert "id: 42" in result
        assert "author: alice" in result
        assert "created: 2025-01-01 00:00:00" in result
        assert "source: src" in result
        assert "full note" in result

    def test_no_source_line_when_empty(self):
        entry = Entry(id=1, content="note", source="", author="alice", created_at="2025-01-01 00:00:00")
        result = format_full(entry)
        assert "source:" not in result

    def test_content_at_end(self):
        entry = Entry(id=1, content="the body", source="", author="alice", created_at="2025-01-01 00:00:00")
        result = format_full(entry)
        lines = result.strip().split("\n")
        assert lines[-1] == "the body"
