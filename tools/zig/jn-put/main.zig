//! jn-put: Universal writer for JN
//!
//! Reads NDJSON from stdin and writes to various output formats.
//!
//! Usage:
//!   jn-put [OPTIONS] <ADDRESS>
//!
//! Address formats:
//!   - output.csv            Local file (format auto-detected)
//!   - output.json           JSON array output
//!   - output.txt~csv        Format override
//!   - -                     Write to stdout
//!
//! Options:
//!   --help, -h              Show this help
//!   --version               Show version
//!   --delimiter=CHAR        CSV delimiter (passed to plugin)
//!   --indent=N              JSON indentation (passed to plugin)
//!
//! Examples:
//!   jn-put output.csv
//!   jn-put output.json
//!   jn-put output.txt~csv
//!   jn-put -~json

const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");
const jn_address = @import("jn-address");

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

    // Get address from positional argument
    const address_str = getPositionalArg() orelse {
        jn_core.exitWithError("jn-put: missing address argument\nUsage: jn-put [OPTIONS] <ADDRESS>", .{});
    };

    // Parse the address
    const address = jn_address.parse(address_str);

    // Route based on address type
    switch (address.address_type) {
        .stdin => {
            // Stdout: write to stdout via format plugin
            try handleStdout(allocator, address, &args);
        },
        .file => {
            try handleFile(allocator, address, &args);
        },
        .url => {
            jn_core.exitWithError("jn-put: remote URLs not yet supported\nAddress: {s}", .{address_str});
        },
        .profile => {
            jn_core.exitWithError("jn-put: profile references not yet supported\nAddress: {s}", .{address_str});
        },
        .glob => {
            jn_core.exitWithError("jn-put: glob patterns not supported for output\nAddress: {s}", .{address_str});
        },
    }
}

/// Get the first positional argument (not starting with --)
fn getPositionalArg() ?[]const u8 {
    var args_iter = std.process.args();
    _ = args_iter.skip(); // Skip program name

    while (args_iter.next()) |arg| {
        if (!std.mem.startsWith(u8, arg, "-")) {
            return arg;
        }
        // Skip --key=value style args
        if (std.mem.startsWith(u8, arg, "--")) {
            continue;
        }
        // Single dash is stdout
        if (std.mem.eql(u8, arg, "-")) {
            return arg;
        }
    }
    return null;
}

/// Handle stdout output
fn handleStdout(allocator: std.mem.Allocator, address: jn_address.Address, args: *const jn_cli.ArgParser) !void {
    const format = address.effectiveFormat() orelse "jsonl";

    // For JSONL, just pass through
    if (std.mem.eql(u8, format, "jsonl") or std.mem.eql(u8, format, "ndjson")) {
        try passthroughStdin();
        return;
    }

    // For other formats, spawn the format plugin in write mode
    try spawnFormatPlugin(allocator, format, null, args);
}

/// Handle local file output
fn handleFile(allocator: std.mem.Allocator, address: jn_address.Address, args: *const jn_cli.ArgParser) !void {
    const format = address.effectiveFormat() orelse {
        jn_core.exitWithError("jn-put: cannot determine format for '{s}'\nHint: use ~format to specify (e.g., output.txt~csv)", .{address.path});
    };

    // Spawn format plugin with output redirected to file
    try spawnFormatPluginToFile(allocator, format, address.path, args);
}

/// Spawn a format plugin in write mode, output to stdout
fn spawnFormatPlugin(allocator: std.mem.Allocator, format: []const u8, file_path: ?[]const u8, args: *const jn_cli.ArgParser) !void {
    _ = file_path; // Not used for stdout

    const plugin_path = findPlugin(allocator, format) orelse {
        jn_core.exitWithError("jn-put: format plugin '{s}' not found", .{format});
    };

    // Build argument list
    var argv_buf: [6][]const u8 = undefined;
    var argc: usize = 0;

    argv_buf[argc] = plugin_path;
    argc += 1;
    argv_buf[argc] = "--mode=write";
    argc += 1;

    // Pass through relevant arguments
    var delim_arg_buf: [32]u8 = undefined;
    if (args.get("delimiter", null)) |delim| {
        const written = std.fmt.bufPrint(&delim_arg_buf, "--delimiter={s}", .{delim}) catch {
            jn_core.exitWithError("jn-put: delimiter too long", .{});
        };
        argv_buf[argc] = written;
        argc += 1;
    }

    var indent_arg_buf: [32]u8 = undefined;
    if (args.get("indent", null)) |indent| {
        const written = std.fmt.bufPrint(&indent_arg_buf, "--indent={s}", .{indent}) catch {
            jn_core.exitWithError("jn-put: indent too long", .{});
        };
        argv_buf[argc] = written;
        argc += 1;
    }

    const argv = argv_buf[0..argc];

    // Spawn the plugin
    var child = std.process.Child.init(argv, allocator);
    child.stdin_behavior = .Inherit;
    child.stdout_behavior = .Inherit;
    child.stderr_behavior = .Inherit;

    try child.spawn();
    const result = child.wait() catch |err| {
        jn_core.exitWithError("jn-put: plugin execution failed: {s}", .{@errorName(err)});
    };

    if (result.Exited != 0) {
        std.process.exit(result.Exited);
    }
}

