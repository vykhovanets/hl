# hl 🇺🇦

Personal highlight capture.
Authorship + MCP

> another evening experiment

## Usage

```
hl add                        # opens $EDITOR, write, save
hl add -s "https://..."       # same, with source
hl search "attention"         # full-text search
hl show 3                     # full entry
hl ls                         # latest entries
hl ls -a claude               # only AI-captured
hl ed                         # pick & edit in $EDITOR
hl ed 3                       # edit entry 3 directly
hl rm 3                       # delete entry
```

Also runs as an MCP server — Claude can search and capture highlights during conversations.

## Install

```
uv tool install git+https://github.com/vykhovanets/hl.git
claude mcp add hl -- hl-mcp
```
