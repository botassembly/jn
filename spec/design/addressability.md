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

## Address Syntax

JN addresses use two operators:

| Operator | Purpose | Example |
|----------|---------|---------|
| `~` | **Format override** | `-~csv`, `file.txt~json` |
| `?` | **Parameters/config** | `?gene=BRAF`, `?delimiter=;` |

**Combined:**
```bash
-~csv?delimiter=;              # Override to CSV with semicolon delimiter
file.txt~table?fmt=grid        # Override to table format with grid style
```

---

## Address Types

JN supports five types of addresses:

### 1. Files
**Syntax:** `path/to/file.ext[~format][?config]`

```bash
# Auto-detected format (from extension)
jn cat data.csv
jn cat /absolute/path/data.json
jn cat ./relative/data.yaml

# Format override
jn cat data.txt~csv                    # Force CSV parsing
jn cat data.unknown~json               # Treat as JSON

# Format override + config
jn cat data.csv~csv?delimiter=tab      # TSV with tab delimiter
jn put output.txt~json?indent=4        # JSON with indentation
```

**Why:** Standard file paths, format override when auto-detection isn't right.

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
**Syntax:** `-[~format][?config]` or `stdin`/`stdout`

```bash
# Auto-detect format (tries JSON/NDJSON)
echo '{"a":1}' | jn cat - | jn put output.json

# Force format
cat data.csv | jn cat "-~csv" | jn put output.json
cat data.tsv | jn cat "-~csv?delimiter=tab"

# Write to stdout
jn cat data.csv | jn put -                     # NDJSON
jn cat data.csv | jn put "-~table"             # Default table
jn cat data.csv | jn put "-~table.grid"        # Grid style table
jn cat data.csv | jn put "-~json?indent=2"     # Pretty JSON
```

**Special formats:**
```bash
# Table output (display-only)
-~table              # Default table (simple)
-~table.grid         # Grid borders
-~table.markdown     # Markdown format
-~table.html         # HTML table

# With config
-~table?fmt=grid&width=20&index=true
```

**Why:** Standard Unix convention (`-` means stdin/stdout). `~` makes format explicit.

---

### 5. Plugin References
**Syntax:** `@plugin` (no slash)

Direct plugin invocation when you want to bypass auto-detection.

```bash
# Force specific plugin
jn cat data.csv | jn put - --plugin @json
jn cat data.csv | jn put - --plugin @table
```

**Resolution order:**
1. Check if profile exists (`@something/name`)
2. If not, check if plugin exists (`@something`)

**Why:** Explicit control when auto-detection isn't right.

---

## Format Override: The `~` Operator

**Purpose:** Override auto-detected format

**When to use:**
- File has wrong/no extension: `data.txt~csv`
- Stdin with known format: `-~csv`
- Force output format: `output.txt~json`
- Try different parser: `data.unknown~yaml`

**Syntax:**
```
address~format[?config]
```

**Examples:**
```bash
# Files
data.txt~csv                   # Parse as CSV
input.bin~json                 # Parse as JSON
output.log~table.grid          # Write as table

# Stdin/stdout
-~csv                          # Parse stdin as CSV
-~table.markdown               # Format stdout as markdown table
-~json?indent=4                # Pretty-print JSON

# Combined with parameters
-~csv?delimiter=;              # CSV with semicolon
-~table?fmt=grid&width=30      # Grid table, 30 char columns
```

---

## Configuration: The `?` Operator

**Purpose:** Pass parameters and configuration

**Two uses:**
1. **Profile parameters** (for `@profile/source`)
2. **Plugin configuration** (for formats)

### Profile Parameters

```bash
# API query parameters
jn cat "@genomoncology/alterations?gene=BRAF&mutation_type=Missense&limit=10"

# Multiple values for same key
jn cat "@api/data?tag=urgent&tag=bug&tag=security"

# Gmail search
jn cat "@gmail/inbox?from=boss&has=attachment&newer_than=7d"
```

### Plugin Configuration

**CSV options:**
```bash
# Delimiter
-~csv?delimiter=;              # Semicolon
-~csv?delimiter=tab            # Tab-separated
-~csv?delimiter=|              # Pipe-separated

# Header control
output.csv?header=false        # No header row
```

**JSON options:**
```bash
# Indentation
output.json?indent=4           # 4-space indent
output.json?indent=2           # 2-space indent
-~json?indent=0                # Compact (no indent)
```

**Table options:**
```bash
# Format/style
-~table?fmt=grid               # Grid borders
-~table?fmt=simple             # Simple format
-~table?fmt=markdown           # Markdown table
-~table?fmt=html               # HTML table

# Column width
-~table?width=20               # Max 20 chars per column
-~table?width=30               # Max 30 chars per column

# Row index
-~table?index=true             # Show row numbers
-~table?index=false            # Hide row numbers

# Alignment
-~table?numalign=right         # Right-align numbers
-~table?stralign=center        # Center-align strings

# Combined
-~table?fmt=grid&width=20&index=true&numalign=right
```

**Shortened names:**
- `fmt` - table format/style (was `tablefmt`)
- `width` - column width (was `maxcolwidths`)
- `index` - show row index (was `showindex`)
- `numalign` - number alignment (same)
- `stralign` - string alignment (same)

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
  | jn put "-~table.grid"
```

**Behavior:**
- Sources processed sequentially
- All converted to NDJSON
- Concatenated in order
- One output stream

**Why:** Essential for agent workflows. Agents need to combine data from multiple sources naturally.

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

### Stdin Processing with Format Override
```bash
curl https://api.example.com/data.csv | jn cat "-~csv" | jn filter '.revenue > 1000'
```

### Table Output for Humans
```bash
jn cat "@warehouse/orders?status=pending" | jn put "-~table.grid"
jn cat data.json | jn put "-~table?fmt=markdown&width=30"
```

### Gmail to CSV
```bash
jn cat "@gmail/inbox?from=boss&has=attachment&newer_than=7d" | jn put emails.csv
```

### S3 to Local with Format Override
```bash
jn cat "s3://mybucket/data.log~json" | jn put local-copy.json
```

### Complex Filter Pipeline
```bash
jn cat sales.json \
  | jn filter '@builtin/pivot?row=product&col=month&value=revenue' \
  | jn filter '.total > 10000' \
  | jn put "-~table?fmt=markdown"
```

---

## Summary

**Universal Addressing Syntax:**

```
address[~format][?config]

Where address is:
  - file.ext              → Local file
  - protocol://path       → Protocol URL
  - @api/source           → Profile reference
  - @plugin               → Plugin reference
  - -                     → Stdin/stdout

Where ~format is:
  - csv, json, yaml       → Format plugins
  - table, table.grid     → Display formats

Where ?config is:
  - key=value&key2=value2 → Parameters/configuration
```

**Operators:**
- **`~`** - Format override (which plugin)
- **`?`** - Parameters/config (how to process)

**Result:** Clean, composable addressing with distinct operators for different purposes.
