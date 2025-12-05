const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");
const jn_plugin = @import("jn-plugin");

const plugin_meta = jn_plugin.PluginMeta{
    .name = "toml",
    .version = "0.1.0",
    .matches = &.{".*\\.toml$"},
    .role = .format,
    .modes = &.{ .read, .write },
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
        try writeMode(allocator);
        return;
    }

    jn_core.exitWithError("toml: unknown mode '{s}'", .{mode});
}

// =============================================================================
// Read Mode: TOML -> NDJSON
// =============================================================================

fn readMode(allocator: std.mem.Allocator) !void {
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    // Read all input
    var input = std.ArrayList(u8){};
    defer input.deinit(allocator);

    while (jn_core.readLine(reader)) |line| {
        try input.appendSlice(allocator, line);
        try input.append(allocator, '\n');
    }

    if (input.items.len == 0) {
        jn_core.flushWriter(writer);
        return;
    }

    // Parse TOML
    var parser = TomlParser.init(allocator, input.items);
    defer parser.deinit();

    const value = parser.parse() catch {
        jn_core.exitWithError("toml: parse error at line {d}: {s}", .{
            parser.line_number,
            parser.error_message orelse "unknown error",
        });
    };
    // Note: parser.deinit() handles freeing the root value

    // Output as NDJSON (single object for TOML)
    jn_core.writeJsonLine(writer, value) catch |err|
        jn_core.handleWriteError(err);

    jn_core.flushWriter(writer);
}

// =============================================================================
// Write Mode: NDJSON -> TOML
// =============================================================================

// Explicit error set for recursive write functions
const WriteError = error{
    OutOfMemory,
    BrokenPipe,
    ConnectionResetByPeer,
    Unexpected,
    NoSpaceLeft,
    InputOutput,
    DiskQuota,
    FileTooBig,
    AccessDenied,
    NotOpenForWriting,
    LockViolation,
    WouldBlock,
    DeviceBusy,
    OperationAborted,
    WriteFailed,
};

fn writeMode(allocator: std.mem.Allocator) !void {
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;

        const parsed = std.json.parseFromSlice(std.json.Value, allocator, line, .{}) catch |err| {
            jn_core.exitWithError("toml: invalid JSON input: {}", .{err});
        };
        defer parsed.deinit();

        if (parsed.value != .object) {
            jn_core.exitWithError("toml: root must be an object", .{});
        }

        writeTomlObject(writer, parsed.value.object, "") catch |err|
            jn_core.handleWriteError(err);
    }

    jn_core.flushWriter(writer);
}

