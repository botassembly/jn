const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");
const jn_plugin = @import("jn-plugin");

const plugin_meta = jn_plugin.PluginMeta{
    .name = "csv",
    .version = "0.2.0",
    .matches = &.{ ".*\\.csv$", ".*\\.tsv$", ".*\\.txt$" },
    .role = .format,
    .modes = &.{ .read, .write },
};

const Config = struct {
    delimiter: u8 = ',',
    auto_detect: bool = false,
    no_header: bool = false,
};

/// Maximum number of fields per CSV row. This limit prevents buffer overflow
/// attacks with maliciously crafted CSV files.
const MAX_CSV_FIELDS: usize = 4096;

/// Warning state for field truncation (passed to avoid global mutable state)
const TruncationWarningState = struct {
    warned: bool = false,
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
    // Handle named delimiters
    if (std.mem.eql(u8, value, "tab") or std.mem.eql(u8, value, "\\t")) {
        return '\t';
    }
    if (std.mem.eql(u8, value, "comma")) {
        return ',';
    }
    if (std.mem.eql(u8, value, "semicolon")) {
        return ';';
    }
    if (std.mem.eql(u8, value, "pipe")) {
        return '|';
    }

    // Handle empty input with warning
    if (value.len == 0) {
        std.debug.print("csv: warning: empty delimiter specified, using comma\n", .{});
        return ',';
    }

    // Warn if multi-character delimiter specified (only first char is used)
    if (value.len > 1) {
        std.debug.print("csv: warning: only first character of delimiter '{s}' will be used\n", .{value});
    }

    return value[0];
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
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    var field_starts: [MAX_CSV_FIELDS]usize = undefined;
    var field_ends: [MAX_CSV_FIELDS]usize = undefined;

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

        // Note: null for warn_state since header parsing doesn't need truncation warnings
        const field_count = parseCSVRowFast(header_line, delimiter, &field_starts, &field_ends, null);
        for (0..field_count) |i| {
            var needs_free: bool = false;
            const field = unquoteField(allocator, header_line[field_starts[i]..field_ends[i]], &needs_free);
            defer if (needs_free) allocator.free(@constCast(field));
            const duped = try allocator.dupe(u8, field);
            try headers.append(allocator, duped);
        }

        if (sample_lines.items.len > 0) {
            data_start_idx = 1; // Skip header in sample
        }
    }

    // Warning state for field truncation (local, not global)
    var truncation_warn = TruncationWarningState{};

    // Helper to process a single data line
    const processLine = struct {
        fn f(
            alloc: std.mem.Allocator,
            w: anytype,
            line: []const u8,
            delim: u8,
            hdrs: *std.ArrayListUnmanaged([]const u8),
            no_header: bool,
            starts: *[MAX_CSV_FIELDS]usize,
            ends: *[MAX_CSV_FIELDS]usize,
            warn_state: *TruncationWarningState,
        ) void {
            if (line.len == 0) return;

            const fc = parseCSVRowFast(line, delim, starts, ends, warn_state);

            w.writeByte('{') catch |err| jn_core.handleWriteError(err);

            if (no_header) {
                for (0..fc) |i| {
                    if (i > 0) w.writeByte(',') catch |err| jn_core.handleWriteError(err);
                    w.print("\"col{d}\":", .{i}) catch |err| jn_core.handleWriteError(err);
                    var needs_free: bool = false;
                    const fld = unquoteField(alloc, line[starts[i]..ends[i]], &needs_free);
                    defer if (needs_free) alloc.free(@constCast(fld));
                    jn_core.writeJsonString(w, fld) catch |err| jn_core.handleWriteError(err);
                }
            } else {
                const num_fields = @min(fc, hdrs.items.len);
                for (0..num_fields) |i| {
                    if (i > 0) w.writeByte(',') catch |err| jn_core.handleWriteError(err);
                    jn_core.writeJsonString(w, hdrs.items[i]) catch |err| jn_core.handleWriteError(err);
                    w.writeByte(':') catch |err| jn_core.handleWriteError(err);
                    var needs_free: bool = false;
                    const fld = unquoteField(alloc, line[starts[i]..ends[i]], &needs_free);
                    defer if (needs_free) alloc.free(@constCast(fld));
                    jn_core.writeJsonString(w, fld) catch |err| jn_core.handleWriteError(err);
                }

                if (fc > hdrs.items.len) {
                    for (hdrs.items.len..fc) |i| {
                        w.writeByte(',') catch |err| jn_core.handleWriteError(err);
                        w.print("\"_extra{d}\":", .{i - hdrs.items.len}) catch |err| jn_core.handleWriteError(err);
                        var needs_free: bool = false;
                        const fld = unquoteField(alloc, line[starts[i]..ends[i]], &needs_free);
                        defer if (needs_free) alloc.free(@constCast(fld));
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
        processLine(allocator, writer, line, delimiter, &headers, config.no_header, &field_starts, &field_ends, &truncation_warn);
    }

    // Continue reading from stdin
    while (jn_core.readLine(reader)) |line| {
        const clean_line = jn_core.stripCR(line);
        processLine(allocator, writer, clean_line, delimiter, &headers, config.no_header, &field_starts, &field_ends, &truncation_warn);
    }

    jn_core.flushWriter(writer);
}

fn parseCSVRowFast(line: []const u8, delimiter: u8, starts: *[MAX_CSV_FIELDS]usize, ends: *[MAX_CSV_FIELDS]usize, warn_state: ?*TruncationWarningState) usize {
    var field_count: usize = 0;
    var i: usize = 0;
    var field_start: usize = 0;
    var in_quotes = false;
    var truncated = false;

    while (i < line.len) : (i += 1) {
        const c = line[i];

        if (c == '"') {
            if (in_quotes and i + 1 < line.len and line[i + 1] == '"') {
                i += 1;
                continue;
            }
            in_quotes = !in_quotes;
        } else if (c == delimiter and !in_quotes) {
            if (field_count < MAX_CSV_FIELDS) {
                starts[field_count] = field_start;
                ends[field_count] = i;
                field_count += 1;
            } else {
                truncated = true;
            }
            field_start = i + 1;
        }
    }

    if (field_count < MAX_CSV_FIELDS) {
        starts[field_count] = field_start;
        ends[field_count] = line.len;
        field_count += 1;
    } else {
        truncated = true;
    }

    // Warn once about field truncation (using passed state to avoid global mutable state)
    if (truncated) {
        if (warn_state) |ws| {
            if (!ws.warned) {
                ws.warned = true;
                const stderr = std.fs.File.stderr();
                _ = stderr.write("csv: warning: row has more than ") catch {};
                var num_buf: [16]u8 = undefined;
                const num_str = std.fmt.bufPrint(&num_buf, "{d}", .{MAX_CSV_FIELDS}) catch "4096";
                _ = stderr.write(num_str) catch {};
                _ = stderr.write(" fields, extra fields truncated\n") catch {};
            }
        }
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
            var needs_free: bool = false;
            const field = unquoteField(allocator, line[field_start..i], &needs_free);
            // Always dupe to ensure consistent ownership - fields list owns all memory
            const duped = if (needs_free) field else try allocator.dupe(u8, field);
            try fields.append(allocator, duped);
            field_start = i + 1;
            i += 1;
        } else {
            i += 1;
        }
    }

    var needs_free: bool = false;
    const field = unquoteField(allocator, line[field_start..], &needs_free);
    const duped = if (needs_free) field else try allocator.dupe(u8, field);
    try fields.append(allocator, duped);
}

/// Unquote and unescape a CSV field.
/// Returns a slice that may or may not need freeing depending on `needs_free` output.
/// Handles RFC 4180 escaped quotes (doubled quotes "" become single ").
///
/// NOTE: On allocation failure, returns the raw unprocessed field content
/// (with quotes stripped but escaped quotes not unescaped). A warning is printed
/// to stderr. This is a trade-off for streaming resilience - we prefer to output
/// slightly malformed data rather than abort the entire stream on transient OOM.
fn unquoteField(allocator: std.mem.Allocator, field: []const u8, needs_free: *bool) []const u8 {
    needs_free.* = false;

    if (field.len < 2) return field;
    if (field[0] != '"' or field[field.len - 1] != '"') return field;

    const inner = field[1 .. field.len - 1];

    // Check if the field contains escaped quotes
    var has_escaped_quote = false;
    var i: usize = 0;
    while (i < inner.len) : (i += 1) {
        if (i + 1 < inner.len and inner[i] == '"' and inner[i + 1] == '"') {
            has_escaped_quote = true;
            break;
        }
    }

    if (!has_escaped_quote) {
        // No escaped quotes - just return the inner slice
        return inner;
    }

    // Need to unescape - build new string replacing "" with "
    var result: std.ArrayListUnmanaged(u8) = .empty;
    // Track if we need to cleanup on OOM - can't use errdefer with non-error return
    var cleanup_on_oom = true;
    defer if (cleanup_on_oom) result.deinit(allocator);

    i = 0;
    while (i < inner.len) {
        if (i + 1 < inner.len and inner[i] == '"' and inner[i + 1] == '"') {
            result.append(allocator, '"') catch {
                std.debug.print("csv: warning: out of memory unescaping field, data may be malformed\n", .{});
                return inner;
            };
            i += 2;
        } else {
            result.append(allocator, inner[i]) catch {
                std.debug.print("csv: warning: out of memory unescaping field, data may be malformed\n", .{});
                return inner;
            };
            i += 1;
        }
    }

    const owned = result.toOwnedSlice(allocator) catch {
        std.debug.print("csv: warning: out of memory unescaping field, data may be malformed\n", .{});
        return inner;
    };
    cleanup_on_oom = false; // Success - caller owns the memory now
    needs_free.* = true;
    return owned;
}

fn writeMode(allocator: std.mem.Allocator, config: Config) !void {
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&stdout_buf);
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
    defer {
        for (fields.items) |f| allocator.free(@constCast(f));
        fields.deinit(allocator);
    }

    try parseCSVRow(allocator, "a,b,c", ',', &fields);
    try std.testing.expectEqual(@as(usize, 3), fields.items.len);
    try std.testing.expectEqualStrings("a", fields.items[0]);
    try std.testing.expectEqualStrings("b", fields.items[1]);
    try std.testing.expectEqualStrings("c", fields.items[2]);
}

test "parse quoted csv row" {
    const allocator = std.testing.allocator;
    var fields = std.ArrayListUnmanaged([]const u8){};
    defer {
        for (fields.items) |f| allocator.free(@constCast(f));
        fields.deinit(allocator);
    }

    try parseCSVRow(allocator, "\"hello, world\",b,c", ',', &fields);
    try std.testing.expectEqual(@as(usize, 3), fields.items.len);
    try std.testing.expectEqualStrings("hello, world", fields.items[0]);
}

test "parse csv with escaped quotes" {
    const allocator = std.testing.allocator;
    var fields = std.ArrayListUnmanaged([]const u8){};
    defer {
        for (fields.items) |f| allocator.free(@constCast(f));
        fields.deinit(allocator);
    }

    // RFC 4180: doubled quotes inside quoted field should become single quote
    try parseCSVRow(allocator, "\"He said \"\"Hello\"\"\",b,c", ',', &fields);
    try std.testing.expectEqual(@as(usize, 3), fields.items.len);
    try std.testing.expectEqualStrings("He said \"Hello\"", fields.items[0]);
}

test "unquote field" {
    const allocator = std.testing.allocator;
    var needs_free: bool = false;

    // Simple quoted field
    const field1 = unquoteField(allocator, "\"hello\"", &needs_free);
    defer if (needs_free) allocator.free(@constCast(field1));
    try std.testing.expectEqualStrings("hello", field1);
    try std.testing.expect(!needs_free);

    // Unquoted field
    needs_free = false;
    const field2 = unquoteField(allocator, "world", &needs_free);
    defer if (needs_free) allocator.free(@constCast(field2));
    try std.testing.expectEqualStrings("world", field2);
    try std.testing.expect(!needs_free);
}

test "unquote field with escaped quotes" {
    const allocator = std.testing.allocator;
    var needs_free: bool = false;

    // Field with escaped quotes - should allocate
    const field = unquoteField(allocator, "\"He said \"\"Hi\"\"\"", &needs_free);
    defer if (needs_free) allocator.free(@constCast(field));
    try std.testing.expectEqualStrings("He said \"Hi\"", field);
    try std.testing.expect(needs_free);
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

test "parseDelimiter handles named delimiters" {
    try std.testing.expectEqual(@as(u8, '\t'), parseDelimiter("tab"));
    try std.testing.expectEqual(@as(u8, '\t'), parseDelimiter("\\t"));
    try std.testing.expectEqual(@as(u8, ','), parseDelimiter("comma"));
    try std.testing.expectEqual(@as(u8, ';'), parseDelimiter("semicolon"));
    try std.testing.expectEqual(@as(u8, '|'), parseDelimiter("pipe"));
}

test "parseDelimiter handles single character" {
    try std.testing.expectEqual(@as(u8, ','), parseDelimiter(","));
    try std.testing.expectEqual(@as(u8, ';'), parseDelimiter(";"));
    try std.testing.expectEqual(@as(u8, ':'), parseDelimiter(":"));
}

test "parseDelimiter empty returns comma" {
    // Empty delimiter should fall back to comma (with warning printed to stderr)
    try std.testing.expectEqual(@as(u8, ','), parseDelimiter(""));
}
