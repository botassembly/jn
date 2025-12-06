# JN Codebase Review Report

**Date:** 2024-12-06
**Reviewer:** Claude Code Assessment

---

## Executive Summary

The JN codebase is well-organized and largely matches the architecture documents in `spec/`. The migration from Python to Zig is substantially complete with 11 Zig CLI tools and 7 Zig plugins operational. There are some documentation inconsistencies and 3 demos that need additional work.

---

## 1. Architecture Alignment

### What Matches

| Component | Spec | Actual | Status |
|-----------|------|--------|--------|
| Zig Libraries | 6 in `libs/zig/` | 6 present | ✅ |
| Zig Tools | 12 in `tools/zig/` | 11 present | ⚠️ |
| Zig Plugins | 5 in `plugins/zig/` | 7 present | ✅ |
| ZQ Engine | `zq/` | Present | ✅ |
| Python Plugins | `jn_home/plugins/` | Present | ✅ |
| Legacy Python CLI | `src/jn/` | Removed | ✅ |

### Discrepancies

1. **Missing `jn-table` tool**: Listed in `spec/04-project-layout.md` but not implemented. Table rendering uses Python `table_.py` plugin instead.

2. **Missing `jn-profile` tool**: Listed in spec but doesn't exist.

3. **Python plugin layout differs**: Spec says `plugins/python/*.py` but actual is `jn_home/plugins/{formats,protocols,databases,shell}/*.py`. This is a better organization but spec should be updated.

4. **Spec subdirectories don't exist**: Spec mentions `spec/zig-refactor/` and `spec/done/` but specs are flat in `spec/`.

### Recommendations

- Update `spec/04-project-layout.md` to match actual structure
- Either implement missing tools or remove from spec
- Consider consolidating spec documents

---

## 2. Testing Strategy

### Current Test Infrastructure

| Test Type | Location | Runs Via |
|-----------|----------|----------|
| Zig unit tests | Embedded in `main.zig` / `root.zig` | `make test` |
| Python integration | `tests/cli/test_zig_tools.py` | `pytest` |
| Python plugin tests | `tests/plugins/test_zig_*.py` | `pytest` |

### Zig Embedded Tests

All Zig components have embedded tests **except gz plugin**:

```
libs/zig/jn-core/src/root.zig      ✓ tests
libs/zig/jn-cli/src/root.zig       ✓ tests
libs/zig/jn-plugin/src/root.zig    ✓ tests
libs/zig/jn-address/src/root.zig   ✓ tests
libs/zig/jn-profile/src/root.zig   ✓ tests
libs/zig/jn-discovery/src/root.zig ✓ tests

plugins/zig/csv/main.zig           ✓ tests
plugins/zig/json/main.zig          ✓ tests
plugins/zig/jsonl/main.zig         ✓ tests
plugins/zig/yaml/main.zig          ✓ tests
plugins/zig/toml/main.zig          ✓ tests
plugins/zig/gz/main.zig            ✗ NO TESTS
plugins/zig/opendal/               ✓ separate test files

tools/zig/*/main.zig               ✓ all have tests
```

### Recommendations

1. **Add tests to gz plugin** - only untested Zig component
2. **Keep `tests/cli/test_zig_tools.py`** - valuable for pipeline integration
3. **Consider removing `tests/plugins/`** - redundant with embedded Zig tests
4. **Convert demos to integration tests** - demos should pass in CI

---

## 3. Test Coverage

### Current State

- **Total tests:** 563 (per spec/00-plan.md)
- **Library tests:** 89
- **Integration tests:** 31

### Coverage Measurement

Zig doesn't have built-in coverage. Options:

```bash
# Option 1: Zig experimental coverage
zig test src/main.zig -fllvm -ftest-coverage

# Option 2: kcov wrapper
kcov --include-path=./src coverage/ ./test_binary
```

### Coverage Gaps

| Component | Has Tests | Notes |
|-----------|-----------|-------|
| gz plugin | ❌ | Needs compress/decompress tests |
| opendal plugin | Partial | S3 untested |
| Python plugins | Limited | Only 4 test files |
| Demos | None | Should become integration tests |

### Recommendations

1. Add `make coverage` target using kcov
2. Set coverage threshold (suggest 70%)
3. Track coverage in CI

---

## 4. Demo Status

### Current Status

| Demo | Status | Blocker |
|------|--------|---------|
| csv-filtering | ✅ Working | None |
| join | ✅ Working | None |
| shell-commands | ⚠️ Partial | Requires external `jc` tool |
| http-api | ⚠️ Limited | Works via curl for simple cases |
| glob | ⚠️ Limited | Glob patterns not implemented |
| xlsx-files | ❌ Pending | Python plugin discovery needed |
| table-rendering | ❌ Pending | Missing `jn table` command |
| code-lcov | ❌ Pending | @code profile resolution needed |
| adapter-merge | ❌ Pending | DuckDB profile resolution needed |
| genomoncology | 📋 Example | Requires credentials (expected) |

### Fix Priority

**Quick Wins (Low effort):**
- shell-commands: Document `jc` requirement, add to prerequisites

**Medium Effort:**
- table-rendering: Route `jn table` to `table_.py`
- glob: Implement native glob expansion in jn-cat
- http-api: Already works, just needs testing

**High Effort:**
- xlsx-files: Implement Python plugin invocation in jn-cat
- code-lcov: Implement protocol-based profile resolution
- adapter-merge: Implement DuckDB profile resolution

### Recommendations

1. Create `demos/run_tests.sh` that validates each demo
2. Add demo validation to CI
3. Update demos/README.md to match spec/00-plan.md

---

## 5. Action Items

### Immediate (Documentation)

- [ ] Update `spec/04-project-layout.md` to reflect actual plugin locations
- [ ] Update `demos/README.md` to match spec status
- [ ] Remove references to non-existent `jn-table` and `jn-profile` tools

### Short-term (Testing)

- [ ] Add unit tests to `plugins/zig/gz/main.zig`
- [ ] Create `make coverage` target
- [ ] Convert demos to CI-runnable tests

### Medium-term (Features)

- [ ] Implement `jn table` subcommand
- [ ] Implement glob pattern expansion in jn-cat
- [ ] Implement Python plugin invocation in jn-cat

### Long-term (Architecture)

- [ ] Complete Phase 12: DuckDB and Code profile resolution
- [ ] Consider removing `tests/plugins/` (now redundant)
- [ ] Consolidate spec documents

---

## Appendix: File Counts

```
libs/zig/           6 libraries, 6 with tests
tools/zig/         11 tools, 11 with tests
plugins/zig/        7 plugins, 6 with tests (gz missing)
jn_home/plugins/   10 Python plugins
zq/                 1 filter engine with tests
tests/              8 test files
demos/             10 demo directories
spec/              17 documentation files
```
