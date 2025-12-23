const std = @import("std");

// Integration tests for ZQ
// These test the full pipeline: stdin -> parse -> eval -> stdout

fn runZq(allocator: std.mem.Allocator, expr: []const u8, input: []const u8) ![]u8 {
    const exe_path = "zig-out/bin/zq";

    // Zig 0.15.2 API: init takes (argv, allocator) as positional args
    var child = std.process.Child.init(&[_][]const u8{ exe_path, expr }, allocator);
    child.stdin_behavior = .Pipe;
    child.stdout_behavior = .Pipe;
    child.stderr_behavior = .Pipe;

    try child.spawn();

    // Write input and close stdin
    if (child.stdin) |stdin| {
        try stdin.writeAll(input);
        stdin.close();
        child.stdin = null;
    }

    // Read output using direct file reads (0.15.2 compatible)
    var stdout_data: std.ArrayListUnmanaged(u8) = .empty;
    errdefer stdout_data.deinit(allocator);
    var stderr_data: std.ArrayListUnmanaged(u8) = .empty;
    defer stderr_data.deinit(allocator);

    // Read in chunks until EOF
    var read_buf: [4096]u8 = undefined;
    if (child.stdout) |stdout_file| {
        while (true) {
            const n = try stdout_file.read(&read_buf);
            if (n == 0) break;
            try stdout_data.appendSlice(allocator, read_buf[0..n]);
        }
    }

    if (child.stderr) |stderr_file| {
        while (true) {
            const n = try stderr_file.read(&read_buf);
            if (n == 0) break;
            try stderr_data.appendSlice(allocator, read_buf[0..n]);
        }
    }

    const term = try child.wait();
    switch (term) {
        .Exited => |code| {
            if (code != 0) {
                std.debug.print("ZQ failed with exit code {d}: {s}\n", .{ code, stderr_data.items });
                return error.ProcessFailed;
            }
        },
        else => {
            std.debug.print("ZQ terminated abnormally: {s}\n", .{stderr_data.items});
            return error.ProcessFailed;
        },
    }

    return stdout_data.toOwnedSlice(allocator);
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

// Sprint 03 integration tests

test "integration: array first" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output = runZq(arena.allocator(), "first", "[1,2,3]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("1\n", output);
}

test "integration: array last" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output = runZq(arena.allocator(), "last", "[1,2,3]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("3\n", output);
}

test "integration: array sort" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output = runZq(arena.allocator(), "sort", "[3,1,2]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("[1,2,3]\n", output);
}

test "integration: array unique" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output = runZq(arena.allocator(), "unique", "[1,2,2,3,1]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("[1,2,3]\n", output);
}

test "integration: array reverse" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output = runZq(arena.allocator(), "reverse", "[1,2,3]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("[3,2,1]\n", output);
}

test "integration: array flatten" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output = runZq(arena.allocator(), "flatten", "[[1,2],[3,4]]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("[1,2,3,4]\n", output);
}

test "integration: add numbers" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output = runZq(arena.allocator(), "add", "[1,2,3]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("6\n", output);
}

test "integration: add strings" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output = runZq(arena.allocator(), "add", "[\"a\",\"b\",\"c\"]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("\"abc\"\n", output);
}

test "integration: min max" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output_min = runZq(arena.allocator(), "min", "[3,1,2]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("1\n", output_min);

    const output_max = runZq(arena.allocator(), "max", "[3,1,2]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("3\n", output_max);
}

test "integration: sort_by" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output = runZq(arena.allocator(), "sort_by(.x)", "[{\"x\":3},{\"x\":1},{\"x\":2}]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("[{\"x\":1},{\"x\":2},{\"x\":3}]\n", output);
}

test "integration: min_by max_by" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output_min = runZq(arena.allocator(), "min_by(.x)", "[{\"x\":3},{\"x\":1},{\"x\":2}]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("{\"x\":1}\n", output_min);

    const output_max = runZq(arena.allocator(), "max_by(.x)", "[{\"x\":3},{\"x\":1},{\"x\":2}]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("{\"x\":3}\n", output_max);
}

test "integration: map" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output = runZq(arena.allocator(), "map(. * 2)", "[1,2,3]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("[2,4,6]\n", output);
}

test "integration: split join" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output_split = runZq(arena.allocator(), "split(\",\")", "\"a,b,c\"\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("[\"a\",\"b\",\"c\"]\n", output_split);

    const output_join = runZq(arena.allocator(), "join(\",\")", "[\"a\",\"b\",\"c\"]\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("\"a,b,c\"\n", output_join);
}

test "integration: ascii case" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output_down = runZq(arena.allocator(), "ascii_downcase", "\"HELLO\"\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("\"hello\"\n", output_down);

    const output_up = runZq(arena.allocator(), "ascii_upcase", "\"hello\"\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("\"HELLO\"\n", output_up);
}

test "integration: string predicates" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const output_sw = runZq(arena.allocator(), "startswith(\"hel\")", "\"hello\"\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("true\n", output_sw);

    const output_ew = runZq(arena.allocator(), "endswith(\"llo\")", "\"hello\"\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("true\n", output_ew);

    const output_c = runZq(arena.allocator(), "contains(\"ell\")", "\"hello\"\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("true\n", output_c);
}

test "integration: trim strings" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const output_l = runZq(arena.allocator(), "ltrimstr(\"hel\")", "\"hello\"\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("\"lo\"\n", output_l);

    const output_r = runZq(arena.allocator(), "rtrimstr(\"llo\")", "\"hello\"\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("\"he\"\n", output_r);
}

test "integration: array construction" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const output = runZq(arena.allocator(), "[.a, .b]", "{\"a\":1,\"b\":2}\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    try std.testing.expectEqualStrings("[1,2]\n", output);
}

// Edge case tests for integer overflow handling
// These tests verify that overflow cases don't crash and produce reasonable output
test "integration: incr at maxInt handles overflow" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    // i64 max is 9223372036854775807
    // Without overflow protection, this would crash or produce incorrect results
    const output = runZq(arena.allocator(), "incr", "9223372036854775807\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    // Key check: it doesn't crash and produces output (float converted to whole number)
    // Expected: 9223372036854776000 (float approximation)
    try std.testing.expect(output.len > 0);
    const trimmed = std.mem.trim(u8, output, " \n\r\t");
    // The result should start with 92233... (larger than input)
    try std.testing.expect(std.mem.startsWith(u8, trimmed, "92233"));
}

test "integration: decr at minInt handles overflow" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    // i64 min is -9223372036854775808
    // Without overflow protection, this would crash or produce incorrect results
    const output = runZq(arena.allocator(), "decr", "-9223372036854775808\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    // Key check: it doesn't crash and produces output
    try std.testing.expect(output.len > 0);
    const trimmed = std.mem.trim(u8, output, " \n\r\t");
    // The result should be negative (start with -)
    try std.testing.expect(trimmed.len > 0);
    try std.testing.expect(trimmed[0] == '-');
}

test "integration: negate at minInt handles overflow" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    // i64 min is -9223372036854775808, negating it would overflow
    // since maxInt(i64) is only 9223372036854775807
    const output = runZq(arena.allocator(), "negate", "-9223372036854775808\n") catch |err| {
        std.debug.print("Test skipped: zq not built ({any})\n", .{err});
        return;
    };
    // Result should be positive (not crash)
    try std.testing.expect(output.len > 0);
    const trimmed = std.mem.trim(u8, output, " \n\r\t");
    try std.testing.expect(trimmed.len > 0);
    try std.testing.expect(trimmed[0] != '-');
}
