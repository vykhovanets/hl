"""CLI — thin wrapper over core API with $EDITOR integration."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
import termios
import time
import tty
from collections.abc import Callable
from pathlib import Path

import typer

from . import api
from . import lock

app = typer.Typer(no_args_is_help=True, add_completion=False)


# =============================================================================
# Helpers
# =============================================================================


def _get_or_exit(entry_id: int) -> api.Entry:
    """Fetch entry by ID or exit with error."""
    entry = api.get(entry_id)
    if not entry:
        typer.echo(f"No entry with id {entry_id}")
        raise typer.Exit(1)
    return entry


GUI_EDITORS_WAIT_FLAG = {
    "subl": "-w",
    "code": "--wait",
    "mate": "-w",
    "atom": "--wait",
    "zed": "--wait",
}


def _load_config() -> dict[str, str]:
    """Load key=value pairs from ~/.config/hl/hl.conf (respects XDG_CONFIG_HOME)."""
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    conf = base / "hl" / "hl.conf"
    if not conf.is_file():
        return {}
    result: dict[str, str] = {}
    for line in conf.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and value:
            result[key] = value
    return result


def _editor_cmd() -> list[str]:
    """Build editor command, adding --wait for GUI editors."""
    editor = _load_config().get("editor") or os.environ.get("EDITOR", os.environ.get("VISUAL", "nano"))
    parts = shlex.split(editor)
    basename = Path(parts[0]).stem
    wait_flag = GUI_EDITORS_WAIT_FLAG.get(basename)
    if wait_flag and wait_flag not in parts:
        parts.append(wait_flag)
    return parts


def _pick(items: list[str], visible: int = 5) -> int | None:
    """Arrow/j/k picker. Returns selected index or None on q/Esc."""
    if not items:
        return None
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    n = len(items)
    cur = 0
    top = 0
    vis = min(visible, n)

    def render(first: bool = False) -> None:
        nonlocal top
        if cur < top:
            top = cur
        elif cur >= top + vis:
            top = cur - vis + 1
        if not first:
            sys.stdout.write(f"\033[{vis}A")
        for i in range(top, top + vis):
            marker = ">" if i == cur else " "
            sys.stdout.write(f"\r\033[K {marker} {items[i]}\n")
        sys.stdout.flush()

    def readkey() -> str:
        b = os.read(fd, 1)
        if b == b"\x1b":
            b2 = os.read(fd, 1)
            if b2 == b"[":
                b3 = os.read(fd, 1)
                return {"A": "up", "B": "down"}.get(b3.decode(), "")
            return "esc"
        return {"\r": "enter", "\x03": "ctrl-c"}.get(b.decode("utf-8", "ignore"), b.decode("utf-8", "ignore"))

    tty.setraw(fd)
    try:
        render(first=True)
        while True:
            key = readkey()
            if key in ("k", "up") and cur > 0:
                cur -= 1
                render()
            elif key in ("j", "down") and cur < n - 1:
                cur += 1
                render()
            elif key == "enter":
                return cur
            elif key in ("q", "esc", "ctrl-c"):
                return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _open_editor(
    initial: str = "",
    on_save: Callable[[str], None] | None = None,
) -> str | None:
    """Open $EDITOR, return content or None if empty.

    If *on_save* is provided, the temp file is polled every second while the
    editor is still running.  Whenever the file's mtime changes and the content
    differs from the last known version, *on_save(new_content)* is called so
    the caller can persist intermediate saves (e.g. to the database).
    """
    cmd = _editor_cmd()
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write(initial)
        tmp_path = f.name

    try:
        proc = subprocess.Popen([*cmd, tmp_path])

        if on_save:
            last_mtime = os.path.getmtime(tmp_path)
            last_content = initial
            while proc.poll() is None:
                time.sleep(1)
                try:
                    mtime = os.path.getmtime(tmp_path)
                    if mtime != last_mtime:
                        last_mtime = mtime
                        content = Path(tmp_path).read_text().strip()
                        if content and content != last_content:
                            on_save(content)
                            last_content = content
                except OSError:
                    pass
        else:
            proc.wait()

        content = Path(tmp_path).read_text().strip()
        return content if content else None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# =============================================================================
# Commands
# =============================================================================


@app.command()
def add(
    source: str = typer.Option("", "-s", "--source", help="Where this came from (URL, book, etc)"),
) -> None:
    """Open editor to capture a highlight."""
    content = _open_editor()
    if content is None:
        typer.echo("Aborted — empty.")
        raise typer.Exit(1)

    entry = api.add(content=content, author="user", source=source)
    typer.echo(f"Saved #{entry.id}")


@app.command()
def search(
    query: list[str] = typer.Argument(..., help="Search terms"),
    limit: int = typer.Option(20, "-n", "--limit"),
) -> None:
    """Search highlights."""
    results = api.search(" ".join(query), limit=limit)
    if not results:
        typer.echo("No results.")
        raise typer.Exit(1)

    for e in results:
        typer.echo(api.format_short(e))
        typer.echo()


@app.command()
def show(
    entry_id: int = typer.Argument(..., help="Entry ID"),
) -> None:
    """Show full highlight."""
    entry = _get_or_exit(entry_id)
    typer.echo(api.format_full(entry))


@app.command()
def ed(
    entry_id: int | None = typer.Argument(None, help="Entry ID (picker if omitted)"),
) -> None:
    """Edit an existing highlight in $EDITOR."""
    if entry_id is None:
        entries = api.recent(limit=50)
        if not entries:
            typer.echo("No highlights yet.")
            raise typer.Exit(0)
        lines = [
            typer.style(f"[{e.id}]", bold=True)
            + " "
            + typer.style(e.created_at, dim=True)
            + " | "
            + e.content.split(chr(10))[0][:60]
            for e in entries
        ]
        idx = _pick(lines)
        if idx is None:
            raise typer.Exit(0)
        entry = entries[idx]
    else:
        entry = _get_or_exit(entry_id)

    try:
        lock.acquire(entry.id)
    except lock.EditorLockError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1)

    try:
        def _persist(text: str) -> None:
            api.update(entry.id, content=text)

        content = _open_editor(entry.content, on_save=_persist)
        if content is None or content == entry.content:
            typer.echo("No changes.")
            raise typer.Exit(0)

        updated = api.update(entry.id, content=content)
        if updated:
            typer.echo(f"Updated #{updated.id}")
    finally:
        lock.release(entry.id)


@app.command()
def ls(
    limit: int = typer.Option(20, "-n", "--limit"),
    author: str = typer.Option(None, "-a", "--author", help="Filter: 'user' or 'claude'"),
) -> None:
    """List recent highlights."""
    results = api.recent(limit=limit, author=author)
    if not results:
        typer.echo("No highlights yet.")
        raise typer.Exit(0)

    for e in results:
        typer.echo(api.format_short(e))


@app.command()
def rm(
    entry_id: int = typer.Argument(..., help="Entry ID"),
    force: bool = typer.Option(False, "-f", "--force", help="Skip confirmation"),
) -> None:
    """Delete a highlight."""
    entry = _get_or_exit(entry_id)

    if not force:
        typer.echo(api.format_short(entry))
        if not typer.confirm("Delete?"):
            raise typer.Exit(0)

    api.delete(entry_id)
    typer.echo(f"Deleted #{entry_id}")


def main() -> None:
    app()
