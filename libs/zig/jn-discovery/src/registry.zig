//! Plugin registry for matching addresses to plugins.
//!
//! The registry stores discovered plugins and provides pattern matching
//! to find the best plugin for a given address.
//!
//! Resolution priority:
//! 1. Source: project > user > bundled
//! 2. Language: Zig > Python (within same source)
//! 3. Specificity: longer patterns win (more specific)

const std = @import("std");
const discovery = @import("discovery.zig");

/// Plugin registry
pub const Registry = struct {
    /// All registered plugins
    plugins: std.ArrayListUnmanaged(discovery.PluginInfo),

    /// Allocator
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator) Registry {
        return .{
            .plugins = .empty,
            .allocator = allocator,
        };
    }

    pub fn deinit(self: *Registry) void {
        for (self.plugins.items) |*p| {
            p.deinit();
        }
        self.plugins.deinit(self.allocator);
    }

    /// Add a plugin to the registry
    pub fn add(self: *Registry, plugin: discovery.PluginInfo) !void {
        try self.plugins.append(self.allocator, plugin);
    }

    /// Add multiple plugins to the registry
    pub fn addAll(self: *Registry, plugins: []discovery.PluginInfo) !void {
        for (plugins) |p| {
            try self.plugins.append(self.allocator, p);
        }
    }

    /// Find the best matching plugin for an address and mode.
    ///
    /// Returns null if no plugin matches.
    pub fn findPlugin(
        self: Registry,
        address: []const u8,
        mode: discovery.PluginMode,
    ) ?*const discovery.PluginInfo {
        var best_match: ?*const discovery.PluginInfo = null;
        var best_score: i32 = std.math.minInt(i32);

        for (self.plugins.items) |*plugin| {
            // Check if plugin supports the requested mode
            if (!plugin.supportsMode(mode)) continue;

            // Check if any pattern matches
            const match_result = matchAddress(plugin.*, address);
            if (match_result.matched) {
                const score = calculateScore(plugin.*, match_result.pattern_len);
                if (score > best_score) {
                    best_score = score;
                    best_match = plugin;
                }
            }
        }

        return best_match;
    }

    /// Find all plugins that match an address (regardless of mode).
    ///
    /// Returns plugins sorted by score (best first).
    pub fn findAllMatching(
        self: Registry,
        allocator: std.mem.Allocator,
        address: []const u8,
    ) ![]const *const discovery.PluginInfo {
        var matches: std.ArrayListUnmanaged(MatchEntry) = .empty;
        defer matches.deinit(allocator);

        for (self.plugins.items) |*plugin| {
            const match_result = matchAddress(plugin.*, address);
            if (match_result.matched) {
                const score = calculateScore(plugin.*, match_result.pattern_len);
                try matches.append(allocator, .{ .plugin = plugin, .score = score });
            }
        }

        // Sort by score (highest first)
        std.mem.sort(MatchEntry, matches.items, {}, struct {
            fn lessThan(_: void, a: MatchEntry, b: MatchEntry) bool {
                return a.score > b.score;
            }
        }.lessThan);

        // Extract just the plugin pointers
        var result = try allocator.alloc(*const discovery.PluginInfo, matches.items.len);
        for (matches.items, 0..) |entry, i| {
            result[i] = entry.plugin;
        }

        return result;
    }

    /// Get a plugin by name
    pub fn getByName(self: Registry, name: []const u8) ?*const discovery.PluginInfo {
        for (self.plugins.items) |*plugin| {
            if (std.mem.eql(u8, plugin.name, name)) {
                return plugin;
            }
        }
        return null;
    }

    /// Get all plugins of a specific role
    pub fn getByRole(
        self: Registry,
        allocator: std.mem.Allocator,
        role: discovery.PluginRole,
    ) ![]const *const discovery.PluginInfo {
        var result: std.ArrayListUnmanaged(*const discovery.PluginInfo) = .empty;
        errdefer result.deinit(allocator);

        for (self.plugins.items) |*plugin| {
            if (plugin.role == role) {
                try result.append(allocator, plugin);
            }
        }

        return result.toOwnedSlice(allocator);
    }

    /// Get count of registered plugins
    pub fn count(self: Registry) usize {
        return self.plugins.items.len;
    }
};

const MatchEntry = struct {
    plugin: *const discovery.PluginInfo,
    score: i32,
};

/// Match result from pattern matching
const MatchResult = struct {
    matched: bool,
    pattern_len: usize,
};