fn writeTomlObject(writer: anytype, obj: std.json.ObjectMap, prefix: []const u8) WriteError!void {
    // First pass: write simple key-value pairs
    var iter1 = obj.iterator();
    while (iter1.next()) |entry| {
        if (entry.value_ptr.* != .object and entry.value_ptr.* != .array) {
            if (prefix.len > 0) {
                // Skip - these will be written in table sections
            } else {
                try writeTomlKey(writer, entry.key_ptr.*);
                try writer.writeAll(" = ");
                try writeTomlValue(writer, entry.value_ptr.*);
                try writer.writeByte('\n');
            }
        } else if (entry.value_ptr.* == .array) {
            // Check if it's an array of tables
            const arr = entry.value_ptr.array;
            if (arr.items.len > 0 and arr.items[0] == .object) {
                // Handle in second pass
            } else {
                // Simple array
                if (prefix.len == 0) {
                    try writeTomlKey(writer, entry.key_ptr.*);
                    try writer.writeAll(" = ");
                    try writeTomlArray(writer, arr);
                    try writer.writeByte('\n');
                }
            }
        }
    }

    // Second pass: write nested objects as tables
    var iter2 = obj.iterator();
    while (iter2.next()) |entry| {
        if (entry.value_ptr.* == .object) {
            try writer.writeByte('\n');
            try writer.writeByte('[');
            if (prefix.len > 0) {
                try writer.writeAll(prefix);
                try writer.writeByte('.');
            }
            try writeTomlKey(writer, entry.key_ptr.*);
            try writer.writeAll("]\n");

            // Write contents
            var table_prefix_buf: [512]u8 = undefined;
            var table_prefix_len: usize = 0;
            if (prefix.len > 0) {
                @memcpy(table_prefix_buf[0..prefix.len], prefix);
                table_prefix_len = prefix.len;
                table_prefix_buf[table_prefix_len] = '.';
                table_prefix_len += 1;
            }
            @memcpy(table_prefix_buf[table_prefix_len .. table_prefix_len + entry.key_ptr.len], entry.key_ptr.*);
            table_prefix_len += entry.key_ptr.len;

            const table_prefix = table_prefix_buf[0..table_prefix_len];

            // Write simple values in this table
            var table_iter = entry.value_ptr.object.iterator();
            while (table_iter.next()) |sub_entry| {
                if (sub_entry.value_ptr.* != .object and
                    !(sub_entry.value_ptr.* == .array and isArrayOfTables(sub_entry.value_ptr.array)))
                {
                    try writeTomlKey(writer, sub_entry.key_ptr.*);
                    try writer.writeAll(" = ");
                    try writeTomlValue(writer, sub_entry.value_ptr.*);
                    try writer.writeByte('\n');
                }
            }

            // Recursively write nested tables
            try writeTomlObject(writer, entry.value_ptr.object, table_prefix);
        } else if (entry.value_ptr.* == .array and isArrayOfTables(entry.value_ptr.array)) {
            // Array of tables
            for (entry.value_ptr.array.items) |item| {
                try writer.writeByte('\n');
                try writer.writeAll("[[");
                if (prefix.len > 0) {
                    try writer.writeAll(prefix);
                    try writer.writeByte('.');
                }
                try writeTomlKey(writer, entry.key_ptr.*);
                try writer.writeAll("]]\n");

                // Write table contents
                var table_iter = item.object.iterator();
                while (table_iter.next()) |sub_entry| {
                    try writeTomlKey(writer, sub_entry.key_ptr.*);
                    try writer.writeAll(" = ");
                    try writeTomlValue(writer, sub_entry.value_ptr.*);
                    try writer.writeByte('\n');
                }
            }
        }
    }
}

fn isArrayOfTables(arr: std.json.Array) bool {
    if (arr.items.len == 0) return false;
    return arr.items[0] == .object;
}

fn writeTomlValue(writer: anytype, value: std.json.Value) WriteError!void {
    switch (value) {
        .null => try writer.writeAll("\"\""), // TOML has no null, use empty string
        .bool => |b| try writer.writeAll(if (b) "true" else "false"),
        .integer => |i| try writer.print("{d}", .{i}),
        .float => |f| {
            if (std.math.isNan(f)) {
                try writer.writeAll("nan");
            } else if (std.math.isInf(f)) {
                if (f < 0) {
                    try writer.writeAll("-inf");
                } else {
                    try writer.writeAll("inf");
                }
            } else {
                try writer.print("{d}", .{f});
            }
        },
        .number_string => |s| try writer.writeAll(s),
        .string => |s| try writeTomlString(writer, s),
        .array => |arr| try writeTomlArray(writer, arr),
        .object => |obj| try writeTomlInlineTable(writer, obj),
    }
}

fn writeTomlString(writer: anytype, s: []const u8) WriteError!void {
    // Check if we need basic string (with escapes) or literal string
    var needs_escaping = false;
    for (s) |c| {
        if (c == '\n' or c == '\r' or c == '\t' or c == '\\' or c == '"' or c < 0x20) {
            needs_escaping = true;
            break;
        }
    }

    try writer.writeByte('"');
    if (needs_escaping) {
        for (s) |c| {
            switch (c) {
                '\n' => try writer.writeAll("\\n"),
                '\r' => try writer.writeAll("\\r"),
                '\t' => try writer.writeAll("\\t"),
                '\\' => try writer.writeAll("\\\\"),
                '"' => try writer.writeAll("\\\""),
                else => {
                    if (c < 0x20) {
                        try writer.print("\\u{x:0>4}", .{c});
                    } else {
                        try writer.writeByte(c);
                    }
                },
            }
        }
    } else {
        try writer.writeAll(s);
    }
    try writer.writeByte('"');
}

