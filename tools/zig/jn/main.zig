//! jn: Main orchestrator for JN CLI tools
//!
//! Thin dispatcher that routes subcommands to jn-* tools.
//!
//! Usage:
//!   jn <command> [args...]
//!
//! Commands:
//!   cat        Read and convert to NDJSON (jn-cat)
//!   put        Write from NDJSON to other formats (jn-put)
//!   filter     Filter and transform NDJSON (jn-filter)
//!   head       Output first N records (jn-head)
//!   tail       Output last N records (jn-tail)
//!   analyze    Compute statistics on NDJSON (jn-analyze)
//!   inspect    Profile discovery and schema inference (jn-inspect)
//!   join       Join two NDJSON sources (jn-join)
//!   merge      Concatenate multiple sources (jn-merge)
//!   sh         Execute shell commands as NDJSON (jn-sh)
//!
//! Options:
//!   --help, -h       Show this help
//!   --version        Show version
//!
//! Examples:
//!   jn cat data.csv
//!   jn cat data.csv | jn filter '.x > 10' | jn put output.json
//!   jn --help
//!   jn cat --help

const std = @import("std");
const jn_core = @import("jn-core");

const VERSION = "0.1.0";

/// Known subcommands and their descriptions
const Command = struct {
    name: []const u8,
    tool: []const u8,
    description: []const u8,
};

const COMMANDS = [_]Command{
    .{ .name = "cat", .tool = "jn-cat", .description = "Read and convert to NDJSON" },
    .{ .name = "put", .tool = "jn-put", .description = "Write from NDJSON to other formats" },
    .{ .name = "filter", .tool = "jn-filter", .description = "Filter and transform NDJSON" },
    .{ .name = "head", .tool = "jn-head", .description = "Output first N records" },
    .{ .name = "tail", .tool = "jn-tail", .description = "Output last N records" },
    .{ .name = "analyze", .tool = "jn-analyze", .description = "Compute statistics on NDJSON" },
    .{ .name = "inspect", .tool = "jn-inspect", .description = "Profile discovery and schema inference" },
    .{ .name = "join", .tool = "jn-join", .description = "Join two NDJSON sources" },
    .{ .name = "merge", .tool = "jn-merge", .description = "Concatenate multiple sources" },
    .{ .name = "sh", .tool = "jn-sh", .description = "Execute shell commands as NDJSON" },
};

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    // Get command line arguments
    var args = std.process.args();
    _ = args.skip(); // Skip program name

    // Get first argument
    const first_arg = args.next() orelse {
        printUsage();
        return;
    };

    // Handle --help or -h
    if (std.mem.eql(u8, first_arg, "--help") or std.mem.eql(u8, first_arg, "-h")) {
        printUsage();
        return;
    }

    // Handle --version
    if (std.mem.eql(u8, first_arg, "--version")) {
        printVersion();
        return;
    }

    // Look up the subcommand
    var tool_name: ?[]const u8 = null;
    for (COMMANDS) |cmd| {
        if (std.mem.eql(u8, first_arg, cmd.name)) {
            tool_name = cmd.tool;
            break;
        }
    }

    if (tool_name == null) {
        // Check if it looks like an option
        if (std.mem.startsWith(u8, first_arg, "-")) {
            jn_core.exitWithError("jn: unknown option: {s}\nUse 'jn --help' for usage", .{first_arg});
        }
        jn_core.exitWithError("jn: unknown command: {s}\nUse 'jn --help' for available commands", .{first_arg});
    }

    // Find the tool binary
    const tool_path = findTool(allocator, tool_name.?) orelse {
        jn_core.exitWithError("jn: tool '{s}' not found\nHint: run 'make zig-tools' to build tools", .{tool_name.?});
    };

    // Build argument list for the tool
    // Count remaining arguments first
    var arg_count: usize = 1; // tool path
    var temp_args = args;
    while (temp_args.next()) |_| {
        arg_count += 1;
    }

    // Allocate and fill argv
    var argv = allocator.alloc([]const u8, arg_count) catch {
        jn_core.exitWithError("jn: out of memory", .{});
    };
    defer allocator.free(argv);

    argv[0] = tool_path;

    // Reset and refill
    args = std.process.args();
    _ = args.skip(); // Skip program name
    _ = args.skip(); // Skip subcommand

    var idx: usize = 1;
    while (args.next()) |arg| {
        argv[idx] = arg;
        idx += 1;
    }

    // Execute the tool
    var child = std.process.Child.init(argv, allocator);
    child.stdin_behavior = .Inherit;
    child.stdout_behavior = .Inherit;
    child.stderr_behavior = .Inherit;

    child.spawn() catch |err| {
        jn_core.exitWithError("jn: failed to execute '{s}': {s}", .{ tool_name.?, @errorName(err) });
    };

    const result = child.wait() catch |err| {
        jn_core.exitWithError("jn: failed to wait for '{s}': {s}", .{ tool_name.?, @errorName(err) });
    };

    // Exit with the tool's exit code
    switch (result) {
        .Exited => |code| {
            if (code != 0) {
                std.process.exit(code);
            }
        },
        .Signal => |sig| {
            // Signal + 128 per shell convention
            const sig_u8: u8 = @truncate(sig);
            std.process.exit(128 +| sig_u8);
        },
        .Stopped => |sig| {
            const sig_u8: u8 = @truncate(sig);
            std.process.exit(128 +| sig_u8);
        },
        .Unknown => |val| {
            std.process.exit(@truncate(val));
        },
    }
}

