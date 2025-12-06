//! jn-sh: Execute shell commands and output NDJSON
//!
//! Executes shell commands and parses output to NDJSON using jc if available.
//!
//! Usage:
//!   jn-sh [OPTIONS] <COMMAND> [ARGS...]
//!
//! Options:
//!   --raw                   Output raw text wrapped in JSON (skip jc parsing)
//!   --help, -h              Show this help
//!   --version               Show version
//!
//! Examples:
//!   jn-sh ls -l /tmp
//!   jn-sh ps aux
//!   jn-sh df -h
//!   jn-sh --raw cat /etc/passwd

const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");

const VERSION = "0.1.0";

/// Cached result for jc availability check
var jc_available: ?bool = null;

/// Check if jc is installed (cached)
fn isJcInstalled() bool {
    if (jc_available) |available| {
        return available;
    }

    // Try to run 'jc --version' to check if it's installed
    const argv: [2][]const u8 = .{ "jc", "--version" };
    var child = std.process.Child.init(&argv, std.heap.page_allocator);
    child.stdin_behavior = .Close;
    child.stdout_behavior = .Close;
    child.stderr_behavior = .Close;

    child.spawn() catch {
        jc_available = false;
        return false;
    };

    const result = child.wait() catch {
        jc_available = false;
        return false;
    };

    jc_available = switch (result) {
        .Exited => |code| code == 0,
        .Signal, .Stopped, .Unknown => false,
    };
    return jc_available.?;
}

// Commands supported by jc with streaming parsers
const STREAMING_COMMANDS = [_][]const u8{
    "ls",
    "ping",
    "traceroute",
    "dig",
    "vmstat",
    "iostat",
    "mpstat",
    "netstat",
};

// Commands supported by jc (batch mode)
const BATCH_COMMANDS = [_][]const u8{
    "arp",
    "blkid",
    "crontab",
    "date",
    "df",
    "dmidecode",
    "dpkg",
    "du",
    "env",
    "file",
    "free",
    "group",
    "gshadow",
    "history",
    "hosts",
    "id",
    "ifconfig",
    "ini",
    "ip",
    "iptables",
    "iw",
    "jobs",
    "last",
    "lsblk",
    "lsmod",
    "lsof",
    "lsusb",
    "mount",
    "passwd",
    "pip",
    "ps",
    "route",
    "rpm",
    "shadow",
    "ss",
    "stat",
    "sysctl",
    "systemctl",
    "timedatectl",
    "top",
    "uname",
    "uptime",
    "w",
    "who",
    "xml",
    "yaml",
};

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

    const raw_mode = args.has("raw");

    // Collect command arguments
    var cmd_parts: std.ArrayListUnmanaged([]const u8) = .empty;
    defer cmd_parts.deinit(allocator);

    var args_iter = std.process.args();
    _ = args_iter.skip(); // Skip program name

    var past_options = false;
    while (args_iter.next()) |arg| {
        // Skip options before command
        if (!past_options and std.mem.startsWith(u8, arg, "-")) {
            if (std.mem.eql(u8, arg, "--")) {
                past_options = true;
            }
            continue;
        }
        past_options = true;
        cmd_parts.append(allocator, arg) catch {
            jn_core.exitWithError("jn-sh: out of memory", .{});
        };
    }

    if (cmd_parts.items.len == 0) {
        jn_core.exitWithError("jn-sh: no command specified\nUsage: jn-sh [OPTIONS] <COMMAND> [ARGS...]", .{});
    }

    const command_name = cmd_parts.items[0];

    // Build command string for shell using fixed buffer
    var cmd_buf: [8192]u8 = undefined;
    var cmd_stream = std.io.fixedBufferStream(&cmd_buf);
    const cmd_writer = cmd_stream.writer();

    for (cmd_parts.items, 0..) |part, i| {
        if (i > 0) cmd_writer.writeByte(' ') catch {};
        // Quote if contains spaces or special chars
        if (needsQuoting(part)) {
            cmd_writer.writeByte('\'') catch {};
            for (part) |c| {
                if (c == '\'') {
                    cmd_writer.writeAll("'\\''") catch {};
                } else {
                    cmd_writer.writeByte(c) catch {};
                }
            }
            cmd_writer.writeByte('\'') catch {};
        } else {
            cmd_writer.writeAll(part) catch {};
        }
    }

    const cmd_str = cmd_stream.getWritten();

    // Check if jc supports this command AND jc is installed
    const jc_supports = !raw_mode and jcSupportsCommand(command_name);
    const use_jc = jc_supports and isJcInstalled();
    const use_streaming = use_jc and isStreamingCommand(command_name) and hasStreamingFlag(cmd_parts.items);

    if (use_jc) {
        executeWithJc(allocator, cmd_str, command_name, use_streaming);
    } else {
        executeRaw(allocator, cmd_str);
    }
}

