//! jn-analyze: Single-pass statistics for NDJSON streams
//!
//! Analyzes NDJSON input and produces per-field statistics including
//! record count, field frequency, type distribution, and numeric stats.
//!
//! Usage:
//!   jn-analyze [OPTIONS]
//!
//! Options:
//!   --sample=N              Sample first N records (default: all)
//!   --format={json,text}    Output format (default: text)
//!   --help, -h              Show this help
//!   --version               Show version
//!
//! Examples:
//!   cat data.ndjson | jn-analyze
//!   cat data.ndjson | jn-analyze --sample=1000
//!   cat data.ndjson | jn-analyze --format=json

const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");

const VERSION = "0.1.0";
const DEFAULT_SAMPLE: usize = 0; // 0 = unlimited

/// Type counts for a field
const TypeCounts = struct {
    string: u64 = 0,
    number: u64 = 0,
    boolean: u64 = 0,
    null: u64 = 0,
    array: u64 = 0,
    object: u64 = 0,
};

/// Numeric statistics for a field
const NumericStats = struct {
    count: u64 = 0,
    min: f64 = std.math.inf(f64),
    max: f64 = -std.math.inf(f64),
    sum: f64 = 0.0,

    fn update(self: *NumericStats, value: f64) void {
        self.count += 1;
        if (value < self.min) self.min = value;
        if (value > self.max) self.max = value;
        self.sum += value;
    }

    fn mean(self: NumericStats) ?f64 {
        if (self.count == 0) return null;
        return self.sum / @as(f64, @floatFromInt(self.count));
    }
};

/// Per-field statistics
const FieldStats = struct {
    count: u64 = 0,
    types: TypeCounts = .{},
    numeric: NumericStats = .{},
};

/// Global analysis state
const AnalysisState = struct {
    allocator: std.mem.Allocator,
    record_count: u64 = 0,
    fields: std.StringHashMap(FieldStats),

    fn init(allocator: std.mem.Allocator) AnalysisState {
        return .{
            .allocator = allocator,
            .fields = std.StringHashMap(FieldStats).init(allocator),
        };
    }

    fn deinit(self: *AnalysisState) void {
        var iter = self.fields.keyIterator();
        while (iter.next()) |key| {
            self.allocator.free(key.*);
        }
        self.fields.deinit();
    }

    fn processRecord(self: *AnalysisState, value: std.json.Value) void {
        self.record_count += 1;

        switch (value) {
            .object => |obj| {
                var iter = obj.iterator();
                while (iter.next()) |entry| {
                    self.updateField(entry.key_ptr.*, entry.value_ptr.*);
                }
            },
            else => {}, // Only analyze object records
        }
    }

    fn updateField(self: *AnalysisState, field_name: []const u8, value: std.json.Value) void {
        // Get or create field stats
        const result = self.fields.getOrPut(field_name) catch return;
        if (!result.found_existing) {
            // Need to duplicate the key since it's from the JSON parser
            result.key_ptr.* = self.allocator.dupe(u8, field_name) catch return;
        }

        const stats = result.value_ptr;
        stats.count += 1;

        // Update type counts
        switch (value) {
            .null => stats.types.null += 1,
            .bool => stats.types.boolean += 1,
            .integer => |i| {
                stats.types.number += 1;
                stats.numeric.update(@floatFromInt(i));
            },
            .float => |f| {
                stats.types.number += 1;
                stats.numeric.update(f);
            },
            .number_string => |s| {
                stats.types.number += 1;
                if (std.fmt.parseFloat(f64, s)) |f| {
                    stats.numeric.update(f);
                } else |_| {}
            },
            .string => stats.types.string += 1,
            .array => stats.types.array += 1,
            .object => stats.types.object += 1,
        }
    }
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

    // Get sample size (0 = unlimited)
    var sample_size: usize = DEFAULT_SAMPLE;
    if (args.get("sample", null)) |sample_str| {
        sample_size = std.fmt.parseInt(usize, sample_str, 10) catch {
            jn_core.exitWithError("jn-analyze: invalid sample size: {s}", .{sample_str});
        };
    }

    // Get output format
    const json_format = if (args.get("format", null)) |fmt|
        std.mem.eql(u8, fmt, "json")
    else
        false;

    // Initialize analysis state
    var state = AnalysisState.init(allocator);
    defer state.deinit();

    // Arena allocator for JSON parsing (reset after each line)
    var arena = std.heap.ArenaAllocator.init(allocator);
    defer arena.deinit();

    // Process input
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;

        // Check sample limit
        if (sample_size > 0 and state.record_count >= sample_size) break;

        // Parse JSON
        if (jn_core.parseJsonLine(arena.allocator(), line)) |parsed| {
            defer parsed.deinit();
            state.processRecord(parsed.value);
        }

        // Reset arena for next line
        _ = arena.reset(.retain_capacity);
    }

    // Output results
    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    if (json_format) {
        outputJson(writer, &state);
    } else {
        outputText(writer, &state);
    }

    jn_core.flushWriter(writer);
}

