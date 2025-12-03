const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");
const jn_plugin = @import("jn-plugin");

const plugin_meta = jn_plugin.PluginMeta{
    .name = "csv",
    .version = "0.2.0",
    .matches = &.{ ".*\\.csv$", ".*\\.tsv$" },
    .role = .format,
    .modes = &.{ .read, .write },
};

const Config = struct {
    delimiter: u8 = ',',
    no_header: bool = false,
};

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const args = jn_cli.parseArgs();
    const mode = args.get("mode", "read") orelse "read";
    const config = parseConfig(args);

    if (args.has("jn-meta")) {
        try jn_plugin.outputManifestToStdout(plugin_meta);
        return;
    }

    if (std.mem.eql(u8, mode, "read")) {
        try readMode(allocator, config);
        return;
    }

    if (std.mem.eql(u8, mode, "write")) {
        try writeMode(allocator, config);
        return;
    }

    jn_core.exitWithError("csv: unknown mode '{s}'", .{mode});
}

fn parseConfig(args: jn_cli.ArgParser) Config {
    var config = Config{};

    if (args.get("delimiter", null)) |delim| {
        config.delimiter = parseDelimiter(delim);
    }

    if (args.has("no-header")) {
        config.no_header = true;
    }

    if (args.get("header", null)) |value| {
        if (std.mem.eql(u8, value, "false")) {
            config.no_header = true;
        }
    }

    return config;
}

fn parseDelimiter(value: []const u8) u8 {
    if (std.mem.eql(u8, value, "tab") or std.mem.eql(u8, value, "\\t")) {
        return '\t';
    }
    if (value.len > 0) return value[0];
    return ',';
}

fn readMode(allocator: std.mem.Allocator, config: Config) !void {
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    var field_starts: [1024]usize = undefined;
    var field_ends: [1024]usize = undefined;

    var headers = std.ArrayListUnmanaged([]const u8){};
    defer {
        for (headers.items) |h| allocator.free(h);
        headers.deinit(allocator);
    }

    if (!config.no_header) {
        const maybe_header = jn_core.readLine(reader);
        if (maybe_header == null) {
            jn_core.flushWriter(writer);
            return;
        }

        const clean_line = jn_core.stripCR(maybe_header.?);
        const field_count = parseCSVRowFast(clean_line, config.delimiter, &field_starts, &field_ends);

        for (0..field_count) |i| {
            const field = unquoteField(clean_line[field_starts[i]..field_ends[i]]);
            const duped = try allocator.dupe(u8, field);
            try headers.append(allocator, duped);
        }
    }

    while (jn_core.readLine(reader)) |line| {
        const clean_line = jn_core.stripCR(line);
        if (clean_line.len == 0) continue;

        const field_count = parseCSVRowFast(clean_line, config.delimiter, &field_starts, &field_ends);

        writer.writeByte('{') catch |err| jn_core.handleWriteError(err);

        if (config.no_header) {
            for (0..field_count) |i| {
                if (i > 0) writer.writeByte(',') catch |err| jn_core.handleWriteError(err);
                writer.print("\"col{d}\":", .{i}) catch |err| jn_core.handleWriteError(err);
                const field = unquoteField(clean_line[field_starts[i]..field_ends[i]]);
                jn_core.writeJsonString(writer, field) catch |err| jn_core.handleWriteError(err);
            }
        } else {
            const num_fields = @min(field_count, headers.items.len);
            for (0..num_fields) |i| {
                if (i > 0) writer.writeByte(',') catch |err| jn_core.handleWriteError(err);
                jn_core.writeJsonString(writer, headers.items[i]) catch |err| jn_core.handleWriteError(err);
                writer.writeByte(':') catch |err| jn_core.handleWriteError(err);
                const field = unquoteField(clean_line[field_starts[i]..field_ends[i]]);
                jn_core.writeJsonString(writer, field) catch |err| jn_core.handleWriteError(err);
            }

            if (field_count > headers.items.len) {
                for (headers.items.len..field_count) |i| {
                    writer.writeByte(',') catch |err| jn_core.handleWriteError(err);
                    writer.print("\"_extra{d}\":", .{i - headers.items.len}) catch |err| jn_core.handleWriteError(err);
                    const field = unquoteField(clean_line[field_starts[i]..field_ends[i]]);
                    jn_core.writeJsonString(writer, field) catch |err| jn_core.handleWriteError(err);
                }
            }
        }

        writer.writeByte('}') catch |err| jn_core.handleWriteError(err);
        writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
    }

    jn_core.flushWriter(writer);
}

fn parseCSVRowFast(line: []const u8, delimiter: u8, starts: *[1024]usize, ends: *[1024]usize) usize {
    var field_count: usize = 0;
    var i: usize = 0;
    var field_start: usize = 0;
    var in_quotes = false;

    while (i < line.len) : (i += 1) {
        const c = line[i];

        if (c == '"') {
            if (in_quotes and i + 1 < line.len and line[i + 1] == '"') {
                i += 1;
                continue;
            }
            in_quotes = !in_quotes;
        } else if (c == delimiter and !in_quotes) {
            if (field_count < 1024) {
                starts[field_count] = field_start;
                ends[field_count] = i;
                field_count += 1;
            }
            field_start = i + 1;
        }
    }

    if (field_count < 1024) {
        starts[field_count] = field_start;
        ends[field_count] = line.len;
        field_count += 1;
    }

    return field_count;
}

