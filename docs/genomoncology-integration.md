# GenomOncology API Integration with JN

## Overview

This document demonstrates the integration of the GenomOncology Precision Medicine API with JN, including:
- **Profile-based authentication** with environment variables
- **JQ filters** for data transformation
- **Tabulate plugin** for human-readable table output
- **`--plugin` flag** for explicit plugin selection

---

## GenomOncology Profile

**Location:** `jn_home/profiles/http/genomoncology.json`

```json
{
  "base_url": "https://pwb-demo.genomoncology.io/api",
  "headers": {
    "Authorization": "Token ${GENOMONCOLOGY_API_KEY}",
    "Accept": "application/json"
  },
  "paths": {
    "annotations": "/annotations",
    "annotations_match": "/annotations/match",
    "alterations": "/alterations",
    "genes": "/genes",
    "diseases": "/diseases",
    "therapies": "/therapies"
  },
  "timeout": 60
}
```

### Authentication

The profile uses environment variable substitution for the API key:

```bash
export GENOMONCOLOGY_API_KEY="your-token-here"
```

The header `"Authorization": "Token ${GENOMONCOLOGY_API_KEY}"` resolves to:
```
Authorization: Token your-token-here
```

---

## Example Workflows

### 1. Fetch Alterations (GET)

```bash
# Basic fetch
export GENOMONCOLOGY_API_KEY="e1ec1eb80340ffbef8c9b8baf5312f6250d283bc"
jn cat @genomoncology/alterations | head -n 5

# Extract key fields with JQ filter
jn cat @genomoncology/alterations | \
  jn filter '@genomoncology/extract-alterations' | \
  head -n 20

# Pretty table output
jn cat @genomoncology/alterations | \
  jn filter '@genomoncology/extract-alterations' | \
  head -n 10 | \
  jn put --plugin tabulate --tablefmt grid -
```

**Output:**
```
+--------+------------+-------------------------+-------------+--------------+
| gene   | name       | mutation_type           | aa_change   | biomarkers   |
+========+============+=========================+=============+==============+
| FGF3   | FGF3 R144L | Substitution - Missense | R144L       | FGF3         |
+--------+------------+-------------------------+-------------+--------------+
| FGF3   | FGF3 R181C | Substitution - Missense | R181C       | FGF3         |
+--------+------------+-------------------------+-------------+--------------+
...
```

### 2. Filter by Gene

```bash
# Get EGFR alterations
jn cat @genomoncology/alterations?gene=EGFR | \
  jn filter '.results[] | {gene, name, mutation_type}' | \
  jn put --plugin tabulate -
```

### 3. Save to CSV

```bash
# Convert to CSV for spreadsheet tools
jn cat @genomoncology/alterations | \
  jn filter '@genomoncology/extract-alterations' | \
  head -n 100 | \
  jn put alterations.csv
```

---

## Tabulate Plugin

### Purpose

The tabulate plugin formats NDJSON as **pretty tables for human viewing**. Unlike CSV/JSON which are for data interchange, tabulate is for:
- **Terminal display** (stdout)
- **Reports and documentation**
- **Quick data inspection**

### Design: Is This Possible?

**Yes!** The `--plugin` flag enables explicit plugin selection, bypassing file extension matching:

```bash
jn put --plugin tabulate -        # Use tabulate plugin, write to stdout
jn put --plugin tabulate stdout   # Same thing (alternative syntax)
jn put --plugin csv output.txt    # Use CSV plugin even for .txt file
```

**Why this works:**
1. **Explicit plugin** (`--plugin tabulate`) overrides registry matching
2. **Stdout destinations** (`-` or `stdout`) skip file creation
3. **Plugin config** (e.g., `--tablefmt grid`) passes args to plugin

**Plugin Name Resolution:**

JN uses a smart fallback strategy for plugin names:
1. **Exact match first** - If you ask for `csv` and there's a plugin named `csv`, use it
2. **Underscore fallback** - If no exact match, try `csv_` (the actual plugin names)
3. **User-friendly** - You can use either `tabulate` or `tabulate_`, both work!

