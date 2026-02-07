"""CLI — thin wrapper over core API with $EDITOR integration."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import typer

from . import api

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


def _open_editor(initial: str = "") -> str | None:
    """Open $EDITOR, return content or None if empty."""
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vi"))
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write(initial)
        tmp_path = f.name

    try:
        subprocess.run([editor, tmp_path], check=True)
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
def edit(
    entry_id: int = typer.Argument(..., help="Entry ID"),
) -> None:
    """Edit an existing highlight in $EDITOR."""
    entry = _get_or_exit(entry_id)

    content = _open_editor(entry.content)
    if content is None or content == entry.content:
        typer.echo("No changes.")
        raise typer.Exit(0)

    updated = api.update(entry_id, content=content)
    if updated:
        typer.echo(f"Updated #{updated.id}")


@app.command()
def recent(
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
