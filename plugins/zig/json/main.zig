const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");
const jn_plugin = @import("jn-plugin");

const plugin_meta = jn_plugin.PluginMeta{
    .name = "json",
    .version = "0.2.0",
    .matches = &.{".*\\.json$"},
    .role = .format,
    .modes = &.{ .read, .write },
};

/// Maximum input size (100MB default). Can be overridden with --max-size=N
/// This prevents OOM on extremely large files.
const DEFAULT_MAX_INPUT_SIZE: usize = 100 * 1024 * 1024;

const WriteFormat = enum { array, ndjson, object };

const WriteConfig = struct {
    format: WriteFormat = .array,
    indent: ?u8 = null,
};

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const args = jn_cli.parseArgs();
    const mode = args.get("mode", "read") orelse "read";

    if (args.has("jn-meta")) {
        try jn_plugin.outputManifestToStdout(plugin_meta);
        return;
    }

    if (std.mem.eql(u8, mode, "read")) {
        try readMode(allocator);
        return;
    }

    if (std.mem.eql(u8, mode, "write")) {
        const config = parseWriteConfig(args);
        try writeMode(config, allocator);
        return;
    }

    jn_core.exitWithError("json: unknown mode '{s}'", .{mode});
}

fn parseWriteConfig(args: jn_cli.ArgParser) WriteConfig {
    var config = WriteConfig{};

    if (args.get("format", null)) |fmt| {
        config.format = parseFormat(fmt) catch
            jn_core.exitWithError("json: unknown format '{s}'", .{fmt});
    }

    if (args.get("indent", null)) |value| {
        config.indent = parseIndent(value);
    }

    return config;
}

fn parseFormat(value: []const u8) !WriteFormat {
    if (std.mem.eql(u8, value, "array")) return .array;
    if (std.mem.eql(u8, value, "ndjson")) return .ndjson;
    if (std.mem.eql(u8, value, "object")) return .object;
    return error.UnknownFormat;
}

fn parseIndent(value: []const u8) u8 {
    return std.fmt.parseInt(u8, value, 10) catch
        jn_core.exitWithError("json: invalid indent '{s}'", .{value});
}

fn readMode(allocator: std.mem.Allocator) !void {
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    var input = std.ArrayList(u8){};
    defer input.deinit(allocator);

    while (jn_core.readLine(reader)) |line| {
        // Check size limit to prevent OOM on maliciously large input
        if (input.items.len + line.len > DEFAULT_MAX_INPUT_SIZE) {
            jn_core.exitWithError("json: input exceeds maximum size of {d}MB", .{DEFAULT_MAX_INPUT_SIZE / (1024 * 1024)});
        }
        try input.appendSlice(allocator, line);
        try input.append(allocator, '\n');
    }

    if (input.items.len == 0) {
        jn_core.flushWriter(writer);
        return;
    }

    const parsed = std.json.parseFromSlice(std.json.Value, allocator, input.items, .{}) catch |err| {
        jn_core.exitWithError("json: parse error: {}", .{err});
    };
    defer parsed.deinit();

    switch (parsed.value) {
        .array => |arr| {
            for (arr.items) |item| {
                jn_core.writeJsonLine(writer, item) catch |err|
                    jn_core.handleWriteError(err);
            }
        },
        else => {
            jn_core.writeJsonLine(writer, parsed.value) catch |err|
                jn_core.handleWriteError(err);
        },
    }

    jn_core.flushWriter(writer);
}

fn writeMode(config: WriteConfig, allocator: std.mem.Allocator) !void {
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    switch (config.format) {
        .ndjson => try streamNdjson(reader, writer),
        .array => try writeArray(reader, writer, config.indent),
        .object => try writeSingleObject(reader, writer, allocator),
    }

    jn_core.flushWriter(writer);
}

fn streamNdjson(reader: anytype, writer: anytype) !void {
    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;
        writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
        writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
    }
}

fn writeArray(reader: anytype, writer: anytype, indent: ?u8) !void {
    const pretty = indent != null;
    const indent_spaces = indent orelse 0;

    writer.writeByte('[') catch |err| jn_core.handleWriteError(err);

    var first = true;
    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;

        if (!first) {
            writer.writeByte(',') catch |err| jn_core.handleWriteError(err);
        }
        if (pretty) {
            writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
            try writeIndent(writer, indent_spaces);
        }

        writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
        first = false;
    }

    if (pretty and !first) {
        writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
    }

    writer.writeByte(']') catch |err| jn_core.handleWriteError(err);
    writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
}

fn writeSingleObject(reader: anytype, writer: anytype, allocator: std.mem.Allocator) !void {
    var first = std.ArrayList(u8){};
    defer first.deinit(allocator);
    var has_value = false;

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;
        if (!has_value) {
            try first.appendSlice(allocator, line);
            has_value = true;
        } else {
            jn_core.exitWithError("json: multiple records cannot be written as a single object", .{});
        }
    }

    if (!has_value) {
        writer.writeAll("{}\n") catch |err| jn_core.handleWriteError(err);
        return;
    }

    writer.writeAll(first.items) catch |err| jn_core.handleWriteError(err);
    writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
}

fn writeIndent(writer: anytype, spaces: u8) !void {
    var i: u8 = 0;
    while (i < spaces) : (i += 1) {
        writer.writeByte(' ') catch |err| jn_core.handleWriteError(err);
    }
}

test "manifest output contains json name" {
    var buf: [256]u8 = undefined;
    var fbs = std.io.fixedBufferStream(&buf);
    try jn_plugin.outputManifest(fbs.writer(), plugin_meta);
    try std.testing.expect(std.mem.indexOf(u8, fbs.getWritten(), "\"json\"") != null);
}
