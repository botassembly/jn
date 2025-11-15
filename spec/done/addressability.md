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

## Addressing Operators

JN addresses use two operators:

| Operator | Purpose | Example |
|----------|---------|---------|
| `~` | **Format override** | `-~csv`, `file.txt~json`, `-~table.grid` |
| `?` | **Parameters** | `?gene=BRAF`, `?delimiter=;`, `?tablefmt=grid` |

**Syntax:**
```
address[~format][?parameters]
```

**Examples:**
```bash
file.csv                       # Auto-detect format from extension
file.txt~csv                   # Override: treat as CSV
-~csv?delimiter=;              # Override: CSV, params: semicolon delimiter
@api/source?gene=BRAF          # Profile with query parameters
```

---

## Format Override: The `~` Operator

**Purpose:** Override auto-detected format (which plugin to use)

**Common overrides:**
```bash
# Force specific format
file.txt~csv                   # Treat text file as CSV
data.unknown~json              # Parse unknown extension as JSON
-~csv                          # Parse stdin as CSV
-~table.grid                   # Output stdout as grid table

# Format variants (shorthands)
-~table.grid                   # Equivalent to -~table?tablefmt=grid
-~table.markdown               # Equivalent to -~table?tablefmt=markdown
-~table.html                   # Equivalent to -~table?tablefmt=html
```

**When to use:**
- File has wrong/no extension
- Stdin/stdout with known format
- Force specific output style
- Try different parser

---

## Parameters: The `?` Operator

**Purpose:** Pass parameters to profiles and plugin configuration

**Parameters go to both:**
- **Profile parameters** - API query params, search filters
- **Plugin configuration** - Format options, output styling

**Examples:**
```bash
# Profile parameters
@genomoncology/alterations?gene=BRAF&limit=10

# Plugin configuration
-~csv?delimiter=;
-~table?tablefmt=grid&maxcolwidths=20

# Combined (profile + plugin both receive params)
@api/source?limit=100          # Both profile and plugin get limit=100
```

---

## Address Types

### Files
**Syntax:** `path/to/file.ext[~format][?config]`

```bash
# Auto-detected format
jn cat data.csv
jn cat /absolute/path/data.json
jn cat ./relative/data.yaml

# Format override
jn cat data.txt~csv                    # Force CSV parsing
jn cat data.unknown~json               # Treat as JSON

# Format override + config
jn cat data.csv~csv?delimiter=;        # Semicolon-separated
jn cat data.tsv~csv?delimiter=\t       # Tab-separated (TSV)
jn put output.txt~json?indent=4        # Pretty JSON
```

**Auto-detection:** File extension determines format (`.csv` → CSV plugin, `.json` → JSON plugin)

---

### Protocol URLs
**Syntax:** `protocol://path[?params]`

```bash
# HTTP/HTTPS
jn cat "http://example.com/data.csv"
jn cat "https://api.example.com/data.json?key=value"

# S3
jn cat "s3://bucket/key.json"
jn cat "s3://bucket/data.csv?region=us-west-2"

# Gmail (protocol plugin)
jn cat "gmail://me/messages?from=boss&is=unread"

# FTP
jn cat "ftp://server/path/file.xlsx"
```

**Note:** The `?params` in protocol URLs are part of the URL itself (standard URL query string), not JN operators.

**Two-stage resolution:**
1. **Protocol** detected (`http://` → HTTP plugin)
2. **Format** detected (`.csv` extension → CSV plugin for binary formats)

---

### Profile References
**Syntax:** `@profile/component[?params]`

Profiles are **named configurations** for APIs, databases, and services.

**Pattern:** `@profile/component`
- `profile` - Plugin or profile namespace (e.g., `genomoncology`, `gmail`, `stripe`)
- `component` - Source or target name (e.g., `alterations`, `inbox`, `orders`)

**Examples:**
```bash
# HTTP API profiles
jn cat "@genomoncology/alterations?gene=BRAF&limit=10"
jn cat "@github/repos?org=anthropics"
jn cat "@stripe/customers?created_after=2024-01-01"

# Gmail profile (wraps gmail:// protocol)
jn cat "@gmail/inbox?from=boss&newer_than=7d"

# Database profiles
jn cat "@warehouse/orders?status=pending"
```

**How it works:**
```
@genomoncology/alterations?gene=BRAF
  ↓
Load: profiles/http/genomoncology/_meta.json (connection config)
      + profiles/http/genomoncology/alterations.json (source config)
  ↓
Resolve to: https://api.genomoncology.io/api/alterations?gene=BRAF
  ↓
HTTP plugin fetches data
```

**Profile ambiguity resolution:**
- If profile name is unique → `@inbox` works
- If multiple profiles have `inbox` → Must specify: `@gmail/inbox`, `@exchange/inbox`
- If unclear → Error with suggestions

---

### Stdin/Stdout
**Syntax:** `-[~format][?config]`

```bash
# Auto-detect (tries JSON/NDJSON)
echo '{"a":1}' | jn cat - | jn put output.json

# Force format
cat data.csv | jn cat "-~csv" | jn put output.json
cat data.tsv | jn cat "-~csv?delimiter=\t"

# Stdout formats
jn cat data.json | jn put -                          # NDJSON (default)
jn cat data.csv | jn put "-~table"                   # Simple table
jn cat data.csv | jn put "-~table.grid"              # Grid table
jn cat data.json | jn put "-~json?indent=2"          # Pretty JSON
```