fn writeTomlArray(writer: anytype, arr: std.json.Array) WriteError!void {
    try writer.writeByte('[');
    for (arr.items, 0..) |item, i| {
        if (i > 0) try writer.writeAll(", ");
        try writeTomlValue(writer, item);
    }
    try writer.writeByte(']');
}

fn writeTomlInlineTable(writer: anytype, obj: std.json.ObjectMap) WriteError!void {
    try writer.writeAll("{ ");
    var iter = obj.iterator();
    var first = true;
    while (iter.next()) |entry| {
        if (!first) try writer.writeAll(", ");
        first = false;
        try writeTomlKey(writer, entry.key_ptr.*);
        try writer.writeAll(" = ");
        try writeTomlValue(writer, entry.value_ptr.*);
    }
    try writer.writeAll(" }");
}

fn writeTomlKey(writer: anytype, key: []const u8) WriteError!void {
    // Check if key needs quoting
    var needs_quoting = key.len == 0;
    for (key) |c| {
        if (!((c >= 'a' and c <= 'z') or (c >= 'A' and c <= 'Z') or
            (c >= '0' and c <= '9') or c == '_' or c == '-'))
        {
            needs_quoting = true;
            break;
        }
    }

    if (needs_quoting) {
        try writeTomlString(writer, key);
    } else {
        try writer.writeAll(key);
    }
}

// =============================================================================
// TOML Parser
// =============================================================================

