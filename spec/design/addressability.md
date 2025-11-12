# JN Addressability System

**Purpose:** Define how users and agents address data sources, destinations, and operations in JN
**Status:** Final design for v5
**Date:** 2025-11-12

---

## Overview

JN uses a **universal addressing system** where everything is addressable: files, APIs, databases, email, cloud storage, stdin/stdout. This document explains what addresses look like, why they work this way, and how users and agents interact with them.

**Design Principles:**
1. **Familiar syntax** - Use patterns people already know (URLs, query strings)
2. **Self-contained** - Complete address in one string (no scattered flags)
3. **Composable** - Mix local files, remote APIs, protocols naturally
4. **Discoverable** - Agents can understand addresses without execution
5. **Extensible** - New data sources added via plugins

---

## Address Types

JN supports five types of addresses:

### 1. Files
**Syntax:** `path/to/file.ext`

```bash
jn cat data.csv                    # Local file
jn cat /absolute/path/data.json    # Absolute path
jn cat ./relative/data.yaml        # Relative path
jn cat "file with spaces.xlsx"     # Quoted for spaces
```

**Auto-detection:** File extension determines format (`.csv` → CSV plugin, `.json` → JSON plugin)

**Why:** Standard file path syntax, works like every other Unix tool.

---

### 2. Protocol URLs
**Syntax:** `protocol://path[?params]`

```bash
# HTTP/HTTPS
jn cat "http://example.com/data.csv"
jn cat "https://api.example.com/data.json?key=value"

# S3
jn cat "s3://bucket/key.json"
jn cat "s3://bucket/data.csv?region=us-west-2"

# Gmail
jn cat "gmail://me/messages?from=boss&is=unread"

# FTP
jn cat "ftp://server/path/file.xlsx"
```

**Two-stage resolution:**
1. **Protocol** detected (`http://` → HTTP plugin)
2. **Format** detected (`.csv` extension → CSV plugin)

**For binary formats** (XLSX, PDF, Parquet):
```
http://example.com/data.xlsx
  → curl downloads bytes
  → XLSX plugin parses
  → NDJSON stream
```

**For text formats** (JSON, CSV, NDJSON):
```
http://example.com/data.json
  → HTTP plugin downloads and parses
  → NDJSON stream
```

**Why:** Standard URL syntax everyone knows. Protocols are explicit and unambiguous.

---

### 3. Profile References
**Syntax:** `@api/source[?params]`

Profiles are **named configurations** for APIs, databases, and services. They abstract authentication, base URLs, and endpoint structure.

```bash
# HTTP API profiles
jn cat "@genomoncology/alterations?gene=BRAF&limit=10"
jn cat "@github/repos?org=anthropics"
jn cat "@stripe/customers?created_after=2024-01-01"

# Gmail profile (friendlier than protocol URL)
jn cat "@gmail/inbox?from=boss&newer_than=7d"

# Database profiles
jn cat "@warehouse/orders?status=pending"
jn cat "@analytics/revenue?year=2024"
```

**Profile resolution:**
```
@genomoncology/alterations?gene=BRAF
  ↓
Load: profiles/http/genomoncology/_meta.json (connection config)
      + profiles/http/genomoncology/alterations.json (endpoint config)
  ↓
Resolve to: https://pwb-demo.genomoncology.io/api/alterations?gene=BRAF
  ↓
HTTP plugin fetches data
```

**Why profiles?**
- **Simplicity:** `@api/source` vs full URL with auth headers
- **Reusability:** Same config across many queries
- **Security:** Credentials in config files, not command line
- **Discovery:** Agents can list and explore available profiles

---

### 4. Stdin/Stdout
**Syntax:** `-` (dash) or explicit `stdin`/`stdout`

```bash
# Read from stdin (auto-detect format)
echo '{"a":1}\n{"b":2}' | jn cat - | jn put output.json

# Read from stdin with explicit format
cat data.csv | jn cat "-?fmt=csv" | jn put output.json

# Write to stdout
jn cat data.csv | jn put -

# Write to stdout with formatting
jn cat data.csv | jn put "-?fmt=table"
```

**Format detection:**
- `-` alone → Try auto-detect (JSON/NDJSON)
- `-?fmt=csv` → Force CSV parsing
- `-?fmt=table` → Format as table
- `-?fmt=json` → Format as JSON array

**Why:** Standard Unix convention (`-` means stdin/stdout). Format hint solves ambiguity.

---

### 5. Plugin References
**Syntax:** `@plugin` (no slash)

Direct plugin invocation when you want to bypass auto-detection.

