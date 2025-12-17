//! jn-merge: Concatenate multiple NDJSON sources
//!
//! Combines multiple sources into a single stream, adding source metadata.
//!
//! Usage:
//!   jn-merge [OPTIONS] <SOURCE1> [SOURCE2] ...
//!
//! Options:
//!   --no-source             Don't add _source field
//!   --fail-fast             Stop on first source error (default: continue)
//!   --help, -h              Show this help
//!   --version               Show version
//!
//! Source format:
//!   path                    Simple path (uses filename as source)
//!   path:label=NAME         Custom label for source
//!
//! Examples:
//!   jn-merge data1.csv data2.csv data3.csv
//!   jn-merge "jan.csv:label=January" "feb.csv:label=February"
//!   jn-merge --no-source file1.ndjson file2.ndjson

const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");
const jn_address = @import("jn-address");

const VERSION = "0.1.0";

// Source configuration
const SourceSpec = struct {
    path: []const u8,
    label: ?[]const u8 = null,

    fn parse(spec: []const u8) SourceSpec {
        // Check for :label= suffix
        if (std.mem.indexOf(u8, spec, ":label=")) |idx| {
            return .{
                .path = spec[0..idx],
                .label = spec[idx + 7 ..],
            };
        }
        return .{ .path = spec };
    }

    fn getSourceName(self: SourceSpec) []const u8 {
        return self.label orelse self.path;
    }
};

// Configuration
const MergeConfig = struct {
    add_source: bool = true,
    fail_fast: bool = false,
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

    // Parse configuration
    const config = MergeConfig{
        .add_source = !args.has("no-source"),
        .fail_fast = args.has("fail-fast"),
    };

    // Collect source arguments
    var sources: std.ArrayListUnmanaged(SourceSpec) = .empty;
    defer sources.deinit(allocator);

    var args_iter = std.process.args();
    _ = args_iter.skip(); // Skip program name

    while (args_iter.next()) |arg| {
        // Skip options
        if (std.mem.startsWith(u8, arg, "-")) continue;

        sources.append(allocator, SourceSpec.parse(arg)) catch {
            jn_core.exitWithError("jn-merge: out of memory", .{});
        };
    }

    if (sources.items.len == 0) {
        jn_core.exitWithError("jn-merge: no sources specified\nUsage: jn-merge [OPTIONS] <SOURCE1> [SOURCE2] ...", .{});
    }

    // Process each source
    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    var had_errors = false;

    for (sources.items) |source| {
        const success = processSource(allocator, source, &config, writer);
        if (!success) {
            had_errors = true;
            if (config.fail_fast) {
                std.process.exit(1);
            }
        }
    }

    jn_core.flushWriter(writer);

    if (had_errors) {
        std.process.exit(1);
    }
}

/// Process a single source and output records
fn processSource(allocator: std.mem.Allocator, source: SourceSpec, config: *const MergeConfig, writer: anytype) bool {
    const address = jn_address.parse(source.path);

    switch (address.address_type) {
        .file => {
            return processFile(allocator, source, config, writer);
        },
        .stdin => {
            return processStdin(source, config, writer);
        },
        else => {
            // For URLs and profiles, try using jn-cat
            return processViaJnCat(allocator, source, config, writer);
        },
    }
}

/// Process local file
fn processFile(allocator: std.mem.Allocator, source: SourceSpec, config: *const MergeConfig, writer: anytype) bool {
    const format = jn_address.parse(source.path).effectiveFormat() orelse "jsonl";

    // For non-JSONL files, use jn-cat for conversion
    if (!std.mem.eql(u8, format, "jsonl") and !std.mem.eql(u8, format, "ndjson") and !std.mem.eql(u8, format, "json")) {
        return processViaJnCat(allocator, source, config, writer);
    }

    // Direct NDJSON reading
    const file = std.fs.cwd().openFile(source.path, .{}) catch |err| {
        var stderr_buf: [256]u8 = undefined;
        var stderr_wrapper = std.fs.File.stderr().writerStreaming(&stderr_buf);
        const stderr = &stderr_wrapper.interface;
        stderr.print("jn-merge: cannot open '{s}': {s}\n", .{ source.path, @errorName(err) }) catch {};
        jn_core.flushWriter(stderr);
        return false;
    };
    defer file.close();

    var file_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var file_wrapper = file.reader(&file_buf);
    const reader = &file_wrapper.interface;

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;
        outputRecord(allocator, line, source, config, writer);
    }

    return true;
}

