//! jn-cat: Universal reader for JN
//!
//! Reads data from various sources and outputs NDJSON to stdout.
//!
//! Usage:
//!   jn-cat [OPTIONS] <ADDRESS>
//!
//! Address formats:
//!   - data.csv              Local file (format auto-detected)
//!   - data.csv.gz           Compressed file (decompressed automatically)
//!   - data.txt~csv          Format override
//!   - -                     Read from stdin
//!
//! Options:
//!   --help, -h              Show this help
//!   --version               Show version
//!   --delimiter=CHAR        CSV delimiter (passed to plugin)
//!   --no-header             CSV has no header row (passed to plugin)
//!
//! Examples:
//!   jn-cat data.csv
//!   jn-cat data.csv.gz
//!   jn-cat data.txt~csv
//!   jn-cat - < data.csv
//!   jn-cat --delimiter=';' data.csv

const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");
const jn_address = @import("jn-address");
const jn_profile = @import("jn-profile");

const VERSION = "0.1.0";

/// Escape a path for use in single-quoted shell arguments.
/// Returns the escaped string (caller must free) or the original if safe.
///
/// SECURITY: This prevents command injection via paths containing single quotes.
///
/// NOTE: For new code, prefer using jn_core.escapeForShell() which returns
/// an EscapedString with clear ownership semantics and a deinit() method.
/// This legacy function requires manual pointer comparison for cleanup.
fn escapeShellPath(allocator: std.mem.Allocator, path: []const u8) ![]const u8 {
    if (jn_core.isSafeForShellSingleQuote(path)) {
        return path;
    }
    return jn_core.escapeForShellSingleQuote(allocator, path);
}

/// Check if a string is safe for use as an HTTP header key or value.
/// SECURITY: Rejects strings containing CR (\r) or LF (\n) characters to prevent
/// HTTP header injection attacks. Header injection could allow attackers to:
/// - Add arbitrary headers (e.g., Set-Cookie for session fixation)
/// - Inject response body content (HTTP response splitting)
/// - Bypass security controls
///
/// Returns true if the string is safe, false if it contains CR/LF.
fn isValidHttpHeaderValue(value: []const u8) bool {
    for (value) |c| {
        if (c == '\r' or c == '\n') return false;
    }
    return true;
}

/// Build a shell command with properly escaped arguments.
/// All paths should be passed through escapeShellPath before inclusion.
fn buildShellCommand(allocator: std.mem.Allocator, comptime fmt: []const u8, args: anytype) ![]u8 {
    return std.fmt.allocPrint(allocator, fmt, args);
}

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const args = jn_cli.parseArgs();

    // Handle --help
    if (args.has("help") or args.has("h")) {
        printUsage();
        return;
    }

    // Handle --version
    if (args.has("version")) {
        printVersion();
        return;
    }

    // Get address from positional argument
    const address_str = getPositionalArg() orelse {
        jn_core.exitWithError("jn-cat: missing address argument\nUsage: jn-cat [OPTIONS] <ADDRESS>", .{});
    };

    // Parse the address
    const address = jn_address.parse(address_str);

    // Route based on address type
    switch (address.address_type) {
        .stdin => {
            try handleStdin(allocator, address, &args);
        },
        .file => {
            try handleFile(allocator, address, &args);
        },
        .url => {
            try handleUrl(allocator, address, &args);
        },
        .profile => {
            try handleProfile(allocator, address, &args);
        },
        .glob => {
            try handleGlob(allocator, address, &args);
        },
    }
}

/// Get the first positional argument (not starting with --)
fn getPositionalArg() ?[]const u8 {
    var args_iter = std.process.args();
    _ = args_iter.skip(); // Skip program name

    while (args_iter.next()) |arg| {
        if (!std.mem.startsWith(u8, arg, "-")) {
            return arg;
        }
        // Skip --key=value style args
        if (std.mem.startsWith(u8, arg, "--")) {
            continue;
        }
        // Single dash is stdin
        if (std.mem.eql(u8, arg, "-")) {
            return arg;
        }
        // -~format is stdin with format override
        if (arg.len > 1 and arg[0] == '-' and arg[1] == '~') {
            return arg;
        }
    }
    return null;
}

/// Handle stdin input
fn handleStdin(allocator: std.mem.Allocator, address: jn_address.Address, args: *const jn_cli.ArgParser) !void {
    const format = address.effectiveFormat() orelse "jsonl";

    // For JSONL, just pass through
    if (std.mem.eql(u8, format, "jsonl") or std.mem.eql(u8, format, "ndjson")) {
        try passthroughStdin();
        return;
    }

    // For other formats, spawn the format plugin
    try spawnFormatPlugin(allocator, format, null, address.query_string, args);
}

/// Handle local file
fn handleFile(allocator: std.mem.Allocator, address: jn_address.Address, args: *const jn_cli.ArgParser) !void {
    const format = address.effectiveFormat() orelse {
        jn_core.exitWithError("jn-cat: cannot determine format for '{s}'\nHint: use ~format to specify (e.g., data.txt~csv)", .{address.path});
    };

    // Check if file exists
    std.fs.cwd().access(address.path, .{}) catch {
        jn_core.exitWithError("jn-cat: file not found: {s}", .{address.path});
    };

    // Handle compression pipeline
    if (address.compression != .none) {
        try handleCompressedFile(allocator, address, format, args);
        return;
    }

    // Spawn format plugin with file as stdin
    try spawnFormatPlugin(allocator, format, address.path, address.query_string, args);
}

/// Build format plugin argument string for shell commands.
/// Returns allocated string that caller must free.
/// SECURITY: All values are properly escaped to prevent shell injection.
fn buildFormatArgs(allocator: std.mem.Allocator, args: *const jn_cli.ArgParser) ![]const u8 {
    var result: std.ArrayListUnmanaged(u8) = .empty;
    errdefer result.deinit(allocator);

    if (args.get("delimiter", null)) |delim| {
        // SECURITY: Escape delimiter to prevent shell injection via single quotes
        const escaped = try jn_core.escapeForShellSingleQuote(allocator, delim);
        defer allocator.free(escaped);

        try result.appendSlice(allocator, " --delimiter='");
        try result.appendSlice(allocator, escaped);
        try result.append(allocator, '\'');
    }
    if (args.has("no-header")) {
        try result.appendSlice(allocator, " --no-header");
    }

    return try result.toOwnedSlice(allocator);
}

/// Build CLI arguments from query string parameters.
/// Converts key=value pairs to --key=value format, skipping 'mode' which is handled separately.
/// SECURITY: All values are properly escaped to prevent shell injection.
fn buildQueryArgs(allocator: std.mem.Allocator, query_string: ?[]const u8) ![]const u8 {
    const qs = query_string orelse return try allocator.dupe(u8, "");

    var result: std.ArrayListUnmanaged(u8) = .empty;
    errdefer result.deinit(allocator);

    // Parse query string: key=value&key2=value2
    var params_iter = std.mem.splitScalar(u8, qs, '&');
    while (params_iter.next()) |param| {
        if (param.len == 0) continue;

        // Split on first '='
        var kv_iter = std.mem.splitScalar(u8, param, '=');
        const key = kv_iter.next() orelse continue;
        const value = kv_iter.rest();

        // Skip 'mode' parameter - handled separately
        if (std.mem.eql(u8, key, "mode")) continue;

        // Convert underscore to hyphen for CLI args (header_row -> header-row)
        var key_buf: [64]u8 = undefined;
        const key_len = @min(key.len, key_buf.len);
        @memcpy(key_buf[0..key_len], key[0..key_len]);
        for (key_buf[0..key_len]) |*c| {
            if (c.* == '_') c.* = '-';
        }
        const cli_key = key_buf[0..key_len];

        // SECURITY: Escape value to prevent shell injection
        const escaped = try jn_core.escapeForShellSingleQuote(allocator, value);
        defer allocator.free(escaped);

        try result.appendSlice(allocator, " --");
        try result.appendSlice(allocator, cli_key);
        try result.appendSlice(allocator, "='");
        try result.appendSlice(allocator, escaped);
        try result.append(allocator, '\'');
    }

    return try result.toOwnedSlice(allocator);
}

/// Extract mode from query string, defaulting to "read".
fn extractModeFromQuery(query_string: ?[]const u8) []const u8 {
    const qs = query_string orelse return "read";

    var params_iter = std.mem.splitScalar(u8, qs, '&');
    while (params_iter.next()) |param| {
        if (param.len == 0) continue;

        var kv_iter = std.mem.splitScalar(u8, param, '=');
        const key = kv_iter.next() orelse continue;
        const value = kv_iter.rest();

        if (std.mem.eql(u8, key, "mode") and value.len > 0) {
            return value;
        }
    }

    return "read";
}

