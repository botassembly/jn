//! jn-edit: Edit JSON fields in NDJSON streams
//!
//! Usage:
//!   jn-edit [OPTIONS] [EDITS...]
//!
//! Edit Syntax:
//!   .path=value         Set path to string value
//!   .path:=value        Set path to raw JSON value (number, bool, null, object, array)
//!   --del .path         Delete a field
//!   --merge '{...}'     Merge JSON object (RFC 7396 style)
//!   --append .path val  Append value to array
//!   --prepend .path val Prepend value to array
//!
//! Examples:
//!   cat data.json | jn-edit .name=Alice
//!   cat data.json | jn-edit .count:=42 .active:=true
//!   cat data.json | jn-edit --del .temp --del .debug
//!   cat data.json | jn-edit --merge '{"user": {"name": "Bob"}}'
//!   cat data.json | jn-edit --append .tags admin

const std = @import("std");
const jn_core = @import("jn-core");

const VERSION = "0.1.0";
const MAX_EDITS = 64;
const MAX_PATH_DEPTH = 32;

/// Type of edit operation
const EditOp = enum {
    set_string, // .path=value
    set_json, // .path:=value
    delete, // --del .path
    append, // --append .path value
    prepend, // --prepend .path value
};

/// A single edit operation
const Edit = struct {
    op: EditOp,
    path: []const u8, // Path without leading dot
    value: []const u8, // Value to set (or empty for delete)
};

/// Parsed merge JSON (stored separately)
var merge_json: ?[]const u8 = null;

/// All edit operations
var edits: [MAX_EDITS]Edit = undefined;
var edit_count: usize = 0;

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    // Parse arguments
    const parse_result = parseArguments();
    if (parse_result == .exit) return;

    // Check we have something to do
    if (edit_count == 0 and merge_json == null) {
        jn_core.exitWithError("jn-edit: no edits specified\n  Use --help for usage", .{});
    }

    // Set up I/O
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    // Process each line
    var arena = std.heap.ArenaAllocator.init(allocator);
    defer arena.deinit();

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;

        _ = arena.reset(.retain_capacity);
        const arena_alloc = arena.allocator();

        // Parse JSON
        const parsed = jn_core.parseJsonLine(arena_alloc, line) orelse {
            // Invalid JSON - pass through unchanged
            writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
            writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
            continue;
        };

        var root = parsed.value;

        // Apply merge first (if specified)
        if (merge_json) |mj| {
            root = applyMerge(arena_alloc, root, mj) orelse root;
        }

        // Apply each edit
        for (edits[0..edit_count]) |edit| {
            root = applyEdit(arena_alloc, root, edit) orelse root;
        }

        // Write result
        jn_core.writeJsonValue(writer, root) catch |err| jn_core.handleWriteError(err);
        writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
    }

    jn_core.flushWriter(writer);
}

/// Result of argument parsing
const ParseResult = enum { ok, exit };

/// Parse command line arguments
fn parseArguments() ParseResult {
    var args_iter = std.process.args();
    _ = args_iter.skip(); // Skip program name

    while (args_iter.next()) |arg| {
        if (std.mem.eql(u8, arg, "--help") or std.mem.eql(u8, arg, "-h")) {
            printUsage();
            return .exit;
        }
        if (std.mem.eql(u8, arg, "--version")) {
            printVersion();
            return .exit;
        }
        if (std.mem.eql(u8, arg, "--del")) {
            // Next arg is the path
            if (args_iter.next()) |path| {
                addEdit(.delete, path, "");
            } else {
                jn_core.exitWithError("jn-edit: --del requires a path argument", .{});
            }
        } else if (std.mem.eql(u8, arg, "--merge")) {
            // Next arg is the JSON
            if (args_iter.next()) |json| {
                merge_json = json;
            } else {
                jn_core.exitWithError("jn-edit: --merge requires a JSON argument", .{});
            }
        } else if (std.mem.eql(u8, arg, "--append")) {
            // Next two args are path and value
            const path = args_iter.next() orelse {
                jn_core.exitWithError("jn-edit: --append requires path and value", .{});
            };
            const value = args_iter.next() orelse {
                jn_core.exitWithError("jn-edit: --append requires path and value", .{});
            };
            addEdit(.append, path, value);
        } else if (std.mem.eql(u8, arg, "--prepend")) {
            // Next two args are path and value
            const path = args_iter.next() orelse {
                jn_core.exitWithError("jn-edit: --prepend requires path and value", .{});
            };
            const value = args_iter.next() orelse {
                jn_core.exitWithError("jn-edit: --prepend requires path and value", .{});
            };
            addEdit(.prepend, path, value);
        } else if (std.mem.startsWith(u8, arg, ".")) {
            // Path assignment: .path=value or .path:=value
            if (std.mem.indexOf(u8, arg, ":=")) |idx| {
                // Raw JSON assignment
                const path = arg[0..idx];
                const value = arg[idx + 2 ..];
                addEdit(.set_json, path, value);
            } else if (std.mem.indexOf(u8, arg, "=")) |idx| {
                // String assignment
                const path = arg[0..idx];
                const value = arg[idx + 1 ..];
                addEdit(.set_string, path, value);
            } else {
                jn_core.exitWithError("jn-edit: invalid edit '{s}' - use .path=value or .path:=json", .{arg});
            }
        } else if (std.mem.startsWith(u8, arg, "--")) {
            // Unknown option
            jn_core.exitWithError("jn-edit: unknown option '{s}'", .{arg});
        } else {
            // Positional arg without leading dot
            jn_core.exitWithError("jn-edit: invalid path '{s}' - must start with '.'", .{arg});
        }
    }

    return .ok;
}

