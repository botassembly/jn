const std = @import("std");
const builtin = @import("builtin");

pub fn main() void {
    const stdout = std.io.getStdOut().writer();
    stdout.print("Hello from Zig!\n", .{}) catch {};
    stdout.print("Target: {s}-{s}\n", .{
        @tagName(builtin.cpu.arch),
        @tagName(builtin.os.tag),
    }) catch {};
}