/// Handle compressed file (spawn decompression + format pipeline)
fn handleCompressedFile(allocator: std.mem.Allocator, address: jn_address.Address, format: []const u8, args: *const jn_cli.ArgParser) !void {
    // Find compression plugin
    const compression_plugin = switch (address.compression) {
        .gzip => "gz",
        .bzip2 => {
            jn_core.exitWithError("jn-cat: bzip2 decompression not yet supported", .{});
        },
        .xz => {
            jn_core.exitWithError("jn-cat: xz decompression not yet supported", .{});
        },
        .zstd => {
            jn_core.exitWithError("jn-cat: zstd decompression not yet supported", .{});
        },
        .none => unreachable,
    };

    // Find plugins
    const gz_path = findPlugin(allocator, compression_plugin) orelse {
        jn_core.exitWithError("jn-cat: compression plugin '{s}' not found", .{compression_plugin});
    };

    const format_path = findPlugin(allocator, format) orelse {
        jn_core.exitWithError("jn-cat: format plugin '{s}' not found", .{format});
    };

    // Build format args (dynamically allocated, properly escaped)
    const format_args = try buildFormatArgs(allocator, args);
    defer allocator.free(format_args);

    // SECURITY: Escape the file path to prevent command injection via filenames
    // containing single quotes (e.g., "file'; rm -rf /; echo '")
    const escaped_path = try escapeShellPath(allocator, address.path);
    defer if (escaped_path.ptr != address.path.ptr) allocator.free(@constCast(escaped_path));

    // Use shell to construct pipeline: cat file | gz --mode=raw | format --mode=read [args]
    const shell_cmd = try std.fmt.allocPrint(
        allocator,
        "cat '{s}' | {s} --mode=raw | {s} --mode=read{s}",
        .{ escaped_path, gz_path, format_path, format_args },
    );
    defer allocator.free(shell_cmd);

    // Run via shell
    const shell_argv: [3][]const u8 = .{ "/bin/sh", "-c", shell_cmd };
    var shell_child = std.process.Child.init(&shell_argv, allocator);
    shell_child.stdin_behavior = .Close;
    shell_child.stdout_behavior = .Inherit;
    shell_child.stderr_behavior = .Inherit;

    try shell_child.spawn();
    const result = shell_child.wait() catch |err| {
        jn_core.exitWithError("jn-cat: pipeline execution failed: {s}", .{@errorName(err)});
    };

    switch (result) {
        .Exited => |code| if (code != 0) std.process.exit(code),
        .Signal => |sig| std.process.exit(128 +| @as(u8, @intCast(@min(sig, 127)))),
        .Stopped, .Unknown => std.process.exit(1),
    }
}

/// Profile type enumeration
const ProfileType = enum { http, duckdb, code, file };

/// Handle profile reference (@namespace/name)
fn handleProfile(allocator: std.mem.Allocator, address: jn_address.Address, args: *const jn_cli.ArgParser) !void {
    const namespace = address.profile_namespace orelse {
        jn_core.exitWithError("jn-cat: profile reference requires namespace: @namespace/name\nAddress: {s}", .{address.raw});
    };
    const name = address.profile_name orelse {
        jn_core.exitWithError("jn-cat: profile reference requires name: @namespace/name\nAddress: {s}", .{address.raw});
    };

    // Special case: @code/* routes directly to code_.py plugin
    if (std.mem.eql(u8, namespace, "code")) {
        try handleCodeProfile(allocator, address);
        return;
    }

    // Detect project root by looking for .jn directory
    var project_root: ?[]const u8 = null;
    var cwd_buf: [std.fs.max_path_bytes]u8 = undefined;
    if (std.fs.cwd().realpath(".", &cwd_buf)) |cwd| {
        // Check if .jn exists in current directory
        var check_dir: []const u8 = cwd;
        while (true) {
            const jn_dir = std.fmt.allocPrint(allocator, "{s}/.jn", .{check_dir}) catch break;
            defer allocator.free(jn_dir);
            if (std.fs.cwd().access(jn_dir, .{})) |_| {
                project_root = allocator.dupe(u8, check_dir) catch null;
                break;
            } else |_| {}
            // Go up one directory
            if (std.fs.path.dirname(check_dir)) |parent| {
                if (std.mem.eql(u8, parent, check_dir)) break; // Reached root
                check_dir = parent;
            } else break;
        }
    } else |_| {}
    defer if (project_root) |pr| allocator.free(pr);

    // Get profile directories
    const profile_dirs = jn_profile.getProfileDirs(allocator, .{
        .project_root = project_root,
        .home_dir = jn_profile.getHomeDir(),
        .jn_home = jn_profile.getJnHome(),
    }) catch {
        jn_core.exitWithError("jn-cat: failed to get profile directories", .{});
    };
    defer {
        for (profile_dirs) |d| allocator.free(d);
        allocator.free(profile_dirs);
    }

    // Search for profile in each directory
    // Try HTTP first, then DuckDB
    var profile_type: ProfileType = .http;
    var profile_file: ?[]const u8 = null;
    var profile_dir: ?[]const u8 = null;

    // Search HTTP profiles: profiles/http/<namespace>/<name>.json
    for (profile_dirs) |dir| {
        const path = std.fmt.allocPrint(allocator, "{s}/http/{s}/{s}.json", .{ dir, namespace, name }) catch continue;
        if (jn_profile.pathExists(path)) {
            profile_file = path;
            profile_dir = std.fmt.allocPrint(allocator, "{s}/http/{s}", .{ dir, namespace }) catch {
                allocator.free(path);
                continue;
            };
            profile_type = .http;
            break;
        } else {
            allocator.free(path);
        }
    }

    // If no HTTP profile found, search DuckDB profiles: profiles/duckdb/<namespace>/<name>.sql
    if (profile_file == null) {
        for (profile_dirs) |dir| {
            const path = std.fmt.allocPrint(allocator, "{s}/duckdb/{s}/{s}.sql", .{ dir, namespace, name }) catch continue;
            if (jn_profile.pathExists(path)) {
                profile_file = path;
                profile_dir = std.fmt.allocPrint(allocator, "{s}/duckdb/{s}", .{ dir, namespace }) catch {
                    allocator.free(path);
                    continue;
                };
                profile_type = .duckdb;
                break;
            } else {
                allocator.free(path);
            }
        }
    }

    // If no DuckDB profile found, search file/folder profiles: profiles/file/<namespace>/<name>.json
    if (profile_file == null) {
        for (profile_dirs) |dir| {
            const path = std.fmt.allocPrint(allocator, "{s}/file/{s}/{s}.json", .{ dir, namespace, name }) catch continue;
            if (jn_profile.pathExists(path)) {
                profile_file = path;
                profile_dir = std.fmt.allocPrint(allocator, "{s}/file/{s}", .{ dir, namespace }) catch {
                    allocator.free(path);
                    continue;
                };
                profile_type = .file;
                break;
            } else {
                allocator.free(path);
            }
        }
    }

    if (profile_file == null or profile_dir == null) {
        jn_core.exitWithError("jn-cat: profile not found: @{s}/{s}\nSearched:\n  profiles/http/{s}/{s}.json\n  profiles/duckdb/{s}/{s}.sql\n  profiles/file/{s}/{s}.json", .{ namespace, name, namespace, name, namespace, name, namespace, name });
    }
    defer allocator.free(profile_file.?);
    defer allocator.free(profile_dir.?);

    // Route based on profile type
    switch (profile_type) {
        .http => try handleHttpProfile(allocator, address, args, namespace, name, profile_dir.?),
        .duckdb => try handleDuckdbProfile(allocator, address, profile_dir.?),
        .file => try handleFileProfile(allocator, address, args, namespace, name, profile_dir.?),
        .code => unreachable, // Handled above
    }
}

/// Find the plugins root directory (where jn_home/plugins lives)
/// Tries multiple locations: JN_HOME, relative to cwd, relative to executable
/// Returns an allocated string that the caller must free.
fn findPluginsRoot(allocator: std.mem.Allocator) []const u8 {
    // Try JN_HOME first - but verify jn_home/plugins exists there
    if (std.posix.getenv("JN_HOME")) |jn_home| {
        const check_path = std.fmt.allocPrint(allocator, "{s}/jn_home/plugins", .{jn_home}) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
        defer allocator.free(check_path);
        if (std.fs.cwd().access(check_path, .{})) |_| {
            return allocator.dupe(u8, jn_home) catch {
                jn_core.exitWithError("jn-cat: out of memory", .{});
            };
        } else |_| {}
    }

    // Try relative to current working directory
    if (std.fs.cwd().access("jn_home/plugins", .{})) |_| {
        return allocator.dupe(u8, ".") catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    } else |_| {}

    // Try to find relative to executable path
    var exe_path_buf: [std.fs.max_path_bytes]u8 = undefined;
    if (std.fs.selfExePath(&exe_path_buf)) |exe_path| {
        // Try libexec layout first: jn_home is sibling in same directory
        if (std.fs.path.dirname(exe_path)) |exe_dir| {
            const check_path = std.fmt.allocPrint(allocator, "{s}/jn_home/plugins", .{exe_dir}) catch {
                jn_core.exitWithError("jn-cat: out of memory", .{});
            };
            defer allocator.free(check_path);
            if (std.fs.cwd().access(check_path, .{})) |_| {
                return allocator.dupe(u8, exe_dir) catch {
                    jn_core.exitWithError("jn-cat: out of memory", .{});
                };
            } else |_| {}
        }

        // Try dev layout: go up 4 levels from bin -> jn-cat -> zig -> tools -> jn
        var dir = std.fs.path.dirname(exe_path); // bin
        var i: usize = 0;
        while (i < 4 and dir != null) : (i += 1) {
            dir = std.fs.path.dirname(dir.?);
        }
        if (dir) |root| {
            const check_path = std.fmt.allocPrint(allocator, "{s}/jn_home/plugins", .{root}) catch {
                jn_core.exitWithError("jn-cat: out of memory", .{});
            };
            defer allocator.free(check_path);
            if (std.fs.cwd().access(check_path, .{})) |_| {
                // Return a copy since root points into exe_path_buf
                return allocator.dupe(u8, root) catch {
                    jn_core.exitWithError("jn-cat: out of memory", .{});
                };
            } else |_| {}
        }
    } else |_| {}

    // Fallback - always return allocated memory for consistent ownership
    return allocator.dupe(u8, ".") catch {
        jn_core.exitWithError("jn-cat: out of memory", .{});
    };
}

