# ZQ: JN Filter Language

**ZQ** is a minimal, high-performance filter language for NDJSON streams, implemented in Zig.

## Goals

1. **2-3x faster than jq** for common filter operations
2. **Zero dependencies** - single static binary
3. **JN-optimized** - only features JN actually uses
4. **Streaming** - constant memory, instant first output

## Supported Expressions

### Identity & Field Access
```
.                    # Pass through unchanged
.name                # Extract field
.user.address.city   # Nested field path
.[0]                 # Array index
.[-1]                # Last element
.[]                  # Iterate array elements
```

### Filtering
```
select(.active)              # Truthy check
select(.age > 30)            # Numeric comparison
select(.status == "active")  # String equality
select(.x != null)           # Null check
select(.a > 1 and .b < 10)   # Boolean logic
select(.x or .y)             # Or logic
select(not .deleted)         # Negation
```

### Object Construction
```
{name: .user, id: .uuid}     # New object from fields
{(.key): .value}             # Dynamic key
{name, age}                  # Shorthand (same as {name: .name, age: .age})
```

### Type Operations
```
.count | tonumber    # String → number
.id | tostring       # Number → string
type                 # Returns "object", "array", "string", "number", "boolean", "null"
```

### Defaults
```
.nickname // .name           # First non-null
.timeout // 30               # Default value
```

### Array Operations
```
length               # Array/string length
first                # First element
last                 # Last element
reverse              # Reverse array
sort                 # Sort array
unique               # Remove duplicates
contains("x")        # Check membership
```

### Aggregation (requires slurp)
```
add                  # Sum numbers or concat arrays
min                  # Minimum value
max                  # Maximum value
group_by(.type)      # Group by field
sort_by(.name)       # Sort by field
unique_by(.id)       # Unique by field
```

### String Operations
```
split(",")           # String → array
join(", ")           # Array → string
startswith("http")   # Prefix check
endswith(".json")    # Suffix check
ascii_downcase       # Lowercase
ascii_upcase         # Uppercase
```

### Object Operations
```
keys                 # Get object keys as array
values               # Get object values as array
has("field")         # Check key exists
del(.temp)           # Remove field
```

### Control Flow
```
if .x then .a else .b end    # Conditional
.items[]                      # Iterate and flatten
```

## Not Supported

Intentionally excluded (use full jq if needed):

- Regex (`test`, `match`, `sub`, `gsub`)
- Recursion (`recurse`, `walk`, `..`)
- Variables (`as $x`)
- Reduce (`reduce`)
- Modules (`import`, `include`)
- Math functions (trig, log, etc.)
- Date/time functions
- Format strings (`@base64`, `@uri`, `@csv`)
- SQL-style operators (`INDEX`, `IN`, `JOIN`)
- Error handling (`try`, `catch`, `error`)

## Architecture

```
stdin (NDJSON) → [Parse] → [Evaluate] → [Serialize] → stdout (NDJSON)
                    ↓           ↓            ↓
              Arena Alloc   Direct Eval   Buffered I/O
                    ↓
              Reset per line (O(1) memory reclaim)
```

### Key Optimizations

1. **Arena allocator** - Reset per line, no per-object allocations
2. **Direct evaluation** - No AST interpretation overhead
3. **Buffered I/O** - 64KB read/write buffers
4. **Single parse** - JSON parsed once, evaluated directly
5. **Static dispatch** - Expression type known at parse time

## CLI

```bash
# Basic usage
echo '{"x":1}' | zq '.x'
cat data.ndjson | zq 'select(.value > 100)'
cat data.ndjson | zq '{id: .uuid, name: .user.name}'

# Slurp mode (aggregate)
cat data.ndjson | zq -s 'group_by(.type) | map({type: .[0].type, count: length})'

# Compact output (default for NDJSON compatibility)
zq -c '.name' < data.json

# Raw string output
zq -r '.message' < data.ndjson
```

### Flags

| Flag | Description |
|------|-------------|
| `-c` | Compact output (default) |
| `-r` | Raw string output (no quotes) |
| `-s` | Slurp: read all input into array |
| `-e` | Exit with error on empty output |

## Implementation Phases

### Phase 1: Core (Current)
- [x] Identity (`.`)
- [x] Field access (`.field`, `.a.b.c`)
- [x] Select with comparisons
- [ ] Boolean logic (`and`, `or`, `not`)
- [ ] Array index (`.[0]`, `.[-1]`)

### Phase 2: Construction
- [ ] Object literals (`{a: .x, b: .y}`)
- [ ] Dynamic keys (`{(.k): .v}`)
- [ ] Shorthand (`{name, age}`)
- [ ] Alternative (`//`)

### Phase 3: Operations
- [ ] Type functions (`tonumber`, `tostring`, `type`)
- [ ] Array iteration (`.[]`)
- [ ] `length`, `first`, `last`
- [ ] `keys`, `values`, `has`, `del`

### Phase 4: Strings & Arrays
- [ ] `split`, `join`
- [ ] `startswith`, `endswith`
- [ ] `sort`, `reverse`, `unique`
- [ ] `contains`

### Phase 5: Aggregation
- [ ] Slurp mode (`-s`)
- [ ] `add`, `min`, `max`
- [ ] `group_by`, `sort_by`, `unique_by`
- [ ] `map` (with slurp)

### Phase 6: Control Flow
- [ ] `if-then-else`
- [ ] Pipes (`|`)

## Performance Targets

| Expression | Target | vs jq |
|------------|--------|-------|
| `.field` | <60ms/100K | 2x faster |
| `select(.x > N)` | <65ms/100K | 3x faster |
| `{a: .x}` | <80ms/100K | 2x faster |
| `group_by` (slurp) | <150ms/100K | 1.5x faster |

## Binary Size

| Build | Size |
|-------|------|
| Debug | ~5MB |
| ReleaseFast | ~2.5MB |
| ReleaseSmall | ~500KB |

## Integration with JN

```bash
# JN filter command uses zq
jn cat data.csv | jn filter '.revenue > 1000' | jn put output.json
                         ↓
                    Invokes zq

# Direct usage
jn cat data.csv | zq 'select(.active)' | jn put filtered.csv
```

ZQ replaces the jq dependency for JN's filter operations while maintaining jq-compatible syntax for the subset of features JN uses.