/// Add an edit operation
fn addEdit(op: EditOp, path: []const u8, value: []const u8) void {
    if (edit_count >= MAX_EDITS) {
        jn_core.exitWithError("jn-edit: too many edits (max {d})", .{MAX_EDITS});
    }

    // Validate path starts with dot
    if (!std.mem.startsWith(u8, path, ".")) {
        jn_core.exitWithError("jn-edit: invalid path '{s}' - must start with '.'", .{path});
    }

    edits[edit_count] = Edit{
        .op = op,
        .path = path[1..], // Strip leading dot
        .value = value,
    };
    edit_count += 1;
}

/// Apply a single edit operation to a JSON value
fn applyEdit(allocator: std.mem.Allocator, root: std.json.Value, edit: Edit) ?std.json.Value {
    return switch (edit.op) {
        .set_string => setPath(allocator, root, edit.path, .{ .string = edit.value }),
        .set_json => blk: {
            // Parse the JSON value
            const parsed = std.json.parseFromSlice(std.json.Value, allocator, edit.value, .{}) catch {
                // If parse fails, treat as string
                break :blk setPath(allocator, root, edit.path, .{ .string = edit.value });
            };
            break :blk setPath(allocator, root, edit.path, parsed.value);
        },
        .delete => deletePath(allocator, root, edit.path),
        .append => appendToArray(allocator, root, edit.path, edit.value),
        .prepend => prependToArray(allocator, root, edit.path, edit.value),
    };
}

/// Parse a path segment, handling array indices like "tags[0]"
const PathSegment = struct {
    key: []const u8,
    array_index: ?usize,
};

fn parsePathSegment(segment: []const u8) PathSegment {
    // Check for array index notation: key[N]
    if (std.mem.indexOf(u8, segment, "[")) |bracket_start| {
        if (std.mem.indexOf(u8, segment, "]")) |bracket_end| {
            if (bracket_end > bracket_start + 1) {
                const key = segment[0..bracket_start];
                const index_str = segment[bracket_start + 1 .. bracket_end];
                const index = std.fmt.parseInt(usize, index_str, 10) catch return .{ .key = segment, .array_index = null };
                return .{ .key = key, .array_index = index };
            }
        }
    }
    return .{ .key = segment, .array_index = null };
}

/// Set a value at a path, creating intermediate objects as needed
fn setPath(allocator: std.mem.Allocator, root: std.json.Value, path: []const u8, value: std.json.Value) ?std.json.Value {
    if (path.len == 0) {
        return value;
    }

    // Split path into segments
    var segments: [MAX_PATH_DEPTH]PathSegment = undefined;
    var segment_count: usize = 0;

    var iter = std.mem.splitScalar(u8, path, '.');
    while (iter.next()) |seg| {
        if (seg.len == 0) continue;
        if (segment_count >= MAX_PATH_DEPTH) return null;
        segments[segment_count] = parsePathSegment(seg);
        segment_count += 1;
    }

    if (segment_count == 0) return value;

    return setPathRecursive(allocator, root, segments[0..segment_count], value);
}

