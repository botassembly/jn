# MCP Integration in JN

**Status:** Implemented (naked URIs, inspect command, self-contained plugin)
**Date:** 2025-11-12
**Work Ticket:** `spec/work/23-mcp-naked-access-refactor.md`

---

## What is MCP?

**Model Context Protocol (MCP)** - Standard protocol for connecting AI applications to external data sources.

**Key Concepts:**
- **Servers** - Provide tools (callable functions) and resources (read-only data)
- **Transports** - stdio (subprocess), SSE (HTTP streaming), WebSocket
- **JSON-RPC 2.0** - Request/response protocol envelope

**Example MCP Servers:**
- `biomcp-python` - Biomedical data (clinical trials, PubMed, etc.)
- `@upstash/context7-mcp` - Code search and documentation
- Custom servers via Python/Node scripts

---

## Current Implementation

### 1. Naked MCP URIs (No Profiles Required)

Access MCP servers directly without pre-existing profile configuration:

**URI Format:** `mcp+{launcher}://{package}[/{command}]?{params}`

**Supported Launchers:**
- `uvx` - UV tool runner (Python MCPs): `mcp+uvx://biomcp-python/biomcp`
- `npx` - NPM executor (Node MCPs): `mcp+npx://@upstash/context7-mcp@latest`
- `python` - Local Python script: `mcp+python://./server.py`
- `node` - Local Node script: `mcp+node://./server.js`

**Examples:**
```bash
# Inspect server (list tools/resources)
jn inspect "mcp+uvx://biomcp-python/biomcp"

# Call tool directly
jn cat "mcp+uvx://biomcp-python/biomcp?tool=search&gene=BRAF"

# NPM-based MCP
jn cat "mcp+npx://@upstash/context7-mcp@latest?tool=search&library=fastapi"
```

**Implementation:** `parse_naked_mcp_uri()` in `jn_home/plugins/protocols/mcp_.py`

### 2. Inspect Command

List available tools and resources from an MCP server:

```bash
jn inspect "mcp+uvx://biomcp-python/biomcp"           # Text output
jn inspect "@biomcp" --format json                     # JSON output
```

**Output:**
- Server info (transport, connection)
- Tools list (name, description, parameters)
- Resources list (URI, name, description, mimeType)

**Implementation:**
- Plugin function: `inspects()` in `mcp_.py`
- CLI command: `src/jn/cli/commands/inspect.py`
- Direct plugin invocation (bypasses addressing system)

### 3. Profile-Based Access

Traditional profile references still work:

```bash
jn cat "@biomcp/search?gene=BRAF"
jn cat "@biomcp?list=tools"
```

**Profile Structure:**
```
profiles/mcp/biomcp/
  _meta.json        # Server connection (command, args, env)
  search.json       # Tool definition (optional)
```

**Profile Locations (priority order):**
1. Project: `.jn/profiles/mcp/`
2. User: `~/.local/jn/profiles/mcp/`
3. Bundled: `$JN_HOME/profiles/mcp/`

### 4. Self-Contained Plugin

**Fixed:** Plugin no longer imports framework code (`jn.profiles.mcp`).

**Solution:** Vendored ~250 LOC into `mcp_.py`:
- `ProfileError` class
- `find_profile_paths()` - Search project/user/bundled locations
- `substitute_env_vars()` / `substitute_env_vars_recursive()`
- `load_hierarchical_profile()` - Load _meta.json + tool.json
- `resolve_profile_reference()` - Parse @server/tool syntax

**Verification:**
- `jn check` passes without whitelist entries
- No framework imports
- Truly portable PEP 723 script

---

## Plugin API

The MCP plugin (`mcp_.py`) implements three functions:

### `reads(url: str, **params) -> Iterator[dict]`

Read from MCP server (naked URI or profile reference):

```python
# Naked URI
for record in reads("mcp+uvx://biomcp-python/biomcp?tool=search&gene=BRAF"):
    print(record)

# Profile reference
for record in reads("@biomcp/search", gene="BRAF"):
    print(record)
```

**Operations:**
- `list_tools` - List available tools
- `list_resources` - List available resources
- `call_tool` - Invoke tool with parameters
- `read_resource` - Fetch resource content

### `inspects(url: str, **config) -> dict`

List tools and resources:

```python
result = inspects("mcp+uvx://biomcp-python/biomcp")
# Returns: {"server": "...", "tools": [...], "resources": [...]}
```

### `writes(url: str, **config) -> None`