/// Handle @code/* profiles by invoking code_.py plugin
fn handleCodeProfile(allocator: std.mem.Allocator, address: jn_address.Address) !void {
    // Find code_.py plugin - use plugins root, not JN_HOME
    const plugins_root = findPluginsRoot(allocator);
    defer allocator.free(plugins_root);

    const plugin_path = try std.fmt.allocPrint(allocator, "{s}/jn_home/plugins/protocols/code_.py", .{plugins_root});
    defer allocator.free(plugin_path);

    // Build the full address with query string
    const full_address = if (address.query_string) |qs|
        try std.fmt.allocPrint(allocator, "@{s}/{s}?{s}", .{
            address.profile_namespace.?,
            address.profile_name.?,
            qs,
        })
    else
        try std.fmt.allocPrint(allocator, "@{s}/{s}", .{
            address.profile_namespace.?,
            address.profile_name.?,
        });
    defer allocator.free(full_address);

    // Build shell command: uv run --script code_.py --mode=read <address>
    const shell_cmd = try std.fmt.allocPrint(
        allocator,
        "uv run --script '{s}' --mode=read '{s}'",
        .{ plugin_path, full_address },
    );
    defer allocator.free(shell_cmd);

    // Run via shell
    const shell_argv: [3][]const u8 = .{ "/bin/sh", "-c", shell_cmd };
    var shell_child = std.process.Child.init(&shell_argv, allocator);
    shell_child.stdin_behavior = .Close;
    shell_child.stdout_behavior = .Inherit;
    shell_child.stderr_behavior = .Inherit;

    try shell_child.spawn();
    const result = try shell_child.wait();

    switch (result) {
        .Exited => |code| {
            if (code != 0) {
                std.process.exit(code);
            }
        },
        else => {
            std.process.exit(1);
        },
    }
}

/// Handle DuckDB profiles by invoking duckdb_.py plugin
fn handleDuckdbProfile(allocator: std.mem.Allocator, address: jn_address.Address, profile_dir: []const u8) !void {
    // Find duckdb_.py plugin - use plugins root, not JN_HOME
    const plugins_root = findPluginsRoot(allocator);
    defer allocator.free(plugins_root);

    const plugin_path = try std.fmt.allocPrint(allocator, "{s}/jn_home/plugins/databases/duckdb_.py", .{plugins_root});
    defer allocator.free(plugin_path);

    // Build the full address with query string
    const full_address = if (address.query_string) |qs|
        try std.fmt.allocPrint(allocator, "@{s}/{s}?{s}", .{
            address.profile_namespace.?,
            address.profile_name.?,
            qs,
        })
    else
        try std.fmt.allocPrint(allocator, "@{s}/{s}", .{
            address.profile_namespace.?,
            address.profile_name.?,
        });
    defer allocator.free(full_address);

    // Set JN_PROJECT_DIR to the project root (so duckdb_.py can find profiles)
    // The profile_dir is like ".../profiles/duckdb/namespace"
    // duckdb_.py looks in JN_PROJECT_DIR/profiles/duckdb, so we need to go up 3 levels:
    //   namespace -> duckdb -> profiles -> project_root
    const duckdb_dir = std.fs.path.dirname(profile_dir) orelse profile_dir; // .../profiles/duckdb
    const profiles_dir = std.fs.path.dirname(duckdb_dir) orelse duckdb_dir; // .../profiles
    const project_root = std.fs.path.dirname(profiles_dir) orelse profiles_dir; // ...

    // Build shell command: JN_PROJECT_DIR=<project_root> uv run --script duckdb_.py --mode=read --path <address>
    const shell_cmd = try std.fmt.allocPrint(
        allocator,
        "JN_PROJECT_DIR='{s}' uv run --script '{s}' --mode=read --path '{s}'",
        .{ project_root, plugin_path, full_address },
    );
    defer allocator.free(shell_cmd);

    // Run via shell
    const shell_argv: [3][]const u8 = .{ "/bin/sh", "-c", shell_cmd };
    var shell_child = std.process.Child.init(&shell_argv, allocator);
    shell_child.stdin_behavior = .Close;
    shell_child.stdout_behavior = .Inherit;
    shell_child.stderr_behavior = .Inherit;

    try shell_child.spawn();
    const result = try shell_child.wait();

    switch (result) {
        .Exited => |code| {
            if (code != 0) {
                std.process.exit(code);
            }
        },
        else => {
            std.process.exit(1);
        },
    }
}

/// Handle HTTP profiles using curl
fn handleHttpProfile(allocator: std.mem.Allocator, address: jn_address.Address, args: *const jn_cli.ArgParser, namespace: []const u8, name: []const u8, profile_dir: []const u8) !void {
    // Load profile with hierarchical merge
    const profile_path = try std.fmt.allocPrint(allocator, "{s}.json", .{name});
    defer allocator.free(profile_path);

    var config = jn_profile.loadProfile(allocator, profile_dir, profile_path, true) catch |err| {
        jn_core.exitWithError("jn-cat: failed to load profile @{s}/{s}: {s}", .{ namespace, name, @errorName(err) });
    };
    defer jn_profile.freeValue(allocator, config);

    // Extract profile fields
    const base_url = if (config.object.get("base_url")) |v| v.string else null;
    const path_str = if (config.object.get("path")) |v| v.string else "";

    if (base_url == null) {
        jn_core.exitWithError("jn-cat: profile @{s}/{s} missing base_url", .{ namespace, name });
    }

    // Build full URL
    const full_url = if (path_str.len > 0)
        try std.fmt.allocPrint(allocator, "{s}{s}", .{ base_url.?, path_str })
    else
        try std.fmt.allocPrint(allocator, "{s}", .{base_url.?});
    defer allocator.free(full_url);

    // Add query parameters from address
    const url_with_params = if (address.query_string) |qs|
        try std.fmt.allocPrint(allocator, "{s}?{s}", .{ full_url, qs })
    else
        try std.fmt.allocPrint(allocator, "{s}", .{full_url});
    defer allocator.free(url_with_params);

    // Build headers from profile with proper shell escaping
    var header_list: std.ArrayListUnmanaged(u8) = .empty;
    defer header_list.deinit(allocator);

    if (config.object.get("headers")) |headers_val| {
        if (headers_val == .object) {
            var iter = headers_val.object.iterator();
            while (iter.next()) |entry| {
                if (entry.value_ptr.* == .string) {
                    // SECURITY: Validate header key and value to prevent HTTP header injection
                    // (CR/LF characters could allow injecting additional headers or response splitting)
                    if (!isValidHttpHeaderValue(entry.key_ptr.*) or !isValidHttpHeaderValue(entry.value_ptr.string)) {
                        std.debug.print("jn-cat: warning: skipping header with invalid characters (CR/LF not allowed)\n", .{});
                        continue;
                    }

                    // SECURITY: Escape header key and value to prevent command injection
                    const escaped_key = escapeShellPath(allocator, entry.key_ptr.*) catch continue;
                    defer if (escaped_key.ptr != entry.key_ptr.*.ptr) allocator.free(@constCast(escaped_key));
                    const escaped_value = escapeShellPath(allocator, entry.value_ptr.string) catch continue;
                    defer if (escaped_value.ptr != entry.value_ptr.string.ptr) allocator.free(@constCast(escaped_value));

                    header_list.appendSlice(allocator, " -H '") catch continue;
                    header_list.appendSlice(allocator, escaped_key) catch continue;
                    header_list.appendSlice(allocator, ": ") catch continue;
                    header_list.appendSlice(allocator, escaped_value) catch continue;
                    header_list.append(allocator, '\'') catch continue;
                }
            }
        }
    }
    const header_args = header_list.items;

    // Get format (default to json for HTTP profiles)
    const format = address.effectiveFormat() orelse "json";

    // Find format plugin
    const plugin_path = findPlugin(allocator, format);

    // Build format args (dynamically allocated, properly escaped)
    const format_args = try buildFormatArgs(allocator, args);
    defer allocator.free(format_args);

    // SECURITY: Escape the URL to prevent command injection
    const escaped_url = try escapeShellPath(allocator, url_with_params);
    defer if (escaped_url.ptr != url_with_params.ptr) allocator.free(@constCast(escaped_url));

    // Build curl command with headers
    var shell_cmd: []const u8 = undefined;

    if (plugin_path) |fmt_path| {
        shell_cmd = std.fmt.allocPrint(
            allocator,
            "curl -sS -L -f{s} '{s}' | {s} --mode=read{s}",
            .{ header_args, escaped_url, fmt_path, format_args },
        ) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    } else if (std.mem.eql(u8, format, "jsonl") or std.mem.eql(u8, format, "ndjson") or std.mem.eql(u8, format, "json")) {
        shell_cmd = std.fmt.allocPrint(
            allocator,
            "curl -sS -L -f{s} '{s}'",
            .{ header_args, escaped_url },
        ) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    } else {
        jn_core.exitWithError("jn-cat: format plugin '{s}' not found", .{format});
    }
    defer allocator.free(shell_cmd);

    // Run via shell
    const shell_argv: [3][]const u8 = .{ "/bin/sh", "-c", shell_cmd };
    var shell_child = std.process.Child.init(&shell_argv, allocator);
    shell_child.stdin_behavior = .Close;
    shell_child.stdout_behavior = .Inherit;
    shell_child.stderr_behavior = .Inherit;

    try shell_child.spawn();
    const result = shell_child.wait() catch |err| {
        jn_core.exitWithError("jn-cat: profile fetch failed: {s}", .{@errorName(err)});
    };

    switch (result) {
        .Exited => |code| {
            if (code != 0) {
                if (code == 22) {
                    jn_core.exitWithError("jn-cat: HTTP error fetching profile @{s}/{s}: {s}", .{ namespace, name, url_with_params });
                }
                std.process.exit(code);
            }
        },
        else => {
            std.process.exit(1);
        },
    }
}

