# MCP Profiles - Hierarchical Server Configuration

JN uses a **hierarchical profile system** for MCP servers, similar to HTTP profiles. This provides better organization, reusability, and discoverability.

## Quick Start

```bash
# Using profile references (recommended)
jn cat "@biomcp?list=tools"
jn cat "@biomcp/search?gene=BRAF&disease=Melanoma"
jn cat "@context7/search?library=mcp"

# Pipeline with profiles
echo '{"gene": "TP53"}' | jn put "@biomcp/search"
```

## Profile Structure

Profiles are organized in hierarchical directories:

```
profiles/mcp/
  {server-name}/
    _meta.json           # Server connection info (required)
    {tool-name}.json     # Tool definitions (optional)
    {resource-name}.json # Resource definitions (optional)
```

### Profile Locations (Priority Order)

1. **Project profiles** (highest priority): `.jn/profiles/mcp/`
2. **User profiles**: `~/.local/jn/profiles/mcp/`
3. **Bundled profiles** (lowest priority): `jn_home/profiles/mcp/`

Higher priority profiles override lower ones with the same name.

## Profile Files

### _meta.json (Server Configuration)

Contains server connection information:

```json
{
  "command": "uv",
  "args": ["run", "--with", "biomcp-python", "biomcp", "run"],
  "description": "BioMCP: Biomedical Model Context Protocol",
  "transport": "stdio",
  "env": {
    "OPTIONAL_API_KEY": "${BIOMCP_API_KEY}"
  }
}
```

**Required fields:**
- `command`: Command to launch the MCP server
- `args`: Command-line arguments (array)

**Optional fields:**
- `description`: Human-readable description
- `transport`: Transport type (`"stdio"` or `"http"`)
- `env`: Environment variables (supports `${VAR}` substitution)

### Tool Definition (tool-name.json)

Optional tool metadata and parameter schemas:

```json
{
  "tool": "search",
  "description": "Search biomedical resources",
  "parameters": {
    "gene": {
      "type": "string",
      "description": "Gene symbol (e.g., BRAF, TP53)",
      "required": true
    },
    "disease": {
      "type": "string",
      "description": "Disease or condition name"
    }
  }
}
```

Tool definitions are:
- **Optional**: JN can discover tools dynamically from the server
- **Useful for**: Documentation, validation, and IDE autocomplete
- **Merged with**: Server `_meta.json` when referenced

## Profile References

Profile references use the `@server/tool` syntax, similar to npm packages:

### Basic Syntax

```
@{server-name}               # Just server (lists resources)
@{server-name}/{tool-name}   # Server + tool
@{server-name}?{query}       # Server + query params
@{server-name}/{tool}?{params} # Server + tool + params
```

### Examples

```bash
# List server resources (default)
jn cat "@biomcp"

# List server tools
jn cat "@biomcp?list=tools"

# List server resources (explicit)
jn cat "@biomcp?list=resources"

# Call a tool (tool in path)
jn cat "@biomcp/search?gene=BRAF"

# Call a tool (tool in query)
jn cat "@biomcp?tool=search&gene=BRAF&disease=Melanoma"

# Read a resource
jn cat "@biomcp?resource=resource://trials/NCT12345"
```

## Bundled Profiles

JN includes profiles for popular MCP servers:

### BioMCP
**Location**: `jn_home/profiles/mcp/biomcp/`

Biomedical data access (clinical trials, literature, genomic variants).

**Tools**:
- `search`: General biomedical search
- `trial_search`: Clinical trials search
- `variant_search`: Genomic variants search

**Installation**:
```bash
uv tool install biomcp-python
```

**Example**:
```bash
jn cat "@biomcp/variant_search?gene=TP53&significance=pathogenic"
```

### Context7
**Location**: `jn_home/profiles/mcp/context7/`

Up-to-date code documentation from official sources.

**Tools**:
- `search`: Search library documentation

**Installation**:
```bash
npm install -g @upstash/context7-mcp
```

**Example**:
```bash
jn cat "@context7/search?library=mcp&version=1.0"
```

### Desktop Commander
**Location**: `jn_home/profiles/mcp/desktop-commander/`

File system and terminal control for local development.

**Tools**:
- `execute`: Execute shell commands

**Installation**:
```bash
npm install -g @wonderwhy-er/desktop-commander
```

**Example**:
```bash
echo '{"command": "ls -la"}' | jn put "@desktop-commander/execute"
```

## Creating Custom Profiles

### Project-Specific Profile

Create `.jn/profiles/mcp/myserver/_meta.json` in your project:

```json
{
  "command": "python",
  "args": ["./my-mcp-server.py"],
  "description": "My custom MCP server",
  "transport": "stdio"
}
```

Use it:
```bash
jn cat "@myserver?list=tools"
```

### User-Global Profile

Create `~/.local/jn/profiles/mcp/myserver/_meta.json` for use across all projects.

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

Set environment variables before use:
```bash
export MY_API_KEY="secret"
export MY_BASE_URL="https://api.example.com"
jn cat "@myserver/search"
```

### With Tool Definitions

Create `.jn/profiles/mcp/myserver/search.json`:

