//! jn-filter: ZQ wrapper for JN
//!
//! Filters and transforms NDJSON using ZQ expressions.
//!
//! Usage:
//!   jn-filter [OPTIONS] <EXPRESSION>
//!
//! Options:
//!   --help, -h              Show this help
//!   --version               Show version
//!   -c, --compact           Compact output (default)
//!   -r, --raw-strings       Output raw strings (unquoted)
//!   -s, --slurp             Read all input into array first
//!
//! Examples:
//!   jn-filter '.name'
//!   jn-filter 'select(.age > 21)'
//!   jn-filter '.x + .y'
//!   jn-filter 'map(.value)'

const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");

const VERSION = "0.1.0";

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const args = jn_cli.parseArgs();

    // Handle --help
    if (args.has("help") or args.has("h")) {
        printUsage();
        return;
    }

    // Handle --version
    if (args.has("version")) {
        printVersion();
        return;
    }

    // Get expression from positional argument
    const expression = getPositionalArg() orelse {
        jn_core.exitWithError("jn-filter: missing expression argument\nUsage: jn-filter [OPTIONS] <EXPRESSION>", .{});
    };

    // Find ZQ binary
    const zq_path = findZq(allocator) orelse {
        jn_core.exitWithError("jn-filter: zq binary not found\nHint: run 'make zq' to build it", .{});
    };

    // Build ZQ arguments
    var argv_buf: [10][]const u8 = undefined;
    var argc: usize = 0;

    argv_buf[argc] = zq_path;
    argc += 1;

    // Pass through ZQ options
    if (args.has("c") or args.has("compact")) {
        argv_buf[argc] = "-c";
        argc += 1;
    }
    if (args.has("r") or args.has("raw-strings")) {
        argv_buf[argc] = "-r";
        argc += 1;
    }
    if (args.has("s") or args.has("slurp")) {
        argv_buf[argc] = "-s";
        argc += 1;
    }

    // Add expression
    argv_buf[argc] = expression;
    argc += 1;

    const argv = argv_buf[0..argc];

    // Execute ZQ
    var child = std.process.Child.init(argv, allocator);
    child.stdin_behavior = .Inherit;
    child.stdout_behavior = .Inherit;
    child.stderr_behavior = .Inherit;

    try child.spawn();
    const result = child.wait() catch |err| {
        jn_core.exitWithError("jn-filter: zq execution failed: {s}", .{@errorName(err)});
    };

    // Properly handle all termination types to avoid undefined behavior
    switch (result) {
        .Exited => |code| {
            if (code != 0) {
                std.process.exit(code);
            }
        },
        .Signal => |sig| {
            // Exit with 128 + signal number (Unix convention)
            std.process.exit(128 +| @as(u8, @truncate(sig)));
        },
        .Stopped => |sig| {
            // Stopped has a u32 stop code, not an enum
            std.process.exit(128 +| @as(u8, @truncate(sig)));
        },
        .Unknown => |code| {
            std.process.exit(if (code != 0) 1 else 0);
        },
    }
}

/// Get the first positional argument (not starting with -)
fn getPositionalArg() ?[]const u8 {
    var args_iter = std.process.args();
    _ = args_iter.skip(); // Skip program name

    while (args_iter.next()) |arg| {
        // Skip flags
        if (std.mem.startsWith(u8, arg, "-")) {
            continue;
        }
        return arg;
    }
    return null;
}

