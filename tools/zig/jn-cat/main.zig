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
            jn_core.exitWithError("jn-cat: profile references not yet supported\nAddress: {s}", .{address_str});
        },
        .glob => {
            jn_core.exitWithError("jn-cat: glob patterns not yet supported\nAddress: {s}", .{address_str});
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
    const plugin_path = findPlugin(allocator, format) orelse {
        jn_core.exitWithError("jn-cat: format plugin '{s}' not found", .{format});
    };

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

        // Build format args for shell command
        var format_args_buf: [64]u8 = undefined;
        const format_args = buildFormatArgs(args, &format_args_buf);

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

/// Find a plugin by name
fn findPlugin(allocator: std.mem.Allocator, name: []const u8) ?[]const u8 {
    // Try paths relative to JN_HOME
    if (std.posix.getenv("JN_HOME")) |jn_home| {
        const path = std.fmt.allocPrint(allocator, "{s}/plugins/zig/{s}/bin/{s}", .{ jn_home, name, name }) catch return null;
        if (std.fs.cwd().access(path, .{})) |_| {
            return path;
        } else |_| {}
    }

    // Try relative to current directory (development mode)
    const dev_path = std.fmt.allocPrint(allocator, "plugins/zig/{s}/bin/{s}", .{ name, name }) catch return null;
    if (std.fs.cwd().access(dev_path, .{})) |_| {
        return dev_path;
    } else |_| {}

    // Try ~/.local/jn/plugins
    if (std.posix.getenv("HOME")) |home| {
        const user_path = std.fmt.allocPrint(allocator, "{s}/.local/jn/plugins/zig/{s}/bin/{s}", .{ home, name, name }) catch return null;
        if (std.fs.cwd().access(user_path, .{})) |_| {
            return user_path;
        } else |_| {}
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
