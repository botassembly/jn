//! Address parsing for JN.
//!
//! Parses addresses of the form: [protocol://]path[~format][?params]
//!
//! Examples:
//!   - data.csv              -> File, format=csv
//!   - https://api.com/data  -> URL, protocol=https
//!   - @myapi/users          -> Profile, namespace=myapi, name=users
//!   - -                     -> Stdin
//!   - data/*.csv            -> Glob
//!   - data.txt~csv          -> File, format=csv (override)
//!   - file.csv?delimiter=;  -> File with params
//!
//! ## Design Decision: Zero-Allocation Parsing
//!
//! The `parse()` function returns an Address struct with slices that point
//! directly into the input string. It does NOT allocate any memory.
//! This is INTENTIONAL for performance:
//!
//! 1. **Hot path optimization**: Address parsing happens on every pipeline
//!    invocation. Zero allocation means zero overhead.
//!
//! 2. **Caller controls lifetime**: The caller knows how long the input
//!    string lives and can manage memory appropriately.
//!
//! 3. **Composability**: Parsed addresses can be passed around without
//!    ownership transfer concerns.
//!
//! **Important**: The returned Address is only valid while the input string
//! is valid. If you need the address to outlive the input, copy the relevant
//! slices using an allocator.
//!
//! Example of safe usage:
//! ```zig
//! // input lives for duration of function
//! const addr = parse(input);
//! // use addr.path, addr.format_override, etc. while input is valid
//! ```
//!
//! See also: spec/01-vision.md ("Simple Over Clever")

const std = @import("std");

/// Address type enumeration
pub const AddressType = enum {
    file,
    url,
    profile,
    stdin,
    glob,
};

/// Compression type based on extension
pub const Compression = enum {
    none,
    gzip,
    bzip2,
    xz,
    zstd,

    /// Detect compression from extension
    pub fn fromExtension(ext: []const u8) Compression {
        if (std.mem.eql(u8, ext, ".gz")) return .gzip;
        if (std.mem.eql(u8, ext, ".bz2")) return .bzip2;
        if (std.mem.eql(u8, ext, ".xz")) return .xz;
        if (std.mem.eql(u8, ext, ".zst")) return .zstd;
        return .none;
    }

    /// Get the extension for this compression type
    pub fn extension(self: Compression) ?[]const u8 {
        return switch (self) {
            .none => null,
            .gzip => ".gz",
            .bzip2 => ".bz2",
            .xz => ".xz",
            .zstd => ".zst",
        };
    }
};

/// Parsed address structure
pub const Address = struct {
    /// The original input string
    raw: []const u8,

    /// Type of address (file, url, profile, stdin, glob)
    address_type: AddressType,

    /// Protocol (e.g., "https", "s3", "duckdb") - null for files
    protocol: ?[]const u8,

    /// Path component (after protocol, before format/params)
    path: []const u8,

    /// Format override (e.g., "csv", "json") - null if not specified
    format_override: ?[]const u8,

    /// Inferred format from extension - null if unknown
    inferred_format: ?[]const u8,

    /// Query parameters as raw string
    query_string: ?[]const u8,

    /// Detected compression
    compression: Compression,

    /// For profile addresses: namespace (e.g., "myapi" from @myapi/users)
    profile_namespace: ?[]const u8,

    /// For profile addresses: name (e.g., "users" from @myapi/users)
    profile_name: ?[]const u8,

    /// Get the effective format (override takes precedence)
    pub fn effectiveFormat(self: Address) ?[]const u8 {
        return self.format_override orelse self.inferred_format;
    }

    /// Check if this is a remote address (URL with network protocol)
    pub fn isRemote(self: Address) bool {
        if (self.protocol) |proto| {
            return std.mem.eql(u8, proto, "http") or
                std.mem.eql(u8, proto, "https") or
                std.mem.eql(u8, proto, "s3") or
                std.mem.eql(u8, proto, "gs") or
                std.mem.eql(u8, proto, "gcs") or
                std.mem.eql(u8, proto, "az") or
                std.mem.eql(u8, proto, "azblob") or
                std.mem.eql(u8, proto, "hdfs") or
                std.mem.eql(u8, proto, "ftp") or
                std.mem.eql(u8, proto, "sftp");
        }
        return false;
    }
};

