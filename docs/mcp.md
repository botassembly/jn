# MCP Plugin - Model Context Protocol for JN

Connect to MCP servers using JN's hierarchical profile system.

## Quick Start

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

## Profile System

MCP profiles use hierarchical directories:

```
profiles/mcp/
  {server-name}/
    _meta.json        # Server connection info (required)
    {tool}.json       # Tool definitions (optional)
```

### Profile Locations (Priority Order)

1. **Project**: `.jn/profiles/mcp/` (highest priority)
2. **User**: `~/.local/jn/profiles/mcp/`
3. **Bundled**: `jn_home/profiles/mcp/` (included with JN)

## Bundled Profiles

### BioMCP
Biomedical data (clinical trials, literature, genomic variants).

**Installation**:
```bash
uv tool install biomcp-python
```

**Tools**:
- `search`: General biomedical search
- `trial_search`: Clinical trials
- `variant_search`: Genomic variants

**Examples**:
```bash
jn cat "@biomcp/variant_search?gene=TP53&significance=pathogenic"
jn cat "@biomcp/trial_search?condition=Melanoma&phase=PHASE3"
```

### Context7
Up-to-date code documentation from official sources.

**Installation**:
```bash
npm install -g @upstash/context7-mcp
```

**Tools**:
- `search`: Library documentation search

**Examples**:
```bash
jn cat "@context7/search?library=mcp"
jn cat "@context7/search?library=fastapi&version=0.100.0"
```

### Desktop Commander
File system and terminal access for local development.

**Installation**:
```bash
npm install -g @wonderwhy-er/desktop-commander
```

**Tools**:
- `execute`: Execute shell commands

**Examples**:
```bash
echo '{"command": "ls -la"}' | jn put "@desktop-commander/execute"
```

## Reference Syntax

```
@{server}                    # List resources (default)
@{server}?list=tools         # List tools
@{server}?list=resources     # List resources (explicit)
@{server}/{tool}             # Call tool
@{server}/{tool}?{params}    # Call tool with params
@{server}?resource={uri}     # Read specific resource
```

## Creating Custom Profiles

### Minimal Profile

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
```

### With Environment Variables

```json
{
  "command": "python",
  "args": ["./server.py"],
  "env": {
    "API_KEY": "${MY_API_KEY}",
    "BASE_URL": "${MY_BASE_URL}"
  }
}
```

Set variables before use:
```bash
export MY_API_KEY="secret"
jn cat "@myserver/search"
```

### With Tool Definitions

Create `.jn/profiles/mcp/myserver/search.json`:

```json
{
  "tool": "search",
  "description": "Search my data source",
  "parameters": {
    "query": {
      "type": "string",
      "description": "Search query",
      "required": true
    }
  }
}
```

Tool definitions are optional (for documentation only). The MCP server determines available tools.

## Pipeline Examples

### Search and Filter

```bash
jn cat "@biomcp/search?gene=BRAF" | \
  jn filter '.text | contains("Phase 3")' | \
  jn put results.json
```

### Batch Processing

```bash
jn cat genes.csv | \
  jn filter '{gene: .symbol}' | \
  jn put "@biomcp/variant_search" | \
  jn put variants.json
```

### Cross-Source Integration

```bash
jn cat "@context7/search?library=genomics" | \
  jn filter '{gene: .gene_name}' | \
  jn put "@biomcp/trial_search" | \
  jn put results.json
```

## Error Handling

Errors are returned as NDJSON records with `_error: true`:

```json
{
  "_error": true,
  "type": "profile_error",
  "message": "MCP server profile not found: unknown"
}
```

Common error types:
- `profile_error` - Profile not found or invalid
- `resolution_error` - Error resolving profile reference
- `mcp_error` - MCP protocol error
- `json_decode_error` - Invalid JSON in input

## Implementation

### Files
- **Profile system**: `src/jn/profiles/mcp.py`
- **Plugin**: `jn_home/plugins/protocols/mcp_.py`
- **Bundled profiles**: `jn_home/profiles/mcp/`

### Pattern Matching

The MCP plugin matches URLs starting with `@`:
```
^@[a-zA-Z0-9_-]+
```

### How It Works

1. Framework sees `@biomcp/search?gene=BRAF`
2. MCP plugin's `reads()` is called with the reference
3. Plugin calls `resolve_profile_reference()` from profile system
4. Profile system loads `biomcp/_meta.json` + `search.json`
5. Returns server config + operation details
6. Plugin starts MCP server, connects via stdio
7. Executes operation (list/read/call)
8. Returns NDJSON records

## Resources

- **MCP Specification**: https://modelcontextprotocol.io/
- **MCP Python SDK**: https://github.com/modelcontextprotocol/python-sdk
- **BioMCP**: https://biomcp.org/
- **HTTP Profiles**: Similar system for REST APIs (`src/jn/profiles/http.py`)