/// Spawn a format plugin in write mode, output to file
fn spawnFormatPluginToFile(allocator: std.mem.Allocator, format: []const u8, file_path: []const u8, args: *const jn_cli.ArgParser) !void {
    const plugin_path = findPlugin(allocator, format) orelse {
        jn_core.exitWithError("jn-put: format plugin '{s}' not found", .{format});
    };

    // Build shell command to redirect output to file
    // Format: plugin --mode=write [args] > file
    var cmd_buf: [1024]u8 = undefined;
    var cmd_len: usize = 0;

    // Add plugin path
    const plugin_slice = std.fmt.bufPrint(cmd_buf[cmd_len..], "{s} --mode=write", .{plugin_path}) catch {
        jn_core.exitWithError("jn-put: command too long", .{});
    };
    cmd_len += plugin_slice.len;

    // Add optional args
    if (args.get("delimiter", null)) |delim| {
        const arg_slice = std.fmt.bufPrint(cmd_buf[cmd_len..], " --delimiter={s}", .{delim}) catch {
            jn_core.exitWithError("jn-put: command too long", .{});
        };
        cmd_len += arg_slice.len;
    }

    if (args.get("indent", null)) |indent| {
        const arg_slice = std.fmt.bufPrint(cmd_buf[cmd_len..], " --indent={s}", .{indent}) catch {
            jn_core.exitWithError("jn-put: command too long", .{});
        };
        cmd_len += arg_slice.len;
    }

    // Add output redirection
    const redir_slice = std.fmt.bufPrint(cmd_buf[cmd_len..], " > '{s}'", .{file_path}) catch {
        jn_core.exitWithError("jn-put: command too long", .{});
    };
    cmd_len += redir_slice.len;

    const shell_cmd = cmd_buf[0..cmd_len];

    // Run via shell
    const shell_argv: [3][]const u8 = .{ "/bin/sh", "-c", shell_cmd };
    var shell_child = std.process.Child.init(&shell_argv, allocator);
    shell_child.stdin_behavior = .Inherit;
    shell_child.stdout_behavior = .Inherit;
    shell_child.stderr_behavior = .Inherit;

    try shell_child.spawn();
    const result = shell_child.wait() catch |err| {
        jn_core.exitWithError("jn-put: plugin execution failed: {s}", .{@errorName(err)});
    };

    if (result.Exited != 0) {
        std.process.exit(result.Exited);
    }
}

/// Find a plugin by name
fn findPlugin(allocator: std.mem.Allocator, name: []const u8) ?[]const u8 {
    // Try paths relative to JN_HOME
    if (std.posix.getenv("JN_HOME")) |jn_home| {
        const path = std.fmt.allocPrint(allocator, "{s}/plugins/zig/{s}/bin/{s}", .{ jn_home, name, name }) catch return null;
        if (std.fs.cwd().access(path, .{})) |_| {
            return path;
        } else |_| {}
    }

    // Try relative to current directory (development mode)
    const dev_path = std.fmt.allocPrint(allocator, "plugins/zig/{s}/bin/{s}", .{ name, name }) catch return null;
    if (std.fs.cwd().access(dev_path, .{})) |_| {
        return dev_path;
    } else |_| {}

    // Try ~/.local/jn/plugins
    if (std.posix.getenv("HOME")) |home| {
        const user_path = std.fmt.allocPrint(allocator, "{s}/.local/jn/plugins/zig/{s}/bin/{s}", .{ home, name, name }) catch return null;
        if (std.fs.cwd().access(user_path, .{})) |_| {
            return user_path;
        } else |_| {}
    }

    return null;
}

/// Pass stdin through to stdout (for JSONL)
fn passthroughStdin() !void {
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;
        writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
        writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
    }

    jn_core.flushWriter(writer);
}

/// Print version
fn printVersion() void {
    var buf: [256]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.print("jn-put {s}\n", .{VERSION}) catch {};
    jn_core.flushWriter(stdout);
}

/// Print usage information
fn printUsage() void {
    const usage =
        \\jn-put - Universal writer for JN
        \\
        \\Usage: jn-put [OPTIONS] <ADDRESS>
        \\
        \\Address formats:
        \\  output.csv            Local file (format auto-detected)
        \\  output.json           JSON array output
        \\  output.txt~csv        Format override
        \\  -                     Write to stdout
        \\
        \\Options:
        \\  --help, -h            Show this help
        \\  --version             Show version
        \\  --delimiter=CHAR      CSV delimiter (passed to plugin)
        \\  --indent=N            JSON indentation (passed to plugin)
        \\
        \\Examples:
        \\  cat data.ndjson | jn-put output.csv
        \\  cat data.ndjson | jn-put output.json
        \\  cat data.ndjson | jn-put output.txt~csv
        \\  cat data.ndjson | jn-put -~json
        \\
    ;
    var buf: [2048]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.writeAll(usage) catch {};
    jn_core.flushWriter(stdout);
}

// Tests
test "parse simple file address" {
    const addr = jn_address.parse("output.csv");
    try std.testing.expectEqual(jn_address.AddressType.file, addr.address_type);
    try std.testing.expectEqualStrings("csv", addr.effectiveFormat().?);
}

test "parse stdout address" {
    const addr = jn_address.parse("-");
    try std.testing.expectEqual(jn_address.AddressType.stdin, addr.address_type);
}

test "parse format override" {
    const addr = jn_address.parse("output.txt~json");
    try std.testing.expectEqual(jn_address.AddressType.file, addr.address_type);
    try std.testing.expectEqualStrings("json", addr.effectiveFormat().?);
}
