//! Plugin cache for JN discovery.
//!
//! Caches discovered plugin metadata to avoid re-scanning directories
//! and re-executing plugins on every command.
//!
//! Cache location: $JN_HOME/cache/plugins.json
//!
//! Cache format:
//! ```json
//! {
//!   "version": 1,
//!   "plugins": [
//!     {
//!       "name": "csv",
//!       "path": "/path/to/csv",
//!       "mtime": 1234567890,
//!       ...
//!     }
//!   ]
//! }
//! ```

const std = @import("std");
const discovery = @import("discovery.zig");

/// Cache file version (increment when format changes)
const CACHE_VERSION: u32 = 1;

/// Cached plugin entry
pub const CachedPlugin = struct {
    name: []const u8,
    version: []const u8,
    matches: []const []const u8,
    role: []const u8,
    modes: []const []const u8,
    profile_type: ?[]const u8,
    language: []const u8,
    source: []const u8,
    path: []const u8,
    mtime: i128,
};

/// Plugin cache
pub const Cache = struct {
    /// Cache file path
    path: []const u8,

    /// Allocator
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator, jn_home: ?[]const u8) !Cache {
        const home = jn_home orelse std.posix.getenv("JN_HOME") orelse {
            // Default to ~/.local/jn if JN_HOME not set
            const user_home = std.posix.getenv("HOME") orelse return error.NoHomeDir;
            const default_path = try std.fmt.allocPrint(allocator, "{s}/.local/jn/cache/plugins.json", .{user_home});
            return .{ .path = default_path, .allocator = allocator };
        };

        const cache_path = try std.fmt.allocPrint(allocator, "{s}/cache/plugins.json", .{home});
        return .{ .path = cache_path, .allocator = allocator };
    }

    pub fn deinit(self: *Cache) void {
        self.allocator.free(self.path);
    }

    /// Load plugins from cache.
    ///
    /// Returns null if cache doesn't exist or is invalid.
    pub fn load(self: Cache) ?[]discovery.PluginInfo {
        const file = std.fs.cwd().openFile(self.path, .{}) catch return null;
        defer file.close();

        const content = file.readToEndAlloc(self.allocator, 10 * 1024 * 1024) catch return null; // 10MB max
        defer self.allocator.free(content);

        const parsed = std.json.parseFromSlice(std.json.Value, self.allocator, content, .{}) catch return null;
        defer parsed.deinit();

        return parseCache(self.allocator, parsed.value) catch null;
    }

    /// Save plugins to cache.
    pub fn save(self: Cache, plugins: []const discovery.PluginInfo) !void {
        // Ensure cache directory exists
        const dir_path = std.fs.path.dirname(self.path) orelse return error.InvalidPath;
        std.fs.cwd().makePath(dir_path) catch {};

        // Build JSON
        var json_buf: std.ArrayListUnmanaged(u8) = .empty;
        defer json_buf.deinit(self.allocator);

        const writer = json_buf.writer(self.allocator);

        try writer.writeAll("{\"version\":");
        try writer.print("{d}", .{CACHE_VERSION});
        try writer.writeAll(",\"plugins\":[");

        for (plugins, 0..) |plugin, i| {
            if (i > 0) try writer.writeByte(',');
            try writePluginJson(writer, plugin);
        }

        try writer.writeAll("]}");

        // Write atomically (write to temp, then rename)
        const temp_path = try std.fmt.allocPrint(self.allocator, "{s}.tmp", .{self.path});
        defer self.allocator.free(temp_path);

        const temp_file = try std.fs.cwd().createFile(temp_path, .{});
        errdefer std.fs.cwd().deleteFile(temp_path) catch {};

        try temp_file.writeAll(json_buf.items);
        temp_file.close();

        // Rename temp to final
        std.fs.cwd().rename(temp_path, self.path) catch |err| {
            std.fs.cwd().deleteFile(temp_path) catch {};
            return err;
        };
    }

    /// Check if cache is valid (all files still have same mtime).
    pub fn isValid(_: Cache, plugins: []const discovery.PluginInfo) bool {
        for (plugins) |plugin| {
            const stat = std.fs.cwd().statFile(plugin.path) catch return false;
            if (stat.mtime != plugin.mtime) return false;
        }
        return true;
    }

    /// Invalidate cache (delete cache file).
    pub fn invalidate(self: Cache) void {
        std.fs.cwd().deleteFile(self.path) catch {};
    }
};