/// Handle file/folder profiles - expand glob pattern and process files
/// Profile format:
/// {
///   "pattern": "data/**/*.jsonl",      // glob pattern (required)
///   "inject_meta": true,               // inject path metadata (optional, default true)
///   "filter": "select(.level == ...)", // ZQ filter expression (optional)
///   "description": "..."               // human readable description (optional)
/// }
fn handleFileProfile(allocator: std.mem.Allocator, address: jn_address.Address, args: *const jn_cli.ArgParser, namespace: []const u8, name: []const u8, profile_dir: []const u8) !void {
    _ = address; // Profile address is resolved through profile_dir

    // Load profile with hierarchical merge
    const profile_path = std.fmt.allocPrint(allocator, "{s}.json", .{name}) catch {
        jn_core.exitWithError("jn-cat: out of memory", .{});
    };
    defer allocator.free(profile_path);

    var config = jn_profile.loadProfile(allocator, profile_dir, profile_path, true) catch |err| {
        jn_core.exitWithError("jn-cat: failed to load file profile @{s}/{s}: {s}", .{ namespace, name, @errorName(err) });
    };
    defer jn_profile.freeValue(allocator, config);

    // Extract profile fields
    const pattern = if (config.object.get("pattern")) |v| v.string else null;
    const inject_meta_val = config.object.get("inject_meta");
    const inject_meta = if (inject_meta_val) |v| (v == .bool and v.bool) or v != .bool else true; // default true
    const filter_expr = if (config.object.get("filter")) |v| v.string else null;

    if (pattern == null) {
        jn_core.exitWithError("jn-cat: file profile @{s}/{s} missing required 'pattern' field", .{ namespace, name });
    }

    // Resolve pattern relative to profile directory's project root
    // Profile is at: .../project/.jn/profiles/file/<namespace>/<name>.json
    // profile_dir is: .../project/.jn/profiles/file/<namespace>
    // Project root is 4 levels up: namespace -> file -> profiles -> .jn -> project
    const file_dir = std.fs.path.dirname(profile_dir) orelse profile_dir; // .../profiles/file
    const profiles_base = std.fs.path.dirname(file_dir) orelse file_dir; // .../profiles
    const jn_dir = std.fs.path.dirname(profiles_base) orelse profiles_base; // .../.jn
    const project_root = std.fs.path.dirname(jn_dir) orelse jn_dir; // .../project

    // Build full pattern path
    var full_pattern: []const u8 = undefined;
    if (std.fs.path.isAbsolute(pattern.?)) {
        full_pattern = allocator.dupe(u8, pattern.?) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    } else {
        full_pattern = std.fmt.allocPrint(allocator, "{s}/{s}", .{ project_root, pattern.? }) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    }
    defer allocator.free(full_pattern);

    // Create a synthetic address for glob processing
    const glob_address = jn_address.parse(full_pattern);

    // Override inject_meta based on profile setting or command line
    const effective_inject_meta = inject_meta or args.has("meta") or args.has("inject-meta");

    // If there's a filter expression, we need to pipe through jn-filter
    if (filter_expr) |filter| {
        // Process glob with filter: expand glob, process files, pipe through filter
        try handleFileProfileWithFilter(allocator, glob_address, args, effective_inject_meta, filter);
    } else {
        // Process glob directly with modified args
        if (effective_inject_meta and !args.has("meta") and !args.has("inject-meta")) {
            // Need to force inject_meta - call handleGlob with meta flag
            // Create a modified args parser isn't straightforward, so use shell pipeline
            try handleFileProfileDirect(allocator, full_pattern, args, effective_inject_meta);
        } else {
            try handleGlob(allocator, glob_address, args);
        }
    }
}

/// Handle file profile with direct glob expansion and optional metadata injection
fn handleFileProfileDirect(allocator: std.mem.Allocator, pattern: []const u8, args: *const jn_cli.ArgParser, inject_meta: bool) !void {
    _ = args;

    // Build shell command for glob expansion
    var expand_cmd: []const u8 = undefined;

    if (std.mem.indexOf(u8, pattern, "**") != null) {
        // Use find for recursive patterns
        const last_slash = std.mem.lastIndexOf(u8, pattern, "/") orelse 0;
        const base_dir = if (last_slash > 0) pattern[0..last_slash] else ".";
        var file_pattern = pattern[last_slash + 1 ..];

        // Strip **/ prefix from file pattern
        while (std.mem.startsWith(u8, file_pattern, "**/")) {
            file_pattern = file_pattern[3..];
        }
        if (std.mem.startsWith(u8, file_pattern, "**")) {
            file_pattern = file_pattern[2..];
        }

        // Extract the base directory (before any **)
        var dir_to_search = base_dir;
        if (std.mem.indexOf(u8, base_dir, "**")) |double_star| {
            dir_to_search = if (double_star > 0) base_dir[0 .. double_star - 1] else ".";
        }

        // SECURITY: Escape directory and file pattern
        const escaped_dir = try escapeShellPath(allocator, dir_to_search);
        defer if (escaped_dir.ptr != dir_to_search.ptr) allocator.free(@constCast(escaped_dir));
        const escaped_file_pattern = try escapeShellPath(allocator, file_pattern);
        defer if (escaped_file_pattern.ptr != file_pattern.ptr) allocator.free(@constCast(escaped_file_pattern));

        expand_cmd = std.fmt.allocPrint(
            allocator,
            "find '{s}' -type f -name '{s}' 2>/dev/null | sort",
            .{ escaped_dir, escaped_file_pattern },
        ) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    } else {
        // Simple glob - use bash with globstar
        if (!jn_core.isGlobPatternSafe(pattern)) {
            jn_core.exitWithError("jn-cat: glob pattern contains unsafe characters: {s}", .{pattern});
        }

        expand_cmd = std.fmt.allocPrint(
            allocator,
            "shopt -s nullglob; for f in {s}; do [ -f \"$f\" ] && echo \"$f\"; done",
            .{pattern},
        ) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    }
    defer allocator.free(expand_cmd);

    // Use bash for better glob support
    const expand_argv: [3][]const u8 = .{ "/bin/bash", "-c", expand_cmd };
    var expand_child = std.process.Child.init(&expand_argv, allocator);
    expand_child.stdin_behavior = .Close;
    expand_child.stdout_behavior = .Pipe;
    expand_child.stderr_behavior = .Inherit;

    try expand_child.spawn();

    // Read file list from stdout and process
    const stdout_pipe = expand_child.stdout.?;
    var file_count: usize = 0;

    var reader_buf: [4096]u8 = undefined;
    var reader_wrapper = stdout_pipe.reader(&reader_buf);
    const reader = &reader_wrapper.interface;
    while (jn_core.readLine(reader)) |line| {
        const file_path = std.mem.trim(u8, line, " \t\r\n");
        if (file_path.len == 0) continue;

        // Process this file with metadata injection
        if (inject_meta) {
            try outputWithMeta(allocator, file_path, file_count);
        } else {
            // Just cat the file
            const escaped_path = try escapeShellPath(allocator, file_path);
            defer if (escaped_path.ptr != file_path.ptr) allocator.free(@constCast(escaped_path));

            const shell_cmd = std.fmt.allocPrint(allocator, "cat '{s}'", .{escaped_path}) catch continue;
            defer allocator.free(shell_cmd);

            const shell_argv: [3][]const u8 = .{ "/bin/sh", "-c", shell_cmd };
            var child = std.process.Child.init(&shell_argv, allocator);
            child.stdin_behavior = .Close;
            child.stdout_behavior = .Inherit;
            child.stderr_behavior = .Inherit;

            try child.spawn();
            _ = child.wait() catch {};
        }
        file_count += 1;
    }

    _ = expand_child.wait() catch {};

    if (file_count == 0) {
        jn_core.exitWithError("jn-cat: no files match pattern: {s}", .{pattern});
    }
}

/// Handle file profile with ZQ filter - pipe expanded glob through jn-filter
fn handleFileProfileWithFilter(allocator: std.mem.Allocator, glob_address: jn_address.Address, args: *const jn_cli.ArgParser, inject_meta: bool, filter: []const u8) !void {
    _ = args;
    const pattern = glob_address.path;

    // Find jn-filter executable
    var exe_path_buf: [std.fs.max_path_bytes]u8 = undefined;
    var filter_path: []const u8 = "jn-filter"; // fallback to PATH

    if (std.fs.selfExePath(&exe_path_buf)) |exe_path| {
        if (std.fs.path.dirname(exe_path)) |exe_dir| {
            const sibling_path = std.fmt.allocPrint(allocator, "{s}/jn-filter", .{exe_dir}) catch filter_path;
            if (std.fs.cwd().access(sibling_path, .{})) |_| {
                filter_path = sibling_path;
            } else |_| {
                allocator.free(sibling_path);
            }
        }
    } else |_| {}

    // Build glob expansion command
    var expand_part: []const u8 = undefined;

    if (std.mem.indexOf(u8, pattern, "**") != null) {
        const last_slash = std.mem.lastIndexOf(u8, pattern, "/") orelse 0;
        const base_dir = if (last_slash > 0) pattern[0..last_slash] else ".";
        var file_pattern = pattern[last_slash + 1 ..];

        while (std.mem.startsWith(u8, file_pattern, "**/")) {
            file_pattern = file_pattern[3..];
        }
        if (std.mem.startsWith(u8, file_pattern, "**")) {
            file_pattern = file_pattern[2..];
        }

        var dir_to_search = base_dir;
        if (std.mem.indexOf(u8, base_dir, "**")) |double_star| {
            dir_to_search = if (double_star > 0) base_dir[0 .. double_star - 1] else ".";
        }

        const escaped_dir = try escapeShellPath(allocator, dir_to_search);
        defer if (escaped_dir.ptr != dir_to_search.ptr) allocator.free(@constCast(escaped_dir));
        const escaped_file_pattern = try escapeShellPath(allocator, file_pattern);
        defer if (escaped_file_pattern.ptr != file_pattern.ptr) allocator.free(@constCast(escaped_file_pattern));

        expand_part = std.fmt.allocPrint(allocator, "find '{s}' -type f -name '{s}' 2>/dev/null | sort", .{ escaped_dir, escaped_file_pattern }) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    } else {
        if (!jn_core.isGlobPatternSafe(pattern)) {
            jn_core.exitWithError("jn-cat: glob pattern contains unsafe characters: {s}", .{pattern});
        }
        expand_part = std.fmt.allocPrint(allocator, "shopt -s nullglob; for f in {s}; do [ -f \"$f\" ] && echo \"$f\"; done", .{pattern}) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    }
    defer allocator.free(expand_part);

    // Escape filter for shell
    const escaped_filter = try escapeShellPath(allocator, filter);
    defer if (escaped_filter.ptr != filter.ptr) allocator.free(@constCast(escaped_filter));

    // Build full pipeline: expand files -> read each with metadata -> filter
    // We need to process files in a subshell and pipe through filter
    const meta_flag: []const u8 = if (inject_meta) " --meta" else "";

    // Find jn-cat executable path
    var cat_path: []const u8 = "jn-cat";
    if (std.fs.selfExePath(&exe_path_buf)) |exe_path| {
        cat_path = exe_path;
    } else |_| {}

    const escaped_cat_path = try escapeShellPath(allocator, cat_path);
    defer if (escaped_cat_path.ptr != cat_path.ptr) allocator.free(@constCast(escaped_cat_path));
    const escaped_pattern = try escapeShellPath(allocator, pattern);
    defer if (escaped_pattern.ptr != pattern.ptr) allocator.free(@constCast(escaped_pattern));

    // Build the shell command: jn-cat 'pattern' [--meta] | jn-filter 'filter'
    const shell_cmd = std.fmt.allocPrint(
        allocator,
        "'{s}' '{s}'{s} | '{s}' '{s}'",
        .{ escaped_cat_path, escaped_pattern, meta_flag, filter_path, escaped_filter },
    ) catch {
        jn_core.exitWithError("jn-cat: out of memory", .{});
    };
    defer allocator.free(shell_cmd);

    // Run via bash (need shopt for globs)
    const shell_argv: [3][]const u8 = .{ "/bin/bash", "-c", shell_cmd };
    var shell_child = std.process.Child.init(&shell_argv, allocator);
    shell_child.stdin_behavior = .Close;
    shell_child.stdout_behavior = .Inherit;
    shell_child.stderr_behavior = .Inherit;

    try shell_child.spawn();
    const result = shell_child.wait() catch |err| {
        jn_core.exitWithError("jn-cat: file profile execution failed: {s}", .{@errorName(err)});
    };

    switch (result) {
        .Exited => |code| {
            if (code != 0) {
                std.process.exit(code);
            }
        },
        else => {
            std.process.exit(1);
        },
    }
}

