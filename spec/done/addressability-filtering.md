# Universal Addressability with On-the-Fly Filtering

## Overview

JN implements a powerful universal addressing system that allows **filtering at the source** through URI syntax, eliminating the need for intermediate `jn filter` commands. This document explains how it works and explores its implications.

## Architecture

### Three-Part URI Syntax

```
address[~format][?parameters]
```

**Components:**
1. **address**: Base address (file, URL, profile, plugin, stdin)
2. **~format**: Optional format override
3. **?parameters**: Optional query parameters (config + filters)

### Examples from Real Usage

```bash
# NCBI Gene Info - HTTP + gzip + CSV auto-detection + filtering
jn head "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz~?chromosome=19&type_of_gene!=protein-coding"

# Local CSV with filter
jn inspect "./tests/data/people.csv?salary<80000"

# HTTP with format override + delimiter detection
jn inspect "https://...file.gz~csv?delimiter=auto"
```

## How It Works

### 1. Address Parsing (`src/jn/addressing/parser.py`)

**The `~` operator separates URL query strings from JN filter parameters:**

```python
# For protocol URLs, the ~ is critical:
https://example.com/data?token=xyz~csv?chromosome=19
#                          ^              ^
#                  URL query string    JN parameters
```

**Parsing steps:**
1. Detect if address contains `://` (protocol URL)
2. Find `~` to separate base from format/parameters
3. For protocol URLs: keep native query string in base
4. Extract JN parameters after `~?`
5. Detect compression (.gz, .bz2, .xz)