/// Parse an address string into components.
///
/// This does not allocate; all slices point into the original input.
pub fn parse(input: []const u8) Address {
    var addr = Address{
        .raw = input,
        .address_type = .file,
        .protocol = null,
        .path = input,
        .format_override = null,
        .inferred_format = null,
        .query_string = null,
        .compression = .none,
        .profile_namespace = null,
        .profile_name = null,
    };

    // Empty or "-" is stdin (may have ~format suffix)
    if (input.len == 0 or std.mem.eql(u8, input, "-")) {
        addr.address_type = .stdin;
        addr.path = "";
        return addr;
    }

    // stdin with format override: -~format or -~format?params
    if (input.len > 2 and input[0] == '-' and input[1] == '~') {
        addr.address_type = .stdin;
        addr.path = "";
        // Extract format and optional query params from after -~
        var rest = input[2..]; // Skip "-~"
        if (std.mem.indexOf(u8, rest, "?")) |q_pos| {
            addr.query_string = rest[q_pos + 1 ..];
            addr.format_override = rest[0..q_pos];
        } else {
            addr.format_override = rest;
        }
        return addr;
    }

    // Profile reference starts with @
    if (input[0] == '@') {
        return parseProfile(input, addr);
    }

    // Check for URL (has ://)
    if (std.mem.indexOf(u8, input, "://")) |proto_end| {
        addr.address_type = .url;
        addr.protocol = input[0..proto_end];

        // Rest after ://
        const rest = input[proto_end + 3 ..];
        parsePathFormatParams(rest, &addr);
        return addr;
    }

    // Check for glob patterns
    if (isGlobPattern(input)) {
        addr.address_type = .glob;
    }

    // Parse as file path with optional format/params
    parsePathFormatParams(input, &addr);
    return addr;
}

/// Parse a profile reference: @namespace/name[?params]
fn parseProfile(input: []const u8, addr_in: Address) Address {
    var addr = addr_in;
    addr.address_type = .profile;

    // Skip the @
    var rest = input[1..];

    // Split off query string first
    if (std.mem.indexOf(u8, rest, "?")) |q_pos| {
        addr.query_string = rest[q_pos + 1 ..];
        rest = rest[0..q_pos];
    }

    // Split namespace/name
    if (std.mem.indexOf(u8, rest, "/")) |slash_pos| {
        addr.profile_namespace = rest[0..slash_pos];
        addr.profile_name = rest[slash_pos + 1 ..];
        addr.path = rest;
    } else {
        // No slash - entire thing is the name
        addr.profile_namespace = null;
        addr.profile_name = rest;
        addr.path = rest;
    }

    return addr;
}

/// Parse path, format override, and query params from a string.
/// Modifies addr in place.
fn parsePathFormatParams(input: []const u8, addr: *Address) void {
    var path = input;

    // Extract query string first
    if (std.mem.indexOf(u8, path, "?")) |q_pos| {
        addr.query_string = path[q_pos + 1 ..];
        path = path[0..q_pos];
    }

    // Extract format override (after ~)
    if (std.mem.lastIndexOf(u8, path, "~")) |tilde_pos| {
        // Make sure ~ is not part of the path (e.g., ~/file.csv)
        // ~ at position 0 is a home directory, not a format override
        if (tilde_pos > 0) {
            addr.format_override = path[tilde_pos + 1 ..];
            path = path[0..tilde_pos];
        }
    }

    addr.path = path;

    // Detect compression and infer format from extension
    detectCompressionAndFormat(path, addr);
}

/// Detect compression and infer format from file extension.
fn detectCompressionAndFormat(path: []const u8, addr: *Address) void {
    var remaining_path = path;

    // Check for compression extension
    const compression_exts = [_][]const u8{ ".gz", ".bz2", ".xz", ".zst" };
    for (compression_exts) |ext| {
        if (std.mem.endsWith(u8, remaining_path, ext)) {
            addr.compression = Compression.fromExtension(ext);
            remaining_path = remaining_path[0 .. remaining_path.len - ext.len];
            break;
        }
    }

    // Infer format from remaining extension
    if (std.mem.lastIndexOf(u8, remaining_path, ".")) |dot_pos| {
        // Get extension without the dot
        const ext = remaining_path[dot_pos + 1 ..];
        if (ext.len > 0 and ext.len <= 10) {
            addr.inferred_format = ext;
        }
    }
}

