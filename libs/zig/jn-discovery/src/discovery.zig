//! Plugin discovery for JN.
//!
//! Discovers plugins from multiple directories in priority order:
//! 1. Project plugins: .jn/plugins/
//! 2. User plugins: ~/.local/jn/plugins/
//! 3. Bundled plugins: $JN_HOME/plugins/
//!
//! Supports both Zig (binary) and Python (PEP 723) plugins.

const std = @import("std");
const pep723 = @import("pep723.zig");

/// Plugin language/type
pub const PluginLanguage = enum {
    zig,
    python,

    pub fn toString(self: PluginLanguage) []const u8 {
        return switch (self) {
            .zig => "zig",
            .python => "python",
        };
    }
};

/// Plugin source priority (lower = higher priority)
pub const PluginSource = enum {
    project, // .jn/plugins/
    user, // ~/.local/jn/plugins/
    bundled, // $JN_HOME/plugins/

    pub fn priority(self: PluginSource) u8 {
        return switch (self) {
            .project => 0,
            .user => 1,
            .bundled => 2,
        };
    }

    pub fn toString(self: PluginSource) []const u8 {
        return switch (self) {
            .project => "project",
            .user => "user",
            .bundled => "bundled",
        };
    }
};

/// Plugin role
pub const PluginRole = enum {
    format,
    protocol,
    compression,
    database,

    pub fn fromString(s: []const u8) ?PluginRole {
        if (std.mem.eql(u8, s, "format")) return .format;
        if (std.mem.eql(u8, s, "protocol")) return .protocol;
        if (std.mem.eql(u8, s, "compression")) return .compression;
        if (std.mem.eql(u8, s, "database")) return .database;
        return null;
    }

    pub fn toString(self: PluginRole) []const u8 {
        return switch (self) {
            .format => "format",
            .protocol => "protocol",
            .compression => "compression",
            .database => "database",
        };
    }
};

/// Plugin mode
pub const PluginMode = enum {
    read,
    write,
    raw,
    profiles,

    pub fn fromString(s: []const u8) ?PluginMode {
        if (std.mem.eql(u8, s, "read")) return .read;
        if (std.mem.eql(u8, s, "write")) return .write;
        if (std.mem.eql(u8, s, "raw")) return .raw;
        if (std.mem.eql(u8, s, "profiles")) return .profiles;
        return null;
    }
};

/// Discovered plugin information
pub const PluginInfo = struct {
    /// Plugin name (e.g., "csv", "json", "xlsx")
    name: []const u8,

    /// Plugin version (semver)
    version: []const u8,

    /// Regex patterns this plugin matches
    matches: []const []const u8,

    /// Plugin role
    role: PluginRole,

    /// Supported modes
    modes: []const PluginMode,

    /// Profile type (for plugins supporting profiles mode)
    profile_type: ?[]const u8,

    /// Plugin language (zig or python)
    language: PluginLanguage,

    /// Source (project, user, bundled)
    source: PluginSource,

    /// Full path to the plugin executable/script
    path: []const u8,

    /// File modification time (for cache invalidation)
    mtime: i128,

    /// Allocator that owns the memory
    allocator: std.mem.Allocator,

    pub fn deinit(self: *PluginInfo) void {
        self.allocator.free(self.name);
        self.allocator.free(self.version);
        for (self.matches) |m| self.allocator.free(m);
        self.allocator.free(self.matches);
        self.allocator.free(self.modes);
        if (self.profile_type) |pt| self.allocator.free(pt);
        self.allocator.free(self.path);
    }

    /// Calculate pattern specificity (longest pattern wins)
    pub fn maxPatternLength(self: PluginInfo) usize {
        var max: usize = 0;
        for (self.matches) |pattern| {
            if (pattern.len > max) max = pattern.len;
        }
        return max;
    }

    /// Check if plugin supports a given mode
    pub fn supportsMode(self: PluginInfo, mode: PluginMode) bool {
        for (self.modes) |m| {
            if (m == mode) return true;
        }
        return false;
    }
};

