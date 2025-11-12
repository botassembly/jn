# MCP Integration Assessment for JN

**Date:** 2025-11-12
**Status:** Assessment and Recommendations
**Related:** `spec/design/mcp-integration.md` (consolidated design)

---

## Executive Summary

**Bottom Line:** MCP integration in JN is working well for the "exploit" phase (using MCPs), but lacks tooling for the "explore" phase (discovering and inspecting MCPs). The profile system successfully reduces verbosity and provides curation, but LLMs and users need discovery commands to make profiles searchable and inspectable.

**Key Findings:**
1. ✅ Both local (BioMCP via uv) and remote (Context7 via npx) MCPs work correctly
2. ✅ Profile system reduces verbosity and provides curation layer
3. ✅ JSON output structure is fine for JN's NDJSON architecture
4. ❌ No discovery/exploration tools - users must manually read JSON files
5. ❌ Profile CLI design exists but not implemented
6. ⚠️ Terminology mismatch between MCP (tools/resources) and JN (sources/targets)

**Recommendations:**
1. Implement profile discovery CLI (`jn profile list`, `jn profile info`)
2. Add MCP-specific introspection (`jn mcp tools @biomcp`)
3. Document explore vs exploit pattern clearly
4. Clarify MCP terminology mapping to JN concepts
5. Consolidate scattered design docs into single source of truth

---

## Current State: What's Working

### 1. MCP Plugin Implementation

**Status:** ✅ **Fully functional**

**Implementation:**
- **Plugin:** `jn_home/plugins/protocols/mcp_.py`
- **Profile System:** `src/jn/profiles/mcp.py`
- **Tests:** All passing (8 plugin tests, 14 profile tests)

**Features:**
- Reads from MCP servers via `reads()` function
- Writes to MCP tools via `writes()` function (streaming, reuses connection)
- Proper resource cleanup (no leaks)
- Error handling with `_error: true` NDJSON records

**Example:**
```bash
jn cat "@biomcp/search?gene=BRAF"
jn cat "@context7/search?library=mcp"
echo '{"gene": "TP53"}' | jn put "@biomcp/variant_search"
```

### 2. Local vs Remote MCPs

**Status:** ✅ **Both working**

**Local MCP (BioMCP):**
- **Type:** Python-based, installed via uv
- **Launch:** `uv run --with biomcp-python biomcp run`
- **Transport:** stdio
- **Tools:** search, trial_search, variant_search
- **Profile:** `tests/jn_home/profiles/mcp/biomcp/`

**Remote MCP (Context7):**
- **Type:** Node-based, installed via npm
- **Launch:** `npx -y @upstash/context7-mcp@latest`
- **Transport:** stdio
- **Tools:** search (code documentation)
- **Profile:** `tests/jn_home/profiles/mcp/context7/`

**Verdict:** Both local (uv) and remote (npx) execution models work correctly. Profile system abstracts the difference - users don't need to know which is which.

### 3. Profile System

**Status:** ✅ **Well-designed and functional**

**Structure:**
```
profiles/mcp/
  {server}/
    _meta.json     # Server config (command, args, env)
    {tool}.json    # Tool definitions (optional, for docs)
```

**Priority Search:**
1. Project: `.jn/profiles/mcp/` (highest)
2. User: `~/.local/jn/profiles/mcp/`
3. Bundled: `jn_home/profiles/mcp/` (lowest)

**Resolution:**
```bash
@biomcp/search?gene=BRAF
  ↓
1. Find profile: biomcp/_meta.json + search.json
2. Load server config: {command: "uv", args: [...], env: {...}}
3. Parse operation: call_tool with params {gene: "BRAF"}
4. Plugin starts MCP server via stdio
5. Execute tool call
6. Return NDJSON results
```

**Benefits:**
- **Reduces verbosity:** `@biomcp/search` vs manually launching server
- **Abstracts execution:** Users don't care if it's uv/npx/node
- **Environment isolation:** Each profile can have its own env vars
- **Curation:** Can create multiple profiles per server with different defaults

---

## Key Concern #1: JSON Output

**User Question:** "BioMCP doesn't generate much JSON. Is this problematic?"

**Analysis:**

### What MCPs Actually Return

