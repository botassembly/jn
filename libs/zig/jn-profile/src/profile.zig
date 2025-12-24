//! Profile loading and resolution for JN.
//!
//! Profiles are stored in hierarchical directories:
//! 1. Project: .jn/profiles/
//! 2. User: ~/.local/jn/profiles/
//! 3. Bundled: $JN_HOME/profiles/
//!
//! Each profile type has its own subdirectory:
//! - profiles/http/     -> HTTP API profiles
//! - profiles/zq/       -> ZQ filter profiles
//! - profiles/duckdb/   -> DuckDB profiles
//!
//! Within a type directory, profiles can use _meta.json for shared config:
//!   profiles/http/myapi/
//!   ├── _meta.json       # Base config (auth, base_url)
//!   ├── users.json       # Endpoint config
//!   └── orders/
//!       ├── _meta.json   # Nested base (inherits parent)
//!       └── pending.json # Endpoint config
//!
//! ## Memory Ownership
//!
//! Functions return **allocated** data that the caller must free:
//!
//! - `getProfileDirs()` returns `[][]const u8` - free each string, then the slice
//! - `loadProfile()` returns `std.json.Value` - use `freeValue()` to clean up
//! - `deepMerge()`/`cloneValue()` return allocated JSON values - use `freeValue()`
//!
//! Example:
//! ```zig
//! const config = try loadProfile(allocator, base_dir, "myprofile.json", true);
//! defer freeValue(allocator, config);
//! ```

const std = @import("std");
const envsubst = @import("envsubst.zig");

/// Profile source priority
pub const Source = enum {
    project, // .jn/profiles/
    user, // ~/.local/jn/profiles/
    bundled, // $JN_HOME/profiles/

    pub fn prefix(self: Source) []const u8 {
        return switch (self) {
            .project => ".jn/profiles",
            .user => "~/.local/jn/profiles",
            .bundled => "$JN_HOME/profiles",
        };
    }
};

/// Parsed profile reference: @namespace/name[?params]
pub const ProfileRef = struct {
    /// Profile type (e.g., "http", "zq", "duckdb")
    profile_type: ?[]const u8,

    /// Namespace (e.g., "myapi" from @myapi/users)
    namespace: ?[]const u8,

    /// Profile name/path (e.g., "users" or "orders/pending")
    name: []const u8,

    /// Query string (without leading ?)
    query_string: ?[]const u8,
};

/// Loaded profile data
pub const Profile = struct {
    /// Source where the profile was found
    source: Source,

    /// Full path to the profile file
    path: []const u8,

    /// Profile type (from directory structure)
    profile_type: []const u8,

    /// The merged configuration
    config: std.json.Value,

    /// Allocator that owns the config memory
    allocator: std.mem.Allocator,

    pub fn deinit(self: *Profile) void {
        self.config.deinit(self.allocator);
    }
};

/// Directory discovery configuration
pub const DiscoveryConfig = struct {
    /// Project root (for .jn/profiles/)
    project_root: ?[]const u8 = null,

    /// User home directory (for ~/.local/jn/profiles/)
    home_dir: ?[]const u8 = null,

    /// JN home directory (for bundled profiles)
    jn_home: ?[]const u8 = null,
};

/// Get the user's home directory
pub fn getHomeDir() ?[]const u8 {
    return std.posix.getenv("HOME");
}

/// Get JN_HOME or default to ~/.local/jn
pub fn getJnHome() ?[]const u8 {
    if (std.posix.getenv("JN_HOME")) |jn_home| {
        return jn_home;
    }
    // Default would be ~/.local/jn but we can't allocate here
    return null;
}