/// Discovery configuration
pub const DiscoveryConfig = struct {
    /// Project root for .jn/plugins/
    project_root: ?[]const u8 = null,

    /// User home directory
    home_dir: ?[]const u8 = null,

    /// JN home directory ($JN_HOME)
    jn_home: ?[]const u8 = null,

    /// Timeout for plugin --jn-meta execution (ms)
    exec_timeout_ms: u32 = 5000,
};

/// Get plugin directories in priority order
pub fn getPluginDirs(allocator: std.mem.Allocator, config: DiscoveryConfig) ![]PluginDir {
    var dirs: std.ArrayListUnmanaged(PluginDir) = .empty;
    errdefer {
        for (dirs.items) |d| d.deinit(allocator);
        dirs.deinit(allocator);
    }

    // 1. Project plugins
    if (config.project_root) |root| {
        const zig_dir = try std.fmt.allocPrint(allocator, "{s}/.jn/plugins/zig", .{root});
        const py_dir = try std.fmt.allocPrint(allocator, "{s}/.jn/plugins/python", .{root});
        try dirs.append(allocator, .{ .path = zig_dir, .source = .project, .language = .zig });
        try dirs.append(allocator, .{ .path = py_dir, .source = .project, .language = .python });
    }

    // 2. User plugins
    const home = config.home_dir orelse std.posix.getenv("HOME");
    if (home) |h| {
        const zig_dir = try std.fmt.allocPrint(allocator, "{s}/.local/jn/plugins/zig", .{h});
        const py_dir = try std.fmt.allocPrint(allocator, "{s}/.local/jn/plugins/python", .{h});
        try dirs.append(allocator, .{ .path = zig_dir, .source = .user, .language = .zig });
        try dirs.append(allocator, .{ .path = py_dir, .source = .user, .language = .python });
    }

    // 3. Bundled plugins
    const jn_home = config.jn_home orelse std.posix.getenv("JN_HOME");
    if (jn_home) |jh| {
        const zig_dir = try std.fmt.allocPrint(allocator, "{s}/plugins/zig", .{jh});
        const py_dir = try std.fmt.allocPrint(allocator, "{s}/plugins", .{jh});
        try dirs.append(allocator, .{ .path = zig_dir, .source = .bundled, .language = .zig });
        try dirs.append(allocator, .{ .path = py_dir, .source = .bundled, .language = .python });
    }

    return dirs.toOwnedSlice(allocator);
}

/// Plugin directory entry
pub const PluginDir = struct {
    path: []const u8,
    source: PluginSource,
    language: PluginLanguage,

    pub fn deinit(self: PluginDir, allocator: std.mem.Allocator) void {
        allocator.free(self.path);
    }
};

/// Discover a Zig plugin by executing --jn-meta
pub fn discoverZigPlugin(
    allocator: std.mem.Allocator,
    path: []const u8,
    source: PluginSource,
) !?PluginInfo {
    // Check file exists and is executable
    const stat = std.fs.cwd().statFile(path) catch return null;
    if (stat.kind != .file) return null;

    // Execute plugin with --jn-meta
    var child = std.process.Child.init(&.{ path, "--jn-meta" }, allocator);
    child.stdout_behavior = .Pipe;
    child.stderr_behavior = .Ignore;

    child.spawn() catch return null;

    // Read stdout (limited to 64KB)
    const stdout = child.stdout.?.readToEndAlloc(allocator, 64 * 1024) catch {
        _ = child.wait() catch {};
        return null;
    };
    defer allocator.free(stdout);

    const result = child.wait() catch return null;
    // Check for successful exit (not signal/stop/unknown)
    switch (result) {
        .Exited => |code| if (code != 0) return null,
        else => return null, // Signal, Stop, or Unknown - treat as failure
    }

    // Parse JSON output
    const parsed = std.json.parseFromSlice(std.json.Value, allocator, stdout, .{}) catch return null;
    defer parsed.deinit();

    return parsePluginMeta(allocator, parsed.value, path, source, .zig, stat.mtime);
}

