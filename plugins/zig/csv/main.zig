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
    auto_detect: bool = false,
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
        if (std.mem.eql(u8, delim, "auto")) {
            config.auto_detect = true;
        } else {
            config.delimiter = parseDelimiter(delim);
        }
    } else {
        // Default to auto-detect when no delimiter specified
        config.auto_detect = true;
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

/// Delimiter detection result
const DetectionResult = struct {
    delimiter: u8,
    has_evidence: bool,
};

/// Candidate delimiters to try (comma, semicolon, tab, pipe)
const DELIMITER_CANDIDATES = [_]u8{ ',', ';', '\t', '|' };
const SAMPLE_SIZE: usize = 50;

/// Auto-detect delimiter using heuristic scoring.
///
/// Algorithm:
/// - For each candidate delimiter, count columns per line
/// - Score based on consistency (low variance) and few empty fields
/// - Pick delimiter with highest score
fn detectDelimiter(sample_lines: []const []const u8) DetectionResult {
    if (sample_lines.len == 0) {
        return .{ .delimiter = ',', .has_evidence = false };
    }

    var best_delim: u8 = ',';
    var best_score: f64 = -std.math.inf(f64);
    var found = false;

    for (DELIMITER_CANDIDATES) |delim| {
        var col_counts: [SAMPLE_SIZE]usize = undefined;
        var count_idx: usize = 0;
        var empty_fields: usize = 0;
        var total_fields: usize = 0;

        for (sample_lines) |line| {
            // Quick check: does delimiter appear in line?
            var has_delim = false;
            for (line) |c| {
                if (c == delim) {
                    has_delim = true;
                    break;
                }
            }
            if (!has_delim) continue;

            // Count columns using simple split (not quote-aware for speed)
            var cols: usize = 1;
            var empty_in_line: usize = 0;
            var field_start: usize = 0;

            for (line, 0..) |c, i| {
                if (c == delim) {
                    // Check if field is empty
                    if (i == field_start) {
                        empty_in_line += 1;
                    }
                    field_start = i + 1;
                    cols += 1;
                }
            }
            // Check last field
            if (field_start >= line.len) {
                empty_in_line += 1;
            }

            if (cols <= 1) continue;

            if (count_idx < SAMPLE_SIZE) {
                col_counts[count_idx] = cols;
                count_idx += 1;
            }
            empty_fields += empty_in_line;
            total_fields += cols;
        }

        // Need at least 3 lines with this delimiter
        if (count_idx < 3) continue;

        found = true;

        // Calculate mean column count
        var sum: usize = 0;
        for (col_counts[0..count_idx]) |c| {
            sum += c;
        }
        const mean: f64 = @as(f64, @floatFromInt(sum)) / @as(f64, @floatFromInt(count_idx));

        // Calculate variance
        var variance_sum: f64 = 0;
        for (col_counts[0..count_idx]) |c| {
            const diff = @as(f64, @floatFromInt(c)) - mean;
            variance_sum += diff * diff;
        }
        const variance = variance_sum / @as(f64, @floatFromInt(count_idx));

        // Calculate empty ratio
        const empty_ratio: f64 = if (total_fields > 0)
            @as(f64, @floatFromInt(empty_fields)) / @as(f64, @floatFromInt(total_fields))
        else
            0;

        // Score: reward consistency, penalize variance and empties
        const n: f64 = @floatFromInt(count_idx);
        const score = n - 5.0 * variance - 2.0 * empty_ratio * n;

        if (score > best_score) {
            best_score = score;
            best_delim = delim;
        }
    }

    return .{ .delimiter = best_delim, .has_evidence = found };
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

    // Buffer for sample lines when auto-detecting
    var sample_lines: std.ArrayListUnmanaged([]const u8) = .empty;
    defer {
        for (sample_lines.items) |line| allocator.free(line);
        sample_lines.deinit(allocator);
    }

    // Determine the delimiter
    var delimiter = config.delimiter;
    if (config.auto_detect) {
        // Buffer up to SAMPLE_SIZE lines for detection
        while (sample_lines.items.len < SAMPLE_SIZE) {
            const maybe_line = jn_core.readLine(reader);
            if (maybe_line == null) break;
            const clean_line = jn_core.stripCR(maybe_line.?);
            const duped = try allocator.dupe(u8, clean_line);
            try sample_lines.append(allocator, duped);
        }

        if (sample_lines.items.len == 0) {
            jn_core.flushWriter(writer);
            return;
        }

        const detection = detectDelimiter(sample_lines.items);
        delimiter = detection.delimiter;
    }

    var headers = std.ArrayListUnmanaged([]const u8){};
    defer {
        for (headers.items) |h| allocator.free(h);
        headers.deinit(allocator);
    }

    // Process header from first line (either from sample or fresh read)
    var data_start_idx: usize = 0;
    if (!config.no_header) {
        const header_line = if (sample_lines.items.len > 0)
            sample_lines.items[0]
        else blk: {
            const maybe_header = jn_core.readLine(reader);
            if (maybe_header == null) {
                jn_core.flushWriter(writer);
                return;
            }
            break :blk jn_core.stripCR(maybe_header.?);
        };

        const field_count = parseCSVRowFast(header_line, delimiter, &field_starts, &field_ends);
        for (0..field_count) |i| {
            const field = unquoteField(header_line[field_starts[i]..field_ends[i]]);
            const duped = try allocator.dupe(u8, field);
            try headers.append(allocator, duped);
        }

        if (sample_lines.items.len > 0) {
            data_start_idx = 1; // Skip header in sample
        }
    }

    // Helper to process a single data line
    const processLine = struct {
        fn f(
            w: anytype,
            line: []const u8,
            delim: u8,
            hdrs: *std.ArrayListUnmanaged([]const u8),
            no_header: bool,
            starts: *[1024]usize,
            ends: *[1024]usize,
        ) void {
            if (line.len == 0) return;

            const fc = parseCSVRowFast(line, delim, starts, ends);

            w.writeByte('{') catch |err| jn_core.handleWriteError(err);

            if (no_header) {
                for (0..fc) |i| {
                    if (i > 0) w.writeByte(',') catch |err| jn_core.handleWriteError(err);
                    w.print("\"col{d}\":", .{i}) catch |err| jn_core.handleWriteError(err);
                    const fld = unquoteField(line[starts[i]..ends[i]]);
                    jn_core.writeJsonString(w, fld) catch |err| jn_core.handleWriteError(err);
                }
            } else {
                const num_fields = @min(fc, hdrs.items.len);
                for (0..num_fields) |i| {
                    if (i > 0) w.writeByte(',') catch |err| jn_core.handleWriteError(err);
                    jn_core.writeJsonString(w, hdrs.items[i]) catch |err| jn_core.handleWriteError(err);
                    w.writeByte(':') catch |err| jn_core.handleWriteError(err);
                    const fld = unquoteField(line[starts[i]..ends[i]]);
                    jn_core.writeJsonString(w, fld) catch |err| jn_core.handleWriteError(err);
                }

                if (fc > hdrs.items.len) {
                    for (hdrs.items.len..fc) |i| {
                        w.writeByte(',') catch |err| jn_core.handleWriteError(err);
                        w.print("\"_extra{d}\":", .{i - hdrs.items.len}) catch |err| jn_core.handleWriteError(err);
                        const fld = unquoteField(line[starts[i]..ends[i]]);
                        jn_core.writeJsonString(w, fld) catch |err| jn_core.handleWriteError(err);
                    }
                }
            }

            w.writeByte('}') catch |err| jn_core.handleWriteError(err);
            w.writeByte('\n') catch |err| jn_core.handleWriteError(err);
        }
    }.f;

    // Process buffered sample lines first
    for (sample_lines.items[data_start_idx..]) |line| {
        processLine(writer, line, delimiter, &headers, config.no_header, &field_starts, &field_ends);
    }

    // Continue reading from stdin
    while (jn_core.readLine(reader)) |line| {
        const clean_line = jn_core.stripCR(line);
        processLine(writer, clean_line, delimiter, &headers, config.no_header, &field_starts, &field_ends);
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

test "detect comma delimiter" {
    const sample = [_][]const u8{
        "a,b,c",
        "1,2,3",
        "4,5,6",
        "7,8,9",
    };
    const result = detectDelimiter(&sample);
    try std.testing.expectEqual(@as(u8, ','), result.delimiter);
    try std.testing.expect(result.has_evidence);
}

test "detect tab delimiter" {
    const sample = [_][]const u8{
        "a\tb\tc",
        "1\t2\t3",
        "4\t5\t6",
        "7\t8\t9",
    };
    const result = detectDelimiter(&sample);
    try std.testing.expectEqual(@as(u8, '\t'), result.delimiter);
    try std.testing.expect(result.has_evidence);
}

test "detect semicolon delimiter" {
    const sample = [_][]const u8{
        "a;b;c",
        "1;2;3",
        "4;5;6",
        "7;8;9",
    };
    const result = detectDelimiter(&sample);
    try std.testing.expectEqual(@as(u8, ';'), result.delimiter);
    try std.testing.expect(result.has_evidence);
}

test "detect pipe delimiter" {
    const sample = [_][]const u8{
        "a|b|c",
        "1|2|3",
        "4|5|6",
        "7|8|9",
    };
    const result = detectDelimiter(&sample);
    try std.testing.expectEqual(@as(u8, '|'), result.delimiter);
    try std.testing.expect(result.has_evidence);
}

test "detect delimiter with inconsistent columns prefers consistent" {
    // Comma has inconsistent column counts, semicolon is consistent
    const sample = [_][]const u8{
        "a,b,c;x;y",
        "1,2;x;y",
        "3;x;y",
        "4;x;y",
    };
    const result = detectDelimiter(&sample);
    // Semicolon should win due to consistency
    try std.testing.expectEqual(@as(u8, ';'), result.delimiter);
}

test "detect delimiter empty input returns comma" {
    const sample = [_][]const u8{};
    const result = detectDelimiter(&sample);
    try std.testing.expectEqual(@as(u8, ','), result.delimiter);
    try std.testing.expect(!result.has_evidence);
}

test "detect delimiter no delimiters found returns comma" {
    const sample = [_][]const u8{
        "hello",
        "world",
        "test",
    };
    const result = detectDelimiter(&sample);
    try std.testing.expectEqual(@as(u8, ','), result.delimiter);
    try std.testing.expect(!result.has_evidence);
}
