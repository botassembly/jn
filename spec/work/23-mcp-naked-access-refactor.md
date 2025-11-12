# MCP Naked Access and Plugin Self-Containment

**Status:** Not Started
**Priority:** High
**See:** `spec/design/mcp.md`

---

## What

Enable naked MCP server access (no profiles required) and make MCP plugin fully self-contained by removing framework imports.

---

## Why

**Problem 1: Can't explore without profiles (chicken-and-egg)**
- Current: Must create profile before using MCP server
- Need: Direct access for exploration via naked URIs
- Use case: `jn inspect "mcp+uvx://biomcp-python/biomcp?command=run"`

**Problem 2: Plugin violates self-containment rule**
- Current: `mcp_.py` imports `jn.profiles.mcp` (framework code)
- Violates: Plugin contract says no framework imports
- Impact: Plugin not portable, can't run independently

---

## Goals

1. **Naked MCP URIs** - Access MCP servers without pre-existing profiles
2. **Inspect command** - List tools/resources from MCP server
3. **Cat/Head/Tail support** - Call tools directly with naked URIs
4. **Self-contained plugin** - Vendor profile resolver into mcp_.py (no framework imports)

---

## Naked URI Syntax

**Format:** `mcp+{launcher}://{package}[/{command}]?{params}`

**Examples:**
```bash
# UVX launcher
mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF

# NPX launcher
mcp+npx://@upstash/context7-mcp@latest?tool=search&library=fastapi

# Python launcher (local script)
mcp+python://./my_server.py?tool=fetch_data

# Node launcher (local script)
mcp+node://./server.js?tool=analyze
```

**Supported launchers:**
- `uvx` - UV tool runner (most common for Python MCPs)
- `npx` - NPM package executor (most common for Node MCPs)
- `python` - Direct Python script
- `node` - Direct Node script

---

## Inspect Command

**Purpose:** List what's available from MCP server (tools, resources)

**Terminology:** "inspect" matches MCP ecosystem (not "explore")

**Usage:**
```bash
# Inspect MCP server (naked URI)
jn inspect "mcp+uvx://biomcp-python/biomcp?command=run"

# Inspect via profile (later, once profiles work)
jn inspect "@biomcp"

# JSON output
jn inspect "mcp+uvx://..." --format json

# Text output (default)
jn inspect "mcp+uvx://..." --format text
```

**Output structure:**
```json
{
  "server": "biomcp-python/biomcp",
  "transport": "stdio",
  "tools": [
    {
      "name": "search",
      "description": "Search biomedical resources",
      "inputSchema": {
        "type": "object",
        "properties": {
          "gene": {"type": "string", "description": "Gene symbol"},
          "disease": {"type": "string", "description": "Disease name"}
        },
        "required": ["gene"]
      }
    },
    {
      "name": "trial_search",
      "description": "Clinical trials search",
      "inputSchema": { ... }
    }
  ],
  "resources": [
    {
      "uri": "resource://trials/NCT12345",
      "name": "Clinical Trial NCT12345",
      "description": "Phase 3 trial for melanoma"
    }
  ]
}
```

---

## Cat/Head/Tail with Naked URIs

**Call tools directly without profiles:**

```bash
# Call tool (reads all results)
jn cat "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF"

# First 10 results
jn head "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF"

# Last 10 results
jn tail "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF"

# Pipe through filters
jn cat "mcp+uvx://..." | jn filter '.text | contains("Phase 3")' | jn put results.json
```

**Implementation:** Update `reads()` function to handle both naked URIs and profile references.

---

## Self-Contained Plugin Refactor

### Current Problem

**File:** `jn_home/plugins/protocols/mcp_.py`

**Current imports:**
```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# PROBLEM: Framework import
from jn.profiles.mcp import resolve_profile_reference, ProfileError
```

**Why this is bad:**
- Violates plugin self-containment principle
- Plugin can't run independently without JN installed
- Not a true PEP 723 standalone script
- Breaks portability

### Solution: Vendor Profile Resolver

**Copy ~255 LOC from `src/jn/profiles/mcp.py` into `mcp_.py`:**

