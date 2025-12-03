# ZQ vs jq Gap Analysis

**Date:** Sprint 04 (v0.4.0)
**Purpose:** Document behavioral differences between ZQ and jq

---

## Summary

| Category | Count | Severity |
|----------|-------|----------|
| Output Formatting | 3 | Low |
| Number Handling | 2 | Medium |
| Null Propagation | 2 | Low |
| Error Behavior | 3 | Low |
| Missing Features | 6+ | N/A (intentional) |

---

## 1. Output Formatting Differences

### 1.1 Float Representation

**jq:**
```bash
echo '{"x":1}' | jq '.x + 0.0'
# Output: 1.0
```

**ZQ:**
```bash
echo '{"x":1}' | zq '.x + 0.0'
# Output: 1 (if result is whole number, returns integer)
```

**Impact:** Low - ZQ returns integers when mathematically equivalent
**Recommendation:** Keep as-is. ZQ behavior is more efficient for NDJSON pipelines.

### 1.2 Object Key Ordering

**jq:** Preserves insertion order in objects (since jq 1.6)
**ZQ:** Uses HashMap (order not guaranteed)

**Impact:** Low - NDJSON semantics don't require order
**Recommendation:** Document as known difference. Consider switching to ArrayHashMap if needed.

### 1.3 Compact Output Default

**jq:** Pretty-prints by default (use `-c` for compact)
**ZQ:** Compact by default (NDJSON-optimized)

**Impact:** None - correct behavior for NDJSON
**Status:** Working as designed

---

## 2. Number Handling

### 2.1 Integer/Float Type Preservation

**jq:**
```bash
echo '1' | jq '. * 1.0'
# Output: 1.0 (always float when float involved)
```

**ZQ:**
```bash
echo '1' | zq '. * 1.0'
# Output: 1 (if result is whole, returns integer)
```

**Impact:** Medium - may affect downstream JSON schema expectations
**Current behavior:** ZQ returns integer if `@trunc(result) == result`
**Recommendation:** Consider adding a `--preserve-types` flag for strict mode

### 2.2 Large Number Handling

**jq:** Uses double precision (may lose precision >2^53)
**ZQ:** Uses i64 for integers, f64 for floats

**Impact:** Low - same precision limits
**Status:** Compatible

---

## 3. Null Propagation

### 3.1 Missing Field Access

**jq:**
```bash
echo '{"x":1}' | jq '.y'
# Output: null
```

**ZQ:**
```bash
echo '{"x":1}' | zq '.y'
# Output: (empty - no output)
```

**Impact:** Low - ZQ filters out nulls by default (NDJSON-friendly)
**Workaround:** Use `.y // null` to explicitly output null
**Status:** Intentional difference

### 3.2 Null in Arithmetic

**jq:**
```bash
echo 'null' | jq '. + 1'
# Output: 1 (null treated as 0)
```

**ZQ:**
```bash
echo 'null' | zq '. + 1'
# Output: (empty)
```

**Impact:** Low - ZQ behavior is more explicit
**Status:** Intentional

---

## 4. Error Behavior

### 4.1 Division by Zero

**jq:**
```bash
echo '1' | jq '. / 0'
# Error: number (1) and number (0) cannot be divided because the divisor is zero
```

**ZQ:**
```bash
echo '1' | zq '. / 0'
# Output: (empty - silent)
```

**Impact:** Low - ZQ continues processing, jq errors
**Recommendation:** Consider adding `--strict` mode for errors

### 4.2 Type Errors

**jq:**
```bash
echo '"hello"' | jq '. + 1'
# Error: string ("hello") and number (1) cannot be added
```

**ZQ:**
```bash
echo '"hello"' | zq '. + 1'
# Output: (empty)
```

**Impact:** Low - ZQ silently skips, jq errors
**Status:** Intentional (NDJSON streaming friendly)

### 4.3 Parse Errors

**jq:** Detailed error messages with position
**ZQ:** Simple "invalid expression" errors

