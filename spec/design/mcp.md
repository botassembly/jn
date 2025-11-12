# MCP Integration in JN

**Purpose:** Complete design for Model Context Protocol (MCP) integration
**Status:** Implemented (client mode with profiles), Discovery flow proposed
**Date:** 2025-11-12
**Related:** `spec/work/19-mcp-protocol.md`, `docs/mcp.md`

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Assessment](#current-state-assessment)
3. [What is MCP?](#what-is-mcp)
4. [Naked MCP Access (Priority)](#naked-mcp-access-priority)
5. [Inspect Command](#inspect-command)
6. [Self-Contained Plugin Refactor](#self-contained-plugin-refactor)
7. [Future: Plugin Discovery Contract](#future-plugin-discovery-contract)
8. [Future: Generic Discovery Flow](#future-generic-discovery-flow)
9. [Future: Schema Versioning](#future-schema-versioning)
10. [Implementation Roadmap](#implementation-roadmap)

---

## Executive Summary

**Current State:**
- ✅ MCP client works (read/write to MCP servers)
- ✅ Profile-based access functional
- ✅ Both local (uvx) and remote (npx) MCPs supported
- ❌ **BROKEN:** Plugin violates self-containment (imports `jn.profiles.mcp`)
- ❌ No naked protocol access (profiles required = chicken-and-egg)
- ❌ No inspect command for listing tools/resources

**Immediate Priority (Work Ticket #23):**
1. **Naked MCP URIs** - Access servers without profiles: `mcp+uvx://package/command?params`
2. **Inspect command** - List tools/resources: `jn inspect "mcp+uvx://..."`
3. **Vendor profile resolver** - Remove framework imports (~255 LOC into mcp_.py)
4. **Cat/head/tail support** - Call tools directly with naked URIs

**Future Work (Later Tickets):**
1. **Profile creation helpers** - Commands/templates for creating profiles
2. **Generic plugin contract** - explores()/validates()/versions() for all plugins
3. **Schema versioning** - Hash-based change detection
4. **Profile management** - Generic discovery system for MCP, HTTP, S3, etc.

**Key Insight:** Focus on naked access FIRST. Prove it works. Generalize LATER.

---

## Current State Assessment

### What Works Today

**File:** `jn_home/plugins/protocols/mcp_.py`

**Functionality:**
- ✅ Connects to MCP servers via stdio transport
- ✅ Calls tools with parameters
- ✅ Reads resources
- ✅ Lists tools/resources dynamically
- ✅ Batch writes (reuses connection)
- ✅ Proper cleanup (no resource leaks)
- ✅ Works with both local (uvx) and remote (npx) MCPs

**Tests:**
- ✅ 8 plugin tests passing
- ✅ 14 profile tests passing

### What's Broken

**Problem 1: Violates Self-Containment Rule**

**Current imports:**
```python
from mcp import ClientSession, StdioServerParameters  # OK - external dep
from mcp.client.stdio import stdio_client              # OK - external dep

from jn.profiles.mcp import resolve_profile_reference, ProfileError  # BROKEN - framework import
```

**Why this is bad:**
- Plugin can't run standalone (requires JN framework installed)
- Violates PEP 723 self-contained script principle
- Not portable - can't copy plugin elsewhere and run
- Breaks clean plugin/framework boundary

**Assessment:** The profile resolver (~255 LOC in `src/jn/profiles/mcp.py`) should be vendored into the plugin.

**Problem 2: Chicken-and-Egg (No Naked Access)**

**Current flow:**
1. Must create profile manually (`_meta.json` + tool definitions)
2. Then can use MCP server: `jn cat "@biomcp/search?gene=BRAF"`

**Missing:**
- Can't inspect MCP server before creating profile
- Can't call tools without profile
- Can't explore what's available

**Needed:**
- Naked URI support: `jn inspect "mcp+uvx://biomcp-python/biomcp?command=run"`
- Direct tool calls: `jn cat "mcp+uvx://...&tool=search&gene=BRAF"`

**Problem 3: No Inspect Command**

**Current workaround:**
```bash
jn cat "@biomcp?list=tools"  # Only works if profile exists
```

**Need:**
```bash
jn inspect "mcp+uvx://..."  # Works WITHOUT profile
```

**Terminology:** "inspect" is MCP ecosystem standard (not "explore").

### Resolution Strategy

**Recommended:** Vendor profile resolver into plugin (single-file or multi-file in same directory).

**Tradeoff:**
- ✅ Plugin becomes self-contained
- ✅ Portable and runs independently
- ✅ Honors plugin contract
- ❌ ~255 LOC duplicated
- ❌ Changes to core resolver won't auto-sync

**Decision:** Accept duplication for self-containment. This is the right architectural choice.

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

## Naked MCP Access (Priority)

### Goal

Enable MCP server access WITHOUT pre-existing profiles for exploration and experimentation.

### Proposed URI Syntax

**Format:** `mcp+{launcher}://{package}[/{command}]?{params}`

**Supported launchers:**
- `uvx` - UV tool runner (Python MCPs)
- `npx` - NPM package executor (Node MCPs)
- `python` - Direct Python script
- `node` - Direct Node script

**Examples:**
```bash
# UVX launcher (most common for Python MCPs)
mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF

# NPX launcher (most common for Node MCPs)
mcp+npx://@upstash/context7-mcp@latest?tool=search&library=fastapi

# Python launcher (local script)
mcp+python://./my_server.py?tool=fetch_data&id=123

# Node launcher (local script)
mcp+node://./server.js?tool=analyze&file=data.csv
```

### URI Parsing

**Implementation approach:**

```python
def parse_naked_mcp_uri(uri: str) -> tuple[dict, dict]:
    """Parse mcp+{launcher}://{package}?{params}.

    Returns:
        (server_config, tool_params)
    """
    # Split protocol
    protocol, rest = uri.split("://", 1)
    launcher = protocol.split("+")[1]  # "uvx", "npx", "python", "node"

    # Split package/path and query
    if "?" in rest:
        package_path, query_string = rest.split("?", 1)
        params = parse_qs(query_string)
    else:
        package_path = rest
        params = {}

    # Build server config based on launcher
    if launcher == "uvx":
        # mcp+uvx://biomcp-python/biomcp?command=run
        parts = package_path.split("/")
        command = params.pop("command", ["run"])[0]
        return {
            "command": "uv",
            "args": ["run", "--with", parts[0], parts[1], command],
            "transport": "stdio"
        }, params

    elif launcher == "npx":
        # mcp+npx://@upstash/context7-mcp@latest
        return {
            "command": "npx",
            "args": ["-y", package_path],
            "transport": "stdio"
        }, params

    elif launcher == "python":
        # mcp+python://./my_server.py
        return {
            "command": "python",
            "args": [package_path],
            "transport": "stdio"
        }, params

    elif launcher == "node":
        # mcp+node://./server.js
        return {
            "command": "node",
            "args": [package_path],
            "transport": "stdio"
        }, params

    else:
        raise ValueError(f"Unsupported launcher: {launcher}")
```

### Integration with reads()

**Update MCP plugin to handle both naked URIs and profiles:**

```python
def reads(url: str, **params) -> Iterator[dict]:
    """Read from MCP - supports naked URIs and profile references."""

    if url.startswith("mcp+"):
        # Naked URI: parse directly
        server_config, tool_params = parse_naked_mcp_uri(url)
        tool_params.update(params)  # Merge with kwargs

        # Extract operation from params
        if "tool" in tool_params:
            operation = {
                "type": "call_tool",
                "tool": tool_params.pop("tool")[0],
                "params": {k: v[0] if isinstance(v, list) else v
                          for k, v in tool_params.items()}
            }
        elif "resource" in tool_params:
            operation = {
                "type": "read_resource",
                "resource": tool_params.pop("resource")[0]
            }
        elif "list" in tool_params:
            list_type = tool_params.pop("list")[0]
            operation = {
                "type": "list_tools" if list_type == "tools" else "list_resources"
            }
        else:
            # Default: list resources
            operation = {"type": "list_resources"}

    else:
        # Profile reference: resolve as before (vendored function)
        server_config, operation = resolve_profile_reference(url, params)

    # Execute operation (existing logic)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(
            execute_mcp_operation(server_config, operation)
        )
        yield from results
    except Exception as e:
        yield error_record("mcp_error", str(e))
    finally:
        loop.close()
```

### Usage Examples

**Inspect tools:**
```bash
jn inspect "mcp+uvx://biomcp-python/biomcp?command=run"
```

**Call tool:**
```bash
jn cat "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF"
```

**First 10 results:**
```bash
jn head "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF"
```

**Pipe through filters:**
```bash
jn cat "mcp+uvx://..." | jn filter '.text | contains("Phase 3")' | jn put results.json
```

---

## Inspect Command

### Purpose

List tools and resources available from an MCP server without requiring a profile.

### Terminology

**"Inspect"** is MCP ecosystem standard (used by MCP CLI tools), not "explore" (generic term).

### Command Signature

```bash
jn inspect <uri> [--format json|text]
```

**Examples:**
```bash
# Inspect via naked URI (no profile required)
jn inspect "mcp+uvx://biomcp-python/biomcp?command=run"

# Inspect via profile reference (once profiles exist)
jn inspect "@biomcp"

# JSON output (for LLM/scripting)
jn inspect "mcp+uvx://..." --format json

# Text output (for humans, default)
jn inspect "mcp+uvx://..." --format text
```

### Implementation

**Add to MCP plugin:**

```python
def inspects(url: str, **config) -> dict:
    """List tools and resources from MCP server.

    This is the 'inspect' operation - shows what's available.
    Does NOT require a pre-existing profile.
    """
    if url.startswith("mcp+"):
        server_config, _ = parse_naked_mcp_uri(url)
    else:
        server_config, _ = resolve_profile_reference(url, {})

    # Connect to MCP server
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        server_params = StdioServerParameters(
            command=server_config["command"],
            args=server_config.get("args", []),
            env=server_config.get("env"),
        )

        read_stream, write_stream = await stdio_client(server_params)
        session = ClientSession(read_stream, write_stream)

        await session.initialize()

        # List tools and resources
        tools_result = await session.list_tools()
        resources_result = await session.list_resources()

        return {
            "server": extract_server_name(url),
            "transport": "stdio",
            "tools": [
                {
                    "name": tool.name,
                    "description": getattr(tool, "description", None),
                    "inputSchema": tool.inputSchema
                }
                for tool in tools_result.tools
            ],
            "resources": [
                {
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": getattr(resource, "description", None),
                    "mimeType": getattr(resource, "mimeType", None)
                }
                for resource in resources_result.resources
            ]
        }
    finally:
        # Cleanup
        loop.close()
```

**Add CLI command:** `src/jn/cli/commands/inspect.py`

```python
import click
import json

@click.command()
@click.argument('url')
@click.option('--format', type=click.Choice(['json', 'text']), default='text')
def inspect(url, format):
    """Inspect tools and resources available from a source.

    Works with MCP servers (and potentially other services in the future).

    Examples:
        jn inspect "mcp+uvx://biomcp-python/biomcp?command=run"
        jn inspect "@biomcp"  (once profile exists)
    """
    from jn.plugins.service import get_plugin_for_url

    # Find appropriate plugin
    plugin = get_plugin_for_url(url)

    # Check if plugin supports inspection
    if not hasattr(plugin, 'inspects'):
        click.echo(f"Error: Plugin does not support inspection", err=True)
        return 1

    # Call plugin's inspect function
    result = plugin.inspects(url)

    if format == 'json':
        click.echo(json.dumps(result, indent=2))
    else:
        # Pretty text output
        click.echo(f"\nServer: {result['server']}")
        click.echo(f"Transport: {result['transport']}\n")

        click.echo(f"Tools ({len(result['tools'])}):")
        for tool in result['tools']:
            desc = tool.get('description', 'No description')
            click.echo(f"  {tool['name']}: {desc}")

            if tool.get('inputSchema'):
                props = tool['inputSchema'].get('properties', {})
                required = tool['inputSchema'].get('required', [])
                if props:
                    click.echo(f"    Parameters:")
                    for param, schema in props.items():
                        req = " (required)" if param in required else ""
                        click.echo(f"      {param}{req}: {schema.get('description', '')}")

        click.echo(f"\nResources ({len(result['resources'])}):")
        for resource in result['resources']:
            desc = resource.get('description', 'No description')
            click.echo(f"  {resource['name']}: {desc}")
            click.echo(f"    URI: {resource['uri']}")
```

### Output Examples

**JSON output:**
```json
{
  "server": "biomcp",
  "transport": "stdio",
  "tools": [
    {
      "name": "search",
      "description": "Search biomedical resources",
      "inputSchema": {
        "type": "object",
        "properties": {
          "gene": {
            "type": "string",
            "description": "Gene symbol (e.g., BRAF, TP53)"
          },
          "disease": {
            "type": "string",
            "description": "Disease or condition name"
          }
        },
        "required": ["gene"]
      }
    }
  ],
  "resources": []
}
```

**Text output:**
```
Server: biomcp
Transport: stdio

Tools (3):
  search: Search biomedical resources
    Parameters:
      gene (required): Gene symbol (e.g., BRAF, TP53)
      disease: Disease or condition name
  trial_search: Search clinical trials
    Parameters:
      gene (required): Gene symbol
      phase: Trial phase (PHASE1, PHASE2, PHASE3)
  variant_search: Search genomic variants
    Parameters:
      gene (required): Gene symbol
      significance: Pathogenic, benign, etc.

Resources (0):
```

---

## Self-Contained Plugin Refactor

### Current Problem

**File:** `jn_home/plugins/protocols/mcp_.py`

**Problematic import:**
```python
from jn.profiles.mcp import resolve_profile_reference, ProfileError
```

**Why bad:**
- Couples plugin to framework internals
- Plugin can't run standalone
- Violates PEP 723 self-contained script principle
- Not portable

### Solution: Vendor Profile Resolver

**Copy ~255 LOC from `src/jn/profiles/mcp.py` into `mcp_.py`:**

**Functions to vendor:**
1. `ProfileError` class
2. `find_profile_paths()` - Search project/.jn, user/~/.local, bundled/JN_HOME
3. `substitute_env_vars()` / `substitute_env_vars_recursive()` - Expand ${VAR}
4. `load_hierarchical_profile()` - Merge _meta.json + tool.json
5. `list_server_tools()` - List tools in profile directory
6. `resolve_profile_reference()` - Parse @server/tool?query

**Implementation options:**

**Option 1: Single-file plugin (recommended)**
- Copy all functions into `mcp_.py`
- Keep as one PEP 723 script
- Pros: Simple, self-contained
- Cons: Large file (~500 LOC total)

**Option 2: Multi-file in same directory**
- Main: `mcp_.py` (PEP 723 script)
- Helper: `mcp_profiles.py` (no PEP 723, local import)
- Pros: Cleaner organization
- Cons: Slightly more complex

**Recommendation:** Single-file for simplicity.

### After Refactor

**No framework imports:**
```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# All profile resolver logic is now in this file (vendored)
```

**Plugin becomes truly self-contained:**
```bash
# Can run standalone with uv
uv run --script jn_home/plugins/protocols/mcp_.py --mode read "@biomcp/search?gene=BRAF"
```

**Remove from plugin checker whitelist:**
- No more `framework_import` warning
- No more `missing_dependency ('jn')` warning

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

**Need:** Detect when service schemas change, update profiles accordingly.

**This is not MCP-specific** - same problem for HTTP APIs, S3 buckets, Gmail, any service with profiles.

---

## Plugin Discovery Contract

### The Problem with MCP-Specific Commands

**What I initially proposed:**
```bash
jn mcp explore <uri>      # Discover MCP tools
jn mcp tools <uri>        # List MCP tools
jn mcp schema <uri>       # Show MCP schema
```

**The issue:** If we add MCP-specific commands, we'll need:
- `jn http explore <api>` - Discover HTTP endpoints
- `jn s3 explore <bucket>` - Discover S3 contents
- `jn gmail explore` - Discover Gmail labels/filters
- `jn {plugin} explore` - For every plugin with profiles

**This doesn't scale.** We'd have N discovery systems instead of one generic system.

### The Solution: Plugin Contract Extension

**Current plugin contract:**
```python
def reads(url: str, **config) -> Iterator[dict]:
    """Read from source, yield NDJSON records."""

def writes(url: str | None = None, **config) -> None:
    """Read NDJSON from stdin, write to target."""
```

**Proposed extension:**
```python
def explores(url: str, **config) -> dict:
    """Discover what's available from this service.

    Returns schema of discoverable items:
    - For MCP: tools, resources, their parameters
    - For HTTP: endpoints, methods, parameters
    - For S3: buckets, keys, metadata
    - For Gmail: labels, filters, search operators

    This is the "universe" behind a profile.
    """

def validates(profile: dict, **config) -> ValidationResult:
    """Check if profile matches current service state.

    Returns:
        ValidationResult with status (valid/changed/error) and details
    """

def versions(url: str, **config) -> str:
    """Calculate version hash of service schema.

    Returns hash string that changes when discoverable schema changes.
    Used for detecting if service changed since profile created.
    """
```

### Generic Discovery Commands

**With plugin contract, commands become generic:**

```bash
# Explore ANY service via profile reference or naked URI
jn profile explore @biomcp
jn profile explore "mcp+uvx://biomcp-python/biomcp?command=run"
jn profile explore @genomoncology
jn profile explore "https://api.genomoncology.com/openapi.json"

# Validate ANY profile
jn profile validate @biomcp
jn profile validate @genomoncology

# Show version hash
jn profile version @biomcp
jn profile version @genomoncology

# Create profile from exploration
jn profile create biomcp < profile.json

# Update profile when service changes
jn profile update @biomcp
```

**Same commands work for all plugins.**

### How It Works

**User runs:**
```bash
jn profile explore @biomcp
```

**Framework does:**
1. Parse `@biomcp` → Look for existing profile
2. If found: Load `_meta.json`, get server config
3. If not found: Treat as naked URI (see next section)
4. Determine plugin from protocol/pattern (`mcp_.py` matches `@` pattern)
5. Call `plugin.explores(config)` function
6. Plugin connects to service, discovers what's available
7. Return structured schema to user/LLM

**LLM receives:**
```json
{
  "plugin": "mcp",
  "service": "biomcp",
  "version_hash": "a3f5b8c2e1f4...",
  "discoverable": {
    "tools": [
      {
        "name": "search",
        "description": "Search biomedical resources",
        "parameters": {
          "gene": {"type": "string", "required": true},
          "disease": {"type": "string", "required": false}
        }
      },
      {
        "name": "trial_search",
        "parameters": { ... }
      }
    ],
    "resources": [ ... ]
  }
}
```

### Plugin-Specific Implementation

**Each plugin implements the contract differently:**

#### MCP Plugin

```python
def explores(url: str, **config) -> dict:
    """Connect to MCP server, list tools and resources."""
    server_config, _ = resolve_profile_reference(url, {})

    # Connect to MCP server
    session = connect_mcp_server(server_config)

    # Query available tools and resources
    tools_result = await session.list_tools()
    resources_result = await session.list_resources()

    return {
        "plugin": "mcp",
        "service": extract_service_name(url),
        "version_hash": calculate_mcp_schema_hash(tools_result.tools),
        "discoverable": {
            "tools": [serialize_tool(t) for t in tools_result.tools],
            "resources": [serialize_resource(r) for r in resources_result.resources]
        }
    }

def versions(url: str, **config) -> str:
    """Calculate MD5 hash of MCP tool schemas."""
    tools = explores(url, **config)["discoverable"]["tools"]
    return calculate_mcp_schema_hash(tools)

def validates(profile: dict, **config) -> ValidationResult:
    """Check if MCP server schema matches profile."""
    current_hash = versions(profile["_meta"]["server_ref"], **config)
    expected_hash = profile.get("schema_hash")

    if expected_hash and current_hash != expected_hash:
        return ValidationResult(status="changed", details={
            "expected": expected_hash,
            "current": current_hash,
            "message": "MCP tool schemas have changed"
        })

    return ValidationResult(status="valid")
```

#### HTTP Plugin

```python
def explores(url: str, **config) -> dict:
    """Fetch OpenAPI spec or explore API endpoints."""
    # Option 1: OpenAPI/Swagger spec provided
    if url.endswith("/openapi.json") or url.endswith("/swagger.json"):
        spec = fetch_openapi_spec(url)
        return {
            "plugin": "http",
            "service": extract_domain(url),
            "version_hash": hash_openapi_spec(spec),
            "discoverable": {
                "endpoints": parse_openapi_endpoints(spec),
                "schemas": spec.get("components", {}).get("schemas", {})
            }
        }

    # Option 2: Explore by crawling (less reliable)
    return explore_api_by_crawling(url)

def versions(url: str, **config) -> str:
    """Hash OpenAPI spec or endpoint signatures."""
    spec = explores(url, **config)
    return hash_openapi_endpoints(spec["discoverable"]["endpoints"])

def validates(profile: dict, **config) -> ValidationResult:
    """Check if API schema matches profile."""
    # Similar to MCP, compare hashes
    pass
```

#### S3 Plugin

```python
def explores(url: str, **config) -> dict:
    """List bucket contents and structure."""
    bucket, prefix = parse_s3_url(url)

    s3_client = boto3.client('s3')
    objects = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

    return {
        "plugin": "s3",
        "service": bucket,
        "version_hash": None,  # S3 contents change frequently, no stable hash
        "discoverable": {
            "keys": [obj["Key"] for obj in objects.get("Contents", [])],
            "patterns": infer_key_patterns(objects),
            "sample_metadata": get_sample_metadata(objects)
        }
    }

def versions(url: str, **config) -> str:
    """S3 doesn't version - could hash bucket structure patterns."""
    return None  # Or hash common prefixes/patterns

def validates(profile: dict, **config) -> ValidationResult:
    """Check if bucket exists and is accessible."""
    # Different from MCP - not about schema, about access
    pass
```

### Why This Design is Better

**Scalability:**
- ✅ One discovery system works for all plugins
- ✅ Plugins define their own discoverable schema
- ✅ No plugin-specific top-level commands

**Consistency:**
- ✅ Same commands work everywhere: `jn profile explore`, `validate`, `version`
- ✅ Same profile structure across plugins (with plugin-specific fields)
- ✅ Same workflow: explore → design → create → validate

**Extensibility:**
- ✅ New plugins automatically get discovery support
- ✅ Plugin defines what's meaningful to discover
- ✅ Plugin defines how to version/validate

**Flexibility:**
- ✅ MCP discovers tools (function-like)
- ✅ HTTP discovers endpoints (REST-like)
- ✅ S3 discovers keys (hierarchical)
- ✅ Each returns what makes sense for that service

---

## Naked Protocol Access

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

## Generic Discovery Flow

### Goal: Explore Service → Design Profile → Validate

**Works for all plugins:** MCP, HTTP, S3, Gmail, etc.

**Current problem:** Profiles are manually created without systematic exploration.

### Universal Flow

**Phase 1: Explore (via plugin's `explores()` function)**

```bash
# Explore ANY service - framework calls appropriate plugin
jn profile explore "mcp+uvx://biomcp-python/biomcp?command=run"
jn profile explore "https://api.genomoncology.com/openapi.json"
jn profile explore "s3://my-bucket/data/"
```

**What happens:**
1. Parse URI, determine plugin (mcp_, http_, s3_)
2. Call `plugin.explores(uri, config)`
3. Plugin connects to service
4. Plugin returns structured discovery data
5. Output to user/LLM as JSON

**Example output (MCP):**
```json
{
  "plugin": "mcp",
  "service": "biomcp",
  "version_hash": "a3f5b8c2e1f4...",
  "discoverable": {
    "tools": [
      {
        "name": "search",
        "description": "Search biomedical resources",
        "parameters": {
          "gene": {"type": "string", "required": true},
          "disease": {"type": "string", "required": false}
        }
      }
    ],
    "resources": []
  }
}
```

**Example output (HTTP API):**
```json
{
  "plugin": "http",
  "service": "genomoncology.com",
  "version_hash": "f7d3a1e9...",
  "discoverable": {
    "endpoints": [
      {
        "path": "/alterations",
        "method": "GET",
        "parameters": {
          "gene": {"type": "string", "in": "query"},
          "mutation_type": {"type": "string", "in": "query"}
        }
      },
      {
        "path": "/trials",
        "method": "GET",
        "parameters": { ... }
      }
    ]
  }
}
```

### Phase 2: LLM Experimentation

**LLM reviews schema, calls endpoints/tools to understand behavior:**

**For MCP:**
```bash
# Test tool with different parameters
jn cat "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF"
jn cat "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=BRAF&disease=melanoma"
jn cat "mcp+uvx://biomcp-python/biomcp?command=run&tool=search&gene=EGFR"

# LLM observes:
# - Returns plain text (not structured JSON)
# - gene param is required
# - disease param is optional but useful
# - Output is prose suitable for LLM consumption
```

**For HTTP API:**
```bash
# Test endpoints with different parameters
jn cat "https://api.genomoncology.com/alterations?gene=BRAF&limit=5"
jn cat "https://api.genomoncology.com/alterations?gene=EGFR&mutation_type=Missense&limit=5"
jn cat "https://api.genomoncology.com/trials?gene=BRAF&phase=PHASE3"

# LLM observes:
# - Returns paginated JSON with {results: [...], pagination: {...}}
# - limit param controls page size (default 100)
# - Fields: gene, mutation_type, biomarker are filters
# - Response time ~500ms for typical query
```

**For S3:**
```bash
# Test reading from bucket
jn cat "s3://my-data-bucket/raw-data/2024/*.csv"
jn cat "s3://my-data-bucket/processed/summaries/*.json"

# LLM observes:
# - Bucket has predictable date-based structure
# - Raw data in CSV format (large files 100MB+)
# - Processed data in JSON (smaller, 1-10MB)
# - Access requires AWS credentials in env
```

**Key point:** LLM doesn't just read the schema - it **tries things** to understand actual behavior.

### Phase 3: Profile Design

**LLM designs profile based on exploration - structure varies by plugin type:**

**MCP Profile Example:**
```json
{
  "plugin": "mcp",
  "server": "biomcp",
  "description": "BioMCP: Biomedical data",
  "connection": {
    "command": "uv",
    "args": ["run", "--with", "biomcp-python", "biomcp", "run"],
    "transport": "stdio"
  },
  "schema_hash": "a3f5b8c2...",
  "schema_updated": "2025-11-12",
  "tools": {
    "search": {
      "parameters": {"gene": {"required": true}, "disease": {}},
      "output_format": "text/plain",
      "notes": "Returns prose, not JSON. Good for LLM consumption."
    }
  },
  "tested_with": ["search?gene=BRAF", "search?gene=EGFR&disease=lung"]
}
```

**HTTP Profile Example:**
```json
{
  "plugin": "http",
  "api": "genomoncology",
  "description": "GenomOncology clinical data API",
  "connection": {
    "base_url": "https://api.genomoncology.com",
    "headers": {"Authorization": "Token ${API_KEY}"},
    "timeout": 60
  },
  "schema_hash": "f7d3a1e9...",
  "schema_updated": "2025-11-12",
  "endpoints": {
    "alterations": {
      "path": "/alterations",
      "method": "GET",
      "parameters": {"gene": {}, "mutation_type": {}, "limit": {"default": 100}},
      "output_format": "application/json",
      "pagination": {"type": "cursor", "field": "next_cursor"},
      "notes": "Returns paginated results. Use limit=5 for testing."
    }
  },
  "tested_with": ["alterations?gene=BRAF&limit=5", "trials?gene=BRAF"]
}
```

**S3 Profile Example:**
```json
{
  "plugin": "s3",
  "bucket": "my-data-bucket",
  "description": "Production data warehouse",
  "connection": {
    "region": "us-west-2",
    "credentials": "${AWS_ACCESS_KEY_ID}/${AWS_SECRET_ACCESS_KEY}"
  },
  "schema_hash": null,  // S3 contents change frequently
  "structure": {
    "raw-data": {"pattern": "raw-data/YYYY/MM/*.csv", "format": "csv", "size": "large"},
    "processed": {"pattern": "processed/summaries/*.json", "format": "json", "size": "small"}
  },
  "notes": "Raw data is large (100MB+). Use processed/ for quick access.",
  "tested_with": ["raw-data/2024/11/*.csv", "processed/summaries/*.json"]
}
```

**Universal profile fields:**
- `plugin` - Which plugin this is for
- `schema_hash` - Version hash (null if not applicable)
- `schema_updated` - When profile was created/updated
- `notes` - LLM observations about behavior
- `tested_with` - Example queries that worked

**Plugin-specific fields:**
- MCP: `tools`, `connection.command`
- HTTP: `endpoints`, `connection.base_url`
- S3: `structure`, `connection.region`

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