const TomlParser = struct {
    allocator: std.mem.Allocator,
    source: []const u8,
    pos: usize,
    line_number: usize,
    error_message: ?[]const u8,
    root: std.json.ObjectMap,

    const Self = @This();

    // Explicit error set for recursive parsing functions
    const ParseError = error{
        OutOfMemory,
        ParseError,
    };

    fn init(allocator: std.mem.Allocator, source: []const u8) Self {
        return .{
            .allocator = allocator,
            .source = source,
            .pos = 0,
            .line_number = 1,
            .error_message = null,
            .root = std.json.ObjectMap.init(allocator),
        };
    }

    fn deinit(self: *Self) void {
        self.freeObjectMap(&self.root);
    }

    fn freeValue(self: *Self, value: std.json.Value) void {
        self.freeValueRecursive(value);
    }

    fn freeValueRecursive(self: *Self, value: std.json.Value) void {
        switch (value) {
            .string => |s| self.allocator.free(s),
            .array => |arr| {
                for (arr.items) |item| {
                    self.freeValueRecursive(item);
                }
                var a = arr;
                a.deinit();
            },
            .object => |obj| {
                var m = obj;
                self.freeObjectMap(&m);
            },
            else => {},
        }
    }

    fn freeObjectMap(self: *Self, obj: *std.json.ObjectMap) void {
        var iter = obj.iterator();
        while (iter.next()) |entry| {
            self.allocator.free(entry.key_ptr.*);
            self.freeValueRecursive(entry.value_ptr.*);
        }
        obj.deinit();
    }

    fn parse(self: *Self) !std.json.Value {
        var current_table: *std.json.ObjectMap = &self.root;

        while (self.pos < self.source.len) {
            self.skipWhitespaceAndComments();
            if (self.pos >= self.source.len) break;

            const c = self.source[self.pos];

            // Table header
            if (c == '[') {
                if (self.pos + 1 < self.source.len and self.source[self.pos + 1] == '[') {
                    // Array of tables [[name]]
                    current_table = try self.parseArrayOfTables();
                } else {
                    // Regular table [name]
                    current_table = try self.parseTableHeader();
                }
            } else if (c == '\n') {
                self.pos += 1;
                self.line_number += 1;
            } else {
                // Key-value pair
                try self.parseKeyValue(current_table);
            }
        }

        return .{ .object = self.root };
    }

    fn parseTableHeader(self: *Self) ParseError!*std.json.ObjectMap {
        self.pos += 1; // skip [

        const path = try self.parseKeyPath();
        defer {
            for (path) |key| {
                self.allocator.free(key);
            }
            self.allocator.free(path);
        }

        self.skipWhitespace();
        if (self.pos >= self.source.len or self.source[self.pos] != ']') {
            self.error_message = "expected ']'";
            return error.ParseError;
        }
        self.pos += 1;

        // Navigate to or create the table
        return self.getOrCreateTable(path);
    }

    fn parseArrayOfTables(self: *Self) ParseError!*std.json.ObjectMap {
        self.pos += 2; // skip [[

        const path = try self.parseKeyPath();
        defer {
            for (path) |key| {
                self.allocator.free(key);
            }
            self.allocator.free(path);
        }

        self.skipWhitespace();
        if (self.pos + 1 >= self.source.len or
            self.source[self.pos] != ']' or self.source[self.pos + 1] != ']')
        {
            self.error_message = "expected ']]'";
            return error.ParseError;
        }
        self.pos += 2;

        // Navigate to parent and append new table to array
        return self.getOrCreateArrayTable(path);
    }

    fn parseKeyPath(self: *Self) ParseError![][]const u8 {
        var keys = std.ArrayList([]const u8){};
        errdefer {
            for (keys.items) |key| {
                self.allocator.free(key);
            }
            keys.deinit(self.allocator);
        }

        while (true) {
            self.skipWhitespace();
            const key = try self.parseKey();
            try keys.append(self.allocator, key);

            self.skipWhitespace();
            if (self.pos < self.source.len and self.source[self.pos] == '.') {
                self.pos += 1;
            } else {
                break;
            }
        }

        return try keys.toOwnedSlice(self.allocator);
    }

    fn getOrCreateTable(self: *Self, path: [][]const u8) !*std.json.ObjectMap {
        var current: *std.json.ObjectMap = &self.root;

        for (path) |key| {
            if (current.get(key)) |existing| {
                switch (existing) {
                    .object => |*obj| {
                        current = @constCast(obj);
                    },
                    .array => |arr| {
                        // Get last element of array
                        if (arr.items.len > 0 and arr.items[arr.items.len - 1] == .object) {
                            current = @constCast(&arr.items[arr.items.len - 1].object);
                        } else {
                            self.error_message = "expected table";
                            return error.ParseError;
                        }
                    },
                    else => {
                        self.error_message = "key already exists as non-table";
                        return error.ParseError;
                    },
                }
            } else {
                const new_table = std.json.ObjectMap.init(self.allocator);
                const key_copy = try self.allocator.dupe(u8, key);
                try current.put(key_copy, .{ .object = new_table });
                const entry = current.getPtr(key_copy).?;
                current = &entry.object;
            }
        }

        return current;
    }

    fn getOrCreateArrayTable(self: *Self, path: [][]const u8) !*std.json.ObjectMap {
        var current: *std.json.ObjectMap = &self.root;

        // Navigate to parent
        for (path[0 .. path.len - 1]) |key| {
            if (current.get(key)) |existing| {
                switch (existing) {
                    .object => |*obj| {
                        current = @constCast(obj);
                    },
                    .array => |arr| {
                        if (arr.items.len > 0 and arr.items[arr.items.len - 1] == .object) {
                            current = @constCast(&arr.items[arr.items.len - 1].object);
                        } else {
                            self.error_message = "expected table in array";
                            return error.ParseError;
                        }
                    },
                    else => {
                        self.error_message = "expected table";
                        return error.ParseError;
                    },
                }
            } else {
                const new_table = std.json.ObjectMap.init(self.allocator);
                const key_copy = try self.allocator.dupe(u8, key);
                try current.put(key_copy, .{ .object = new_table });
                const entry = current.getPtr(key_copy).?;
                current = &entry.object;
            }
        }

        // Handle the final key (array element)
        const last_key = path[path.len - 1];
        if (current.getPtr(last_key)) |existing| {
            switch (existing.*) {
                .array => |*arr| {
                    const new_table = std.json.ObjectMap.init(self.allocator);
                    try arr.append(.{ .object = new_table });
                    return &arr.items[arr.items.len - 1].object;
                },
                else => {
                    self.error_message = "expected array of tables";
                    return error.ParseError;
                },
            }
        } else {
            var new_array = std.json.Array.init(self.allocator);
            const new_table = std.json.ObjectMap.init(self.allocator);
            try new_array.append(.{ .object = new_table });
            const key_copy = try self.allocator.dupe(u8, last_key);
            try current.put(key_copy, .{ .array = new_array });
            const arr = &current.getPtr(key_copy).?.array;
            return &arr.items[0].object;
        }
    }

    fn parseKeyValue(self: *Self, table: *std.json.ObjectMap) ParseError!void {
        const path = try self.parseKeyPath();
        defer {
            for (path) |key| {
                self.allocator.free(key);
            }
            self.allocator.free(path);
        }

        self.skipWhitespace();
        if (self.pos >= self.source.len or self.source[self.pos] != '=') {
            self.error_message = "expected '='";
            return error.ParseError;
        }
        self.pos += 1;
        self.skipWhitespace();

        const value = try self.parseValue();

        // Navigate to parent and set value
        var current = table;
        for (path[0 .. path.len - 1]) |key| {
            if (current.getPtr(key)) |existing| {
                if (existing.* == .object) {
                    current = &existing.object;
                } else {
                    self.error_message = "expected table for dotted key";
                    self.freeValueRecursive(value);
                    return error.ParseError;
                }
            } else {
                const new_table = std.json.ObjectMap.init(self.allocator);
                const key_copy = try self.allocator.dupe(u8, key);
                try current.put(key_copy, .{ .object = new_table });
                current = &current.getPtr(key_copy).?.object;
            }
        }

        const final_key = try self.allocator.dupe(u8, path[path.len - 1]);
        try current.put(final_key, value);

        // Skip to end of line
        self.skipWhitespace();
        if (self.pos < self.source.len and self.source[self.pos] == '#') {
            while (self.pos < self.source.len and self.source[self.pos] != '\n') : (self.pos += 1) {}
        }
    }

    fn parseKey(self: *Self) ParseError![]const u8 {
        self.skipWhitespace();

        if (self.pos >= self.source.len) {
            self.error_message = "unexpected end of input";
            return error.ParseError;
        }

        const c = self.source[self.pos];

        // Quoted key
        if (c == '"' or c == '\'') {
            return self.parseString();
        }

        // Bare key
        const start = self.pos;
        while (self.pos < self.source.len) {
            const ch = self.source[self.pos];
            if ((ch >= 'a' and ch <= 'z') or (ch >= 'A' and ch <= 'Z') or
                (ch >= '0' and ch <= '9') or ch == '_' or ch == '-')
            {
                self.pos += 1;
            } else {
                break;
            }
        }

        if (self.pos == start) {
            self.error_message = "expected key";
            return error.ParseError;
        }

        return try self.allocator.dupe(u8, self.source[start..self.pos]);
    }

    fn parseValue(self: *Self) ParseError!std.json.Value {
        self.skipWhitespace();

        if (self.pos >= self.source.len) {
            self.error_message = "unexpected end of input";
            return error.ParseError;
        }

        const c = self.source[self.pos];

        // String
        if (c == '"' or c == '\'') {
            const s = try self.parseString();
            return .{ .string = s };
        }

        // Array
        if (c == '[') {
            return self.parseArray();
        }

        // Inline table
        if (c == '{') {
            return self.parseInlineTable();
        }

        // Boolean, number, or other
        return self.parseScalar();
    }

    fn parseString(self: *Self) ParseError![]const u8 {
        const quote = self.source[self.pos];
        const is_double = quote == '"';

        // Check for multi-line
        if (self.pos + 2 < self.source.len and
            self.source[self.pos + 1] == quote and self.source[self.pos + 2] == quote)
        {
            return self.parseMultiLineString();
        }

        self.pos += 1; // skip opening quote

        var result = std.ArrayList(u8){};
        errdefer result.deinit(self.allocator);

        while (self.pos < self.source.len) {
            const c = self.source[self.pos];

            if (c == quote) {
                self.pos += 1;
                break;
            }

            if (c == '\n') {
                self.error_message = "newline in single-line string";
                result.deinit(self.allocator);
                return error.ParseError;
            }

            if (is_double and c == '\\' and self.pos + 1 < self.source.len) {
                self.pos += 1;
                const escaped = self.source[self.pos];
                switch (escaped) {
                    'n' => try result.append(self.allocator, '\n'),
                    'r' => try result.append(self.allocator, '\r'),
                    't' => try result.append(self.allocator, '\t'),
                    '\\' => try result.append(self.allocator, '\\'),
                    '"' => try result.append(self.allocator, '"'),
                    'u' => {
                        // Unicode escape \uXXXX
                        if (self.pos + 4 < self.source.len) {
                            self.pos += 1;
                            const hex = self.source[self.pos .. self.pos + 4];
                            const cp = std.fmt.parseInt(u21, hex, 16) catch {
                                self.error_message = "invalid unicode escape";
                                result.deinit(self.allocator);
                                return error.ParseError;
                            };
                            var utf8_buf: [4]u8 = undefined;
                            const len = std.unicode.utf8Encode(cp, &utf8_buf) catch {
                                self.error_message = "invalid unicode codepoint";
                                result.deinit(self.allocator);
                                return error.ParseError;
                            };
                            try result.appendSlice(self.allocator, utf8_buf[0..len]);
                            self.pos += 3; // Will be incremented again below
                        }
                    },
                    else => {
                        try result.append(self.allocator, '\\');
                        try result.append(self.allocator, escaped);
                    },
                }
                self.pos += 1;
            } else {
                try result.append(self.allocator, c);
                self.pos += 1;
            }
        }

        return try result.toOwnedSlice(self.allocator);
    }

    fn parseMultiLineString(self: *Self) ParseError![]const u8 {
        const quote = self.source[self.pos];
        const is_double = quote == '"';
        self.pos += 3; // skip """

        // Skip leading newline
        if (self.pos < self.source.len and self.source[self.pos] == '\n') {
            self.pos += 1;
            self.line_number += 1;
        }

        var result = std.ArrayList(u8){};
        errdefer result.deinit(self.allocator);

        while (self.pos < self.source.len) {
            // Check for closing quotes
            if (self.pos + 2 < self.source.len and
                self.source[self.pos] == quote and
                self.source[self.pos + 1] == quote and
                self.source[self.pos + 2] == quote)
            {
                self.pos += 3;
                break;
            }

            const c = self.source[self.pos];

            if (c == '\n') {
                self.line_number += 1;
                try result.append(self.allocator, '\n');
                self.pos += 1;
            } else if (is_double and c == '\\') {
                if (self.pos + 1 < self.source.len) {
                    const next = self.source[self.pos + 1];
                    if (next == '\n' or next == ' ' or next == '\t') {
                        // Line ending backslash - skip whitespace
                        self.pos += 1;
                        while (self.pos < self.source.len and
                            (self.source[self.pos] == ' ' or
                            self.source[self.pos] == '\t' or
                            self.source[self.pos] == '\n'))
                        {
                            if (self.source[self.pos] == '\n') self.line_number += 1;
                            self.pos += 1;
                        }
                    } else {
                        // Regular escape
                        self.pos += 1;
                        switch (next) {
                            'n' => try result.append(self.allocator, '\n'),
                            'r' => try result.append(self.allocator, '\r'),
                            't' => try result.append(self.allocator, '\t'),
                            '\\' => try result.append(self.allocator, '\\'),
                            '"' => try result.append(self.allocator, '"'),
                            else => {
                                try result.append(self.allocator, '\\');
                                try result.append(self.allocator, next);
                            },
                        }
                        self.pos += 1;
                    }
                } else {
                    try result.append(self.allocator, c);
                    self.pos += 1;
                }
            } else {
                try result.append(self.allocator, c);
                self.pos += 1;
            }
        }

        return try result.toOwnedSlice(self.allocator);
    }

    fn parseArray(self: *Self) ParseError!std.json.Value {
        self.pos += 1; // skip [
        var arr = std.json.Array.init(self.allocator);
        errdefer arr.deinit();

        self.skipWhitespaceAndNewlines();

        while (self.pos < self.source.len and self.source[self.pos] != ']') {
            const value = try self.parseValue();
            try arr.append(value);

            self.skipWhitespaceAndNewlines();
            if (self.pos < self.source.len and self.source[self.pos] == ',') {
                self.pos += 1;
                self.skipWhitespaceAndNewlines();
            }
        }

        if (self.pos < self.source.len) self.pos += 1; // skip ]

        return .{ .array = arr };
    }

    fn parseInlineTable(self: *Self) ParseError!std.json.Value {
        self.pos += 1; // skip {
        var obj = std.json.ObjectMap.init(self.allocator);
        errdefer self.freeObjectMap(&obj);

        self.skipWhitespace();

        while (self.pos < self.source.len and self.source[self.pos] != '}') {
            const key = try self.parseKey();
            errdefer self.allocator.free(key);

            self.skipWhitespace();
            if (self.pos >= self.source.len or self.source[self.pos] != '=') {
                self.error_message = "expected '=' in inline table";
                self.allocator.free(key);
                return error.ParseError;
            }
            self.pos += 1;
            self.skipWhitespace();

            const value = try self.parseValue();
            try obj.put(key, value);

            self.skipWhitespace();
            if (self.pos < self.source.len and self.source[self.pos] == ',') {
                self.pos += 1;
                self.skipWhitespace();
            }
        }

        if (self.pos < self.source.len) self.pos += 1; // skip }

        return .{ .object = obj };
    }

    fn parseScalar(self: *Self) ParseError!std.json.Value {
        const start = self.pos;

        // Find end of value
        while (self.pos < self.source.len) {
            const c = self.source[self.pos];
            if (c == ',' or c == ']' or c == '}' or c == '\n' or c == '#') break;
            self.pos += 1;
        }

        const value = std.mem.trim(u8, self.source[start..self.pos], " \t");

        // Boolean
        if (std.mem.eql(u8, value, "true")) return .{ .bool = true };
        if (std.mem.eql(u8, value, "false")) return .{ .bool = false };

        // Integer (including hex, octal, binary)
        if (value.len > 2 and value[0] == '0') {
            if (value[1] == 'x' or value[1] == 'X') {
                if (std.fmt.parseInt(i64, value[2..], 16)) |i| {
                    return .{ .integer = i };
                } else |_| {}
            } else if (value[1] == 'o' or value[1] == 'O') {
                if (std.fmt.parseInt(i64, value[2..], 8)) |i| {
                    return .{ .integer = i };
                } else |_| {}
            } else if (value[1] == 'b' or value[1] == 'B') {
                if (std.fmt.parseInt(i64, value[2..], 2)) |i| {
                    return .{ .integer = i };
                } else |_| {}
            }
        }

        // Try regular integer (with underscores removed)
        var clean_buf: [64]u8 = undefined;
        var clean_len: usize = 0;
        for (value) |c| {
            if (c != '_' and clean_len < clean_buf.len) {
                clean_buf[clean_len] = c;
                clean_len += 1;
            }
        }
        const clean = clean_buf[0..clean_len];

        if (std.fmt.parseInt(i64, clean, 10)) |i| {
            return .{ .integer = i };
        } else |_| {}

        // Try float
        if (std.mem.eql(u8, clean, "inf") or std.mem.eql(u8, clean, "+inf")) {
            return .{ .float = std.math.inf(f64) };
        }
        if (std.mem.eql(u8, clean, "-inf")) {
            return .{ .float = -std.math.inf(f64) };
        }
        if (std.mem.eql(u8, clean, "nan") or std.mem.eql(u8, clean, "+nan") or std.mem.eql(u8, clean, "-nan")) {
            return .{ .float = std.math.nan(f64) };
        }

        if (std.fmt.parseFloat(f64, clean)) |f| {
            return .{ .float = f };
        } else |_| {}

        // Treat as string (for dates, times, etc.)
        const s = try self.allocator.dupe(u8, value);
        return .{ .string = s };
    }

    fn skipWhitespace(self: *Self) void {
        while (self.pos < self.source.len) {
            const c = self.source[self.pos];
            if (c == ' ' or c == '\t') {
                self.pos += 1;
            } else {
                break;
            }
        }
    }

    fn skipWhitespaceAndNewlines(self: *Self) void {
        while (self.pos < self.source.len) {
            const c = self.source[self.pos];
            if (c == ' ' or c == '\t' or c == '\r') {
                self.pos += 1;
            } else if (c == '\n') {
                self.pos += 1;
                self.line_number += 1;
            } else if (c == '#') {
                while (self.pos < self.source.len and self.source[self.pos] != '\n') : (self.pos += 1) {}
            } else {
                break;
            }
        }
    }

    fn skipWhitespaceAndComments(self: *Self) void {
        while (self.pos < self.source.len) {
            const c = self.source[self.pos];
            if (c == ' ' or c == '\t' or c == '\r') {
                self.pos += 1;
            } else if (c == '#') {
                while (self.pos < self.source.len and self.source[self.pos] != '\n') : (self.pos += 1) {}
            } else {
                break;
            }
        }
    }
};

