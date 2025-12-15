# ZQ Functions Specification

This document specifies functions for ZQ, the NDJSON filter engine used by JN.

## Overview

Functions are organized into categories:

| Category | Description | Example |
|----------|-------------|---------|
| **Generator** | Create values from nothing | `now`, `uuid`, `random` |
| **Transform** | Modify existing values | `trim`, `incr`, `toggle` |
| **Encoding** | Encode/decode values | `base64`, `md5`, `urlencode` |
| **Case** | Change string casing | `capitalize`, `snakecase` |
| **Predicate** | Return boolean checks | `empty`, `blank`, `defined` |
| **String** | String manipulation | `words`, `lines`, `squeeze` |
| **Math** | Mathematical operations | `sqrt`, `pow`, `clamp` |

---

## Generator Functions

Functions that create new values without requiring input. These ignore the current JSON value.

### Date/Time Generators

| Function | Output Type | Description | Example Output |
|----------|-------------|-------------|----------------|
| `day` | integer | Current day of month (1-31) | `15` |
| `epoch` | integer | Unix timestamp in seconds | `1734282600` |
| `epoch_ms` | integer | Unix timestamp in milliseconds | `1734282600000` |
| `hour` | integer | Current hour (0-23) | `17` |
| `minute` | integer | Current minute (0-59) | `30` |
| `month` | integer | Current month (1-12) | `12` |
| `now` | string | ISO 8601 timestamp (UTC) | `"2024-12-15T17:30:00Z"` |
| `second` | integer | Current second (0-59) | `45` |
| `time` | string | Time only (HH:MM:SS) | `"17:30:45"` |
| `today` | string | Date only (YYYY-MM-DD) | `"2024-12-15"` |
| `weekday` | string | Day of week name | `"Sunday"` |
| `weekday_num` | integer | Day of week (0=Sun, 6=Sat) | `0` |
| `week` | integer | ISO week number (1-53) | `50` |
| `year` | integer | Current year | `2024` |

**Usage:**
```bash
# Add timestamp to each record
jn cat data.csv | jn filter '.created_at = now'

# Add date components
jn cat data.csv | jn filter '{date: today, year: year, month: month, day: day, data: .}'
```

### ID Generators

| Function | Output Type | Length | Description | Example Output |
|----------|-------------|--------|-------------|----------------|
| `nanoid` | string | 21 | NanoID (URL-safe) | `"V1StGXR8_Z5jdHi6B-myT"` |
| `shortid` | string | 8 | Base62 short ID | `"a1B2c3D4"` |
| `sid` | string | 6 | Base62 super-short ID | `"xK9mPq"` |
| `ulid` | string | 26 | ULID (time-sortable) | `"01ARZ3NDEKTSV4RRFFQ69G5FAV"` |
| `uuid` | string | 36 | UUID v4 (random) | `"550e8400-e29b-41d4-a716-446655440000"` |
| `uuid7` | string | 36 | UUID v7 (time-sortable) | `"018c5a2e-0b9a-7def-8a1b-1c2d3e4f5a6b"` |
| `xid` | string | 20 | XID (compact, sortable) | `"9m4e2mr0ui3e8a215n4g"` |

**ID Format Comparison:**

| Format | Sortable | Length | Chars | Uniqueness |
|--------|----------|--------|-------|------------|
| `sid` | No | 6 | base62 | 56.8 billion |
| `shortid` | No | 8 | base62 | 218 trillion |
| `xid` | Yes | 20 | base32hex | Time + machine + counter |
| `nanoid` | No | 21 | base64url | 2^126 |
| `ulid` | Yes | 26 | base32 | Time + random |
| `uuid` | No | 36 | hex+dash | 2^122 |
| `uuid7` | Yes | 36 | hex+dash | Time + random |

**Usage:**
```bash
# Add unique ID to each record
jn cat data.csv | jn filter '.id = shortid'

# Time-sortable IDs for events
jn cat events.csv | jn filter '.event_id = ulid'
```

### Random Generators

| Function | Output Type | Description | Example Output |
|----------|-------------|-------------|----------------|
| `random` | float | Random float 0.0 to 1.0 | `0.7234891...` |
| `randbool` | boolean | Random true/false | `true` |

**Usage:**
```bash
# Random sampling (keep ~10% of records)
jn cat data.csv | jn filter 'select(random < 0.1)'

# Random boolean field
jn cat users.csv | jn filter '.verified = randbool'
```

### Sequence Generators

| Function | Output Type | Description | Example Output |
|----------|-------------|-------------|----------------|
| `rownum` | integer | Alias for seq | `1`, `2`, `3`... |
| `seq` | integer | Incrementing counter (per run) | `1`, `2`, `3`... |

