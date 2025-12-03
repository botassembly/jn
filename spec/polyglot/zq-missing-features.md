# ZQ Missing jq Features

**Status:** Reference Document
**Date:** 2025-12-02

## Overview

ZQ is JN's pure Zig jq replacement. While it supports most common jq operations needed for ETL pipelines, some advanced jq features are not yet implemented. This document catalogs missing features for planning and workaround guidance.

## Missing Features

### 1. Variable Binding (`as $var`)

**jq Syntax:**
```jq
. as $first | [$first] + [inputs]
```

**Description:**
Variable binding allows storing intermediate values for later use in the expression.

**Impact:**
- Cannot capture values mid-pipeline
- Cannot implement stateful transformations
- Affects builtin profiles: `group_count`, `group_sum`, `stats`

**Current Workaround:**
- Use ZQ's native `group_by` with slurp mode (`-s`)
- Rewrite expressions to avoid intermediate variables

**Example ZQ Alternative:**
```bash
# Instead of jq variable binding
jn cat data.json | jn filter -s 'group_by(.status) | map({status: .[0].status, count: length}) | .[]'
```

---

### 2. `inputs` Function

**jq Syntax:**
```jq
. as $first | [$first] + [inputs]
```

**Description:**
The `inputs` function reads remaining lines from stdin after the first. Used with slurp-like patterns.

**Impact:**
- Cannot process multiple NDJSON records in complex patterns
- Affects: All aggregation profiles that need to slurp without `-s` flag

**Current Workaround:**
- Use ZQ's `-s` (slurp) flag which collects all inputs into an array
- Pipe to `jq` for complex multi-input patterns (not recommended)

**Example ZQ Alternative:**
```bash
# ZQ with slurp mode
jn cat data.json | jn filter -s 'group_by(.status) | .[]'
```

---

### 3. Recursive Descent (`..`)

**jq Syntax:**
```jq
.. | objects | select(has("id"))
```

**Description:**
Recursive descent operator (`..`) traverses all nested values recursively.

**Impact:**
- Cannot flatten deeply nested structures generically
- Cannot search for keys at arbitrary depths
- Affects builtin profiles: `flatten_nested`

**Current Workaround:**
- For known structures, use explicit field paths
- For flattening, preprocess with Python or external jq

**Example:**
```bash
# Instead of recursive descent, use explicit paths
jn cat data.json | jn filter '{name: .user.name, city: .user.address.city}'
```

---

### 4. User-Defined Functions (`def`)

**jq Syntax:**
```jq
def flatten_obj(prefix): ...;
flatten_obj("")
```

**Description:**
jq supports defining custom functions for reuse within expressions.

**Impact:**
- Cannot define reusable transformation logic
- Affects: `flatten_nested` profile which defines `flatten_obj`

**Current Workaround:**
- Use ZQ's builtin functions directly
- For complex logic, use Python plugins or multiple pipeline stages

---

### 5. `reduce` Expression

**jq Syntax:**
```jq
reduce keys[] as $key ({};  ... )
```

**Description:**
Reduce accumulates values across an iteration.

**Impact:**
- Cannot perform arbitrary accumulations
- Cannot implement complex aggregations in single expression

**Current Workaround:**
- Use ZQ's `add`, `min`, `max`, `group_by` which cover common cases
- For complex reductions, use Python

---

### 6. Dynamic Key Access with Variables (`$var` in index)

**jq Syntax:**
```jq
.[$by]      # where $by is a variable
{($key): .value}  # dynamic key in object construction
```

**Description:**
Using variables as object keys or for dynamic field access.

**Impact:**
- Cannot parameterize field names at runtime
- Affects all profiles with `$by`, `$sum`, `$field` parameters

**Current Workaround:**
- Use string substitution in JN profiles (replaces `$var` with literal value)
- Hardcode field names when possible

---

## Affected Builtin Profiles

| Profile | Missing Features | Status |
|---------|-----------------|--------|
| `@builtin/group_count` | `as $var`, `inputs`, `.$var` | Broken |
| `@builtin/group_sum` | `as $var`, `inputs`, `.$var` | Broken |
| `@builtin/stats` | `as $var`, `inputs`, `.$var` | Broken |
| `@builtin/flatten_nested` | `def`, `reduce`, `..` | Broken |
| `@builtin/pivot` | Likely affected | Untested |

## Implementation Priority

### High Priority (Common Use Cases)
1. **`inputs`** - Enable multi-record aggregations
2. **Dynamic key access** - Enable parameterized queries

### Medium Priority (Power Users)
3. **`as $var`** - Variable binding for complex transforms
4. **`reduce`** - Custom aggregations

### Low Priority (Rare Use Cases)
5. **`..`** (recursive descent) - Deep structure traversal
6. **`def`** (user functions) - Custom function definitions

## Recommendations

### Short Term
1. Document limitations clearly
2. Provide ZQ-native alternatives where possible
3. Use `-s` (slurp) mode for aggregations

### Medium Term
1. Implement `inputs` for better NDJSON handling
2. Add dynamic key access support
3. Rewrite builtin profiles to use ZQ-compatible syntax

### Long Term
1. Consider variable binding support
2. Evaluate if `reduce` is needed or if `map`/`add` suffices
3. Assess demand for recursive descent

## References

- `zq/src/main.zig` - ZQ implementation (4077 lines)
- `jn_home/profiles/jq/builtin/` - Affected builtin profiles
- `tests/cli/test_jq_profiles.py` - Tests documenting limitations
- [jq Manual](https://jqlang.github.io/jq/manual/) - Full jq feature reference