```json
{
  "tool": "search",
  "description": "Search my custom data source",
  "parameters": {
    "query": {
      "type": "string",
      "description": "Search query",
      "required": true
    },
    "limit": {
      "type": "integer",
      "description": "Maximum results",
      "default": 10
    }
  }
}
```

Reference it:
```bash
jn cat "@myserver/search?query=foo&limit=20"
```

## Profile Resolution

When you use `@biomcp/search?gene=BRAF`:

1. **Find server profile**: Search for `biomcp/_meta.json` in profile paths (project → user → bundled)
2. **Load server config**: Parse `_meta.json` and substitute env vars
3. **Find tool definition**: Look for `biomcp/search.json` (optional)
4. **Merge configuration**: Combine `_meta.json` + `search.json`
5. **Parse operation**: Determine operation type (call_tool) and parameters
6. **Return**: `(server_config, operation_info)`

## Environment Variable Substitution

Profiles support `${VAR}` syntax for environment variables:

```json
{
  "command": "curl",
  "args": ["-H", "Authorization: Bearer ${API_TOKEN}"]
}
```

If `API_TOKEN` is not set, you'll get a `ProfileError`.

## Pipeline Examples

### Search and Filter

```bash
# Search BioMCP and filter results
jn cat "@biomcp/search?gene=BRAF" | \
  jn filter '.text | contains("Phase 3")' | \
  jn put results.json
```

### Batch Processing

```bash
# Process multiple genes
jn cat genes.csv | \
  jn filter '{gene: .symbol}' | \
  jn put "@biomcp/variant_search" | \
  jn put variants.json
```

### Cross-Source Integration

```bash
# Get docs from Context7, search trials in BioMCP
jn cat "@context7/search?library=genomics" | \
  jn filter '{gene: .gene_name}' | \
  jn put "@biomcp/trial_search" | \
  jn put integrated_results.json
```

## Comparison: Profiles vs. Legacy

### Legacy (mcp-servers.json)

```bash
# Old way (still supported)
jn cat "mcp://biomcp?tool=search&gene=BRAF"
```

Requires `~/.jn/mcp-servers.json`:
```json
{
  "biomcp": {
    "command": "uv",
    "args": ["run", "--with", "biomcp-python", "biomcp", "run"]
  }
}
```

### Profiles (Recommended)

```bash
# New way (recommended)
jn cat "@biomcp/search?gene=BRAF"
```

Bundled profiles work out-of-the-box. No configuration needed!

**Benefits**:
- ✅ Hierarchical organization (server + tools)
- ✅ Tool definitions for documentation
- ✅ Project/user/bundled priority system
- ✅ Environment variable support
- ✅ Bundled profiles included
- ✅ Cleaner syntax (`@` vs `mcp://`)

## Troubleshooting

### Profile Not Found

```json
{"_error": true, "type": "profile_error", "message": "MCP server profile not found: myserver"}
```

**Solution**: Check profile paths:
1. Is `_meta.json` in the right location?
2. Check `.jn/profiles/mcp/`, `~/.local/jn/profiles/mcp/`, or `jn_home/profiles/mcp/`

### Environment Variable Not Set

```json
{"_error": true, "type": "profile_error", "message": "Environment variable API_KEY not set"}
```

**Solution**: Set the required environment variable:
```bash
export API_KEY="your-key"
```

### Tool Not Found

```json
{"_error": true, "type": "profile_error", "message": "Source not found: biomcp/unknown_tool"}
```

**Solution**:
- Check available tools: `jn cat "@biomcp?list=tools"`
- Tool definitions in profiles are optional (for documentation only)
- The server itself determines which tools are available

## Implementation Details

### Files

- **Profile system**: `src/jn/profiles/mcp.py`
- **MCP plugin**: `jn_home/plugins/protocols/mcp_.py`
- **Bundled profiles**: `jn_home/profiles/mcp/{server}/`

### Functions

```python
from jn.profiles.mcp import (
    find_profile_paths,          # Get search paths
    load_hierarchical_profile,   # Load _meta + tool
    resolve_profile_reference,   # Parse @server/tool
    list_server_tools,           # List available tools
)

# Resolve a profile reference
server_config, operation = resolve_profile_reference("@biomcp/search?gene=BRAF")

# server_config: {'command': 'uv', 'args': [...], ...}
# operation: {'type': 'call_tool', 'tool': 'search', 'params': {'gene': 'BRAF'}}
```

### Pattern Matching

The MCP plugin matches these patterns:

- `^@[a-zA-Z0-9_-]+` - Profile references (`@biomcp`, `@context7`)
- `^mcp://.*` - Legacy MCP URLs
- `^mcp\+stdio://.*` - Explicit stdio transport
- `^mcp\+http://.*` - HTTP transport (planned)

## See Also

- **HTTP Profiles**: Similar system for REST APIs (`src/jn/profiles/http.py`)
- **MCP Plugin**: Main plugin implementation (`jn_home/plugins/protocols/mcp_.py`)
- **MCP Specification**: [modelcontextprotocol.io](https://modelcontextprotocol.io/)
- **BioMCP**: [biomcp.org](https://biomcp.org/)
