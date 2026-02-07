# hl

Personal highlight capture. 
Authorship + MCP

> another evening experiment

## Usage

```
hl add                        # opens $EDITOR, write, save
hl add -s "https://..."       # same, with source
hl search "attention"         # full-text search
hl show 3                     # full entry
hl recent                     # latest entries
hl recent -a claude           # only AI-captured
```

Also runs as an MCP server — Claude can search and capture highlights during conversations.

## Install

```
uv tool install .             # CLI
hl-mcp install                # register MCP server
```
