# MCP Integration in JN - Complete Design

**Purpose:** Comprehensive design for Model Context Protocol (MCP) integration in JN
**Status:** Implemented (client mode), Discovery CLI pending
**Date:** 2025-11-12
**Related:** `spec/design/mcp-assessment.md`, `spec/work/19-mcp-protocol.md`, `docs/mcp.md`

---

## Table of Contents

1. [Overview](#overview)
2. [What is MCP?](#what-is-mcp)
3. [Why MCP in JN?](#why-mcp-in-jn)
4. [Architecture](#architecture)
5. [Profile System](#profile-system)
6. [Usage Patterns](#usage-patterns)
7. [Explore vs Exploit](#explore-vs-exploit)
8. [Terminology Mapping](#terminology-mapping)
9. [Implementation Status](#implementation-status)
10. [Future Work](#future-work)

---

## Overview

**Model Context Protocol (MCP)** is an open protocol that allows AI applications to securely access external data sources and tools. JN integrates with MCP as a **client**, enabling pipelines to read from and write to MCP servers.

**Key Design Principles:**

1. **Profiles are required** - MCPs have no standard URL scheme, so profiles define how to launch servers
2. **Source and target usage** - MCP tools can be used as both data sources (read) and targets (write)
3. **Profile-based curation** - Expose only the tools you care about with pre-filled defaults
4. **Explore-then-exploit** - Discover tools first, then use them in production pipelines
5. **NDJSON everywhere** - MCP responses wrapped in NDJSON records for streaming

---

## What is MCP?

### MCP Specification

**Official Spec:** https://modelcontextprotocol.io/

MCP defines four core primitives:

1. **Resources** - Static or dynamic data sources (files, DB results, documents)
   - **READ-ONLY** - Expose data to clients
   - URI-addressed: `resource://domain/path`
   - Example: `resource://trials/NCT12345`

2. **Tools** - Invokable functions with parameters
   - **CALLABLE** - Execute actions, return results
   - Schema-defined parameters (JSON Schema)
   - Example: `search(gene="BRAF", disease="melanoma")`

3. **Prompts** - Templates for LLM interactions
   - Pre-defined conversation starters
   - Not currently used in JN

4. **Sampling** - LLM completion requests
   - Servers can request LLM completions
   - Not relevant for JN (JN provides data TO LLMs, not from them)

### MCP Transports

MCP supports multiple transport layers:

- **stdio** - Standard input/output (most common, used by JN)
- **HTTP/SSE** - HTTP with Server-Sent Events
- **WebSocket** - Real-time bidirectional communication

**JN currently supports:** stdio only

---

## Why MCP in JN?

### Problem: Fragmented Data Access

AI agents need access to:
- Biomedical databases (clinical trials, genomics)
- Code documentation (up-to-date library docs)
- Local system access (files, shell commands)
- External APIs (weather, financial data, etc.)

**Without MCP:** Each data source needs a custom plugin. No standardization.

**With MCP:** Standard protocol for data access. One MCP plugin connects to many servers.

### JN's Role: Data Pipeline for AI

**JN as MCP Client:**
```
MCP Server → JN → Transform → Output
  (data)     (pipeline)  (filter)  (format)
```

**Example:**
```bash
# Get biomedical data from MCP, filter, export
jn cat "@biomcp/search?gene=BRAF" | \
  jn filter '.text | contains("Phase 3")' | \
  jn put trials.csv
```

### Benefits of MCP Integration

1. **Standardization** - One protocol for many data sources
2. **Ecosystem** - Leverage existing MCP servers (BioMCP, Context7, etc.)
3. **AI-Native** - Designed for agent workflows
4. **Extensibility** - New MCP servers added via profiles, no code changes

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                      JN Framework                            │
├─────────────────────────────────────────────────────────────┤
│  Addressability:  @biomcp/search?gene=BRAF                  │
│        ↓                                                     │
│  Profile System:  Load biomcp/_meta.json + search.json      │
│        ↓                                                     │
│  MCP Plugin:      Start server, connect via stdio           │
│        ↓                                                     │
│  MCP Client SDK:  Call tool with parameters                 │
│        ↓                                                     │
│  NDJSON Output:   Stream results as JSON records            │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server (External)                     │
├─────────────────────────────────────────────────────────────┤
│  Launch:   uv run biomcp run  (or)  npx @upstash/context7  │
│  Protocol: stdio                                             │
│  Tools:    search, trial_search, variant_search             │
└─────────────────────────────────────────────────────────────┘
```

### File Structure

```
src/jn/
  profiles/
    mcp.py                    # Profile resolution system

jn_home/
  plugins/
    protocols/
      mcp_.py                 # MCP plugin implementation
  profiles/
    mcp/
      biomcp/
        _meta.json            # Server launch config
        search.json           # Tool definition (optional)
        trial_search.json
        variant_search.json
      context7/
        _meta.json
        search.json
      desktop-commander/
        _meta.json
        execute.json
```

### Data Flow: Read Mode

```bash
jn cat "@biomcp/search?gene=BRAF"
```

**Step-by-step:**

1. **Address Parsing** - Framework recognizes `@biomcp/search` pattern
2. **Plugin Selection** - `^@[a-zA-Z0-9_-]+` matches MCP plugin
3. **Profile Resolution** - `resolve_profile_reference("@biomcp/search", {"gene": "BRAF"})`
   - Load `biomcp/_meta.json` (server config)
   - Load `biomcp/search.json` (tool definition)
   - Merge params from query string
4. **Server Launch** - `subprocess.Popen(["uv", "run", "--with", "biomcp-python", "biomcp", "run"])`
5. **MCP Connection** - stdio_client connects to server process
6. **Tool Call** - `session.call_tool("search", {"gene": "BRAF"})`
7. **Response Handling** - Parse MCP response, wrap in NDJSON
8. **Stream Output** - Yield records to stdout

### Data Flow: Write Mode

```bash
echo '{"gene": "BRAF"}' | jn put "@biomcp/search"
```

**Key difference:** Reuses single MCP connection for all input records.

**Step-by-step:**

1. **Profile Resolution** - Same as read mode
2. **Server Launch** - Start once, reuse for all records
3. **Read stdin** - Parse NDJSON records from stdin
4. **For each record:**
   - Extract parameters from record fields
   - Call tool with parameters
   - Output result as NDJSON
5. **Cleanup** - Close connection when stdin ends

**Performance:** Avoids reconnecting for each record (resource leak prevention).

---

## Profile System

### Why Profiles are Required

**Unlike HTTP or S3, MCP has no standard URL scheme.**

**HTTP:** `https://api.example.com/endpoint` (self-contained)
**S3:** `s3://bucket/key` (self-contained)
**MCP:** ??? (no standard - each server launches differently)

**Examples of MCP launch commands:**
- BioMCP: `uv run --with biomcp-python biomcp run`
- Context7: `npx -y @upstash/context7-mcp@latest`
- Custom: `python my_server.py` or `node server.js`

**Profiles define how to launch each MCP server.**

### Profile Structure

#### Minimal Profile: _meta.json Only

**File:** `profiles/mcp/myserver/_meta.json`

```json
{
  "command": "python",
  "args": ["./my_server.py"],
  "description": "My custom MCP server",
  "transport": "stdio"
}
```

**Usage:**
```bash
jn cat "@myserver?list=tools"           # List tools dynamically
jn cat "@myserver?tool=search&q=test"   # Call tool directly
```

**When to use:** Exploration, simple servers, don't want to pre-define tools.

#### Full Profile: _meta.json + Tool Definitions

**Files:**
```
profiles/mcp/biomcp/
  _meta.json           # Server config (required)
  search.json          # Tool definition
  trial_search.json    # Tool definition
  variant_search.json  # Tool definition
```

**_meta.json:**
```json
{
  "command": "uv",
  "args": ["run", "--with", "biomcp-python", "biomcp", "run"],
  "description": "BioMCP: Biomedical Model Context Protocol",
  "transport": "stdio"
}
```

**search.json:**
```json
{
  "tool": "search",
  "description": "Search biomedical resources (trials, articles, variants)",
  "parameters": {
    "gene": {
      "type": "string",
      "description": "Gene symbol (e.g., BRAF, TP53)"
    },
    "disease": {
      "type": "string",
      "description": "Disease or condition name"
    },
    "variant": {
      "type": "string",
      "description": "Specific variant notation"
    }
  }
}
```

**Usage:**
```bash
jn cat "@biomcp/search?gene=BRAF"               # Named tool
jn cat "@biomcp/trial_search?condition=Melanoma"
```

**When to use:** Production, curated subset, documentation, LLM discovery.

### Profile Search Order

Profiles are searched in priority order:

1. **Project:** `.jn/profiles/mcp/` (highest priority)
2. **User:** `~/.local/jn/profiles/mcp/`
3. **Bundled:** `jn_home/profiles/mcp/` (lowest priority)

**Override bundled profiles:** Create same-named profile in project/user location.

### Environment Variable Substitution

**Syntax:** `${VAR_NAME}` in strings

**Example:**
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

**Usage:**
```bash
export MY_API_KEY="secret123"
export MY_BASE_URL="https://api.example.com"
jn cat "@myserver/search?q=test"
```

### Pre-Filled Defaults (Curation)

**Purpose:** Create multiple curated profiles from the same tool with different defaults.

**Example: BRAF Trials**

**File:** `profiles/mcp/biomcp/braf-trials.json`

```json
{
  "tool": "trial_search",
  "defaults": {
    "gene": "BRAF",
    "status": "recruiting"
  },
  "parameters": {
    "disease": {
      "type": "string",
      "description": "Disease or condition"
    },
    "phase": {
      "type": "string",
      "description": "Trial phase (PHASE1, PHASE2, PHASE3)"
    }
  },
  "description": "Recruiting clinical trials for BRAF mutations"
}
```

**Usage:**
```bash
# Pre-filled: gene=BRAF, status=recruiting
jn cat "@biomcp/braf-trials?disease=melanoma"

# Override defaults if needed
jn cat "@biomcp/braf-trials?gene=EGFR&status=active"
```

**Parameter merge order:**
1. Tool defaults (lowest priority)
2. Profile defaults
3. Query string parameters (highest priority)

**Use cases for defaults:**
- Common filters (status, type, etc.)
- Enum pre-selection (ascending vs descending)
- Curated workflows (braf-trials vs egfr-trials)

---

## Usage Patterns

### Reading from MCP (Source)

**Basic usage:**
```bash
jn cat "@biomcp/search?gene=BRAF"
```

**With filters:**
```bash
jn cat "@biomcp/search?gene=BRAF" | \
  jn filter '.text | contains("Phase 3")' | \
  jn put results.json
```

**Multiple parameters:**
```bash
jn cat "@biomcp/search?gene=BRAF&disease=Melanoma&variant=V600E"
```

**List operations:**
```bash
# List all tools
jn cat "@biomcp?list=tools"

# List all resources
jn cat "@biomcp?list=resources"
```

**Read specific resource:**
```bash
jn cat "@biomcp?resource=resource://trials/NCT12345"
```

### Writing to MCP (Target)

**Streaming records to tool:**
```bash
# Single record
echo '{"gene": "BRAF"}' | jn put "@biomcp/search"

# Multiple records (batch)
jn cat genes.csv | \
  jn filter '{gene: .symbol}' | \
  jn put "@biomcp/variant_search"
```

**Key feature:** Connection reused across all records (no reconnection overhead).

### Multi-Source Pipelines

**Mix MCP with other sources:**
```bash
jn cat \
  local_data.csv \
  "@biomcp/search?gene=BRAF" \
  "@context7/search?library=fastapi" \
  "https://api.example.com/data.json" \
  | jn filter '.score > 0.8' \
  | jn put combined.json
```

### Cross-MCP Workflows

**Chain multiple MCPs:**
```bash
# Get code docs, extract gene names, search biomedical data
jn cat "@context7/search?library=genomics" | \
  jn filter '.text | match("([A-Z]{3,})"; "g") | .captures[].string' | \
  jn filter '{gene: .}' | \
  jn put "@biomcp/variant_search" | \
  jn put variants.csv
```

---

## Explore vs Exploit

### The Two Phases

**Explore Phase: Discovery**
- What MCPs do I have access to?
- What tools does each MCP provide?
- What parameters does each tool accept?
- How do I use this tool?

**Exploit Phase: Production**
- Use known tools in pipelines
- Reliable, repeatable workflows
- Performance-optimized (cached profiles)

### Current Status

**Exploit Phase: ✅ Fully Working**

```bash
# Known profiles, use directly
jn cat "@biomcp/search?gene=BRAF"
jn cat "@context7/search?library=mcp"
echo '{"gene": "TP53"}' | jn put "@biomcp/variant_search"
```

**Explore Phase: ⚠️ Manual Workarounds**

```bash
# Current: Manual file browsing
ls -la tests/jn_home/profiles/mcp/
cat tests/jn_home/profiles/mcp/biomcp/_meta.json
cat tests/jn_home/profiles/mcp/biomcp/search.json

# Dynamic: Query MCP directly
jn cat "@biomcp?list=tools"
jn cat "@biomcp?list=resources"
```

**Problem:** No structured discovery commands. Users and LLMs must manually read files or parse dynamic output.

### Proposed: Profile Discovery CLI

**Design:** See `spec/design/profile-cli.md` for full specification.

**Key commands:**

#### 1. List All Profiles

```bash
jn profile list
jn profile list --type mcp
jn profile list --format json    # For LLM consumption
```

**Output:**
```
MCP Profiles:
  @biomcp/search              - Search biomedical resources
  @biomcp/trial_search        - Clinical trials search
  @biomcp/variant_search      - Genomic variants search
  @context7/search            - Code documentation search
  @desktop-commander/execute  - Execute shell commands

HTTP Profiles:
  @genomoncology/alterations  - Genetic alterations endpoint
  ...
```

#### 2. Inspect Specific Profile

```bash
jn profile info @biomcp/search
jn profile info @biomcp/search --format json
```

**Output:**
```
Profile: @biomcp/search
Type: MCP tool
Server: biomcp
Location: jn_home/profiles/mcp/biomcp/search.json

Server Configuration:
  Command: uv run --with biomcp-python biomcp run
  Transport: stdio

Tool: search
Description: Search biomedical resources (trials, articles, variants)

Parameters:
  gene     (string) - Gene symbol (e.g., BRAF, TP53)
  disease  (string) - Disease or condition name
  variant  (string) - Specific variant notation

Examples:
  jn cat "@biomcp/search?gene=BRAF"
  jn cat "@biomcp/search?gene=BRAF&disease=Melanoma"
```

#### 3. MCP-Specific Introspection

```bash
# List tools from running server (dynamic)
jn mcp tools @biomcp

# List resources from server
jn mcp resources @biomcp

# Show tool schema
jn mcp schema @biomcp search
```

**Difference:**
- `jn profile info` - Static (reads profile files, fast)
- `jn mcp tools` - Dynamic (connects to server, current, slow)

### LLM Workflow Example

**Session 1: Explore**
```python
# Discover available MCPs
llm> jn profile list --type mcp --format json
{
  "@biomcp": ["search", "trial_search", "variant_search"],
  "@context7": ["search"],
  "@desktop-commander": ["execute"]
}

# Inspect specific tool
llm> jn profile info @biomcp/search --format json
{
  "tool": "search",
  "parameters": {
    "gene": {"type": "string", "description": "..."},
    ...
  }
}

# Create knowledge: Store in profile cache or context
```

**Session 2: Exploit**
```python
# Use cached knowledge
llm> "Find BRAF trials"
assistant> jn cat "@biomcp/search?gene=BRAF&disease=melanoma"
```

**Key insight:** Profiles act as cached knowledge. Discovery CLI populates cache. Subsequent sessions use cached profiles directly.

---

## Terminology Mapping

### MCP Terms vs JN Terms

| MCP Concept | MCP Usage | JN Equivalent | JN Usage |
|-------------|-----------|---------------|----------|
| **Resource** | Read-only data | **Source** | `jn cat "@mcp?resource=uri"` |
| **Tool** (read) | Call function, get data | **Source** | `jn cat "@mcp/tool?params"` |
| **Tool** (write) | Call function per record | **Target** | `echo '{}' \| jn put "@mcp/tool"` |
| Prompt | LLM template | N/A | Not implemented |
| Sampling | LLM completion | N/A | Not relevant |

### Key Insight: Tools are Dual-Purpose

**MCP Tools can be BOTH sources and targets in JN:**

**As Source (read mode):**
```bash
jn cat "@biomcp/search?gene=BRAF"
# Calls tool once, yields results as NDJSON stream
```

**As Target (write mode):**
```bash
echo '{"gene": "BRAF"}' | jn put "@biomcp/search"
echo '{"gene": "TP53"}' | jn put "@biomcp/search"
# Calls tool once PER input record
```

### Resources are Source-Only

**MCP Resources are read-only:**
```bash
jn cat "@biomcp?resource=resource://trials/NCT12345"
```

**Cannot write to resources** (MCP spec doesn't support this).

### Terminology in Code

**Profile files use MCP terminology:**
```json
{
  "tool": "search",         // MCP term
  "resource": "uri",        // MCP term
  "parameters": { ... }     // MCP schema
}
```

**Why:** Matches MCP specification, easier to auto-generate from schema.

**JN framework maps internally:**
- MCP tool → JN source (if used with `jn cat`)
- MCP tool → JN target (if used with `jn put`)
- MCP resource → JN source (always)

**Documentation should clarify this mapping.**

---

## Implementation Status

### ✅ Implemented (Client Mode)

**Files:**
- `src/jn/profiles/mcp.py` - Profile resolution system
- `jn_home/plugins/protocols/mcp_.py` - MCP plugin
- `tests/cli/test_mcp_plugin.py` - Plugin tests (8 passing)
- `tests/profiles/test_mcp_profiles.py` - Profile tests (14 passing)

**Features:**
- ✅ Profile-based MCP server configuration
- ✅ Tool calling (read and write modes)
- ✅ Resource reading
- ✅ List operations (tools, resources)
- ✅ Environment variable substitution
- ✅ Hierarchical profile search (project > user > bundled)
- ✅ Connection reuse for write mode (performance)
- ✅ Proper resource cleanup (no leaks)
- ✅ Error handling (NDJSON error records)
- ✅ stdio transport
- ✅ Works with both local (uv) and remote (npx) MCPs

**Bundled Profiles:**
- BioMCP - Biomedical data (trials, genomics, literature)
- Context7 - Code documentation (up-to-date library docs)
- Desktop Commander - Local file/shell access

**Usage:**
```bash
jn cat "@biomcp/search?gene=BRAF"
jn cat "@context7/search?library=mcp"
echo '{"gene": "TP53"}' | jn put "@biomcp/variant_search"
```

### ❌ Not Implemented

**Profile Discovery CLI:**
- `jn profile list` - List all profiles
- `jn profile info <reference>` - Inspect profile details
- `jn profile tree` - Visual hierarchy
- `jn profile test <reference>` - Validate profile works

**Design exists:** `spec/design/profile-cli.md`

**MCP Introspection:**
- `jn mcp tools @server` - List tools from running server
- `jn mcp resources @server` - List resources
- `jn mcp schema @server tool` - Show tool schema

**MCP Server Mode:**
- Expose JN data sources to other MCP clients
- Not currently needed (JN is primarily a data processing tool, not a data provider)

**Additional Transports:**
- HTTP/SSE transport
- WebSocket transport
- Currently only stdio supported

**Prompt/Sampling Support:**
- MCP prompts feature
- MCP sampling feature
- Not currently relevant for JN's use case

---

## Future Work

### Priority 1: Profile Discovery CLI (MVP)

**Goal:** Enable explore phase for users and LLMs

**Tasks:**
1. Implement `jn profile list` (text + JSON output)
2. Implement `jn profile info <reference>` (detailed inspection)
3. Add filtering: `--type mcp`, `--namespace biomcp`

**Effort:** 2-3 days

**Why first:** Solves biggest current pain point (discovery), enables LLM workflows.

**Acceptance criteria:**
- LLM can discover all available MCP profiles in <1 second
- LLM can get parameter list for any tool in JSON format
- Humans can browse profiles with readable output

### Priority 2: MCP Introspection

**Goal:** Dynamic tool discovery from running servers

**Tasks:**
1. Implement `jn mcp tools @server` - List tools
2. Implement `jn mcp resources @server` - List resources
3. Implement `jn mcp schema @server tool` - Show tool schema

**Effort:** 1-2 days

**Why:** Complements static profiles with dynamic discovery, useful for exploration.

### Priority 3: Curated Profile Examples

**Goal:** Showcase profile curation power

**Tasks:**
1. Create profiles with pre-filled defaults (braf-trials, egfr-trials)
2. Add adapter examples for normalizing MCP text output
3. Document curation patterns and best practices

**Effort:** 2-3 hours

**Why:** Demonstrates full potential of profile system, provides templates for users.

### Priority 4: Additional Transports

**Goal:** Support HTTP and WebSocket MCPs

**Tasks:**
1. Implement HTTP/SSE transport in MCP plugin
2. Implement WebSocket transport
3. Update profiles to specify transport type

**Effort:** 3-5 days

**Why:** Some MCPs use HTTP instead of stdio. Low priority because most MCPs use stdio.

### Not Planned: MCP Server Mode

**Why not:**
- JN is primarily a data **consumer** (processing pipelines)
- Exposing JN data sources to other MCP clients is niche use case
- Would require significant architectural changes
- Current client mode covers 95% of use cases

**If needed later:** Could expose JN pipelines as MCP tools/resources for other agents to consume.

---

## JSON Output Structure

### What MCPs Return

MCP tool calls return content in standardized format:

**Text content:**
```json
{
  "type": "tool_result",
  "tool": "search",
  "mimeType": "text/plain",
  "text": "BRAF V600E is a common mutation in melanoma...",
  "blob": null
}
```

**Binary content:**
```json
{
  "type": "tool_result",
  "tool": "fetch_image",
  "mimeType": "image/png",
  "text": null,
  "blob": "base64encodeddata..."
}
```

**Resource content:**
```json
{
  "type": "resource_content",
  "uri": "resource://trials/NCT12345",
  "mimeType": "application/json",
  "text": "{\"nct_id\": \"NCT12345\", ...}",
  "blob": null
}
```

### Is Text-in-JSON a Problem?

**No. It's perfectly fine for JN.**

**Reasons:**
1. **It IS JSON** - Valid JSON object per record
2. **It IS NDJSON** - One object per line, streamable
3. **Filterable** - Extract text with JQ: `.text`
4. **Parseable** - Parse embedded JSON: `.text | fromjson`
5. **Transformable** - Apply adapters to normalize

**Example workflows:**

**Extract text only:**
```bash
jn cat "@biomcp/search?gene=BRAF" | jn filter '.text'
```

**Filter by text content:**
```bash
jn cat "@biomcp/search?gene=BRAF" | \
  jn filter '.text | contains("Phase 3")'
```

**Parse embedded JSON:**
```bash
jn cat "@biomcp/fetch_data?id=123" | \
  jn filter '.text | fromjson | {id, name, status}'
```

**Normalize with adapter:**
```bash
# Create profile with adapter
# profiles/mcp/biomcp/search-normalized.json
{
  "tool": "search",
  "adapter": "filters/extract-genes.jq"
}

# Use normalized profile
jn cat "@biomcp/search-normalized?gene=BRAF"
```

### Structured Data vs Text

**Many MCPs return text** because:
- Natural language is more flexible than rigid schemas
- LLMs consume text better than structured data
- Less brittle than strict JSON schemas

**If you need structured data:**
1. Parse text with JQ filters
2. Use MCP prompts to request structured format
3. Build/use MCPs that return structured JSON
4. Apply adapters to normalize output

**Bottom line:** Text-in-JSON is a feature, not a bug. It works perfectly with JN's architecture.

---

## Best Practices

### Profile Organization

**One profile per MCP server:**
```
profiles/mcp/
  biomcp/           # One server
    _meta.json
    search.json
    trial_search.json
  context7/         # Another server
    _meta.json
    search.json
```

**Use descriptive tool names:**
- ✅ `search.json`, `trial_search.json`, `variant_search.json`
- ❌ `tool1.json`, `tool2.json`, `search_v2.json`

**Document parameters:**
```json
{
  "tool": "search",
  "description": "Clear description of what this tool does",
  "parameters": {
    "gene": {
      "type": "string",
      "description": "Gene symbol (e.g., BRAF, TP53)",
      "required": true
    }
  }
}
```

### Curation with Defaults

**Create specialized profiles for common workflows:**

```
profiles/mcp/biomcp/
  search.json              # Generic search (no defaults)
  braf-trials.json         # Pre-filled: gene=BRAF, type=trial
  egfr-trials.json         # Pre-filled: gene=EGFR, type=trial
  recruiting-trials.json   # Pre-filled: status=recruiting
```

**Benefits:**
- Shorter commands
- Self-documenting workflows
- Easier for LLMs to discover

### Environment Variables

**Use env vars for secrets:**
```json
{
  "command": "node",
  "args": ["server.js"],
  "env": {
    "API_KEY": "${MY_API_KEY}",      // Good: env var
    "BASE_URL": "https://api.example.com"  // OK: not secret
  }
}
```

**Never commit secrets to profiles:**
- ❌ `"API_KEY": "secret123"` in _meta.json
- ✅ `"API_KEY": "${MY_API_KEY}"` with env var

### Error Handling

**Check for errors in pipelines:**
```bash
jn cat "@biomcp/search?gene=UNKNOWN" | \
  jn filter 'select(._error | not)' | \  # Filter out errors
  jn put results.json
```

**Error records have `_error: true`:**
```json
{
  "_error": true,
  "type": "mcp_error",
  "message": "Tool not found: unknown_tool",
  "exception_type": "ToolNotFoundError"
}
```

### Performance

**Reuse connections in write mode:**
```bash
# Good: Single connection for all records
jn cat genes.csv | jn put "@biomcp/variant_search"

# Bad: Reconnect for each gene (slower)
jn cat genes.csv | \
  jn filter '@biomcp/variant_search?gene=\(.symbol)'
```

**Cache profiles locally:**
- Project: `.jn/profiles/mcp/` for project-specific MCPs
- User: `~/.local/jn/profiles/mcp/` for personal MCPs
- Don't modify bundled profiles directly

---

## Examples

### Example 1: Biomedical Research

```bash
# Find recruiting trials for BRAF mutations in melanoma
jn cat "@biomcp/search?gene=BRAF&disease=melanoma" | \
  jn filter '.text | contains("recruiting")' | \
  jn filter '.text | contains("Phase 3")' | \
  jn put braf-melanoma-trials.json

# Lookup variants for list of genes
jn cat genes.csv | \
  jn filter '{gene: .symbol}' | \
  jn put "@biomcp/variant_search" | \
  jn filter '.text | contains("pathogenic")' | \
  jn put pathogenic-variants.csv
```

### Example 2: Code Documentation

```bash
# Get latest FastAPI docs
jn cat "@context7/search?library=fastapi" | \
  jn filter '.text' | \
  jn put fastapi-docs.txt

# Get docs for multiple libraries
echo '{"library": "fastapi"}' | jn put "@context7/search" > fastapi.json
echo '{"library": "pydantic"}' | jn put "@context7/search" > pydantic.json
jn cat fastapi.json pydantic.json | jn put combined-docs.json
```

### Example 3: Cross-Source Integration

```bash
# Combine local data with MCP results
jn cat \
  local-genes.csv \
  "@biomcp/search?gene=BRAF" \
  "@biomcp/search?gene=TP53" \
  "@biomcp/search?gene=EGFR" \
  | jn filter '.text | contains("FDA approved")' \
  | jn put approved-therapies.json
```

### Example 4: Local System Access

```bash
# Execute commands via MCP
echo '{"command": "ls -la"}' | jn put "@desktop-commander/execute" | \
  jn filter '.text'

# Batch command execution
jn cat commands.csv | \
  jn filter '{command: .cmd}' | \
  jn put "@desktop-commander/execute" | \
  jn put results.json
```

---

## Troubleshooting

### Error: "MCP server profile not found"

**Cause:** Profile doesn't exist in any search path.

**Solution:**
```bash
# Check profile exists
ls -la .jn/profiles/mcp/myserver/
ls -la ~/.local/jn/profiles/mcp/myserver/
ls -la jn_home/profiles/mcp/myserver/

# Create minimal profile
mkdir -p .jn/profiles/mcp/myserver
cat > .jn/profiles/mcp/myserver/_meta.json <<EOF
{
  "command": "python",
  "args": ["./server.py"],
  "transport": "stdio"
}
EOF
```

### Error: "Environment variable not set"

**Cause:** Profile references `${VAR_NAME}` but var not set.

**Solution:**
```bash
export VAR_NAME="value"
jn cat "@myserver/tool"
```

### MCP Server Not Starting

**Symptoms:** Timeout, connection errors, no output.

**Debug:**
```bash
# Test server manually
uv run --with biomcp-python biomcp run

# Check server logs (stderr)
jn cat "@biomcp/search?gene=BRAF" 2> errors.log
cat errors.log
```

### Slow Performance

**Cause:** Reconnecting for each record in write mode.

**Solution:** Use batch mode (single connection):
```bash
# Good: Single connection
jn cat genes.csv | jn put "@biomcp/variant_search"

# Bad: Multiple connections
for gene in BRAF TP53 EGFR; do
  jn cat "@biomcp/search?gene=$gene"  # Reconnects each time
done
```

---

## Summary

**MCP integration in JN provides:**
1. **Standardized access** to external data via MCP protocol
2. **Profile-based curation** for managing MCP servers and tools
3. **Source and target usage** for flexible pipeline integration
4. **Local and remote support** for uv, npx, and custom servers
5. **NDJSON streaming** for consistent data flow

**Current status:**
- ✅ Client mode fully working
- ✅ Profile system mature
- ❌ Discovery CLI not yet implemented (biggest gap)

**Next steps:**
1. Implement profile discovery CLI
2. Add MCP introspection commands
3. Create curated profile examples
4. Document best practices

**Key insight:** Profiles are the interface to MCPs. They reduce verbosity, provide curation, and enable discovery. Without profiles, MCPs would be too fragmented to use effectively.
