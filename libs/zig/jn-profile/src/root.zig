//! JN Profile Library
//!
//! Provides hierarchical profile resolution for JN tools.
//!
//! Profiles are discovered from multiple locations (in priority order):
//! 1. Project: `.jn/profiles/`
//! 2. User: `~/.local/jn/profiles/`
//! 3. Bundled: `$JN_HOME/profiles/`
//!
//! Each profile type has its own subdirectory (e.g., `profiles/http/`, `profiles/zq/`).
//!
//! Features:
//! - Hierarchical merge via `_meta.json` files
//! - Environment variable substitution (`${VAR}`, `${VAR:-default}`)
//! - Deep merge of nested objects
//!
//! Example:
//! ```
//! profiles/http/myapi/
//! ├── _meta.json       # {"base_url": "https://api.com", "headers": {"Auth": "${TOKEN}"}}
//! └── users.json       # {"path": "/users", "method": "GET"}
//!
//! Merged result:
//! {
//!   "base_url": "https://api.com",
//!   "headers": {"Auth": "actual-token-value"},
//!   "path": "/users",
//!   "method": "GET"
//! }
//! ```

pub const profile = @import("profile.zig");
pub const envsubst = @import("envsubst.zig");

// Re-export main types
pub const Source = profile.Source;
pub const ProfileRef = profile.ProfileRef;
pub const Profile = profile.Profile;
pub const DiscoveryConfig = profile.DiscoveryConfig;

// Re-export main functions
pub const getHomeDir = profile.getHomeDir;
pub const getJnHome = profile.getJnHome;
pub const getProfileDirs = profile.getProfileDirs;
pub const deepMerge = profile.deepMerge;
pub const freeValue = profile.freeValue;
pub const cloneValue = profile.cloneValue;
pub const parseJsonFile = profile.parseJsonFile;
pub const loadProfile = profile.loadProfile;
pub const pathExists = profile.pathExists;

// Environment substitution
pub const substitute = envsubst.substitute;
pub const substituteJsonValue = envsubst.substituteJsonValue;

test {
    @import("std").testing.refAllDecls(@This());
}