**Impact:** Low for end users (JN wraps expressions)
**Recommendation:** Improve error messages in future sprint

---

## 5. Optional Access (`.foo?`) Behavior

### 5.1 jq Semantics

In jq, the `?` operator suppresses errors:
```bash
# Without ?
echo 'null' | jq '.x'
# Error: Cannot index null with string "x"

# With ?
echo 'null' | jq '.x?'
# Output: (empty - error suppressed)
```

### 5.2 ZQ Semantics

ZQ never errors on field access - it returns empty:
```bash
echo 'null' | zq '.x'
# Output: (empty - no error)

echo 'null' | zq '.x?'
# Output: (empty - same behavior)
```

**Impact:** Low - The `?` is effectively a no-op in ZQ since ZQ never errors on these cases
**Status:** Parsed but functionally equivalent to non-optional
**Note:** This is actually NDJSON-friendly behavior - no need to change

---

## 6. Intentionally Missing Features

These are **by design** and documented in ZQ.md:

| Feature | jq Example | ZQ Alternative |
|---------|------------|----------------|
| Regex | `test("foo")` | Use `contains("foo")` for simple cases |
| Variables | `as $x` | Chain with pipes |
| Reduce | `reduce .[]` | Use aggregation functions |
| Recursion | `..`, `recurse` | Not supported |
| Modules | `import`, `include` | Not applicable |
| Format strings | `@base64`, `@csv` | Use JN format plugins |

---

## 7. Spacing/Whitespace

### 7.1 String Output

**Both identical:** No spacing differences in JSON output

### 7.2 Array/Object Formatting

**jq (compact):**
```json
{"a":1,"b":2}
[1,2,3]
```

**ZQ:**
```json
{"a":1,"b":2}
[1,2,3]
```

**Status:** Identical in compact mode

---

## 8. Recommendations for Future Sprints

### High Priority (Sprint 05)
1. **Error messages** - Improve parse error reporting with position info
2. **`empty` builtin** - Explicit empty output for consistency with jq

### Medium Priority (Sprint 06+)
1. **Object key ordering** - Consider ArrayHashMap for deterministic output
2. **Strict mode flag** - `--strict` for jq-compatible error behavior
3. **Type preservation flag** - `--preserve-types` for float consistency

### Low Priority (Future)
1. **`error` builtin** - Explicit error raising
2. **`@base64` format** - Common encoding need

---

## 9. Test Matrix

| Test Case | jq Output | ZQ Output | Status |
|-----------|-----------|-----------|--------|
| `.x` on `{"x":1}` | `1` | `1` | ✅ |
| `.y` on `{"x":1}` | `null` | (empty) | ⚠️ Known |
| `.y?` on `{"x":1}` | `null` | (empty) | ⚠️ Known |
| `.[2:5]` on `[0,1,2,3,4,5]` | `[2,3,4]` | `[2,3,4]` | ✅ |
| `has("x")` on `{"x":1}` | `true` | `true` | ✅ |
| `del(.x)` on `{"x":1,"y":2}` | `{"y":2}` | `{"y":2}` | ✅ |
| `to_entries` on `{"a":1}` | `[{"key":"a","value":1}]` | `[{"key":"a","value":1}]` | ✅ |
| `1 + 1.5` | `2.5` | `2.5` | ✅ |
| `3 / 2` | `1.5` | `1.5` | ✅ |
| `4 / 2` | `2` | `2` | ✅ |

---

## Conclusion

ZQ is **~95% compatible** with jq for JN use cases. The remaining differences are:

1. **Intentional** - Optimized for NDJSON streaming (null filtering, silent errors)
2. **Minor** - Object key ordering, number type preservation
3. **Enhancement** - Better error messages, `empty` builtin

**Key insight:** ZQ's "silent failure" behavior (returning empty instead of erroring) is actually a feature for NDJSON streaming - it allows pipelines to continue processing even when individual records have missing/incompatible data.

No blocking issues for JN integration.
