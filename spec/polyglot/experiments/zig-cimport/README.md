# Experiment: Zig @cImport

**Risk:** C library integration is fundamental to the architecture (simdjson, PCRE2, libcurl).

**Goal:** Validate @cImport works smoothly with a C library.

## Test Case

Use a simple C library to avoid complexity. PCRE2 is a good candidate since regex matching is needed for plugin discovery.

## Steps

```bash
# 1. Install PCRE2 dev headers
apt-get install libpcre2-dev  # or brew install pcre2

# 2. Build
cd spec/polyglot/experiments/zig-cimport
zig build

# 3. Test
echo "test.csv" | ./zig-out/bin/regex-test ".*\.csv$"
# Expected: match

echo "test.json" | ./zig-out/bin/regex-test ".*\.csv$"
# Expected: no match
```

## Success Criteria

- [ ] @cImport compiles without manual header tweaks
- [ ] Can match regex patterns against strings
- [ ] No memory leaks (use `-fsanitize=address` if needed)
- [ ] Build works on Linux and macOS

## Files

- `build.zig` - Build configuration
- `src/main.zig` - Minimal regex matcher using PCRE2
