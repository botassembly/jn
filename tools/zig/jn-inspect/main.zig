//! jn-inspect: Profile discovery and schema inference for JN
//!
//! Discovers available profiles and infers schema from NDJSON data.
//!
//! Usage:
//!   jn-inspect profiles [--type=TYPE]    List available profiles
//!   jn-inspect schema [--sample=N]       Infer schema from stdin
//!   jn-inspect profile @NAME             Show profile details
//!
//! Options:
//!   --format={json,text}    Output format (default: text)
//!   --type=TYPE             Filter profiles by type (http, duckdb, etc.)
//!   --sample=N              Sample first N records for schema (default: 100)
//!   --help, -h              Show this help
//!   --version               Show version
//!
//! Examples:
//!   jn-inspect profiles
//!   jn-inspect profiles --type=http
//!   cat data.ndjson | jn-inspect schema
//!   jn-inspect profile @gmail/inbox

const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");

const VERSION = "0.1.0";
const DEFAULT_SAMPLE: usize = 100;

/// Schema type for a field
const SchemaType = enum {
    string,
    number,
    boolean,
    null_type,
    array,
    object,
    mixed,

    fn fromJsonType(value: std.json.Value) SchemaType {
        return switch (value) {
            .null => .null_type,
            .bool => .boolean,
            .integer, .float, .number_string => .number,
            .string => .string,
            .array => .array,
            .object => .object,
        };
    }

    fn name(self: SchemaType) []const u8 {
        return switch (self) {
            .string => "string",
            .number => "number",
            .boolean => "boolean",
            .null_type => "null",
            .array => "array",
            .object => "object",
            .mixed => "mixed",
        };
    }
};

/// Field schema information
const FieldSchema = struct {
    seen_count: u64 = 0,
    types_seen: u8 = 0, // Bitmap of SchemaType
    nullable: bool = false,
    sample_values: std.ArrayListUnmanaged([]const u8) = .empty,
    allocator: std.mem.Allocator = undefined,

    const TYPE_STRING: u8 = 1;
    const TYPE_NUMBER: u8 = 2;
    const TYPE_BOOLEAN: u8 = 4;
    const TYPE_NULL: u8 = 8;
    const TYPE_ARRAY: u8 = 16;
    const TYPE_OBJECT: u8 = 32;

    fn init(allocator: std.mem.Allocator) FieldSchema {
        return .{
            .allocator = allocator,
        };
    }

    fn deinit(self: *FieldSchema) void {
        for (self.sample_values.items) |v| {
            self.allocator.free(v);
        }
        self.sample_values.deinit(self.allocator);
    }

    fn addType(self: *FieldSchema, schema_type: SchemaType) void {
        const bit: u8 = switch (schema_type) {
            .string => TYPE_STRING,
            .number => TYPE_NUMBER,
            .boolean => TYPE_BOOLEAN,
            .null_type => TYPE_NULL,
            .array => TYPE_ARRAY,
            .object => TYPE_OBJECT,
            .mixed => 0,
        };
        self.types_seen |= bit;
        if (schema_type == .null_type) self.nullable = true;
    }

    fn primaryType(self: FieldSchema) SchemaType {
        const count = @popCount(self.types_seen);
        if (count == 0) return .null_type;
        if (count > 2 or (count == 2 and !self.nullable)) return .mixed;

        // Return the primary non-null type
        if (self.types_seen & TYPE_STRING != 0) return .string;
        if (self.types_seen & TYPE_NUMBER != 0) return .number;
        if (self.types_seen & TYPE_BOOLEAN != 0) return .boolean;
        if (self.types_seen & TYPE_ARRAY != 0) return .array;
        if (self.types_seen & TYPE_OBJECT != 0) return .object;
        return .null_type;
    }
};