/// Check if a string needs shell quoting
fn needsQuoting(s: []const u8) bool {
    for (s) |c| {
        switch (c) {
            ' ', '\t', '"', '\'', '\\', '|', '&', ';', '<', '>', '(', ')', '$', '`', '*', '?', '[', ']', '#', '~', '!' => return true,
            else => {},
        }
    }
    return false;
}

/// Check if jc supports the command
fn jcSupportsCommand(command: []const u8) bool {
    // Extract base command (handle paths like /bin/ls)
    const base = if (std.mem.lastIndexOf(u8, command, "/")) |idx| command[idx + 1 ..] else command;

    for (STREAMING_COMMANDS) |cmd| {
        if (std.mem.eql(u8, base, cmd)) return true;
    }
    for (BATCH_COMMANDS) |cmd| {
        if (std.mem.eql(u8, base, cmd)) return true;
    }
    return false;
}

/// Check if command is a streaming parser
fn isStreamingCommand(command: []const u8) bool {
    const base = if (std.mem.lastIndexOf(u8, command, "/")) |idx| command[idx + 1 ..] else command;

    for (STREAMING_COMMANDS) |cmd| {
        if (std.mem.eql(u8, base, cmd)) return true;
    }
    return false;
}

/// Check if ls has -l flag (required for streaming)
fn hasStreamingFlag(parts: []const []const u8) bool {
    if (parts.len == 0) return false;
    const cmd = parts[0];
    const base = if (std.mem.lastIndexOf(u8, cmd, "/")) |idx| cmd[idx + 1 ..] else cmd;

    // ls requires -l for streaming
    if (std.mem.eql(u8, base, "ls")) {
        for (parts[1..]) |arg| {
            if (std.mem.eql(u8, arg, "--")) break;
            if (std.mem.startsWith(u8, arg, "-") and !std.mem.startsWith(u8, arg, "--")) {
                // Check for 'l' in combined flags
                for (arg[1..]) |c| {
                    if (c == 'l') return true;
                }
            }
            if (std.mem.eql(u8, arg, "-l") or std.mem.eql(u8, arg, "--long")) return true;
        }
        return false;
    }

    // Other streaming commands don't need special flags
    return true;
}