/// Find profile directories in priority order.
///
/// Returns an array of directories to search, in priority order:
/// 1. .jn/profiles/ (if project_root is set)
/// 2. ~/.local/jn/profiles/
/// 3. $JN_HOME/profiles/
pub fn getProfileDirs(allocator: std.mem.Allocator, config: DiscoveryConfig) ![][]const u8 {
    var dirs: std.ArrayListUnmanaged([]const u8) = .empty;
    errdefer {
        for (dirs.items) |d| allocator.free(d);
        dirs.deinit(allocator);
    }

    // 1. Project profiles
    if (config.project_root) |root| {
        const project_profiles = try std.fmt.allocPrint(allocator, "{s}/.jn/profiles", .{root});
        try dirs.append(allocator, project_profiles);
    }

    // 2. User profiles
    const home = config.home_dir orelse getHomeDir();
    if (home) |h| {
        const user_profiles = try std.fmt.allocPrint(allocator, "{s}/.local/jn/profiles", .{h});
        try dirs.append(allocator, user_profiles);
    }

    // 3. Bundled profiles
    const jn_home = config.jn_home orelse getJnHome();
    if (jn_home) |jh| {
        const bundled_profiles = try std.fmt.allocPrint(allocator, "{s}/profiles", .{jh});
        try dirs.append(allocator, bundled_profiles);
    }

    return dirs.toOwnedSlice(allocator);
}

/// Deep merge two JSON objects.
///
/// The `override` object's values take precedence over `base`.
/// Objects are merged recursively; other types are replaced.
pub fn deepMerge(allocator: std.mem.Allocator, base: std.json.Value, override: std.json.Value) !std.json.Value {
    // If either is not an object, override wins
    if (base != .object or override != .object) {
        return try cloneValue(allocator, override);
    }

    // Both are objects - merge them
    var result = std.json.ObjectMap.init(allocator);
    errdefer result.deinit();

    // Copy all base values
    var base_iter = base.object.iterator();
    while (base_iter.next()) |entry| {
        const key = try allocator.dupe(u8, entry.key_ptr.*);
        errdefer allocator.free(key);

        // Check if override has this key
        if (override.object.get(entry.key_ptr.*)) |override_val| {
            // Recursively merge
            const merged = try deepMerge(allocator, entry.value_ptr.*, override_val);
            try result.put(key, merged);
        } else {
            // Just copy from base
            const cloned = try cloneValue(allocator, entry.value_ptr.*);
            try result.put(key, cloned);
        }
    }

    // Add any keys only in override
    var override_iter = override.object.iterator();
    while (override_iter.next()) |entry| {
        if (!base.object.contains(entry.key_ptr.*)) {
            const key = try allocator.dupe(u8, entry.key_ptr.*);
            errdefer allocator.free(key);
            const cloned = try cloneValue(allocator, entry.value_ptr.*);
            try result.put(key, cloned);
        }
    }

    return .{ .object = result };
}

/// Free a JSON value that was created by cloneValue or deepMerge
pub fn freeValue(allocator: std.mem.Allocator, value: std.json.Value) void {
    switch (value) {
        .null, .bool, .integer, .float => {},
        .number_string => |s| allocator.free(s),
        .string => |s| allocator.free(s),
        .array => |arr| {
            for (arr.items) |item| {
                freeValue(allocator, item);
            }
            var array = arr;
            array.deinit();
        },
        .object => |obj| {
            var iter = obj.iterator();
            while (iter.next()) |entry| {
                allocator.free(entry.key_ptr.*);
                freeValue(allocator, entry.value_ptr.*);
            }
            var object = obj;
            object.deinit();
        },
    }
}