/// Discover a Python plugin by parsing PEP 723 metadata
pub fn discoverPythonPlugin(
    allocator: std.mem.Allocator,
    path: []const u8,
    source: PluginSource,
) !?PluginInfo {
    // Read file
    const file = std.fs.cwd().openFile(path, .{}) catch return null;
    defer file.close();

    const stat = file.stat() catch return null;
    const content = file.readToEndAlloc(allocator, 256 * 1024) catch return null; // 256KB max
    defer allocator.free(content);

    // Parse PEP 723 metadata
    const meta = pep723.parseToolJn(allocator, content) catch return null;
    if (meta == null) return null;
    defer {
        var m = meta.?;
        m.deinit();
    }

    return parsePluginMeta(allocator, meta.?.value, path, source, .python, stat.mtime);
}

/// Parse plugin metadata from JSON value
fn parsePluginMeta(
    allocator: std.mem.Allocator,
    value: std.json.Value,
    path: []const u8,
    source: PluginSource,
    language: PluginLanguage,
    mtime: i128,
) !?PluginInfo {
    if (value != .object) return null;
    const obj = value.object;

    // Required: name
    const name_val = obj.get("name") orelse return null;
    if (name_val != .string) return null;
    const name = try allocator.dupe(u8, name_val.string);
    errdefer allocator.free(name);

    // Optional: version (default "0.0.0")
    const version = blk: {
        if (obj.get("version")) |v| {
            if (v == .string) break :blk try allocator.dupe(u8, v.string);
        }
        break :blk try allocator.dupe(u8, "0.0.0");
    };
    errdefer allocator.free(version);

    // Required: matches
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
    if (matches.items.len == 0) return null;
    const matches_slice = try matches.toOwnedSlice(allocator);
    errdefer {
        for (matches_slice) |m| allocator.free(m);
        allocator.free(matches_slice);
    }

    // Optional: role (default format)
    const role = blk: {
        if (obj.get("role")) |r| {
            if (r == .string) {
                if (PluginRole.fromString(r.string)) |role| break :blk role;
            }
        }
        break :blk PluginRole.format;
    };

    // Optional: modes (default [read, write])
    const modes = blk: {
        if (obj.get("modes")) |m| {
            if (m == .array) {
                var mode_list: std.ArrayListUnmanaged(PluginMode) = .empty;
                errdefer mode_list.deinit(allocator);
                for (m.array.items) |item| {
                    if (item == .string) {
                        if (PluginMode.fromString(item.string)) |pm| {
                            try mode_list.append(allocator, pm);
                        }
                    }
                }
                if (mode_list.items.len > 0) {
                    break :blk try mode_list.toOwnedSlice(allocator);
                }
                mode_list.deinit(allocator);
            }
        }
        const default_modes = try allocator.alloc(PluginMode, 2);
        default_modes[0] = .read;
        default_modes[1] = .write;
        break :blk default_modes;
    };
    errdefer allocator.free(modes);

    // Optional: profile_type
    const profile_type: ?[]const u8 = blk: {
        if (obj.get("profile_type")) |pt| {
            if (pt == .string) break :blk try allocator.dupe(u8, pt.string);
        }
        break :blk null;
    };
    errdefer if (profile_type) |pt| allocator.free(pt);

    // Copy path
    const path_copy = try allocator.dupe(u8, path);
    errdefer allocator.free(path_copy);

    return PluginInfo{
        .name = name,
        .version = version,
        .matches = matches_slice,
        .role = role,
        .modes = modes,
        .profile_type = profile_type,
        .language = language,
        .source = source,
        .path = path_copy,
        .mtime = mtime,
        .allocator = allocator,
    };
}

