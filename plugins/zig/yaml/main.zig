const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");
const jn_plugin = @import("jn-plugin");

const plugin_meta = jn_plugin.PluginMeta{
    .name = "yaml",
    .version = "0.1.0",
    .matches = &.{ ".*\\.yaml$", ".*\\.yml$" },
    .role = .format,
    .modes = &.{ .read, .write },
};

/// Maximum input size (100MB default). This prevents OOM on extremely large files.
const DEFAULT_MAX_INPUT_SIZE: usize = 100 * 1024 * 1024;

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
        const indent = if (args.get("indent", null)) |v|
            std.fmt.parseInt(u8, v, 10) catch 2
        else
            2;
        try writeMode(allocator, indent);
        return;
    }

    jn_core.exitWithError("yaml: unknown mode '{s}'", .{mode});
}

// =============================================================================
// Read Mode: YAML -> NDJSON
// =============================================================================

fn readMode(allocator: std.mem.Allocator) !void {
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    // Read all input into memory (YAML requires full document for indentation)
    // Use ArrayListUnmanaged for explicit allocator passing (clearer ownership)
    var input: std.ArrayListUnmanaged(u8) = .empty;
    defer input.deinit(allocator);

    while (jn_core.readLine(reader)) |line| {
        // Check size limit to prevent OOM on maliciously large input
        if (input.items.len + line.len > DEFAULT_MAX_INPUT_SIZE) {
            jn_core.exitWithError("yaml: input exceeds maximum size of {d}MB", .{DEFAULT_MAX_INPUT_SIZE / (1024 * 1024)});
        }
        try input.appendSlice(allocator, line);
        try input.append(allocator, '\n');
    }

    if (input.items.len == 0) {
        jn_core.flushWriter(writer);
        return;
    }

    // Parse YAML and output as NDJSON
    var parser = YamlParser.init(allocator, input.items);
    defer parser.deinit();

    var doc_count: usize = 0;
    while (parser.parseDocument()) |value| {
        defer parser.freeValue(value);
        doc_count += 1;

        // If root is an array and this is the only document, emit each element as a line
        if (value == .array and doc_count == 1 and !parser.hasMoreDocuments()) {
            for (value.array.items) |item| {
                jn_core.writeJsonLine(writer, item) catch |err|
                    jn_core.handleWriteError(err);
            }
        } else {
            jn_core.writeJsonLine(writer, value) catch |err|
                jn_core.handleWriteError(err);
        }
    } else |err| {
        if (err != error.EndOfInput) {
            jn_core.exitWithError("yaml: parse error at line {d}: {s}", .{
                parser.line_number,
                parser.error_message orelse "unknown error",
            });
        }
    }

    jn_core.flushWriter(writer);
}

// =============================================================================
// Write Mode: NDJSON -> YAML
// =============================================================================

fn writeMode(allocator: std.mem.Allocator, indent: u8) !void {
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    var first = true;
    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;

        const parsed = std.json.parseFromSlice(std.json.Value, allocator, line, .{}) catch |err| {
            jn_core.exitWithError("yaml: invalid JSON input: {}", .{err});
        };
        defer parsed.deinit();

        // Add document separator for multi-document output
        if (!first) {
            writer.writeAll("---\n") catch |err| jn_core.handleWriteError(err);
        }
        first = false;

        writeYamlValue(writer, parsed.value, 0, indent) catch |err|
            jn_core.handleWriteError(err);
    }

    jn_core.flushWriter(writer);
}

fn writeYamlValue(writer: anytype, value: std.json.Value, depth: u16, indent: u8) !void {
    switch (value) {
        .null => try writer.writeAll("null\n"),
        .bool => |b| try writer.writeAll(if (b) "true\n" else "false\n"),
        .integer => |i| try writer.print("{d}\n", .{i}),
        .float => |f| try writer.print("{d}\n", .{f}),
        .number_string => |s| {
            try writer.writeAll(s);
            try writer.writeByte('\n');
        },
        .string => |s| try writeYamlString(writer, s),
        .array => |arr| {
            if (arr.items.len == 0) {
                try writer.writeAll("[]\n");
                return;
            }
            try writer.writeByte('\n');
            for (arr.items) |item| {
                try writeIndent(writer, depth, indent);
                try writer.writeAll("- ");
                if (item == .array or item == .object) {
                    try writeYamlValue(writer, item, depth + 1, indent);
                } else {
                    try writeYamlValueInline(writer, item);
                }
            }
        },
        .object => |obj| {
            if (obj.count() == 0) {
                try writer.writeAll("{}\n");
                return;
            }
            try writer.writeByte('\n');
            var iter = obj.iterator();
            while (iter.next()) |entry| {
                try writeIndent(writer, depth, indent);
                try writeYamlKey(writer, entry.key_ptr.*);
                try writer.writeAll(": ");
                if (entry.value_ptr.* == .array or entry.value_ptr.* == .object) {
                    try writeYamlValue(writer, entry.value_ptr.*, depth + 1, indent);
                } else {
                    try writeYamlValueInline(writer, entry.value_ptr.*);
                }
            }
        },
    }
}

