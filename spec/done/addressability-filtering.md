# Universal Addressability with On-the-Fly Filtering

## Overview

JN implements a universal addressing system that enables **filtering at the source** through URI syntax, eliminating intermediate `jn filter` commands.

## URI Syntax

```
address[~format][?parameters]
```

**Components:**
1. **address**: Base (file, URL, @profile, @plugin, -)
2. **~format**: Optional format override
3. **?parameters**: Config + filter parameters

**Examples:**
```bash
# HTTP + gzip + CSV + filtering
jn head "https://ftp.ncbi.nlm.nih.gov/.../Homo_sapiens.gene_info.gz~?chromosome=19&type_of_gene!=protein-coding"

# Local file + filter
jn inspect "./tests/data/people.csv?salary<80000"

# Format override + auto-delimiter
jn inspect "https://...file.gz~csv?delimiter=auto"
```

## How It Works

### 1. Tilde (~) Separates URL from JN Parameters

```
https://example.com/data?token=xyz~csv?chromosome=19
                            ^          ^           ^
                    URL query      escape     JN filters
```

**The `~` is critical for protocol URLs:**
- Before `~`: Full URL (including native query string)
- After `~`: Format override + JN parameters
- URL-safe (RFC 3986 unreserved character)

### 2. Filter Parameters → jq Expressions

**Simple operators:**
```
field=value   → .field == "value"
field!=value  → .field != "value"
field>value   → (.field | tonumber) > value
field<value   → (.field | tonumber) < value
field>=value  → (.field | tonumber) >= value
field<=value  → (.field | tonumber) <= value
```

**Type inference:**
- `"123"` → `123` (integer)
- `"12.34"` → `12.34` (float)
- `"true"` → `true` (boolean)
- `"hello"` → `"hello"` (string)

**Builder location:** `src/jn/filtering.py` (shared utility)

### 3. Execution Pipeline

```
HTTP → gz decompress → CSV parse → jq filter (subprocess) → NDJSON → head
```

**Key:** Filter runs as **separate subprocess** for proper backpressure, using the actual `jq` binary (not reimplementing jq logic).

## Tilde (~) Evaluation

**Verdict: ✅ Keep it!**

| ✅ Why | Details |
|--------|---------|
| **URL-safe** | RFC 3986 unreserved character |
| **Rare in paths** | Only `~user` in Unix (clear context) |
| **Semantic** | Reads as "treat AS" (file.txt~csv) |
| **No conflicts** | Not used in protocols, shells, regex |

**Alternatives rejected:** `:` (protocol conflict), `#` (fragment), `@` (profiles), `!` (shell)

## Shared Filter Builder

**No code duplication!** One builder (`filtering.py`) used by:
- `head.py` - inline filters in address
- `tail.py` - inline filters in address
- `inspect.py` - inline filters in address
- `cat.py` - inline filters in address
- All execute via `jn filter '<jq-expr>'` subprocess

**Architecture:**
1. `filtering.py` - Generator (simple syntax → jq expressions)
2. `jq_` plugin - Executor (runs jq binary)
3. `jq` binary - Evaluator (actual filtering)

## Inline vs. Piped Filters

**Inline (using filtering.py):**
```bash
jn cat "data.csv?revenue>1000"
```

**Piped (manual jq):**
```bash
jn cat data.csv | jn filter '.revenue > 1000'
```

**Both valid!** Inline for source filtering, pipes for complex transformations. Both use the same `jq` binary and executor.

## Future: Profile Save Feature

**Not implemented yet.** This section describes how query auto-capture could work.

### Concept

Complex queries can be "banked" as reusable profiles:

```bash
# Explore with inline filtering
jn head "https://ftp.ncbi.nlm.nih.gov/.../Homo_sapiens.gene_info.gz~?chromosome=19&type_of_gene!=protein-coding"

# Save as profile (proposed)
jn head "..." --save-profile @ncbi/chr19-non-coding

# Reuse
jn head @ncbi/chr19-non-coding
```

### Saved Profile Format

**Option 1: Keep whole URL structure (opaque blob)**

```json
{
  "type": "data_file",
  "full_address": "https://ftp.ncbi.nlm.nih.gov/.../Homo_sapiens.gene_info.gz~?chromosome=19&type_of_gene!=protein-coding",
  "description": "Chromosome 19 non-coding genes from NCBI"
}
```