**Usage:**
```bash
# Add row numbers
jn cat data.csv | jn filter '{row: seq, data: .}'

# Create batch IDs
jn cat data.csv | jn filter '.batch_id = seq'
```

---

## Transform Functions

Functions that modify the input value.

### Numeric Transforms

| Function | Input | Output | Description | Example |
|----------|-------|--------|-------------|---------|
| `abs` | number | number | Absolute value | `-5` → `5` |
| `decr` | number | number | Subtract 1 | `5` → `4` |
| `double` | number | number | Multiply by 2 | `5` → `10` |
| `half` | number | number | Divide by 2 | `10` → `5` |
| `incr` | number | number | Add 1 | `5` → `6` |
| `negate` | number | number | Flip sign | `5` → `-5` |
| `toggle` | boolean | boolean | Flip boolean | `true` → `false` |

**Usage:**
```bash
# Increment version number
jn cat package.json | jn filter '.version = (.version | incr)'

# Toggle active flag
jn cat users.json | jn filter '.active = (.active | toggle)'

# Negate balance
jn cat ledger.json | jn filter '.debit = (.credit | negate)'
```

### String Transforms

| Function | Input | Output | Description | Example |
|----------|-------|--------|-------------|---------|
| `chomp` | string | string | Remove trailing newline | `"hello\n"` → `"hello"` |
| `ltrim` | string | string | Trim leading whitespace | `"  hi"` → `"hi"` |
| `rtrim` | string | string | Trim trailing whitespace | `"hi  "` → `"hi"` |
| `squeeze` | string | string | Collapse multiple spaces | `"a  b"` → `"a b"` |
| `trim` | string | string | Trim both sides | `"  hi  "` → `"hi"` |

**Usage:**
```bash
# Clean whitespace
jn cat data.csv | jn filter '.name = (.name | trim | squeeze)'
```

### String Splitting

| Function | Input | Output | Description | Example |
|----------|-------|--------|-------------|---------|
| `chars` | string | array | Split into characters | `"abc"` → `["a","b","c"]` |
| `lines` | string | array | Split by newlines | `"a\nb"` → `["a","b"]` |
| `words` | string | array | Split by whitespace | `"a b c"` → `["a","b","c"]` |

**Usage:**
```bash
# Tokenize text
jn cat posts.json | jn filter '.tokens = (.body | words)'

# Count words
jn cat posts.json | jn filter '.word_count = (.body | words | length)'
```

### Slug/URL Transforms

| Function | Input | Output | Description | Example |
|----------|-------|--------|-------------|---------|
| `slugify` | string | string | URL-safe slug | `"Hello World!"` → `"hello-world"` |

**Usage:**
```bash
# Generate URL slugs from titles
jn cat posts.csv | jn filter '.slug = (.title | slugify)'
```

---

## Encoding Functions

Functions for encoding, decoding, and hashing.

### Base Encoding

| Function | Input | Output | Description | Example |
|----------|-------|--------|-------------|---------|
| `base64` | string | string | Base64 encode | `"hello"` → `"aGVsbG8="` |
| `base64d` | string | string | Base64 decode | `"aGVsbG8="` → `"hello"` |
| `hex` | string | string | Hex encode | `"hi"` → `"6869"` |
| `unhex` | string | string | Hex decode | `"6869"` → `"hi"` |

**Usage:**
```bash
# Encode sensitive data
jn cat data.json | jn filter '.payload = (.data | base64)'

# Decode hex values
jn cat packets.json | jn filter '.decoded = (.hex_data | unhex)'
```

### URL Encoding

| Function | Input | Output | Description | Example |
|----------|-------|--------|-------------|---------|
| `urldecode` | string | string | URL decode | `"a%20b"` → `"a b"` |
| `urlencode` | string | string | URL encode | `"a b"` → `"a%20b"` |

**Usage:**
```bash
# Build URLs
jn cat queries.json | jn filter '.url = "https://api.com/search?q=" + (.query | urlencode)'
```

### Hash Functions

| Function | Input | Output | Description | Example |
|----------|-------|--------|-------------|---------|
| `crc32` | string | string | CRC32 checksum (hex) | `"hello"` → `"3610a686"` |
| `md5` | string | string | MD5 hash (hex) | `"hello"` → `"5d41402abc4b2a76..."` |
| `sha1` | string | string | SHA1 hash (hex) | `"hello"` → `"aaf4c61ddcc5e8a2..."` |
| `sha256` | string | string | SHA256 hash (hex) | `"hello"` → `"2cf24dba5fb0a30e..."` |

**Usage:**
```bash
# Create dedup key from email
jn cat users.json | jn filter '.dedup_key = (.email | md5)'

# Checksum for data integrity
jn cat files.json | jn filter '.checksum = (.content | sha256)'
```

