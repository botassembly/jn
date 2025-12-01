# Sprint 10: Zig Core Binary

**Status:** 🔲 PLANNED

**Goal:** Replace Python CLI with single Zig binary for all JN operations

**Prerequisite:** Sprint 09 complete (HTTP & compression plugins)

---

## Deliverables

1. Single `jn` binary (Zig)
2. All subcommands: cat, put, filter, head, tail, run
3. Plugin discovery and execution
4. Python plugin compatibility (spawn Python for .py plugins)
5. Native Zig plugin loading

---

## Why Zig Core?

**Current State (Python CLI):**
- ~100ms startup time
- Requires Python installation
- Multiple dependencies (click, ruamel.yaml)
- Process spawn overhead for each stage

**Target State (Zig CLI):**
- <5ms startup time
- Single binary, no dependencies
- Native plugin execution (no spawn for Zig plugins)
- Smaller distribution size

---

## Phase 1: Core CLI Framework

### Argument Parsing
- [ ] Parse subcommand: `jn cat`, `jn filter`, etc.
- [ ] Parse global flags: `--help`, `--version`, `--debug`
- [ ] Parse subcommand-specific flags
- [ ] Handle positional arguments

### Subcommands
```
jn cat <address>           # Read data → NDJSON
jn put <address>           # Write NDJSON → format
jn filter <expr>           # Filter/transform NDJSON
jn head [-n N]             # First N records
jn tail [-n N]             # Last N records
jn run <input> <output>    # Two-stage pipeline
```

### Implementation
```zig
const Command = enum { cat, put, filter, head, tail, run, help, version };

pub fn main() !void {
    var args = std.process.args();
    _ = args.next(); // skip program name

    const cmd_str = args.next() orelse return printUsage();
    const cmd = std.meta.stringToEnum(Command, cmd_str) orelse {
        return error.UnknownCommand;
    };

    switch (cmd) {
        .cat => try catCommand(&args),
        .put => try putCommand(&args),
        .filter => try filterCommand(&args),
        // ...
    }
}
```

### Quality Gate
- [ ] `jn --help` shows usage
- [ ] `jn --version` shows version
- [ ] Unknown command → error message

---

## Phase 2: Plugin Discovery

### Plugin Types
1. **Native Zig plugins** - Compiled .so/.dylib, loaded directly
2. **Python plugins** - .py files, spawned via `python plugin.py`

### Discovery Algorithm
```zig
fn discoverPlugins(jn_home: []const u8) ![]Plugin {
    // 1. Scan jn_home/plugins/formats/, protocols/, etc.
    // 2. For .py files: parse PEP 723 TOML for matches
    // 3. For .so/.dylib files: call plugin_meta() symbol
    // 4. Return sorted by priority (native > python)
}
```

### Pattern Matching
- [ ] Compile regex patterns from plugin metadata
- [ ] Match source address against patterns
- [ ] Return best-matching plugin
- [ ] Cache discovery results (invalidate on file change)

### Quality Gate
- [ ] Discovers Python plugins
- [ ] Discovers Zig plugins
- [ ] Correct priority ordering
- [ ] Cache works correctly

---

## Phase 3: cat Command

### Address Parsing
```
address[~format][?params]
```

- [ ] Parse protocol: `http://`, `file://`, or bare path
- [ ] Parse format hint: `~json`, `~csv`
- [ ] Parse parameters: `?key=value&key2=value2`
- [ ] Detect compression: `.gz` extension

### Execution
```zig
fn catCommand(args: *ArgIterator) !void {
    const address = args.next() orelse return error.MissingAddress;
    const parsed = try parseAddress(address);
    const plugin = try resolvePlugin(parsed);

    // For Python plugin:
    var child = try spawnPlugin(plugin, .read, parsed.params);
    try pipeToStdout(child.stdout);

    // For native plugin:
    // Direct function call, no spawn
}
```

### Quality Gate
- [ ] `jn cat file.csv` works
- [ ] `jn cat http://api/data.json` works
- [ ] `jn cat file.csv.gz` works (decompression chain)
- [ ] Format hints work: `jn cat file~csv`

---

## Phase 4: put Command

### Execution
- [ ] Read NDJSON from stdin
- [ ] Resolve output plugin from address
- [ ] Spawn/call plugin in write mode
- [ ] Handle compression if .gz extension

### Quality Gate
- [ ] `jn cat file.csv | jn put out.json` works
- [ ] `jn cat file.json | jn put out.csv.gz` works
- [ ] Error handling for invalid NDJSON

---

## Phase 5: filter Command

### ZQ Integration
- [ ] Use embedded ZQ (compile as library)
- [ ] Parse expression
- [ ] Stream eval on each NDJSON record
- [ ] Output filtered/transformed records

### Implementation
```zig
fn filterCommand(args: *ArgIterator) !void {
    const expr = args.next() orelse return error.MissingExpression;
    const compiled = try zq.compile(expr);

    var reader = std.io.bufferedReader(std.io.getStdIn().reader());
    var writer = std.io.bufferedWriter(std.io.getStdOut().writer());

    while (try reader.readUntilDelimiterOrEof('\n')) |line| {
        const value = try std.json.parse(line);
        const result = try zq.eval(compiled, value);
        try std.json.stringify(result, writer);
        try writer.writeByte('\n');
    }
    try writer.flush();
}
```