/// Handle URL address (http://, https://, s3://, etc.)
fn handleUrl(allocator: std.mem.Allocator, address: jn_address.Address, args: *const jn_cli.ArgParser) !void {
    const protocol = address.protocol orelse {
        jn_core.exitWithError("jn-cat: URL has no protocol: {s}", .{address.raw});
    };

    // For HTTP/HTTPS, use curl (OpenDAL HTTP service doesn't work well with REST APIs)
    if (std.mem.eql(u8, protocol, "http") or std.mem.eql(u8, protocol, "https")) {
        try handleHttpUrl(allocator, address, args);
        return;
    }

    // For cloud storage (S3, GCS, GDrive), use OpenDAL plugin
    if (std.mem.eql(u8, protocol, "s3") or
        std.mem.eql(u8, protocol, "gs") or
        std.mem.eql(u8, protocol, "gcs") or
        std.mem.eql(u8, protocol, "gdrive"))
    {
        try handleOpenDalUrl(allocator, address, args);
        return;
    }

    jn_core.exitWithError("jn-cat: protocol '{s}' not supported\nAddress: {s}", .{ protocol, address.raw });
}

/// Handle HTTP/HTTPS URL using curl
fn handleHttpUrl(allocator: std.mem.Allocator, address: jn_address.Address, args: *const jn_cli.ArgParser) !void {
    const format = address.effectiveFormat() orelse "json"; // Default to JSON for HTTP

    // Build the clean URL (protocol://path) with query string but without format hint
    const protocol = address.protocol.?;
    const url = if (address.query_string) |qs|
        try std.fmt.allocPrint(allocator, "{s}://{s}?{s}", .{ protocol, address.path, qs })
    else
        try std.fmt.allocPrint(allocator, "{s}://{s}", .{ protocol, address.path });
    defer allocator.free(url);

    // Find format plugin
    const plugin_path = findPlugin(allocator, format);

    // Build format args (dynamically allocated, properly escaped)
    const format_args = try buildFormatArgs(allocator, args);
    defer allocator.free(format_args);

    // Build header arg if provided
    // Note: Headers from --header arg could also contain quotes; escape them
    var header_arg_buf: [512]u8 = undefined;
    var header_arg: []const u8 = "";
    if (args.get("header", null)) |header| {
        // SECURITY: Escape the header to prevent command injection
        const escaped_header = escapeShellPath(allocator, header) catch "";
        defer if (escaped_header.len > 0 and escaped_header.ptr != header.ptr) allocator.free(@constCast(escaped_header));
        if (escaped_header.len > 0) {
            header_arg = std.fmt.bufPrint(&header_arg_buf, " -H '{s}'", .{escaped_header}) catch "";
        }
    }

    // SECURITY: Escape the URL to prevent command injection
    const escaped_url = try escapeShellPath(allocator, url);
    defer if (escaped_url.ptr != url.ptr) allocator.free(@constCast(escaped_url));

    // Build the shell command
    var shell_cmd: []const u8 = undefined;

    if (address.compression != .none) {
        // URL with compression: curl | gunzip | format_plugin
        const gz_path = findPlugin(allocator, "gz") orelse {
            jn_core.exitWithError("jn-cat: compression plugin 'gz' not found", .{});
        };

        if (plugin_path) |fmt_path| {
            // curl URL | gz --mode=raw | format --mode=read
            shell_cmd = try std.fmt.allocPrint(
                allocator,
                "curl -sS -L -f{s} '{s}' | {s} --mode=raw | {s} --mode=read{s}",
                .{ header_arg, escaped_url, gz_path, fmt_path, format_args },
            );
        } else {
            // No format plugin (assume JSONL) - just decompress
            shell_cmd = try std.fmt.allocPrint(
                allocator,
                "curl -sS -L -f{s} '{s}' | {s} --mode=raw",
                .{ header_arg, escaped_url, gz_path },
            );
        }
    } else if (plugin_path) |fmt_path| {
        // curl URL | format_plugin --mode=read
        shell_cmd = try std.fmt.allocPrint(
            allocator,
            "curl -sS -L -f{s} '{s}' | {s} --mode=read{s}",
            .{ header_arg, escaped_url, fmt_path, format_args },
        );
    } else if (std.mem.eql(u8, format, "jsonl") or std.mem.eql(u8, format, "ndjson")) {
        // JSONL/NDJSON - just curl directly
        shell_cmd = try std.fmt.allocPrint(
            allocator,
            "curl -sS -L -f{s} '{s}'",
            .{ header_arg, escaped_url },
        );
    } else {
        jn_core.exitWithError("jn-cat: format plugin '{s}' not found", .{format});
    }
    defer allocator.free(shell_cmd);

    // Run via shell
    const shell_argv: [3][]const u8 = .{ "/bin/sh", "-c", shell_cmd };
    var shell_child = std.process.Child.init(&shell_argv, allocator);
    shell_child.stdin_behavior = .Close;
    shell_child.stdout_behavior = .Inherit;
    shell_child.stderr_behavior = .Inherit;

    try shell_child.spawn();
    const result = shell_child.wait() catch |err| {
        jn_core.exitWithError("jn-cat: URL fetch failed: {s}", .{@errorName(err)});
    };

    switch (result) {
        .Exited => |code| {
            if (code != 0) {
                // curl exit codes: 22 = HTTP error (4xx/5xx), 6 = couldn't resolve host
                if (code == 22) {
                    jn_core.exitWithError("jn-cat: HTTP error fetching URL: {s}", .{url});
                } else if (code == 6) {
                    jn_core.exitWithError("jn-cat: could not resolve host for URL: {s}", .{url});
                } else {
                    std.process.exit(code);
                }
            }
        },
        else => {
            std.process.exit(1);
        },
    }
}

/// Handle glob pattern - expand and process each file
fn handleGlob(allocator: std.mem.Allocator, address: jn_address.Address, args: *const jn_cli.ArgParser) !void {
    const pattern = address.path;
    const format = address.effectiveFormat();
    const inject_meta = args.has("meta") or args.has("inject-meta");

    // Build shell command for glob expansion
    // For ** patterns, use find; for simple globs, use bash globstar
    var expand_cmd: []const u8 = undefined;

    if (std.mem.indexOf(u8, pattern, "**") != null) {
        // Use find for recursive patterns - convert ** to -name pattern
        // Split pattern into base dir and file pattern
        // e.g., "test_data/**/*.jsonl" -> find test_data -name "*.jsonl"
        const last_slash = std.mem.lastIndexOf(u8, pattern, "/") orelse 0;
        const base_dir = if (last_slash > 0) pattern[0..last_slash] else ".";
        var file_pattern = pattern[last_slash + 1 ..];

        // Strip **/ prefix from file pattern
        while (std.mem.startsWith(u8, file_pattern, "**/")) {
            file_pattern = file_pattern[3..];
        }
        if (std.mem.startsWith(u8, file_pattern, "**")) {
            file_pattern = file_pattern[2..];
        }

        // Extract the base directory (before any **)
        var dir_to_search = base_dir;
        if (std.mem.indexOf(u8, base_dir, "**")) |double_star| {
            dir_to_search = if (double_star > 0) base_dir[0 .. double_star - 1] else ".";
        }

        // SECURITY: Escape directory and file pattern to prevent shell injection
        const escaped_dir = try escapeShellPath(allocator, dir_to_search);
        defer if (escaped_dir.ptr != dir_to_search.ptr) allocator.free(@constCast(escaped_dir));
        const escaped_file_pattern = try escapeShellPath(allocator, file_pattern);
        defer if (escaped_file_pattern.ptr != file_pattern.ptr) allocator.free(@constCast(escaped_file_pattern));

        // Use find with -name pattern
        expand_cmd = std.fmt.allocPrint(
            allocator,
            "find '{s}' -type f -name '{s}' 2>/dev/null | sort",
            .{ escaped_dir, escaped_file_pattern },
        ) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    } else {
        // Simple glob - use bash with globstar
        // SECURITY: Validate pattern contains only safe characters for unquoted glob expansion
        // We cannot quote the pattern (glob chars wouldn't expand), so we must reject unsafe patterns
        if (!jn_core.isGlobPatternSafe(pattern)) {
            jn_core.exitWithError("jn-cat: glob pattern contains unsafe characters: {s}", .{pattern});
        }

        expand_cmd = std.fmt.allocPrint(
            allocator,
            "shopt -s nullglob; for f in {s}; do [ -f \"$f\" ] && echo \"$f\"; done",
            .{pattern},
        ) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    }
    defer allocator.free(expand_cmd);

    // Use bash for better glob support
    const expand_argv: [3][]const u8 = .{ "/bin/bash", "-c", expand_cmd };
    var expand_child = std.process.Child.init(&expand_argv, allocator);
    expand_child.stdin_behavior = .Close;
    expand_child.stdout_behavior = .Pipe;
    expand_child.stderr_behavior = .Inherit;

    try expand_child.spawn();

    // Read file list from stdout
    const stdout_pipe = expand_child.stdout.?;
    var file_count: usize = 0;

    var reader_buf: [4096]u8 = undefined;
    var reader_wrapper = stdout_pipe.reader(&reader_buf);
    const reader = &reader_wrapper.interface;
    while (jn_core.readLine(reader)) |line| {
        const file_path = std.mem.trim(u8, line, " \t\r\n");
        if (file_path.len == 0) continue;

        // Process this file
        try processGlobFile(allocator, file_path, format, args, file_count, inject_meta);
        file_count += 1;
    }

    _ = expand_child.wait() catch {};

    if (file_count == 0) {
        jn_core.exitWithError("jn-cat: no files match pattern: {s}", .{pattern});
    }
}

