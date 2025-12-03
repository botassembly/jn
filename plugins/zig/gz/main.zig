const std = @import("std");
const zig_builtin = @import("builtin");

// ============================================================================
// GZ Plugin - Streaming Gzip Decompression/Compression for JN
//
// Reads gzip-compressed bytes from stdin and writes decompressed bytes to stdout.
// Operates in raw mode (bytes, not NDJSON).
//
// Usage:
//   cat file.csv.gz | jn-gz --mode=raw > file.csv
//   jn cat file.csv.gz  # Framework chains: gz (raw) → csv (read)
// ============================================================================

const Plugin = struct {
    name: []const u8,
    version: []const u8,
    matches: []const []const u8,
    role: []const u8,
    modes: []const []const u8,
    supports_raw: bool,
};

const plugin = Plugin{
    .name = "gz",
    .version = "0.1.0",
    .matches = &[_][]const u8{".*\\.gz$"},
    .role = "compression",
    .modes = &[_][]const u8{"raw"},
    .supports_raw = true,
};

pub fn main() !void {
    // Parse command line arguments
    var args = std.process.args();
    _ = args.skip(); // Skip program name

    var mode: []const u8 = "raw";
    var jn_meta = false;

    while (args.next()) |arg| {
        if (std.mem.eql(u8, arg, "--jn-meta")) {
            jn_meta = true;
        } else if (std.mem.startsWith(u8, arg, "--mode=")) {
            mode = arg["--mode=".len..];
        }
    }

    // Handle --jn-meta: output plugin manifest
    if (jn_meta) {
        try outputManifest();
        return;
    }

    // Dispatch based on mode
    if (std.mem.eql(u8, mode, "raw")) {
        try decompressMode();
    } else {
        std.debug.print("gz: error: unknown mode '{s}' (only 'raw' supported)\n", .{mode});
        std.process.exit(1);
    }
}

fn outputManifest() !void {
    var stdout_buf: [4096]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    try writer.writeAll("{\"name\":\"");
    try writer.writeAll(plugin.name);
    try writer.writeAll("\",\"version\":\"");
    try writer.writeAll(plugin.version);
    try writer.writeAll("\",\"matches\":[");

    for (plugin.matches, 0..) |pattern, i| {
        if (i > 0) try writer.writeByte(',');
        try writer.writeByte('"');
        for (pattern) |c| {
            if (c == '"' or c == '\\') try writer.writeByte('\\');
            try writer.writeByte(c);
        }
        try writer.writeByte('"');
    }

    try writer.writeAll("],\"role\":\"");
    try writer.writeAll(plugin.role);
    try writer.writeAll("\",\"modes\":[");

    for (plugin.modes, 0..) |m, i| {
        if (i > 0) try writer.writeByte(',');
        try writer.writeByte('"');
        try writer.writeAll(m);
        try writer.writeByte('"');
    }

    try writer.writeAll("],\"supports_raw\":true}\n");
    try writer.flush();
}

// ============================================================================
// Decompress Mode (raw) - stream gzip stdin to stdout
// ============================================================================

fn decompressMode() !void {
    // Use buffered stdin for gzip decompressor
    var stdin_buf: [64 * 1024]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);

    // Allocate window buffer for deflate (required for gzip decompression)
    var window_buf: [std.compress.flate.max_window_len]u8 = undefined;

    // Create gzip decompressor over buffered stdin with gzip container
    var decomp = std.compress.flate.Decompress.init(&stdin_wrapper.interface, .gzip, &window_buf);

    // Stream decompressed data to stdout (unbuffered for raw binary)
    const stdout = std.fs.File.stdout();
    var buf: [64 * 1024]u8 = undefined;

    while (true) {
        const n = decomp.reader.readSliceShort(&buf) catch |err| {
            // EndOfStream means we've read all data - that's success
            if (err == error.EndOfStream) break;
            std.debug.print("gz: decompression error: {}\n", .{err});
            std.process.exit(1);
        };

        if (n == 0) break; // EOF

        _ = stdout.write(buf[0..n]) catch |err| {
            // EPIPE (BrokenPipe) means downstream closed - exit cleanly
            if (err == error.BrokenPipe) {
                std.process.exit(0);
            }
            std.debug.print("gz: write error: {}\n", .{err});
            std.process.exit(1);
        };
    }
}