/// Scan a directory for plugins
pub fn scanDirectory(
    allocator: std.mem.Allocator,
    dir_path: []const u8,
    source: PluginSource,
    language: PluginLanguage,
) ![]PluginInfo {
    var plugins: std.ArrayListUnmanaged(PluginInfo) = .empty;
    errdefer {
        for (plugins.items) |*p| p.deinit();
        plugins.deinit(allocator);
    }

    // Open directory
    var dir = std.fs.cwd().openDir(dir_path, .{ .iterate = true }) catch return plugins.toOwnedSlice(allocator);
    defer dir.close();

    var iter = dir.iterate();
    while (try iter.next()) |entry| {
        const full_path = try std.fmt.allocPrint(allocator, "{s}/{s}", .{ dir_path, entry.name });
        defer allocator.free(full_path);

        const plugin_info: ?PluginInfo = switch (language) {
            .zig => blk: {
                // For Zig, look for bin/ subdirectory with binary
                if (entry.kind == .directory) {
                    const bin_path = try std.fmt.allocPrint(allocator, "{s}/bin/{s}", .{ full_path, entry.name });
                    defer allocator.free(bin_path);
                    break :blk try discoverZigPlugin(allocator, bin_path, source);
                }
                break :blk null;
            },
            .python => blk: {
                // For Python, look for *.py files with tool.jn metadata
                if (entry.kind == .file and std.mem.endsWith(u8, entry.name, "_.py")) {
                    break :blk try discoverPythonPlugin(allocator, full_path, source);
                }
                // Also scan subdirectories (formats/, protocols/, etc.)
                if (entry.kind == .directory) {
                    const sub_plugins = try scanDirectory(allocator, full_path, source, language);
                    defer allocator.free(sub_plugins);
                    for (sub_plugins) |p| {
                        try plugins.append(allocator, p);
                    }
                }
                break :blk null;
            },
        };

        if (plugin_info) |info| {
            try plugins.append(allocator, info);
        }
    }

    return plugins.toOwnedSlice(allocator);
}

/// Discover all plugins from configured directories
pub fn discoverAll(allocator: std.mem.Allocator, config: DiscoveryConfig) ![]PluginInfo {
    var all_plugins: std.ArrayListUnmanaged(PluginInfo) = .empty;
    errdefer {
        for (all_plugins.items) |*p| p.deinit();
        all_plugins.deinit(allocator);
    }

    const dirs = try getPluginDirs(allocator, config);
    defer {
        for (dirs) |d| d.deinit(allocator);
        allocator.free(dirs);
    }

    for (dirs) |dir| {
        const plugins = try scanDirectory(allocator, dir.path, dir.source, dir.language);
        defer allocator.free(plugins);
        for (plugins) |p| {
            try all_plugins.append(allocator, p);
        }
    }

    return all_plugins.toOwnedSlice(allocator);
}

// ============================================================================
// Tests
// ============================================================================

test "PluginSource priority order" {
    try std.testing.expectEqual(@as(u8, 0), PluginSource.project.priority());
    try std.testing.expectEqual(@as(u8, 1), PluginSource.user.priority());
    try std.testing.expectEqual(@as(u8, 2), PluginSource.bundled.priority());
}

test "PluginRole.fromString parses valid roles" {
    try std.testing.expectEqual(PluginRole.format, PluginRole.fromString("format").?);
    try std.testing.expectEqual(PluginRole.protocol, PluginRole.fromString("protocol").?);
    try std.testing.expectEqual(PluginRole.compression, PluginRole.fromString("compression").?);
    try std.testing.expect(PluginRole.fromString("invalid") == null);
}

test "PluginMode.fromString parses valid modes" {
    try std.testing.expectEqual(PluginMode.read, PluginMode.fromString("read").?);
    try std.testing.expectEqual(PluginMode.write, PluginMode.fromString("write").?);
    try std.testing.expectEqual(PluginMode.raw, PluginMode.fromString("raw").?);
    try std.testing.expect(PluginMode.fromString("invalid") == null);
}