/// Process a single file from glob expansion
fn processGlobFile(allocator: std.mem.Allocator, file_path: []const u8, format: ?[]const u8, args: *const jn_cli.ArgParser, file_index: usize, inject_meta: bool) !void {
    // Determine format from file extension if not specified
    var effective_format: []const u8 = "jsonl";
    var compression: jn_address.Compression = .none;

    // Check for compression
    const compression_exts = [_][]const u8{ ".gz", ".bz2", ".xz", ".zst" };
    var path_for_format = file_path;
    for (compression_exts) |ext| {
        if (std.mem.endsWith(u8, file_path, ext)) {
            compression = jn_address.Compression.fromExtension(ext);
            path_for_format = file_path[0 .. file_path.len - ext.len];
            break;
        }
    }

    // Get format from extension
    if (format) |f| {
        effective_format = f;
    } else if (std.mem.lastIndexOf(u8, path_for_format, ".")) |dot_pos| {
        const ext = path_for_format[dot_pos + 1 ..];
        if (ext.len > 0 and ext.len <= 10) {
            effective_format = ext;
        }
    }

    // For JSONL with metadata injection, handle specially (before plugin lookup)
    const is_jsonl = std.mem.eql(u8, effective_format, "jsonl") or std.mem.eql(u8, effective_format, "ndjson");
    if (is_jsonl and inject_meta and compression == .none) {
        try outputWithMeta(allocator, file_path, file_index);
        return;
    }

    // Find format plugin (including Python plugins)
    const plugin_info = findPluginInfo(allocator, effective_format);

    // Build format args (dynamically allocated, properly escaped)
    const format_args = try buildFormatArgs(allocator, args);
    defer allocator.free(format_args);

    // SECURITY: Escape the file path to prevent command injection
    const escaped_file_path = try escapeShellPath(allocator, file_path);
    defer if (escaped_file_path.ptr != file_path.ptr) allocator.free(@constCast(escaped_file_path));

    // Build the pipeline command
    var shell_cmd: []const u8 = undefined;

    if (compression != .none) {
        const gz_path = findPlugin(allocator, "gz") orelse {
            jn_core.exitWithError("jn-cat: compression plugin 'gz' not found", .{});
        };

        if (plugin_info) |info| {
            if (info.plugin_type == .python) {
                // Python plugin with compression
                shell_cmd = try std.fmt.allocPrint(
                    allocator,
                    "cat '{s}' | {s} --mode=raw | uv run --script {s} --mode=read{s}",
                    .{ escaped_file_path, gz_path, info.path, format_args },
                );
            } else {
                shell_cmd = try std.fmt.allocPrint(
                    allocator,
                    "cat '{s}' | {s} --mode=raw | {s} --mode=read{s}",
                    .{ escaped_file_path, gz_path, info.path, format_args },
                );
            }
        } else {
            shell_cmd = try std.fmt.allocPrint(
                allocator,
                "cat '{s}' | {s} --mode=raw",
                .{ escaped_file_path, gz_path },
            );
        }
    } else if (plugin_info) |info| {
        if (info.plugin_type == .python) {
            // Python plugin
            shell_cmd = try std.fmt.allocPrint(
                allocator,
                "cat '{s}' | uv run --script {s} --mode=read{s}",
                .{ escaped_file_path, info.path, format_args },
            );
        } else {
            shell_cmd = try std.fmt.allocPrint(
                allocator,
                "cat '{s}' | {s} --mode=read{s}",
                .{ escaped_file_path, info.path, format_args },
            );
        }
    } else if (std.mem.eql(u8, effective_format, "jsonl") or std.mem.eql(u8, effective_format, "ndjson")) {
        // JSONL without metadata injection (inject_meta case handled earlier)
        shell_cmd = try std.fmt.allocPrint(allocator, "cat '{s}'", .{escaped_file_path});
    } else {
        jn_core.exitWithError("jn-cat: format plugin '{s}' not found", .{effective_format});
    }
    defer allocator.free(shell_cmd);

    // Run the pipeline
    const shell_argv: [3][]const u8 = .{ "/bin/sh", "-c", shell_cmd };
    var child = std.process.Child.init(&shell_argv, allocator);
    child.stdin_behavior = .Close;
    child.stdout_behavior = .Inherit;
    child.stderr_behavior = .Inherit;

    try child.spawn();
    const result = child.wait() catch |err| {
        jn_core.exitWithError("jn-cat: failed to process file '{s}': {s}", .{ file_path, @errorName(err) });
    };

    switch (result) {
        .Exited => |code| {
            if (code != 0) {
                // Continue with other files, don't fail
            }
        },
        else => {},
    }
}

/// Output JSONL file with path metadata injected
fn outputWithMeta(allocator: std.mem.Allocator, file_path: []const u8, file_index: usize) !void {
    const file = std.fs.cwd().openFile(file_path, .{}) catch |err| {
        std.debug.print("jn-cat: cannot open '{s}': {s}\n", .{ file_path, @errorName(err) });
        return;
    };
    defer file.close();

    // Parse path components
    const dirname = std.fs.path.dirname(file_path) orelse ".";
    const filename = std.fs.path.basename(file_path);
    const ext_start = std.mem.lastIndexOf(u8, filename, ".") orelse filename.len;
    const basename = filename[0..ext_start];
    const ext = if (ext_start < filename.len) filename[ext_start..] else "";

    var stdout_buf: [8192]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&stdout_buf);
    const stdout = &stdout_wrapper.interface;
    var line_index: usize = 0;
    var reader_buf: [65536]u8 = undefined;
    var reader_wrapper = file.reader(&reader_buf);
    const reader = &reader_wrapper.interface;

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;

        // Parse JSON and inject metadata
        // For simplicity, just prepend metadata fields to the JSON object
        if (line[0] == '{' and line[line.len - 1] == '}') {
            // Insert metadata at start of object
            const meta = try std.fmt.allocPrint(allocator, "\"_path\":\"{s}\",\"_dir\":\"{s}\",\"_filename\":\"{s}\",\"_basename\":\"{s}\",\"_ext\":\"{s}\",\"_file_index\":{d},\"_line_index\":{d},", .{
                file_path,
                dirname,
                filename,
                basename,
                ext,
                file_index,
                line_index,
            });
            defer allocator.free(meta);

            stdout.print("{{{s}{s}\n", .{ meta, line[1..] }) catch |err| {
                jn_core.handleWriteError(err);
            };
            jn_core.flushWriter(stdout);
        } else {
            // Not a JSON object, output as-is
            stdout.print("{s}\n", .{line}) catch |err| {
                jn_core.handleWriteError(err);
            };
            jn_core.flushWriter(stdout);
        }
        line_index += 1;
    }
    jn_core.flushWriter(stdout);
}