/// Match an address against a plugin's patterns.
///
/// Uses simple pattern matching (not full regex) for performance.
/// Patterns are treated as:
/// - `^prefix` - starts with prefix
/// - `suffix$` - ends with suffix
/// - `.*\.ext$` - ends with .ext
/// - Exact match otherwise
fn matchAddress(plugin: discovery.PluginInfo, address: []const u8) MatchResult {
    for (plugin.matches) |pattern| {
        if (matchPattern(pattern, address)) {
            return .{ .matched = true, .pattern_len = pattern.len };
        }
    }
    return .{ .matched = false, .pattern_len = 0 };
}

/// Match a single pattern against an address.
///
/// Supports common regex patterns used in JN plugins:
/// - `^protocol://` - starts with protocol
/// - `.*\.ext$` - ends with extension
/// - `.*\.ext1|.*\.ext2` - multiple extensions (via |)
fn matchPattern(pattern: []const u8, address: []const u8) bool {
    // Handle OR patterns (e.g., ".*\.csv$|.*\.tsv$")
    var iter = std.mem.splitScalar(u8, pattern, '|');
    while (iter.next()) |sub_pattern| {
        if (matchSinglePattern(sub_pattern, address)) return true;
    }
    return false;
}

fn matchSinglePattern(pattern: []const u8, address: []const u8) bool {
    // Empty pattern matches nothing
    if (pattern.len == 0) return false;

    // Handle start anchor: ^prefix
    if (pattern[0] == '^') {
        const prefix = extractLiteralPrefix(pattern[1..]);
        return std.mem.startsWith(u8, address, prefix);
    }

    // Handle end anchor with wildcard: .*\.ext$
    if (std.mem.startsWith(u8, pattern, ".*") and pattern[pattern.len - 1] == '$') {
        return endsWithUnescaped(address, pattern[2 .. pattern.len - 1]);
    }

    // Handle end anchor only: suffix$
    if (pattern[pattern.len - 1] == '$') {
        return endsWithUnescaped(address, pattern[0 .. pattern.len - 1]);
    }

    // Exact match
    return std.mem.eql(u8, pattern, address);
}

/// Extract literal prefix from a regex-like pattern.
/// Handles escaped characters like \. -> .
fn extractLiteralPrefix(pattern: []const u8) []const u8 {
    var end: usize = 0;
    var i: usize = 0;
    while (i < pattern.len) {
        const c = pattern[i];
        // Stop at regex metacharacters
        if (c == '.' or c == '*' or c == '+' or c == '?' or c == '[' or c == '(' or c == '$') {
            break;
        }
        // Handle escape
        if (c == '\\' and i + 1 < pattern.len) {
            i += 2;
            end = i;
            continue;
        }
        i += 1;
        end = i;
    }
    return pattern[0..end];
}

fn endsWithUnescaped(address: []const u8, pattern: []const u8) bool {
    var address_i: usize = address.len;
    var pattern_i: usize = pattern.len;

    while (pattern_i > 0) {
        pattern_i -= 1;
        const c = pattern[pattern_i];
        if (pattern_i > 0 and pattern[pattern_i - 1] == '\\') {
            pattern_i -= 1;
        }

        if (address_i == 0) return false;
        address_i -= 1;
        if (address[address_i] != c) return false;
    }

    return true;
}

/// Calculate plugin match score.
///
/// Higher score = better match:
/// - Source priority: project(300), user(200), bundled(100)
/// - Language: Zig(+10), Python(+0)
/// - Pattern length (specificity)
fn calculateScore(plugin: discovery.PluginInfo, pattern_len: usize) i32 {
    var score: i32 = 0;

    // Source priority (project > user > bundled)
    score += switch (plugin.source) {
        .project => 300,
        .user => 200,
        .bundled => 100,
    };

    // Language priority (Zig > Python)
    score += switch (plugin.language) {
        .zig => 10,
        .python => 0,
    };

    // Pattern specificity (longer = more specific)
    score += @as(i32, @intCast(pattern_len));

    return score;
}

// ============================================================================
// Tests
// ============================================================================

test "matchPattern handles extension patterns" {
    // Standard extension pattern
    try std.testing.expect(matchPattern(".*\\.csv$", "data.csv"));
    try std.testing.expect(matchPattern(".*\\.csv$", "/path/to/data.csv"));
    try std.testing.expect(!matchPattern(".*\\.csv$", "data.json"));
    try std.testing.expect(!matchPattern(".*\\.csv$", "csv"));

    // Multiple extensions
    try std.testing.expect(matchPattern(".*\\.csv$|.*\\.tsv$", "data.csv"));
    try std.testing.expect(matchPattern(".*\\.csv$|.*\\.tsv$", "data.tsv"));
    try std.testing.expect(!matchPattern(".*\\.csv$|.*\\.tsv$", "data.json"));
}