fn writeYamlValueInline(writer: anytype, value: std.json.Value) !void {
    switch (value) {
        .null => try writer.writeAll("null\n"),
        .bool => |b| try writer.writeAll(if (b) "true\n" else "false\n"),
        .integer => |i| try writer.print("{d}\n", .{i}),
        .float => |f| try writer.print("{d}\n", .{f}),
        .number_string => |s| {
            try writer.writeAll(s);
            try writer.writeByte('\n');
        },
        .string => |s| try writeYamlString(writer, s),
        .array => try writer.writeAll("[]\n"),
        .object => try writer.writeAll("{}\n"),
    }
}

fn writeYamlString(writer: anytype, s: []const u8) !void {
    // Check if string needs quoting
    if (needsQuoting(s)) {
        try writer.writeByte('"');
        for (s) |c| {
            switch (c) {
                '"' => try writer.writeAll("\\\""),
                '\\' => try writer.writeAll("\\\\"),
                '\n' => try writer.writeAll("\\n"),
                '\r' => try writer.writeAll("\\r"),
                '\t' => try writer.writeAll("\\t"),
                else => try writer.writeByte(c),
            }
        }
        try writer.writeAll("\"\n");
    } else {
        try writer.writeAll(s);
        try writer.writeByte('\n');
    }
}

fn writeYamlKey(writer: anytype, key: []const u8) !void {
    if (needsQuoting(key)) {
        try writer.writeByte('"');
        for (key) |c| {
            switch (c) {
                '"' => try writer.writeAll("\\\""),
                '\\' => try writer.writeAll("\\\\"),
                else => try writer.writeByte(c),
            }
        }
        try writer.writeByte('"');
    } else {
        try writer.writeAll(key);
    }
}

fn needsQuoting(s: []const u8) bool {
    if (s.len == 0) return true;

    // Check for reserved words
    if (std.mem.eql(u8, s, "true") or std.mem.eql(u8, s, "false") or
        std.mem.eql(u8, s, "null") or std.mem.eql(u8, s, "~") or
        std.mem.eql(u8, s, "yes") or std.mem.eql(u8, s, "no") or
        std.mem.eql(u8, s, "on") or std.mem.eql(u8, s, "off"))
    {
        return true;
    }

    // Check for special first characters
    const first = s[0];
    if (first == '#' or first == '&' or first == '*' or first == '!' or
        first == '|' or first == '>' or first == '\'' or first == '"' or
        first == '%' or first == '@' or first == '`' or first == '-' or
        first == ':' or first == '?' or first == '[' or first == ']' or
        first == '{' or first == '}' or first == ',')
    {
        return true;
    }

    // Check for special characters anywhere
    for (s) |c| {
        if (c == ':' or c == '#' or c == '\n' or c == '\r' or c == '\t') {
            return true;
        }
    }

    // Check if it looks like a number
    if (looksLikeNumber(s)) return true;

    return false;
}

fn looksLikeNumber(s: []const u8) bool {
    if (s.len == 0) return false;

    var i: usize = 0;
    if (s[0] == '-' or s[0] == '+') i += 1;
    if (i >= s.len) return false;

    var has_digit = false;
    while (i < s.len and (s[i] >= '0' and s[i] <= '9')) : (i += 1) {
        has_digit = true;
    }

    if (i >= s.len) return has_digit;
    if (s[i] == '.') {
        i += 1;
        while (i < s.len and (s[i] >= '0' and s[i] <= '9')) : (i += 1) {
            has_digit = true;
        }
    }

    if (i >= s.len) return has_digit;
    if (s[i] == 'e' or s[i] == 'E') {
        i += 1;
        if (i < s.len and (s[i] == '+' or s[i] == '-')) i += 1;
        while (i < s.len and (s[i] >= '0' and s[i] <= '9')) : (i += 1) {}
    }

    return i >= s.len and has_digit;
}

