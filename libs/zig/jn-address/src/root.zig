//! JN Address Library
//!
//! Provides address parsing for JN tools and plugins.
//! Addresses follow the format: [protocol://]path[~format][?params]
//!
//! Supported address types:
//! - File: `data.csv`, `path/to/file.json`
//! - URL: `https://api.com/data`, `s3://bucket/key`
//! - Profile: `@namespace/name`, `@myapi/users?limit=10`
//! - Stdin: `-` or empty string
//! - Glob: `data/*.csv`, `**/*.json`
//!
//! Examples:
//! ```zig
//! const addr = jn_address.parse("https://api.com/data.csv.gz");
//! // addr.address_type == .url
//! // addr.protocol == "https"
//! // addr.path == "api.com/data.csv.gz"
//! // addr.inferred_format == "csv"
//! // addr.compression == .gzip
//!
//! const profile = jn_address.parse("@myapi/users?limit=10");
//! // profile.address_type == .profile
//! // profile.profile_namespace == "myapi"
//! // profile.profile_name == "users"
//! // jn_address.getQueryParam(profile, "limit") == "10"
//! ```

pub const address = @import("address.zig");

// Re-export main types
pub const Address = address.Address;
pub const AddressType = address.AddressType;
pub const Compression = address.Compression;

// Re-export main functions
pub const parse = address.parse;
pub const queryParams = address.queryParams;
pub const getQueryParam = address.getQueryParam;
pub const QueryIterator = address.QueryIterator;

test {
    @import("std").testing.refAllDecls(@This());
}