/// Clone a JSON value (deep copy)
///
/// ## Design Decision: Error Path Cleanup
///
/// The errdefer on array/object containers (new_arr.deinit(), new_obj.deinit())
/// frees the container but not already-cloned items. This is ACCEPTABLE because:
///
/// 1. **Profile loading is startup-only**: Profiles are loaded once at tool startup.
///    If cloning fails, the tool exits with an error anyway.
///
/// 2. **Errors are fatal**: In JN's process-per-tool model, profile load errors
///    cause immediate exit. The OS reclaims all memory on exit.
///
/// 3. **Complexity tradeoff**: Adding cleanup loops for already-cloned items
///    would significantly complicate the code for a scenario that (a) rarely
///    happens, and (b) results in process exit anyway.
///
/// For library usage where profiles might be loaded/retried multiple times,
/// use freeValue() to clean up on error paths, or use an arena allocator
/// that can be reset/freed atomically.
///
/// See also: freeValue() for proper cleanup of successfully cloned values.
pub fn cloneValue(allocator: std.mem.Allocator, value: std.json.Value) !std.json.Value {
    return switch (value) {
        .null => .null,
        .bool => |b| .{ .bool = b },
        .integer => |i| .{ .integer = i },
        .float => |f| .{ .float = f },
        .number_string => |s| .{ .number_string = try allocator.dupe(u8, s) },
        .string => |s| .{ .string = try allocator.dupe(u8, s) },
        .array => |arr| blk: {
            var new_arr = std.json.Array.init(allocator);
            errdefer new_arr.deinit();
            for (arr.items) |item| {
                try new_arr.append(try cloneValue(allocator, item));
            }
            break :blk .{ .array = new_arr };
        },
        .object => |obj| blk: {
            var new_obj = std.json.ObjectMap.init(allocator);
            errdefer new_obj.deinit();
            var iter = obj.iterator();
            while (iter.next()) |entry| {
                const key = try allocator.dupe(u8, entry.key_ptr.*);
                errdefer allocator.free(key);
                try new_obj.put(key, try cloneValue(allocator, entry.value_ptr.*));
            }
            break :blk .{ .object = new_obj };
        },
    };
}

/// Parse a JSON file and return its contents.
pub fn parseJsonFile(allocator: std.mem.Allocator, path: []const u8) !std.json.Parsed(std.json.Value) {
    const file = try std.fs.cwd().openFile(path, .{});
    defer file.close();

    const content = try file.readToEndAlloc(allocator, 1024 * 1024); // 1MB max
    defer allocator.free(content);

    return std.json.parseFromSlice(std.json.Value, allocator, content, .{});
}

/// Load a profile with hierarchical merge.
///
/// Walks up the directory tree collecting _meta.json files,
/// then merges them with the specific profile file.
pub fn loadProfile(
    allocator: std.mem.Allocator,
    base_dir: []const u8,
    profile_path: []const u8,
    apply_env_subst: bool,
) !std.json.Value {
    // Build full path to profile
    const full_path = try std.fmt.allocPrint(allocator, "{s}/{s}", .{ base_dir, profile_path });
    defer allocator.free(full_path);

    // Collect all _meta.json files from root to the profile's directory
    var metas: std.ArrayListUnmanaged(std.json.Parsed(std.json.Value)) = .empty;
    defer {
        for (metas.items) |*m| m.deinit();
        metas.deinit(allocator);
    }

    // Walk up from profile location to base_dir
    var current_dir: []const u8 = std.fs.path.dirname(full_path) orelse base_dir;

    while (true) {
        // Try to load _meta.json at this level
        const meta_path = try std.fmt.allocPrint(allocator, "{s}/_meta.json", .{current_dir});
        defer allocator.free(meta_path);

        if (parseJsonFile(allocator, meta_path)) |meta| {
            try metas.append(allocator, meta);
        } else |_| {
            // No _meta.json at this level, continue
        }

        // Move up one directory
        if (std.mem.eql(u8, current_dir, base_dir)) break;
        current_dir = std.fs.path.dirname(current_dir) orelse break;
    }

    // Load the specific profile file
    var profile_json = try parseJsonFile(allocator, full_path);
    defer profile_json.deinit(); // Always clean up the parsed profile

    // Merge _meta.json files (from root to leaf) with profile
    var result = std.json.Value{ .object = std.json.ObjectMap.init(allocator) };
    errdefer freeValue(allocator, result); // Clean up on error

    // Apply metas in reverse order (root first)
    var i: usize = metas.items.len;
    while (i > 0) {
        i -= 1;
        const merged = try deepMerge(allocator, result, metas.items[i].value);
        freeValue(allocator, result);
        result = merged;
    }

    // Finally merge with the profile itself
    const final = try deepMerge(allocator, result, profile_json.value);
    freeValue(allocator, result);
    result = final;

    // Apply environment variable substitution if requested
    if (apply_env_subst) {
        try envsubst.substituteJsonValue(allocator, &result);
    }

    return result;
}