/// Find ZQ binary
fn findZq(allocator: std.mem.Allocator) ?[]const u8 {
    // Try paths relative to JN_HOME
    if (std.posix.getenv("JN_HOME")) |jn_home| {
        // First try $JN_HOME/bin/zq (installed location)
        const bin_path = std.fmt.allocPrint(allocator, "{s}/bin/zq", .{jn_home}) catch return null;
        if (std.fs.cwd().access(bin_path, .{})) |_| {
            return bin_path;
        } else |_| {
            allocator.free(bin_path);
        }

        // Also try $JN_HOME/zq/zig-out/bin/zq (development location)
        const dev_path = std.fmt.allocPrint(allocator, "{s}/zq/zig-out/bin/zq", .{jn_home}) catch return null;
        if (std.fs.cwd().access(dev_path, .{})) |_| {
            return dev_path;
        } else |_| {
            allocator.free(dev_path);
        }
    }

    // Try sibling to executable (installed layout: both in same bin/)
    var exe_path_buf: [std.fs.max_path_bytes]u8 = undefined;
    if (std.fs.selfExePath(&exe_path_buf)) |exe_path| {
        if (std.fs.path.dirname(exe_path)) |exe_dir| {
            const sibling_path = std.fmt.allocPrint(allocator, "{s}/zq", .{exe_dir}) catch return null;
            if (std.fs.cwd().access(sibling_path, .{})) |_| {
                return sibling_path;
            } else |_| {
                allocator.free(sibling_path);
            }
        }
    } else |_| {}

    // Try relative to current directory (development mode)
    const cwd_dev_path = "zq/zig-out/bin/zq";
    if (std.fs.cwd().access(cwd_dev_path, .{})) |_| {
        return cwd_dev_path;
    } else |_| {}

    // Try relative to executable's location (development layout)
    // Executable is at: /path/to/jn/tools/zig/jn-filter/bin/jn-filter
    // ZQ is at: /path/to/jn/zq/zig-out/bin/zq
    if (std.fs.selfExePath(&exe_path_buf)) |exe_path| {
        // Go up 4 levels: bin -> jn-filter -> zig -> tools -> root
        var dir = std.fs.path.dirname(exe_path);
        var i: usize = 0;
        while (i < 4 and dir != null) : (i += 1) {
            dir = std.fs.path.dirname(dir.?);
        }
        if (dir) |root| {
            const exe_rel_path = std.fmt.allocPrint(allocator, "{s}/zq/zig-out/bin/zq", .{root}) catch return null;
            if (std.fs.cwd().access(exe_rel_path, .{})) |_| {
                return exe_rel_path;
            } else |_| {
                allocator.free(exe_rel_path);
            }
        }
    } else |_| {}

    // Try ~/.local/jn/bin
    if (std.posix.getenv("HOME")) |home| {
        const user_path = std.fmt.allocPrint(allocator, "{s}/.local/jn/bin/zq", .{home}) catch return null;
        if (std.fs.cwd().access(user_path, .{})) |_| {
            return user_path;
        } else |_| {
            allocator.free(user_path);
        }
    }

    // Try system PATH
    const system_path = "/usr/local/bin/zq";
    if (std.fs.cwd().access(system_path, .{})) |_| {
        return system_path;
    } else |_| {}

    return null;
}

/// Print version
fn printVersion() void {
    var buf: [256]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.print("jn-filter {s}\n", .{VERSION}) catch {};
    jn_core.flushWriter(stdout);
}

/// Print usage information
fn printUsage() void {
    const usage =
        \\jn-filter - ZQ wrapper for JN
        \\
        \\Usage: jn-filter [OPTIONS] <EXPRESSION>
        \\
        \\Filters and transforms NDJSON using ZQ (jq-compatible) expressions.
        \\
        \\Options:
        \\  --help, -h            Show this help
        \\  --version             Show version
        \\  -c, --compact         Compact output (default)
        \\  -r, --raw-strings     Output raw strings (unquoted)
        \\  -s, --slurp           Read all input into array first
        \\
        \\Examples:
        \\  cat data.ndjson | jn-filter '.name'
        \\  cat data.ndjson | jn-filter 'select(.age > 21)'
        \\  cat data.ndjson | jn-filter '.x + .y'
        \\  cat data.ndjson | jn-filter -s 'map(.value)'
        \\
        \\Expression syntax (jq-compatible subset):
        \\  .field              Access field
        \\  .[0]                Array index
        \\  .[]                 Iterate array
        \\  select(cond)        Filter by condition
        \\  map(expr)           Transform each element
        \\  .a | .b             Pipe expressions
        \\  .a + .b             Arithmetic
        \\
    ;
    var buf: [2048]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.writeAll(usage) catch {};
    jn_core.flushWriter(stdout);
}

// Tests
test "getPositionalArg skips flags" {
    // This test would need mock args, so just verify it compiles
    _ = getPositionalArg;
}
