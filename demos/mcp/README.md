# MCP - Model Context Protocol for JN

Connect to MCP servers using JN's profile system.

## Quick Examples

```bash
# List tools from BioMCP (bundled profile)
jn cat "@biomcp?list=tools"

# Search biomedical data
jn cat "@biomcp/search?gene=BRAF&disease=Melanoma"

# Get code documentation
jn cat "@context7/search?library=mcp"

# Pipeline example
echo '{"gene": "TP53"}' | jn put "@biomcp/variant_search"
```

## Bundled MCP Servers

**BioMCP** - Biomedical data (clinical trials, genomic variants)
```bash
uv tool install biomcp-python
jn cat "@biomcp/variant_search?gene=TP53&significance=pathogenic"
```

**Context7** - Code documentation from official sources
```bash
npm install -g @upstash/context7-mcp
jn cat "@context7/search?library=fastapi"
```

**Desktop Commander** - File system and terminal access
```bash
npm install -g @wonderwhy-er/desktop-commander
echo '{"command": "ls -la"}' | jn put "@desktop-commander/execute"
```

## Creating Custom Profiles

Create `.jn/profiles/mcp/myserver/_meta.json`:

```json
{
  "command": "python",
  "args": ["./my-mcp-server.py"],
  "description": "My custom MCP server"
}
```

Use it:
```bash
jn cat "@myserver?list=tools"
jn cat "@myserver/search?query=example"
```

## Profile Locations (Priority Order)

1. `.jn/profiles/mcp/` - Project profiles
2. `~/.local/jn/profiles/mcp/` - User profiles
3. `jn_home/profiles/mcp/` - Bundled profiles

## Reference Syntax

```
@{server}                    # List resources
@{server}?list=tools         # List tools
@{server}/{tool}?{params}    # Call tool
```

See `example.sh` for more patterns and the MCP specification at https://modelcontextprotocol.io/
