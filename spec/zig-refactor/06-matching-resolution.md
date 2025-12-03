# Matching and Resolution

> **Purpose**: How JN decides which plugin handles a given address.

---

## The Resolution Problem

Given an address like `https://api.example.com/data.csv.gz`, JN must determine:
1. Which protocol plugin fetches the data (http)
2. Which compression plugin decompresses it (gz)
3. Which format plugin parses it (csv)
4. In what order to chain them

This document explains how that resolution works.

---

## Address Parsing

Every address is parsed into components:

```
[protocol://]path[~format][?params]
```

### Components

| Component | Example | Purpose |
|-----------|---------|---------|
| Protocol | `https://` | Determines protocol plugin |
| Path | `api.example.com/data.csv.gz` | Resource location |
| Format override | `~csv` | Forces specific format |
| Parameters | `?delimiter=;` | Plugin configuration |

### Address Types

| Type | Detection | Example |
|------|-----------|---------|
| File | No `://`, exists on filesystem | `data.csv` |
| URL | Has `://` | `https://api.com/data` |
| Profile | Starts with `@` | `@myapi/users` |
| Stdin | `-` or empty | `-`, `-~csv` |
| Glob | Contains `*`, `**`, `?` | `data/*.csv` |

### Parsing Examples

```
Input: data.csv
├── Type: file
├── Path: data.csv
├── Format: csv (inferred from .csv)
└── Compression: none

Input: https://api.com/data.csv.gz
├── Type: URL
├── Protocol: https
├── Path: api.com/data.csv.gz
├── Format: csv (inferred from .csv)
└── Compression: gz (detected from .gz)

Input: @myapi/users?limit=10
├── Type: profile
├── Namespace: myapi
├── Name: users
├── Params: {limit: 10}
└── Format: (from profile)

Input: data.txt~csv?delimiter=;
├── Type: file
├── Path: data.txt
├── Format: csv (override)
└── Params: {delimiter: ";"}
```

---

## Pattern Matching

Plugins declare regex patterns they handle:

```toml
[tool.jn]
matches = [".*\\.csv$", ".*\\.tsv$"]
```

### Matching Algorithm

1. **Compile patterns**: Each plugin's patterns become a regex
2. **Test against address**: Check if address matches pattern
3. **Collect matches**: Multiple plugins may match
4. **Rank by specificity**: Longer patterns win
5. **Apply priority**: User > bundled, Zig > Python

### Specificity Scoring

Specificity = length of pattern string.

```
Pattern: ".*\.csv$"           Specificity: 9
Pattern: ".*_test\.csv$"      Specificity: 14  ← wins for "foo_test.csv"
Pattern: ".*"                 Specificity: 2   ← lowest priority
```

### Priority Tiebreaking

When specificity is equal:

1. **Location priority**: Project > User > Bundled
2. **Language priority**: Zig > Python
3. **First match**: Order in pattern list

### Common Patterns

| Pattern | Matches | Plugin |
|---------|---------|--------|
| `.*\.csv$` | `.csv` files | csv |
| `.*\.tsv$` | `.tsv` files | csv (tab delimiter) |
| `.*\.json$` | `.json` files | json |
| `.*\.jsonl$` | `.jsonl` files | jsonl |
| `^https?://` | HTTP/HTTPS URLs | http |
| `.*\.gz$` | Gzip compressed | gz |
| `^@` | Profile references | (profile resolver) |

---

## Format Override

The `~format` syntax bypasses pattern matching:

```bash
jn cat data.txt~csv           # Force CSV parser on .txt file
jn cat @myapi/export~json     # Force JSON parser on API response
```

### Override Resolution

1. Extract format name from `~format`
2. Look up plugin by name (not pattern)
3. Check if plugin supports requested mode
4. Use plugin directly

### When to Use Override

- Text file is actually CSV: `data.txt~csv`
- JSON file is NDJSON: `data.json~jsonl`
- API returns unlabeled data: `@api/data~csv`
- Force specific parser: `data.csv~csvfast`

---

## Multi-Stage Resolution

Complex addresses may require multiple plugins:

### Example: `https://api.com/data.csv.gz`

```
Stage 1: Protocol
├── Match: ^https?:// → http plugin
└── Output: raw bytes (compressed CSV)

Stage 2: Compression
├── Match: .*\.gz$ → gz plugin
└── Output: raw bytes (CSV)

Stage 3: Format
├── Match: .*\.csv$ → csv plugin
└── Output: NDJSON
```

### Pipeline Construction

```
http --mode=raw | gz --mode=raw | csv --mode=read
```

Three processes connected by pipes, running concurrently.

### Extension Stripping

For multi-stage detection, extensions are stripped progressively:

```
data.csv.gz
├── .gz detected → compression stage
└── strip .gz → data.csv
    ├── .csv detected → format stage
    └── done
```

