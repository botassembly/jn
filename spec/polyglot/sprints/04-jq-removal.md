# Sprint 04: jq Removal

**Status:** 🔲 NEXT

**Goal:** Replace jq with ZQ in `jn filter` - rip and replace, no deprecation

**Prerequisite:** Sprint 03 complete (ZQ v0.3.0 with aggregation/string functions)

---

## Deliverables

1. `jn filter` uses ZQ binary by default
2. Delete `jq_.py` plugin
3. Remove jq from dependencies
4. Update all tests to use ZQ

---

## Phase 1: Update `jn filter` Command

### Tasks
- [ ] Modify `src/jn/cli/commands/filter.py`
- [ ] Remove jq fallback logic
- [ ] Always invoke ZQ binary
- [ ] Remove `JN_USE_JQ` environment variable
- [ ] Update error messages for ZQ-specific errors

### Code Changes
```python
# Before (filter.py)
def get_filter_command():
    if os.environ.get("JN_USE_JQ"):
        return find_jq()
    zq = find_zq_binary()
    if zq and is_zq_compatible(expr):
        return zq
    return find_jq()  # fallback

# After (filter.py)
def get_filter_command():
    return find_zq_binary()  # ZQ only, no fallback
```

### Quality Gate
- [ ] `jn filter '.x'` uses ZQ
- [ ] `JN_USE_JQ=1 jn filter '.x'` is ignored (still uses ZQ)

---

## Phase 2: Delete jq Plugin

### Tasks
- [ ] Delete `jn_home/plugins/filters/jq_.py`
- [ ] Remove jq from plugin registry
- [ ] Remove jq pattern matching in filter.py

### Files to Delete
```
jn_home/plugins/filters/jq_.py
```

### Quality Gate
- [ ] `jn plugin list` does not show jq
- [ ] No references to jq_.py in codebase

---

## Phase 3: Remove jq Dependency

### Tasks
- [ ] Remove jq from `pyproject.toml` dependencies (if present)
- [ ] Update CLAUDE.md to remove jq references
- [ ] Update README if it mentions jq requirement
- [ ] Remove any jq installation checks

### Files to Update
- [ ] `pyproject.toml`
- [ ] `CLAUDE.md`
- [ ] `README.md` (if exists)

### Quality Gate
- [ ] Fresh install works without jq installed
- [ ] `which jq` not required

---

## Phase 4: Update Tests

### Tasks
- [ ] Find all tests that use jq directly
- [ ] Update to use ZQ instead
- [ ] Remove jq compatibility tests
- [ ] Add ZQ-specific tests for unsupported expressions

### Test Updates
```python
# Before
def test_filter_basic():
    # This might call jq under the hood
    result = run_filter('.x', '{"x":1}')

# After
def test_filter_basic():
    # Explicitly uses ZQ
    result = run_filter('.x', '{"x":1}')
    # Same test, but now ZQ-only
```

### Quality Gate
- [ ] `make test` passes
- [ ] No tests require jq installed
- [ ] Coverage stable or improved

---

## Phase 5: Update filtering.py

### Tasks
- [ ] Simplify `find_filter_plugin()` - ZQ only
- [ ] Remove jq compatibility patterns
- [ ] Remove `is_zq_compatible()` function (everything goes to ZQ)
- [ ] Simplify error handling

### Code Cleanup
```python
# Remove these functions/patterns:
# - is_zq_compatible()
# - find_jq()
# - JQ_PATTERNS
# - jq fallback logic
```

### Quality Gate
- [ ] filtering.py is simpler
- [ ] No dead code

---

## Phase 6: Documentation Updates

### Tasks
- [ ] Update CLAUDE.md filter examples
- [ ] Update spec docs that mention jq
- [ ] Add ZQ limitations to docs (no regex, no variables, no modules)

### Key Messages
- `jn filter` now uses ZQ (Zig-based, 2x faster than jq)
- ZQ supports ~95% of jq expressions used by JN
- Unsupported: regex (test/match), variables ($x), modules

### Quality Gate
- [ ] No stale jq references in docs

---

## Success Criteria

| Metric | Target |
|--------|--------|
| jq references in code | 0 |
| jq_.py exists | No |
| `make test` passes | Yes |
| Fresh install without jq | Works |
| `jn filter` performance | 2x faster than before |

---

## Rollback Plan

If critical issues found:
1. Revert filter.py changes
2. Restore jq_.py from git
3. Re-add jq fallback

**Note:** No deprecation period. If users need jq features not in ZQ, they can pipe to jq directly: `jn cat data.csv | jq 'complex_expr'`

---

## Post-Sprint

After jq removal:
- Monitor for user issues with unsupported expressions
- Add ZQ features as needed based on feedback
- Continue to Sprint 05 (Zig Plugin Library)
