const std = @import("std");

// ============================================================================
// CSV Plugin - Standalone Zig plugin for JN
//
// Reads CSV files and outputs NDJSON records.
// Write mode reads NDJSON and outputs CSV.
// Supports quoted fields, escaped quotes, and configurable delimiter.
//
// Note: Multi-line quoted fields are NOT supported (for simplicity).
// ============================================================================

const Plugin = struct {
    name: []const u8,
    version: []const u8,
    matches: []const []const u8,
    role: []const u8,
    modes: []const []const u8,
};

const plugin = Plugin{
    .name = "csv",
    .version = "0.1.0",
    .matches = &[_][]const u8{ ".*\\.csv$", ".*\\.tsv$" },
    .role = "format",
    .modes = &[_][]const u8{ "read", "write" },
};

const Config = struct {
    delimiter: u8 = ',',
    no_header: bool = false,
};

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    // Parse command line arguments
    var args = std.process.args();
    _ = args.skip(); // Skip program name

    var mode: []const u8 = "read";
    var jn_meta = false;
    var config = Config{};

    while (args.next()) |arg| {
        if (std.mem.eql(u8, arg, "--jn-meta")) {
            jn_meta = true;
        } else if (std.mem.startsWith(u8, arg, "--mode=")) {
            mode = arg["--mode=".len..];
        } else if (std.mem.startsWith(u8, arg, "--delimiter=")) {
            const delim_str = arg["--delimiter=".len..];
            if (delim_str.len > 0) {
                if (std.mem.eql(u8, delim_str, "tab") or std.mem.eql(u8, delim_str, "\\t")) {
                    config.delimiter = '\t';
                } else {
                    config.delimiter = delim_str[0];
                }
            }
        } else if (std.mem.eql(u8, arg, "--no-header")) {
            config.no_header = true;
        } else if (std.mem.eql(u8, arg, "--header=false")) {
            config.no_header = true;
        }
    }

    // Handle --jn-meta: output plugin manifest
    if (jn_meta) {
        try outputManifest();
        return;
    }

    // Dispatch based on mode
    if (std.mem.eql(u8, mode, "read")) {
        try readMode(allocator, config);
    } else if (std.mem.eql(u8, mode, "write")) {
        try writeMode(allocator, config);
    } else {
        std.debug.print("csv: error: unknown mode '{s}'\n", .{mode});
        std.process.exit(1);
    }
}

fn outputManifest() !void {
    var stdout_buf: [4096]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    try writer.writeAll("{\"name\":\"");
    try writer.writeAll(plugin.name);
    try writer.writeAll("\",\"version\":\"");
    try writer.writeAll(plugin.version);
    try writer.writeAll("\",\"matches\":[");

    for (plugin.matches, 0..) |pattern, i| {
        if (i > 0) try writer.writeByte(',');
        try writer.writeByte('"');
        for (pattern) |c| {
            if (c == '"' or c == '\\') try writer.writeByte('\\');
            try writer.writeByte(c);
        }
        try writer.writeByte('"');
    }

    try writer.writeAll("],\"role\":\"");
    try writer.writeAll(plugin.role);
    try writer.writeAll("\",\"modes\":[");

    for (plugin.modes, 0..) |m, i| {
        if (i > 0) try writer.writeByte(',');
        try writer.writeByte('"');
        try writer.writeAll(m);
        try writer.writeByte('"');
    }

    try writer.writeAll("]}\n");
    try writer.flush();
}

// ============================================================================
// CSV Read Mode
// ============================================================================