/// Check if a path exists
pub fn pathExists(path: []const u8) bool {
    std.fs.cwd().access(path, .{}) catch return false;
    return true;
}

// ============================================================================
// Tests
// ============================================================================

test "deepMerge basic" {
    const allocator = std.testing.allocator;

    // Parse base and override
    const base_json = try std.json.parseFromSlice(
        std.json.Value,
        allocator,
        \\{"a": 1, "b": 2}
    ,
        .{},
    );
    defer base_json.deinit();

    const override_json = try std.json.parseFromSlice(
        std.json.Value,
        allocator,
        \\{"b": 3, "c": 4}
    ,
        .{},
    );
    defer override_json.deinit();

    const result = try deepMerge(allocator, base_json.value, override_json.value);
    defer freeValue(allocator, result);

    // Check merged result
    try std.testing.expectEqual(@as(i64, 1), result.object.get("a").?.integer);
    try std.testing.expectEqual(@as(i64, 3), result.object.get("b").?.integer);
    try std.testing.expectEqual(@as(i64, 4), result.object.get("c").?.integer);
}

test "deepMerge nested objects" {
    const allocator = std.testing.allocator;

    const base_json = try std.json.parseFromSlice(
        std.json.Value,
        allocator,
        \\{"headers": {"a": "1", "b": "2"}}
    ,
        .{},
    );
    defer base_json.deinit();

    const override_json = try std.json.parseFromSlice(
        std.json.Value,
        allocator,
        \\{"headers": {"b": "3", "c": "4"}}
    ,
        .{},
    );
    defer override_json.deinit();

    const result = try deepMerge(allocator, base_json.value, override_json.value);
    defer freeValue(allocator, result);

    const headers = result.object.get("headers").?.object;
    try std.testing.expectEqualStrings("1", headers.get("a").?.string);
    try std.testing.expectEqualStrings("3", headers.get("b").?.string);
    try std.testing.expectEqualStrings("4", headers.get("c").?.string);
}

test "cloneValue primitives" {
    const allocator = std.testing.allocator;

    const null_clone = try cloneValue(allocator, .null);
    try std.testing.expect(null_clone == .null);

    const bool_clone = try cloneValue(allocator, .{ .bool = true });
    try std.testing.expect(bool_clone.bool == true);

    const int_clone = try cloneValue(allocator, .{ .integer = 42 });
    try std.testing.expectEqual(@as(i64, 42), int_clone.integer);
}

test "cloneValue string" {
    const allocator = std.testing.allocator;

    const original = "hello";
    const clone = try cloneValue(allocator, .{ .string = original });
    defer {
        allocator.free(clone.string);
    }

    try std.testing.expectEqualStrings("hello", clone.string);
    // Should be a copy, not the same pointer
    try std.testing.expect(clone.string.ptr != original.ptr);
}

test "getProfileDirs with config" {
    const allocator = std.testing.allocator;

    const dirs = try getProfileDirs(allocator, .{
        .project_root = "/project",
        .home_dir = "/home/user",
        .jn_home = "/opt/jn",
    });
    defer {
        for (dirs) |d| allocator.free(d);
        allocator.free(dirs);
    }

    try std.testing.expectEqual(@as(usize, 3), dirs.len);
    try std.testing.expectEqualStrings("/project/.jn/profiles", dirs[0]);
    try std.testing.expectEqualStrings("/home/user/.local/jn/profiles", dirs[1]);
    try std.testing.expectEqualStrings("/opt/jn/profiles", dirs[2]);
}

test "getProfileDirs partial config" {
    const allocator = std.testing.allocator;

    const dirs = try getProfileDirs(allocator, .{
        .project_root = null, // No project
        .home_dir = "/home/user",
        .jn_home = null, // No JN_HOME
    });
    defer {
        for (dirs) |d| allocator.free(d);
        allocator.free(dirs);
    }

    try std.testing.expectEqual(@as(usize, 1), dirs.len);
    try std.testing.expectEqualStrings("/home/user/.local/jn/profiles", dirs[0]);
}