/// Schema inference state
const SchemaState = struct {
    allocator: std.mem.Allocator,
    record_count: u64 = 0,
    fields: std.StringHashMap(FieldSchema),

    fn init(allocator: std.mem.Allocator) SchemaState {
        return .{
            .allocator = allocator,
            .fields = std.StringHashMap(FieldSchema).init(allocator),
        };
    }

    fn deinit(self: *SchemaState) void {
        var iter = self.fields.iterator();
        while (iter.next()) |entry| {
            self.allocator.free(entry.key_ptr.*);
            entry.value_ptr.deinit();
        }
        self.fields.deinit();
    }

    fn processRecord(self: *SchemaState, value: std.json.Value) !void {
        self.record_count += 1;

        switch (value) {
            .object => |obj| {
                var obj_iter = obj.iterator();
                while (obj_iter.next()) |entry| {
                    try self.updateField(entry.key_ptr.*, entry.value_ptr.*);
                }
            },
            else => {},
        }
    }

    fn updateField(self: *SchemaState, field_name: []const u8, value: std.json.Value) !void {
        const result = self.fields.getOrPut(field_name) catch return;
        if (!result.found_existing) {
            result.key_ptr.* = try self.allocator.dupe(u8, field_name);
            result.value_ptr.* = FieldSchema.init(self.allocator);
        }

        const schema = result.value_ptr;
        schema.seen_count += 1;
        schema.addType(SchemaType.fromJsonType(value));

        // Capture sample values (up to 3)
        if (schema.sample_values.items.len < 3) {
            var buf: [128]u8 = undefined;
            const sample = switch (value) {
                .string => |s| blk: {
                    const len = @min(s.len, 50);
                    break :blk self.allocator.dupe(u8, s[0..len]) catch return;
                },
                .integer => |i| blk: {
                    const n = std.fmt.bufPrint(&buf, "{d}", .{i}) catch return;
                    break :blk self.allocator.dupe(u8, n) catch return;
                },
                .float => |f| blk: {
                    const n = std.fmt.bufPrint(&buf, "{d:.4}", .{f}) catch return;
                    break :blk self.allocator.dupe(u8, n) catch return;
                },
                .bool => |b| blk: {
                    break :blk self.allocator.dupe(u8, if (b) "true" else "false") catch return;
                },
                .null => self.allocator.dupe(u8, "null") catch return,
                else => return,
            };
            schema.sample_values.append(schema.allocator, sample) catch {
                self.allocator.free(sample);
            };
        }
    }
};

/// Profile info for display
const ProfileInfo = struct {
    source: []const u8,
    profile_type: []const u8,
    name: []const u8,
    path: []const u8,
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

    // Get subcommand
    const subcommand = getPositionalArg(0) orelse {
        printUsage();
        return;
    };

    // Get output format
    const json_format = if (args.get("format", null)) |fmt|
        std.mem.eql(u8, fmt, "json")
    else
        false;

    // Route to subcommand
    if (std.mem.eql(u8, subcommand, "profiles")) {
        const type_filter = args.get("type", null);
        listProfiles(allocator, type_filter, json_format);
    } else if (std.mem.eql(u8, subcommand, "schema")) {
        var sample_size: usize = DEFAULT_SAMPLE;
        if (args.get("sample", null)) |sample_str| {
            sample_size = std.fmt.parseInt(usize, sample_str, 10) catch DEFAULT_SAMPLE;
        }
        try inferSchema(allocator, sample_size, json_format);
    } else if (std.mem.eql(u8, subcommand, "profile")) {
        const profile_ref = getPositionalArg(1) orelse {
            jn_core.exitWithError("jn-inspect: missing profile reference\nUsage: jn-inspect profile @NAME", .{});
        };
        showProfile(allocator, profile_ref, json_format);
    } else {
        jn_core.exitWithError("jn-inspect: unknown subcommand: {s}\nUse --help for usage", .{subcommand});
    }
}

/// Get positional argument by index (skipping flags)
fn getPositionalArg(index: usize) ?[]const u8 {
    var args_iter = std.process.args();
    _ = args_iter.skip(); // Skip program name

    var pos_count: usize = 0;
    while (args_iter.next()) |arg| {
        // Skip flags
        if (std.mem.startsWith(u8, arg, "-")) continue;
        if (pos_count == index) return arg;
        pos_count += 1;
    }
    return null;
}