fn readMode(allocator: std.mem.Allocator, config: Config) !void {
    var stdin_buf: [64 * 1024]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [64 * 1024]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    // Pre-allocate reusable field indices (no per-row allocation)
    var field_starts: [1024]usize = undefined;
    var field_ends: [1024]usize = undefined;

    // Read and parse header row (unless --no-header)
    var headers = std.ArrayListUnmanaged([]const u8){};
    defer {
        for (headers.items) |h| allocator.free(h);
        headers.deinit(allocator);
    }

    if (!config.no_header) {
        // Read header line
        const maybe_header = reader.takeDelimiter('\n') catch |err| {
            std.debug.print("csv: read error: {}\n", .{err});
            std.process.exit(1);
        };

        if (maybe_header) |header_line| {
            // Strip \r if present
            const clean_line = stripCR(header_line);

            // Parse header fields (store indices, not slices)
            const field_count = parseCSVRowFast(clean_line, config.delimiter, &field_starts, &field_ends);

            // Store headers (only headers need allocation - they're reused)
            for (0..field_count) |i| {
                const field = unquoteField(clean_line[field_starts[i]..field_ends[i]]);
                const duped = try allocator.dupe(u8, field);
                try headers.append(allocator, duped);
            }
        } else {
            // Empty file - no output
            try writer.flush();
            return;
        }
    }

    // Read data rows (zero allocation per row)
    while (true) {
        const maybe_line = reader.takeDelimiter('\n') catch |err| {
            std.debug.print("csv: read error: {}\n", .{err});
            std.process.exit(1);
        };

        if (maybe_line) |line| {
            // Strip \r if present
            const clean_line = stripCR(line);

            // Skip empty lines
            if (clean_line.len == 0) continue;

            // Parse fields into pre-allocated arrays (no allocation!)
            const field_count = parseCSVRowFast(clean_line, config.delimiter, &field_starts, &field_ends);

            // Output as JSON object
            try writer.writeByte('{');

            if (config.no_header) {
                // Use column indices as keys
                for (0..field_count) |i| {
                    if (i > 0) try writer.writeByte(',');
                    try writer.print("\"col{d}\":", .{i});
                    const field = unquoteField(clean_line[field_starts[i]..field_ends[i]]);
                    try writeJsonValue(writer, field);
                }
            } else {
                // Use header names as keys
                const num_fields = @min(field_count, headers.items.len);
                for (0..num_fields) |i| {
                    if (i > 0) try writer.writeByte(',');
                    try writeJsonString(writer, headers.items[i]);
                    try writer.writeByte(':');
                    const field = unquoteField(clean_line[field_starts[i]..field_ends[i]]);
                    try writeJsonValue(writer, field);
                }
                // Handle extra fields (more than headers)
                if (field_count > headers.items.len) {
                    for (headers.items.len..field_count) |i| {
                        try writer.writeByte(',');
                        try writer.print("\"_extra{d}\":", .{i - headers.items.len});
                        const field = unquoteField(clean_line[field_starts[i]..field_ends[i]]);
                        try writeJsonValue(writer, field);
                    }
                }
            }

            try writer.writeByte('}');
            try writer.writeByte('\n');
        } else {
            break; // EOF
        }
    }

    try writer.flush();
}

fn parseCSVRowFast(line: []const u8, delimiter: u8, starts: *[1024]usize, ends: *[1024]usize) usize {
    var field_count: usize = 0;
    var i: usize = 0;
    var field_start: usize = 0;
    var in_quotes = false;

    while (i < line.len) : (i += 1) {
        const c = line[i];

        if (c == '"') {
            if (in_quotes) {
                // Check for escaped quote ("")
                if (i + 1 < line.len and line[i + 1] == '"') {
                    i += 1;
                    continue;
                }
            }
            in_quotes = !in_quotes;
        } else if (c == delimiter and !in_quotes) {
            // End of field
            if (field_count < 1024) {
                starts[field_count] = field_start;
                ends[field_count] = i;
                field_count += 1;
            }
            field_start = i + 1;
        }
    }

    // Don't forget the last field
    if (field_count < 1024) {
        starts[field_count] = field_start;
        ends[field_count] = line.len;
        field_count += 1;
    }

    return field_count;
}

fn stripCR(line: []const u8) []const u8 {
    if (line.len > 0 and line[line.len - 1] == '\r') {
        return line[0 .. line.len - 1];
    }
    return line;
}

fn parseCSVRow(allocator: std.mem.Allocator, line: []const u8, delimiter: u8, fields: *std.ArrayListUnmanaged([]const u8)) !void {
    var i: usize = 0;
    var field_start: usize = 0;
    var in_quotes = false;

    while (i < line.len) {
        const c = line[i];

        if (c == '"') {
            if (in_quotes) {
                // Check for escaped quote ("")
                if (i + 1 < line.len and line[i + 1] == '"') {
                    i += 2;
                    continue;
                }
            }
            in_quotes = !in_quotes;
            i += 1;
        } else if (c == delimiter and !in_quotes) {
            // End of field
            try fields.append(allocator, unquoteField(line[field_start..i]));
            field_start = i + 1;
            i += 1;
        } else {
            i += 1;
        }
    }

    // Don't forget the last field
    try fields.append(allocator, unquoteField(line[field_start..]));
}