/// Check if a path contains glob patterns.
/// Distinguishes from query params: glob ? is not followed by key=value pattern.
fn isGlobPattern(path: []const u8) bool {
    // First, strip any query string (anything after ?)
    // If the ? is followed by something like "key=value", it's a query param, not a glob
    var check_path = path;
    if (std.mem.indexOf(u8, path, "?")) |q_pos| {
        // Check if this looks like a query string (has = after ?)
        const after_q = path[q_pos + 1 ..];
        if (std.mem.indexOf(u8, after_q, "=") != null) {
            // This is a query string, not a glob ?
            check_path = path[0..q_pos];
        }
    }

    for (check_path) |c| {
        if (c == '*') return true;
        if (c == '?') return true; // Single char wildcard
        if (c == '[') {
            // Check for bracket expression [...]
            if (std.mem.indexOf(u8, check_path, "]") != null) return true;
        }
    }
    return false;
}

// ============================================================================
// Query Parameter Parsing
// ============================================================================

/// Iterator for query parameters
pub const QueryIterator = struct {
    remaining: []const u8,

    pub fn next(self: *QueryIterator) ?struct { key: []const u8, value: []const u8 } {
        if (self.remaining.len == 0) return null;

        // Find the end of this parameter
        const param_end = std.mem.indexOf(u8, self.remaining, "&") orelse self.remaining.len;
        const param = self.remaining[0..param_end];

        // Advance past this parameter
        if (param_end < self.remaining.len) {
            self.remaining = self.remaining[param_end + 1 ..];
        } else {
            self.remaining = "";
        }

        // Split key=value
        if (std.mem.indexOf(u8, param, "=")) |eq_pos| {
            return .{
                .key = param[0..eq_pos],
                .value = param[eq_pos + 1 ..],
            };
        } else {
            // Key without value
            return .{
                .key = param,
                .value = "",
            };
        }
    }
};

/// Create an iterator over query parameters
pub fn queryParams(addr: Address) QueryIterator {
    return .{
        .remaining = addr.query_string orelse "",
    };
}

/// Get a specific query parameter value
pub fn getQueryParam(addr: Address, key: []const u8) ?[]const u8 {
    var iter = queryParams(addr);
    while (iter.next()) |param| {
        if (std.mem.eql(u8, param.key, key)) {
            return param.value;
        }
    }
    return null;
}

// ============================================================================
// Tests
// ============================================================================

test "parse simple file" {
    const addr = parse("data.csv");
    try std.testing.expectEqual(AddressType.file, addr.address_type);
    try std.testing.expect(addr.protocol == null);
    try std.testing.expectEqualStrings("data.csv", addr.path);
    try std.testing.expectEqualStrings("csv", addr.inferred_format.?);
    try std.testing.expect(addr.format_override == null);
    try std.testing.expectEqual(Compression.none, addr.compression);
}

test "parse file with compression" {
    const addr = parse("data.csv.gz");
    try std.testing.expectEqual(AddressType.file, addr.address_type);
    try std.testing.expectEqualStrings("data.csv.gz", addr.path);
    try std.testing.expectEqualStrings("csv", addr.inferred_format.?);
    try std.testing.expectEqual(Compression.gzip, addr.compression);
}

test "parse file with format override" {
    const addr = parse("data.txt~csv");
    try std.testing.expectEqual(AddressType.file, addr.address_type);
    try std.testing.expectEqualStrings("data.txt", addr.path);
    try std.testing.expectEqualStrings("csv", addr.format_override.?);
    try std.testing.expectEqualStrings("txt", addr.inferred_format.?);
}

test "parse file with query params" {
    const addr = parse("data.csv?delimiter=;");
    try std.testing.expectEqual(AddressType.file, addr.address_type);
    try std.testing.expectEqualStrings("data.csv", addr.path);
    try std.testing.expectEqualStrings("delimiter=;", addr.query_string.?);

    const delim = getQueryParam(addr, "delimiter");
    try std.testing.expectEqualStrings(";", delim.?);
}

test "parse stdin" {
    const addr1 = parse("-");
    try std.testing.expectEqual(AddressType.stdin, addr1.address_type);

    const addr2 = parse("");
    try std.testing.expectEqual(AddressType.stdin, addr2.address_type);
}