/// Output statistics as JSON
fn outputJson(writer: anytype, state: *AnalysisState) void {
    writer.writeAll("{\"record_count\":") catch return;
    writer.print("{d}", .{state.record_count}) catch return;
    writer.writeAll(",\"fields\":{") catch return;

    // Collect and sort field names for deterministic output
    var names: std.ArrayListUnmanaged([]const u8) = .empty;
    defer names.deinit(state.allocator);

    var iter = state.fields.keyIterator();
    while (iter.next()) |key| {
        names.append(state.allocator, key.*) catch continue;
    }

    std.mem.sort([]const u8, names.items, {}, struct {
        fn lessThan(_: void, a: []const u8, b: []const u8) bool {
            return std.mem.order(u8, a, b) == .lt;
        }
    }.lessThan);

    var first = true;
    for (names.items) |name| {
        if (state.fields.get(name)) |stats| {
            if (!first) writer.writeByte(',') catch {};
            first = false;

            jn_core.writeJsonString(writer, name) catch {};
            writer.writeAll(":{") catch {};

            // Count and frequency
            writer.print("\"count\":{d}", .{stats.count}) catch {};
            const freq = if (state.record_count > 0)
                @as(f64, @floatFromInt(stats.count)) / @as(f64, @floatFromInt(state.record_count)) * 100.0
            else
                0.0;
            writer.print(",\"frequency\":{d:.1}", .{freq}) catch {};

            // Types
            writer.writeAll(",\"types\":{") catch {};
            var type_first = true;
            if (stats.types.string > 0) {
                writer.print("\"string\":{d}", .{stats.types.string}) catch {};
                type_first = false;
            }
            if (stats.types.number > 0) {
                if (!type_first) writer.writeByte(',') catch {};
                writer.print("\"number\":{d}", .{stats.types.number}) catch {};
                type_first = false;
            }
            if (stats.types.boolean > 0) {
                if (!type_first) writer.writeByte(',') catch {};
                writer.print("\"boolean\":{d}", .{stats.types.boolean}) catch {};
                type_first = false;
            }
            if (stats.types.null > 0) {
                if (!type_first) writer.writeByte(',') catch {};
                writer.print("\"null\":{d}", .{stats.types.null}) catch {};
                type_first = false;
            }
            if (stats.types.array > 0) {
                if (!type_first) writer.writeByte(',') catch {};
                writer.print("\"array\":{d}", .{stats.types.array}) catch {};
                type_first = false;
            }
            if (stats.types.object > 0) {
                if (!type_first) writer.writeByte(',') catch {};
                writer.print("\"object\":{d}", .{stats.types.object}) catch {};
            }
            writer.writeByte('}') catch {};

            // Numeric stats if applicable
            if (stats.numeric.count > 0) {
                writer.writeAll(",\"numeric\":{") catch {};
                writer.print("\"min\":{d}", .{stats.numeric.min}) catch {};
                writer.print(",\"max\":{d}", .{stats.numeric.max}) catch {};
                if (stats.numeric.mean()) |m| {
                    writer.print(",\"mean\":{d:.4}", .{m}) catch {};
                }
                writer.print(",\"sum\":{d}", .{stats.numeric.sum}) catch {};
                writer.writeByte('}') catch {};
            }

            writer.writeByte('}') catch {};
        }
    }

    writer.writeAll("}}\n") catch {};
}