test "getPluginDirs returns correct directories" {
    const allocator = std.testing.allocator;

    const dirs = try getPluginDirs(allocator, .{
        .project_root = "/project",
        .home_dir = "/home/user",
        .jn_home = "/opt/jn",
    });
    defer {
        for (dirs) |d| d.deinit(allocator);
        allocator.free(dirs);
    }

    // 2 dirs per source (zig + python) x 3 sources = 6 total
    try std.testing.expectEqual(@as(usize, 6), dirs.len);

    // First should be project zig
    try std.testing.expectEqualStrings("/project/.jn/plugins/zig", dirs[0].path);
    try std.testing.expectEqual(PluginSource.project, dirs[0].source);
    try std.testing.expectEqual(PluginLanguage.zig, dirs[0].language);
}

test "parsePluginMeta extracts fields correctly" {
    const allocator = std.testing.allocator;

    const json_str =
        \\{"name": "csv", "version": "1.0.0", "matches": [".*\\.csv$"], "role": "format", "modes": ["read", "write"]}
    ;
    const parsed = try std.json.parseFromSlice(std.json.Value, allocator, json_str, .{});
    defer parsed.deinit();

    var info = (try parsePluginMeta(allocator, parsed.value, "/test/csv", .bundled, .zig, 0)).?;
    defer info.deinit();

    try std.testing.expectEqualStrings("csv", info.name);
    try std.testing.expectEqualStrings("1.0.0", info.version);
    try std.testing.expectEqual(@as(usize, 1), info.matches.len);
    try std.testing.expectEqualStrings(".*\\.csv$", info.matches[0]);
    try std.testing.expectEqual(PluginRole.format, info.role);
    try std.testing.expectEqual(@as(usize, 2), info.modes.len);
}

test "parsePluginMeta handles missing optional fields" {
    const allocator = std.testing.allocator;

    const json_str =
        \\{"name": "test", "matches": [".*\\.test$"]}
    ;
    const parsed = try std.json.parseFromSlice(std.json.Value, allocator, json_str, .{});
    defer parsed.deinit();

    var info = (try parsePluginMeta(allocator, parsed.value, "/test/plugin", .user, .python, 0)).?;
    defer info.deinit();

    try std.testing.expectEqualStrings("test", info.name);
    try std.testing.expectEqualStrings("0.0.0", info.version); // Default
    try std.testing.expectEqual(PluginRole.format, info.role); // Default
    try std.testing.expectEqual(@as(usize, 2), info.modes.len); // Default [read, write]
}

test "PluginInfo.maxPatternLength finds longest pattern" {
    const info = PluginInfo{
        .name = "test",
        .version = "1.0.0",
        .matches = &.{ ".*\\.csv$", ".*\\.tsv$", ".*\\.tab$" },
        .role = .format,
        .modes = &.{ .read, .write },
        .profile_type = null,
        .language = .zig,
        .source = .bundled,
        .path = "/test",
        .mtime = 0,
        .allocator = std.testing.allocator,
    };

    // Pattern ".*\.csv$" is 8 characters after escape processing
    try std.testing.expectEqual(@as(usize, 8), info.maxPatternLength());
}

test "PluginInfo.supportsMode checks mode support" {
    const info = PluginInfo{
        .name = "test",
        .version = "1.0.0",
        .matches = &.{".*"},
        .role = .format,
        .modes = &.{ .read, .write },
        .profile_type = null,
        .language = .zig,
        .source = .bundled,
        .path = "/test",
        .mtime = 0,
        .allocator = std.testing.allocator,
    };

    try std.testing.expect(info.supportsMode(.read));
    try std.testing.expect(info.supportsMode(.write));
    try std.testing.expect(!info.supportsMode(.raw));
    try std.testing.expect(!info.supportsMode(.profiles));
}