test "parse stdin with format override" {
    const addr = parse("-~table");
    try std.testing.expectEqual(AddressType.stdin, addr.address_type);
    try std.testing.expectEqualStrings("", addr.path);
    try std.testing.expectEqualStrings("table", addr.format_override.?);
}

test "parse URL" {
    const addr = parse("https://api.example.com/data.json");
    try std.testing.expectEqual(AddressType.url, addr.address_type);
    try std.testing.expectEqualStrings("https", addr.protocol.?);
    try std.testing.expectEqualStrings("api.example.com/data.json", addr.path);
    try std.testing.expectEqualStrings("json", addr.inferred_format.?);
    try std.testing.expect(addr.isRemote());
}

test "parse URL with compression" {
    const addr = parse("https://example.com/data.csv.gz");
    try std.testing.expectEqual(AddressType.url, addr.address_type);
    try std.testing.expectEqualStrings("https", addr.protocol.?);
    try std.testing.expectEqualStrings("csv", addr.inferred_format.?);
    try std.testing.expectEqual(Compression.gzip, addr.compression);
}

test "parse S3 URL" {
    const addr = parse("s3://mybucket/path/to/file.parquet");
    try std.testing.expectEqual(AddressType.url, addr.address_type);
    try std.testing.expectEqualStrings("s3", addr.protocol.?);
    try std.testing.expectEqualStrings("mybucket/path/to/file.parquet", addr.path);
    try std.testing.expectEqualStrings("parquet", addr.inferred_format.?);
    try std.testing.expect(addr.isRemote());
}

test "parse profile reference" {
    const addr = parse("@myapi/users");
    try std.testing.expectEqual(AddressType.profile, addr.address_type);
    try std.testing.expectEqualStrings("myapi", addr.profile_namespace.?);
    try std.testing.expectEqualStrings("users", addr.profile_name.?);
}

test "parse profile with params" {
    const addr = parse("@myapi/users?limit=10&status=active");
    try std.testing.expectEqual(AddressType.profile, addr.address_type);
    try std.testing.expectEqualStrings("myapi", addr.profile_namespace.?);
    try std.testing.expectEqualStrings("users", addr.profile_name.?);
    try std.testing.expectEqualStrings("limit=10&status=active", addr.query_string.?);

    const limit = getQueryParam(addr, "limit");
    try std.testing.expectEqualStrings("10", limit.?);
}

test "parse nested profile" {
    const addr = parse("@myapi/orders/pending");
    try std.testing.expectEqual(AddressType.profile, addr.address_type);
    try std.testing.expectEqualStrings("myapi", addr.profile_namespace.?);
    try std.testing.expectEqualStrings("orders/pending", addr.profile_name.?);
}

test "parse glob pattern" {
    const addr1 = parse("data/*.csv");
    try std.testing.expectEqual(AddressType.glob, addr1.address_type);

    const addr2 = parse("data/**/*.json");
    try std.testing.expectEqual(AddressType.glob, addr2.address_type);

    const addr3 = parse("file?.txt");
    try std.testing.expectEqual(AddressType.glob, addr3.address_type);
}

test "parse home directory (not format override)" {
    const addr = parse("~/data.csv");
    try std.testing.expectEqual(AddressType.file, addr.address_type);
    try std.testing.expectEqualStrings("~/data.csv", addr.path);
    try std.testing.expect(addr.format_override == null);
    try std.testing.expectEqualStrings("csv", addr.inferred_format.?);
}

test "query iterator" {
    const addr = parse("file.csv?a=1&b=2&c=3");
    var iter = queryParams(addr);

    const p1 = iter.next().?;
    try std.testing.expectEqualStrings("a", p1.key);
    try std.testing.expectEqualStrings("1", p1.value);

    const p2 = iter.next().?;
    try std.testing.expectEqualStrings("b", p2.key);
    try std.testing.expectEqualStrings("2", p2.value);

    const p3 = iter.next().?;
    try std.testing.expectEqualStrings("c", p3.key);
    try std.testing.expectEqualStrings("3", p3.value);

    try std.testing.expect(iter.next() == null);
}

test "compression types" {
    try std.testing.expectEqual(Compression.gzip, Compression.fromExtension(".gz"));
    try std.testing.expectEqual(Compression.bzip2, Compression.fromExtension(".bz2"));
    try std.testing.expectEqual(Compression.xz, Compression.fromExtension(".xz"));
    try std.testing.expectEqual(Compression.zstd, Compression.fromExtension(".zst"));
    try std.testing.expectEqual(Compression.none, Compression.fromExtension(".txt"));
}