/// Find a tool binary by name
fn findTool(allocator: std.mem.Allocator, name: []const u8) ?[]const u8 {
    // Try paths relative to JN_HOME
    if (std.posix.getenv("JN_HOME")) |jn_home| {
        const path = std.fmt.allocPrint(allocator, "{s}/tools/zig/{s}/bin/{s}", .{ jn_home, name, name }) catch return null;
        if (std.fs.cwd().access(path, .{})) |_| {
            return path;
        } else |_| {
            allocator.free(path);
        }

        // Also check $JN_HOME/bin/ (installed tools)
        const bin_path = std.fmt.allocPrint(allocator, "{s}/bin/{s}", .{ jn_home, name }) catch return null;
        if (std.fs.cwd().access(bin_path, .{})) |_| {
            return bin_path;
        } else |_| {
            allocator.free(bin_path);
        }
    }

    // Try relative to current directory (development mode)
    const dev_path = std.fmt.allocPrint(allocator, "tools/zig/{s}/bin/{s}", .{ name, name }) catch return null;
    if (std.fs.cwd().access(dev_path, .{})) |_| {
        return dev_path;
    } else |_| {
        allocator.free(dev_path);
    }

    // Try ~/.local/jn/bin (user installation)
    if (std.posix.getenv("HOME")) |home| {
        const user_path = std.fmt.allocPrint(allocator, "{s}/.local/jn/bin/{s}", .{ home, name }) catch return null;
        if (std.fs.cwd().access(user_path, .{})) |_| {
            return user_path;
        } else |_| {
            allocator.free(user_path);
        }
    }

    return null;
}

/// Print version
fn printVersion() void {
    var buf: [256]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.print("jn {s}\n", .{VERSION}) catch {};
    jn_core.flushWriter(stdout);
}

/// Print usage information
fn printUsage() void {
    const usage =
        \\jn - Universal data transformation tool
        \\
        \\Usage: jn <command> [args...]
        \\
        \\Commands:
        \\  cat        Read and convert to NDJSON
        \\  put        Write from NDJSON to other formats
        \\  filter     Filter and transform NDJSON
        \\  head       Output first N records
        \\  tail       Output last N records
        \\  analyze    Compute statistics on NDJSON
        \\  inspect    Profile discovery and schema inference
        \\  join       Join two NDJSON sources
        \\  merge      Concatenate multiple sources
        \\  sh         Execute shell commands as NDJSON
        \\
        \\Options:
        \\  --help, -h     Show this help
        \\  --version      Show version
        \\
        \\Examples:
        \\  jn cat data.csv                          Read CSV as NDJSON
        \\  jn cat data.csv | jn filter '.x > 10'    Filter records
        \\  jn cat input.csv | jn put output.json    Convert CSV to JSON
        \\  jn cat --help                            Help for specific command
        \\
        \\NDJSON is the universal interchange format. All tools read/write NDJSON.
        \\Pipelines: jn cat (read) → jn filter (transform) → jn put (write)
        \\
    ;
    var buf: [2048]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.writeAll(usage) catch {};
    jn_core.flushWriter(stdout);
}

// Tests
test "command lookup" {
    for (COMMANDS) |cmd| {
        try std.testing.expect(cmd.name.len > 0);
        try std.testing.expect(cmd.tool.len > 0);
        try std.testing.expect(cmd.description.len > 0);
    }
}

test "known commands" {
    // Verify all expected commands are present
    const expected = [_][]const u8{ "cat", "put", "filter", "head", "tail", "analyze", "inspect", "join", "merge", "sh" };
    for (expected) |name| {
        var found = false;
        for (COMMANDS) |cmd| {
            if (std.mem.eql(u8, cmd.name, name)) {
                found = true;
                break;
            }
        }
        try std.testing.expect(found);
    }
}