MCP tools return content in one of these forms:
1. **Text content:** `{"type": "tool_result", "tool": "search", "text": "Some text..."}`
2. **Binary content:** `{"type": "tool_result", "tool": "search", "blob": "base64..."}`
3. **Resource content:** Similar structure with `uri` field

**Example from BioMCP:**
```json
{
  "type": "tool_result",
  "tool": "search",
  "mimeType": "text/plain",
  "text": "BRAF V600E is a common mutation in melanoma...",
  "blob": null
}
```

### Is This Compatible with JN?

**Answer: ✅ Yes, perfectly fine**

**Reasons:**
1. **It IS JSON** - Each record is a valid JSON object
2. **It IS NDJSON** - Plugin outputs one JSON object per line
3. **Streamable** - Works with JN's streaming architecture
4. **Filterable** - Can extract just text: `jn cat @biomcp/search | jn filter '.text'`
5. **Transformable** - Adapters could normalize structure if needed

**Example pipeline:**
```bash
# Get text results
jn cat "@biomcp/search?gene=BRAF" | jn filter '.text'

# Filter by content
jn cat "@biomcp/search?gene=BRAF" | jn filter '.text | contains("Phase 3")'

# Extract structured data (if text is JSON)
jn cat "@biomcp/search?gene=BRAF" | jn filter '.text | fromjson'
```

### Comparison: Structured vs Text Output

**Structured JSON (ideal):**
```json
{"gene": "BRAF", "variant": "V600E", "significance": "pathogenic"}
```

**Text in JSON (what BioMCP returns):**
```json
{"type": "tool_result", "text": "BRAF V600E: pathogenic"}
```

**Both work in JN.** The second just needs an extra filter step to parse text if you want structured data.

### Recommendation

**Verdict:** No problem. Text-in-JSON is fine for JN's architecture.

**If you want more structure:**
1. **Adapters:** Create profile-specific JQ filters to parse text
2. **Prompts:** Use MCP prompts feature to request structured output
3. **Different MCP:** Find/build MCPs that return structured JSON

**But** for many use cases (especially LLM-consumed data), text output is actually preferable - LLMs understand prose better than rigid schemas.

---

## Key Concern #2: Profiles - With vs Without

**User Question:** "How do you use an MCP with and without a profile?"

### Without Profile (Direct MCP URL)

**Not currently supported in JN.**

MCP has no standard URL scheme like `http://` or `s3://`. Each MCP server is launched differently:
- BioMCP: `uv run --with biomcp-python biomcp run`
- Context7: `npx -y @upstash/context7-mcp@latest`
- Custom: `python my_server.py` or `node server.js`

**Why profiles are required for MCP:**
- No universal addressing (unlike `http://example.com/data`)
- Each server needs custom launch command
- Connection details (stdio, http, sse) vary
- Environment variables differ per server

### With Profile (Current Approach)

**Profiles ARE the interface to MCPs in JN.**

**Minimal profile (_meta.json only):**
```json
{
  "command": "uv",
  "args": ["run", "--with", "biomcp-python", "biomcp", "run"],
  "transport": "stdio"
}
```

**Usage:**
```bash
jn cat "@biomcp?list=tools"        # List available tools dynamically
jn cat "@biomcp?tool=search&gene=BRAF"  # Call tool with params
```

**Full profile (_meta.json + tool definitions):**
```
profiles/mcp/biomcp/
  _meta.json        # Server launch config
  search.json       # Tool definition (parameters, description)
  variant_search.json
  trial_search.json
```

**Usage:**
```bash
jn cat "@biomcp/search?gene=BRAF"  # Use named tool from profile
```

### Profile Benefits

**Why profiles are valuable:**

1. **Curation:** Expose only tools you care about
2. **Documentation:** Tool definitions describe parameters
3. **Defaults:** Pre-fill common parameters
4. **Discovery:** LLMs can find tools via profile discovery (when implemented)
5. **Simplicity:** `@biomcp/search` vs remembering launch command

**Example: Pre-filled defaults**

Create `profiles/mcp/biomcp/braf-trials.json`:
```json
{
  "tool": "trial_search",
  "defaults": {
    "gene": "BRAF",
    "status": "recruiting"
  },
  "parameters": {
    "disease": {"type": "string", "description": "Disease name"}
  }
}
```

