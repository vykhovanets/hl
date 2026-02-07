"""Test fixtures — redirect DB to temp directory so tests don't touch real data."""

import tempfile
from pathlib import Path

import pytest

import hl.db as db


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    """Redirect DB to a temp directory for each test."""
    db._conn = None
    db.DB_DIR = tmp_path
    db.DB_PATH = tmp_path / "highlights.db"
    yield
    if db._conn is not None:
        db._conn.close()
        db._conn = None
