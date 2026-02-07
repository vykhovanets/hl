"""MCP server exposing hl functionality to Claude Code.

Usage:
    uv run hl-mcp install   # Register with Claude Code
    uv run hl-mcp uninstall # Remove registration
    uv run hl-mcp serve     # Run server (called by Claude Code)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from . import api

server = Server("hl")


# =============================================================================
# MCP Tool Definitions
# =============================================================================


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="hl_add",
            description="Capture a highlight. Author is automatically set to 'claude'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The highlight — quote, idea, insight, or note",
                    },
                    "source": {
                        "type": "string",
                        "description": "Where this came from (URL, book, paper, conversation)",
                        "default": "",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="hl_search",
            description="Search highlights by keyword across content and source.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 20)",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="hl_show",
            description="Show full details of a highlight entry by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer",
                        "description": "Entry ID",
                    },
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="hl_recent",
            description="List recent highlights. Optionally filter by author ('user' or 'claude').",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 20)",
                        "default": 20,
                    },
                    "author": {
                        "type": "string",
                        "description": "Filter by author: 'user' or 'claude'",
                    },
                },
            },
        ),
    ]


# =============================================================================
# MCP Tool Dispatch
# =============================================================================


def _format_entry_list(header: str, entries: list) -> list[TextContent]:
    lines = [header]
    for e in entries:
        lines.append(api.format_short(e))
    return [TextContent(type="text", text="\n".join(lines))]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "hl_add":
        entry = api.add(
            content=arguments["content"],
            source=arguments.get("source", ""),
            author="claude",
        )
        return [TextContent(type="text", text=f"Saved highlight #{entry.id}")]

    elif name == "hl_search":
        results = api.search(arguments["query"], limit=arguments.get("limit", 20))
        if not results:
            return [TextContent(type="text", text=f"No highlights found for: {arguments['query']}")]
        return _format_entry_list(f"Found {len(results)} results:\n", results)

    elif name == "hl_show":
        entry = api.get(arguments["id"])
        if not entry:
            return [TextContent(type="text", text=f"No entry with id {arguments['id']}")]
        return [TextContent(type="text", text=api.format_full(entry))]

    elif name == "hl_recent":
        results = api.recent(
            limit=arguments.get("limit", 20),
            author=arguments.get("author"),
        )
        if not results:
            return [TextContent(type="text", text="No highlights yet.")]
        return _format_entry_list(f"{len(results)} recent highlights:\n", results)

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def run_server():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


# =============================================================================
# Install/Uninstall CLI
# =============================================================================

mcp_app = typer.Typer(no_args_is_help=True, add_completion=False)


def _mcp_json_path() -> Path:
    return Path.cwd() / ".mcp.json"


def _load_mcp_json() -> dict:
    path = _mcp_json_path()
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save_mcp_json(config: dict) -> None:
    path = _mcp_json_path()
    path.write_text(json.dumps(config, indent=2) + "\n")


@mcp_app.command()
def install() -> None:
    """Register hl MCP server with Claude Code."""
    config = _load_mcp_json()
    config.setdefault("mcpServers", {})
    config["mcpServers"]["hl"] = {
        "command": "hl-mcp",
        "args": ["serve"],
    }
    _save_mcp_json(config)
    typer.echo(f"Registered hl MCP server in {_mcp_json_path()}")
    typer.echo("  Restart Claude Code to activate.")


@mcp_app.command()
def uninstall() -> None:
    """Remove hl MCP server registration."""
    config = _load_mcp_json()
    if "mcpServers" in config and "hl" in config["mcpServers"]:
        del config["mcpServers"]["hl"]
        if not config["mcpServers"]:
            del config["mcpServers"]
        _save_mcp_json(config)
        typer.echo("Removed hl MCP server registration.")
    else:
        typer.echo("hl MCP server not registered.")


@mcp_app.command()
def serve() -> None:
    """Run MCP server (called by Claude Code)."""
    asyncio.run(run_server())


def main() -> None:
    mcp_app()