Read NDJSON from stdin, call MCP tool for each record:

```python
echo '{"gene": "BRAF"}' | jn put "@biomcp/search"
```

---

## CLI Integration

### `jn inspect`

List tools/resources from MCP server:

```bash
jn inspect "mcp+uvx://biomcp-python/biomcp"
jn inspect "@biomcp" --format json
```

**Implementation:** Bypasses addressing system, directly invokes `mcp_` plugin.

**Why bypass addressing?** The parser treats `@biomcp` (no slash) as plugin name lookup, not pattern matching. Direct invocation avoids this ambiguity.

### `jn cat`

Read from MCP server (via standard addressing):

```bash
jn cat "@biomcp/search?gene=BRAF"
jn cat "mcp+uvx://biomcp-python/biomcp?tool=search&gene=BRAF"
```

Pattern matching (`^@[a-zA-Z0-9_-]+` and `^mcp\+[a-z]+://`) routes to `mcp_` plugin.

### `jn put`

Write to MCP server (call tool with NDJSON input):

```bash
echo '{"gene": "BRAF"}' | jn put "@biomcp/search"
```

---

## URI Parsing Details

### Naked URI Syntax

**Format:** `mcp+{launcher}://{package}[/{command}]?{params}`

**Components:**
- `launcher` - Execution method: uvx, npx, python, node
- `package` - Package name or script path
- `command` - Optional command/entrypoint
- `params` - Query string parameters

### UV Launcher (uvx)

```
mcp+uvx://biomcp-python/biomcp?tool=search&gene=BRAF
          └─package─────┘└cmd─┘└────params────────────┘

Command: uv run --with biomcp-python biomcp
```

### NPM Launcher (npx)

```
mcp+npx://@upstash/context7-mcp@latest?tool=search
         └────────package─────────────┘└params──┘

Command: npx -y @upstash/context7-mcp@latest
```

### Python/Node Launchers

```
mcp+python://./my_server.py?tool=fetch
             └─script path─┘└params──┘

Command: python ./my_server.py
```

---

## Pattern Matching

Plugin metadata in `mcp_.py`:

```python
# [tool.jn]
# matches = [
#   "^@[a-zA-Z0-9_-]+",      # Profile references
#   "^mcp\\+[a-z]+://",      # Naked MCP URIs
# ]
```

**Plugin registry:**
- `@biomcp` → matches `mcp_` plugin
- `@biomcp/search` → matches `mcp_` plugin
- `mcp+uvx://...` → matches `mcp_` plugin

---

## Testing

**33 tests passing:**
- 9 plugin tests (`tests/cli/test_mcp_plugin.py`)
  - Self-containment verification
  - Pattern matching
  - Function interface
- 10 CLI tests (`tests/cli/test_inspect_command.py`)
  - Command registration
  - Format options (json/text)
  - Argument validation
- 14 profile tests (`tests/profiles/test_mcp_profiles.py`)
  - Profile resolution
  - Parameter merging
  - Operation types

**Code quality:**
- `jn check` passes (0 errors, 0 warnings)
- No whitelist entries required
- Self-contained plugin

---

## Future Work

**Profile Creation Helpers:**
- `jn inspect --save @biomcp` - Generate profile from inspection
- Profile templates for common MCPs

**Generic Discovery Contract:**
- `explores()` - List available operations
- `validates()` - Check configuration
- `versions()` - Track schema changes

**See:** Original assessment notes in git history for detailed exploration/exploit analysis.

---

## Summary

**Implemented:**
✅ Naked MCP URIs (no profiles required)
✅ Inspect command (list tools/resources)
✅ Self-contained plugin (no framework imports)
✅ Profile-based access (hierarchical config)
✅ Four launchers (uvx, npx, python, node)
✅ CLI integration (inspect, cat, put)
✅ Full test coverage (33 tests)

**Key Files:**
- Plugin: `jn_home/plugins/protocols/mcp_.py` (755 LOC)
- CLI: `src/jn/cli/commands/inspect.py`
- Tests: `tests/cli/test_mcp_plugin.py`, `tests/cli/test_inspect_command.py`
- Profiles: Framework (`src/jn/profiles/mcp.py`), Vendored (in plugin)

**Usage:**
```bash
# No profile required
jn inspect "mcp+uvx://biomcp-python/biomcp"
jn cat "mcp+uvx://biomcp-python/biomcp?tool=search&gene=BRAF"

# With profile
jn inspect "@biomcp"
jn cat "@biomcp/search?gene=BRAF"
```
