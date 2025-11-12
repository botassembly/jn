# MCP Protocol Integration

**Status:** ✅ Implemented (Client Mode)
**See:** `spec/design/mcp-integration.md` (comprehensive design)

---

## What is MCP?

**Model Context Protocol (MCP)** is an open standard that enables AI applications to securely access external data sources and tools.

**Official Spec:** https://modelcontextprotocol.io/

**MCP Primitives:**
- **Resources** - Read-only data sources (files, DB results, documents)
- **Tools** - Invokable functions with parameters
- **Prompts** - LLM interaction templates
- **Sampling** - LLM completion requests

---

## Why MCP in JN?

**Problem:** AI agents need access to biomedical databases, code documentation, APIs, local systems, etc. Each source traditionally requires a custom plugin.

**Solution:** MCP provides a standard protocol. One JN plugin connects to many MCP servers.

**JN's Role:** Data pipeline for AI
```
MCP Server → JN → Transform → Output
  (data)     (pipeline)  (filter)  (format)
```

**Example:**
```bash
# Get biomedical data, filter, export
jn cat "@biomcp/search?gene=BRAF" | \
  jn filter '.text | contains("Phase 3")' | \
  jn put trials.csv
```

---

## Implementation Status

### ✅ Implemented: Client Mode

**JN as MCP client** - Read from and write to external MCP servers.

**Features:**
- Profile-based server configuration
- Tool calling (read and write modes)
- Resource reading
- Environment variable substitution
- Connection reuse (performance)
- stdio transport
- Works with local (uv) and remote (npx) servers

**Files:**
- `src/jn/profiles/mcp.py` - Profile system
- `jn_home/plugins/protocols/mcp_.py` - MCP plugin
- `jn_home/profiles/mcp/` - Bundled profiles (BioMCP, Context7, Desktop Commander)

**Usage:**
```bash
# Read from MCP tool
jn cat "@biomcp/search?gene=BRAF"

# Write to MCP tool (batch)
echo '{"gene": "TP53"}' | jn put "@biomcp/variant_search"

# List available tools
jn cat "@biomcp?list=tools"
```

### ❌ Not Implemented

**Profile Discovery CLI:**
- `jn profile list` - List all profiles
- `jn profile info @biomcp/search` - Inspect tool details

**Design exists:** `spec/design/profile-cli.md`

**MCP Server Mode:**
- Exposing JN data sources to other MCP clients
- Not currently needed (JN is primarily a data consumer)

---

## Profile System

**Why profiles?** MCPs have no standard URL scheme (unlike `http://` or `s3://`). Each server launches differently.

**Profile Structure:**
```
profiles/mcp/
  {server}/
    _meta.json     # Server config (command, args, env)
    {tool}.json    # Tool definitions (optional)
```

**Example: BioMCP**

**_meta.json:**
```json
{
  "command": "uv",
  "args": ["run", "--with", "biomcp-python", "biomcp", "run"],
  "description": "BioMCP: Biomedical data access",
  "transport": "stdio"
}
```

**search.json:**
```json
{
  "tool": "search",
  "description": "Search biomedical resources",
  "parameters": {
    "gene": {"type": "string", "description": "Gene symbol"},
    "disease": {"type": "string", "description": "Disease name"}
  }
}
```

**Usage:**
```bash
jn cat "@biomcp/search?gene=BRAF&disease=Melanoma"
```

---

## Key Concepts

### Profiles are Required

Unlike HTTP (`https://api.com/endpoint`), MCP has no standard addressing. Profiles define how to launch each server:
- BioMCP: `uv run --with biomcp-python biomcp run`
- Context7: `npx -y @upstash/context7-mcp@latest`
- Custom: `python my_server.py`

### Tools as Sources and Targets

**As Source (read):**
```bash
jn cat "@biomcp/search?gene=BRAF"  # Call tool, get results
```

**As Target (write):**
```bash
echo '{"gene": "BRAF"}' | jn put "@biomcp/search"  # Call per record
```

### JSON Output Structure

MCPs return records like:
```json
{
  "type": "tool_result",
  "tool": "search",
  "text": "BRAF V600E is a common mutation...",
  "mimeType": "text/plain"
}
```

**This is fine for JN** - It's valid NDJSON, streamable, filterable:
```bash
jn cat "@biomcp/search?gene=BRAF" | jn filter '.text'
```

---

## Examples

**Biomedical research:**
```bash
jn cat "@biomcp/trial_search?gene=BRAF&phase=PHASE3"
```

**Code documentation:**
```bash
jn cat "@context7/search?library=fastapi"
```

**Batch processing:**
```bash
jn cat genes.csv | \
  jn filter '{gene: .symbol}' | \
  jn put "@biomcp/variant_search" | \
  jn put results.json
```

**Cross-source integration:**
```bash
jn cat \
  local.csv \
  "@biomcp/search?gene=BRAF" \
  "https://api.example.com/data.json" \
  | jn filter '.score > 0.8' \
  | jn put combined.json
```

---

## Resources

- **Comprehensive Design:** `spec/design/mcp-integration.md`
- **User Docs:** `docs/mcp.md`
- **Profile CLI Design:** `spec/design/profile-cli.md` (not implemented)
- **Assessment:** `spec/design/mcp-assessment.md`
- **MCP Specification:** https://modelcontextprotocol.io/
