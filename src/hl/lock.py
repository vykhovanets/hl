"""Editor lock — prevents concurrent editing of the same entry.

Uses PID-based lockfiles in the state directory.  A lock is considered
stale when the owning PID is no longer alive, so editor crashes don't
leave permanent locks behind.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import db


class EditorLockError(Exception):
    """Raised when an entry is already being edited by another process."""

    def __init__(self, entry_id: int, pid: int) -> None:
        self.entry_id = entry_id
        self.pid = pid
        super().__init__(
            f"Entry #{entry_id} is already being edited (pid {pid})"
        )


def _lock_dir() -> Path:
    # Read db.DB_DIR at call time so test overrides work.
    return db.DB_DIR / "locks"


def _lock_path(entry_id: int) -> Path:
    return _lock_dir() / f"{entry_id}.lock"


def _pid_alive(pid: int) -> bool:
    """Check whether *pid* refers to a running process."""
    try:
        os.kill(pid, 0)  # signal 0 = existence check, nothing sent
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but belongs to another user.
        return True


def acquire(entry_id: int) -> None:
    """Acquire an editor lock.  Raises *EditorLockError* if held."""
    lock = _lock_path(entry_id)
    lock.parent.mkdir(parents=True, exist_ok=True)

    if lock.exists():
        try:
            pid = int(lock.read_text().strip())
            if _pid_alive(pid):
                raise EditorLockError(entry_id, pid)
        except (ValueError, OSError):
            pass  # corrupted / unreadable — treat as stale

    lock.write_text(str(os.getpid()))


def release(entry_id: int) -> None:
    """Release an editor lock (idempotent)."""
    _lock_path(entry_id).unlink(missing_ok=True)