**Why `-` is special:**
- Standard Unix convention (stdin/stdout)
- Needs format hint when auto-detection fails
- Can use shorthand variants (`.grid`, `.markdown`)

---

### Plugin References
**Syntax:** `@plugin` (no slash) or `--plugin @plugin`

**Used when:**
- Profile reference ambiguous
- Want to explicitly invoke plugin
- Bypass profile system

**Examples:**
```bash
# Via --plugin flag
jn cat data.csv | jn put - --plugin @json
jn cat data.csv | jn put - --plugin @table

# Standalone (if no profile collision)
jn cat "@json" < data.json     # Would look for "json" profile first
```

**Resolution order:**
1. Check if `@name/component` profile exists
2. If not, check if `@name` plugin exists
3. Error if neither found

**Difference from profiles:**
- Profiles: `@namespace/component` (has slash)
- Plugins: `@name` (no slash)

---

## Plugin Configuration

### CSV Options
```bash
# Delimiter
-~csv?delimiter=;              # Semicolon
-~csv?delimiter=\t             # Tab (TSV)
-~csv?delimiter=|              # Pipe

# Headers
output.csv?header=false        # Omit header row
```

### JSON Options
```bash
# Indentation
output.json?indent=4           # 4-space indent
output.json?indent=2           # 2-space indent
-~json?indent=0                # Compact (no indent)
```

### Table Options
```bash
# Format/style (tablefmt parameter)
-~table?tablefmt=grid               # Grid borders
-~table?tablefmt=simple             # Simple format
-~table?tablefmt=markdown           # Markdown table
-~table?tablefmt=html               # HTML table

# Shorthand (equivalent to tablefmt)
-~table.grid                        # Same as ?tablefmt=grid
-~table.markdown                    # Same as ?tablefmt=markdown

# Column width (maxcolwidths parameter)
-~table?maxcolwidths=20             # Max 20 chars per column
-~table?maxcolwidths=30             # Max 30 chars per column

# Row index (showindex parameter)
-~table?showindex=true              # Show row numbers
-~table?showindex=false             # Hide row numbers

# Alignment (global)
-~table?numalign=right              # Right-align all numbers
-~table?numalign=decimal            # Decimal align (default)
-~table?stralign=left               # Left-align all strings (default)
-~table?stralign=center             # Center-align all strings

# Combined
-~table?tablefmt=grid&maxcolwidths=20&showindex=true&numalign=right
```

**Available table formats:**
`plain`, `simple`, `grid`, `fancy_grid`, `pipe`, `orgtbl`, `github`, `jira`, `presto`, `pretty`, `psql`, `rst`, `mediawiki`, `html`, `latex`, `latex_raw`, `latex_booktabs`, `tsv`, `rounded_grid`, `heavy_grid`, `mixed_grid`, `double_grid`, `outline`, `simple_outline`, `rounded_outline`, `heavy_outline`, `mixed_outline`, `double_outline`

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

### Multi-Source Aggregation
```bash
jn cat \
  local/sales-*.csv \
  "@stripe/charges?created_after=2024-01-01" \
  "https://api.example.com/returns.json" \
  | jn put combined.json
```

### Stdin with Format Override
```bash
curl https://api.example.com/data.csv | jn cat "-~csv" | jn filter '.revenue > 1000'
```

### Table Output for Humans
```bash
jn cat "@warehouse/orders?status=pending" | jn put "-~table.grid"
jn cat data.json | jn put "-~table?tablefmt=markdown&maxcolwidths=30"
```

### Gmail to CSV
```bash
jn cat "@gmail/inbox?from=boss&has=attachment&newer_than=7d" | jn put emails.csv
```

### Complex Delimiters
```bash
# Semicolon CSV
cat data.txt | jn cat "-~csv?delimiter=;" | jn put output.json

# Pipe-delimited
cat data.txt | jn cat "-~csv?delimiter=|" | jn put output.json

# Tab-separated (TSV)
cat data.tsv | jn cat "-~csv?delimiter=\t" | jn put output.json
```

### S3 to Local with Override
```bash
jn cat "s3://mybucket/data.log~json" | jn put local-copy.json
```

### Filter Pipeline
```bash
jn cat sales.json \
  | jn filter '@builtin/pivot?row=product&col=month&value=revenue' \
  | jn filter '.total > 10000' \
  | jn put "-~table?tablefmt=markdown"
```

---

## Summary

**Universal Addressing Syntax:**
```
address[~format][?parameters]

Where address is:
  file.ext              # Local file
  protocol://path       # Protocol URL
  @profile/component    # Profile reference
  @plugin               # Plugin reference
  -                     # Stdin/stdout

Where ~format is:
  csv, json, yaml       # Format plugins
  table, table.grid     # Display formats (shorthand)

Where ?parameters is:
  key=value&key2=value2 # Parameters for profiles and plugins
```

**Two Operators:**
- **`~`** - Format override (which plugin to use)
- **`?`** - Parameters (passed to both profile and plugin)

**Key Points:**
- Format override comes before parameters: `file~format?params`
- Parameters go to BOTH profile and plugin (no priority)
- Shorthand formats: `-~table.grid` = `-~table?tablefmt=grid`
- Use actual delimiter characters: `;`, `|`, `\t`
- Profile syntax: `@profile/component` or just `@profile` if unique

**Result:** Clean, composable addressing with distinct operators for format vs configuration.