### Quality Gate
- [ ] `jn filter '.field'` works
- [ ] `jn filter 'select(.x > 10)'` works
- [ ] Error messages clear and helpful

---

## Phase 6: head/tail Commands

### head
- [ ] Count records (newlines)
- [ ] Output first N
- [ ] Stop reading after N (early termination)

### tail
- [ ] Buffer last N records
- [ ] Output at end of input
- [ ] Handle memory for large N

### Quality Gate
- [ ] `jn head -n 5` outputs 5 records
- [ ] `jn tail -n 5` outputs 5 records
- [ ] Early termination works for head

---

## Phase 7: run Command

### Two-Stage Pipeline
```bash
jn run input.csv output.json
# Equivalent to: jn cat input.csv | jn put output.json
```

- [ ] Parse input and output addresses
- [ ] Resolve both plugins
- [ ] Connect with pipe (no intermediate shell)
- [ ] Handle errors from either stage

### Implementation
```zig
fn runCommand(args: *ArgIterator) !void {
    const input = args.next() orelse return error.MissingInput;
    const output = args.next() orelse return error.MissingOutput;

    const reader_plugin = try resolvePlugin(parseAddress(input));
    const writer_plugin = try resolvePlugin(parseAddress(output));

    // Create pipe
    var pipe = try std.os.pipe();

    // Spawn reader
    var reader = try spawnPlugin(reader_plugin, .read, ...);
    reader.stdout = pipe[1];

    // Spawn writer
    var writer = try spawnPlugin(writer_plugin, .write, ...);
    writer.stdin = pipe[0];

    // Wait for both
    _ = try reader.wait();
    _ = try writer.wait();
}
```

### Quality Gate
- [ ] `jn run in.csv out.json` works
- [ ] Error from reader propagates
- [ ] Error from writer propagates

---

## Phase 8: Native Plugin Loading

### Shared Library Interface
```zig
// Plugin exports these symbols:
export fn plugin_meta() [*:0]const u8;  // Returns JSON manifest
export fn plugin_read(config: [*:0]const u8) void;
export fn plugin_write(config: [*:0]const u8) void;
```

### Dynamic Loading
```zig
fn loadNativePlugin(path: []const u8) !NativePlugin {
    const lib = try std.DynLib.open(path);
    return .{
        .meta = lib.lookup(*fn() [*:0]const u8, "plugin_meta"),
        .read = lib.lookup(*fn([*:0]const u8) void, "plugin_read"),
        .write = lib.lookup(*fn([*:0]const u8) void, "plugin_write"),
    };
}
```

### Benefits
- No process spawn for native plugins
- Direct function call
- Shared memory possible

### Quality Gate
- [ ] Native plugins load correctly
- [ ] Direct execution works
- [ ] Faster than spawned Python

---

## Phase 9: Python Compatibility

### Spawning Python Plugins
- [ ] Detect .py extension
- [ ] Find Python interpreter
- [ ] Spawn with correct arguments
- [ ] Handle stdin/stdout piping

### Implementation
```zig
fn spawnPythonPlugin(plugin: Plugin, mode: Mode, config: Config) !Child {
    const python = findPython() orelse return error.PythonNotFound;

    var child = std.ChildProcess.init(&[_][]const u8{
        python,
        plugin.path,
        "--mode",
        @tagName(mode),
    }, allocator);

    child.stdin_behavior = .Pipe;
    child.stdout_behavior = .Pipe;

    try child.spawn();
    return child;
}
```

### Quality Gate
- [ ] Python plugins work from Zig CLI
- [ ] All existing plugins work
- [ ] Performance acceptable

---

## Phase 10: Testing & Release

### Test Matrix
| Command | Python Plugin | Zig Plugin | Test |
|---------|--------------|------------|------|
| cat | ✅ | ✅ | ✅ |
| put | ✅ | ✅ | ✅ |
| filter | N/A | Native | ✅ |
| head | N/A | Native | ✅ |
| tail | N/A | Native | ✅ |
| run | ✅ | ✅ | ✅ |

### Backward Compatibility
- [ ] All existing `jn` commands work
- [ ] All existing pipelines work
- [ ] Python plugins work unchanged

### Release Artifacts
```
jn-v2.0.0-linux-x86_64.tar.gz
├── jn              # Single binary (all commands)
├── plugins/
│   ├── formats/
│   │   ├── csv.so      # Native CSV
│   │   ├── json.so     # Native JSON
│   │   └── *.py        # Python plugins
│   └── ...
```

### Binary Size
- [ ] `jn` binary <2MB (ReleaseSmall)
- [ ] Total distribution <5MB

### Quality Gate
- [ ] All tests pass
- [ ] Backward compatible
- [ ] Binary size target met

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Startup time | <5ms |
| Binary size | <2MB |
| Backward compatibility | 100% |
| All commands work | Yes |
| Python plugins work | Yes |
| Native plugins work | Yes |

---

## Notes

**Architecture Decisions:**
- Embed ZQ directly (not as separate binary)
- Support both native and Python plugins
- Single binary distribution (no runtime dependencies)

**Deferred:**
- profile command (complex, keep in Python initially)
- inspect command (complex, keep in Python initially)
- analyze command (complex, keep in Python initially)
- sh command (jc integration complex)

**Migration Path:**
1. Release Zig `jn` binary alongside Python version
2. Users can choose which to use via PATH
3. Gradually deprecate Python CLI
4. Eventually Python CLI becomes optional/legacy