```bash
# All of these work:
jn put --plugin tabulate -      # Resolves to tabulate_
jn put --plugin tabulate_ -     # Direct match
jn put --plugin csv output.csv  # Resolves to csv_
jn put --plugin csv_ output.csv # Direct match
```

This means you can use clean names without worrying about trailing underscores!

### Is Tabulate a Format?

**Kind of, but not exactly.** Here's the distinction:

| Aspect | File Formats (CSV, JSON) | Tabulate |
|--------|--------------------------|----------|
| Purpose | Data interchange | Human visualization |
| Reversible | ✅ Can read back | ❌ Display only |
| Output | Files | Stdout (terminal) |
| Structure | Machine-parseable | Pretty-printed |

**Tabulate is a "display format"** - it only implements `writes()`, not `reads()`.

### Tabulate Usage

```bash
# Different table styles
jn cat data.json | jn put --plugin tabulate --tablefmt simple -
jn cat data.json | jn put --plugin tabulate --tablefmt grid -
jn cat data.json | jn put --plugin tabulate --tablefmt fancy_grid -
jn cat data.json | jn put --plugin tabulate --tablefmt psql -
jn cat data.json | jn put --plugin tabulate --tablefmt markdown -
```

**Available formats:**
- `simple` (default) - Clean, minimal
- `grid` - Box drawing characters
- `fancy_grid` - Heavy box drawing
- `pipe` - Markdown tables
- `psql` - PostgreSQL style
- `rst` - reStructuredText
- `html` - HTML table
- `latex` - LaTeX table

---

## JQ Filters

### Bundled GenomOncology Filters

**`@genomoncology/extract-alterations`**

Extracts key fields from alterations:

```jq
.results[] | {
  gene: .gene,
  name: .name,
  mutation_type: .mutation_type,
  aa_change: .aa_change,
  biomarkers: .biomarkers | join(", ")
}
```

### Custom Inline Filters

```bash
# Filter by mutation type
jn cat @genomoncology/alterations | \
  jn filter '.results[] | select(.mutation_type_group == "Missense")'

# Count by gene
jn cat @genomoncology/alterations | \
  jn filter '.results | group_by(.gene) | map({gene: .[0].gene, count: length})'
```

---

## POST Requests (Future Enhancement)

The variant annotations endpoint uses **POST with form data**:

```bash
curl -X POST \
  --header 'Authorization: Token e1ec1eb80340ffbef8c9b8baf5312f6250d283bc' \
  -d 'batch=chr7|140453136|A|T|GRCh37&batch=NM_005228.3:c.2239_2241delTTA' \
  'https://pwb-demo.genomoncology.io/api/annotations/match'
```

### Current Status

- **GET requests**: ✅ Fully supported
- **POST with JSON**: ✅ Supported (via stdin)
- **POST with form data**: ⏳ Needs enhancement

### Proposed Enhancement

Update `http_.py` to support `--data-urlencode`:

```bash
# Future syntax
jn cat --method POST \
  --data-urlencode "batch=chr7|140453136|A|T|GRCh37" \
  @genomoncology/annotations_match
```

Or use a profile config:

```json
{
  "method": "POST",
  "form_data": {
    "batch": "chr7|140453136|A|T|GRCh37"
  }
}
```

---

## API Schema Exploration

The GenomOncology API provides OpenAPI schema:

```bash
# Fetch full schema
jn cat https://pwb-demo.genomoncology.io/api/schema \
  --headers '{"Authorization": "Token e1ec1eb80340ffbef8c9b8baf5312f6250d283bc"}' \
  | jn put schema.json

# Extract endpoint paths
jn cat schema.json | \
  jn filter '.paths | keys[] | select(startswith("/api/"))'
```

### Available Endpoints

- `/api/alterations` - Genetic alterations database
- `/api/annotations` - Variant annotations
- `/api/annotations/match` - Batch variant matching (POST)
- `/api/genes` - Gene information
- `/api/diseases` - Disease ontology
- `/api/therapies` - Therapy information
- `/api/alerts` - Alert configurations
- `/api/anatomic_sites` - Anatomic site ontology

---

## Recommended Workflows

### 1. Alteration Discovery