/// Output statistics as human-readable text
fn outputText(writer: anytype, state: *AnalysisState) void {
    // Header
    writer.writeAll("=== NDJSON Analysis ===\n\n") catch {};
    writer.print("Records: {d}\n", .{state.record_count}) catch {};
    writer.print("Fields:  {d}\n\n", .{state.fields.count()}) catch {};

    if (state.fields.count() == 0) return;

    // Collect and sort field names
    var names: std.ArrayListUnmanaged([]const u8) = .empty;
    defer names.deinit(state.allocator);

    var iter = state.fields.keyIterator();
    while (iter.next()) |key| {
        names.append(state.allocator, key.*) catch continue;
    }

    std.mem.sort([]const u8, names.items, {}, struct {
        fn lessThan(_: void, a: []const u8, b: []const u8) bool {
            return std.mem.order(u8, a, b) == .lt;
        }
    }.lessThan);

    // Per-field stats
    writer.writeAll("--- Field Statistics ---\n\n") catch {};

    for (names.items) |name| {
        if (state.fields.get(name)) |stats| {
            // Field name and count
            writer.writeAll(name) catch {};
            writer.writeAll(":\n") catch {};

            const freq = if (state.record_count > 0)
                @as(f64, @floatFromInt(stats.count)) / @as(f64, @floatFromInt(state.record_count)) * 100.0
            else
                0.0;
            writer.print("  count:     {d} ({d:.1}%)\n", .{ stats.count, freq }) catch {};

            // Type breakdown
            writer.writeAll("  types:     ") catch {};
            var type_count: u32 = 0;
            if (stats.types.string > 0) {
                if (type_count > 0) writer.writeAll(", ") catch {};
                writer.print("string({d})", .{stats.types.string}) catch {};
                type_count += 1;
            }
            if (stats.types.number > 0) {
                if (type_count > 0) writer.writeAll(", ") catch {};
                writer.print("number({d})", .{stats.types.number}) catch {};
                type_count += 1;
            }
            if (stats.types.boolean > 0) {
                if (type_count > 0) writer.writeAll(", ") catch {};
                writer.print("boolean({d})", .{stats.types.boolean}) catch {};
                type_count += 1;
            }
            if (stats.types.null > 0) {
                if (type_count > 0) writer.writeAll(", ") catch {};
                writer.print("null({d})", .{stats.types.null}) catch {};
                type_count += 1;
            }
            if (stats.types.array > 0) {
                if (type_count > 0) writer.writeAll(", ") catch {};
                writer.print("array({d})", .{stats.types.array}) catch {};
                type_count += 1;
            }
            if (stats.types.object > 0) {
                if (type_count > 0) writer.writeAll(", ") catch {};
                writer.print("object({d})", .{stats.types.object}) catch {};
            }
            writer.writeByte('\n') catch {};

            // Numeric stats
            if (stats.numeric.count > 0) {
                writer.print("  min:       {d}\n", .{stats.numeric.min}) catch {};
                writer.print("  max:       {d}\n", .{stats.numeric.max}) catch {};
                if (stats.numeric.mean()) |m| {
                    writer.print("  mean:      {d:.4}\n", .{m}) catch {};
                }
                writer.print("  sum:       {d}\n", .{stats.numeric.sum}) catch {};
            }

            writer.writeByte('\n') catch {};
        }
    }
}

/// Print version
fn printVersion() void {
    var buf: [256]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.print("jn-analyze {s}\n", .{VERSION}) catch {};
    jn_core.flushWriter(stdout);
}

/// Print usage information
fn printUsage() void {
    const usage =
        \\jn-analyze - Single-pass statistics for NDJSON streams
        \\
        \\Usage: jn-analyze [OPTIONS]
        \\
        \\Analyzes NDJSON input and produces per-field statistics.
        \\
        \\Options:
        \\  --sample=N            Sample first N records (default: all)
        \\  --format={json,text}  Output format (default: text)
        \\  --help, -h            Show this help
        \\  --version             Show version
        \\
        \\Output includes:
        \\  - Record count
        \\  - Per-field frequency (% of records containing field)
        \\  - Type distribution (string, number, boolean, null, array, object)
        \\  - Numeric statistics (min, max, mean, sum)
        \\
        \\Examples:
        \\  cat data.ndjson | jn-analyze
        \\  cat data.ndjson | jn-analyze --sample=1000
        \\  cat data.ndjson | jn-analyze --format=json
        \\
    ;
    var buf: [2048]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.writeAll(usage) catch {};
    jn_core.flushWriter(stdout);
}

// Tests
test "TypeCounts defaults to zero" {
    const tc = TypeCounts{};
    try std.testing.expectEqual(@as(u64, 0), tc.string);
    try std.testing.expectEqual(@as(u64, 0), tc.number);
}

test "NumericStats.update tracks min/max/sum" {
    var ns = NumericStats{};
    ns.update(10.0);
    ns.update(5.0);
    ns.update(15.0);

    try std.testing.expectEqual(@as(u64, 3), ns.count);
    try std.testing.expectEqual(@as(f64, 5.0), ns.min);
    try std.testing.expectEqual(@as(f64, 15.0), ns.max);
    try std.testing.expectEqual(@as(f64, 30.0), ns.sum);
    try std.testing.expectEqual(@as(f64, 10.0), ns.mean().?);
}

test "NumericStats.mean returns null when empty" {
    const ns = NumericStats{};
    try std.testing.expect(ns.mean() == null);
}