---

## Case Functions

Functions for changing string case.

| Function | Input | Output | Description | Example |
|----------|-------|--------|-------------|---------|
| `camelcase` | string | string | toCamelCase | `"hello_world"` → `"helloWorld"` |
| `capitalize` | string | string | First letter upper | `"hello"` → `"Hello"` |
| `kebabcase` | string | string | to-kebab-case | `"hello_world"` → `"hello-world"` |
| `pascalcase` | string | string | ToPascalCase | `"hello_world"` → `"HelloWorld"` |
| `screamcase` | string | string | SCREAMING_CASE | `"helloWorld"` → `"HELLO_WORLD"` |
| `snakecase` | string | string | to_snake_case | `"helloWorld"` → `"hello_world"` |
| `titlecase` | string | string | Title Case | `"hello world"` → `"Hello World"` |

**Usage:**
```bash
# Normalize field names
jn cat data.json | jn filter 'to_entries | map({key: (.key | snakecase), value}) | from_entries'

# Format names
jn cat users.csv | jn filter '.display_name = (.name | titlecase)'
```

---

## Predicate Functions

Functions that return boolean values for filtering/conditionals.

| Function | Input | Output | Description | Example |
|----------|-------|--------|-------------|---------|
| `blank` | any | boolean | Is null, empty string, empty array, or empty object | `""` → `true`, `[]` → `true` |
| `defined` | any | boolean | Is not null | `null` → `false`, `0` → `true` |
| `empty` | string/array/object | boolean | Has zero length | `""` → `true`, `"a"` → `false` |
| `numeric` | any | boolean | Is a number or numeric string | `"42"` → `true` |
| `present` | any | boolean | Not blank (opposite of blank) | `"hi"` → `true` |

**Usage:**
```bash
# Filter out blank values
jn cat data.csv | jn filter 'select(.email | present)'

# Check for defined fields
jn cat data.json | jn filter 'select(.optional_field | defined)'

# Skip empty arrays
jn cat data.json | jn filter 'select(.items | empty | not)'
```

---

## Math Functions

Mathematical operations beyond basic arithmetic.

### Basic Math

| Function | Input | Output | Description | Example |
|----------|-------|--------|-------------|---------|
| `ceil` | float | integer | Round up | `4.2` → `5` |
| `exp` | number | float | e^x | `1` → `2.718...` |
| `floor` | float | integer | Round down | `4.8` → `4` |
| `ln` | number | float | Natural log | `2.718` → `1.0` |
| `log10` | number | float | Base-10 log | `100` → `2` |
| `log2` | number | float | Base-2 log | `8` → `3` |
| `round` | float | integer | Round to nearest | `4.5` → `5` |
| `sqrt` | number | float | Square root | `9` → `3` |

### Trigonometry

| Function | Input | Output | Description |
|----------|-------|--------|-------------|
| `acos` | number | float | Arc cosine |
| `asin` | number | float | Arc sine |
| `atan` | number | float | Arc tangent |
| `cos` | number | float | Cosine |
| `sin` | number | float | Sine |
| `tan` | number | float | Tangent |

**Note:** Existing in ZQ: `floor`, `ceil`, `round`, `fabs`

---

## Parametric Functions

Functions that take arguments. These require special syntax.

### String Functions with Parameters

| Function | Syntax | Description | Example |
|----------|--------|-------------|---------|
| `default` | `default(value)` | Use value if null | `.name \| default("Unknown")` |
| `lpad` | `lpad(n, char)` | Left pad to length | `"42" \| lpad(5, "0")` → `"00042"` |
| `repeat` | `repeat(n)` | Repeat string n times | `"ab" \| repeat(3)` → `"ababab"` |
| `replace` | `replace(old, new)` | Replace substring | `"hello" \| replace("l", "L")` → `"heLLo"` |
| `rpad` | `rpad(n, char)` | Right pad to length | `"42" \| rpad(5, "0")` → `"42000"` |
| `substr` | `substr(start, len)` | Extract substring | `"hello" \| substr(1, 3)` → `"ell"` |
| `truncate` | `truncate(n)` | Truncate to n chars | `"hello world" \| truncate(5)` → `"hello"` |

### Numeric Functions with Parameters

| Function | Syntax | Description | Example |
|----------|--------|-------------|---------|
| `clamp` | `clamp(min, max)` | Clamp to range | `150 \| clamp(0, 100)` → `100` |
| `pow` | `pow(n)` | Raise to power | `2 \| pow(3)` → `8` |
| `randint` | `randint(min, max)` | Random integer in range | `randint(1, 100)` → `42` |
| `roundto` | `roundto(places)` | Round to decimal places | `3.14159 \| roundto(2)` → `3.14` |

