//! ZQ Performance Benchmarks
//!
//! Run with: zig test -O ReleaseFast benchmarks/zq_bench.zig
//!
//! These benchmarks measure specific hotspot functions in ZQ.

const std = @import("std");

// Timer helper for benchmarks
fn benchLoop(comptime T: type, iterations: usize, context: T, func: fn (T) void) u64 {
    var timer = std.time.Timer.start() catch unreachable;
    for (0..iterations) |_| {
        func(context);
    }
    return timer.read();
}

// ============================================================================
// JSON String Escaping Benchmark
// ============================================================================

/// Original character-by-character JSON string escaping
fn writeJsonStringOriginal(writer: anytype, s: []const u8) !void {
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

/// Optimized JSON string escaping with batch writes for safe characters
fn writeJsonStringOptimized(writer: anytype, s: []const u8) !void {
    try writer.writeByte('"');

    var start: usize = 0;
    for (s, 0..) |c, i| {
        // Check if character needs escaping
        const needs_escape = (c == '"' or c == '\\' or c < 0x20);

        if (!needs_escape) continue;

        // Write batch of safe chars before this escape
        if (i > start) {
            try writer.writeAll(s[start..i]);
        }

        switch (c) {
            '"' => try writer.writeAll("\\\""),
            '\\' => try writer.writeAll("\\\\"),
            '\n' => try writer.writeAll("\\n"),
            '\r' => try writer.writeAll("\\r"),
            '\t' => try writer.writeAll("\\t"),
            else => try writer.print("\\u{x:0>4}", .{c}),
        }
        start = i + 1;
    }

    // Write remaining safe chars
    if (start < s.len) {
        try writer.writeAll(s[start..]);
    }
    try writer.writeByte('"');
}

test "JSON string escaping benchmark" {
    const allocator = std.testing.allocator;

    // Test string with mostly safe chars and a few escapes
    const test_string = "user_12345@example.com is a \"test\" value\nwith some\tescape sequences";
    const iterations: usize = 100_000;

    var out_buf: [4096]u8 = undefined;

    // Benchmark original
    var fbs1 = std.io.fixedBufferStream(&out_buf);
    var timer1 = try std.time.Timer.start();
    for (0..iterations) |_| {
        fbs1.reset();
        try writeJsonStringOriginal(fbs1.writer(), test_string);
    }
    const orig_ns = timer1.read();

    // Benchmark optimized
    var fbs2 = std.io.fixedBufferStream(&out_buf);
    var timer2 = try std.time.Timer.start();
    for (0..iterations) |_| {
        fbs2.reset();
        try writeJsonStringOptimized(fbs2.writer(), test_string);
    }
    const opt_ns = timer2.read();

    // Print results
    std.debug.print("\n=== JSON String Escaping Benchmark ===\n", .{});
    std.debug.print("String length: {d} chars\n", .{test_string.len});
    std.debug.print("Iterations: {d}\n", .{iterations});
    std.debug.print("Original: {d} ns/iter ({d:.2} MB/s)\n", .{
        orig_ns / iterations,
        @as(f64, @floatFromInt(test_string.len * iterations)) / @as(f64, @floatFromInt(orig_ns)) * 1000,
    });
    std.debug.print("Optimized: {d} ns/iter ({d:.2} MB/s)\n", .{
        opt_ns / iterations,
        @as(f64, @floatFromInt(test_string.len * iterations)) / @as(f64, @floatFromInt(opt_ns)) * 1000,
    });
    std.debug.print("Speedup: {d:.2}x\n", .{
        @as(f64, @floatFromInt(orig_ns)) / @as(f64, @floatFromInt(opt_ns)),
    });

    // Verify they produce the same output
    var buf1: [256]u8 = undefined;
    var buf2: [256]u8 = undefined;
    var stream1 = std.io.fixedBufferStream(&buf1);
    var stream2 = std.io.fixedBufferStream(&buf2);
    try writeJsonStringOriginal(stream1.writer(), test_string);
    try writeJsonStringOptimized(stream2.writer(), test_string);
    try std.testing.expectEqualStrings(stream1.getWritten(), stream2.getWritten());

    _ = allocator;
}

// ============================================================================
// CSV Field Parsing Benchmark
// ============================================================================

const MAX_CSV_FIELDS: usize = 256;

/// Original CSV row parser (character-by-character)
fn parseCSVRowOriginal(line: []const u8, delimiter: u8, starts: *[MAX_CSV_FIELDS]usize, ends: *[MAX_CSV_FIELDS]usize) usize {
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
            if (field_count < MAX_CSV_FIELDS) {
                starts[field_count] = field_start;
                ends[field_count] = i;
                field_count += 1;
            }
            field_start = i + 1;
        }
    }

    if (field_count < MAX_CSV_FIELDS) {
        starts[field_count] = field_start;
        ends[field_count] = line.len;
        field_count += 1;
    }

    return field_count;
}

