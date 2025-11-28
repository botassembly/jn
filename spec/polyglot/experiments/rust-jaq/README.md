# Experiment: Rust jaq Implementation

**Risk:** jq replacement needs to be fast and compatible with JN's usage patterns.

**Goal:** Validate jaq library works for NDJSON filtering and compare performance to Python + jq.

## Test Case

Filter NDJSON stream using jq expressions via jaq-core library.

## Steps

```bash
cd spec/polyglot/experiments/rust-jaq

# Build release
cargo build --release

# Test basic filter
echo '{"id":1,"name":"alice"}' | ./target/release/jaq-filter '.name'
# Expected: "alice"

# Test select
echo -e '{"id":1,"active":true}\n{"id":2,"active":false}' | ./target/release/jaq-filter 'select(.active)'
# Expected: {"id":1,"active":true}

# Benchmark (generate test data first)
seq 1 100000 | while read n; do echo "{\"id\":$n,\"value\":$((n*2))}"; done > /tmp/bench.ndjson

# Compare: jaq-filter vs jq vs python+jq
time ./target/release/jaq-filter 'select(.id > 50000)' < /tmp/bench.ndjson > /dev/null
time jq -c 'select(.id > 50000)' < /tmp/bench.ndjson > /dev/null
time python filter.py 'select(.id > 50000)' < /tmp/bench.ndjson > /dev/null
```

## Success Criteria

- [ ] Basic jq expressions work (.field, select, map)
- [ ] Startup time <10ms (vs jq ~50ms)
- [ ] Throughput comparable to or better than jq
- [ ] Binary size <5MB

## Files

- `Cargo.toml` - Dependencies (jaq-core, jaq-std, jaq-parse)
- `src/main.rs` - NDJSON filter using jaq
- `filter.py` - Python subprocess wrapper for comparison
