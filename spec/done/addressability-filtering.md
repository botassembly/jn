# Universal Addressability and Inline Filtering

## URI Syntax

```
address[~format][?parameters]
```

**Components:**
1. **address**: Base resource (file path, URL, @profile, @plugin, -)
2. **~format**: Optional format override (e.g., ~csv, ~json)
3. **?parameters**: Config + filter parameters (e.g., ?delimiter=auto&salary>50000)

**Examples:**
```bash
# HTTP + gzip + CSV + filtering
jn head "https://ftp.ncbi.nlm.nih.gov/.../file.gz~?chromosome=19&type_of_gene!=protein-coding"

# Local file + filter
jn inspect "./tests/data/people.csv?salary<80000"

# Format override
jn cat "data.txt~json"
```

---

## Address Routing

JN routes addresses by detecting patterns in the base address component:

### Protocol URLs
- **Pattern**: `http://` or `https://`
- **Handler**: HTTP plugin fetches remote content
- **Example**: `https://example.com/data.csv`

### File Paths
- **Absolute**: `/home/user/data.csv`
- **Relative**: `data.csv` (resolved from current directory)
- **Explicit relative**: `./data.csv` or `../data.csv`
- **Handler**: File plugin reads from filesystem

### Profiles
- **Pattern**: `@namespace/name`
- **Handler**: Profile plugin loads JSON config, resolves to actual address
- **Example**: `@ncbi/genes` → `https://ftp.ncbi.nlm.nih.gov/.../Homo_sapiens.gene_info.gz`

### Plugins
- **Pattern**: `@plugin_name` (no slash)
- **Handler**: Direct plugin invocation
- **Example**: `@jq` for jq filter plugin

### Stdin
- **Pattern**: `-`
- **Handler**: Read from stdin (for pipeline composition)

---

## Format Routing

Formats are detected in two ways:

### 1. File Extension Detection
```bash
data.csv        → CSV plugin
data.json       → JSON plugin
data.yaml       → YAML plugin
data.csv.gz     → CSV plugin (after gz decompression)
```

Plugin declares patterns in `[tool.jn] matches = [".*\\.csv$", ".*\\.json$"]`

### 2. Format Override (Tilde)
```bash
data.txt~csv    → CSV plugin (ignore .txt extension)
data.gz~json    → JSON plugin (decompress, parse as JSON)
```

**Override wins over extension.**

---

## Tilde (~) Separator

The `~` separates URL query strings from JN format/parameters:

```
https://example.com/data?token=xyz~csv?chromosome=19
                            ^      ^               ^
                    URL query  escape    JN format+filters
```

**Critical for protocol URLs:**
- Before `~`: Full URL (including native `?query`)
- After `~`: JN format override + parameters

**Why tilde?**
- URL-safe (RFC 3986 unreserved character)
- Rare in file paths (only `~user` in Unix)
- Semantic ("treat AS")
- No conflicts with protocols, shells, regex

**Alternatives rejected:** `:` (protocol conflict), `#` (fragment), `@` (profiles), `!` (shell)

---

## Query Parameters

Parameters after `?` serve two purposes:

### 1. Format Config
```bash
data.csv?delimiter=tab          # CSV with tab delimiter
data.json?indent=2              # JSON with pretty-printing
```

Passed to format plugin as config dict.

### 2. Filter Operators
```bash
data.csv?salary>50000           # Numeric comparison
data.csv?name=Alice             # Equality
data.csv?status!=inactive       # Inequality
```

Converted to jq expressions by `filtering.py`.

**Operator mapping:**
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

---

## JQ Streaming (The Right Way)

Filters run as **separate subprocess** for proper backpressure:

```python
# reader process pipes to filter process
reader = Popen([...], stdout=PIPE)
filter = Popen(["jq", expr], stdin=reader.stdout, stdout=PIPE)
reader.stdout.close()  # Critical for SIGPIPE
```

**Why subprocess, not inline?**
1. **Automatic backpressure**: OS pipe buffers block when full
2. **Parallel execution**: Reader and filter run simultaneously on different CPUs
3. **Early termination**: `| head -n 10` sends SIGPIPE backward, stopping reader
4. **Constant memory**: No buffering in Python process

**Execution pipeline:**
```
HTTP fetch → gz decompress → CSV parse → jq filter (subprocess) → NDJSON → head
    ↓             ↓              ↓              ↓                     ↓
 Process 1    Process 2      Process 3      Process 4           Process 5
```

All stages run concurrently with automatic flow control via OS pipes.

---

## Shared Filter Builder

**One builder (`filtering.py`), no duplication:**

```python
# src/jn/filtering.py - Converts simple operators to jq expressions
def build_jq_filter(filters: List[Tuple[str, str, str]]) -> str:
    # [("salary", ">", "50000")] → 'select(.salary | tonumber) > 50000)'
```

**Used by all commands:**
- `head.py` - Inline filters in address
- `tail.py` - Inline filters in address
- `cat.py` - Inline filters in address
- `inspect.py` - Inline filters in address

**Architecture:**
1. `filtering.py` - Generator (simple syntax → jq expression string)
2. `jq_` plugin - Executor (runs `jq` binary as subprocess)
3. `jq` binary - Evaluator (actual filtering)

**No code duplication.** No reimplementing jq logic.

---

## Inline vs. Piped

**Inline (filter at source):**
```bash
jn cat "data.csv?revenue>1000"
```

**Piped (filter downstream):**
```bash
jn cat data.csv | jn filter '.revenue > 1000'
```

**Both valid!**
- Inline: Filter early (reduce data transfer)
- Piped: Complex transformations (full jq expressions)
- Both use same `jq` binary and subprocess architecture