---

## Compression Detection

### By Extension

| Extension | Compression |
|-----------|-------------|
| `.gz` | gzip |
| `.bz2` | bzip2 |
| `.xz` | xz/lzma |
| `.zst` | zstd |

### By Magic Bytes (Optional)

When extension is ambiguous, check file header:

| Magic | Compression |
|-------|-------------|
| `1f 8b` | gzip |
| `42 5a 68` | bzip2 |
| `fd 37 7a 58 5a` | xz |

### Decompression Stage

Compression is always handled as a separate stage:

```
file → gz --mode=raw → csv --mode=read → stdout
```

This allows:
- Any format to be compressed
- Streaming decompression
- Consistent pipeline model

---

## CSV Delimiter Detection

CSV files may use different delimiters:

| Delimiter | Common In |
|-----------|-----------|
| `,` (comma) | Standard CSV |
| `\t` (tab) | TSV files |
| `;` (semicolon) | European locales |
| `|` (pipe) | Database exports |

### Detection Algorithm

1. **Extension hints**: `.tsv` → tab, `.csv` → comma
2. **Sample analysis**: Read first 50 lines
3. **Score candidates**: Each delimiter scored by:
   - Consistency (same column count per line)
   - Reasonable count (2-100 columns)
   - No empty columns
4. **Select best**: Highest score wins
5. **Fallback**: Comma if uncertain

### Explicit Override

```bash
jn cat "data.csv?delimiter=;"        # Semicolon
jn cat "data.csv?delimiter=tab"      # Tab
jn cat "data.csv?delimiter=%7C"      # Pipe (URL-encoded)
```

---

## Profile Resolution

Profile references (`@namespace/name`) have special handling:

### Resolution Flow

```
@myapi/users?limit=10
    │
    ▼
1. Parse reference
   ├── Namespace: myapi
   ├── Name: users
   └── Params: {limit: 10}
    │
    ▼
2. Find profile
   ├── Check: ~/.local/jn/profiles/http/myapi/users.json
   ├── Load: _meta.json + users.json (merged)
   └── Substitute: ${API_TOKEN} → actual value
    │
    ▼
3. Determine plugin
   ├── Profile type: http
   └── Plugin: http
    │
    ▼
4. Build request
   ├── URL: https://api.example.com/users?limit=10
   ├── Headers: Authorization: Bearer xxx
   └── Method: GET
    │
    ▼
5. Execute
   └── http --mode=read --url=... --headers=...
```

### Profile Type Routing

Profile type determines which plugin handles it:

| Profile Type | Plugin | Location |
|--------------|--------|----------|
| `http` | http | `profiles/http/` |
| `zq` | (filter) | `profiles/zq/` |
| `gmail` | gmail | `profiles/gmail/` |
| `mcp` | mcp | `profiles/mcp/` |
| `duckdb` | duckdb | `profiles/duckdb/` |

---

## Resolution Summary

### Decision Tree

```
Is there a format override (~format)?
├── Yes → Look up plugin by name
└── No ↓

Is it a profile reference (@...)?
├── Yes → Resolve profile, use profile's plugin type
└── No ↓

Is it a URL (has ://)?
├── Yes → Match protocol, then format
└── No ↓

Is it a glob pattern?
├── Yes → Expand glob, process each file
└── No ↓

Is it stdin (-)?
├── Yes → Use format from override or error
└── No ↓

Is it a file?
├── Yes → Detect compression, then format
└── No → Error: unknown address type
```

### Resolution Order

1. **Format override**: `~format` takes precedence
2. **Profile**: `@namespace/name` resolved via profile system
3. **Protocol**: URL scheme determines protocol plugin
4. **Compression**: `.gz`, `.bz2`, etc. add decompression stage
5. **Format**: Extension determines format plugin
6. **Fallback**: Error if no match

---

## Design Decisions

### Why Regex Patterns?

**Pros**:
- Flexible (extensions, paths, protocols)
- Specificity via pattern length
- No explicit registration

**Cons**:
- Parsing overhead (mitigated by caching)
- Complex patterns hard to debug

### Why Extension-Based Detection?

**Pros**:
- Fast (string suffix check)
- Predictable
- User controls via renaming

**Cons**:
- Wrong extension = wrong parser
- Requires override for mismatches

### Why Multi-Stage Pipelines?

**Pros**:
- Composable (any format + any compression)
- Parallel (stages run concurrently)
- Streaming (constant memory)

**Cons**:
- Process overhead (mitigated by shared libraries)
- More complex orchestration

---

## See Also

- [05-plugin-system.md](05-plugin-system.md) - Plugin interface details
- [07-profiles.md](07-profiles.md) - Profile resolution
- [03-users-guide.md](03-users-guide.md) - Address syntax examples
