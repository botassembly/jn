# MCP Integration in JN

**Purpose:** Complete design for Model Context Protocol (MCP) integration
**Status:** Implemented (client mode with profiles), Discovery flow proposed
**Date:** 2025-11-12
**Related:** `spec/work/19-mcp-protocol.md`, `docs/mcp.md`

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [What is MCP?](#what-is-mcp)
3. [Current Implementation](#current-implementation)
4. [The Versioning Problem](#the-versioning-problem)
5. [Naked MCP Access](#naked-mcp-access)
6. [Discovery Flow](#discovery-flow)
7. [Schema Change Detection](#schema-change-detection)
8. [Profile System](#profile-system)
9. [Explore vs Exploit](#explore-vs-exploit)
10. [Implementation Strategy](#implementation-strategy)

---

## Executive Summary

**Current State:**
- ✅ MCP client works (read/write to MCP servers)
- ✅ Profile-based access functional
- ✅ Both local (uvx) and remote (npx) MCPs supported
- ❌ No "naked" MCP access (profiles required)
- ❌ No discovery flow (explore → profile creation)
- ❌ No schema versioning/change detection

**Key Challenge:** MCPs can change their tool schemas without versioning, potentially breaking profiles. Need discovery flow + change detection.

**Proposed Solution:**
1. **Naked MCP URIs** - Access MCPs without profiles for exploration
2. **Discovery flow** - LLM explores MCP, designs profile
3. **Schema hashing** - Detect when MCP tools change
4. **Profile versioning** - Track which schema version profile expects

---

## What is MCP?

### MCP Specification

**Official Spec:** https://modelcontextprotocol.io/

**MCP Protocol Uses JSON-RPC:**
- Protocol envelope: JSON-RPC 2.0
- Tool responses: JSON objects with `content` field
- Content can be:
  - `text` (string) - Plain text, JSON, markdown, etc.
  - `blob` (base64) - Binary data
  - `mimeType` - Indicates content type

**Example MCP response:**
```json
{
  "type": "tool_result",
  "content": [
    {
      "type": "text",
      "text": "BRAF V600E is a common mutation...",
      "mimeType": "text/plain"
    }
  ]
}
```

**So yes, MCP always returns JSON** (the protocol), but the payload (`text` field) can be anything - plain text, JSON, markdown, etc.

### MCP Primitives

1. **Resources** - Read-only data (files, DB results)
   - URI: `resource://domain/path`
   - Operation: `read_resource(uri)`

2. **Tools** - Invokable functions with parameters
   - Schema: JSON Schema for parameters
   - Operation: `call_tool(name, arguments)`
   - Can be called multiple times with different args

3. **Prompts** - LLM interaction templates (not used in JN)

4. **Sampling** - LLM completion requests (not relevant for JN)

### MCP Transports

- **stdio** - Standard input/output (most common, JN uses this)
- **HTTP/SSE** - HTTP with Server-Sent Events
- **WebSocket** - Real-time bidirectional

---

## Current Implementation

### What Works Today

**Profile-based access:**
```bash
# Read from MCP tool
jn cat "@biomcp/search?gene=BRAF"

# Write to MCP tool (batch)
echo '{"gene": "TP53"}' | jn put "@biomcp/variant_search"

# List tools dynamically
jn cat "@biomcp?list=tools"
```

**Implementation:**
- Plugin: `jn_home/plugins/protocols/mcp_.py`
- Profiles: `src/jn/profiles/mcp.py`
- Tests: All passing (8 plugin, 14 profile tests)

**Profile structure:**
```
profiles/mcp/
  biomcp/
    _meta.json        # Server launch config
    search.json       # Tool definition (optional)
    trial_search.json
```

**Profile example (_meta.json):**
```json
{
  "command": "uv",
  "args": ["run", "--with", "biomcp-python", "biomcp", "run"],
  "transport": "stdio"
}
```

### Why Profiles Are Currently Required

**MCPs have no standard URI scheme.**

Different MCPs launch differently:
- BioMCP: `uv run --with biomcp-python biomcp run`
- Context7: `npx -y @upstash/context7-mcp@latest`
- Custom: `python my_server.py` or `node server.js`

**Profiles define HOW to launch each server.**

---

## The Versioning Problem

### MCPs Can Change Without Warning

**Unlike traditional APIs:**
- REST APIs have versions: `/v1/endpoint`, `/v2/endpoint`
- Breaking changes = new version
- Old versions maintained for backwards compatibility

**MCPs have no versioning:**
- Tool schemas can change at any time
- No version in tool name or protocol
- LLMs don't care (they read schema fresh each time)
- But profiles DO care (they document expected schema)

### Example: Schema Change Breaking Profile

**Profile created for BioMCP v1:**
```json
{
  "tool": "search",
  "parameters": {
    "gene": {"type": "string", "required": true},
    "disease": {"type": "string"}
  }
}
```

**BioMCP v2 changes schema:**
```json
{
  "tool": "search",
  "parameters": {
    "query": {"type": "string", "required": true},  // Renamed!
    "filters": {"type": "object"}                    // New structure
  }
}
```

**Result:** Profile expects `gene` parameter, but MCP now expects `query`. Calls fail.

### Why This Matters for JN

**Profiles cache knowledge:**
- Documentation says "use gene parameter"
- Examples show `?gene=BRAF`
- LLMs learn from profile, use wrong params
- Calls fail mysteriously

**Need:** Detect when MCP schema changes, update profiles accordingly.

---

## Naked MCP Access

### Proposal: MCP Protocol URIs

**Goal:** Access MCP without pre-existing profile, for exploration.

**Challenge:** MCPs launch differently (uvx, npx, python, node). How to encode in URI?

### Proposed URI Schemes

#### Option 1: Extended Protocol Syntax

**Format:** `mcp+{launcher}://{package}?{params}`

**Examples:**
```bash
# UVX launcher
mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF

# NPX launcher
mcp+npx://@upstash/context7-mcp@latest?tool=search&library=fastapi

# Python launcher
mcp+python://./my_server.py?tool=fetch_data

# Node launcher
mcp+node://./server.js?tool=analyze
```

**Pros:**
- Self-contained (all info in URI)
- Standard URI syntax
- Easy to parse launcher type

**Cons:**
- Complex for multi-arg commands
- Hard to encode `--with` flags and complex args

#### Option 2: Query String Parameters

**Format:** `mcp://{server}?launcher={type}&package={pkg}&tool={name}&{args}`

**Examples:**
```bash
mcp://biomcp?launcher=uvx&package=biomcp-python&command=run&tool=search&gene=BRAF

mcp://context7?launcher=npx&package=@upstash/context7-mcp@latest&tool=search&library=mcp
```

**Pros:**
- Pure query string (standard parsing)
- Flexible for complex args

**Cons:**
- Very long URIs
- Launcher params mixed with tool params

#### Option 3: Launcher Presets

**Format:** `mcp://{preset}?tool={name}&{args}`

**Requires:** Registry of known launchers (like profiles but minimal)

**Registry file:** `.jn/mcp-launchers.json`
```json
{
  "biomcp": {
    "launcher": "uvx",
    "package": "biomcp-python",
    "command": "biomcp",
    "args": ["run"]
  },
  "context7": {
    "launcher": "npx",
    "package": "@upstash/context7-mcp@latest"
  }
}
```

**Usage:**
```bash
jn cat "mcp://biomcp?tool=search&gene=BRAF"
```

**Pros:**
- Clean URIs
- Reusable launcher configs
- Easy to extend

**Cons:**
- Still needs minimal config file (but simpler than full profile)
- Not truly "naked" (requires launcher registry)

### Recommendation: Option 1 (Extended Protocol)

**Why:**
- Truly naked (no pre-existing config needed)
- Standard URI syntax
- Clear launcher type
- Works for most common cases

**For complex launchers:** Fall back to minimal profile.

**Implementation:**
```python
def parse_naked_mcp_uri(uri: str) -> ServerConfig:
    """Parse mcp+{launcher}://{package}?{params} format."""
    # Example: mcp+uvx://biomcp-python/biomcp?command=run
    protocol, rest = uri.split("://", 1)
    launcher = protocol.split("+")[1]  # "uvx"
    package_path, query = rest.split("?", 1)

    if launcher == "uvx":
        parts = package_path.split("/")
        return {
            "command": "uv",
            "args": ["run", "--with", parts[0], parts[1], ...],
            "transport": "stdio"
        }
    elif launcher == "npx":
        return {
            "command": "npx",
            "args": ["-y", package_path],
            "transport": "stdio"
        }
    # etc.
```

---

## Discovery Flow

### Goal: Explore MCP → Design Profile

**Current problem:** Profiles are manually created. No systematic exploration.

**Proposed flow:**

### Phase 1: Naked Connection

```bash
# Connect to MCP without profile
jn mcp explore "mcp+uvx://biomcp-python/biomcp?command=run"
```

**What it does:**
1. Parse naked URI
2. Launch MCP server
3. Call `list_tools()` and `list_resources()`
4. Output tools and schemas to LLM

**Output:**
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
      "inputSchema": { ... }
    }
  ],
  "resources": [ ... ]
}
```

### Phase 2: LLM Exploration

**LLM reviews schema, calls tools to understand behavior:**

```bash
# LLM: "Let me test the search tool"
jn cat "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF"

# LLM: "Output is text about BRAF mutations. Let me try with disease filter."
jn cat "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF&disease=melanoma"

# LLM: "More specific results. Let me check if optional params work."
jn cat "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=EGFR"
```

**LLM understanding:**
- `search` tool returns plain text (not structured JSON)
- `gene` param is required
- `disease` param is optional but useful for filtering
- Output is suitable for LLM consumption (prose description)

### Phase 3: Profile Design

**LLM designs profile based on exploration:**

```json
{
  "server": "biomcp",
  "description": "BioMCP: Biomedical data for clinical trials and genomics",
  "launcher": {
    "command": "uv",
    "args": ["run", "--with", "biomcp-python", "biomcp", "run"],
    "transport": "stdio"
  },
  "tools": {
    "search": {
      "description": "General biomedical search. Returns text summaries.",
      "parameters": {
        "gene": {"type": "string", "required": true, "description": "Gene symbol (e.g., BRAF)"},
        "disease": {"type": "string", "description": "Filter by disease name"}
      },
      "output_format": "text/plain",
      "notes": "Returns prose description, not structured JSON. Good for LLM consumption."
    },
    "trial_search": {
      "description": "Search clinical trials by gene/disease/phase",
      "parameters": { ... }
    }
  },
  "schema_hash": "a3f5b8c2...",  // MD5 of tool schemas
  "created": "2025-11-12",
  "tested_with": {
    "search": ["BRAF", "BRAF+melanoma", "EGFR"],
    "trial_search": ["BRAF+PHASE3"]
  }
}
```

**Key additions:**
- `schema_hash` - For change detection
- `output_format` - What to expect from tool
- `notes` - LLM's observations about behavior
- `tested_with` - Example queries that worked during exploration

### Phase 4: Save Profile

```bash
# LLM: "I'll save this as a profile"
jn profile create biomcp < profile.json

# Creates:
# ~/.local/jn/profiles/mcp/biomcp/_meta.json
# ~/.local/jn/profiles/mcp/biomcp/search.json
# ~/.local/jn/profiles/mcp/biomcp/trial_search.json
```

### Phase 5: Use Profile

**Now profile-based access works:**
```bash
jn cat "@biomcp/search?gene=BRAF"
```

**And schema validation happens automatically.**

---

## Schema Change Detection

### Strategy: Hash-Based Versioning

**Goal:** Detect when MCP tool schema changes, prompt profile update.

### What to Hash

**Include in hash:**
- Tool name
- Required parameters (names and types)
- Parameter types
- Required vs optional distinction

**Exclude from hash:**
- Parameter descriptions (can change without breaking)
- Tool description
- Optional parameter additions (backwards compatible)

### Hash Calculation

```python
def calculate_schema_hash(tools: list[dict]) -> str:
    """Calculate MD5 hash of tool schemas."""
    hash_input = []

    for tool in sorted(tools, key=lambda t: t["name"]):
        tool_sig = {
            "name": tool["name"],
            "required": sorted(tool["inputSchema"].get("required", [])),
            "types": {
                param: schema["type"]
                for param, schema in tool["inputSchema"]["properties"].items()
            }
        }
        hash_input.append(json.dumps(tool_sig, sort_keys=True))

    return hashlib.md5("\n".join(hash_input).encode()).hexdigest()
```

### Schema Validation on Use

**Every time profile is used:**

```python
def validate_profile_schema(profile: dict, server_config: dict) -> ValidationResult:
    """Check if MCP server schema matches profile expectation."""

    # Connect to server
    session = connect_mcp(server_config)
    current_tools = session.list_tools()

    # Calculate current schema hash
    current_hash = calculate_schema_hash(current_tools)

    # Compare with profile's expected hash
    expected_hash = profile.get("schema_hash")

    if expected_hash is None:
        return ValidationResult(status="unknown", message="Profile has no schema hash")

    if current_hash != expected_hash:
        # Detect what changed
        changes = detect_schema_changes(profile["tools"], current_tools)
        return ValidationResult(
            status="changed",
            message="MCP schema has changed since profile was created",
            changes=changes,
            current_hash=current_hash
        )

    return ValidationResult(status="valid")
```

### Change Detection Details

**Types of changes:**

1. **Breaking changes** (require profile update):
   - Required parameter added
   - Required parameter removed
   - Required parameter renamed
   - Parameter type changed

2. **Non-breaking changes** (informational):
   - Optional parameter added
   - Description changed
   - Optional parameter removed (if not used in profile)

3. **Behavioral changes** (need LLM review):
   - Output format changed (e.g., text → JSON)
   - Semantics changed (same params, different behavior)

### User Experience

**When schema mismatch detected:**

```bash
$ jn cat "@biomcp/search?gene=BRAF"

Warning: MCP server schema has changed since profile was created.

Changes detected:
  - Tool 'search': Required parameter 'gene' renamed to 'query'
  - Tool 'search': New optional parameter 'filters' added

Profile hash: a3f5b8c2...
Current hash: f7d3a1e9...

Options:
  1. Update profile: jn profile update biomcp
  2. Explore changes: jn mcp explore biomcp
  3. Ignore (may cause errors): jn cat "@biomcp/search?gene=BRAF" --ignore-schema
```

**Auto-update flow:**

```bash
$ jn profile update biomcp

Connecting to biomcp MCP server...
Fetching current tool schemas...

Changes detected:
  - 'gene' parameter renamed to 'query' (breaking change)
  - 'filters' parameter added (non-breaking)

Update strategy:
  1. Update profile to use 'query' instead of 'gene'
  2. Add 'filters' parameter as optional
  3. Recalculate schema hash

Update examples in profile? (Y/n) y

Updated profile saved to ~/.local/jn/profiles/mcp/biomcp/
New schema hash: f7d3a1e9...

Test updated profile? (Y/n) y
Running: jn cat "@biomcp/search?query=BRAF"
✓ Success

Profile updated successfully.
```

---

## Profile System

### Current Profile Structure

```
profiles/mcp/
  {server}/
    _meta.json        # Server launch config
    {tool}.json       # Tool definitions (optional)
```

### Enhanced Profile Structure (Proposed)

**Add schema versioning fields:**

```json
{
  "server": "biomcp",
  "command": "uv",
  "args": ["run", "--with", "biomcp-python", "biomcp", "run"],
  "transport": "stdio",

  "schema_hash": "a3f5b8c2e1f4...",
  "schema_updated": "2025-11-12T10:30:00Z",
  "schema_validation": "warn",  // "warn", "error", "ignore"

  "tools": {
    "search": {
      "tool": "search",
      "description": "Search biomedical resources",
      "parameters": { ... },
      "output_format": "text/plain",
      "notes": "Returns prose, not structured JSON"
    }
  }
}
```

**New fields:**
- `schema_hash` - MD5 of tool schemas when profile created
- `schema_updated` - Last time schema was validated
- `schema_validation` - How to handle mismatches (warn/error/ignore)
- `output_format` - Expected output type (helps LLM understand)
- `notes` - Human/LLM observations about tool behavior

### Minimal vs Full Profiles

**Minimal profile (for exploration):**
```json
{
  "command": "uv",
  "args": ["run", "--with", "biomcp-python", "biomcp", "run"],
  "transport": "stdio"
}
```

**Usage:** `jn cat "@biomcp?tool=search&gene=BRAF"`
- No tool definitions
- No schema hash (always queries server)
- Good for exploration

**Full profile (for exploitation):**
```json
{
  "command": "uv",
  "args": [...],
  "schema_hash": "...",
  "tools": {
    "search": { detailed definition },
    "trial_search": { detailed definition }
  }
}
```

**Usage:** `jn cat "@biomcp/search?gene=BRAF"`
- Tool definitions cached
- Schema validated
- Good for production

---

## Explore vs Exploit

### The Two Phases

**Explore Phase:** Discovery and understanding
- Connect to MCP without profile (naked URI)
- List tools and resources
- Call tools with test inputs
- Understand output formats
- Design profile based on findings

**Exploit Phase:** Production usage
- Use curated profile
- Schema validation
- Fast (cached tool definitions)
- Reliable (versioned)

### Current State

**Exploit works, explore doesn't:**
- ✅ Can use profiles: `jn cat "@biomcp/search?gene=BRAF"`
- ❌ Can't explore without profile (naked URI not supported)
- ❌ No discovery commands: `jn mcp explore ...`
- ❌ No schema validation

### Proposed Commands

#### Exploration Commands

```bash
# Connect and list tools
jn mcp explore "mcp+uvx://biomcp-python/biomcp?command=run"

# Call tool directly (naked URI)
jn cat "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF"

# List tools from running server
jn mcp tools "mcp+uvx://biomcp-python/biomcp?command=run"

# Get tool schema
jn mcp schema "mcp+uvx://biomcp-python/biomcp?command=run" search
```

#### Profile Management Commands

```bash
# List all profiles
jn profile list --type mcp

# Show profile details
jn profile info @biomcp

# Validate profile against current MCP schema
jn profile validate @biomcp

# Update profile to match current schema
jn profile update @biomcp

# Create profile from exploration
jn profile create biomcp < profile.json
```

#### Schema Commands

```bash
# Show current schema hash for MCP
jn mcp hash "mcp+uvx://biomcp-python/biomcp?command=run"

# Compare profile schema with current
jn profile diff @biomcp
```

---

## Implementation Strategy

### Phase 1: Naked MCP URIs (Foundation)

**Goal:** Enable exploration without profiles

**Tasks:**
1. Implement `mcp+{launcher}://` URI parsing
2. Support uvx, npx, python, node launchers
3. Extract tool and params from query string
4. Update MCP plugin to handle naked URIs

**Effort:** 2-3 days

**Acceptance:**
```bash
jn cat "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF"
# Works without pre-existing profile
```

### Phase 2: Discovery Commands

**Goal:** Systematic exploration

**Tasks:**
1. `jn mcp explore <uri>` - List tools and resources
2. `jn mcp tools <uri>` - List just tools
3. `jn mcp schema <uri> <tool>` - Show tool schema

**Effort:** 2-3 days

**Acceptance:**
```bash
jn mcp explore "mcp+uvx://biomcp-python/biomcp?command=run"
# Returns JSON with all tools and schemas
```

### Phase 3: Schema Hashing

**Goal:** Detect changes

**Tasks:**
1. Implement `calculate_schema_hash()`
2. Add `schema_hash` field to profiles
3. Validate hash on profile use
4. Warn if mismatch

**Effort:** 1-2 days

**Acceptance:**
```bash
jn cat "@biomcp/search?gene=BRAF"
# Warns if schema changed since profile created
```

### Phase 4: Profile Management

**Goal:** Easy profile creation and updates

**Tasks:**
1. `jn profile create` - Save new profile
2. `jn profile update` - Update existing profile
3. `jn profile validate` - Check schema match
4. `jn profile diff` - Show changes

**Effort:** 3-4 days

**Acceptance:**
```bash
# Explore, design, save
jn mcp explore "mcp+uvx://..." > schema.json
# LLM designs profile
jn profile create biomcp < profile.json
# Profile saved and ready
```

### Phase 5: LLM-Guided Exploration

**Goal:** Automated profile creation flow

**Tasks:**
1. Document exploration workflow
2. Create prompts for LLM to follow
3. Test with real MCPs
4. Iterate on profile format

**Effort:** 2-3 days

**This is the key value-add:** LLM explores, understands, documents - not just auto-generating from schema.

---

## Open Questions

### 1. How aggressively to validate schemas?

**Options:**
- **Warn:** Show warning, continue (default)
- **Error:** Refuse to run if schema changed
- **Ignore:** Skip validation (fast but risky)

**Recommendation:** Configurable per profile, default to warn.

### 2. Should profiles cache tool outputs?

**Idea:** During exploration, cache sample outputs for documentation.

**Pros:**
- LLMs can see example outputs without calling MCP
- Faster profile inspection
- Helps understand output format

**Cons:**
- Profiles get large
- Outputs may be stale
- Privacy concerns (if outputs contain data)

**Recommendation:** Optional, off by default. Add `examples` field:

```json
{
  "tool": "search",
  "parameters": { ... },
  "examples": [
    {
      "input": {"gene": "BRAF"},
      "output_sample": "BRAF V600E is a common mutation..."
    }
  ]
}
```

### 3. How to handle output format changes?

**Problem:** MCP changes from text → JSON, or vice versa.

**Detection:** mimeType change or structure change.

**Recommendation:**
- Store `output_format` in profile
- Warn if mimeType changes
- LLM should re-explore and update profile

### 4. Naked URI for complex launchers?

**Problem:** Some MCPs need complex launch commands that don't fit in URI.

**Example:**
```bash
uv run --with package1 --with package2 command --flag1 --flag2=value subcommand
```

**Recommendation:** Fall back to minimal profile for complex cases. Naked URI for common cases (80%).

---

## Summary

### Current State
- ✅ MCP client works with profiles
- ✅ Both local and remote MCPs supported
- ❌ No naked access (exploration)
- ❌ No schema versioning
- ❌ No automated profile creation flow

### Proposed Enhancements

1. **Naked MCP URIs** - `mcp+uvx://package/command?params`
   - Enable exploration without pre-existing profile
   - Standard URI syntax
   - Support common launchers (uvx, npx, python, node)

2. **Discovery Flow** - Explore → Design → Create
   - LLM connects to MCP (naked URI)
   - LLM explores tools by calling them
   - LLM designs profile based on understanding
   - LLM saves profile with schema hash

3. **Schema Versioning** - MD5 hash of tool schemas
   - Calculate hash when profile created
   - Validate hash on profile use
   - Warn if schema changed
   - Auto-update or manual review

4. **Profile Management** - Commands for lifecycle
   - `jn mcp explore` - Connect and list tools
   - `jn profile create` - Save new profile
   - `jn profile update` - Update to new schema
   - `jn profile validate` - Check for changes

### Why This Matters

**Without versioning:**
- MCPs change silently
- Profiles break mysteriously
- Users confused by errors

**With versioning:**
- Changes detected immediately
- Clear error messages
- Easy update path

**Without naked access:**
- Must create profile before exploring
- Chicken-and-egg problem
- Manual, error-prone

**With naked access:**
- Explore first, profile later
- LLM-guided discovery
- Systematic documentation

### Next Steps

1. Implement naked MCP URI parsing
2. Build discovery commands
3. Add schema hashing
4. Test with real MCPs (BioMCP, Context7)
5. Iterate on profile format
6. Document LLM exploration workflow

---

## Appendix: MCP Protocol Details

### Does MCP Return JSON?

**Yes, with nuance:**

**Protocol level:** JSON-RPC 2.0
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "...",
        "mimeType": "text/plain"
      }
    ]
  }
}
```

**Content level:** Can be anything
- `mimeType: "text/plain"` - Plain text in `text` field
- `mimeType: "application/json"` - JSON string in `text` field
- `mimeType: "image/png"` - Base64 in `blob` field

**For JN:** We wrap everything in NDJSON records:
```json
{"type": "tool_result", "tool": "search", "text": "...", "mimeType": "text/plain"}
```

This is fine for streaming, filtering, and pipelines.

### Terminology: MCP vs JN

| MCP Term | MCP Meaning | JN Equivalent | JN Usage |
|----------|-------------|---------------|----------|
| Resource | Read-only data | Source | `jn cat "@mcp?resource=uri"` |
| Tool (read) | Call, get data | Source | `jn cat "@mcp/tool?params"` |
| Tool (write) | Call per record | Target | `echo {} \| jn put "@mcp/tool"` |

**Key insight:** MCP tools are dual-purpose in JN (source or target depending on usage).