```bash
# Find all BRAF V600E-related alterations
jn cat @genomoncology/alterations?name=BRAF+V600E | \
  jn filter '.results[]' | \
  jn put --plugin tabulate --tablefmt grid -
```

### 2. Gene Analysis

```bash
# Get all EGFR alterations and save to CSV
jn cat @genomoncology/alterations?gene=EGFR | \
  jn filter '@genomoncology/extract-alterations' | \
  jn put egfr_alterations.csv
```

### 3. Quick Inspection

```bash
# Browse first 20 results with pagination
jn cat @genomoncology/alterations | \
  jn filter '@genomoncology/extract-alterations' | \
  head -n 20 | \
  jn put --plugin tabulate --tablefmt simple -
```

### 4. Multi-stage Pipeline

```bash
# Fetch → Filter → Transform → Display
jn cat @genomoncology/alterations | \
  jn filter '.results[] | select(.mutation_type_group == "Missense")' | \
  jn filter '{gene, aa_change, biomarkers: .biomarkers[0]}' | \
  head -n 25 | \
  jn put --plugin tabulate --tablefmt psql -
```

---

## Summary: Answering Your Questions

### 1. Can we use `--plugin` to invoke plugins without file extensions?

**Yes!** The `--plugin` flag explicitly specifies which plugin to use:

```bash
jn put --plugin tabulate -      # Tabulate to stdout
jn put --plugin csv output.txt  # CSV even for .txt
```

### 2. Is tabulate a "format" like CSV/JSON/TOML?

**Partially.** Tabulate is a **display-only format**:
- ✅ Implements `writes()` for output
- ❌ Doesn't implement `reads()` (not reversible)
- 🎯 Purpose: Human visualization, not data interchange

It's more accurate to call it a **"renderer"** or **"presenter"** than a traditional file format.

### 3. How to handle `-` (stdout) without a file extension?

**Three approaches:**

1. **Pattern matching** - Tabulate plugin matches `^-$` and `^stdout$`
2. **Explicit plugin** - Use `--plugin tabulate` flag
3. **Auto-detection** - When dest is `-`, prefer display formats

All three work! The `--plugin` flag is most explicit and recommended.

### 4. Environment variable substitution in profiles?

**Yes!** The profile system supports `${VAR}` syntax:

```json
{
  "headers": {
    "Authorization": "Token ${GENOMONCOLOGY_API_KEY}"
  }
}
```

This resolves at runtime from environment variables.

---

## Next Steps

1. **Enhance HTTP Plugin** - Add POST form data support
2. **More Filters** - Create additional GenomOncology JQ filters
3. **Profile Templates** - Add more bundled API profiles
4. **OpenAPI Generator** - Auto-generate profiles from OpenAPI specs (Phase 2)

---

## Complete Example

```bash
#!/bin/bash
# complete-genomoncology-example.sh

export GENOMONCOLOGY_API_KEY="e1ec1eb80340ffbef8c9b8baf5312f6250d283bc"

echo "=== GenomOncology Alterations Analysis ==="
echo ""

echo "Fetching FGF3 alterations..."
jn cat @genomoncology/alterations | \
  jn filter '.results[] | select(.gene == "FGF3") | {gene, name, mutation_type, aa_change}' | \
  head -n 15 | \
  jn put --plugin tabulate --tablefmt grid -

echo ""
echo "=== Saving to CSV for further analysis ==="
jn cat @genomoncology/alterations | \
  jn filter '@genomoncology/extract-alterations' | \
  head -n 100 | \
  jn put alterations_sample.csv

echo "Saved to alterations_sample.csv"
```

**Output:**
```
=== GenomOncology Alterations Analysis ===

Fetching FGF3 alterations...
+--------+------------+-------------------------+-------------+
| gene   | name       | mutation_type           | aa_change   |
+========+============+=========================+=============+
| FGF3   | FGF3 R144L | Substitution - Missense | R144L       |
+--------+------------+-------------------------+-------------+
| FGF3   | FGF3 R181C | Substitution - Missense | R181C       |
+--------+------------+-------------------------+-------------+
...

=== Saving to CSV for further analysis ===
Saved to alterations_sample.csv
```

---

**Documentation complete!** 🎉