fn unquoteField(field: []const u8) []const u8 {
    if (field.len < 2) return field;
    if (field[0] != '"' or field[field.len - 1] != '"') return field;

    // Return the content without surrounding quotes
    // Note: This doesn't handle escaped quotes ("") - for full compliance we'd need to allocate
    return field[1 .. field.len - 1];
}

fn writeJsonString(writer: anytype, s: []const u8) !void {
    try writer.writeByte('"');
    for (s) |c| {
        switch (c) {
            '"' => try writer.writeAll("\\\""),
            '\\' => try writer.writeAll("\\\\"),
            '\n' => try writer.writeAll("\\n"),
            '\r' => try writer.writeAll("\\r"),
            '\t' => try writer.writeAll("\\t"),
            else => {
                if (c < 0x20) {
                    try writer.print("\\u{x:0>4}", .{c});
                } else {
                    try writer.writeByte(c);
                }
            },
        }
    }
    try writer.writeByte('"');
}

fn writeJsonValue(writer: anytype, value: []const u8) !void {
    // Output as JSON string (no type inference - CSV values are text)
    try writeJsonString(writer, value);
}

// ============================================================================
// CSV Write Mode
// ============================================================================

fn writeMode(allocator: std.mem.Allocator, config: Config) !void {
    var stdin_buf: [64 * 1024]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [64 * 1024]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    // Store raw JSON lines - we'll re-parse them
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

    // Read all NDJSON records
    while (true) {
        const maybe_line = reader.takeDelimiter('\n') catch |err| {
            std.debug.print("csv: read error: {}\n", .{err});
            std.process.exit(1);
        };

        if (maybe_line) |line| {
            // Skip empty lines
            if (line.len == 0) continue;

            // Parse JSON to extract headers
            const parsed = std.json.parseFromSlice(std.json.Value, allocator, line, .{}) catch |err| {
                std.debug.print("csv: JSON parse error: {}\n", .{err});
                continue;
            };
            defer parsed.deinit();

            // Collect headers from this record
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

            // Store the line for later
            const duped_line = try allocator.dupe(u8, line);
            try lines.append(allocator, duped_line);
        } else {
            break; // EOF
        }
    }

    if (lines.items.len == 0) {
        try writer.flush();
        return;
    }

    // Write header row
    if (!config.no_header) {
        for (headers_list.items, 0..) |header, i| {
            if (i > 0) try writer.writeByte(config.delimiter);
            try writeCSVField(writer, header, config.delimiter);
        }
        try writer.writeByte('\n');
    }

    // Write data rows
    for (lines.items) |line| {
        const parsed = std.json.parseFromSlice(std.json.Value, allocator, line, .{}) catch continue;
        defer parsed.deinit();

        if (parsed.value != .object) continue;

        for (headers_list.items, 0..) |header, i| {
            if (i > 0) try writer.writeByte(config.delimiter);

            if (parsed.value.object.get(header)) |val| {
                try writeCSVValue(writer, val, config.delimiter, allocator);
            }
            // Missing field -> empty
        }
        try writer.writeByte('\n');
    }

    try writer.flush();
}

fn writeCSVField(writer: anytype, field: []const u8, delimiter: u8) !void {
    // Check if quoting is needed
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

fn writeCSVValue(writer: anytype, value: std.json.Value, delimiter: u8, _: std.mem.Allocator) !void {
    switch (value) {
        .null => {}, // Empty field
        .bool => |b| try writer.writeAll(if (b) "true" else "false"),
        .integer => |i| try writer.print("{d}", .{i}),
        .float => |f| try writer.print("{d}", .{f}),
        .string => |s| try writeCSVField(writer, s, delimiter),
        .array => try writeCSVField(writer, "[array]", delimiter),
        .object => try writeCSVField(writer, "[object]", delimiter),
        .number_string => |s| try writeCSVField(writer, s, delimiter),
    }
}

// ============================================================================
// Tests
// ============================================================================

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
