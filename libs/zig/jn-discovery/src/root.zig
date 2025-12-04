//! JN Plugin Discovery Library
//!
//! Discovers and manages plugins for JN from multiple sources:
//! - Project plugins: .jn/plugins/
//! - User plugins: ~/.local/jn/plugins/
//! - Bundled plugins: $JN_HOME/plugins/
//!
//! Supports both Zig (binary) and Python (PEP 723) plugins.
//!
//! ## Example Usage
//!
//! ```zig
//! const jn_discovery = @import("jn-discovery");
//!
//! // Discover all plugins
//! const plugins = try jn_discovery.discoverAll(allocator, .{
//!     .project_root = "/my/project",
//!     .jn_home = "/opt/jn",
//! });
//! defer {
//!     for (plugins) |*p| p.deinit();
//!     allocator.free(plugins);
//! }
//!
//! // Build registry for fast lookups
//! var registry = jn_discovery.Registry.init(allocator);
//! defer registry.deinit();
//! try registry.addAll(plugins);
//!
//! // Find plugin for a file
//! if (registry.findPlugin("data.csv", .read)) |plugin| {
//!     // Use plugin.path to invoke it
//! }
//!
//! // Use cache for faster startup
//! var cache = try jn_discovery.Cache.init(allocator, null);
//! defer cache.deinit();
//!
//! // Try to load from cache
//! if (cache.load()) |cached_plugins| {
//!     if (cache.isValid(cached_plugins)) {
//!         // Use cached plugins
//!     }
//! }
//! ```

const std = @import("std");

// Re-export submodules
pub const discovery = @import("discovery.zig");
pub const pep723 = @import("pep723.zig");
pub const registry = @import("registry.zig");
pub const cache = @import("cache.zig");

// Re-export commonly used types
pub const PluginInfo = discovery.PluginInfo;
pub const PluginLanguage = discovery.PluginLanguage;
pub const PluginSource = discovery.PluginSource;
pub const PluginRole = discovery.PluginRole;
pub const PluginMode = discovery.PluginMode;
pub const PluginDir = discovery.PluginDir;
pub const DiscoveryConfig = discovery.DiscoveryConfig;

pub const Registry = registry.Registry;
pub const Cache = cache.Cache;

// Re-export main functions
pub const getPluginDirs = discovery.getPluginDirs;
pub const discoverZigPlugin = discovery.discoverZigPlugin;
pub const discoverPythonPlugin = discovery.discoverPythonPlugin;
pub const scanDirectory = discovery.scanDirectory;
pub const discoverAll = discovery.discoverAll;

pub const parseToolJn = pep723.parseToolJn;

/// Discover plugins with optional caching.
///
/// If cache is valid, returns cached plugins.
/// Otherwise, performs full discovery and updates cache.
pub fn discoverWithCache(
    allocator: std.mem.Allocator,
    config: DiscoveryConfig,
    use_cache: bool,
) ![]PluginInfo {
    if (use_cache) {
        var plugin_cache = Cache.init(allocator, config.jn_home) catch |err| {
            // Cache init failed, fall through to full discovery
            std.log.warn("Cache init failed: {}", .{err});
            return discoverAll(allocator, config);
        };
        defer plugin_cache.deinit();

        // Try to load from cache
        if (plugin_cache.load()) |cached| {
            if (plugin_cache.isValid(cached)) {
                return cached;
            }
            // Cache is stale, free and rediscover
            for (cached) |*p| p.deinit();
            allocator.free(cached);
        }

        // Perform discovery
        const plugins = try discoverAll(allocator, config);

        // Save to cache (ignore errors)
        plugin_cache.save(plugins) catch {};

        return plugins;
    }

    return discoverAll(allocator, config);
}

/// Create a registry from discovered plugins.
pub fn createRegistry(allocator: std.mem.Allocator, plugins: []PluginInfo) !Registry {
    var reg = Registry.init(allocator);
    errdefer reg.deinit();

    for (plugins) |plugin| {
        try reg.add(plugin);
    }

    return reg;
}

// ============================================================================
// Tests
// ============================================================================

test "module exports are accessible" {
    // Verify types are exported
    _ = PluginInfo;
    _ = PluginLanguage;
    _ = PluginSource;
    _ = PluginRole;
    _ = PluginMode;
    _ = Registry;
    _ = Cache;
    _ = DiscoveryConfig;
}

test "PluginLanguage enum values" {
    try std.testing.expectEqualStrings("zig", PluginLanguage.zig.toString());
    try std.testing.expectEqualStrings("python", PluginLanguage.python.toString());
}

test "PluginSource priority ordering" {
    try std.testing.expect(PluginSource.project.priority() < PluginSource.user.priority());
    try std.testing.expect(PluginSource.user.priority() < PluginSource.bundled.priority());
}

test "PluginRole parsing" {
    try std.testing.expectEqual(PluginRole.format, PluginRole.fromString("format").?);
    try std.testing.expectEqual(PluginRole.protocol, PluginRole.fromString("protocol").?);
    try std.testing.expectEqual(PluginRole.compression, PluginRole.fromString("compression").?);
    try std.testing.expectEqual(PluginRole.database, PluginRole.fromString("database").?);
    try std.testing.expect(PluginRole.fromString("unknown") == null);
}

test "PluginMode parsing" {
    try std.testing.expectEqual(PluginMode.read, PluginMode.fromString("read").?);
    try std.testing.expectEqual(PluginMode.write, PluginMode.fromString("write").?);
    try std.testing.expectEqual(PluginMode.raw, PluginMode.fromString("raw").?);
    try std.testing.expectEqual(PluginMode.profiles, PluginMode.fromString("profiles").?);
    try std.testing.expect(PluginMode.fromString("unknown") == null);
}

// Run all submodule tests
test {
    std.testing.refAllDecls(@This());
    _ = @import("discovery.zig");
    _ = @import("pep723.zig");
    _ = @import("registry.zig");
    _ = @import("cache.zig");
}
