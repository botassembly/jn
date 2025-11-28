# Sprint 01: ZQ Foundation

**Goal:** Complete ZQ core features to production-ready quality

**Starting Point:** Prototype in `experiments/zig-jq-subset/` (2-3x faster than jq)

---

## Deliverables

1. Production ZQ binary with core expressions
2. Comprehensive test suite
3. Benchmark suite vs jq
4. Integration with `jn filter` command

---

## Phase 1: Project Setup

### Tasks
- [ ] Create `zq/` directory at repo root
- [ ] Move prototype code from `experiments/zig-jq-subset/`
- [ ] Set up proper build.zig with test targets
- [ ] Add CI for Zig builds (linux, macos, windows)

### Quality Gate
- [ ] `zig build` succeeds
- [ ] `zig build test` passes
- [ ] CI runs on all platforms

---

## Phase 2: Core Expressions

Complete and harden existing features:

### Identity & Field Access
- [ ] `.` - pass through unchanged
- [ ] `.field` - single field access
- [ ] `.a.b.c` - nested field path
- [ ] `.[0]` - array index (positive)
- [ ] `.[-1]` - array index (negative)
- [ ] `.[]` - iterate array elements

### Filtering
- [ ] `select(.field)` - truthy check
- [ ] `select(.x > N)` - greater than
- [ ] `select(.x < N)` - less than
- [ ] `select(.x >= N)` - greater or equal
- [ ] `select(.x <= N)` - less or equal
- [ ] `select(.x == val)` - equality (string, number, bool)
- [ ] `select(.x != val)` - inequality

### Boolean Logic
- [ ] `select(.a and .b)` - logical and
- [ ] `select(.a or .b)` - logical or
- [ ] `select(not .deleted)` - negation

### Quality Gate
- [ ] All tests pass
- [ ] Benchmark: each expression within 50% of prototype speed

---

## Phase 3: Error Handling

### Tasks
- [ ] Graceful handling of malformed JSON
- [ ] Clear error messages to stderr
- [ ] Exit code 0 on success, non-zero on error
- [ ] Option to skip invalid lines vs fail

### Edge Cases
- [ ] Empty input → empty output
- [ ] Missing fields → skip line (select) or null (.field)
- [ ] Invalid expression → error message and exit 1
- [ ] Very long lines (>1MB)
- [ ] Unicode content

### Quality Gate
- [ ] No crashes on fuzz input
- [ ] Error messages are actionable

---

## Phase 4: CLI Interface

### Flags
- [ ] `-c` - compact output (default, for NDJSON)
- [ ] `-r` - raw string output (no quotes)
- [ ] `-e` - exit with error if no output
- [ ] `--version` - print version
- [ ] `--help` - print usage

### Quality Gate
- [ ] `zq --help` shows all options
- [ ] Flags work correctly

---

## Phase 5: Integration

### JN Integration
- [ ] Build ZQ as part of JN
- [ ] `jn filter` detects and uses ZQ binary
- [ ] Fallback to jq if ZQ not available
- [ ] Environment variable to force jq: `JN_USE_JQ=1`

### Installation
- [ ] Binary copied to `jn_home/bin/zq`
- [ ] Or bundled in jn distribution

### Quality Gate
- [ ] `jn filter '.x'` uses ZQ
- [ ] `JN_USE_JQ=1 jn filter '.x'` uses jq
- [ ] All existing filter tests pass

---

## Phase 6: Testing & Benchmarks

### Test Suite
- [ ] Unit tests for parser
- [ ] Unit tests for evaluator
- [ ] Integration tests (stdin → stdout)
- [ ] Compatibility tests vs jq output

### Benchmark Suite
```bash
./benchmark.sh "." 100000
./benchmark.sh ".field" 100000
./benchmark.sh "select(.x > 50000)" 100000
./benchmark.sh ".a.b.c" 100000
```

### Quality Gate
- [ ] All expressions 2x+ faster than jq
- [ ] Test coverage >80%

---

## Success Criteria

| Metric | Target |
|--------|--------|
| `.field` speed | <60ms / 100K records |
| `select(.x > N)` speed | <70ms / 100K records |
| Binary size (ReleaseFast) | <3MB |
| Binary size (ReleaseSmall) | <600KB |
| Test pass rate | 100% |
| jq compatibility | 100% for supported expressions |

---

## Notes

**Deferred to Sprint 02:**
- Object construction `{a: .x}`
- Type functions (tonumber, tostring)
- Alternative operator (//)
- Aggregation (group_by, map)