/// Handle cloud storage URLs using OpenDAL plugin (s3://, gs://, gcs://, gdrive://)
fn handleOpenDalUrl(allocator: std.mem.Allocator, address: jn_address.Address, args: *const jn_cli.ArgParser) !void {
    const format = address.effectiveFormat() orelse "jsonl"; // Default to JSONL for cloud storage

    // Find OpenDAL plugin
    const opendal_path = findPlugin(allocator, "opendal") orelse {
        jn_core.exitWithError("jn-cat: OpenDAL plugin not found\nHint: build with 'make zig-opendal'", .{});
    };

    // Find format plugin if needed
    const format_path = findPlugin(allocator, format);

    // Build format args (dynamically allocated, properly escaped)
    const format_args = try buildFormatArgs(allocator, args);
    defer allocator.free(format_args);

    // Build the shell command
    // Set LD_LIBRARY_PATH for OpenDAL shared library
    var shell_cmd: []const u8 = undefined;

    // Get JN_HOME for library path
    const jn_home = std.posix.getenv("JN_HOME") orelse ".";
    const lib_path = try std.fmt.allocPrint(allocator, "{s}/vendor/opendal/bindings/c/target/release", .{jn_home});
    defer allocator.free(lib_path);

    // SECURITY: Escape address.raw to prevent shell injection via malicious URLs
    const escaped_address = try escapeShellPath(allocator, address.raw);
    const needs_free = escaped_address.ptr != address.raw.ptr;
    defer if (needs_free) allocator.free(@constCast(escaped_address));

    if (address.compression != .none) {
        const gz_path = findPlugin(allocator, "gz") orelse {
            jn_core.exitWithError("jn-cat: compression plugin 'gz' not found", .{});
        };

        if (format_path) |fmt_path| {
            shell_cmd = try std.fmt.allocPrint(
                allocator,
                "LD_LIBRARY_PATH='{s}' {s} '{s}' | {s} --mode=raw | {s} --mode=read{s}",
                .{ lib_path, opendal_path, escaped_address, gz_path, fmt_path, format_args },
            );
        } else {
            shell_cmd = try std.fmt.allocPrint(
                allocator,
                "LD_LIBRARY_PATH='{s}' {s} '{s}' | {s} --mode=raw",
                .{ lib_path, opendal_path, escaped_address, gz_path },
            );
        }
    } else if (format_path) |fmt_path| {
        shell_cmd = try std.fmt.allocPrint(
            allocator,
            "LD_LIBRARY_PATH='{s}' {s} '{s}' | {s} --mode=read{s}",
            .{ lib_path, opendal_path, escaped_address, fmt_path, format_args },
        );
    } else if (std.mem.eql(u8, format, "jsonl") or std.mem.eql(u8, format, "ndjson")) {
        shell_cmd = try std.fmt.allocPrint(
            allocator,
            "LD_LIBRARY_PATH='{s}' {s} '{s}'",
            .{ lib_path, opendal_path, escaped_address },
        );
    } else {
        jn_core.exitWithError("jn-cat: format plugin '{s}' not found", .{format});
    }
    defer allocator.free(shell_cmd);

    // Run via shell
    const shell_argv: [3][]const u8 = .{ "/bin/sh", "-c", shell_cmd };
    var shell_child = std.process.Child.init(&shell_argv, allocator);
    shell_child.stdin_behavior = .Close;
    shell_child.stdout_behavior = .Inherit;
    shell_child.stderr_behavior = .Inherit;

    try shell_child.spawn();
    const result = shell_child.wait() catch |err| {
        jn_core.exitWithError("jn-cat: OpenDAL execution failed: {s}", .{@errorName(err)});
    };

    switch (result) {
        .Exited => |code| {
            if (code != 0) {
                std.process.exit(code);
            }
        },
        else => {
            std.process.exit(1);
        },
    }
}

/// Spawn a format plugin to read a file
fn spawnFormatPlugin(allocator: std.mem.Allocator, format: []const u8, file_path: ?[]const u8, query_string: ?[]const u8, args: *const jn_cli.ArgParser) !void {
    const plugin_info = findPluginInfo(allocator, format) orelse {
        jn_core.exitWithError("jn-cat: format plugin '{s}' not found", .{format});
    };

    // Build format args from CLI (dynamically allocated, properly escaped)
    const format_args = try buildFormatArgs(allocator, args);
    defer allocator.free(format_args);

    // Build query args from query string
    const query_args = try buildQueryArgs(allocator, query_string);
    defer allocator.free(query_args);

    // Combine format_args and query_args
    const all_args = try std.fmt.allocPrint(allocator, "{s}{s}", .{ format_args, query_args });
    defer allocator.free(all_args);

    // Extract mode from query string (defaults to "read")
    const mode = extractModeFromQuery(query_string);

    // Handle Python plugins via uv run --script
    if (plugin_info.plugin_type == .python) {
        try spawnPythonPlugin(allocator, plugin_info.path, mode, file_path, all_args);
        return;
    }

    // Zig plugin handling
    const plugin_path = plugin_info.path;

    // Build argument list (fixed array with max args)
    var argv_buf: [5][]const u8 = undefined;
    var argc: usize = 0;

    // Build mode arg
    var mode_arg_buf: [32]u8 = undefined;
    const mode_arg = std.fmt.bufPrint(&mode_arg_buf, "--mode={s}", .{mode}) catch {
        jn_core.exitWithError("jn-cat: mode name too long", .{});
    };

    argv_buf[argc] = plugin_path;
    argc += 1;
    argv_buf[argc] = mode_arg;
    argc += 1;

    // Allocate delimiter arg if needed
    var delim_arg_buf: [32]u8 = undefined;
    if (args.get("delimiter", null)) |delim| {
        const written = std.fmt.bufPrint(&delim_arg_buf, "--delimiter={s}", .{delim}) catch {
            jn_core.exitWithError("jn-cat: delimiter too long", .{});
        };
        argv_buf[argc] = written;
        argc += 1;
    }
    if (args.has("no-header")) {
        argv_buf[argc] = "--no-header";
        argc += 1;
    }

    const argv = argv_buf[0..argc];

    // Spawn the plugin
    var child = std.process.Child.init(argv, allocator);

    if (file_path) |path| {
        // Verify file exists
        std.fs.cwd().access(path, .{}) catch |err| {
            jn_core.exitWithError("jn-cat: cannot open file '{s}': {s}", .{ path, @errorName(err) });
        };

        // SECURITY: Escape the file path to prevent command injection
        const escaped_path = try escapeShellPath(allocator, path);
        defer if (escaped_path.ptr != path.ptr) allocator.free(@constCast(escaped_path));

        // Use shell to pipe file into plugin with all args
        const shell_cmd = try std.fmt.allocPrint(allocator, "cat '{s}' | {s} --mode={s}{s}", .{ escaped_path, plugin_path, mode, all_args });
        defer allocator.free(shell_cmd);

        const shell_argv: [3][]const u8 = .{ "/bin/sh", "-c", shell_cmd };
        var shell_child = std.process.Child.init(&shell_argv, allocator);
        shell_child.stdin_behavior = .Close;
        shell_child.stdout_behavior = .Inherit;
        shell_child.stderr_behavior = .Inherit;

        try shell_child.spawn();
        const result = shell_child.wait() catch |err| {
            jn_core.exitWithError("jn-cat: plugin execution failed: {s}", .{@errorName(err)});
        };

        switch (result) {
            .Exited => |code| if (code != 0) std.process.exit(code),
            .Signal => |sig| std.process.exit(128 +| @as(u8, @intCast(@min(sig, 127)))),
            .Stopped, .Unknown => std.process.exit(1),
        }
    } else {
        // Use our stdin directly
        child.stdin_behavior = .Inherit;
        child.stdout_behavior = .Inherit;
        child.stderr_behavior = .Inherit;

        try child.spawn();
        const result = child.wait() catch |err| {
            jn_core.exitWithError("jn-cat: plugin execution failed: {s}", .{@errorName(err)});
        };

        switch (result) {
            .Exited => |code| if (code != 0) std.process.exit(code),
            .Signal => |sig| std.process.exit(128 +| @as(u8, @intCast(@min(sig, 127)))),
            .Stopped, .Unknown => std.process.exit(1),
        }
    }
}

/// Spawn a Python plugin via uv run --script
fn spawnPythonPlugin(allocator: std.mem.Allocator, plugin_path: []const u8, mode: []const u8, file_path: ?[]const u8, extra_args: []const u8) !void {
    // SECURITY: Escape paths to prevent command injection
    const escaped_plugin_path = try escapeShellPath(allocator, plugin_path);
    defer if (escaped_plugin_path.ptr != plugin_path.ptr) allocator.free(@constCast(escaped_plugin_path));

    var shell_cmd: []u8 = undefined;

    if (file_path) |path| {
        const escaped_file_path = try escapeShellPath(allocator, path);
        defer if (escaped_file_path.ptr != path.ptr) allocator.free(@constCast(escaped_file_path));

        // Pipe file into plugin: cat <file> | uv run --script <plugin> --mode=<mode> [args]
        shell_cmd = std.fmt.allocPrint(allocator, "cat '{s}' | uv run --script '{s}' --mode={s}{s}", .{ escaped_file_path, escaped_plugin_path, mode, extra_args }) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    } else {
        // Use stdin: uv run --script <plugin> --mode=<mode> [args]
        shell_cmd = std.fmt.allocPrint(allocator, "uv run --script '{s}' --mode={s}{s}", .{ escaped_plugin_path, mode, extra_args }) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    }
    defer allocator.free(shell_cmd);

    // Run via shell
    const shell_argv: [3][]const u8 = .{ "/bin/sh", "-c", shell_cmd };
    var shell_child = std.process.Child.init(&shell_argv, allocator);
    shell_child.stdin_behavior = if (file_path != null) .Close else .Inherit;
    shell_child.stdout_behavior = .Inherit;
    shell_child.stderr_behavior = .Inherit;

    try shell_child.spawn();
    const result = shell_child.wait() catch |err| {
        jn_core.exitWithError("jn-cat: Python plugin execution failed: {s}", .{@errorName(err)});
    };

    switch (result) {
        .Exited => |code| {
            if (code != 0) {
                std.process.exit(code);
            }
        },
        else => {
            std.process.exit(1);
        },
    }
}

/// Plugin type (Zig binary or Python script)
const PluginType = enum { zig, python };

/// Plugin info including path and type
const PluginInfo = struct {
    path: []const u8,
    plugin_type: PluginType,
};

/// Format to Python plugin filename mapping
const FORMAT_TO_PYTHON = [_]struct { format: []const u8, plugin: []const u8 }{
    .{ .format = "xlsx", .plugin = "xlsx_.py" },
    .{ .format = "xlsm", .plugin = "xlsx_.py" },
    .{ .format = "md", .plugin = "markdown_.py" },
    .{ .format = "markdown", .plugin = "markdown_.py" },
    .{ .format = "xml", .plugin = "xml_.py" },
    .{ .format = "lcov", .plugin = "lcov_.py" },
    .{ .format = "info", .plugin = "lcov_.py" }, // .info is LCOV format
    .{ .format = "table", .plugin = "table_.py" },
};

/// Find a plugin by name (returns Zig plugin path or null)
fn findPlugin(allocator: std.mem.Allocator, name: []const u8) ?[]const u8 {
    const info = findPluginInfo(allocator, name);
    if (info) |i| {
        if (i.plugin_type == .zig) {
            return i.path;
        }
    }
    return null;
}