/// Optimized CSV parser using memchr for delimiter scanning
fn parseCSVRowOptimized(line: []const u8, delimiter: u8, starts: *[MAX_CSV_FIELDS]usize, ends: *[MAX_CSV_FIELDS]usize) usize {
    var field_count: usize = 0;
    var field_start: usize = 0;
    var pos: usize = 0;

    while (pos < line.len and field_count < MAX_CSV_FIELDS) {
        // Check if field starts with quote
        if (line[pos] == '"') {
            // Quoted field - scan for closing quote
            pos += 1;
            while (pos < line.len) {
                if (line[pos] == '"') {
                    if (pos + 1 < line.len and line[pos + 1] == '"') {
                        pos += 2; // escaped quote
                        continue;
                    }
                    pos += 1; // closing quote
                    break;
                }
                pos += 1;
            }
            // Now find delimiter or end
            if (pos < line.len and line[pos] == delimiter) {
                starts[field_count] = field_start;
                ends[field_count] = pos;
                field_count += 1;
                field_start = pos + 1;
                pos += 1;
            }
        } else {
            // Unquoted field - use memchr to find delimiter
            if (std.mem.indexOfScalar(u8, line[pos..], delimiter)) |delim_pos| {
                starts[field_count] = field_start;
                ends[field_count] = pos + delim_pos;
                field_count += 1;
                pos = pos + delim_pos + 1;
                field_start = pos;
            } else {
                break; // no more delimiters
            }
        }
    }

    // Add final field
    if (field_count < MAX_CSV_FIELDS) {
        starts[field_count] = field_start;
        ends[field_count] = line.len;
        field_count += 1;
    }

    return field_count;
}

test "CSV parsing benchmark" {
    // Typical CSV line with 8 fields
    const test_line = "12345,user_test_12345,user12345@example.com,42,87.5,true,CategoryA,New York City";
    const iterations: usize = 100_000;

    var starts: [MAX_CSV_FIELDS]usize = undefined;
    var ends: [MAX_CSV_FIELDS]usize = undefined;

    // Benchmark original
    var timer1 = try std.time.Timer.start();
    for (0..iterations) |_| {
        _ = parseCSVRowOriginal(test_line, ',', &starts, &ends);
    }
    const orig_ns = timer1.read();

    // Benchmark optimized
    var timer2 = try std.time.Timer.start();
    for (0..iterations) |_| {
        _ = parseCSVRowOptimized(test_line, ',', &starts, &ends);
    }
    const opt_ns = timer2.read();

    // Print results
    std.debug.print("\n=== CSV Parsing Benchmark ===\n", .{});
    std.debug.print("Line length: {d} chars, 8 fields\n", .{test_line.len});
    std.debug.print("Iterations: {d}\n", .{iterations});
    std.debug.print("Original: {d} ns/iter ({d:.2} M rows/s)\n", .{
        orig_ns / iterations,
        @as(f64, @floatFromInt(iterations)) / @as(f64, @floatFromInt(orig_ns)) * 1000,
    });
    std.debug.print("Optimized: {d} ns/iter ({d:.2} M rows/s)\n", .{
        opt_ns / iterations,
        @as(f64, @floatFromInt(iterations)) / @as(f64, @floatFromInt(opt_ns)) * 1000,
    });
    std.debug.print("Speedup: {d:.2}x\n", .{
        @as(f64, @floatFromInt(orig_ns)) / @as(f64, @floatFromInt(opt_ns)),
    });

    // Verify they produce the same field count
    const count1 = parseCSVRowOriginal(test_line, ',', &starts, &ends);
    const count2 = parseCSVRowOptimized(test_line, ',', &starts, &ends);
    try std.testing.expectEqual(count1, count2);
}

// ============================================================================
// JSON Parsing Simulation
// ============================================================================

test "JSON parsing overhead measurement" {
    const allocator = std.testing.allocator;

    // Typical NDJSON record
    const json_line = "{\"id\":12345,\"name\":\"user_test\",\"email\":\"test@example.com\",\"age\":42,\"score\":87.5,\"active\":true,\"category\":\"A\"}";
    const iterations: usize = 10_000;

    // Benchmark parsing
    var timer = try std.time.Timer.start();
    for (0..iterations) |_| {
        const parsed = std.json.parseFromSlice(std.json.Value, allocator, json_line, .{}) catch continue;
        defer parsed.deinit();
        // Simulate field access
        if (parsed.value.object.get("name")) |_| {}
        if (parsed.value.object.get("age")) |_| {}
    }
    const parse_ns = timer.read();

    std.debug.print("\n=== JSON Parse + Field Access Benchmark ===\n", .{});
    std.debug.print("JSON size: {d} bytes\n", .{json_line.len});
    std.debug.print("Iterations: {d}\n", .{iterations});
    std.debug.print("Parse + access: {d} ns/iter\n", .{parse_ns / iterations});
    std.debug.print("Throughput: {d:.2} K records/s\n", .{
        @as(f64, @floatFromInt(iterations)) / @as(f64, @floatFromInt(parse_ns)) * 1_000_000,
    });
}

// ============================================================================
// HashMap vs Array Field Lookup
// ============================================================================

test "field lookup comparison" {
    const allocator = std.testing.allocator;

    // Create a map with typical fields
    var map = std.json.ObjectMap.init(allocator);
    defer map.deinit();
    try map.put("id", .{ .integer = 12345 });
    try map.put("name", .{ .string = "test_user" });
    try map.put("email", .{ .string = "test@example.com" });
    try map.put("age", .{ .integer = 42 });
    try map.put("score", .{ .float = 87.5 });
    try map.put("active", .{ .bool = true });
    try map.put("category", .{ .string = "A" });
    try map.put("city", .{ .string = "NYC" });

    const iterations: usize = 1_000_000;

    // Benchmark single field lookup
    var timer = try std.time.Timer.start();
    for (0..iterations) |_| {
        _ = map.get("name");
        _ = map.get("age");
        _ = map.get("missing");
    }
    const lookup_ns = timer.read();

    std.debug.print("\n=== HashMap Field Lookup Benchmark ===\n", .{});
    std.debug.print("Map size: 8 fields\n", .{});
    std.debug.print("Iterations: {d} (3 lookups each)\n", .{iterations});
    std.debug.print("Lookup time: {d} ns/iter ({d} ns per lookup)\n", .{
        lookup_ns / iterations,
        lookup_ns / iterations / 3,
    });
}
