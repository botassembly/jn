# Sprint 04: ZQ High-Impact jq Features

**Status:** 🔲 NEXT

**Goal:** Implement high/medium impact jq features missing from ZQ to reach ~99% compatibility for JN use cases

**Prerequisite:** Sprint 03 complete (ZQ v0.3.0)

---

## Feature Priority

| Priority | Feature | Impact | Complexity |
|----------|---------|--------|------------|
| P0 | `.[n:m]` slicing | High | Low |
| P0 | `.foo?` optional | High | Low |
| P1 | `has(key)` | Medium | Low |
| P1 | `in(obj)` | Medium | Low |
| P1 | `del(.key)` | Medium | Medium |
| P1 | `to_entries` | Medium | Medium |
| P1 | `from_entries` | Medium | Medium |
| P2 | `test(regex)` | High | High |
| P2 | `match(regex)` | Medium | High |
| P2 | Variables `as $x` | High | High |

**Sprint scope:** P0 + P1 features (slicing, optional, object operations)
**Deferred:** P2 features (regex, variables) - evaluate after Sprint 05

---

## Phase 1: Array Slicing `.[n:m]`

**What:** Extract sub-arrays using slice notation

**Syntax:**
- `.[2:5]` - elements 2,3,4 (start inclusive, end exclusive)
- `.[3:]` - from index 3 to end
- `.[:5]` - from start to index 5
- `.[-3:]` - last 3 elements
- `.[:-2]` - all except last 2

**Implementation pointers:**
- Parser: Extend index expression to handle `:` separator
- `parseIndex()` currently handles `.[n]` - add slice variant
- Store as new `Expr` variant: `slice: SliceExpr`
- SliceExpr: `{ start: ?i64, end: ?i64 }` (null = unbounded)