test "matchPattern handles protocol patterns" {
    // Use | for alternatives since our simple matcher doesn't support ?
    try std.testing.expect(matchPattern("^http://|^https://", "http://example.com"));
    try std.testing.expect(matchPattern("^http://|^https://", "https://example.com"));
    try std.testing.expect(matchPattern("^http://", "http://example.com"));
    try std.testing.expect(!matchPattern("^http://", "ftp://example.com"));

    try std.testing.expect(matchPattern("^s3://", "s3://bucket/key"));
    try std.testing.expect(!matchPattern("^s3://", "http://s3.amazonaws.com"));
}

test "matchPattern handles simple suffix" {
    try std.testing.expect(matchPattern(".csv$", "data.csv"));
    try std.testing.expect(!matchPattern(".csv$", "data.json"));
}

test "calculateScore prioritizes correctly" {
    const project_zig = discovery.PluginInfo{
        .name = "test",
        .version = "1.0.0",
        .matches = &.{},
        .role = .format,
        .modes = &.{},
        .profile_type = null,
        .language = .zig,
        .source = .project,
        .path = "/test",
        .mtime = 0,
        .allocator = std.testing.allocator,
    };

    const user_zig = discovery.PluginInfo{
        .name = "test",
        .version = "1.0.0",
        .matches = &.{},
        .role = .format,
        .modes = &.{},
        .profile_type = null,
        .language = .zig,
        .source = .user,
        .path = "/test",
        .mtime = 0,
        .allocator = std.testing.allocator,
    };

    const bundled_python = discovery.PluginInfo{
        .name = "test",
        .version = "1.0.0",
        .matches = &.{},
        .role = .format,
        .modes = &.{},
        .profile_type = null,
        .language = .python,
        .source = .bundled,
        .path = "/test",
        .mtime = 0,
        .allocator = std.testing.allocator,
    };

    const score_project = calculateScore(project_zig, 10);
    const score_user = calculateScore(user_zig, 10);
    const score_bundled = calculateScore(bundled_python, 10);

    // Project should beat user
    try std.testing.expect(score_project > score_user);
    // User should beat bundled
    try std.testing.expect(score_user > score_bundled);
}

test "Registry.findPlugin finds best match" {
    const allocator = std.testing.allocator;

    var registry = Registry.init(allocator);
    defer registry.deinit();

    // Create test plugins manually (not using deinit since we manage memory)
    const matches1 = try allocator.alloc([]const u8, 1);
    matches1[0] = try allocator.dupe(u8, ".*\\.csv$");
    const modes1 = try allocator.alloc(discovery.PluginMode, 2);
    modes1[0] = .read;
    modes1[1] = .write;

    try registry.add(.{
        .name = try allocator.dupe(u8, "csv"),
        .version = try allocator.dupe(u8, "1.0.0"),
        .matches = matches1,
        .role = .format,
        .modes = modes1,
        .profile_type = null,
        .language = .zig,
        .source = .bundled,
        .path = try allocator.dupe(u8, "/plugins/csv"),
        .mtime = 0,
        .allocator = allocator,
    });

    // Find for CSV file
    const result = registry.findPlugin("data.csv", .read);
    try std.testing.expect(result != null);
    try std.testing.expectEqualStrings("csv", result.?.name);

    // No match for JSON
    const no_match = registry.findPlugin("data.json", .read);
    try std.testing.expect(no_match == null);
}

test "Registry.getByName finds plugin by name" {
    const allocator = std.testing.allocator;

    var registry = Registry.init(allocator);
    defer registry.deinit();

    const matches1 = try allocator.alloc([]const u8, 1);
    matches1[0] = try allocator.dupe(u8, ".*\\.csv$");
    const modes1 = try allocator.alloc(discovery.PluginMode, 1);
    modes1[0] = .read;

    try registry.add(.{
        .name = try allocator.dupe(u8, "csv"),
        .version = try allocator.dupe(u8, "1.0.0"),
        .matches = matches1,
        .role = .format,
        .modes = modes1,
        .profile_type = null,
        .language = .zig,
        .source = .bundled,
        .path = try allocator.dupe(u8, "/plugins/csv"),
        .mtime = 0,
        .allocator = allocator,
    });

    const result = registry.getByName("csv");
    try std.testing.expect(result != null);
    try std.testing.expectEqualStrings("csv", result.?.name);

    const no_result = registry.getByName("nonexistent");
    try std.testing.expect(no_result == null);
}

test "extractLiteralPrefix extracts until metachar" {
    try std.testing.expectEqualStrings("http://", extractLiteralPrefix("http://"));
    try std.testing.expectEqualStrings("s3://", extractLiteralPrefix("s3://"));
    try std.testing.expectEqualStrings("", extractLiteralPrefix(".*\\.csv"));
}
