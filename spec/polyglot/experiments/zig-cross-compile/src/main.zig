const std = @import("std");

pub fn main() void {
    const stdout = std.io.getStdOut().writer();
    stdout.print("Hello from Zig!\n", .{}) catch {};
    stdout.print("Target: {s}-{s}\n", .{
        @tagName(std.Target.current.cpu.arch),
        @tagName(std.Target.current.os.tag),
    }) catch {};
}