Use it:
```bash
jn cat "@biomcp/braf-trials?disease=melanoma"
# Automatically includes gene=BRAF, status=recruiting
```

### Programmatic vs Profile Usage

**User mentioned:** "An MCP has tools you could use programmatically. Then by setting up a profile, you can set up initial filters/adapters."

**Analysis:**

**Programmatic (without profile curation):**
```bash
# Query MCP directly for all tools
jn cat "@biomcp?list=tools"

# Call any tool dynamically
jn cat "@biomcp?tool=search&gene=BRAF"
jn cat "@biomcp?tool=variant_search&gene=TP53"
```

**Curated (with profile definitions):**
```bash
# Only expose curated subset
jn cat "@biomcp/search?gene=BRAF"          # Defined in profile
jn cat "@biomcp/braf-trials?disease=..."   # Pre-filled defaults
```

**Both work.** Profiles add a curation layer but don't prevent programmatic access.

---

## Key Concern #3: Explore vs Exploit Pattern

**User's core question:** "Do we have this concept of explore and exploit in general in JN?"

### What is Explore vs Exploit?

**Explore Phase:**
- Discover what MCPs/profiles exist
- Inspect available tools and parameters
- Learn how to use them
- Create profiles based on discoveries

**Exploit Phase:**
- Use known MCPs/profiles for data processing
- Execute pipelines with confidence
- Production workflows

### Current State

**Exploit Phase: ✅ Works great**
```bash
# I know what I want, just use it
jn cat "@biomcp/search?gene=BRAF" | jn put results.json
jn cat "@context7/search?library=fastapi" | jn filter '.text'
```

**Explore Phase: ❌ Missing tooling**
```bash
# These DON'T work yet:
jn profile list                      # List all profiles
jn profile info @biomcp/search       # Show parameters
jn mcp tools @biomcp                 # List tools from server
jn mcp resources @biomcp             # List resources
```

**Current workaround:** Manually read JSON files
```bash
ls -la tests/jn_home/profiles/mcp/
cat tests/jn_home/profiles/mcp/biomcp/_meta.json
cat tests/jn_home/profiles/mcp/biomcp/search.json
```

### Why This Matters for LLMs

**Problem:** LLMs must relearn profile structure every session.

**Ideal workflow:**
```python
# Session 1: Explore
llm> "What MCPs are available?"
assistant> jn profile list --type mcp
   → Shows: @biomcp, @context7, @desktop-commander

llm> "What tools does biomcp have?"
assistant> jn mcp tools @biomcp
   → Shows: search, trial_search, variant_search

llm> "Show me how to use search"
assistant> jn profile info @biomcp/search
   → Shows parameters, examples, description

# Session 2: Exploit (knowledge cached in profile)
llm> "Find BRAF trials"
assistant> jn cat "@biomcp/search?gene=BRAF"
```

**Current workflow:**
```python
# EVERY session:
llm> "What MCPs are available?"
assistant> [Searches filesystem, reads JSON files manually]

llm> "What tools does biomcp have?"
assistant> [Reads _meta.json, parses directory structure]
```

---

## Key Concern #4: Discovery & Search

**User asks:** "Can we make profiles searchable and discoverable?"

### What Needs to be Discoverable

**For MCP profiles specifically:**

1. **Available servers:** What MCP servers do I have profiles for?
2. **Tools per server:** What tools does each server provide?
3. **Parameters:** What parameters does each tool accept?
4. **Examples:** How do I use this tool?

### Proposed Discovery Commands

**Design exists:** `spec/design/profile-cli.md` has detailed design, not implemented yet.

**Key commands needed:**

#### 1. List All Profiles
```bash
jn profile list
jn profile list --type mcp
jn profile list --format json    # For LLM parsing
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
Location: jn_home/profiles/mcp/biomcp/

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
  echo '{"gene": "TP53"}' | jn put "@biomcp/search"
```

#### 3. MCP-Specific Introspection

These connect to MCP server and query dynamically:

```bash
# List tools from running server (dynamic)
jn mcp tools @biomcp
jn cat "@biomcp?list=tools"      # Alternative

# List resources from server
jn mcp resources @biomcp
jn cat "@biomcp?list=resources"  # Alternative

# Show tool schema from server
jn mcp schema @biomcp search
```