/// List available profiles
fn listProfiles(allocator: std.mem.Allocator, type_filter: ?[]const u8, json_format: bool) void {
    var profiles: std.ArrayListUnmanaged(ProfileInfo) = .empty;
    defer {
        // Free allocated strings in each ProfileInfo to avoid memory leak
        for (profiles.items) |p| {
            allocator.free(p.name);
            allocator.free(p.path);
        }
        profiles.deinit(allocator);
    }

    // Get profile directories
    const home = std.posix.getenv("HOME");
    const jn_home = std.posix.getenv("JN_HOME");

    // Build base paths - track allocated ones for cleanup
    const user_base: ?[]const u8 = if (home) |h|
        std.fmt.allocPrint(allocator, "{s}/.local/jn/profiles", .{h}) catch null
    else
        null;
    defer if (user_base) |ub| allocator.free(ub);

    const bundled_base: ?[]const u8 = if (jn_home) |jh|
        std.fmt.allocPrint(allocator, "{s}/profiles", .{jh}) catch null
    else
        null;
    defer if (bundled_base) |bb| allocator.free(bb);

    // Scan each source
    const sources = [_]struct { name: []const u8, base: ?[]const u8 }{
        .{ .name = "project", .base = ".jn/profiles" },
        .{ .name = "user", .base = user_base },
        .{ .name = "bundled", .base = bundled_base },
    };

    for (sources) |source| {
        if (source.base) |base| {
            scanProfileDir(allocator, &profiles, source.name, base, type_filter);
        }
    }

    // Output
    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    if (json_format) {
        outputProfilesJson(writer, profiles.items);
    } else {
        outputProfilesText(writer, profiles.items);
    }

    jn_core.flushWriter(writer);
}

/// Scan a profile directory for profiles
fn scanProfileDir(
    allocator: std.mem.Allocator,
    profiles: *std.ArrayListUnmanaged(ProfileInfo),
    source_name: []const u8,
    base_path: []const u8,
    type_filter: ?[]const u8,
) void {
    // Open base directory
    var dir = std.fs.cwd().openDir(base_path, .{ .iterate = true }) catch return;
    defer dir.close();

    // Iterate type directories
    var type_iter = dir.iterate();
    while (type_iter.next() catch null) |entry| {
        if (entry.kind != .directory) continue;

        // Apply type filter
        if (type_filter) |filter| {
            if (!std.mem.eql(u8, entry.name, filter)) continue;
        }

        // Scan this type directory
        const type_path = std.fmt.allocPrint(allocator, "{s}/{s}", .{ base_path, entry.name }) catch continue;
        defer allocator.free(type_path);

        var type_dir = std.fs.cwd().openDir(type_path, .{ .iterate = true }) catch continue;
        defer type_dir.close();

        scanProfileTypeDir(allocator, profiles, source_name, entry.name, type_path, &type_dir, "");
    }
}

/// Recursively scan a profile type directory
fn scanProfileTypeDir(
    allocator: std.mem.Allocator,
    profiles: *std.ArrayListUnmanaged(ProfileInfo),
    source_name: []const u8,
    profile_type: []const u8,
    base_path: []const u8,
    dir: *std.fs.Dir,
    prefix: []const u8,
) void {
    var iter = dir.iterate();
    while (iter.next() catch null) |entry| {
        // Skip _meta.json
        if (std.mem.eql(u8, entry.name, "_meta.json")) continue;

        if (entry.kind == .file and std.mem.endsWith(u8, entry.name, ".json")) {
            // Profile file
            const name_without_ext = entry.name[0 .. entry.name.len - 5];
            const full_name = if (prefix.len > 0)
                std.fmt.allocPrint(allocator, "{s}/{s}", .{ prefix, name_without_ext }) catch continue
            else
                allocator.dupe(u8, name_without_ext) catch continue;

            const full_path = std.fmt.allocPrint(allocator, "{s}/{s}", .{ base_path, entry.name }) catch {
                allocator.free(full_name);
                continue;
            };

            profiles.append(allocator, .{
                .source = source_name,
                .profile_type = profile_type,
                .name = full_name,
                .path = full_path,
            }) catch {
                allocator.free(full_name);
                allocator.free(full_path);
            };
        } else if (entry.kind == .directory) {
            // Nested directory - recurse
            const new_prefix = if (prefix.len > 0)
                std.fmt.allocPrint(allocator, "{s}/{s}", .{ prefix, entry.name }) catch continue
            else
                allocator.dupe(u8, entry.name) catch continue;
            defer allocator.free(new_prefix);

            const sub_path = std.fmt.allocPrint(allocator, "{s}/{s}", .{ base_path, entry.name }) catch continue;
            defer allocator.free(sub_path);

            var sub_dir = std.fs.cwd().openDir(sub_path, .{ .iterate = true }) catch continue;
            defer sub_dir.close();

            scanProfileTypeDir(allocator, profiles, source_name, profile_type, sub_path, &sub_dir, new_prefix);
        }
    }
}