/// Write a plugin as JSON
fn writePluginJson(writer: anytype, plugin: discovery.PluginInfo) !void {
    try writer.writeAll("{");

    // name
    try writer.writeAll("\"name\":");
    try writeJsonString(writer, plugin.name);

    // version
    try writer.writeAll(",\"version\":");
    try writeJsonString(writer, plugin.version);

    // matches
    try writer.writeAll(",\"matches\":[");
    for (plugin.matches, 0..) |m, i| {
        if (i > 0) try writer.writeByte(',');
        try writeJsonString(writer, m);
    }
    try writer.writeByte(']');

    // role
    try writer.writeAll(",\"role\":");
    try writeJsonString(writer, plugin.role.toString());

    // modes
    try writer.writeAll(",\"modes\":[");
    for (plugin.modes, 0..) |m, i| {
        if (i > 0) try writer.writeByte(',');
        try writeJsonString(writer, @tagName(m));
    }
    try writer.writeByte(']');

    // profile_type
    if (plugin.profile_type) |pt| {
        try writer.writeAll(",\"profile_type\":");
        try writeJsonString(writer, pt);
    }

    // language
    try writer.writeAll(",\"language\":");
    try writeJsonString(writer, plugin.language.toString());

    // source
    try writer.writeAll(",\"source\":");
    try writeJsonString(writer, plugin.source.toString());

    // path
    try writer.writeAll(",\"path\":");
    try writeJsonString(writer, plugin.path);

    // mtime
    try writer.writeAll(",\"mtime\":");
    try writer.print("{d}", .{plugin.mtime});

    try writer.writeByte('}');
}

/// Write a JSON-escaped string
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

/// Parse cache JSON into plugin info array
fn parseCache(allocator: std.mem.Allocator, value: std.json.Value) ![]discovery.PluginInfo {
    if (value != .object) return error.InvalidCache;
    const obj = value.object;

    // Check version
    const version_val = obj.get("version") orelse return error.InvalidCache;
    if (version_val != .integer or version_val.integer != CACHE_VERSION) {
        return error.CacheVersionMismatch;
    }

    // Get plugins array
    const plugins_val = obj.get("plugins") orelse return error.InvalidCache;
    if (plugins_val != .array) return error.InvalidCache;

    var plugins: std.ArrayListUnmanaged(discovery.PluginInfo) = .empty;
    errdefer {
        for (plugins.items) |*p| p.deinit();
        plugins.deinit(allocator);
    }

    for (plugins_val.array.items) |item| {
        if (try parseCachedPlugin(allocator, item)) |plugin| {
            try plugins.append(allocator, plugin);
        }
    }

    return plugins.toOwnedSlice(allocator);
}

/// Parse a single cached plugin entry
fn parseCachedPlugin(allocator: std.mem.Allocator, value: std.json.Value) !?discovery.PluginInfo {
    if (value != .object) return null;
    const obj = value.object;

    // Required fields
    const name_val = obj.get("name") orelse return null;
    if (name_val != .string) return null;
    const name = try allocator.dupe(u8, name_val.string);
    errdefer allocator.free(name);

    const version_val = obj.get("version") orelse return null;
    if (version_val != .string) return null;
    const version = try allocator.dupe(u8, version_val.string);
    errdefer allocator.free(version);

    const path_val = obj.get("path") orelse return null;
    if (path_val != .string) return null;
    const path = try allocator.dupe(u8, path_val.string);
    errdefer allocator.free(path);

    // Matches array
    const matches_val = obj.get("matches") orelse return null;
    if (matches_val != .array) return null;
    var matches: std.ArrayListUnmanaged([]const u8) = .empty;
    errdefer {
        for (matches.items) |m| allocator.free(m);
        matches.deinit(allocator);
    }
    for (matches_val.array.items) |item| {
        if (item == .string) {
            try matches.append(allocator, try allocator.dupe(u8, item.string));
        }
    }
    const matches_slice = try matches.toOwnedSlice(allocator);
    errdefer {
        for (matches_slice) |m| allocator.free(m);
        allocator.free(matches_slice);
    }

    // Role
    const role_val = obj.get("role") orelse return null;
    if (role_val != .string) return null;
    const role = discovery.PluginRole.fromString(role_val.string) orelse .format;

    // Modes array
    const modes_val = obj.get("modes") orelse return null;
    if (modes_val != .array) return null;
    var modes: std.ArrayListUnmanaged(discovery.PluginMode) = .empty;
    errdefer modes.deinit(allocator);
    for (modes_val.array.items) |item| {
        if (item == .string) {
            if (discovery.PluginMode.fromString(item.string)) |m| {
                try modes.append(allocator, m);
            }
        }
    }
    const modes_slice = try modes.toOwnedSlice(allocator);
    errdefer allocator.free(modes_slice);

    // Language
    const lang_val = obj.get("language") orelse return null;
    if (lang_val != .string) return null;
    const language: discovery.PluginLanguage = if (std.mem.eql(u8, lang_val.string, "zig")) .zig else .python;

    // Source
    const source_val = obj.get("source") orelse return null;
    if (source_val != .string) return null;
    const source: discovery.PluginSource = blk: {
        if (std.mem.eql(u8, source_val.string, "project")) break :blk .project;
        if (std.mem.eql(u8, source_val.string, "user")) break :blk .user;
        break :blk .bundled;
    };

    // Mtime
    const mtime_val = obj.get("mtime") orelse return null;
    const mtime: i128 = switch (mtime_val) {
        .integer => |i| i,
        else => 0,
    };

    // Profile type (optional)
    const profile_type: ?[]const u8 = blk: {
        if (obj.get("profile_type")) |pt| {
            if (pt == .string) break :blk try allocator.dupe(u8, pt.string);
        }
        break :blk null;
    };

    return discovery.PluginInfo{
        .name = name,
        .version = version,
        .matches = matches_slice,
        .role = role,
        .modes = modes_slice,
        .profile_type = profile_type,
        .language = language,
        .source = source,
        .path = path,
        .mtime = mtime,
        .allocator = allocator,
    };
}