```bash
# Force specific plugin
jn cat data.csv | jn put - --plugin @json
jn cat data.csv | jn put - --plugin @table

# In filter
jn cat data.json | jn filter @jq '.[].name'
```

**Resolution order:**
1. Check if profile exists (`@something/name`)
2. If not, check if plugin exists (`@something`)

**Why:** Explicit control when auto-detection isn't right.

---

## Query String Parameters

**Syntax:** `?key=value&key2=value2`

All addresses support URL-style query strings for parameters.

### Profile Parameters
```bash
# API query parameters
jn cat "@genomoncology/alterations?gene=BRAF&mutation_type=Missense&limit=10"

# Multiple values for same key
jn cat "@api/data?tag=urgent&tag=bug&tag=security"

# Gmail search
jn cat "@gmail/inbox?from=boss&has=attachment&newer_than=7d"
```

### Format Hints
```bash
# Stdin format
cat data.csv | jn cat "-?fmt=csv"

# Stdout format
jn cat data.json | jn put "-?fmt=table"
jn cat data.json | jn put "-?fmt=json"  # JSON array (not NDJSON)
```

### Plugin Configuration
```bash
# CSV delimiter
jn cat data.tsv | jn put "output.csv?delimiter=tab"

# JSON indentation
jn cat data.json | jn put "output.json?indent=4"

# YAML formatting
jn cat data.json | jn put "output.yaml?default_flow_style=false"
```

**Why query strings?**
- ✅ **Self-contained** - entire address in one string
- ✅ **Familiar** - URL syntax everyone knows
- ✅ **Composable** - works seamlessly with multi-file cat
- ✅ **Agent-friendly** - easily parsed and generated
- ⚠️ **Requires quoting** - but so do URLs and globs already

---

## Multi-Source Concatenation

**Syntax:** `jn cat source1 source2 source3 ...`

Like Unix `cat`, JN concatenates multiple sources into one NDJSON stream.

```bash
# Mix file types
jn cat data1.csv data2.json data3.yaml | jn put combined.json

# Mix local and remote
jn cat local.csv "@api/remote?limit=100" | jn filter '.active'

# Complex pipelines
jn cat \
  sales/*.csv \
  "@stripe/charges?created_after=2024-01-01" \
  "https://api.example.com/orders.json" \
  "@gmail/receipts?has=attachment" \
  | jn filter '@builtin/deduplicate' \
  | jn put "-?fmt=table"
```

**Behavior:**
- Sources processed sequentially
- All converted to NDJSON
- Concatenated in order
- One output stream

**Why:** Essential for agent workflows. Agents need to combine data from multiple sources naturally.

---

## Table Format

Table is a **format plugin** like CSV or JSON, not a special mode.

### As Input (Reading)
```bash
# Auto-detect table format
jn cat table.txt | jn put output.json

# Explicit table format
jn cat "-?fmt=table" < table.txt | jn put output.json
```

Tables can be in grid, pipe, HTML, markdown, or other formats. The table plugin detects and parses them.

### As Output (Writing)
```bash
# Default table format
jn cat data.json | jn put "-?fmt=table"

# Specific style (via plugin ownership of sub-formats)
jn cat data.json | jn put "-?fmt=table.grid"
jn cat data.json | jn put "-?fmt=table.markdown"
jn cat data.json | jn put "-?fmt=table.html"
```

**Plugin format declaration:**
```python
# In table_.py metadata
[tool.jn]
matches = [
    ".*\\.table$",
    "fmt=table",           # Owns ?fmt=table
    "fmt=table\\..*",      # Owns ?fmt=table.grid, table.markdown, etc.
]
```

**Why this design?**
- Table is just another format (like CSV, JSON, YAML)
- Plugin declares ownership of sub-formats
- No special-case code in framework
- Extensible: any plugin can declare sub-formats

**Alternative syntax (plugin can support both):**
```bash
# Via format hierarchy
jn put "-?fmt=table.grid"

# Via plugin config
jn put "-?fmt=table&style=grid"
```

Plugin decides which it supports.

---

## User Experience

### For Humans

**Simple cases are simple:**
```bash
jn cat data.csv                    # Just works
jn cat data.csv | jn put output.json  # Obvious conversion
```

**Complex cases are explicit:**
```bash
jn cat "@api/source?gene=BRAF&limit=10"  # Clear what parameters do
jn cat "-?fmt=csv" | jn put "-?fmt=table.grid"  # Explicit formats
```

**Quoting is consistent:**
```bash
# These all need quotes for same reason (shell metacharacters)
jn cat "http://example.com/data.csv?key=value"
jn cat "@api/source?gene=BRAF"
jn cat "files/*.csv"
```

