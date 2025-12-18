//! jn-join: Hash join for NDJSON streams
//!
//! Joins data from stdin (left) with another source (right) using hash-based matching.
//!
//! Usage:
//!   jn-join [OPTIONS] <RIGHT_SOURCE>
//!
//! Options:
//!   --on=FIELD              Join key (same name on both sides)
//!   --left-key=FIELD        Left side join key (if different from right)
//!   --right-key=FIELD       Right side join key
//!   --inner                 Inner join (exclude unmatched left records)
//!   --help, -h              Show this help
//!   --version               Show version
//!
//! Examples:
//!   cat orders.csv | jn-join customers.csv --on customer_id
//!   cat orders.csv | jn-join customers.csv --left-key cust_id --right-key id
//!   cat orders.csv | jn-join customers.csv --on customer_id --inner
//!
//! ## Design Decision: Silent Skipping of Malformed Records
//!
//! This tool silently skips records that fail JSON parsing rather than failing
//! the entire pipeline. This is INTENTIONAL for streaming data pipelines:
//!
//! 1. **Resilience**: A single malformed record in a 10GB file shouldn't crash
//!    the entire join operation. Skip it and continue.
//!
//! 2. **Streaming philosophy**: JN processes data line-by-line. Each line is
//!    independent. Bad lines are skipped, good lines flow through.
//!
//! 3. **Practical data quality**: Real-world data often has occasional corruption.
//!    Pipelines should be robust to this.
//!
//! For strict validation, use a separate validation step before the join.
//! Future enhancement: Add --strict flag or warning counter for visibility.
//!
//! See also: spec/08-streaming-backpressure.md

const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");
const jn_address = @import("jn-address");

const VERSION = "0.1.0";

// Configuration
const JoinConfig = struct {
    on_key: ?[]const u8 = null,
    left_key: ?[]const u8 = null,
    right_key: ?[]const u8 = null,
    inner_join: bool = false,

    fn getLeftKey(self: JoinConfig) []const u8 {
        return self.left_key orelse self.on_key orelse "";
    }

    fn getRightKey(self: JoinConfig) []const u8 {
        return self.right_key orelse self.on_key orelse "";
    }
};

// Use string map for simplicity (key is the stringified JSON value)
const RightRecords = std.StringHashMap(std.ArrayListUnmanaged([]const u8));

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const args = jn_cli.parseArgs();

    if (args.has("help") or args.has("h")) {
        printUsage();
        return;
    }

    if (args.has("version")) {
        printVersion();
        return;
    }

    const config = JoinConfig{
        .on_key = args.get("on", null),
        .left_key = args.get("left-key", null),
        .right_key = args.get("right-key", null),
        .inner_join = args.has("inner"),
    };

    if (config.on_key == null and (config.left_key == null or config.right_key == null)) {
        jn_core.exitWithError("jn-join: must specify --on or both --left-key and --right-key", .{});
    }

    const right_source = getPositionalArg() orelse {
        jn_core.exitWithError("jn-join: missing right source argument\nUsage: jn-join [OPTIONS] <RIGHT_SOURCE>", .{});
    };

    // Load right source into hash map
    var right_map = RightRecords.init(allocator);
    defer {
        var it = right_map.iterator();
        while (it.next()) |entry| {
            for (entry.value_ptr.items) |item| {
                allocator.free(item);
            }
            entry.value_ptr.deinit(allocator);
            allocator.free(entry.key_ptr.*);
        }
        right_map.deinit();
    }

    try loadRightSource(allocator, right_source, config.getRightKey(), &right_map);
    try processLeftSource(allocator, &config, &right_map);
}

fn loadRightSource(allocator: std.mem.Allocator, source: []const u8, key_field: []const u8, map: *RightRecords) !void {
    const address = jn_address.parse(source);

    switch (address.address_type) {
        .file => try loadFromFile(allocator, source, key_field, map),
        .stdin => jn_core.exitWithError("jn-join: right source cannot be stdin", .{}),
        else => jn_core.exitWithError("jn-join: right source must be a local file", .{}),
    }
}

fn loadFromFile(allocator: std.mem.Allocator, path: []const u8, key_field: []const u8, map: *RightRecords) !void {
    const format = jn_address.parse(path).effectiveFormat() orelse "jsonl";

    // For non-JSONL files, use jn-cat
    if (!std.mem.eql(u8, format, "jsonl") and !std.mem.eql(u8, format, "ndjson") and !std.mem.eql(u8, format, "json")) {
        try loadViaJnCat(allocator, path, key_field, map);
        return;
    }

    const file = std.fs.cwd().openFile(path, .{}) catch |err| {
        jn_core.exitWithError("jn-join: cannot open '{s}': {s}", .{ path, @errorName(err) });
    };
    defer file.close();

    var file_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var file_wrapper = file.reader(&file_buf);
    const reader = &file_wrapper.interface;

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;
        try addToMap(allocator, line, key_field, map);
    }
}

fn loadViaJnCat(allocator: std.mem.Allocator, path: []const u8, key_field: []const u8, map: *RightRecords) !void {
    const jn_cat_path = findTool(allocator, "jn-cat") orelse {
        jn_core.exitWithError("jn-join: jn-cat not found", .{});
    };

    // Use direct exec instead of shell to avoid command injection vulnerabilities.
    // The path is passed as a direct argument, not through shell interpolation.
    const argv: [2][]const u8 = .{ jn_cat_path, path };
    var child = std.process.Child.init(&argv, allocator);
    child.stdin_behavior = .Close;
    child.stdout_behavior = .Pipe;
    child.stderr_behavior = .Inherit;

    try child.spawn();

    var pipe_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var pipe_wrapper = child.stdout.?.reader(&pipe_buf);
    const reader = &pipe_wrapper.interface;

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;
        try addToMap(allocator, line, key_field, map);
    }

    _ = child.wait() catch {};
}

