const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");
const jn_plugin = @import("jn-plugin");
const comprezz = @import("comprezz.zig");

const plugin_meta = jn_plugin.PluginMeta{
    .name = "gz",
    .version = "0.2.0",
    .matches = &.{".*\\.gz$"},
    .role = .compression,
    .modes = &.{ .raw, .write },
    .supports_raw = true,
};

pub fn main() !void {
    const args = jn_cli.parseArgs();
    const mode = args.get("mode", "raw") orelse "raw";

    if (args.has("jn-meta")) {
        try jn_plugin.outputManifestToStdout(plugin_meta);
        return;
    }

    if (std.mem.eql(u8, mode, "raw")) {
        try decompressMode();
    } else if (std.mem.eql(u8, mode, "write")) {
        try compressMode();
    } else {
        jn_core.exitWithError("gz: unknown mode '{s}' (supported: raw, write)", .{mode});
    }
}

fn decompressMode() !void {
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);

    var window_buf: [std.compress.flate.max_window_len]u8 = undefined;
    var decomp = std.compress.flate.Decompress.init(
        &stdin_wrapper.interface,
        .gzip,
        &window_buf,
    );

    const stdout = std.fs.File.stdout();
    var out_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;

    while (true) {
        const n = decomp.reader.readSliceShort(&out_buf) catch |err| {
            if (err == error.EndOfStream) break;
            jn_core.exitWithError("gz: decompression error: {}", .{err});
        };

        if (n == 0) break;
        _ = stdout.write(out_buf[0..n]) catch |err| jn_core.handleWriteError(err);
    }
}

fn compressMode() !void {
    var stdin_buf: [jn_core.STDIN_BUFFER_SIZE]u8 = undefined;
    var stdin_wrapper = std.fs.File.stdin().reader(&stdin_buf);

    var stdout_buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    var stdout_wrapper = std.fs.File.stdout().writer(&stdout_buf);
    const writer = &stdout_wrapper.interface;

    comprezz.compress(&stdin_wrapper.interface, writer, .{}) catch |err| {
        jn_core.exitWithError("gz: compression error: {}", .{err});
    };

    jn_core.flushWriter(writer);
}