**Functions to vendor:**
1. `find_profile_paths()` - Searches project/.jn, user/~/.local, bundled/JN_HOME
2. `substitute_env_vars()` / `substitute_env_vars_recursive()` - Expands ${VAR}
3. `load_hierarchical_profile()` - Merges _meta.json + tool.json
4. `resolve_profile_reference()` - Parses @server/tool?query

**Result:** Single self-contained plugin file (or multi-file in same directory).

**Benefits:**
- Honors plugin contract (no framework imports)
- Portable (can run anywhere with uv)
- Clean boundaries (CLI orchestrates, plugin does I/O)
- Reproducible (all deps in PEP 723)

**Tradeoffs:**
- Code duplication (~255 lines)
- Changes to core resolver won't automatically reach plugin
- Need to sync manually if resolver evolves

**Decision:** Accept duplication for self-containment. This is the right trade-off.

---

## Implementation Tasks

### Phase 1: Naked URI Parsing (High Priority)

**Goal:** Support `mcp+launcher://` URIs

**Tasks:**
- [ ] Add `parse_naked_mcp_uri(uri: str) -> (server_config, params)` function
- [ ] Support launchers: uvx, npx, python, node
- [ ] Extract tool and params from query string
- [ ] Update plugin pattern to match `^mcp\\+[a-z]+://`

**Acceptance:**
```bash
jn cat "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF"
# Works without pre-existing profile, returns NDJSON results
```

**Effort:** 1 day

### Phase 2: Update reads() Function (High Priority)

**Goal:** Handle both naked URIs and profile references

**Tasks:**
- [ ] Check if URL starts with `mcp+` (naked) or `@` (profile)
- [ ] Parse accordingly
- [ ] Merge parameters
- [ ] Connect to MCP server, execute operation

**Implementation:**
```python
def reads(url: str, **params) -> Iterator[dict]:
    """Read from MCP - supports naked URIs and profiles."""

    if url.startswith("mcp+"):
        # Naked URI: parse directly
        server_config, tool_params = parse_naked_mcp_uri(url)
        tool_params.update(params)
    else:
        # Profile reference: resolve (vendored function)
        server_config, operation = resolve_profile_reference(url, params)
        tool_params = operation["params"]

    # Connect to server, execute, yield results
    # ... existing logic ...
```

**Acceptance:**
- ✅ Naked URIs work: `jn cat "mcp+uvx://..."`
- ✅ Profile refs still work: `jn cat "@biomcp/search"`

**Effort:** 1 day

### Phase 3: Inspect Command (High Priority)

**Goal:** Add `jn inspect` command for listing tools/resources

**Tasks:**
- [ ] Add `inspects(url: str, **config) -> dict` function to mcp_.py
- [ ] Create `src/jn/cli/commands/inspect.py`
- [ ] Register in `src/jn/cli/main.py`
- [ ] Support --format json/text

**Implementation:**
```python
def inspects(url: str, **config) -> dict:
    """List tools and resources from MCP server."""

    if url.startswith("mcp+"):
        server_config, _ = parse_naked_mcp_uri(url)
    else:
        server_config, _ = resolve_profile_reference(url, {})

    # Connect to MCP server
    session = connect_mcp_server(server_config)

    # List tools and resources
    tools_result = await session.list_tools()
    resources_result = await session.list_resources()

    return {
        "server": extract_server_name(url),
        "transport": "stdio",
        "tools": [serialize_tool(t) for t in tools_result.tools],
        "resources": [serialize_resource(r) for r in resources_result.resources]
    }
```

**Acceptance:**
```bash
jn inspect "mcp+uvx://biomcp-python/biomcp?command=run"
# Lists tools: search, trial_search, variant_search
# Lists resources: []
```

**Effort:** 1 day

### Phase 4: Vendor Profile Resolver (High Priority)

**Goal:** Remove framework import, make plugin self-contained

**Tasks:**
- [ ] Copy functions from `src/jn/profiles/mcp.py` into `mcp_.py`
- [ ] Remove `from jn.profiles.mcp import ...`
- [ ] Test profile-based access still works
- [ ] Verify all tests pass
- [ ] Remove mcp_ from plugin checker whitelist