**Difference:**
- `jn profile info` - Reads static profile files (fast, no server connection)
- `jn mcp tools` - Connects to server, lists actual tools (slow, but current)

### Recommendation: Implement Profile CLI

**Priority: HIGH**

**Rationale:**
- Solve explore phase problem
- Enable LLM discovery
- Make profiles searchable
- Consistent with Unix philosophy (small, composable tools)

**Implementation:** Follow `spec/design/profile-cli.md`

**Phases:**
1. **Phase 1 (MVP):** `jn profile list` + `jn profile info` (text + JSON)
2. **Phase 2:** `jn profile tree` (visual hierarchy)
3. **Phase 3:** MCP-specific introspection (`jn mcp tools`)

---

## Key Concern #5: Terminology (Sources/Targets vs Tools/Resources)

**User notes:** "Our language is source and target, not tool. Sources feed filters, which feed targets."

### MCP Terminology

**MCP Specification defines:**
- **Resources:** Static or dynamic data (like files, DB results) - READ
- **Tools:** Invokable functions with parameters - CALL
- **Prompts:** Templates for LLM interactions
- **Sampling:** LLM completion requests

### JN Terminology

**JN Framework uses:**
- **Sources:** Readable data streams (files, APIs, databases)
- **Targets:** Writable destinations (files, APIs, databases)
- **Filters:** Transformations (JQ, adapters)

### Mapping: MCP → JN

| MCP Concept | JN Equivalent | Usage |
|-------------|---------------|-------|
| Resource (read) | Source | `jn cat "@mcp?resource=uri"` |
| Tool (call) | Source or Target | Source: `jn cat "@mcp/tool"` <br> Target: `jn put "@mcp/tool"` |
| Prompt | N/A | Not implemented |
| Sampling | N/A | Not relevant (JN provides data TO LLMs) |

### Tools as Both Sources and Targets

**Key insight:** MCP tools can be BOTH sources and targets depending on how you use them.

**As Source (reads):**
```bash
# Call tool, get results as source data
jn cat "@biomcp/search?gene=BRAF" | jn put results.json
```

**As Target (writes):**
```bash
# Pipe records to tool, call once per record
echo '{"gene": "BRAF"}' | jn put "@biomcp/search"
echo '{"gene": "TP53"}' | jn put "@biomcp/search"
# Each record triggers a tool call
```

### Resources as Sources Only

**MCP resources are read-only:**
```bash
# Read resource
jn cat "@biomcp?resource=resource://trials/NCT12345"
```

