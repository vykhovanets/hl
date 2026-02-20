"""Tests for editor locking — prevent concurrent edits of the same entry."""

import os
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from hl import api, lock
from hl.cli import app

runner = CliRunner()


def test_acquire_creates_lockfile():
    lock.acquire(42)
    lp = lock._lock_path(42)
    assert lp.exists()
    assert lp.read_text().strip() == str(os.getpid())
    lock.release(42)


def test_release_removes_lockfile():
    lock.acquire(7)
    lock.release(7)
    assert not lock._lock_path(7).exists()


def test_release_idempotent():
    lock.release(99)  # no lock exists — should not raise


def test_acquire_blocks_when_held():
    lock.acquire(1)
    with pytest.raises(lock.EditorLockError) as exc_info:
        lock.acquire(1)
    assert exc_info.value.entry_id == 1
    lock.release(1)


def test_stale_lock_is_overwritten():
    """A lock whose PID is dead should be treated as stale."""
    lp = lock._lock_path(5)
    lp.parent.mkdir(parents=True, exist_ok=True)
    lp.write_text("999999999")  # PID that almost certainly doesn't exist

    # Should succeed — stale lock cleared
    lock.acquire(5)
    assert lp.read_text().strip() == str(os.getpid())
    lock.release(5)


def test_corrupted_lock_is_overwritten():
    """A lockfile with non-integer content should be treated as stale."""
    lp = lock._lock_path(6)
    lp.parent.mkdir(parents=True, exist_ok=True)
    lp.write_text("not-a-pid")

    lock.acquire(6)
    assert lp.read_text().strip() == str(os.getpid())
    lock.release(6)


# --- CLI integration ---


def test_ed_rejects_concurrent_edit():
    """Second `ed` on the same entry should fail with a clear message."""
    api.add(content="some text", author="user")

    def fake_editor(initial="", on_save=None):
        # While "in the editor", try to edit the same entry again
        result = runner.invoke(app, ["ed", "1"])
        assert result.exit_code == 1
        assert "already being edited" in result.output
        return initial  # no changes

    with patch("hl.cli._open_editor", side_effect=fake_editor):
        result = runner.invoke(app, ["ed", "1"])

    assert result.exit_code == 0


def test_ed_releases_lock_after_edit():
    """Lock should be gone after ed finishes."""
    api.add(content="hello", author="user")

    with patch("hl.cli._open_editor", return_value="updated"):
        runner.invoke(app, ["ed", "1"])

    assert not lock._lock_path(1).exists()


def test_ed_releases_lock_on_no_changes():
    """Lock released even when no changes are made."""
    api.add(content="unchanged", author="user")

    with patch("hl.cli._open_editor", return_value="unchanged"):
        runner.invoke(app, ["ed", "1"])

    assert not lock._lock_path(1).exists()


def test_different_entries_can_edit_concurrently():
    """Locks are per-entry — different entries don't block each other."""
    lock.acquire(1)
    lock.acquire(2)  # should not raise
    lock.release(1)
    lock.release(2)