**Execution:** Exact replay of original address.

**Option 2: Decompose into structured adapters**

```json
{
  "type": "data_file",
  "url": "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz",
  "adapters": [
    {
      "type": "compression",
      "format": "gz"
    },
    {
      "type": "format",
      "format": "csv",
      "config": {"delimiter": "auto"}
    },
    {
      "type": "filter",
      "filters": {
        "chromosome": "19",
        "type_of_gene!=": ["protein-coding", "pseudo"]
      }
    }
  ],
  "description": "Chromosome 19 non-coding genes from NCBI"
}
```

**Execution:** Rebuild address from adapters, then execute normally.

**Recommended: Option 2 (decomposed adapters)**

**Why:**
- **Editable**: Users can modify filters/config without parsing URIs
- **Composable**: Can create variations easily
- **Discoverable**: `jn profile info` shows structure clearly
- **Flexible**: Can add/remove/reorder adapters

### Multiple Profiles, Same URL

**Yes!** Different filter adapters on same base URL:

```json
// ~/.local/jn/profiles/ncbi/chr1-protein-coding.json
{
  "url": "https://ftp.ncbi.nlm.nih.gov/.../Homo_sapiens.gene_info.gz",
  "adapters": [
    {"type": "compression", "format": "gz"},
    {"type": "format", "format": "csv", "config": {"delimiter": "auto"}},
    {"type": "filter", "filters": {"chromosome": "1", "type_of_gene": "protein-coding"}}
  ]
}

// ~/.local/jn/profiles/ncbi/chr2-pseudogenes.json
{
  "url": "https://ftp.ncbi.nlm.nih.gov/.../Homo_sapiens.gene_info.gz",
  "adapters": [
    {"type": "compression", "format": "gz"},
    {"type": "format", "format": "csv", "config": {"delimiter": "auto"}},
    {"type": "filter", "filters": {"chromosome": "2", "type_of_gene": "pseudo"}}
  ]
}
```

**Usage:**
```bash
jn head @ncbi/chr1-protein-coding
jn head @ncbi/chr2-pseudogenes
```

### Adapter Execution Mapping

**From profile → Reconstructed address → Same execution path:**

```
Profile adapters:
  [compression: gz] + [format: csv, delimiter=auto] + [filter: chr=19, type!=protein-coding]
          ↓
Rebuild address:
  https://...file.gz~csv?delimiter=auto&chromosome=19&type_of_gene!=protein-coding
          ↓
Parse (existing code):
  base: https://...file.gz
  compression: gz
  format_override: csv
  parameters: {delimiter: auto, chromosome: 19, type_of_gene!=: protein-coding}
          ↓
Execute (existing pipeline):
  HTTP → gz decompress → CSV parse → jq filter → NDJSON
```

**No new execution code needed!** Profile just reconstructs the address string, then uses existing parser + pipeline.

### Editing Profiles

**JSON files are human-editable:**

```bash
# Edit with any text editor
vim ~/.local/jn/profiles/ncbi/chr19-non-coding.json

# Change filter
{
  "filters": {
    "chromosome": "19",          # Change to "1"
    "type_of_gene!=": ["pseudo"]  # Add/remove values
  }
}

# Or use jq to edit programmatically
jq '.adapters[2].filters.chromosome = "1"' profile.json
```

**Validation:**
```bash
jn profile check @ncbi/chr19-non-coding  # Validate syntax
jn profile test @ncbi/chr19-non-coding   # Test execution
```

### Implementation Notes

**CLI flag:**
```python
@click.option("--save-profile", help="Save query as profile @namespace/name")
def head(ctx, source, n, save_profile):
    if save_profile:
        addr = parse_address(source)
        profile = decompose_to_adapters(addr)
        save_profile_json(save_profile, profile)
```

**Adapter types:**
- `compression` - gz, bz2, xz
- `format` - csv, json, yaml, etc. (with config)
- `filter` - field operators (from filtering.py)

**Data File vs. API Profile:**
- **Data File**: Static URL, decomposed adapters (this section)
- **API**: Dynamic base_url, headers, env vars (existing HTTP profiles)

### Open Questions

1. **Adapter ordering**: Does order matter? (Yes - compression before format)
2. **Adapter composition**: Can users chain multiple filters? (Yes, merge into single jq expression)
3. **Template support**: Should profiles support `${VAR}` substitution? (Maybe for advanced use)
