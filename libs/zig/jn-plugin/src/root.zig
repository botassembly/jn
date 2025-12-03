//! JN Plugin Library
//!
//! Provides plugin metadata and manifest output for JN plugins.
//! Standardizes the plugin interface across all Zig plugins.

pub const meta = @import("meta.zig");
pub const manifest = @import("manifest.zig");

// Re-export main types and functions
pub const PluginMeta = meta.PluginMeta;
pub const Role = meta.Role;
pub const Mode = meta.Mode;
pub const outputManifest = manifest.outputManifest;
pub const outputManifestToStdout = manifest.outputManifestToStdout;

test {
    @import("std").testing.refAllDecls(@This());
}