fn setPathRecursive(allocator: std.mem.Allocator, current: std.json.Value, segments: []const PathSegment, value: std.json.Value) ?std.json.Value {
    if (segments.len == 0) {
        return value;
    }

    const seg = segments[0];
    const remaining = segments[1..];

    // Handle array index on current segment
    if (seg.array_index) |idx| {
        // First navigate to the object key, then into the array
        if (current != .object) {
            // Create object
            var new_obj = std.json.ObjectMap.init(allocator);
            const arr_value = createArrayWithValue(allocator, idx, value, remaining);
            new_obj.put(seg.key, arr_value) catch return null;
            return .{ .object = new_obj };
        }

        const obj = current.object;
        if (obj.get(seg.key)) |existing| {
            if (existing == .array) {
                var arr = std.json.Array.init(allocator);
                // Copy existing items
                for (existing.array.items) |item| {
                    arr.append(item) catch return null;
                }
                // Expand array if needed
                while (arr.items.len <= idx) {
                    arr.append(.null) catch return null;
                }
                if (remaining.len == 0) {
                    arr.items[idx] = value;
                } else {
                    arr.items[idx] = setPathRecursive(allocator, arr.items[idx], remaining, value) orelse return null;
                }
                var new_obj = cloneObject(allocator, obj) orelse return null;
                new_obj.put(seg.key, .{ .array = arr }) catch return null;
                return .{ .object = new_obj };
            }
        }

        // Create new array
        var new_obj = cloneObject(allocator, obj) orelse return null;
        const arr_value = createArrayWithValue(allocator, idx, value, remaining);
        new_obj.put(seg.key, arr_value) catch return null;
        return .{ .object = new_obj };
    }

    // Regular object key navigation
    if (current != .object) {
        // Create object structure
        var new_obj = std.json.ObjectMap.init(allocator);
        const child_value = if (remaining.len == 0) value else setPathRecursive(allocator, .null, remaining, value) orelse return null;
        new_obj.put(seg.key, child_value) catch return null;
        return .{ .object = new_obj };
    }

    const obj = current.object;
    var new_obj = cloneObject(allocator, obj) orelse return null;

    if (remaining.len == 0) {
        // Set the value directly
        new_obj.put(seg.key, value) catch return null;
    } else {
        // Recurse
        const existing = obj.get(seg.key) orelse .null;
        const new_value = setPathRecursive(allocator, existing, remaining, value) orelse return null;
        new_obj.put(seg.key, new_value) catch return null;
    }

    return .{ .object = new_obj };
}

/// Clone an ObjectMap by copying all entries
fn cloneObject(allocator: std.mem.Allocator, obj: std.json.ObjectMap) ?std.json.ObjectMap {
    var new_obj = std.json.ObjectMap.init(allocator);
    var it = obj.iterator();
    while (it.next()) |entry| {
        new_obj.put(entry.key_ptr.*, entry.value_ptr.*) catch return null;
    }
    return new_obj;
}

fn createArrayWithValue(allocator: std.mem.Allocator, idx: usize, value: std.json.Value, remaining: []const PathSegment) std.json.Value {
    var arr = std.json.Array.init(allocator);
    var i: usize = 0;
    while (i <= idx) : (i += 1) {
        if (i == idx) {
            const v = if (remaining.len == 0) value else setPathRecursive(allocator, .null, remaining, value) orelse .null;
            arr.append(v) catch {};
        } else {
            arr.append(.null) catch {};
        }
    }
    return .{ .array = arr };
}

/// Delete a value at a path
fn deletePath(allocator: std.mem.Allocator, root: std.json.Value, path: []const u8) ?std.json.Value {
    if (path.len == 0 or root != .object) {
        return root;
    }

    // Split path
    var segments: [MAX_PATH_DEPTH][]const u8 = undefined;
    var segment_count: usize = 0;

    var iter = std.mem.splitScalar(u8, path, '.');
    while (iter.next()) |seg| {
        if (seg.len == 0) continue;
        if (segment_count >= MAX_PATH_DEPTH) return root;
        segments[segment_count] = seg;
        segment_count += 1;
    }

    if (segment_count == 0) return root;

    return deletePathRecursive(allocator, root, segments[0..segment_count]);
}

fn deletePathRecursive(allocator: std.mem.Allocator, current: std.json.Value, segments: []const []const u8) ?std.json.Value {
    if (current != .object) return current;

    const key = segments[0];
    const remaining = segments[1..];

    const obj = current.object;
    var new_obj = std.json.ObjectMap.init(allocator);
    var it = obj.iterator();

    while (it.next()) |entry| {
        if (std.mem.eql(u8, entry.key_ptr.*, key)) {
            if (remaining.len == 0) {
                // Skip this key (delete it)
                continue;
            } else {
                // Recurse
                const new_child = deletePathRecursive(allocator, entry.value_ptr.*, remaining) orelse return null;
                new_obj.put(entry.key_ptr.*, new_child) catch return null;
            }
        } else {
            new_obj.put(entry.key_ptr.*, entry.value_ptr.*) catch return null;
        }
    }

    return .{ .object = new_obj };
}