/// Output profiles as JSON
fn outputProfilesJson(writer: anytype, profiles: []const ProfileInfo) void {
    writer.writeByte('[') catch return;
    for (profiles, 0..) |p, i| {
        if (i > 0) writer.writeByte(',') catch {};
        writer.writeAll("{") catch {};
        writer.writeAll("\"source\":") catch {};
        jn_core.writeJsonString(writer, p.source) catch {};
        writer.writeAll(",\"type\":") catch {};
        jn_core.writeJsonString(writer, p.profile_type) catch {};
        writer.writeAll(",\"name\":") catch {};
        jn_core.writeJsonString(writer, p.name) catch {};
        writer.writeAll(",\"ref\":\"@") catch {};
        // Reference format is @<namespace>/<name>, not @<type>/<namespace>/<name>
        writer.writeAll(p.name) catch {};
        writer.writeAll("\"}") catch {};
    }
    writer.writeAll("]\n") catch {};
}

/// Output profiles as text
fn outputProfilesText(writer: anytype, profiles: []const ProfileInfo) void {
    if (profiles.len == 0) {
        writer.writeAll("No profiles found.\n") catch {};
        return;
    }

    writer.writeAll("=== Available Profiles ===\n\n") catch {};

    // Group by type
    var current_type: ?[]const u8 = null;
    for (profiles) |p| {
        if (current_type == null or !std.mem.eql(u8, current_type.?, p.profile_type)) {
            if (current_type != null) writer.writeByte('\n') catch {};
            writer.writeAll("[") catch {};
            writer.writeAll(p.profile_type) catch {};
            writer.writeAll("]\n") catch {};
            current_type = p.profile_type;
        }

        // Reference format is @<namespace>/<name>, not @<type>/<namespace>/<name>
        writer.writeAll("  @") catch {};
        writer.writeAll(p.name) catch {};
        writer.writeAll("  (") catch {};
        writer.writeAll(p.source) catch {};
        writer.writeAll(")\n") catch {};
    }
}

/// Infer schema from NDJSON input
fn inferSchema(allocator: std.mem.Allocator, sample_size: usize, json_format: bool) !void {
    var state = SchemaState.init(allocator);
    defer state.deinit();

    var arena = std.heap.ArenaAllocator.init(allocator);
    defer arena.deinit();

    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;
        if (sample_size > 0 and state.record_count >= sample_size) break;

        if (jn_core.parseJsonLine(arena.allocator(), line)) |parsed| {
            defer parsed.deinit();
            try state.processRecord(parsed.value);
        }

        _ = arena.reset(.retain_capacity);
    }

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    if (json_format) {
        outputSchemaJson(writer, &state);
    } else {
        outputSchemaText(writer, &state);
    }

    jn_core.flushWriter(writer);
}

/// Output schema as JSON
fn outputSchemaJson(writer: anytype, state: *SchemaState) void {
    writer.writeAll("{\"record_count\":") catch return;
    writer.print("{d}", .{state.record_count}) catch return;
    writer.writeAll(",\"fields\":{") catch return;

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

    var first = true;
    for (names.items) |name| {
        if (state.fields.get(name)) |schema| {
            if (!first) writer.writeByte(',') catch {};
            first = false;

            jn_core.writeJsonString(writer, name) catch {};
            writer.writeAll(":{") catch {};
            writer.writeAll("\"type\":") catch {};
            jn_core.writeJsonString(writer, schema.primaryType().name()) catch {};
            writer.print(",\"nullable\":{s}", .{if (schema.nullable) "true" else "false"}) catch {};
            writer.print(",\"count\":{d}", .{schema.seen_count}) catch {};

            if (schema.sample_values.items.len > 0) {
                writer.writeAll(",\"samples\":[") catch {};
                for (schema.sample_values.items, 0..) |s, i| {
                    if (i > 0) writer.writeByte(',') catch {};
                    jn_core.writeJsonString(writer, s) catch {};
                }
                writer.writeByte(']') catch {};
            }

            writer.writeByte('}') catch {};
        }
    }

    writer.writeAll("}}\n") catch {};
}