/// Process stdin
fn processStdin(source: SourceSpec, config: *const MergeConfig, writer: anytype) bool {
    // Need heap allocator for output
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;
        outputRecord(allocator, line, source, config, writer);
    }

    return true;
}

/// Process via jn-cat for format conversion or remote sources
fn processViaJnCat(allocator: std.mem.Allocator, source: SourceSpec, config: *const MergeConfig, writer: anytype) bool {
    // Find jn-cat
    const jn_cat_path = findTool(allocator, "jn-cat") orelse {
        var stderr_buf: [256]u8 = undefined;
        var stderr_wrapper = std.fs.File.stderr().writerStreaming(&stderr_buf);
        const stderr = &stderr_wrapper.interface;
        stderr.print("jn-merge: jn-cat not found (required for '{s}')\n", .{source.path}) catch {};
        jn_core.flushWriter(stderr);
        return false;
    };

    const shell_cmd = std.fmt.allocPrint(allocator, "{s} '{s}'", .{ jn_cat_path, source.path }) catch return false;
    defer allocator.free(shell_cmd);

    const argv: [3][]const u8 = .{ "/bin/sh", "-c", shell_cmd };
    var child = std.process.Child.init(&argv, allocator);
    child.stdin_behavior = .Close;
    child.stdout_behavior = .Pipe;
    child.stderr_behavior = .Inherit;

    child.spawn() catch |err| {
        var stderr_buf: [256]u8 = undefined;
        var stderr_wrapper = std.fs.File.stderr().writerStreaming(&stderr_buf);
        const stderr = &stderr_wrapper.interface;
        stderr.print("jn-merge: failed to spawn jn-cat for '{s}': {s}\n", .{ source.path, @errorName(err) }) catch {};
        jn_core.flushWriter(stderr);
        return false;
    };

    // Read output
    var pipe_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var pipe_wrapper = child.stdout.?.reader(&pipe_buf);
    const reader = &pipe_wrapper.interface;

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;
        outputRecord(allocator, line, source, config, writer);
    }

    const result = child.wait() catch return false;
    return switch (result) {
        .Exited => |code| code == 0,
        .Signal, .Stopped, .Unknown => false,
    };
}

/// Output a record with optional source metadata
fn outputRecord(allocator: std.mem.Allocator, line: []const u8, source: SourceSpec, config: *const MergeConfig, writer: anytype) void {
    if (!config.add_source) {
        // Pass through unchanged
        writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
        writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
        return;
    }

    // Parse and add source fields
    const parsed = std.json.parseFromSlice(std.json.Value, allocator, line, .{}) catch {
        // Invalid JSON - pass through
        writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
        writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
        return;
    };
    defer parsed.deinit();

    if (parsed.value != .object) {
        // Not an object - pass through
        writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
        writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
        return;
    }

    // Build output with _source first using fixed buffer
    var out_buf: [64 * 1024]u8 = undefined;
    var stream = std.io.fixedBufferStream(&out_buf);
    const w = stream.writer();

    w.writeAll("{\"_source\":") catch return;
    jn_core.writeJsonString(w, source.path) catch return;

    // Add _label if present
    if (source.label) |label| {
        w.writeAll(",\"_label\":") catch return;
        jn_core.writeJsonString(w, label) catch return;
    }

    // Copy original fields
    var it = parsed.value.object.iterator();
    while (it.next()) |entry| {
        w.writeByte(',') catch return;
        jn_core.writeJsonString(w, entry.key_ptr.*) catch return;
        w.writeByte(':') catch return;
        jn_core.writeJsonValue(w, entry.value_ptr.*) catch return;
    }

    w.writeByte('}') catch return;

    writer.writeAll(stream.getWritten()) catch |err| jn_core.handleWriteError(err);
    writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
}

