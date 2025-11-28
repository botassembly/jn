const std = @import("std");

pub fn main() !void {
    const allocator = std.heap.page_allocator;

    const args = try std.process.argsAlloc(allocator);
    defer std.process.argsFree(allocator, args);

    if (args.len < 2) {
        std.debug.print("Usage: zq-wrap <jq-expression>\n", .{});
        std.process.exit(1);
    }

    // Build jq command: jq -c <expression>
    var jq_args = std.ArrayList([]const u8).init(allocator);
    try jq_args.append("jq");
    try jq_args.append("-c");
    for (args[1..]) |arg| {
        try jq_args.append(arg);
    }

    // Spawn jq, inherit stdin/stdout/stderr
    var child = std.ChildProcess.init(jq_args.items, allocator);
    child.stdin_behavior = .Inherit;
    child.stdout_behavior = .Inherit;
    child.stderr_behavior = .Inherit;

    _ = try child.spawnAndWait();
}