/// Apply merge patch (RFC 7396 style)
fn applyMerge(allocator: std.mem.Allocator, root: std.json.Value, merge_str: []const u8) ?std.json.Value {
    const parsed = std.json.parseFromSlice(std.json.Value, allocator, merge_str, .{}) catch {
        return null;
    };

    return mergeObjects(allocator, root, parsed.value);
}

fn mergeObjects(allocator: std.mem.Allocator, target: std.json.Value, patch: std.json.Value) ?std.json.Value {
    if (patch != .object) {
        return patch;
    }

    if (target != .object) {
        return patch;
    }

    var result = cloneObject(allocator, target.object) orelse return null;
    var patch_iter = patch.object.iterator();

    while (patch_iter.next()) |entry| {
        const key = entry.key_ptr.*;
        const patch_value = entry.value_ptr.*;

        if (result.get(key)) |existing| {
            // Merge recursively for objects
            if (patch_value == .object and existing == .object) {
                const merged = mergeObjects(allocator, existing, patch_value) orelse return null;
                result.put(key, merged) catch return null;
            } else {
                result.put(key, patch_value) catch return null;
            }
        } else {
            result.put(key, patch_value) catch return null;
        }
    }

    return .{ .object = result };
}

/// Append a value to an array at path
fn appendToArray(allocator: std.mem.Allocator, root: std.json.Value, path: []const u8, value_str: []const u8) ?std.json.Value {
    // Parse value (try as JSON first, fall back to string)
    const value = std.json.parseFromSlice(std.json.Value, allocator, value_str, .{}) catch null;
    const actual_value = if (value) |v| v.value else std.json.Value{ .string = value_str };

    return modifyArray(allocator, root, path, actual_value, .append);
}

/// Prepend a value to an array at path
fn prependToArray(allocator: std.mem.Allocator, root: std.json.Value, path: []const u8, value_str: []const u8) ?std.json.Value {
    const value = std.json.parseFromSlice(std.json.Value, allocator, value_str, .{}) catch null;
    const actual_value = if (value) |v| v.value else std.json.Value{ .string = value_str };

    return modifyArray(allocator, root, path, actual_value, .prepend);
}

const ArrayOp = enum { append, prepend };

fn modifyArray(allocator: std.mem.Allocator, root: std.json.Value, path: []const u8, value: std.json.Value, op: ArrayOp) ?std.json.Value {
    if (path.len == 0 or root != .object) return root;

    // Split path
    var segments: [MAX_PATH_DEPTH][]const u8 = undefined;
    var segment_count: usize = 0;

    var iter = std.mem.splitScalar(u8, path, '.');
    while (iter.next()) |seg| {
        if (seg.len == 0) continue;
        if (segment_count >= MAX_PATH_DEPTH) return root;
        segments[segment_count] = seg;
        segment_count += 1;
    }

    if (segment_count == 0) return root;

    return modifyArrayRecursive(allocator, root, segments[0..segment_count], value, op);
}

fn modifyArrayRecursive(allocator: std.mem.Allocator, current: std.json.Value, segments: []const []const u8, value: std.json.Value, op: ArrayOp) ?std.json.Value {
    if (current != .object) return current;

    const key = segments[0];
    const remaining = segments[1..];

    const obj = current.object;
    var new_obj = cloneObject(allocator, obj) orelse return null;

    if (remaining.len == 0) {
        // This is the target - modify the array
        if (obj.get(key)) |existing| {
            if (existing == .array) {
                var arr = std.json.Array.init(allocator);
                switch (op) {
                    .prepend => arr.append(value) catch return null,
                    .append => {},
                }
                for (existing.array.items) |item| {
                    arr.append(item) catch return null;
                }
                switch (op) {
                    .append => arr.append(value) catch return null,
                    .prepend => {},
                }
                new_obj.put(key, .{ .array = arr }) catch return null;
            } else {
                // Not an array - create one with existing value and new value
                var arr = std.json.Array.init(allocator);
                switch (op) {
                    .append => {
                        arr.append(existing) catch return null;
                        arr.append(value) catch return null;
                    },
                    .prepend => {
                        arr.append(value) catch return null;
                        arr.append(existing) catch return null;
                    },
                }
                new_obj.put(key, .{ .array = arr }) catch return null;
            }
        } else {
            // Key doesn't exist - create array with single value
            var arr = std.json.Array.init(allocator);
            arr.append(value) catch return null;
            new_obj.put(key, .{ .array = arr }) catch return null;
        }
    } else {
        // Recurse
        if (obj.get(key)) |child| {
            const new_child = modifyArrayRecursive(allocator, child, remaining, value, op) orelse return null;
            new_obj.put(key, new_child) catch return null;
        }
    }

    return .{ .object = new_obj };
}