### Hash Functions with Parameters

| Function | Syntax | Description | Example |
|----------|--------|-------------|---------|
| `hash` | `hash(n)` | Hash truncated to n chars | `"hello" \| hash(8)` → `"5d41402a"` |

**Usage:**
```bash
# Default values
jn cat data.csv | jn filter '.status = (.status | default("pending"))'

# Truncate long text
jn cat posts.json | jn filter '.excerpt = (.body | truncate(200))'

# Clamp values
jn cat scores.json | jn filter '.score = (.raw_score | clamp(0, 100))'

# Pad IDs
jn cat data.csv | jn filter '.padded_id = (.id | tostring | lpad(10, "0"))'
```

---

## Implementation Priority

### Phase 1: Core Generators
High value, straightforward implementation.

| Function | Complexity | Notes |
|----------|------------|-------|
| `now` | Low | Zig stdlib timestamp |
| `today` | Low | Date portion of now |
| `epoch` | Low | Zig stdlib |
| `epoch_ms` | Low | Zig stdlib |
| `uuid` | Medium | Random bytes + formatting |
| `shortid` | Medium | Random base62 |
| `seq` | Low | Global counter |
| `random` | Low | Zig stdlib PRNG |

### Phase 2: Essential Transforms
Most requested data cleaning operations.

| Function | Complexity | Notes |
|----------|------------|-------|
| `trim` | Low | String manipulation |
| `ltrim` | Low | String manipulation |
| `rtrim` | Low | String manipulation |
| `incr` | Low | Arithmetic |
| `decr` | Low | Arithmetic |
| `toggle` | Low | Boolean flip |
| `slugify` | Medium | Regex-like transforms |
| `capitalize` | Low | String manipulation |

### Phase 3: Encoding
Data interchange essentials.

| Function | Complexity | Notes |
|----------|------------|-------|
| `base64` | Medium | Zig stdlib |
| `base64d` | Medium | Zig stdlib |
| `hex` | Low | Simple encoding |
| `unhex` | Low | Simple decoding |
| `urlencode` | Medium | Character escaping |
| `urldecode` | Medium | Character unescaping |
| `md5` | High | Hash implementation |
| `sha256` | High | Hash implementation |

### Phase 4: Advanced
Nice-to-have features.

| Function | Complexity | Notes |
|----------|------------|-------|
| `ulid` | Medium | Timestamp + random |
| `nanoid` | Medium | Custom alphabet |
| `snakecase` | Medium | Case detection |
| `camelcase` | Medium | Case detection |
| `words` | Low | Split by whitespace |
| `lines` | Low | Split by newline |
| Parametric functions | High | Parser changes needed |

---

## Existing ZQ Functions Reference

Functions already implemented in ZQ (for reference):

### Type Functions
- `tonumber` - String to number
- `tostring` - Any to string
- `type` - Returns type name
- `length` - String/array/object length
- `keys` - Object keys as array
- `values` - Object values as array

### Type Checks
- `isnumber`, `isstring`, `isboolean`, `isnull`, `isarray`, `isobject`

### Array Functions
- `first`, `last`, `reverse`, `sort`, `unique`, `flatten`

### Aggregation (with -s)
- `add`, `min`, `max`, `group_by`, `sort_by`, `unique_by`, `min_by`, `max_by`, `map`

### String Functions
- `ascii_downcase`, `ascii_upcase`, `split`, `join`
- `startswith`, `endswith`, `contains`, `test`
- `ltrimstr`, `rtrimstr`

### Object Functions
- `has`, `del`, `to_entries`, `from_entries`

### Math Functions
- `floor`, `ceil`, `round`, `fabs`

---

## Design Decisions

### 1. Generator Function Behavior

Generator functions ignore input and produce values:

```bash
# These are equivalent:
echo '{"x":1}' | jn filter '.id = uuid'
echo '{}' | jn filter '.id = uuid'
```

### 2. Case Sensitivity

All function names are lowercase to match jq conventions.

### 3. Error Handling

- Type mismatches return null (like jq)
- Invalid operations produce no output for that record
- Errors don't stop the stream

### 4. Sequence State

`seq` maintains state across the stream but resets between runs:

```bash
# First run: 1, 2, 3...
jn cat data.csv | jn filter '.row = seq'

# Second run: starts at 1 again
jn cat data.csv | jn filter '.row = seq'
```

### 5. Random Determinism

Random functions are not deterministic by default. For reproducible pipelines, consider using hash-based approaches:

```bash
# Non-deterministic (different each run)
jn cat data.csv | jn filter '.sample = random'

# Deterministic (same each run, based on input)
jn cat data.csv | jn filter '.sample = (.id | md5 | substr(0,8) | tonumber) / 4294967295'
```
