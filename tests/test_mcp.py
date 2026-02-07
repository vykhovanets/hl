"""Tests for the MCP server layer (mcp_server.py)."""

import asyncio

from hl.mcp_server import call_tool, list_tools
from hl import api


# -- list_tools --


def test_list_tools_returns_four_tools():
    tools = asyncio.run(list_tools())
    assert len(tools) == 4


def test_list_tools_names():
    tools = asyncio.run(list_tools())
    names = {t.name for t in tools}
    assert names == {"hl_add", "hl_search", "hl_show", "hl_recent"}


def test_list_tools_hl_add_schema_requires_content():
    tools = asyncio.run(list_tools())
    add_tool = [t for t in tools if t.name == "hl_add"][0]
    assert "content" in add_tool.inputSchema["required"]
    assert "source" not in add_tool.inputSchema["required"]


# -- hl_add --


def test_hl_add_basic():
    result = asyncio.run(call_tool("hl_add", {"content": "test insight"}))
    assert len(result) == 1
    assert "Saved highlight #1" in result[0].text


def test_hl_add_with_source():
    result = asyncio.run(
        call_tool("hl_add", {"content": "some quote", "source": "http://example.com"})
    )
    assert "Saved highlight #1" in result[0].text


def test_hl_add_sets_author_to_claude():
    asyncio.run(call_tool("hl_add", {"content": "insight from claude"}))
    entry = api.get(1)
    assert entry is not None
    assert entry.author == "claude"


def test_hl_add_source_defaults_to_empty():
    asyncio.run(call_tool("hl_add", {"content": "no source"}))
    entry = api.get(1)
    assert entry is not None
    assert entry.source == ""


def test_hl_add_increments_ids():
    asyncio.run(call_tool("hl_add", {"content": "first"}))
    result = asyncio.run(call_tool("hl_add", {"content": "second"}))
    assert "Saved highlight #2" in result[0].text


# -- hl_search --


def test_hl_search_finds_matching():
    asyncio.run(call_tool("hl_add", {"content": "attention mechanism in transformers"}))
    result = asyncio.run(call_tool("hl_search", {"query": "attention"}))
    text = result[0].text
    assert "1 results" in text
    assert "attention" in text.lower()


def test_hl_search_no_matches():
    asyncio.run(call_tool("hl_add", {"content": "something unrelated"}))
    result = asyncio.run(call_tool("hl_search", {"query": "nonexistent_xyz"}))
    assert "No highlights found for: nonexistent_xyz" in result[0].text


def test_hl_search_empty_db():
    result = asyncio.run(call_tool("hl_search", {"query": "anything"}))
    assert "No highlights found" in result[0].text


def test_hl_search_respects_limit():
    for i in range(5):
        asyncio.run(call_tool("hl_add", {"content": f"topic alpha number {i}"}))
    result = asyncio.run(call_tool("hl_search", {"query": "alpha", "limit": 2}))
    assert "2 results" in result[0].text


def test_hl_search_matches_source():
    asyncio.run(
        call_tool(
            "hl_add",
            {"content": "some note", "source": "http://arxiv.org/transformers"},
        )
    )
    result = asyncio.run(call_tool("hl_search", {"query": "arxiv"}))
    assert "1 results" in result[0].text


# -- hl_show --


def test_hl_show_existing():
    asyncio.run(
        call_tool(
            "hl_add", {"content": "detailed insight", "source": "http://example.com"}
        )
    )
    result = asyncio.run(call_tool("hl_show", {"id": 1}))
    text = result[0].text
    assert "id: 1" in text
    assert "author: claude" in text
    assert "detailed insight" in text
    assert "source: http://example.com" in text


def test_hl_show_nonexistent():
    result = asyncio.run(call_tool("hl_show", {"id": 999}))
    assert "No entry with id 999" in result[0].text


def test_hl_show_no_source_omits_source_line():
    asyncio.run(call_tool("hl_add", {"content": "no source entry"}))
    result = asyncio.run(call_tool("hl_show", {"id": 1}))
    text = result[0].text
    assert "source:" not in text


# -- hl_recent --


def test_hl_recent_empty_db():
    result = asyncio.run(call_tool("hl_recent", {}))
    assert "No highlights yet." in result[0].text


def test_hl_recent_lists_entries():
    asyncio.run(call_tool("hl_add", {"content": "first entry"}))
    asyncio.run(call_tool("hl_add", {"content": "second entry"}))
    result = asyncio.run(call_tool("hl_recent", {}))
    text = result[0].text
    assert "2 recent highlights" in text


def test_hl_recent_respects_limit():
    for i in range(5):
        asyncio.run(call_tool("hl_add", {"content": f"entry {i}"}))
    result = asyncio.run(call_tool("hl_recent", {"limit": 3}))
    assert "3 recent highlights" in result[0].text


def test_hl_recent_filter_by_author():
    # Add via MCP (author=claude)
    asyncio.run(call_tool("hl_add", {"content": "claude insight"}))
    # Add directly via API (author=user)
    api.add(content="user note", author="user")

    # Filter for claude only
    result = asyncio.run(call_tool("hl_recent", {"author": "claude"}))
    text = result[0].text
    assert "1 recent highlights" in text
    assert "claude insight" in text

    # Filter for user only
    result = asyncio.run(call_tool("hl_recent", {"author": "user"}))
    text = result[0].text
    assert "1 recent highlights" in text
    assert "user note" in text


def test_hl_recent_no_author_returns_all():
    asyncio.run(call_tool("hl_add", {"content": "claude entry"}))
    api.add(content="user entry", author="user")
    result = asyncio.run(call_tool("hl_recent", {}))
    assert "2 recent highlights" in result[0].text


# -- unknown tool --


def test_unknown_tool():
    result = asyncio.run(call_tool("nonexistent", {}))
    assert "Unknown tool: nonexistent" in result[0].text


# -- author separation --


def test_author_separation_mcp_vs_cli():
    """MCP always sets author='claude', distinguishable from CLI author='user'."""
    asyncio.run(call_tool("hl_add", {"content": "mcp entry"}))
    api.add(content="cli entry", author="user")

    mcp_entry = api.get(1)
    cli_entry = api.get(2)

    assert mcp_entry.author == "claude"
    assert cli_entry.author == "user"
    assert mcp_entry.author != cli_entry.author