/// Execute command with jc parsing
fn executeWithJc(allocator: std.mem.Allocator, cmd_str: []const u8, command: []const u8, streaming: bool) void {
    const base = if (std.mem.lastIndexOf(u8, command, "/")) |idx| command[idx + 1 ..] else command;

    // Build jc flag
    var jc_flag_buf: [64]u8 = undefined;
    const jc_flag = if (streaming)
        std.fmt.bufPrint(&jc_flag_buf, "--{s}-s", .{base}) catch "--raw"
    else
        std.fmt.bufPrint(&jc_flag_buf, "--{s}", .{base}) catch "--raw";

    // Build pipeline: cmd | jc --cmd
    const pipeline = std.fmt.allocPrint(allocator, "{s} | jc {s}", .{ cmd_str, jc_flag }) catch {
        jn_core.exitWithError("jn-sh: out of memory", .{});
    };
    defer allocator.free(pipeline);

    const argv: [3][]const u8 = .{ "/bin/sh", "-c", pipeline };
    var child = std.process.Child.init(&argv, allocator);
    child.stdin_behavior = .Close;
    child.stdout_behavior = .Pipe;
    child.stderr_behavior = .Inherit;

    child.spawn() catch |err| {
        jn_core.exitWithError("jn-sh: failed to execute: {s}", .{@errorName(err)});
    };

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    var pipe_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var pipe_wrapper = child.stdout.?.reader(&pipe_buf);
    const reader = &pipe_wrapper.interface;

    if (streaming) {
        // Streaming mode - jc outputs NDJSON
        while (jn_core.readLine(reader)) |line| {
            if (line.len == 0) continue;
            writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
            writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
        }
    } else {
        // Batch mode - jc outputs JSON array, convert to NDJSON
        var output: std.ArrayListUnmanaged(u8) = .empty;
        defer output.deinit(allocator);

        // Read all output (line by line, concatenate)
        while (jn_core.readLine(reader)) |line| {
            output.appendSlice(allocator, line) catch |err| {
                jn_core.exitWithError("jn-sh: out of memory: {s}", .{@errorName(err)});
            };
            output.append(allocator, '\n') catch |err| {
                jn_core.exitWithError("jn-sh: out of memory: {s}", .{@errorName(err)});
            };
        }

        // Parse JSON array
        if (output.items.len > 0) {
            const parsed = std.json.parseFromSlice(std.json.Value, allocator, output.items, .{}) catch {
                // Not valid JSON - output as raw
                writer.writeAll("{\"output\":") catch |err| jn_core.handleWriteError(err);
                jn_core.writeJsonString(writer, output.items) catch {};
                writer.writeAll("}\n") catch |err| jn_core.handleWriteError(err);
                jn_core.flushWriter(writer);
                _ = child.wait() catch {};
                return;
            };
            defer parsed.deinit();

            if (parsed.value == .array) {
                // Output each element as NDJSON
                for (parsed.value.array.items) |item| {
                    jn_core.writeJsonValue(writer, item) catch {};
                    writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
                }
            } else {
                // Single object
                jn_core.writeJsonValue(writer, parsed.value) catch {};
                writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
            }
        }
    }

    jn_core.flushWriter(writer);

    const result = child.wait() catch |err| {
        jn_core.exitWithError("jn-sh: wait failed: {s}", .{@errorName(err)});
    };

    // Properly handle all termination types to avoid undefined behavior
    switch (result) {
        .Exited => |code| {
            if (code != 0) std.process.exit(code);
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

/// Execute command in raw mode (wrap output in JSON)
fn executeRaw(allocator: std.mem.Allocator, cmd_str: []const u8) void {
    const argv: [3][]const u8 = .{ "/bin/sh", "-c", cmd_str };
    var child = std.process.Child.init(&argv, allocator);
    child.stdin_behavior = .Close;
    child.stdout_behavior = .Pipe;
    child.stderr_behavior = .Inherit;

    child.spawn() catch |err| {
        jn_core.exitWithError("jn-sh: failed to execute: {s}", .{@errorName(err)});
    };

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    // Read output line by line, wrap each in JSON
    var pipe_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var pipe_wrapper = child.stdout.?.reader(&pipe_buf);
    const reader = &pipe_wrapper.interface;

    var line_num: usize = 0;

    while (jn_core.readLine(reader)) |line| {
        line_num += 1;
        writer.writeAll("{\"line\":") catch |err| jn_core.handleWriteError(err);
        writer.print("{d}", .{line_num}) catch |err| jn_core.handleWriteError(err);
        writer.writeAll(",\"text\":") catch |err| jn_core.handleWriteError(err);
        jn_core.writeJsonString(writer, line) catch {};
        writer.writeAll("}\n") catch |err| jn_core.handleWriteError(err);
    }

    jn_core.flushWriter(writer);

    const result = child.wait() catch |err| {
        jn_core.exitWithError("jn-sh: wait failed: {s}", .{@errorName(err)});
    };

    // Properly handle all termination types to avoid undefined behavior
    switch (result) {
        .Exited => |code| {
            if (code != 0) std.process.exit(code);
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

/// Print version
fn printVersion() void {
    var buf: [256]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.print("jn-sh {s}\n", .{VERSION}) catch {};
    jn_core.flushWriter(stdout);
}

/// Print usage information
fn printUsage() void {
    const usage =
        \\jn-sh - Execute shell commands and output NDJSON
        \\
        \\Usage: jn-sh [OPTIONS] <COMMAND> [ARGS...]
        \\
        \\Executes shell commands and parses output to NDJSON using jc if available.
        \\If jc doesn't support the command, wraps output as raw text in JSON.
        \\
        \\Options:
        \\  --raw                 Output raw text wrapped in JSON (skip jc parsing)
        \\  --help, -h            Show this help
        \\  --version             Show version
        \\
        \\Supported commands (via jc):
        \\  ls, ps, df, du, mount, env, id, who, w, last, top, uptime, uname
        \\  ifconfig, ip, netstat, ss, arp, route, iptables, dig, ping
        \\  dpkg, rpm, pip, lsblk, lsmod, lsof, lsusb, blkid, dmidecode
        \\  crontab, systemctl, timedatectl, sysctl, free, vmstat, iostat
        \\  stat, file, history, jobs, passwd, group, shadow, hosts, ini, xml, yaml
        \\
        \\Examples:
        \\  # List files as JSON
        \\  jn-sh ls -l /tmp
        \\
        \\  # Process list
        \\  jn-sh ps aux
        \\
        \\  # Disk usage
        \\  jn-sh df -h
        \\
        \\  # Raw mode (wrap output as text)
        \\  jn-sh --raw cat /etc/passwd
        \\
        \\Note: Requires 'jc' (https://github.com/kellyjonbrazil/jc) for parsing.
        \\Without jc, commands run in raw mode automatically.
        \\
    ;
    var buf: [4096]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.writeAll(usage) catch {};
    jn_core.flushWriter(stdout);
}

// Tests
test "needs quoting" {
    try std.testing.expect(needsQuoting("hello world"));
    try std.testing.expect(needsQuoting("foo|bar"));
    try std.testing.expect(needsQuoting("test$var"));
    try std.testing.expect(!needsQuoting("simple"));
    try std.testing.expect(!needsQuoting("file.txt"));
}

test "jc supports command" {
    try std.testing.expect(jcSupportsCommand("ls"));
    try std.testing.expect(jcSupportsCommand("ps"));
    try std.testing.expect(jcSupportsCommand("df"));
    try std.testing.expect(!jcSupportsCommand("unknown"));
}

test "is streaming command" {
    try std.testing.expect(isStreamingCommand("ls"));
    try std.testing.expect(isStreamingCommand("ping"));
    try std.testing.expect(!isStreamingCommand("ps"));
    try std.testing.expect(!isStreamingCommand("df"));
}