test "effective format prefers override" {
    const addr1 = parse("data.txt~csv");
    try std.testing.expectEqualStrings("csv", addr1.effectiveFormat().?);

    const addr2 = parse("data.csv");
    try std.testing.expectEqualStrings("csv", addr2.effectiveFormat().?);
}

test "file protocol is not remote" {
    const addr = parse("file:///path/to/data.csv");
    try std.testing.expectEqual(AddressType.url, addr.address_type);
    try std.testing.expectEqualStrings("file", addr.protocol.?);
    try std.testing.expect(!addr.isRemote());
}

test "duckdb protocol is not remote" {
    const addr = parse("duckdb://mydb.duckdb/table");
    try std.testing.expectEqual(AddressType.url, addr.address_type);
    try std.testing.expectEqualStrings("duckdb", addr.protocol.?);
    try std.testing.expect(!addr.isRemote());
}

// ============================================================================
// Edge Case Tests
// ============================================================================

test "parse empty string" {
    const addr = parse("");
    try std.testing.expectEqual(AddressType.file, addr.address_type);
    try std.testing.expectEqualStrings("", addr.path);
    try std.testing.expect(addr.format_override == null);
}

test "parse single dash (stdin)" {
    const addr = parse("-");
    try std.testing.expectEqual(AddressType.stdin, addr.address_type);
    try std.testing.expectEqualStrings("-", addr.path);
}

test "parse path with multiple tildes" {
    // Multiple tildes - only last should be format override
    const addr = parse("file~v1~csv");
    try std.testing.expectEqual(AddressType.file, addr.address_type);
    try std.testing.expectEqualStrings("file~v1", addr.path);
    try std.testing.expectEqualStrings("csv", addr.format_override.?);
}

test "parse path with tilde in filename" {
    // ~json at the end is a format override, not part of filename
    const addr = parse("~backup.txt~json");
    try std.testing.expectEqualStrings("~backup.txt", addr.path);
    try std.testing.expectEqualStrings("json", addr.format_override.?);
}

test "parse URL with query string and format override" {
    const addr = parse("https://api.example.com/data?key=value~json");
    try std.testing.expectEqual(AddressType.url, addr.address_type);
    // Format override should be extracted before query params
    try std.testing.expectEqualStrings("json", addr.format_override.?);
}

test "parse file with multiple extensions" {
    const addr = parse("data.tar.gz");
    try std.testing.expectEqual(AddressType.file, addr.address_type);
    try std.testing.expectEqual(Compression.gzip, addr.compression);
    try std.testing.expectEqualStrings("tar", addr.inferred_format.?);
}

test "parse path with spaces" {
    const addr = parse("path/to/file with spaces.csv");
    try std.testing.expectEqual(AddressType.file, addr.address_type);
    try std.testing.expectEqualStrings("path/to/file with spaces.csv", addr.path);
    try std.testing.expectEqualStrings("csv", addr.inferred_format.?);
}

test "parse profile with complex path" {
    const addr = parse("@namespace/path/to/nested/profile");
    try std.testing.expectEqual(AddressType.profile, addr.address_type);
    try std.testing.expectEqualStrings("namespace/path/to/nested/profile", addr.path);
}

test "parse glob with complex pattern" {
    const addr = parse("data/**/*test*.csv");
    try std.testing.expectEqual(AddressType.glob, addr.address_type);
    try std.testing.expect(addr.isGlob());
}

test "query iterator handles empty values" {
    const addr = parse("file.csv?key=&other=value");
    var iter = addr.queryIterator();

    const first = iter.next().?;
    try std.testing.expectEqualStrings("key", first.key);
    try std.testing.expectEqualStrings("", first.value);

    const second = iter.next().?;
    try std.testing.expectEqualStrings("other", second.key);
    try std.testing.expectEqualStrings("value", second.value);

    try std.testing.expect(iter.next() == null);
}

test "query iterator handles no equals sign" {
    const addr = parse("file.csv?flag");
    var iter = addr.queryIterator();

    const first = iter.next().?;
    try std.testing.expectEqualStrings("flag", first.key);
    try std.testing.expectEqualStrings("", first.value);
}