### For Agents (AI/Automation)

**Discovery is straightforward:**
```bash
# List available profiles
ls ~/.jn/profiles/http/*/  # All HTTP APIs
ls ~/.jn/profiles/jq/      # All jq filters

# Inspect profile
cat ~/.jn/profiles/http/genomoncology/_meta.json
cat ~/.jn/profiles/http/genomoncology/alterations.json
```

**Generation is templatable:**
```python
# Agent generates query
api = "genomoncology"
source = "alterations"
params = {"gene": "BRAF", "limit": 10}

# Build address
query_string = "&".join(f"{k}={v}" for k, v in params.items())
address = f"@{api}/{source}?{query_string}"

# Execute
run(["jn", "cat", address])
```

**Composability enables workflows:**
```python
# Agent builds multi-source pipeline
sources = [
    "sales/2024-01.csv",
    "sales/2024-02.csv",
    "@stripe/charges?created_after=2024-01-01",
    "https://api.example.com/returns.json"
]

# Natural composition
run(["jn", "cat"] + sources + ["|", "jn", "put", "combined.json"])
```

---

## Why This Design?

### Self-Contained Addresses

**Before (scattered flags):**
```bash
jn cat @api/source -p gene=BRAF -p limit=10 -p status=active
```

Problems:
- Parameters scattered across command line
- Hard to pass as single argument
- Ambiguous with multiple sources
- Not URL-like (unfamiliar)

**After (query strings):**
```bash
jn cat "@api/source?gene=BRAF&limit=10&status=active"
```

Benefits:
- Complete address in one string
- Familiar URL syntax
- Easy to pass around
- Works with multi-source cat

### Profiles Abstract Complexity

**Without profiles:**
```bash
jn cat "https://pwb-demo.genomoncology.io/api/alterations?gene=BRAF" \
  --header "Authorization: Bearer $TOKEN" \
  --header "Accept: application/json"
```

**With profiles:**
```bash
jn cat "@genomoncology/alterations?gene=BRAF"
```

The profile handles:
- Base URL
- Authentication (token from env var)
- Headers (Accept, Content-Type)
- Default parameters
- Endpoint path structure

### Multi-Source Composition

**Essential for agent workflows:**

```bash
# Agent task: "Analyze all January sales data"
jn cat \
  sales/jan/*.csv \                           # Local CSVs
  "@stripe/charges?month=2024-01" \          # Payment processor
  "@quickbooks/invoices?month=2024-01" \     # Accounting system
  | jn filter '@builtin/deduplicate?by=order_id' \
  | jn filter '.total > 1000' \
  | jn put "-?fmt=table.grid"
```

Without multi-source cat, this would require:
- Manual concatenation
- Intermediate files
- Complex shell scripting
- Loss of streaming

### Protocol URLs Stay Explicit

**HTTP URLs work directly:**
```bash
jn cat "http://example.com/data.csv"
jn cat "https://api.example.com/endpoint?key=value"
```

**S3 URLs work directly:**
```bash
jn cat "s3://bucket/key.json"
jn cat "s3://bucket/data.csv?region=us-west-2"
```

**Gmail URLs work directly:**
```bash
jn cat "gmail://me/messages?q=from:boss"
```

**Why support both profiles and protocol URLs?**
- **Protocol URLs** - explicit, complete, portable
- **Profiles** - convenient, secure, reusable

Choose based on use case:
- One-off queries → protocol URLs
- Repeated access → profiles
- Shared configs → profiles
- Full control → protocol URLs

---

## Examples by Use Case

### Data Pipeline: CSV to JSON
```bash
jn cat data.csv | jn put output.json
```

### API Query with Parameters
```bash
jn cat "@genomoncology/alterations?gene=BRAF&mutation_type=Missense&limit=100"
```

### Multi-Source Data Aggregation
```bash
jn cat \
  local/sales-*.csv \
  "@stripe/charges?created_after=2024-01-01" \
  "https://api.example.com/returns.json" \
  | jn put combined.json
```

### Stdin Processing with Format Hint
```bash
curl https://api.example.com/data.csv | jn cat "-?fmt=csv" | jn filter '.revenue > 1000'
```

### Table Output for Humans
```bash
jn cat "@warehouse/orders?status=pending" | jn put "-?fmt=table.grid"
```

### Gmail to CSV
```bash
jn cat "@gmail/inbox?from=boss&has=attachment&newer_than=7d" | jn put boss-emails.csv
```

### S3 to Local
```bash
jn cat "s3://mybucket/data.json?region=us-west-2" | jn put local-copy.json
```