/// Output schema as text
fn outputSchemaText(writer: anytype, state: *SchemaState) void {
    writer.writeAll("=== Schema Inference ===\n\n") catch {};
    writer.print("Records sampled: {d}\n", .{state.record_count}) catch {};
    writer.print("Fields found:    {d}\n\n", .{state.fields.count()}) catch {};

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

    writer.writeAll("--- Fields ---\n\n") catch {};

    for (names.items) |name| {
        if (state.fields.get(name)) |schema| {
            writer.writeAll(name) catch {};
            writer.writeAll(": ") catch {};
            writer.writeAll(schema.primaryType().name()) catch {};
            if (schema.nullable) writer.writeAll("?") catch {};

            const freq = if (state.record_count > 0)
                @as(f64, @floatFromInt(schema.seen_count)) / @as(f64, @floatFromInt(state.record_count)) * 100.0
            else
                0.0;
            writer.print(" ({d:.0}% present)", .{freq}) catch {};
            writer.writeByte('\n') catch {};

            // Show sample values
            if (schema.sample_values.items.len > 0) {
                writer.writeAll("  samples: ") catch {};
                for (schema.sample_values.items, 0..) |s, i| {
                    if (i > 0) writer.writeAll(", ") catch {};
                    writer.writeAll(s) catch {};
                }
                writer.writeByte('\n') catch {};
            }
        }
    }
}

/// Show profile details
fn showProfile(allocator: std.mem.Allocator, profile_ref: []const u8, json_format: bool) void {
    _ = allocator;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    // Parse profile reference
    if (!std.mem.startsWith(u8, profile_ref, "@")) {
        jn_core.exitWithError("jn-inspect: profile reference must start with @", .{});
    }

    const ref = profile_ref[1..]; // Skip @

    if (json_format) {
        writer.writeAll("{\"ref\":") catch {};
        jn_core.writeJsonString(writer, profile_ref) catch {};
        writer.writeAll(",\"status\":\"not_implemented\"}\n") catch {};
    } else {
        writer.writeAll("Profile: ") catch {};
        writer.writeAll(ref) catch {};
        writer.writeAll("\n\nNote: Profile loading not yet implemented.\n") catch {};
        writer.writeAll("Use `jn cat @") catch {};
        writer.writeAll(ref) catch {};
        writer.writeAll("` to access the profile.\n") catch {};
    }

    jn_core.flushWriter(writer);
}

/// Print version
fn printVersion() void {
    var buf: [256]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.print("jn-inspect {s}\n", .{VERSION}) catch {};
    jn_core.flushWriter(stdout);
}

/// Print usage information
fn printUsage() void {
    const usage =
        \\jn-inspect - Profile discovery and schema inference
        \\
        \\Usage:
        \\  jn-inspect profiles [OPTIONS]    List available profiles
        \\  jn-inspect schema [OPTIONS]      Infer schema from stdin
        \\  jn-inspect profile @NAME         Show profile details
        \\
        \\Options:
        \\  --format={json,text}    Output format (default: text)
        \\  --type=TYPE             Filter profiles by type (http, duckdb, etc.)
        \\  --sample=N              Sample first N records for schema (default: 100)
        \\  --help, -h              Show this help
        \\  --version               Show version
        \\
        \\Profile Sources (in priority order):
        \\  1. Project:  .jn/profiles/
        \\  2. User:     ~/.local/jn/profiles/
        \\  3. Bundled:  $JN_HOME/profiles/
        \\
        \\Examples:
        \\  jn-inspect profiles
        \\  jn-inspect profiles --type=http
        \\  jn-inspect profiles --format=json
        \\  cat data.ndjson | jn-inspect schema
        \\  cat data.ndjson | jn-inspect schema --sample=1000
        \\
    ;
    var buf: [2048]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.writeAll(usage) catch {};
    jn_core.flushWriter(stdout);
}

// Tests
test "SchemaType.fromJsonType" {
    try std.testing.expectEqual(SchemaType.null_type, SchemaType.fromJsonType(.null));
    try std.testing.expectEqual(SchemaType.boolean, SchemaType.fromJsonType(.{ .bool = true }));
    try std.testing.expectEqual(SchemaType.number, SchemaType.fromJsonType(.{ .integer = 42 }));
}

test "FieldSchema.addType" {
    var schema = FieldSchema.init(std.testing.allocator);
    defer schema.deinit();

    schema.addType(.string);
    try std.testing.expect(schema.types_seen & FieldSchema.TYPE_STRING != 0);
    try std.testing.expect(!schema.nullable);

    schema.addType(.null_type);
    try std.testing.expect(schema.nullable);
}

test "FieldSchema.primaryType" {
    var schema = FieldSchema.init(std.testing.allocator);
    defer schema.deinit();

    schema.addType(.string);
    try std.testing.expectEqual(SchemaType.string, schema.primaryType());

    schema.addType(.null_type);
    try std.testing.expectEqual(SchemaType.string, schema.primaryType()); // Still string (nullable)

    schema.addType(.number);
    try std.testing.expectEqual(SchemaType.mixed, schema.primaryType()); // Now mixed
}
