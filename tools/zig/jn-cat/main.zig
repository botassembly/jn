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
    try spawnFormatPlugin(allocator, format, null, args);
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
    try spawnFormatPlugin(allocator, format, address.path, args);
}

/// Build format plugin argument string for shell commands
fn buildFormatArgs(args: *const jn_cli.ArgParser, buf: []u8) []const u8 {
    var pos: usize = 0;

    if (args.get("delimiter", null)) |delim| {
        // Quote the delimiter value for shell safety
        const written = std.fmt.bufPrint(buf[pos..], " --delimiter='{s}'", .{delim}) catch return buf[0..pos];
        pos += written.len;
    }
    if (args.has("no-header")) {
        const written = std.fmt.bufPrint(buf[pos..], " --no-header", .{}) catch return buf[0..pos];
        pos += written.len;
    }

    return buf[0..pos];
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

    // Build format args
    var format_args_buf: [64]u8 = undefined;
    const format_args = buildFormatArgs(args, &format_args_buf);

    // Use shell to construct pipeline: cat file | gz --mode=raw | format --mode=read [args]
    const shell_cmd = try std.fmt.allocPrint(
        allocator,
        "cat '{s}' | {s} --mode=raw | {s} --mode=read{s}",
        .{ address.path, gz_path, format_path, format_args },
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

    if (result.Exited != 0) {
        std.process.exit(result.Exited);
    }
}

/// Handle profile reference (@namespace/name)
fn handleProfile(allocator: std.mem.Allocator, address: jn_address.Address, args: *const jn_cli.ArgParser) !void {
    const namespace = address.profile_namespace orelse {
        jn_core.exitWithError("jn-cat: profile reference requires namespace: @namespace/name\nAddress: {s}", .{address.raw});
    };
    const name = address.profile_name orelse {
        jn_core.exitWithError("jn-cat: profile reference requires name: @namespace/name\nAddress: {s}", .{address.raw});
    };

    // Get profile directories
    const profile_dirs = jn_profile.getProfileDirs(allocator, .{
        .project_root = null, // TODO: detect project root
        .home_dir = jn_profile.getHomeDir(),
        .jn_home = jn_profile.getJnHome(),
    }) catch {
        jn_core.exitWithError("jn-cat: failed to get profile directories", .{});
    };
    defer {
        for (profile_dirs) |d| allocator.free(d);
        allocator.free(profile_dirs);
    }

    // Search for profile in each directory (http type for now)
    // Profile path: <profile_dir>/http/<namespace>/<name>.json
    var profile_file: ?[]const u8 = null;
    var profile_dir: ?[]const u8 = null;

    for (profile_dirs) |dir| {
        const path = std.fmt.allocPrint(allocator, "{s}/http/{s}/{s}.json", .{ dir, namespace, name }) catch continue;
        if (jn_profile.pathExists(path)) {
            profile_file = path;
            profile_dir = std.fmt.allocPrint(allocator, "{s}/http/{s}", .{ dir, namespace }) catch {
                allocator.free(path);
                continue;
            };
            break;
        } else {
            allocator.free(path);
        }
    }

    if (profile_file == null or profile_dir == null) {
        jn_core.exitWithError("jn-cat: profile not found: @{s}/{s}\nSearched: profiles/http/{s}/{s}.json", .{ namespace, name, namespace, name });
    }
    defer allocator.free(profile_file.?);
    defer allocator.free(profile_dir.?);

    // Load profile with hierarchical merge
    const profile_path = std.fmt.allocPrint(allocator, "{s}.json", .{name}) catch {
        jn_core.exitWithError("jn-cat: out of memory", .{});
    };
    defer allocator.free(profile_path);

    var config = jn_profile.loadProfile(allocator, profile_dir.?, profile_path, true) catch |err| {
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
    var full_url: []const u8 = undefined;
    if (path_str.len > 0) {
        full_url = std.fmt.allocPrint(allocator, "{s}{s}", .{ base_url.?, path_str }) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    } else {
        full_url = std.fmt.allocPrint(allocator, "{s}", .{base_url.?}) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    }
    defer allocator.free(full_url);

    // Add query parameters from address
    var url_with_params: []const u8 = undefined;
    if (address.query_string) |qs| {
        url_with_params = std.fmt.allocPrint(allocator, "{s}?{s}", .{ full_url, qs }) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    } else {
        url_with_params = std.fmt.allocPrint(allocator, "{s}", .{full_url}) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    }
    defer allocator.free(url_with_params);

    // Build headers from profile
    var header_args: [512]u8 = undefined;
    var header_len: usize = 0;

    if (config.object.get("headers")) |headers_val| {
        if (headers_val == .object) {
            var iter = headers_val.object.iterator();
            while (iter.next()) |entry| {
                if (entry.value_ptr.* == .string) {
                    const h = std.fmt.bufPrint(header_args[header_len..], " -H '{s}: {s}'", .{ entry.key_ptr.*, entry.value_ptr.string }) catch break;
                    header_len += h.len;
                }
            }
        }
    }

    // Get format (default to json for HTTP profiles)
    const format = address.effectiveFormat() orelse "json";

    // Find format plugin
    const plugin_path = findPlugin(allocator, format);

    // Build format args
    var format_args_buf: [64]u8 = undefined;
    const format_args = buildFormatArgs(args, &format_args_buf);

    // Build curl command with headers
    var shell_cmd: []const u8 = undefined;

    if (plugin_path) |fmt_path| {
        shell_cmd = std.fmt.allocPrint(
            allocator,
            "curl -sS -L -f{s} '{s}' | {s} --mode=read{s}",
            .{ header_args[0..header_len], url_with_params, fmt_path, format_args },
        ) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    } else if (std.mem.eql(u8, format, "jsonl") or std.mem.eql(u8, format, "ndjson") or std.mem.eql(u8, format, "json")) {
        shell_cmd = std.fmt.allocPrint(
            allocator,
            "curl -sS -L -f{s} '{s}'",
            .{ header_args[0..header_len], url_with_params },
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

    // Build the clean URL (protocol://path) without format hint
    const protocol = address.protocol.?;
    const url = try std.fmt.allocPrint(allocator, "{s}://{s}", .{ protocol, address.path });
    defer allocator.free(url);

    // Find format plugin
    const plugin_path = findPlugin(allocator, format);

    // Build format args
    var format_args_buf: [64]u8 = undefined;
    const format_args = buildFormatArgs(args, &format_args_buf);

    // Build header arg if provided
    var header_arg_buf: [256]u8 = undefined;
    var header_arg: []const u8 = "";
    if (args.get("header", null)) |header| {
        header_arg = std.fmt.bufPrint(&header_arg_buf, " -H '{s}'", .{header}) catch "";
    }

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
                .{ header_arg, url, gz_path, fmt_path, format_args },
            );
        } else {
            // No format plugin (assume JSONL) - just decompress
            shell_cmd = try std.fmt.allocPrint(
                allocator,
                "curl -sS -L -f{s} '{s}' | {s} --mode=raw",
                .{ header_arg, url, gz_path },
            );
        }
    } else if (plugin_path) |fmt_path| {
        // curl URL | format_plugin --mode=read
        shell_cmd = try std.fmt.allocPrint(
            allocator,
            "curl -sS -L -f{s} '{s}' | {s} --mode=read{s}",
            .{ header_arg, url, fmt_path, format_args },
        );
    } else if (std.mem.eql(u8, format, "jsonl") or std.mem.eql(u8, format, "ndjson")) {
        // JSONL/NDJSON - just curl directly
        shell_cmd = try std.fmt.allocPrint(
            allocator,
            "curl -sS -L -f{s} '{s}'",
            .{ header_arg, url },
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

        // Use find with -name pattern
        expand_cmd = std.fmt.allocPrint(
            allocator,
            "find {s} -type f -name '{s}' 2>/dev/null | sort",
            .{ dir_to_search, file_pattern },
        ) catch {
            jn_core.exitWithError("jn-cat: out of memory", .{});
        };
    } else {
        // Simple glob - use bash with globstar
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

    // Find format plugin
    const plugin_path = findPlugin(allocator, effective_format);

    // Build format args
    var format_args_buf: [64]u8 = undefined;
    const format_args = buildFormatArgs(args, &format_args_buf);

    // Build the pipeline command
    var shell_cmd: []const u8 = undefined;

    if (compression != .none) {
        const gz_path = findPlugin(allocator, "gz") orelse {
            jn_core.exitWithError("jn-cat: compression plugin 'gz' not found", .{});
        };

        if (plugin_path) |fmt_path| {
            shell_cmd = try std.fmt.allocPrint(
                allocator,
                "cat '{s}' | {s} --mode=raw | {s} --mode=read{s}",
                .{ file_path, gz_path, fmt_path, format_args },
            );
        } else {
            shell_cmd = try std.fmt.allocPrint(
                allocator,
                "cat '{s}' | {s} --mode=raw",
                .{ file_path, gz_path },
            );
        }
    } else if (plugin_path) |fmt_path| {
        shell_cmd = try std.fmt.allocPrint(
            allocator,
            "cat '{s}' | {s} --mode=read{s}",
            .{ file_path, fmt_path, format_args },
        );
    } else if (std.mem.eql(u8, effective_format, "jsonl") or std.mem.eql(u8, effective_format, "ndjson")) {
        // JSONL - if inject_meta, wrap each line; otherwise cat directly
        if (inject_meta) {
            // Wrap with path metadata
            try outputWithMeta(allocator, file_path, file_index);
            return;
        }
        shell_cmd = try std.fmt.allocPrint(allocator, "cat '{s}'", .{file_path});
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
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
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

    // Build format args
    var format_args_buf: [64]u8 = undefined;
    const format_args = buildFormatArgs(args, &format_args_buf);

    // Build the shell command
    // Set LD_LIBRARY_PATH for OpenDAL shared library
    var shell_cmd: []const u8 = undefined;

    // Get JN_HOME for library path
    const jn_home = std.posix.getenv("JN_HOME") orelse ".";
    const lib_path = try std.fmt.allocPrint(allocator, "{s}/vendor/opendal/bindings/c/target/release", .{jn_home});
    defer allocator.free(lib_path);

    if (address.compression != .none) {
        const gz_path = findPlugin(allocator, "gz") orelse {
            jn_core.exitWithError("jn-cat: compression plugin 'gz' not found", .{});
        };

        if (format_path) |fmt_path| {
            shell_cmd = try std.fmt.allocPrint(
                allocator,
                "LD_LIBRARY_PATH='{s}' {s} '{s}' | {s} --mode=raw | {s} --mode=read{s}",
                .{ lib_path, opendal_path, address.raw, gz_path, fmt_path, format_args },
            );
        } else {
            shell_cmd = try std.fmt.allocPrint(
                allocator,
                "LD_LIBRARY_PATH='{s}' {s} '{s}' | {s} --mode=raw",
                .{ lib_path, opendal_path, address.raw, gz_path },
            );
        }
    } else if (format_path) |fmt_path| {
        shell_cmd = try std.fmt.allocPrint(
            allocator,
            "LD_LIBRARY_PATH='{s}' {s} '{s}' | {s} --mode=read{s}",
            .{ lib_path, opendal_path, address.raw, fmt_path, format_args },
        );
    } else if (std.mem.eql(u8, format, "jsonl") or std.mem.eql(u8, format, "ndjson")) {
        shell_cmd = try std.fmt.allocPrint(
            allocator,
            "LD_LIBRARY_PATH='{s}' {s} '{s}'",
            .{ lib_path, opendal_path, address.raw },
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
fn spawnFormatPlugin(allocator: std.mem.Allocator, format: []const u8, file_path: ?[]const u8, args: *const jn_cli.ArgParser) !void {
    const plugin_info = findPluginInfo(allocator, format) orelse {
        jn_core.exitWithError("jn-cat: format plugin '{s}' not found", .{format});
    };

    // Build format args for shell command
    var format_args_buf: [64]u8 = undefined;
    const format_args = buildFormatArgs(args, &format_args_buf);

    // Handle Python plugins via uv run --script
    if (plugin_info.plugin_type == .python) {
        try spawnPythonPlugin(allocator, plugin_info.path, "read", file_path, format_args);
        return;
    }

    // Zig plugin handling
    const plugin_path = plugin_info.path;

    // Build argument list (fixed array with max args)
    var argv_buf: [5][]const u8 = undefined;
    var argc: usize = 0;

    argv_buf[argc] = plugin_path;
    argc += 1;
    argv_buf[argc] = "--mode=read";
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

        // Use shell to pipe file into plugin with all args
        const shell_cmd = try std.fmt.allocPrint(allocator, "cat '{s}' | {s} --mode=read{s}", .{ path, plugin_path, format_args });
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

        if (result.Exited != 0) {
            std.process.exit(result.Exited);
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

        if (result.Exited != 0) {
            std.process.exit(result.Exited);
        }
    }
}

/// Spawn a Python plugin via uv run --script
fn spawnPythonPlugin(allocator: std.mem.Allocator, plugin_path: []const u8, mode: []const u8, file_path: ?[]const u8, extra_args: []const u8) !void {
    var cmd_buf: [2048]u8 = undefined;
    var cmd_len: usize = 0;

    if (file_path) |path| {
        // Pipe file into plugin: cat <file> | uv run --script <plugin> --mode=<mode> [args]
        const base = std.fmt.bufPrint(cmd_buf[cmd_len..], "cat '{s}' | uv run --script '{s}' --mode={s}{s}", .{ path, plugin_path, mode, extra_args }) catch {
            jn_core.exitWithError("jn-cat: command too long", .{});
        };
        cmd_len += base.len;
    } else {
        // Use stdin: uv run --script <plugin> --mode=<mode> [args]
        const base = std.fmt.bufPrint(cmd_buf[cmd_len..], "uv run --script '{s}' --mode={s}{s}", .{ plugin_path, mode, extra_args }) catch {
            jn_core.exitWithError("jn-cat: command too long", .{});
        };
        cmd_len += base.len;
    }

    const shell_cmd = cmd_buf[0..cmd_len];

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
        const path = std.fmt.allocPrint(allocator, "{s}/plugins/zig/{s}/bin/{s}", .{ jn_home, name, name }) catch return null;
        if (std.fs.cwd().access(path, .{})) |_| {
            return .{ .path = path, .plugin_type = .zig };
        } else |_| {
            allocator.free(path);
        }
    }

    // Try relative to current directory (development mode)
    const dev_path = std.fmt.allocPrint(allocator, "plugins/zig/{s}/bin/{s}", .{ name, name }) catch return null;
    if (std.fs.cwd().access(dev_path, .{})) |_| {
        return .{ .path = dev_path, .plugin_type = .zig };
    } else |_| {
        allocator.free(dev_path);
    }

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

    const jn_home = std.posix.getenv("JN_HOME") orelse return null;

    // Search in plugin subdirectories
    const subdirs = [_][]const u8{ "formats", "protocols", "databases", "filters", "shell" };
    for (subdirs) |subdir| {
        const path = std.fmt.allocPrint(allocator, "{s}/jn_home/plugins/{s}/{s}", .{ jn_home, subdir, plugin_name.? }) catch continue;
        if (std.fs.cwd().access(path, .{})) |_| {
            return path;
        } else |_| {
            allocator.free(path);
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
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
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
    var stdout_wrapper = std.fs.File.stdout().writer(&buf);
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
    var stdout_wrapper = std.fs.File.stdout().writer(&buf);
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