/// Print version
fn printVersion() void {
    var buf: [256]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.print("jn-edit {s}\n", .{VERSION}) catch {};
    jn_core.flushWriter(stdout);
}

/// Print usage
fn printUsage() void {
    const usage =
        \\jn-edit - Edit JSON fields in NDJSON streams
        \\
        \\Usage: jn-edit [OPTIONS] [EDITS...]
        \\
        \\Edit Syntax:
        \\  .path=value         Set path to string value
        \\  .path:=value        Set path to raw JSON (number, bool, null, array, object)
        \\  --del .path         Delete a field
        \\  --merge '{"k":"v"}' Merge JSON object (RFC 7396 style)
        \\  --append .path val  Append value to array
        \\  --prepend .path val Prepend value to array
        \\
        \\Options:
        \\  --help, -h          Show this help
        \\  --version           Show version
        \\
        \\Examples:
        \\  # Set string value
        \\  cat data.json | jn-edit .name=Alice
        \\
        \\  # Set JSON values (number, bool, null)
        \\  cat data.json | jn-edit .count:=42 .active:=true .temp:=null
        \\
        \\  # Set nested path
        \\  cat data.json | jn-edit .user.profile.name=Bob
        \\
        \\  # Set array element
        \\  cat data.json | jn-edit '.tags[0]=first'
        \\
        \\  # Delete fields
        \\  cat data.json | jn-edit --del .temp --del .debug
        \\
        \\  # Merge objects
        \\  cat data.json | jn-edit --merge '{"user": {"name": "Eve"}}'
        \\
        \\  # Array operations
        \\  cat data.json | jn-edit --append .tags admin
        \\  cat data.json | jn-edit --prepend .tags owner
        \\
        \\  # Multiple edits
        \\  cat data.json | jn-edit .name=Bob .age:=30 --del .temp
        \\
    ;
    var buf: [4096]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.writeAll(usage) catch {};
    jn_core.flushWriter(stdout);
}

// ============================================================================
// Tests
// ============================================================================

test "parsePathSegment handles simple key" {
    const seg = parsePathSegment("name");
    try std.testing.expectEqualStrings("name", seg.key);
    try std.testing.expect(seg.array_index == null);
}

test "parsePathSegment handles array index" {
    const seg = parsePathSegment("tags[0]");
    try std.testing.expectEqualStrings("tags", seg.key);
    try std.testing.expectEqual(@as(usize, 0), seg.array_index.?);

    const seg2 = parsePathSegment("items[42]");
    try std.testing.expectEqualStrings("items", seg2.key);
    try std.testing.expectEqual(@as(usize, 42), seg2.array_index.?);
}

test "setPath creates nested objects" {
    const allocator = std.testing.allocator;
    var arena = std.heap.ArenaAllocator.init(allocator);
    defer arena.deinit();
    const a = arena.allocator();

    // Start with empty object
    const obj = std.json.ObjectMap.init(a);
    const root = std.json.Value{ .object = obj };

    // Set nested path
    const result = setPath(a, root, "user.name", .{ .string = "Alice" });
    try std.testing.expect(result != null);
    try std.testing.expect(result.? == .object);

    const user = result.?.object.get("user");
    try std.testing.expect(user != null);
    try std.testing.expect(user.? == .object);

    const name = user.?.object.get("name");
    try std.testing.expect(name != null);
    try std.testing.expectEqualStrings("Alice", name.?.string);
}

test "deletePath removes field" {
    const allocator = std.testing.allocator;
    var arena = std.heap.ArenaAllocator.init(allocator);
    defer arena.deinit();
    const a = arena.allocator();

    // Create object with field
    var obj = std.json.ObjectMap.init(a);
    obj.put("name", .{ .string = "Alice" }) catch unreachable;
    obj.put("temp", .{ .string = "delete me" }) catch unreachable;
    const root = std.json.Value{ .object = obj };

    // Delete field
    const result = deletePath(a, root, "temp");
    try std.testing.expect(result != null);
    try std.testing.expect(result.?.object.get("name") != null);
    try std.testing.expect(result.?.object.get("temp") == null);
}
