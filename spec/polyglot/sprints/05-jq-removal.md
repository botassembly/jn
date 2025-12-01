# Sprint 05: Error Handling & jq Removal

**Status:** 🔲 PLANNED

**Goal:** Improve ZQ error handling for production use, then remove jq dependency

**Prerequisite:** Sprint 04 complete (ZQ v0.4.0 with slicing, optional, object ops)

---

## Why Error Handling First?

Before removing jq, ZQ must provide:
1. **Clear error messages** - Users need to understand what went wrong
2. **Helpful suggestions** - Point to workarounds for unsupported features
3. **Graceful degradation** - Don't crash on edge cases

This sprint hardens ZQ for production, then removes jq.

---

## Phase 1: ZQ Error Message Improvements

### Current State
- Parse errors show position but not context
- Eval errors may be cryptic
- Unsupported features silently fail or give generic errors

### Target State
- Parse errors show the problematic expression
- Eval errors explain what type was expected vs received
- Unsupported features give specific "not supported" message with workaround

### Implementation Pointers

**Parser errors:**
- Capture expression context when error occurs
- Include character position AND surrounding text
- Example: `Error at position 15: unexpected ')' in ".foo | bar)"`

**Eval errors:**
- Type mismatch: `"Expected array for 'first', got string"`
- Missing field: `"Field 'name' not found in object"`
- Index out of bounds: `"Index 5 out of bounds for array of length 3"`

**Unsupported feature detection:**
- Parser should recognize common jq patterns ZQ doesn't support
- Return helpful error: `"Regex 'test()' not supported. Workaround: pipe to jq"`

### Test Cases
- Malformed expression → clear parse error
- Wrong type → clear type error
- Unsupported feature → clear "not supported" with suggestion

---

## Phase 2: Unsupported Feature Detection

### Features to Detect and Report

| Pattern | Detection | Error Message |
|---------|-----------|---------------|
| `test(...)` | Parser | "Regex not supported. Use: `\| jq 'test(...)'`" |
| `match(...)` | Parser | "Regex not supported. Use: `\| jq 'match(...)'`" |
| `sub(...)` | Parser | "Regex not supported. Use: `\| jq 'sub(...)'`" |
| `gsub(...)` | Parser | "Regex not supported. Use: `\| jq 'gsub(...)'`" |
| `$variable` | Parser | "Variables not supported. Use: `\| jq '...'`" |
| `. as $x` | Parser | "Variables not supported. Use: `\| jq '...'`" |
| `reduce` | Parser | "Reduce not supported. Use: `\| jq 'reduce ...'`" |
| `@base64` | Parser | "Format strings not supported. Use: `\| jq '@base64'`" |

### Implementation Pointers
- In parser, before returning "unknown function", check against known unsupported list
- Return specific error with workaround
- Log to stderr, exit non-zero

---

## Phase 3: Error Output Format

### Standard Error Format
```
zq: error: <category>: <message>
  expression: <the expression>
  position: <offset or range>
  suggestion: <workaround if available>
```

### Examples
```
zq: error: parse: unexpected token ')'
  expression: .foo | bar)
  position: 11
  suggestion: check for unmatched parentheses

zq: error: type: expected array, got string
  expression: first
  input: "hello"
  suggestion: 'first' operates on arrays

zq: error: unsupported: regex functions not available
  expression: test("pattern")
  suggestion: pipe to jq: | jq 'test("pattern")'
```

### Implementation Pointers
- Create error formatting function
- Include `--verbose` flag for full stack traces (dev use)
- Exit code 1 for user errors, 2 for internal errors

---

## Phase 4: jq Removal

After error handling is solid, remove jq:

### Tasks
- [ ] Remove jq fallback from `filter.py`
- [ ] Delete `jn_home/plugins/filters/jq_.py`
- [ ] Remove `JN_USE_JQ` environment variable
- [ ] Update `is_zq_compatible()` → delete entirely
- [ ] Remove jq from any dependency lists

### Files to Modify
- `src/jn/cli/commands/filter.py` - ZQ only
- `src/jn/filtering.py` - Remove jq patterns

### Files to Delete
- `jn_home/plugins/filters/jq_.py`

### Quality Gate
- `jn filter '.x'` works without jq installed
- Unsupported expressions give clear error
- `make test` passes

---

## Phase 5: Documentation Updates

### CLAUDE.md Updates
- Remove jq references
- Document ZQ limitations
- Add "pipe to jq" workaround for advanced features

### ZQ Help Text
```
zq - JSON query tool (jq-compatible subset)

Supported:
  .field, .[n], .[], select(), pipes, arithmetic,
  object construction, if-then-else, slicing,
  group_by, sort_by, map, string functions, etc.

Not supported (pipe to jq for these):
  - Regex: test(), match(), sub(), gsub()
  - Variables: . as $x
  - Reduce: reduce .[] as $x (...)
  - Modules: import, include
```

---

## Phase 6: Testing

### Error Handling Tests
- Each error type has test
- Error messages are verified
- Exit codes are correct

### Integration Tests
- `jn filter` with valid expressions
- `jn filter` with unsupported expressions (clear error)
- Fresh install without jq

### Regression Tests
- All existing filter tests still pass
- Performance benchmarks stable

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Clear error messages | All error paths tested |
| Unsupported feature detection | 8+ patterns detected |
| jq references in code | 0 |
| jq_.py exists | No |
| `make test` passes | Yes |
| `make check` passes | Yes |
| Fresh install without jq | Works |

**Version:** ZQ v0.4.1 (error handling), then v0.5.0 (jq removed)

---

## Risk Mitigation

**Risk:** Users depend on unsupported jq features
**Mitigation:** Clear error messages with workarounds, monitor feedback

**Risk:** Error handling adds overhead
**Mitigation:** Only check for unsupported patterns during parse, not eval

**Rollback:** If critical issues, restore jq fallback from git history

---

## Post-Sprint

- Monitor for user issues
- Collect feedback on missing features
- Prioritize regex support if high demand
- Continue to Sprint 06 (Zig Plugin Library)