/// Find a tool by name
fn findTool(allocator: std.mem.Allocator, name: []const u8) ?[]const u8 {
    // Try paths relative to JN_HOME
    if (std.posix.getenv("JN_HOME")) |jn_home| {
        // Try installed layout: $JN_HOME/bin/{name}
        const bin_path = std.fmt.allocPrint(allocator, "{s}/bin/{s}", .{ jn_home, name }) catch return null;
        if (std.fs.cwd().access(bin_path, .{})) |_| {
            return bin_path;
        } else |_| {
            allocator.free(bin_path);
        }

        // Try development layout: $JN_HOME/tools/zig/{name}/bin/{name}
        const path = std.fmt.allocPrint(allocator, "{s}/tools/zig/{s}/bin/{s}", .{ jn_home, name, name }) catch return null;
        if (std.fs.cwd().access(path, .{})) |_| {
            return path;
        } else |_| {
            allocator.free(path);
        }
    }

    // Try sibling to executable (installed layout: tools in same directory)
    var exe_path_buf: [std.fs.max_path_bytes]u8 = undefined;
    if (std.fs.selfExePath(&exe_path_buf)) |exe_path| {
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

    return null;
}

/// Print version
fn printVersion() void {
    var buf: [256]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.print("jn-merge {s}\n", .{VERSION}) catch {};
    jn_core.flushWriter(stdout);
}

/// Print usage information
fn printUsage() void {
    const usage =
        \\jn-merge - Concatenate multiple NDJSON sources
        \\
        \\Usage: jn-merge [OPTIONS] <SOURCE1> [SOURCE2] ...
        \\
        \\Combines multiple sources into a single NDJSON stream.
        \\Sources are processed sequentially, maintaining order.
        \\
        \\Options:
        \\  --no-source           Don't add _source field to records
        \\  --fail-fast           Stop on first source error (default: continue)
        \\  --help, -h            Show this help
        \\  --version             Show version
        \\
        \\Source format:
        \\  path                  Simple path (uses filename as _source)
        \\  path:label=NAME       Custom label (_label field added)
        \\
        \\Output fields:
        \\  _source               Path of the source file
        \\  _label                Custom label (if :label= specified)
        \\
        \\Examples:
        \\  # Merge multiple files
        \\  jn-merge data1.csv data2.csv data3.csv
        \\
        \\  # With custom labels
        \\  jn-merge "jan.csv:label=January" "feb.csv:label=February" "mar.csv:label=March"
        \\
        \\  # Merge without source metadata
        \\  jn-merge --no-source file1.ndjson file2.ndjson
        \\
        \\  # Stop on first error
        \\  jn-merge --fail-fast file1.csv file2.csv
        \\
        \\Memory: Each source streams through, using constant memory.
        \\
    ;
    var buf: [4096]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.writeAll(usage) catch {};
    jn_core.flushWriter(stdout);
}

// Tests
test "source spec parse simple" {
    const spec = SourceSpec.parse("data.csv");
    try std.testing.expectEqualStrings("data.csv", spec.path);
    try std.testing.expect(spec.label == null);
}

test "source spec parse with label" {
    const spec = SourceSpec.parse("data.csv:label=January");
    try std.testing.expectEqualStrings("data.csv", spec.path);
    try std.testing.expectEqualStrings("January", spec.label.?);
}

test "source spec get name" {
    const spec1 = SourceSpec.parse("data.csv");
    try std.testing.expectEqualStrings("data.csv", spec1.getSourceName());

    const spec2 = SourceSpec.parse("data.csv:label=Custom");
    try std.testing.expectEqualStrings("Custom", spec2.getSourceName());
}

test "config defaults" {
    const config = MergeConfig{};
    try std.testing.expect(config.add_source == true);
    try std.testing.expect(config.fail_fast == false);
}