**Eval logic:**
- Get array, compute effective start/end with negative index handling
- Create new array with slice of elements
- Edge cases: empty result, out of bounds (clamp, don't error)

**Test cases:**
```
.[2:5]     on [0,1,2,3,4,5,6] → [2,3,4]
.[3:]      on [0,1,2,3,4]     → [3,4]
.[:2]      on [0,1,2,3]       → [0,1]
.[-2:]     on [0,1,2,3]       → [2,3]
.[:-1]     on [0,1,2,3]       → [0,1,2]
.[10:20]   on [0,1,2]         → []
.[:0]      on [0,1,2]         → []
```

---

## Phase 2: Optional Access `.foo?`

**What:** Access field without error if missing, return empty

**Syntax:**
- `.foo?` - field access, empty if missing
- `.foo.bar?` - last segment optional
- `.foo?.bar` - intermediate optional
- `.[0]?` - index with optional

**Implementation pointers:**
- Parser: Detect `?` suffix on field/index expressions
- Add `optional: bool` flag to `FieldExpr` and `IndexExpr`
- Eval: If optional and field missing, return empty result instead of propagating null

**Key difference from non-optional:**
- `.missing` on `{"x":1}` → outputs nothing (null propagates)
- `.missing?` on `{"x":1}` → outputs nothing (explicit empty)
- `.x?` on `null` → outputs nothing (doesn't error)

**Test cases:**
```
.missing?     on {"x":1}     → (empty)
.x?           on {"x":1}     → 1
.x?           on null        → (empty)
.[5]?         on [1,2,3]     → (empty)
.a?.b         on {"a":null}  → (empty)
.a.b?         on {"a":{}}    → (empty)
```

---

## Phase 3: Key Existence `has(key)` and `in(obj)`

**What:** Check if key exists in object

**Syntax:**
- `has("key")` - true if object has key
- `"key" | in(obj)` - true if key in object (alternate form)

**Implementation pointers:**
- `has(key)` is simpler - add as builtin taking string arg
- Parse: `has("...")` similar to `startswith("...")`
- Eval: Check if object contains key, return bool

**Note:** `in` is more complex (takes object arg), defer if time-constrained

**Test cases:**
```
has("x")     on {"x":1}     → true
has("y")     on {"x":1}     → false
has("x")     on {"x":null}  → true  # key exists even if null
has("x")     on []          → false # not an object
has("0")     on [1,2,3]     → true  # arrays have numeric string keys in jq
```

---

## Phase 4: Delete Key `del(.key)`

**What:** Remove key from object, return modified object

**Syntax:**
- `del(.key)` - delete single key
- `del(.a, .b)` - delete multiple keys
- `del(.a.b)` - delete nested key

**Implementation pointers:**
- Parse: `del(path_expr)` - new expression type
- Eval: Clone object without specified key(s)
- For nested: navigate to parent, delete from parent

**Edge cases:**
- Delete missing key → no-op, return unchanged
- Delete from non-object → error or pass-through?
- Multiple deletes → apply in sequence

**Test cases:**
```
del(.x)      on {"x":1,"y":2}     → {"y":2}
del(.z)      on {"x":1}           → {"x":1}
del(.a.b)    on {"a":{"b":1,"c":2}} → {"a":{"c":2}}
del(.x,.y)   on {"x":1,"y":2,"z":3} → {"z":3}
```

---

## Phase 5: Entry Conversion `to_entries` / `from_entries`

**What:** Convert between objects and key-value arrays

**Syntax:**
- `to_entries` - `{"a":1,"b":2}` → `[{"key":"a","value":1},{"key":"b","value":2}]`
- `from_entries` - inverse operation
- `with_entries(f)` - shorthand for `to_entries | map(f) | from_entries`

**Implementation pointers:**
- `to_entries`: Iterate object keys, build array of `{key, value}` objects
- `from_entries`: Iterate array, extract key/value, build object
- Handle variations: `{key,value}`, `{k,v}`, `{name,value}`

**Test cases:**
```
to_entries   on {"a":1,"b":2}  → [{"key":"a","value":1},{"key":"b","value":2}]
from_entries on [{"key":"x","value":1}] → {"x":1}
from_entries on [{"k":"x","v":1}]       → {"x":1}  # alternate form
from_entries on [{"name":"x","value":1}] → {"x":1} # alternate form
```

**Note:** `with_entries` can be deferred - users can compose manually

---

## Phase 6: Testing & Validation

**Unit tests:** Add to `main.zig` test blocks
- Each feature needs positive and negative cases
- Edge cases for empty, null, wrong types

**Integration tests:** Add to `tests/integration.zig`
- End-to-end tests for each new feature
- Combination tests (slice + optional, etc.)

**jq compatibility tests:**
- For each feature, verify output matches jq
- Document any intentional differences

---

## Success Criteria

| Feature | Implemented | Tests | jq-compatible |
|---------|-------------|-------|---------------|
| `.[n:m]` slicing | ☐ | ☐ | ☐ |
| `.foo?` optional | ☐ | ☐ | ☐ |
| `has(key)` | ☐ | ☐ | ☐ |
| `del(.key)` | ☐ | ☐ | ☐ |
| `to_entries` | ☐ | ☐ | ☐ |
| `from_entries` | ☐ | ☐ | ☐ |

**Version:** Bump to v0.4.0 on completion

---

## Deferred to Future Sprint

**P2 Features (high complexity):**

| Feature | Why Deferred |
|---------|--------------|
| `test(regex)` | Requires regex library (@cImport PCRE2 or Zig regex) |
| `match(regex)` | Same as above |
| `sub`/`gsub` | Regex replacement, same dependency |
| Variables `as $x` | Requires scope/environment changes |
| `reduce` | Complex iteration model |
| `recurse`/`..` | Recursive descent, stack management |

**Evaluate after Sprint 05:** If jq removal surfaces user needs for regex, prioritize in Sprint 06.

---

## Implementation Order

1. **Slicing** - Foundation, low risk
2. **Optional** - High value, moderate parser change
3. **has()** - Simple builtin
4. **del()** - Object manipulation
5. **to_entries/from_entries** - Object/array conversion

Each phase: implement → test → commit → next
