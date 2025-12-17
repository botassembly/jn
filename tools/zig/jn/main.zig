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
//!   tool       Run a JN utility tool (jn tool <name>)
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

/// Version embedded at compile time from version.txt
const VERSION = blk: {
    const raw = @embedFile("version.txt");
    break :blk std.mem.trimRight(u8, raw, &.{ '\n', '\r', ' ' });
};

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
    .{ .name = "edit", .tool = "jn-edit", .description = "Surgical JSON field editing" },
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

    // Handle 'version' subcommand (alternative to --version)
    if (std.mem.eql(u8, first_arg, "version")) {
        printVersion();
        return;
    }

    // Handle special Python-based commands
    if (std.mem.eql(u8, first_arg, "table")) {
        try runPythonPlugin(allocator, "table_.py", "--mode=write", args);
        return;
    }

    // Handle 'tool' command for user utility tools
    if (std.mem.eql(u8, first_arg, "tool")) {
        try runUserTool(allocator, args);
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
    // Try paths relative to JN_HOME (only if JN_HOME has tools)
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

    // Try libexec layout: bin/jn -> ../libexec/jn/<tool>
    var exe_buf: [std.fs.max_path_bytes]u8 = undefined;
    if (std.fs.selfExePath(&exe_buf)) |exe_path| {
        if (std.fs.path.dirname(exe_path)) |bin_dir| {
            if (std.fs.path.dirname(bin_dir)) |dist_dir| {
                const libexec_path = std.fmt.allocPrint(allocator, "{s}/libexec/jn/{s}", .{ dist_dir, name }) catch return null;
                if (std.fs.cwd().access(libexec_path, .{})) |_| {
                    return libexec_path;
                } else |_| {
                    allocator.free(libexec_path);
                }
            }
        }
    } else |_| {}

    // Try sibling to executable (flat bin/ layout: legacy/fallback)
    if (std.fs.selfExePath(&exe_buf)) |exe_path| {
        if (std.fs.path.dirname(exe_path)) |exe_dir| {
            const sibling_path = std.fmt.allocPrint(allocator, "{s}/{s}", .{ exe_dir, name }) catch return null;
            if (std.fs.cwd().access(sibling_path, .{})) |_| {
                return sibling_path;
            } else |_| {
                allocator.free(sibling_path);
            }
        }
    } else |_| {}

    // Try relative to current directory (development mode)
    const dev_path = std.fmt.allocPrint(allocator, "tools/zig/{s}/bin/{s}", .{ name, name }) catch return null;
    if (std.fs.cwd().access(dev_path, .{})) |_| {
        return dev_path;
    } else |_| {
        allocator.free(dev_path);
    }

    // Try relative to executable's location
    // Executable is at: /path/to/jn/tools/zig/jn/bin/jn
    // Sibling tools are at: /path/to/jn/tools/zig/<tool>/bin/<tool>
    var exe_path_buf: [std.fs.max_path_bytes]u8 = undefined;
    if (std.fs.selfExePath(&exe_path_buf)) |exe_path| {
        // Go up from jn -> bin -> jn -> zig -> tools -> root
        var dir = std.fs.path.dirname(exe_path); // bin
        var i: usize = 0;
        while (i < 2 and dir != null) : (i += 1) {
            dir = std.fs.path.dirname(dir.?); // jn -> zig
        }
        // Now we're at tools/zig, can access sibling tool directories
        if (dir) |zig_dir| {
            const exe_rel_path = std.fmt.allocPrint(allocator, "{s}/{s}/bin/{s}", .{ zig_dir, name, name }) catch return null;
            if (std.fs.cwd().access(exe_rel_path, .{})) |_| {
                return exe_rel_path;
            } else |_| {
                allocator.free(exe_rel_path);
            }
        }
    } else |_| {}

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

/// Find a Python plugin by name in JN_HOME/plugins/*/
fn findPythonPlugin(allocator: std.mem.Allocator, name: []const u8) ?[]const u8 {
    // Search in common plugin subdirectories
    const subdirs = [_][]const u8{ "formats", "protocols", "databases", "filters", "shell" };

    // Try JN_HOME first (if jn_home/plugins exists there)
    if (std.posix.getenv("JN_HOME")) |jn_home| {
        const check_path = std.fmt.allocPrint(allocator, "{s}/jn_home/plugins", .{jn_home}) catch return null;
        defer allocator.free(check_path);
        if (std.fs.cwd().access(check_path, .{})) |_| {
            for (subdirs) |subdir| {
                const path = std.fmt.allocPrint(allocator, "{s}/jn_home/plugins/{s}/{s}", .{ jn_home, subdir, name }) catch continue;
                if (std.fs.cwd().access(path, .{})) |_| {
                    return path;
                } else |_| {
                    allocator.free(path);
                }
            }
        } else |_| {}
    }

    // Try relative to current directory
    for (subdirs) |subdir| {
        const path = std.fmt.allocPrint(allocator, "jn_home/plugins/{s}/{s}", .{ subdir, name }) catch continue;
        if (std.fs.cwd().access(path, .{})) |_| {
            return path;
        } else |_| {
            allocator.free(path);
        }
    }

    // Try relative to executable's location
    var exe_path_buf: [std.fs.max_path_bytes]u8 = undefined;
    if (std.fs.selfExePath(&exe_path_buf)) |exe_path| {
        // Try libexec layout: bin/jn -> ../libexec/jn/jn_home/plugins/
        if (std.fs.path.dirname(exe_path)) |bin_dir| {
            if (std.fs.path.dirname(bin_dir)) |dist_root| {
                for (subdirs) |subdir| {
                    const libexec_path = std.fmt.allocPrint(allocator, "{s}/libexec/jn/jn_home/plugins/{s}/{s}", .{ dist_root, subdir, name }) catch continue;
                    if (std.fs.cwd().access(libexec_path, .{})) |_| {
                        return libexec_path;
                    } else |_| {
                        allocator.free(libexec_path);
                    }
                }
            }
        }

        // Try legacy release layout: bin/jn -> up 1 level -> jn_home/plugins/
        if (std.fs.path.dirname(exe_path)) |bin_dir| {
            if (std.fs.path.dirname(bin_dir)) |release_root| {
                for (subdirs) |subdir| {
                    const release_path = std.fmt.allocPrint(allocator, "{s}/jn_home/plugins/{s}/{s}", .{ release_root, subdir, name }) catch continue;
                    if (std.fs.cwd().access(release_path, .{})) |_| {
                        return release_path;
                    } else |_| {
                        allocator.free(release_path);
                    }
                }
            }
        }

        // Try dev layout: bin -> jn -> zig -> tools -> root (4 levels up)
        var dir = std.fs.path.dirname(exe_path);
        var i: usize = 0;
        while (i < 4 and dir != null) : (i += 1) {
            dir = std.fs.path.dirname(dir.?);
        }
        if (dir) |root| {
            for (subdirs) |subdir| {
                const path = std.fmt.allocPrint(allocator, "{s}/jn_home/plugins/{s}/{s}", .{ root, subdir, name }) catch continue;
                if (std.fs.cwd().access(path, .{})) |_| {
                    return path;
                } else |_| {
                    allocator.free(path);
                }
            }
        }
    } else |_| {}

    return null;
}

/// Find a user tool by name in jn_home/tools/
fn findUserTool(allocator: std.mem.Allocator, name: []const u8) ?[]const u8 {
    // Try JN_HOME first
    if (std.posix.getenv("JN_HOME")) |jn_home| {
        const path = std.fmt.allocPrint(allocator, "{s}/jn_home/tools/{s}", .{ jn_home, name }) catch return null;
        if (std.fs.cwd().access(path, .{})) |_| {
            return path;
        } else |_| {
            allocator.free(path);
        }
    }

    // Try relative to current directory (development mode)
    const dev_path = std.fmt.allocPrint(allocator, "jn_home/tools/{s}", .{name}) catch return null;
    if (std.fs.cwd().access(dev_path, .{})) |_| {
        return dev_path;
    } else |_| {
        allocator.free(dev_path);
    }

    // Try relative to executable's location
    var exe_path_buf: [std.fs.max_path_bytes]u8 = undefined;
    if (std.fs.selfExePath(&exe_path_buf)) |exe_path| {
        // Try libexec layout: bin/jn -> ../libexec/jn/jn_home/tools/
        if (std.fs.path.dirname(exe_path)) |bin_dir| {
            if (std.fs.path.dirname(bin_dir)) |dist_root| {
                const libexec_path = std.fmt.allocPrint(allocator, "{s}/libexec/jn/jn_home/tools/{s}", .{ dist_root, name }) catch return null;
                if (std.fs.cwd().access(libexec_path, .{})) |_| {
                    return libexec_path;
                } else |_| {
                    allocator.free(libexec_path);
                }
            }
        }

        // Try legacy release layout: bin/jn -> up 1 level -> jn_home/tools/
        if (std.fs.path.dirname(exe_path)) |bin_dir| {
            if (std.fs.path.dirname(bin_dir)) |release_root| {
                const release_path = std.fmt.allocPrint(allocator, "{s}/jn_home/tools/{s}", .{ release_root, name }) catch return null;
                if (std.fs.cwd().access(release_path, .{})) |_| {
                    return release_path;
                } else |_| {
                    allocator.free(release_path);
                }
            }
        }

        // Try dev layout: bin -> jn -> zig -> tools -> root (4 levels up)
        var dir = std.fs.path.dirname(exe_path);
        var i: usize = 0;
        while (i < 4 and dir != null) : (i += 1) {
            dir = std.fs.path.dirname(dir.?);
        }
        if (dir) |root| {
            const path = std.fmt.allocPrint(allocator, "{s}/jn_home/tools/{s}", .{ root, name }) catch return null;
            if (std.fs.cwd().access(path, .{})) |_| {
                return path;
            } else |_| {
                allocator.free(path);
            }
        }
    } else |_| {}

    // Try ~/.local/jn/tools (user installation)
    if (std.posix.getenv("HOME")) |home| {
        const user_path = std.fmt.allocPrint(allocator, "{s}/.local/jn/tools/{s}", .{ home, name }) catch return null;
        if (std.fs.cwd().access(user_path, .{})) |_| {
            return user_path;
        } else |_| {
            allocator.free(user_path);
        }
    }

    return null;
}

/// Run a user tool from jn_home/tools/
fn runUserTool(allocator: std.mem.Allocator, args: std.process.ArgIterator) !void {
    var args_copy = args;

    // Get tool name
    const tool_name = args_copy.next() orelse {
        printToolUsage();
        return;
    };

    // Handle --help
    if (std.mem.eql(u8, tool_name, "--help") or std.mem.eql(u8, tool_name, "-h")) {
        printToolUsage();
        return;
    }

    // Find the tool
    const tool_path = findUserTool(allocator, tool_name) orelse {
        jn_core.exitWithError("jn tool: '{s}' not found\nHint: check jn_home/tools/ or ~/.local/jn/tools/", .{tool_name});
    };

    // Count remaining arguments
    var arg_count: usize = 1; // tool path
    var temp_args = args_copy;
    while (temp_args.next()) |_| {
        arg_count += 1;
    }

    // Allocate argv
    var argv = allocator.alloc([]const u8, arg_count) catch {
        jn_core.exitWithError("jn tool: out of memory", .{});
    };
    defer allocator.free(argv);

    argv[0] = tool_path;

    // Fill remaining args
    var args_refill = args;
    _ = args_refill.next(); // Skip tool name
    var idx: usize = 1;
    while (args_refill.next()) |arg| {
        argv[idx] = arg;
        idx += 1;
    }

    // Execute the tool
    var child = std.process.Child.init(argv, allocator);
    child.stdin_behavior = .Inherit;
    child.stdout_behavior = .Inherit;
    child.stderr_behavior = .Inherit;

    child.spawn() catch |err| {
        jn_core.exitWithError("jn tool: failed to execute '{s}': {s}", .{ tool_name, @errorName(err) });
    };

    const result = child.wait() catch |err| {
        jn_core.exitWithError("jn tool: failed to wait for '{s}': {s}", .{ tool_name, @errorName(err) });
    };

    // Exit with the tool's exit code
    switch (result) {
        .Exited => |code| {
            if (code != 0) {
                std.process.exit(code);
            }
        },
        .Signal => |sig| {
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

/// Print tool subcommand usage
fn printToolUsage() void {
    const usage =
        \\jn tool - Run JN utility tools
        \\
        \\Usage: jn tool <name> [args...]
        \\
        \\Tools are standalone utilities that leverage JN's NDJSON infrastructure.
        \\They are located in jn_home/tools/ or ~/.local/jn/tools/
        \\
        \\Available tools:
        \\  todo       Task management with dependencies
        \\
        \\Examples:
        \\  jn tool todo list
        \\  jn tool todo add "Fix bug" -p high
        \\  jn tool todo ready
        \\
        \\Create an alias for convenience:
        \\  alias todo="jn tool todo"
        \\
    ;
    var buf: [1024]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.writeAll(usage) catch {};
    jn_core.flushWriter(stdout);
}

/// Escape a path for use in single-quoted shell arguments.
/// SECURITY: This prevents command injection via paths containing single quotes.
fn escapeShellPath(allocator: std.mem.Allocator, path: []const u8) ![]const u8 {
    if (jn_core.isSafeForShellSingleQuote(path)) {
        return path;
    }
    return jn_core.escapeForShellSingleQuote(allocator, path);
}

/// Run a Python plugin using uv run --script
fn runPythonPlugin(allocator: std.mem.Allocator, plugin_name: []const u8, default_mode: []const u8, remaining_args: std.process.ArgIterator) !void {
    const plugin_path = findPythonPlugin(allocator, plugin_name) orelse {
        jn_core.exitWithError("jn: Python plugin '{s}' not found\nHint: check JN_HOME/jn_home/plugins/", .{plugin_name});
    };

    // SECURITY: Escape the plugin path to prevent command injection
    const escaped_plugin_path = try escapeShellPath(allocator, plugin_path);
    defer if (escaped_plugin_path.ptr != plugin_path.ptr) allocator.free(@constCast(escaped_plugin_path));

    // Build shell command with dynamic allocation to handle escaped args
    var cmd_parts: std.ArrayListUnmanaged(u8) = .empty;
    defer cmd_parts.deinit(allocator);

    // Add base command
    try cmd_parts.appendSlice(allocator, "uv run --script '");
    try cmd_parts.appendSlice(allocator, escaped_plugin_path);
    try cmd_parts.appendSlice(allocator, "' ");
    try cmd_parts.appendSlice(allocator, default_mode);

    // Collect and escape remaining arguments
    var args_copy = remaining_args;
    while (args_copy.next()) |arg| {
        // SECURITY: Escape each argument to prevent command injection
        const escaped_arg = try escapeShellPath(allocator, arg);
        defer if (escaped_arg.ptr != arg.ptr) allocator.free(@constCast(escaped_arg));
        try cmd_parts.appendSlice(allocator, " '");
        try cmd_parts.appendSlice(allocator, escaped_arg);
        try cmd_parts.append(allocator, '\'');
    }

    const shell_cmd = cmd_parts.items;

    // Run via shell
    const shell_argv: [3][]const u8 = .{ "/bin/sh", "-c", shell_cmd };
    var child = std.process.Child.init(&shell_argv, allocator);
    child.stdin_behavior = .Inherit;
    child.stdout_behavior = .Inherit;
    child.stderr_behavior = .Inherit;

    try child.spawn();
    const result = child.wait() catch |err| {
        jn_core.exitWithError("jn: failed to run Python plugin: {s}", .{@errorName(err)});
    };

    switch (result) {
        .Exited => |code| {
            if (code != 0) {
                std.process.exit(code);
            }
        },
        else => {
            std.process.exit(1);
        },
    }
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
        \\  edit       Surgical JSON field editing
        \\  head       Output first N records
        \\  tail       Output last N records
        \\  analyze    Compute statistics on NDJSON
        \\  inspect    Profile discovery and schema inference
        \\  join       Join two NDJSON sources
        \\  merge      Concatenate multiple sources
        \\  sh         Execute shell commands as NDJSON
        \\  table      Format NDJSON as table (via Python)
        \\  tool       Run utility tools (jn tool <name>)
        \\  version    Show version
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
    const expected = [_][]const u8{ "cat", "put", "filter", "edit", "head", "tail", "analyze", "inspect", "join", "merge", "sh" };
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
