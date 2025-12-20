# Fix: User Tool PATH Isolation

**Date:** 2025-12-20
**Status:** Implemented
**Addresses:** PATH dependency issue when calling `jn tool` subcommands from subprocesses

---

## Problem Statement

When calling `jn tool db` as a subprocess (e.g., from Python), it fails with:

```json
{"event":"error","code":"TOOLS_NOT_FOUND","message":"jn tools not found. Please install jn or run 'make build'."}
```

The root cause: user tools like `db` depend on internal tools (`jn-edit`, `zq`) but these are not in PATH when `jn` is invoked programmatically.

### Why This Happens

1. The `jn` binary is typically in `dist/bin/` which users add to PATH
2. Internal tools (`jn-edit`, `zq`, plugins) are in `dist/libexec/jn/` which is NOT on PATH
3. The `jn` orchestrator knows how to find these tools (via `findTool()`)
4. But when `jn` spawns a user tool like `db`, it doesn't pass this knowledge
5. The `db` script tries its own discovery via `$SCRIPT_DIR/../..` but this can fail depending on invocation context

---

## Solution: Automatic PATH Setup

The `jn` orchestrator now automatically prepends the libexec directory to PATH when spawning user tools.

### Implementation

**File:** `tools/zig/jn/main.zig`

1. **New function `findLibexecDir()`** (lines 364-481)
   - Discovers the libexec directory containing internal tools
   - Checks multiple layouts: JN_HOME, libexec, flat bin, development, user install
   - Returns colon-separated paths for dev mode (jn-edit and zq in different locations)
   - Verifies `jn-edit` exists before returning a path

2. **Modified `runUserTool()`** (lines 604-631)
   - Gets the current environment via `std.process.getEnvMap()`
   - Finds libexec directory via `findLibexecDir()`
   - Prepends libexec to PATH
   - Passes modified environment to child process via `child.env_map`

### Search Order for libexec

1. `$JN_HOME/bin/` (if JN_HOME set and contains jn-edit)
2. `../libexec/jn/` relative to jn binary (production layout)
3. Sibling directory of jn binary (flat layout)
4. Development layout: `tools/zig/*/bin/` + `zq/zig-out/bin/`
5. `~/.local/jn/bin/` (user installation)

---

## Testing

### Basic Test

```bash
# From minimal environment (simulating Python subprocess)
env -i PATH=/usr/bin:/bin HOME=$HOME /path/to/jn tool db list
```

### Full Test Suite

```bash
make test  # All 92 tests pass
```

### Manual Verification

```bash
# Initialize database
cd /tmp/test && jn tool db init

# Insert record (uses jn-edit)
jn tool db insert '{"name":"test","value":42}'

# Query records (uses zq)
jn tool db list
```

---

## Design Rationale

### Why PATH Modification?

**Alternative approaches considered:**

1. **Pass JN_LIBEXEC env var**: Requires each tool script to check and use it
2. **Fix db script discovery**: Only fixes one tool, pattern not enforced
3. **Set all tools on user PATH**: Pollutes user's shell, confusing

**Why PATH modification wins:**

- Zero changes to user tools - they already use `command -v`
- Works for all tools (bash, Python, any interpreter)
- Consistent with Unix convention
- Only affects child processes of `jn`
- Matches how other systems work (e.g., `git` adds libexec for hooks)

### Scope of PATH "Pollution"

The PATH modification:
- Only affects processes spawned by `jn tool`
- Does NOT affect the user's shell
- Only adds internal tools with namespaced names (`jn-*`, `zq`)
- Is invisible to users unless they inspect child process environment

---

## Files Changed

| File | Change |
|------|--------|
| `tools/zig/jn/main.zig` | Added `findLibexecDir()`, modified `runUserTool()` |

---

## Related

- Original feedback: GitHub issue about PATH dependency
- Affected tools: `db`, `todo`, and any future user tools
- Distribution layout: `spec/04-project-layout.md`