// =============================================================================
// Tests
// =============================================================================

test "manifest output contains toml name" {
    var buf: [256]u8 = undefined;
    var fbs = std.io.fixedBufferStream(&buf);
    try jn_plugin.outputManifest(fbs.writer(), plugin_meta);
    try std.testing.expect(std.mem.indexOf(u8, fbs.getWritten(), "\"toml\"") != null);
}

test "parse simple key-value" {
    const allocator = std.testing.allocator;
    var parser = TomlParser.init(allocator, "name = \"Alice\"\n");
    defer parser.deinit();

    const value = try parser.parse();
    try std.testing.expect(value == .object);
    try std.testing.expect(value.object.get("name") != null);
}

test "parse integer" {
    const allocator = std.testing.allocator;
    var parser = TomlParser.init(allocator, "count = 42\n");
    defer parser.deinit();

    const value = try parser.parse();
    const count = value.object.get("count").?;
    try std.testing.expect(count == .integer);
    try std.testing.expectEqual(@as(i64, 42), count.integer);
}

test "parse boolean" {
    const allocator = std.testing.allocator;
    var parser = TomlParser.init(allocator, "enabled = true\ndisabled = false\n");
    defer parser.deinit();

    const value = try parser.parse();
    try std.testing.expect(value.object.get("enabled").?.bool == true);
    try std.testing.expect(value.object.get("disabled").?.bool == false);
}

test "parse array" {
    const allocator = std.testing.allocator;
    var parser = TomlParser.init(allocator, "items = [1, 2, 3]\n");
    defer parser.deinit();

    const value = try parser.parse();
    const items = value.object.get("items").?;
    try std.testing.expect(items == .array);
    try std.testing.expectEqual(@as(usize, 3), items.array.items.len);
}

test "parse table" {
    const allocator = std.testing.allocator;
    var parser = TomlParser.init(allocator, "[server]\nhost = \"localhost\"\nport = 8080\n");
    defer parser.deinit();

    const value = try parser.parse();
    const server = value.object.get("server").?;
    try std.testing.expect(server == .object);
    try std.testing.expect(server.object.get("host") != null);
    try std.testing.expect(server.object.get("port") != null);
}

test "parse array of tables" {
    const allocator = std.testing.allocator;
    var parser = TomlParser.init(allocator, "[[users]]\nname = \"Alice\"\n[[users]]\nname = \"Bob\"\n");
    defer parser.deinit();

    const value = try parser.parse();
    const users = value.object.get("users").?;
    try std.testing.expect(users == .array);
    try std.testing.expectEqual(@as(usize, 2), users.array.items.len);
}