fn parseCSVRow(allocator: std.mem.Allocator, line: []const u8, delimiter: u8, fields: *std.ArrayListUnmanaged([]const u8)) !void {
    var i: usize = 0;
    var field_start: usize = 0;
    var in_quotes = false;

    while (i < line.len) {
        const c = line[i];

        if (c == '"') {
            if (in_quotes and i + 1 < line.len and line[i + 1] == '"') {
                i += 2;
                continue;
            }
            in_quotes = !in_quotes;
            i += 1;
        } else if (c == delimiter and !in_quotes) {
            try fields.append(allocator, unquoteField(line[field_start..i]));
            field_start = i + 1;
            i += 1;
        } else {
            i += 1;
        }
    }

    try fields.append(allocator, unquoteField(line[field_start..]));
}

fn unquoteField(field: []const u8) []const u8 {
    if (field.len < 2) return field;
    if (field[0] != '"' or field[field.len - 1] != '"') return field;
    return field[1 .. field.len - 1];
}

fn writeMode(allocator: std.mem.Allocator, config: Config) !void {
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    var lines = std.ArrayListUnmanaged([]const u8){};
    defer {
        for (lines.items) |line| allocator.free(line);
        lines.deinit(allocator);
    }

    var headers_list = std.ArrayListUnmanaged([]const u8){};
    defer {
        for (headers_list.items) |h| allocator.free(h);
        headers_list.deinit(allocator);
    }

    var headers_seen = std.StringHashMap(void).init(allocator);
    defer headers_seen.deinit();

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;

        if (jn_core.parseJsonLine(allocator, line)) |parsed| {
            defer parsed.deinit();
            if (parsed.value == .object) {
                var iter = parsed.value.object.iterator();
                while (iter.next()) |entry| {
                    const key = entry.key_ptr.*;
                    if (!headers_seen.contains(key)) {
                        const duped = try allocator.dupe(u8, key);
                        try headers_list.append(allocator, duped);
                        try headers_seen.put(duped, {});
                    }
                }
            }
        } else {
            continue;
        }

        const duped_line = try allocator.dupe(u8, line);
        try lines.append(allocator, duped_line);
    }

    if (lines.items.len == 0) {
        jn_core.flushWriter(writer);
        return;
    }

    if (!config.no_header) {
        for (headers_list.items, 0..) |header, i| {
            if (i > 0) writer.writeByte(config.delimiter) catch |err| jn_core.handleWriteError(err);
            writeCSVField(writer, header, config.delimiter) catch |err| jn_core.handleWriteError(err);
        }
        writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
    }

    for (lines.items) |line| {
        const parsed = jn_core.parseJsonLine(allocator, line) orelse continue;
        defer parsed.deinit();

        if (parsed.value != .object) continue;

        for (headers_list.items, 0..) |header, i| {
            if (i > 0) writer.writeByte(config.delimiter) catch |err| jn_core.handleWriteError(err);

            if (parsed.value.object.get(header)) |val| {
                writeCSVValue(writer, val, config.delimiter) catch |err| jn_core.handleWriteError(err);
            }
        }
        writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
    }

    jn_core.flushWriter(writer);
}

fn writeCSVField(writer: anytype, field: []const u8, delimiter: u8) !void {
    var needs_quote = false;
    for (field) |c| {
        if (c == delimiter or c == '"' or c == '\n' or c == '\r') {
            needs_quote = true;
            break;
        }
    }

    if (needs_quote) {
        try writer.writeByte('"');
        for (field) |c| {
            if (c == '"') {
                try writer.writeAll("\"\"");
            } else {
                try writer.writeByte(c);
            }
        }
        try writer.writeByte('"');
    } else {
        try writer.writeAll(field);
    }
}

fn writeCSVValue(writer: anytype, value: std.json.Value, delimiter: u8) !void {
    switch (value) {
        .null => {},
        .bool => |b| try writer.writeAll(if (b) "true" else "false"),
        .integer => |i| try writer.print("{d}", .{i}),
        .float => |f| try writer.print("{d}", .{f}),
        .string => |s| try writeCSVField(writer, s, delimiter),
        .array => try writeCSVField(writer, "[array]", delimiter),
        .object => try writeCSVField(writer, "[object]", delimiter),
        .number_string => |s| try writeCSVField(writer, s, delimiter),
    }
}

test "parse simple csv row" {
    const allocator = std.testing.allocator;
    var fields = std.ArrayListUnmanaged([]const u8){};
    defer fields.deinit(allocator);

    try parseCSVRow(allocator, "a,b,c", ',', &fields);
    try std.testing.expectEqual(@as(usize, 3), fields.items.len);
    try std.testing.expectEqualStrings("a", fields.items[0]);
    try std.testing.expectEqualStrings("b", fields.items[1]);
    try std.testing.expectEqualStrings("c", fields.items[2]);
}

test "parse quoted csv row" {
    const allocator = std.testing.allocator;
    var fields = std.ArrayListUnmanaged([]const u8){};
    defer fields.deinit(allocator);

    try parseCSVRow(allocator, "\"hello, world\",b,c", ',', &fields);
    try std.testing.expectEqual(@as(usize, 3), fields.items.len);
    try std.testing.expectEqualStrings("hello, world", fields.items[0]);
}

test "unquote field" {
    try std.testing.expectEqualStrings("hello", unquoteField("\"hello\""));
    try std.testing.expectEqualStrings("world", unquoteField("world"));
}