fn writeIndent(writer: anytype, depth: u16, indent: u8) !void {
    const total = @as(usize, depth) * @as(usize, indent);
    var i: usize = 0;
    while (i < total) : (i += 1) {
        try writer.writeByte(' ');
    }
}

// =============================================================================
// YAML Parser
// =============================================================================

const YamlParser = struct {
    allocator: std.mem.Allocator,
    source: []const u8,
    pos: usize,
    line_number: usize,
    error_message: ?[]const u8,

    const Self = @This();

    // Explicit error set for recursive parsing functions
    const ParseError = error{
        OutOfMemory,
        EndOfInput,
    };

    fn init(allocator: std.mem.Allocator, source: []const u8) Self {
        return .{
            .allocator = allocator,
            .source = source,
            .pos = 0,
            .line_number = 1,
            .error_message = null,
        };
    }

    fn deinit(self: *Self) void {
        _ = self; // Parser has no internal state to clean up
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
            .object => |*obj| {
                var iter = obj.iterator();
                while (iter.next()) |entry| {
                    self.allocator.free(entry.key_ptr.*);
                    self.freeValueRecursive(entry.value_ptr.*);
                }
                var m = @constCast(obj);
                m.deinit();
            },
            else => {},
        }
    }

    fn hasMoreDocuments(self: *Self) bool {
        var pos = self.pos;
        while (pos < self.source.len) {
            if (self.source[pos] == '-' and pos + 2 < self.source.len and
                self.source[pos + 1] == '-' and self.source[pos + 2] == '-')
            {
                return true;
            }
            if (self.source[pos] == '\n') {
                pos += 1;
            } else if (self.source[pos] == ' ' or self.source[pos] == '\t') {
                pos += 1;
            } else if (self.source[pos] == '#') {
                while (pos < self.source.len and self.source[pos] != '\n') : (pos += 1) {}
            } else {
                break;
            }
        }
        return false;
    }

    fn parseDocument(self: *Self) ParseError!std.json.Value {
        self.skipWhitespaceAndComments();

        // Check for end of input
        if (self.pos >= self.source.len) {
            return error.EndOfInput;
        }

        // Skip document start marker
        if (self.matchStr("---")) {
            self.skipToEndOfLine();
            self.skipWhitespaceAndComments();
        }

        if (self.pos >= self.source.len) {
            return error.EndOfInput;
        }

        return self.parseValue(0);
    }

    fn parseValue(self: *Self, min_indent: usize) ParseError!std.json.Value {
        self.skipWhitespaceAndComments();

        if (self.pos >= self.source.len) {
            return .null;
        }

        const current_indent = self.currentIndent();
        if (current_indent < min_indent and min_indent > 0) {
            return .null;
        }

        const c = self.source[self.pos];

        // Flow-style array
        if (c == '[') {
            return self.parseFlowArray();
        }

        // Flow-style object
        if (c == '{') {
            return self.parseFlowObject();
        }

        // Block-style array (starts with -)
        if (c == '-' and self.isArrayIndicator()) {
            return self.parseBlockArray(current_indent);
        }

        // Multi-line string literals
        if (c == '|' or c == '>') {
            return self.parseBlockScalar();
        }

        // Check if this is a mapping key
        if (self.hasColonInLine()) {
            return self.parseBlockObject(current_indent);
        }

        // Otherwise it's a scalar
        return self.parseScalar();
    }

    fn isArrayIndicator(self: *Self) bool {
        if (self.pos + 1 >= self.source.len) return false;
        const next = self.source[self.pos + 1];
        return next == ' ' or next == '\n' or next == '\r';
    }

    fn hasColonInLine(self: *Self) bool {
        var pos = self.pos;
        while (pos < self.source.len) {
            const c = self.source[pos];
            if (c == '\n') return false;
            if (c == ':') {
                // Must be followed by space, newline, or end
                if (pos + 1 >= self.source.len) return true;
                const next = self.source[pos + 1];
                return next == ' ' or next == '\n' or next == '\r';
            }
            pos += 1;
        }
        return false;
    }

    fn parseFlowArray(self: *Self) ParseError!std.json.Value {
        self.pos += 1; // skip [
        var arr = std.json.Array.init(self.allocator);
        errdefer {
            // Clean up already-parsed values on error to prevent memory leaks
            for (arr.items) |item| {
                self.freeValueRecursive(item);
            }
            arr.deinit();
        }

        self.skipWhitespace();

        while (self.pos < self.source.len and self.source[self.pos] != ']') {
            const value = try self.parseFlowValue();
            try arr.append(value);

            self.skipWhitespace();
            if (self.pos < self.source.len and self.source[self.pos] == ',') {
                self.pos += 1;
                self.skipWhitespace();
            }
        }

        if (self.pos < self.source.len) self.pos += 1; // skip ]

        return .{ .array = arr };
    }

    fn parseFlowObject(self: *Self) ParseError!std.json.Value {
        self.pos += 1; // skip {
        var obj = std.json.ObjectMap.init(self.allocator);
        errdefer {
            // Clean up already-parsed key-value pairs on error to prevent memory leaks
            var iter = obj.iterator();
            while (iter.next()) |entry| {
                self.allocator.free(entry.key_ptr.*);
                self.freeValueRecursive(entry.value_ptr.*);
            }
            obj.deinit();
        }

        self.skipWhitespace();

        while (self.pos < self.source.len and self.source[self.pos] != '}') {
            const key = try self.parseFlowKey();
            errdefer self.allocator.free(key); // Free key if value parsing fails
            self.skipWhitespace();

            if (self.pos < self.source.len and self.source[self.pos] == ':') {
                self.pos += 1;
            }
            self.skipWhitespace();

            const value = try self.parseFlowValue();
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

    fn parseFlowKey(self: *Self) ParseError![]const u8 {
        if (self.pos < self.source.len and (self.source[self.pos] == '"' or self.source[self.pos] == '\'')) {
            return self.parseQuotedString();
        }

        const start = self.pos;
        while (self.pos < self.source.len) {
            const c = self.source[self.pos];
            if (c == ':' or c == ',' or c == '}' or c == '\n') break;
            self.pos += 1;
        }

        const key = std.mem.trim(u8, self.source[start..self.pos], " \t");
        return try self.allocator.dupe(u8, key);
    }

    fn parseFlowValue(self: *Self) ParseError!std.json.Value {
        self.skipWhitespace();

        if (self.pos >= self.source.len) return .null;

        const c = self.source[self.pos];
        if (c == '[') return self.parseFlowArray();
        if (c == '{') return self.parseFlowObject();
        if (c == '"' or c == '\'') {
            const s = try self.parseQuotedString();
            return .{ .string = s };
        }

        // Parse until delimiter
        const start = self.pos;
        while (self.pos < self.source.len) {
            const ch = self.source[self.pos];
            if (ch == ',' or ch == ']' or ch == '}' or ch == '\n') break;
            self.pos += 1;
        }

        const value = std.mem.trim(u8, self.source[start..self.pos], " \t");
        return self.parseScalarValue(value);
    }

    fn parseBlockArray(self: *Self, base_indent: usize) ParseError!std.json.Value {
        var arr = std.json.Array.init(self.allocator);
        errdefer {
            // Clean up already-parsed values on error to prevent memory leaks
            for (arr.items) |item| {
                self.freeValueRecursive(item);
            }
            arr.deinit();
        }

        while (self.pos < self.source.len) {
            const current_indent = self.currentIndent();
            if (current_indent < base_indent) break;
            if (current_indent != base_indent) break;

            if (!self.matchStr("- ") and !self.matchChar('-')) break;

            self.pos += 1; // skip -
            self.skipInlineWhitespace();

            // Handle nested content
            if (self.pos < self.source.len and self.source[self.pos] == '\n') {
                self.pos += 1;
                self.line_number += 1;
                self.skipWhitespaceAndComments();
                const value = try self.parseValue(base_indent + 1);
                try arr.append(value);
            } else {
                const value = try self.parseInlineValue(base_indent);
                try arr.append(value);
            }

            self.skipWhitespaceAndComments();
        }

        return .{ .array = arr };
    }

    fn parseBlockObject(self: *Self, base_indent: usize) ParseError!std.json.Value {
        var obj = std.json.ObjectMap.init(self.allocator);
        errdefer {
            // Clean up already-parsed key-value pairs on error to prevent memory leaks
            var iter = obj.iterator();
            while (iter.next()) |entry| {
                self.allocator.free(entry.key_ptr.*);
                self.freeValueRecursive(entry.value_ptr.*);
            }
            obj.deinit();
        }

        while (self.pos < self.source.len) {
            const current_indent = self.currentIndent();
            if (current_indent < base_indent and base_indent > 0) break;

            if (self.matchStr("---") or self.matchStr("...")) break;

            // Find the key
            const key_start = self.pos;
            while (self.pos < self.source.len) {
                const c = self.source[self.pos];
                if (c == ':') break;
                if (c == '\n') break;
                self.pos += 1;
            }

            if (self.pos >= self.source.len or self.source[self.pos] != ':') break;

            const key_raw = std.mem.trim(u8, self.source[key_start..self.pos], " \t");
            const key = try self.unquoteKey(key_raw);
            errdefer self.allocator.free(key); // Free key if value parsing fails

            self.pos += 1; // skip :
            self.skipInlineWhitespace();

            // Parse value
            if (self.pos < self.source.len and self.source[self.pos] == '\n') {
                self.pos += 1;
                self.line_number += 1;
                self.skipWhitespaceAndComments();
                const value = try self.parseValue(current_indent + 1);
                try obj.put(key, value);
            } else {
                const value = try self.parseInlineValue(current_indent);
                try obj.put(key, value);
            }

            self.skipWhitespaceAndComments();
        }

        return .{ .object = obj };
    }

    fn parseInlineValue(self: *Self, _: usize) ParseError!std.json.Value {
        if (self.pos >= self.source.len) return .null;

        const c = self.source[self.pos];
        if (c == '[') return self.parseFlowArray();
        if (c == '{') return self.parseFlowObject();
        if (c == '|' or c == '>') return self.parseBlockScalar();

        return self.parseScalar();
    }

    fn parseBlockScalar(self: *Self) ParseError!std.json.Value {
        const style = self.source[self.pos];
        self.pos += 1;

        // Skip modifiers and get to newline
        while (self.pos < self.source.len and self.source[self.pos] != '\n') : (self.pos += 1) {}
        if (self.pos < self.source.len) {
            self.pos += 1;
            self.line_number += 1;
        }

        // Determine content indent
        const content_indent = self.currentIndent();
        if (content_indent == 0) return .{ .string = try self.allocator.dupe(u8, "") };

        var result: std.ArrayListUnmanaged(u8) = .empty;
        defer result.deinit(self.allocator);

        var first_line = true;
        while (self.pos < self.source.len) {
            const line_indent = self.currentIndent();

            // Check for end of block
            if (line_indent < content_indent and !self.isBlankLine()) {
                break;
            }

            // Skip the indent
            var line_start = self.pos;
            var spaces: usize = 0;
            while (line_start < self.source.len and self.source[line_start] == ' ') : (line_start += 1) {
                spaces += 1;
            }
            if (spaces >= content_indent) {
                self.pos = line_start - (spaces - content_indent);
            }

            // Find end of line
            const start = self.pos;
            while (self.pos < self.source.len and self.source[self.pos] != '\n') : (self.pos += 1) {}

            // Add appropriate separator
            if (!first_line) {
                if (style == '|') {
                    try result.append(self.allocator, '\n');
                } else {
                    try result.append(self.allocator, ' ');
                }
            }
            first_line = false;

            try result.appendSlice(self.allocator, self.source[start..self.pos]);

            if (self.pos < self.source.len) {
                self.pos += 1;
                self.line_number += 1;
            }
        }

        const s = try self.allocator.dupe(u8, result.items);
        return .{ .string = s };
    }

    fn isBlankLine(self: *Self) bool {
        var pos = self.pos;
        while (pos < self.source.len and self.source[pos] == ' ') : (pos += 1) {}
        return pos >= self.source.len or self.source[pos] == '\n';
    }

    fn parseScalar(self: *Self) ParseError!std.json.Value {
        if (self.pos < self.source.len and (self.source[self.pos] == '"' or self.source[self.pos] == '\'')) {
            const s = try self.parseQuotedString();
            return .{ .string = s };
        }

        const start = self.pos;
        while (self.pos < self.source.len) {
            const c = self.source[self.pos];
            if (c == '\n' or c == '#') break;
            self.pos += 1;
        }

        const value = std.mem.trim(u8, self.source[start..self.pos], " \t\r");

        // Skip to end of line
        while (self.pos < self.source.len and self.source[self.pos] != '\n') : (self.pos += 1) {}
        if (self.pos < self.source.len) {
            self.pos += 1;
            self.line_number += 1;
        }

        return self.parseScalarValue(value);
    }

    fn parseScalarValue(self: *Self, value: []const u8) ParseError!std.json.Value {
        if (value.len == 0) return .null;

        // Check for null
        if (std.mem.eql(u8, value, "null") or std.mem.eql(u8, value, "~") or
            std.mem.eql(u8, value, "Null") or std.mem.eql(u8, value, "NULL"))
        {
            return .null;
        }

        // Check for boolean
        if (std.mem.eql(u8, value, "true") or std.mem.eql(u8, value, "True") or
            std.mem.eql(u8, value, "TRUE") or std.mem.eql(u8, value, "yes") or
            std.mem.eql(u8, value, "Yes") or std.mem.eql(u8, value, "YES") or
            std.mem.eql(u8, value, "on") or std.mem.eql(u8, value, "On") or
            std.mem.eql(u8, value, "ON"))
        {
            return .{ .bool = true };
        }

        if (std.mem.eql(u8, value, "false") or std.mem.eql(u8, value, "False") or
            std.mem.eql(u8, value, "FALSE") or std.mem.eql(u8, value, "no") or
            std.mem.eql(u8, value, "No") or std.mem.eql(u8, value, "NO") or
            std.mem.eql(u8, value, "off") or std.mem.eql(u8, value, "Off") or
            std.mem.eql(u8, value, "OFF"))
        {
            return .{ .bool = false };
        }

        // Try parsing as integer
        if (std.fmt.parseInt(i64, value, 10)) |i| {
            return .{ .integer = i };
        } else |_| {}

        // Try parsing as float
        if (std.fmt.parseFloat(f64, value)) |f| {
            return .{ .float = f };
        } else |_| {}

        // It's a string
        const s = try self.allocator.dupe(u8, value);
        return .{ .string = s };
    }

    fn parseQuotedString(self: *Self) ParseError![]const u8 {
        const quote = self.source[self.pos];
        self.pos += 1;

        var result: std.ArrayListUnmanaged(u8) = .empty;
        defer result.deinit(self.allocator);

        while (self.pos < self.source.len) {
            const c = self.source[self.pos];

            // Handle quote character
            if (c == quote) {
                // In single-quoted strings, '' is an escaped single quote
                if (quote == '\'' and self.pos + 1 < self.source.len and self.source[self.pos + 1] == '\'') {
                    try result.append(self.allocator, '\'');
                    self.pos += 2;
                    continue;
                }
                // End of string
                self.pos += 1;
                break;
            }

            // Double-quoted strings support backslash escapes
            if (c == '\\' and quote == '"' and self.pos + 1 < self.source.len) {
                self.pos += 1;
                const escaped = self.source[self.pos];
                switch (escaped) {
                    'n' => try result.append(self.allocator, '\n'),
                    'r' => try result.append(self.allocator, '\r'),
                    't' => try result.append(self.allocator, '\t'),
                    'b' => try result.append(self.allocator, 0x08),
                    'f' => try result.append(self.allocator, 0x0C),
                    '0' => try result.append(self.allocator, 0),
                    '\\' => try result.append(self.allocator, '\\'),
                    '"' => try result.append(self.allocator, '"'),
                    '/' => try result.append(self.allocator, '/'),
                    'x' => {
                        // \xXX - 2-digit hex
                        if (self.pos + 2 < self.source.len) {
                            self.pos += 1;
                            const hex = self.source[self.pos .. self.pos + 2];
                            if (std.fmt.parseInt(u8, hex, 16)) |byte| {
                                try result.append(self.allocator, byte);
                                self.pos += 1;
                            } else |_| {
                                // Invalid hex - treat as literal \x
                                try result.append(self.allocator, '\\');
                                try result.append(self.allocator, 'x');
                                continue;
                            }
                        } else {
                            // Not enough characters - treat as literal \x
                            try result.append(self.allocator, '\\');
                            try result.append(self.allocator, 'x');
                        }
                    },
                    'u' => {
                        // \uXXXX - 4-digit unicode
                        if (self.pos + 4 < self.source.len) {
                            self.pos += 1;
                            const hex = self.source[self.pos .. self.pos + 4];
                            if (std.fmt.parseInt(u21, hex, 16)) |cp| {
                                var utf8_buf: [4]u8 = undefined;
                                if (std.unicode.utf8Encode(cp, &utf8_buf)) |len| {
                                    try result.appendSlice(self.allocator, utf8_buf[0..len]);
                                    self.pos += 3;
                                } else |_| {
                                    // Invalid codepoint - treat as literal \u
                                    try result.append(self.allocator, '\\');
                                    try result.append(self.allocator, 'u');
                                    continue;
                                }
                            } else |_| {
                                // Invalid hex - treat as literal \u
                                try result.append(self.allocator, '\\');
                                try result.append(self.allocator, 'u');
                                continue;
                            }
                        } else {
                            // Not enough characters - treat as literal \u
                            try result.append(self.allocator, '\\');
                            try result.append(self.allocator, 'u');
                        }
                    },
                    'U' => {
                        // \UXXXXXXXX - 8-digit unicode
                        if (self.pos + 8 < self.source.len) {
                            self.pos += 1;
                            const hex = self.source[self.pos .. self.pos + 8];
                            if (std.fmt.parseInt(u21, hex, 16)) |cp| {
                                var utf8_buf: [4]u8 = undefined;
                                if (std.unicode.utf8Encode(cp, &utf8_buf)) |len| {
                                    try result.appendSlice(self.allocator, utf8_buf[0..len]);
                                    self.pos += 7;
                                } else |_| {
                                    // Invalid codepoint - treat as literal \U
                                    try result.append(self.allocator, '\\');
                                    try result.append(self.allocator, 'U');
                                    continue;
                                }
                            } else |_| {
                                // Invalid hex - treat as literal \U
                                try result.append(self.allocator, '\\');
                                try result.append(self.allocator, 'U');
                                continue;
                            }
                        } else {
                            // Not enough characters - treat as literal \U
                            try result.append(self.allocator, '\\');
                            try result.append(self.allocator, 'U');
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

        return try self.allocator.dupe(u8, result.items);
    }

    fn unquoteKey(self: *Self, raw: []const u8) ParseError![]const u8 {
        if (raw.len >= 2) {
            if ((raw[0] == '"' and raw[raw.len - 1] == '"') or
                (raw[0] == '\'' and raw[raw.len - 1] == '\''))
            {
                return try self.allocator.dupe(u8, raw[1 .. raw.len - 1]);
            }
        }
        return try self.allocator.dupe(u8, raw);
    }

    fn currentIndent(self: *Self) usize {
        // Go back to start of current line
        var line_start = self.pos;
        while (line_start > 0 and self.source[line_start - 1] != '\n') : (line_start -= 1) {}

        var indent: usize = 0;
        var pos = line_start;
        while (pos < self.source.len and self.source[pos] == ' ') : (pos += 1) {
            indent += 1;
        }
        return indent;
    }

    fn skipWhitespace(self: *Self) void {
        while (self.pos < self.source.len) {
            const c = self.source[self.pos];
            if (c == ' ' or c == '\t' or c == '\r') {
                self.pos += 1;
            } else if (c == '\n') {
                self.pos += 1;
                self.line_number += 1;
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
            } else if (c == '\n') {
                self.pos += 1;
                self.line_number += 1;
            } else if (c == '#') {
                // Skip comment to end of line
                while (self.pos < self.source.len and self.source[self.pos] != '\n') : (self.pos += 1) {}
            } else {
                break;
            }
        }
    }

    fn skipInlineWhitespace(self: *Self) void {
        while (self.pos < self.source.len) {
            const c = self.source[self.pos];
            if (c == ' ' or c == '\t') {
                self.pos += 1;
            } else {
                break;
            }
        }
    }

    fn skipToEndOfLine(self: *Self) void {
        while (self.pos < self.source.len and self.source[self.pos] != '\n') : (self.pos += 1) {}
        if (self.pos < self.source.len) {
            self.pos += 1;
            self.line_number += 1;
        }
    }

    fn matchStr(self: *Self, s: []const u8) bool {
        if (self.pos + s.len > self.source.len) return false;
        return std.mem.eql(u8, self.source[self.pos .. self.pos + s.len], s);
    }

    fn matchChar(self: *Self, c: u8) bool {
        return self.pos < self.source.len and self.source[self.pos] == c;
    }
};

// =============================================================================
// Tests
// =============================================================================

test "manifest output contains yaml name" {
    var buf: [256]u8 = undefined;
    var fbs = std.io.fixedBufferStream(&buf);
    try jn_plugin.outputManifest(fbs.writer(), plugin_meta);
    try std.testing.expect(std.mem.indexOf(u8, fbs.getWritten(), "\"yaml\"") != null);
}

test "parse simple scalar" {
    const allocator = std.testing.allocator;
    var parser = YamlParser.init(allocator, "hello world\n");
    defer parser.deinit();

    const value = try parser.parseDocument();
    defer parser.freeValue(value);

    try std.testing.expect(value == .string);
    try std.testing.expectEqualStrings("hello world", value.string);
}

test "parse boolean values" {
    const allocator = std.testing.allocator;

    var parser1 = YamlParser.init(allocator, "true\n");
    defer parser1.deinit();
    const v1 = try parser1.parseDocument();
    defer parser1.freeValue(v1);
    try std.testing.expect(v1 == .bool);
    try std.testing.expect(v1.bool == true);

    var parser2 = YamlParser.init(allocator, "false\n");
    defer parser2.deinit();
    const v2 = try parser2.parseDocument();
    defer parser2.freeValue(v2);
    try std.testing.expect(v2 == .bool);
    try std.testing.expect(v2.bool == false);
}

test "parse flow array" {
    const allocator = std.testing.allocator;
    var parser = YamlParser.init(allocator, "[1, 2, 3]\n");
    defer parser.deinit();

    const value = try parser.parseDocument();
    defer parser.freeValue(value);

    try std.testing.expect(value == .array);
    try std.testing.expectEqual(@as(usize, 3), value.array.items.len);
}

test "parse flow object" {
    const allocator = std.testing.allocator;
    var parser = YamlParser.init(allocator, "{name: Alice, age: 30}\n");
    defer parser.deinit();

    const value = try parser.parseDocument();
    defer parser.freeValue(value);

    try std.testing.expect(value == .object);
    try std.testing.expectEqual(@as(usize, 2), value.object.count());
}

test "parse block array" {
    const allocator = std.testing.allocator;
    var parser = YamlParser.init(allocator, "- one\n- two\n- three\n");
    defer parser.deinit();

    const value = try parser.parseDocument();
    defer parser.freeValue(value);

    try std.testing.expect(value == .array);
    try std.testing.expectEqual(@as(usize, 3), value.array.items.len);
}

test "parse block object" {
    const allocator = std.testing.allocator;
    var parser = YamlParser.init(allocator, "name: Alice\nage: 30\n");
    defer parser.deinit();

    const value = try parser.parseDocument();
    defer parser.freeValue(value);

    try std.testing.expect(value == .object);
    try std.testing.expectEqual(@as(usize, 2), value.object.count());
}

test "needsQuoting detects reserved words" {
    try std.testing.expect(needsQuoting("true"));
    try std.testing.expect(needsQuoting("false"));
    try std.testing.expect(needsQuoting("null"));
    try std.testing.expect(needsQuoting("yes"));
    try std.testing.expect(needsQuoting("no"));
    try std.testing.expect(!needsQuoting("hello"));
    try std.testing.expect(!needsQuoting("world"));
}

test "parse escape sequences in double quoted strings" {
    const allocator = std.testing.allocator;

    // Test \x escape
    var parser1 = YamlParser.init(allocator, "\"\\x41\\x42\"\n");
    defer parser1.deinit();
    const v1 = try parser1.parseDocument();
    defer parser1.freeValue(v1);
    try std.testing.expect(v1 == .string);
    try std.testing.expectEqualStrings("AB", v1.string);

    // Test incomplete \x is preserved literally
    var parser2 = YamlParser.init(allocator, "\"test\\x\"\n");
    defer parser2.deinit();
    const v2 = try parser2.parseDocument();
    defer parser2.freeValue(v2);
    try std.testing.expect(v2 == .string);
    try std.testing.expectEqualStrings("test\\x", v2.string);
}