**What to copy (~255 LOC):**
```python
# From src/jn/profiles/mcp.py

class ProfileError(Exception):
    """Error in profile resolution."""
    pass

def find_profile_paths() -> list[Path]:
    """Get search paths for MCP profiles."""
    # Project: .jn/profiles/mcp/
    # User: ~/.local/jn/profiles/mcp/
    # Bundled: $JN_HOME/profiles/mcp/

def substitute_env_vars(value: str) -> str:
    """Substitute ${VAR} in string."""

def substitute_env_vars_recursive(data):
    """Recursively substitute env vars."""

def load_hierarchical_profile(server_name: str, tool: str | None) -> dict:
    """Load _meta.json + tool.json."""

def list_server_tools(server_name: str) -> list[str]:
    """List tools in profile directory."""

def resolve_profile_reference(reference: str, params: dict | None) -> tuple[dict, dict]:
    """Parse @server/tool?query."""
```

**Testing:**
```bash
# Profile-based (should still work)
jn cat "@biomcp/search?gene=BRAF"

# Naked URI (should now work)
jn cat "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF"

# Inspect
jn inspect "mcp+uvx://biomcp-python/biomcp?command=run"
```

**Acceptance:**
- ✅ No `from jn.profiles.mcp import`
- ✅ All existing tests pass
- ✅ Plugin self-contained
- ✅ Removed from checker whitelist

**Effort:** 2-3 hours

### Phase 5: Update Documentation (Medium Priority)

**Tasks:**
- [ ] Update `docs/mcp.md` with naked URI examples
- [ ] Add inspect command docs
- [ ] Document launcher syntax
- [ ] Add troubleshooting section

**Effort:** 1-2 hours

---

## Testing

### Unit Tests

**New tests needed:**

1. **test_parse_naked_mcp_uri()**
   - Parse uvx launcher
   - Parse npx launcher
   - Parse python launcher
   - Parse with tool and params
   - Parse with just command

2. **test_inspect_command()**
   - List tools from MCP server
   - List resources
   - JSON output format
   - Text output format

3. **test_naked_uri_reads()**
   - Call tool with naked URI
   - Merge parameters correctly
   - Handle errors

### Integration Tests

**With real MCP servers:**

```bash
# BioMCP (if installed)
jn inspect "mcp+uvx://biomcp-python/biomcp?command=run"
jn cat "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF" | jn head

# Context7 (if installed)
jn inspect "mcp+npx://@upstash/context7-mcp@latest"
jn cat "mcp+npx://@upstash/context7-mcp@latest?tool=search&library=fastapi"
```

**Manual testing:**
- Verify no framework imports
- Verify plugin runs standalone with uv
- Verify profile-based access still works

---

## Out of Scope

**Not in this ticket:**

1. **Profile creation** - Just edit JSON manually for now
2. **Profile discovery CLI** - Future: `jn profile list`, `jn profile info`
3. **Schema versioning** - Future: hash-based change detection
4. **Generic plugin contract** - explores/validates/versions functions (future design)
5. **HTTP/S3 naked URIs** - This ticket is MCP-only

**Why later:** Focus on naked MCP access first. Prove the concept works. Then generalize.

---

## Acceptance Criteria

**Done when:**

1. ✅ Can inspect MCP server without profile: `jn inspect "mcp+uvx://..."`
2. ✅ Can call tools without profile: `jn cat "mcp+uvx://...&tool=X"`
3. ✅ Plugin has no framework imports (self-contained)
4. ✅ All existing tests pass
5. ✅ Documentation updated
6. ✅ Removed from plugin checker whitelist

---

## Effort Estimate

**Total:** 3-4 days

- Naked URI parsing: 1 day
- Update reads(): 1 day
- Inspect command: 1 day
- Vendor resolver: 2-3 hours
- Testing + docs: 1-2 hours

---

## Notes

**Launcher priority:** Start with uvx and npx (most common). Python/node launchers are nice-to-have.

**Profile creation:** Defer to future ticket. For now, just document: "Create _meta.json manually or copy from examples."

**Generic discovery:** This ticket focuses on MCP. Future work can generalize the pattern to HTTP, S3, etc.

**Terminology:** Use "inspect" (MCP ecosystem standard), not "explore" (generic term).
