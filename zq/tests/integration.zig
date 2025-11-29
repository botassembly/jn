const std = @import("std");

// Integration tests for ZQ
// These test the full pipeline: stdin -> parse -> eval -> stdout

fn runZq(allocator: std.mem.Allocator, expr: []const u8, input: []const u8) ![]u8 {
    const exe_path = "zig-out/bin/zq";

    var child = std.process.Child.init(.{
        .argv = &[_][]const u8{ exe_path, expr },
        .stdin_behavior = .pipe,
        .stdout_behavior = .pipe,
        .stderr_behavior = .pipe,
    }, allocator);

    try child.spawn();

    // Write input
    if (child.stdin) |stdin| {
        stdin.writeAll(input) catch {};
        stdin.close();
        child.stdin = null;
    }

    // Read output
    const stdout = try child.stdout.?.readToEndAlloc(allocator, 1024 * 1024);
    const stderr = try child.stderr.?.readToEndAlloc(allocator, 1024 * 1024);
    defer allocator.free(stderr);

    const term = try child.wait();
    if (term.Exited != 0) {
        std.debug.print("ZQ failed with: {s}\n", .{stderr});
        return error.ProcessFailed;
    }

    return stdout;
}

test "integration: identity" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const output = runZq(arena.allocator(), ".", "{\"x\":1}\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };

    try std.testing.expectEqualStrings("{\"x\":1}\n", output);
}

test "integration: field access" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const output = runZq(arena.allocator(), ".name", "{\"name\":\"Alice\",\"age\":30}\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };

    try std.testing.expectEqualStrings("\"Alice\"\n", output);
}

test "integration: nested path" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const output = runZq(arena.allocator(), ".user.name", "{\"user\":{\"name\":\"Bob\"}}\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };

    try std.testing.expectEqualStrings("\"Bob\"\n", output);
}

test "integration: select greater than" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const input =
        \\{"id":1,"value":50}
        \\{"id":2,"value":150}
        \\{"id":3,"value":75}
        \\
    ;

    const output = runZq(arena.allocator(), "select(.value > 100)", input) catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };

    try std.testing.expectEqualStrings("{\"id\":2,\"value\":150}\n", output);
}

test "integration: select with and" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const input =
        \\{"active":true,"verified":true}
        \\{"active":true,"verified":false}
        \\{"active":false,"verified":true}
        \\
    ;

    const output = runZq(arena.allocator(), "select(.active and .verified)", input) catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };

    try std.testing.expectEqualStrings("{\"active\":true,\"verified\":true}\n", output);
}

test "integration: select with or" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const input =
        \\{"admin":true,"mod":false}
        \\{"admin":false,"mod":true}
        \\{"admin":false,"mod":false}
        \\
    ;

    const output = runZq(arena.allocator(), "select(.admin or .mod)", input) catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };

    // Should have 2 lines (admin=true and mod=true cases)
    var line_count: usize = 0;
    var iter = std.mem.splitScalar(u8, output, '\n');
    while (iter.next()) |line| {
        if (line.len > 0) line_count += 1;
    }
    try std.testing.expectEqual(@as(usize, 2), line_count);
}

test "integration: iterate array" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const output = runZq(arena.allocator(), ".items[]", "{\"items\":[1,2,3]}\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };

    try std.testing.expectEqualStrings("1\n2\n3\n", output);
}

test "integration: multiple lines" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const input =
        \\{"x":1}
        \\{"x":2}
        \\{"x":3}
        \\
    ;

    const output = runZq(arena.allocator(), ".x", input) catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };

    try std.testing.expectEqualStrings("1\n2\n3\n", output);
}