// ============================================================================
// Tests
// ============================================================================

test "Cache.init creates path with JN_HOME" {
    const allocator = std.testing.allocator;

    var cache = try Cache.init(allocator, "/opt/jn");
    defer cache.deinit();

    try std.testing.expectEqualStrings("/opt/jn/cache/plugins.json", cache.path);
}

test "writeJsonString escapes special characters" {
    const allocator = std.testing.allocator;

    var buf: std.ArrayListUnmanaged(u8) = .empty;
    defer buf.deinit(allocator);

    try writeJsonString(buf.writer(allocator), "hello");
    try std.testing.expectEqualStrings("\"hello\"", buf.items);

    buf.clearRetainingCapacity();
    try writeJsonString(buf.writer(allocator), "say \"hi\"");
    try std.testing.expectEqualStrings("\"say \\\"hi\\\"\"", buf.items);

    buf.clearRetainingCapacity();
    try writeJsonString(buf.writer(allocator), "line1\nline2");
    try std.testing.expectEqualStrings("\"line1\\nline2\"", buf.items);
}

test "writePluginJson produces valid JSON" {
    const allocator = std.testing.allocator;

    var buf: std.ArrayListUnmanaged(u8) = .empty;
    defer buf.deinit(allocator);

    const modes: []const discovery.PluginMode = &.{ .read, .write };
    const matches: []const []const u8 = &.{".*\\.csv$"};

    const plugin = discovery.PluginInfo{
        .name = "csv",
        .version = "1.0.0",
        .matches = matches,
        .role = .format,
        .modes = modes,
        .profile_type = null,
        .language = .zig,
        .source = .bundled,
        .path = "/plugins/csv",
        .mtime = 12345,
        .allocator = allocator,
    };

    try writePluginJson(buf.writer(allocator), plugin);

    // Verify it's valid JSON by parsing it
    const parsed = try std.json.parseFromSlice(std.json.Value, allocator, buf.items, .{});
    defer parsed.deinit();

    try std.testing.expect(parsed.value == .object);
    try std.testing.expectEqualStrings("csv", parsed.value.object.get("name").?.string);
}

test "parseCache handles valid cache" {
    const allocator = std.testing.allocator;

    const json_str =
        \\{"version":1,"plugins":[{"name":"csv","version":"1.0.0","matches":[".*\\.csv$"],"role":"format","modes":["read","write"],"language":"zig","source":"bundled","path":"/plugins/csv","mtime":0}]}
    ;

    const parsed = try std.json.parseFromSlice(std.json.Value, allocator, json_str, .{});
    defer parsed.deinit();

    const plugins = try parseCache(allocator, parsed.value);
    defer {
        for (plugins) |*p| {
            var plugin = p.*;
            plugin.deinit();
        }
        allocator.free(plugins);
    }

    try std.testing.expectEqual(@as(usize, 1), plugins.len);
    try std.testing.expectEqualStrings("csv", plugins[0].name);
}

test "parseCache rejects wrong version" {
    const allocator = std.testing.allocator;

    const json_str =
        \\{"version":999,"plugins":[]}
    ;

    const parsed = try std.json.parseFromSlice(std.json.Value, allocator, json_str, .{});
    defer parsed.deinit();

    const result = parseCache(allocator, parsed.value);
    try std.testing.expectError(error.CacheVersionMismatch, result);
}