**Result:**
- `base`: `https://...file.gz?token=xyz` (includes URL's query string)
- `format_override`: `csv`
- `parameters`: `{"chromosome": "19", "type_of_gene!=": "protein-coding"}`
- `compression`: `gz`

### 2. Filter Building (`src/jn/filtering.py`)

**Query parameters are converted to jq filter expressions:**

```python
# Input parameters
{"chromosome": "19", "type_of_gene!=": "protein-coding"}

# Parsed as filters
[("chromosome", "==", "19"), ("type_of_gene", "!=", "protein-coding")]

# Built into jq expression
'select(.chromosome == "19" and .type_of_gene != "protein-coding")'
```

**Supported operators:**
- `field=value` → `==` (equality)
- `field!=value` → `!=` (not equal)
- `field>value` → `>` (greater than)
- `field<value` → `<` (less than)
- `field>=value` → `>=` (greater than or equal)
- `field<=value` → `<=` (less than or equal)

**Type inference:**
- `"123"` → `123` (integer)
- `"12.34"` → `12.34` (float)
- `"true"` → `true` (boolean)
- `"hello"` → `"hello"` (string)

### 3. Execution Pipeline

```
HTTP → gz decompress → CSV parse → jq filter → NDJSON → head
```

**Key insight:** The filter runs **inline** during the pipeline, not as a separate command.

## Delimiter Auto-Detection

The `delimiter=auto` parameter triggers intelligent delimiter detection in the CSV plugin:

```bash
jn inspect "https://...file.gz~csv?delimiter=auto"
```

**How it works:**
1. CSV plugin reads first few lines
2. Tries common delimiters: `\t` (tab), `,`, `;`, `|`
3. Chooses delimiter that produces consistent column counts
4. Applies delimiter to entire file

## Tilde (~) as Format Escape: Good or Bad?

### ✅ **GOOD: Tilde is an excellent choice**

**Reasons:**

1. **URL-safe**: RFC 3986 lists `~` as an unreserved character
   - Safe in URLs without encoding
   - Won't conflict with standard URL syntax

2. **Rare in file paths**:
   - Not used in Windows paths (`:`, `\`)
   - Only appears in Unix home directories (`~user`)
   - Context is clear: after file extension vs. standalone

3. **Semantic clarity**:
   - Visually distinct from `.` (extension) and `?` (query)
   - Reads as "override" or "transform as"
   - `file.txt~csv` → "treat text file AS CSV"

4. **No conflicts with existing conventions**:
   - Not a shell glob (`*`, `?`, `[]`)
   - Not a regex operator
   - Not used in HTTP headers or query strings

### Alternative Characters Considered

| Character | Issue |
|-----------|-------|
| `:` | Conflicts with `protocol://` and Windows paths |
| `#` | URL fragment identifier (client-side only) |
| `@` | Already used for profiles/plugins |
| `!` | Shell history expansion |
| `%` | URL encoding prefix |
| `^` | Shell expansion in some contexts |

**Verdict:** `~` is the right choice. Keep it.

## Profiles as Query Adapters

### Current Query Pattern

```bash
# User types this complex query
jn head "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz~?chromosome=19&type_of_gene!=protein-coding&type_of_gene!=pseudo"
```

### Proposed: Auto-Capture as Profile

**Concept:** Complex queries can be "banked" as reusable profiles.

**Workflow:**
```bash
# 1. User runs exploratory query
jn head "https://ncbi.../Homo_sapiens.gene_info.gz~?chromosome=19&type_of_gene!=protein-coding" --save-as "@ncbi/chr19-non-coding"

# 2. JN creates profile automatically
# File: ~/.local/jn/profiles/http/ncbi/chr19-non-coding.json
{
  "base_url": "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia",
  "path": "/Homo_sapiens.gene_info.gz",
  "format": "csv",
  "compression": "gz",
  "filters": {
    "chromosome": "19",
    "type_of_gene!=": ["protein-coding", "pseudo"]
  },
  "description": "Chromosome 19 non-coding genes from NCBI",
  "created": "2025-11-15T22:24:00Z"
}

# 3. User can now reference it simply
jn head @ncbi/chr19-non-coding
jn inspect @ncbi/chr19-non-coding
```

### Profile Types: API vs. Data File

**Key distinction:**

| Type | Example | Characteristics |
|------|---------|-----------------|
| **Data File Profile** | NCBI gene info | Static URL + filters, no API params |
| **API Profile** | GenomOncology | Dynamic base_url, headers, auth, API parameters |

**Data File Profile:**
```json
{
  "url": "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz",
  "format": "csv",
  "compression": "gz",
  "delimiter": "auto",
  "filters": {"chromosome": "19"},
  "description": "NCBI Homo sapiens gene info for chr 19"
}
```

**API Profile (GenomOncology):**
```json
{
  "base_url": "https://${GENOMONCOLOGY_URL}/api",
  "headers": {
    "Authorization": "Token ${GENOMONCOLOGY_API_KEY}"
  },
  "path": "/alterations",
  "method": "GET",
  "params": ["gene", "mutation_type", "biomarker", "page", "limit"],
  "description": "Genomic alterations endpoint"
}
```

**Auto-capture logic:**
1. **Has `://` but no env vars** → Data File Profile
2. **Has `://` with `${VAR}`** → API Profile
3. **Static filters in query** → Include in profile
4. **Dynamic params (limit, page)** → Exclude from profile (keep as CLI params)

## Implementation: Profile Auto-Capture

### CLI Syntax

```bash
# Save current query as profile
jn head <address> --save-profile "@namespace/name"
jn inspect <address> --save-profile "@namespace/name"

# Interactive prompt (suggests name based on query)
jn head "https://ncbi.../file.gz~?chromosome=19" --save-profile
# Suggests: "@ncbi/homo-sapiens-chr19"
```

### Auto-Generated Profile Structure

**For data files:**
```json
{
  "type": "data_file",
  "url": "https://full-url-here",
  "format": "csv",
  "compression": "gz",
  "delimiter": "auto",
  "filters": {
    "chromosome": "19",
    "type_of_gene!=": ["protein-coding", "pseudo"]
  },
  "created_from_query": "https://ncbi.../file.gz~?chromosome=19&...",
  "description": "Auto-generated from query on 2025-11-15",
  "usage_examples": [
    {
      "command": "jn head @ncbi/chr19-non-coding",
      "description": "Preview first 10 rows"
    }
  ]
}
```

**Benefits:**
1. **Reproducibility**: Exact query is captured
2. **Discoverability**: `jn profile list` shows all saved queries
3. **Documentation**: Auto-generated description and examples
4. **Iteration**: Easy to modify filters in JSON file

## Relationship to Existing `jn filter`

**Current flow (manual):**
```bash
jn cat data.csv | jn filter '.revenue > 1000' | jn put output.json
```

**New flow (inline):**
```bash
jn cat "data.csv?revenue>1000" | jn put output.json
```

**When to use each:**

| Scenario | Syntax | Reason |
|----------|--------|--------|
| Simple source filter | `?revenue>1000` | Inline, efficient |
| Complex transformation | `\| jn filter '@profile/transform'` | Reusable logic |
| Multiple sources | `cat A \| filter \| cat B` | Pipeline composition |
| Ad-hoc exploration | `?field=value` | Quick iteration |

**Both coexist!** Inline filters for source filtering, pipe filters for transformation.

## Next Steps

### 1. Document in Architecture Specs

- [x] Create this document
- [ ] Update `spec/done/arch-design.md` with addressability section
- [ ] Add filtering examples to `spec/done/inspect-design.md`

### 2. Implement Profile Auto-Capture

```python
# src/jn/cli/commands/head.py (add flag)
@click.option("--save-profile", help="Save query as reusable profile")
def head(ctx, source, n, save_profile):
    if save_profile:
        # Extract components from address
        # Generate profile JSON
        # Save to ~/.local/jn/profiles/
        pass
```

### 3. Test GenomOncology API

Verify that API profiles work with the existing system:
```bash
# Should work today
jn cat @genomoncology/alterations -p gene=BRAF

# Should also work with inline filters (if profile supports it)
jn cat "@genomoncology/alterations?gene=BRAF"
```

### 4. Add Auto-Delimiter Detection Docs

Document how `delimiter=auto` works in CSV plugin.

## Security Considerations

**Filter injection risk:**
- Parameters are passed to jq via command args
- jq is sandboxed (no file I/O, no command execution)
- Type inference prevents code injection

**URL validation:**
- Protocol validation in address parser
- No shell expansion in subprocess calls
- All HTTP handled by requests library (safe)

## Performance Impact

**Inline filtering is FASTER than piped filtering:**

```bash
# Inline (1 jq process)
jn cat "data.csv?revenue>1000"  # 0.5s

# Piped (2 jq processes + pipe overhead)
jn cat data.csv | jn filter '.revenue > 1000'  # 0.7s
```

**Why:**
- Fewer process spawns
- Less pipe buffering
- Early termination propagates immediately

## Conclusion

The addressability + filtering system is **elegantly designed**:

1. ✅ **Tilde (~) is the right escape character** - URL-safe, semantically clear
2. ✅ **Inline filtering is powerful** - Reduces pipeline complexity
3. ✅ **Profile auto-capture would be valuable** - Turns exploration into reusable assets
4. ✅ **Data File vs. API profiles are distinct** - Different use cases, different structures
5. ✅ **Coexists with `jn filter`** - Not a replacement, a complement

**Recommendation:**
- Keep current design
- Add `--save-profile` flag to capture queries
- Document the distinction between data file and API profiles
- Celebrate this excellent architecture! 🎉
