# Using cloak as an MCP server

`cloak serve-mcp` exposes redaction as tools any MCP client can call.

```bash
pip install "cloak-llm[mcp]"
cloak serve-mcp        # speaks MCP over stdio
```

## Tools

| Tool | Args | Returns |
|------|------|---------|
| `cloak_scan` | `text`, `detectors` | detected entities (no change) |
| `cloak_mask` | `text`, `strategy`, `detectors` | `masked_text` + a `vault_id` |
| `cloak_unmask` | `text`, `vault_id` | text with originals restored |

The mask→unmask round trip is stateful: `cloak_mask` returns an opaque
`vault_id`; pass it to `cloak_unmask` later to restore. Vaults hold raw PII and
live only for the server's lifetime (the store is capacity-bounded).

## Register it in an MCP client

For example, in a Claude Desktop / Claude Code MCP config:

```json
{
  "mcpServers": {
    "cloak": {
      "command": "cloak",
      "args": ["serve-mcp"]
    }
  }
}
```

Then a model can call `cloak_mask` before sending text onward, and
`cloak_unmask` to recover originals from a `vault_id`.
