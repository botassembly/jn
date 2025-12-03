const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");
const jn_plugin = @import("jn-plugin");

const plugin_meta = jn_plugin.PluginMeta{
    .name = "jsonl",
    .version = "0.2.0",
    .matches = &.{ ".*\\.jsonl$", ".*\\.ndjson$" },
    .role = .format,
    .modes = &.{ .read, .write },
};

pub fn main() !void {
    const args = jn_cli.parseArgs();
    const mode = args.get("mode", "read") orelse "read";

    if (args.has("jn-meta")) {
        try jn_plugin.outputManifestToStdout(plugin_meta);
        return;
    }

    if (std.mem.eql(u8, mode, "read") or std.mem.eql(u8, mode, "write")) {
        try streamNdjson();
        return;
    }

    jn_core.exitWithError("jsonl: unknown mode '{s}'", .{mode});
}

fn streamNdjson() !void {
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

test "manifest output contains plugin name" {
    var buf: [256]u8 = undefined;
    var fbs = std.io.fixedBufferStream(&buf);
    try jn_plugin.outputManifest(fbs.writer(), plugin_meta);
    const output = fbs.getWritten();
    try std.testing.expect(std.mem.indexOf(u8, output, "\"jsonl\"") != null);
}