/// Find a plugin by name, including Python plugins
fn findPluginInfo(allocator: std.mem.Allocator, name: []const u8) ?PluginInfo {
    // Try Zig plugins first (higher priority)

    // Try paths relative to JN_HOME
    if (std.posix.getenv("JN_HOME")) |jn_home| {
        // Try installed layout: $JN_HOME/bin/{name}
        const installed_path = std.fmt.allocPrint(allocator, "{s}/bin/{s}", .{ jn_home, name }) catch return null;
        if (std.fs.cwd().access(installed_path, .{})) |_| {
            return .{ .path = installed_path, .plugin_type = .zig };
        } else |_| {
            allocator.free(installed_path);
        }

        // Try development layout: $JN_HOME/plugins/zig/{name}/bin/{name}
        const path = std.fmt.allocPrint(allocator, "{s}/plugins/zig/{s}/bin/{s}", .{ jn_home, name, name }) catch return null;
        if (std.fs.cwd().access(path, .{})) |_| {
            return .{ .path = path, .plugin_type = .zig };
        } else |_| {
            allocator.free(path);
        }
    }

    // Try sibling to executable (installed layout: binaries in same directory)
    var exe_path_buf2: [std.fs.max_path_bytes]u8 = undefined;
    if (std.fs.selfExePath(&exe_path_buf2)) |exe_path| {
        if (std.fs.path.dirname(exe_path)) |exe_dir| {
            const sibling_path = std.fmt.allocPrint(allocator, "{s}/{s}", .{ exe_dir, name }) catch return null;
            if (std.fs.cwd().access(sibling_path, .{})) |_| {
                return .{ .path = sibling_path, .plugin_type = .zig };
            } else |_| {
                allocator.free(sibling_path);
            }
        }
    } else |_| {}

    // Try relative to current directory (development mode)
    const dev_path = std.fmt.allocPrint(allocator, "plugins/zig/{s}/bin/{s}", .{ name, name }) catch return null;
    if (std.fs.cwd().access(dev_path, .{})) |_| {
        return .{ .path = dev_path, .plugin_type = .zig };
    } else |_| {
        allocator.free(dev_path);
    }

    // Try relative to executable's location
    // Executable is at: /path/to/jn/tools/zig/jn-cat/bin/jn-cat
    // Plugins are at: /path/to/jn/plugins/zig/<name>/bin/<name>
    var exe_path_buf: [std.fs.max_path_bytes]u8 = undefined;
    if (std.fs.selfExePath(&exe_path_buf)) |exe_path| {
        // Go up 5 levels: bin -> jn-cat -> zig -> tools -> root
        var dir = std.fs.path.dirname(exe_path);
        var i: usize = 0;
        while (i < 4 and dir != null) : (i += 1) {
            dir = std.fs.path.dirname(dir.?);
        }
        if (dir) |root| {
            const exe_rel_path = std.fmt.allocPrint(allocator, "{s}/plugins/zig/{s}/bin/{s}", .{ root, name, name }) catch return null;
            if (std.fs.cwd().access(exe_rel_path, .{})) |_| {
                return .{ .path = exe_rel_path, .plugin_type = .zig };
            } else |_| {
                allocator.free(exe_rel_path);
            }
        }
    } else |_| {}

    // Try ~/.local/jn/plugins
    if (std.posix.getenv("HOME")) |home| {
        const user_path = std.fmt.allocPrint(allocator, "{s}/.local/jn/plugins/zig/{s}/bin/{s}", .{ home, name, name }) catch return null;
        if (std.fs.cwd().access(user_path, .{})) |_| {
            return .{ .path = user_path, .plugin_type = .zig };
        } else |_| {
            allocator.free(user_path);
        }
    }

    // Try Python plugins (lower priority)
    if (findPythonPlugin(allocator, name)) |py_path| {
        return .{ .path = py_path, .plugin_type = .python };
    }

    return null;
}

/// Find a Python plugin by format name
fn findPythonPlugin(allocator: std.mem.Allocator, format: []const u8) ?[]const u8 {
    // Map format to plugin filename
    var plugin_name: ?[]const u8 = null;
    for (FORMAT_TO_PYTHON) |mapping| {
        if (std.mem.eql(u8, format, mapping.format)) {
            plugin_name = mapping.plugin;
            break;
        }
    }

    if (plugin_name == null) return null;

    const subdirs = [_][]const u8{ "formats", "protocols", "databases", "filters", "shell" };

    // Try JN_HOME first
    if (std.posix.getenv("JN_HOME")) |jn_home| {
        for (subdirs) |subdir| {
            const path = std.fmt.allocPrint(allocator, "{s}/jn_home/plugins/{s}/{s}", .{ jn_home, subdir, plugin_name.? }) catch continue;
            if (std.fs.cwd().access(path, .{})) |_| {
                return path;
            } else |_| {
                allocator.free(path);
            }
        }
    }

    // Try sibling to executable (libexec layout: jn_home is sibling in same dir)
    var exe_path_buf: [std.fs.max_path_bytes]u8 = undefined;
    if (std.fs.selfExePath(&exe_path_buf)) |exe_path| {
        if (std.fs.path.dirname(exe_path)) |exe_dir| {
            for (subdirs) |subdir| {
                const path = std.fmt.allocPrint(allocator, "{s}/jn_home/plugins/{s}/{s}", .{ exe_dir, subdir, plugin_name.? }) catch continue;
                if (std.fs.cwd().access(path, .{})) |_| {
                    return path;
                } else |_| {
                    allocator.free(path);
                }
            }
        }
    } else |_| {}

    // Try legacy layout (jn_home one level up from bin/)
    if (std.fs.selfExePath(&exe_path_buf)) |exe_path| {
        if (std.fs.path.dirname(exe_path)) |bin_dir| {
            if (std.fs.path.dirname(bin_dir)) |dist_dir| {
                for (subdirs) |subdir| {
                    const path = std.fmt.allocPrint(allocator, "{s}/jn_home/plugins/{s}/{s}", .{ dist_dir, subdir, plugin_name.? }) catch continue;
                    if (std.fs.cwd().access(path, .{})) |_| {
                        return path;
                    } else |_| {
                        allocator.free(path);
                    }
                }
            }
        }
    } else |_| {}

    // Try relative to executable (development layout)
    if (std.fs.selfExePath(&exe_path_buf)) |exe_path| {
        // Go up 4 levels: bin -> tool -> zig -> tools -> root
        var dir = std.fs.path.dirname(exe_path);
        var i: usize = 0;
        while (i < 4 and dir != null) : (i += 1) {
            dir = std.fs.path.dirname(dir.?);
        }
        if (dir) |root| {
            for (subdirs) |subdir| {
                const path = std.fmt.allocPrint(allocator, "{s}/jn_home/plugins/{s}/{s}", .{ root, subdir, plugin_name.? }) catch continue;
                if (std.fs.cwd().access(path, .{})) |_| {
                    return path;
                } else |_| {
                    allocator.free(path);
                }
            }
        }
    } else |_| {}

    // Try ~/.local/jn
    if (std.posix.getenv("HOME")) |home| {
        for (subdirs) |subdir| {
            const path = std.fmt.allocPrint(allocator, "{s}/.local/jn/plugins/{s}/{s}", .{ home, subdir, plugin_name.? }) catch continue;
            if (std.fs.cwd().access(path, .{})) |_| {
                return path;
            } else |_| {
                allocator.free(path);
            }
        }
    }

    return null;
}

/// Pass stdin through to stdout (for JSONL)
fn passthroughStdin() !void {
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);
    const reader = &stdin_wrapper.interface;

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    while (jn_core.readLine(reader)) |line| {
        if (line.len == 0) continue;
        writer.writeAll(line) catch |err| jn_core.handleWriteError(err);
        writer.writeByte('\n') catch |err| jn_core.handleWriteError(err);
    }

    jn_core.flushWriter(writer);
}

/// Print version
fn printVersion() void {
    var buf: [256]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.print("jn-cat {s}\n", .{VERSION}) catch {};
    jn_core.flushWriter(stdout);
}

/// Print usage information
fn printUsage() void {
    const usage =
        \\jn-cat - Universal reader for JN
        \\
        \\Usage: jn-cat [OPTIONS] <ADDRESS>
        \\
        \\Address formats:
        \\  data.csv              Local file (format auto-detected)
        \\  data.csv.gz           Compressed file (decompressed automatically)
        \\  data.txt~csv          Format override
        \\  -                     Read from stdin
        \\
        \\Options:
        \\  --help, -h            Show this help
        \\  --version             Show version
        \\  --delimiter=CHAR      CSV delimiter (passed to plugin)
        \\  --no-header           CSV has no header row (passed to plugin)
        \\
        \\Examples:
        \\  jn-cat data.csv
        \\  jn-cat data.csv.gz
        \\  jn-cat data.txt~csv
        \\  jn-cat - < data.csv
        \\  jn-cat --delimiter=';' data.csv
        \\
    ;
    var buf: [2048]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writerStreaming(&buf);
    const stdout = &stdout_wrapper.interface;
    stdout.writeAll(usage) catch {};
    jn_core.flushWriter(stdout);
}

// Tests
test "parse simple file address" {
    const addr = jn_address.parse("data.csv");
    try std.testing.expectEqual(jn_address.AddressType.file, addr.address_type);
    try std.testing.expectEqualStrings("csv", addr.effectiveFormat().?);
}

test "parse compressed file address" {
    const addr = jn_address.parse("data.csv.gz");
    try std.testing.expectEqual(jn_address.AddressType.file, addr.address_type);
    try std.testing.expectEqual(jn_address.Compression.gzip, addr.compression);
    try std.testing.expectEqualStrings("csv", addr.effectiveFormat().?);
}

test "parse stdin address" {
    const addr = jn_address.parse("-");
    try std.testing.expectEqual(jn_address.AddressType.stdin, addr.address_type);
}

test "parse format override" {
    const addr = jn_address.parse("data.txt~csv");
    try std.testing.expectEqual(jn_address.AddressType.file, addr.address_type);
    try std.testing.expectEqualStrings("csv", addr.effectiveFormat().?);
}