fn addToMap(allocator: std.mem.Allocator, line: []const u8, key_field: []const u8, map: *RightRecords) !void {
    const parsed = std.json.parseFromSlice(std.json.Value, allocator, line, .{}) catch return;
    defer parsed.deinit();

    if (parsed.value != .object) return;

    const key_value = parsed.value.object.get(key_field) orelse return;
    const key_str = try stringifyKey(allocator, key_value);

    const line_copy = try allocator.dupe(u8, line);

    const gop = try map.getOrPut(key_str);
    if (!gop.found_existing) {
        gop.value_ptr.* = .empty;
    } else {
        allocator.free(key_str);
    }
    try gop.value_ptr.append(allocator, line_copy);
}

fn stringifyKey(allocator: std.mem.Allocator, value: std.json.Value) ![]u8 {
    // Use dynamic allocation for keys that may be arbitrarily long (e.g., long strings)
    var result: std.ArrayListUnmanaged(u8) = .empty;
    errdefer result.deinit(allocator);
    jn_core.writeJsonValue(result.writer(allocator), value) catch |err| {
        return err;
    };
    return try result.toOwnedSlice(allocator);
}

fn processLeftSource(allocator: std.mem.Allocator, config: *const JoinConfig, right_map: *RightRecords) !void {
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    const left_key = config.getLeftKey();
    const right_key = config.getRightKey();

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;

        const left_parsed = std.json.parseFromSlice(std.json.Value, allocator, line, .{}) catch {
            writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
            writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
            continue;
        };
        defer left_parsed.deinit();

        if (left_parsed.value != .object) {
            writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
            writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
            continue;
        }

        const key_value = left_parsed.value.object.get(left_key) orelse {
            if (!config.inner_join) {
                writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
                writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
            }
            continue;
        };

        // Use dynamic allocation for keys to handle arbitrarily long values
        const key_str = stringifyKey(allocator, key_value) catch {
            if (!config.inner_join) {
                writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
                writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
            }
            continue;
        };
        defer allocator.free(key_str);

        if (right_map.get(key_str)) |right_records| {
            // Output one merged record per match
            for (right_records.items) |right_line| {
                outputMerged(allocator, left_parsed.value, right_line, right_key, writer);
            }
        } else if (!config.inner_join) {
            writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
            writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
        }
    }

    jn_core.flushWriter(writer);
}

fn outputMerged(allocator: std.mem.Allocator, left: std.json.Value, right_line: []const u8, right_key: []const u8, writer: anytype) void {
    const right_parsed = std.json.parseFromSlice(std.json.Value, allocator, right_line, .{}) catch return;
    defer right_parsed.deinit();

    if (right_parsed.value != .object) return;

    // Build merged output using dynamic allocation for arbitrarily large records
    var out_buf: std.ArrayListUnmanaged(u8) = .empty;
    defer out_buf.deinit(allocator);
    const w = out_buf.writer(allocator);

    w.writeByte('{') catch return;

    var first = true;

    // Write left fields
    var left_it = left.object.iterator();
    while (left_it.next()) |entry| {
        if (!first) w.writeByte(',') catch return;
        first = false;
        jn_core.writeJsonString(w, entry.key_ptr.*) catch return;
        w.writeByte(':') catch return;
        jn_core.writeJsonValue(w, entry.value_ptr.*) catch return;
    }

    // Write right fields (skip join key)
    var right_it = right_parsed.value.object.iterator();
    while (right_it.next()) |entry| {
        if (std.mem.eql(u8, entry.key_ptr.*, right_key)) continue;
        if (!first) w.writeByte(',') catch return;
        first = false;
        jn_core.writeJsonString(w, entry.key_ptr.*) catch return;
        w.writeByte(':') catch return;
        jn_core.writeJsonValue(w, entry.value_ptr.*) catch return;
    }

    w.writeByte('}') catch return;

    writer.writeAll(out_buf.items) catch |err| jn_core.handleWriteError(err);
    writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
}

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

fn getPositionalArg() ?[]const u8 {
    var args_iter = std.process.args();
    _ = args_iter.skip();

    while (args_iter.next()) |arg| {
        if (!std.mem.startsWith(u8, arg, "-")) return arg;
        if (std.mem.startsWith(u8, arg, "--")) continue;
    }
    return null;
}

fn printVersion() void {
    var buf: [256]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.print("jn-join {s}\n", .{VERSION}) catch {};
    jn_core.flushWriter(stdout);
}

fn printUsage() void {
    const usage =
        \\jn-join - Hash join for NDJSON streams
        \\
        \\Usage: jn-join [OPTIONS] <RIGHT_SOURCE>
        \\
        \\Joins stdin (left) with a file (right) using hash-based matching.
        \\
        \\Options:
        \\  --on=FIELD            Join key (same name on both sides)
        \\  --left-key=FIELD      Left side join key (if different)
        \\  --right-key=FIELD     Right side join key
        \\  --inner               Inner join (exclude unmatched left)
        \\  --help, -h            Show this help
        \\  --version             Show version
        \\
        \\Examples:
        \\  cat orders.ndjson | jn-join customers.ndjson --on=customer_id
        \\  cat orders.ndjson | jn-join customers.ndjson --left-key=cust_id --right-key=id
        \\
        \\Memory: Right source is loaded into memory.
        \\
    ;
    var buf: [2048]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.writeAll(usage) catch {};
    jn_core.flushWriter(stdout);
}

test "config defaults" {
    const config = JoinConfig{};
    try std.testing.expect(config.inner_join == false);
}