**Cannot write to resources** (MCP spec doesn't support this).

### Current Profile Structure

**Profile files use MCP terminology:**
```json
{
  "tool": "search",              // MCP terminology
  "description": "...",
  "parameters": { ... }
}
```

**Should we change this?**

**Recommendation: NO. Keep MCP terminology in profiles.**

**Reasons:**
1. Matches MCP specification (easier to understand for MCP users)
2. Tool definitions can be auto-generated from MCP schema
3. JN framework internally maps to sources/targets transparently
4. Changing would break existing profiles

**Document the mapping clearly instead.**

---

## Assessment Summary

### What's Working Well

1. ✅ **MCP plugin implementation** - Fully functional, both reads and writes
2. ✅ **Profile system** - Reduces verbosity, provides curation
3. ✅ **Local and remote MCPs** - Both uv (local) and npx (remote) work
4. ✅ **JSON output structure** - Text-in-JSON is fine for JN/NDJSON
5. ✅ **Exploit phase** - Using known MCPs works great

### What's Missing

1. ❌ **Profile discovery CLI** - No `jn profile list` or `jn profile info`
2. ❌ **Explore phase tooling** - Users manually read JSON files
3. ❌ **MCP introspection** - No way to list tools from server dynamically
4. ❌ **Documentation consolidation** - Multiple overlapping docs
5. ❌ **Search/discovery for LLMs** - No way for LLMs to find profiles efficiently

### What Needs Fixing

1. ⚠️ **Scattered documentation** - Consolidate into single source
2. ⚠️ **Work ticket outdated** - Contains unimplemented server mode vision
3. ⚠️ **Terminology docs unclear** - Explain MCP → JN mapping explicitly
4. ⚠️ **No pre-filled defaults examples** - Profiles don't showcase curation power

---

## Recommendations

### Priority 1: Implement Profile Discovery CLI

**Why:** Solves explore phase, enables LLM discovery, makes profiles searchable.

**What:** Implement from `spec/design/profile-cli.md`
- `jn profile list` (text + JSON output)
- `jn profile info @profile/component` (detailed inspection)
- `jn profile tree` (optional, visual hierarchy)

**Effort:** 2-3 days for MVP

### Priority 2: Consolidate Documentation

**Why:** Single source of truth, eliminate confusion.

**What:**
1. Create `spec/design/mcp-integration.md` (comprehensive design)
2. Trim `spec/work/19-mcp-protocol.md` to basics (what/why MCP)
3. Update `docs/mcp.md` with explore/exploit workflow
4. Add terminology mapping to design doc

**Effort:** 4-6 hours

### Priority 3: Add MCP Introspection

**Why:** Dynamic tool discovery, useful for exploration.

**What:**
- `jn mcp tools @server` - List tools from running server
- `jn mcp resources @server` - List resources
- `jn mcp schema @server tool` - Show tool parameter schema

**Effort:** 1-2 days

### Priority 4: Create Example Curated Profiles

**Why:** Showcase profile power with defaults and adapters.

**What:**
- Add `profiles/mcp/biomcp/braf-trials.json` with pre-filled gene=BRAF
- Add adapter examples for normalizing text output
- Document curation patterns

**Effort:** 2-3 hours

---

## Answering User's Specific Questions

### "Do we have remote and local versions working well?"

**Yes.** BioMCP (local via uv) and Context7 (remote via npx) both work correctly. Profile system abstracts the difference.

### "How do you use an MCP with and without a profile?"

**With profile (current):** `jn cat "@biomcp/search?gene=BRAF"`
**Without profile:** Not supported - profiles are required for MCPs because there's no standard URL scheme.

Profiles can be minimal (_meta.json only) or full (with tool definitions).

### "Is MCP valuable in a system where JSON is the lingua franca?"

**Yes.** MCPs provide:
1. **Access to external data** (biomedical, code docs, APIs)
2. **Standard protocol** for tool integration
3. **Profile-based curation** fits JN's architecture perfectly

Text-in-JSON output is fine for JN. Not a problem.

### "Do we have explore vs exploit?"

**Partially.** Exploit works (using MCPs), explore needs work (discovering MCPs).

**Solution:** Implement profile discovery CLI.

### "Can we make profiles searchable/discoverable?"

**Yes, with profile CLI.** Design exists in `spec/design/profile-cli.md`, needs implementation.

### "Is MCP verbose? Can JN help?"

**Yes, JN helps significantly:**
- Profiles reduce launch command verbosity
- Pre-filled defaults reduce parameter verbosity
- Profile discovery will help LLMs find tools efficiently

**Example verbosity reduction:**

**Without JN:**
```bash
# Manual MCP usage
uv run --with biomcp-python biomcp run &
export MCP_PID=$!
# ...connect to server via stdio...
# ...call tool with JSON-RPC...
# ...parse response...
kill $MCP_PID
```

**With JN:**
```bash
jn cat "@biomcp/search?gene=BRAF"
```

---

## Next Steps

1. **Consolidate docs** → Create `spec/design/mcp-integration.md`
2. **Trim work ticket** → Remove outdated server mode vision
3. **Implement profile CLI** → Start with `jn profile list` MVP
4. **Add MCP examples** → Create curated profiles with defaults
5. **Document terminology** → Explain MCP → JN mapping clearly

---

## Conclusion

MCP integration in JN is **solid and functional** for the "exploit" phase (using MCPs in pipelines). The profile system successfully reduces verbosity and provides a curation layer that fits JN's architecture.

The **main gap** is the "explore" phase - users and LLMs need discovery tools to find and inspect profiles efficiently. Implementing the profile CLI (already designed in `profile-cli.md`) would solve this.

JSON output structure is fine - text-in-JSON works perfectly with JN's NDJSON streaming. Both local (uv) and remote (npx) MCPs work correctly.

**Recommendation:** Implement profile discovery CLI as Priority 1, consolidate documentation as Priority 2.