### Complex Filter Pipeline
```bash
jn cat sales.json \
  | jn filter '@builtin/pivot?row=product&col=month&value=revenue' \
  | jn filter '.total > 10000' \
  | jn put "-?fmt=table.markdown"
```

---

## Address Resolution Summary

```
Input → Detection → Resolution → Plugin → Output

FILE
data.csv
  → Extension: .csv
  → csv_ plugin
  → NDJSON

PROTOCOL URL
http://api.com/data.csv
  → Protocol: http://
  → Format: .csv
  → http_ + csv_ plugins
  → NDJSON

PROFILE
@genomoncology/alterations?gene=BRAF
  → Profile lookup
  → Resolve to URL: https://...
  → http_ plugin
  → NDJSON

STDIN
-?fmt=csv
  → Format hint: csv
  → csv_ plugin
  → NDJSON

PLUGIN
@table
  → Direct plugin reference
  → table_ plugin
  → Formatted output
```

---

## What Changed from Previous Design

### Removed
- ❌ `-p` flag for parameters → Use query strings
- ❌ `--tablefmt` flag → Use `?fmt=table.grid`
- ❌ Single-file cat → Support multiple sources
- ❌ Special-case table handling → Table is a format plugin

### Added
- ✅ Query string parameters everywhere
- ✅ Multi-source concatenation
- ✅ Stdin/stdout format hints
- ✅ Plugin ownership of sub-formats (table.grid, table.markdown)
- ✅ Unified addressing across all source types

### Why Breaking Changes Are OK
- JN is pre-1.0 (early development)
- Clean design now → easier to maintain forever
- No legacy baggage
- Clear, consistent API from day one

---

## Implementation Notes (High-Level Only)

### What Stays the Same
- Plugin discovery and registry (works great)
- Profile resolution (http.py and resolver.py)
- Two-stage resolution for binary formats
- Subprocess pipeline architecture
- NDJSON as universal interchange format

### What Needs Changes
- **CLI commands:** Parse query strings instead of `-p` flags
- **Multi-file support:** Change `input_file` → `input_files` (nargs=-1)
- **Table plugin:** Declare ownership of `fmt=table.*` patterns
- **Documentation:** Update all examples to new syntax

### Complexity Estimate
- Code changes: ~500 lines added, ~150 removed
- Test updates: ~50 test cases to update
- Documentation: All examples updated
- Effort: 6-8 hours focused work
- Risk: Low (changes are localized and well-defined)

---

## Success Criteria

**For users:**
- ✅ Simple things stay simple (`jn cat data.csv`)
- ✅ Complex things are explicit and clear
- ✅ Quoting is consistent with other tools
- ✅ Examples are easy to understand and modify

**For agents:**
- ✅ Addresses are parseable without execution
- ✅ Profiles are discoverable via filesystem
- ✅ Address generation is straightforward (string templating)
- ✅ Multi-source composition enables complex workflows

**For the framework:**
- ✅ No special cases (table is just a format plugin)
- ✅ Extensible (new protocols/formats via plugins)
- ✅ Consistent (same addressing rules everywhere)
- ✅ Maintainable (clear boundaries, no flag pollution)

---

## Future Extensions

### Profile Discovery Commands (Later)
```bash
jn profile list                    # All available profiles
jn profile info @api/source        # Show profile details
jn profile test @api/source        # Test connection
```

### OpenAPI Import (Later)
```bash
jn profile import openapi https://api.example.com/openapi.json --name myapi
```

### OAuth Token Refresh (Later)
```json
// Automatic token refresh in profile config
{
  "auth": {
    "type": "oauth2",
    "token_file": "~/.jn/tokens/gmail.json",
    "refresh_url": "https://oauth2.googleapis.com/token"
  }
}
```

### Path Variables in Profiles (Later)
```json
// Template variables in profile paths
{
  "path": "/repos/{owner}/{repo}",
  "params": ["owner", "repo"]
}
```

```bash
jn cat "@github/repo?owner=anthropics&repo=claude"
# Resolves path: /repos/anthropics/claude
```

---

## Summary

**JN's addressability system provides:**

1. **Universal addresses** - files, URLs, APIs, email, cloud storage, stdin/stdout
2. **Self-contained syntax** - complete address in one string with query params
3. **Profile abstraction** - named configs for APIs and services
4. **Multi-source composition** - concatenate diverse sources naturally
5. **Format hints** - explicit control when auto-detection isn't enough
6. **Agent-friendly** - discoverable, parseable, generatable

**The result:** A consistent, powerful addressing system that scales from simple file conversions to complex multi-source data pipelines, optimized for both human users and AI agents.
