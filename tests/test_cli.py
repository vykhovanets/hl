"""CLI integration tests — exercise each command via typer.testing.CliRunner."""

from unittest.mock import patch

from typer.testing import CliRunner

from hl.cli import app
from hl import api

runner = CliRunner()


# --- add ---


def test_add_saves_entry():
    with patch("hl.cli._open_editor", return_value="some highlight"):
        result = runner.invoke(app, ["add"])
    assert result.exit_code == 0
    assert "Saved #1" in result.output


def test_add_empty_aborts():
    with patch("hl.cli._open_editor", return_value=None):
        result = runner.invoke(app, ["add"])
    assert result.exit_code == 1
    assert "Aborted" in result.output


def test_add_with_source():
    with patch("hl.cli._open_editor", return_value="quote from book"):
        result = runner.invoke(app, ["add", "-s", "http://example.com"])
    assert result.exit_code == 0
    assert "Saved #1" in result.output
    entry = api.get(1)
    assert entry.source == "http://example.com"


def test_add_author_is_user():
    with patch("hl.cli._open_editor", return_value="test content"):
        runner.invoke(app, ["add"])
    entry = api.get(1)
    assert entry.author == "user"


# --- search ---


def test_search_displays_results():
    api.add(content="python testing tips", author="user")
    result = runner.invoke(app, ["search", "python"])
    assert result.exit_code == 0
    assert "python testing tips" in result.output


def test_search_no_results():
    result = runner.invoke(app, ["search", "nonexistent"])
    assert result.exit_code == 1
    assert "No results." in result.output


def test_search_respects_limit():
    for i in range(5):
        api.add(content=f"rust pattern {i}", author="user")
    result = runner.invoke(app, ["search", "rust", "-n", "2"])
    assert result.exit_code == 0
    # Should have at most 2 entry headers
    output_ids = [line for line in result.output.splitlines() if line.startswith("[")]
    assert len(output_ids) <= 2


# --- show ---


def test_show_displays_entry():
    api.add(content="detailed highlight", author="user", source="book.pdf")
    result = runner.invoke(app, ["show", "1"])
    assert result.exit_code == 0
    assert "detailed highlight" in result.output
    assert "book.pdf" in result.output


def test_show_nonexistent_id():
    result = runner.invoke(app, ["show", "999"])
    assert result.exit_code == 1
    assert "No entry with id 999" in result.output


# --- edit ---


def test_edit_saves_changes():
    api.add(content="original text", author="user")
    with patch("hl.cli._open_editor", return_value="updated text"):
        result = runner.invoke(app, ["ed", "1"])
    assert result.exit_code == 0
    assert "Updated #1" in result.output
    assert api.get(1).content == "updated text"


def test_edit_no_changes():
    api.add(content="same text", author="user")
    with patch("hl.cli._open_editor", return_value="same text"):
        result = runner.invoke(app, ["ed", "1"])
    assert result.exit_code == 0
    assert "No changes." in result.output


def test_edit_empty_means_no_changes():
    api.add(content="keep this", author="user")
    with patch("hl.cli._open_editor", return_value=None):
        result = runner.invoke(app, ["ed", "1"])
    assert result.exit_code == 0
    assert "No changes." in result.output
    assert api.get(1).content == "keep this"


def test_edit_persists_on_intermediate_save():
    """ed writes to DB when on_save fires (before editor closes)."""
    api.add(content="original", author="user")

    def fake_editor(initial="", on_save=None):
        assert on_save is not None
        on_save("intermediate save")
        assert api.get(1).content == "intermediate save"
        return "final content"

    with patch("hl.cli._open_editor", side_effect=fake_editor):
        result = runner.invoke(app, ["ed", "1"])

    assert result.exit_code == 0
    assert api.get(1).content == "final content"


def test_edit_nonexistent_id():
    result = runner.invoke(app, ["ed", "999"])
    assert result.exit_code == 1
    assert "No entry with id 999" in result.output


# --- recent ---


def test_recent_lists_entries():
    api.add(content="first", author="user")
    api.add(content="second", author="user")
    result = runner.invoke(app, ["ls"])
    assert result.exit_code == 0
    assert "first" in result.output
    assert "second" in result.output


def test_recent_empty():
    result = runner.invoke(app, ["ls"])
    assert result.exit_code == 0
    assert "No highlights yet." in result.output


def test_recent_author_filter():
    api.add(content="user note", author="user")
    api.add(content="claude note", author="claude")
    result = runner.invoke(app, ["ls", "-a", "user"])
    assert result.exit_code == 0
    assert "user note" in result.output
    assert "claude note" not in result.output


def test_recent_respects_limit():
    for i in range(5):
        api.add(content=f"entry {i}", author="user")
    result = runner.invoke(app, ["ls", "-n", "2"])
    assert result.exit_code == 0
    output_ids = [line for line in result.output.splitlines() if line.startswith("[")]
    assert len(output_ids) == 2


# --- rm ---


def test_rm_force_deletes():
    api.add(content="delete me", author="user")
    result = runner.invoke(app, ["rm", "1", "-f"])
    assert result.exit_code == 0
    assert "Deleted #1" in result.output
    assert api.get(1) is None


def test_rm_confirm_yes(monkeypatch):
    api.add(content="to be removed", author="user")
    result = runner.invoke(app, ["rm", "1"], input="y\n")
    assert result.exit_code == 0
    assert "Deleted #1" in result.output
    assert api.get(1) is None


def test_rm_confirm_no():
    api.add(content="keep me", author="user")
    result = runner.invoke(app, ["rm", "1"], input="n\n")
    assert result.exit_code == 0
    assert api.get(1) is not None


def test_rm_nonexistent_id():
    result = runner.invoke(app, ["rm", "999", "-f"])
    assert result.exit_code == 1
    assert "No entry with id 999" in result.output
