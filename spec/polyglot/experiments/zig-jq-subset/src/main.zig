const std = @import("std");

const CompareValue = union(enum) {
    int: i64,
    float: f64,
    string: []const u8,
    boolean: bool,
    none,
};

const Expr = union(enum) {
    identity, // .
    field: []const u8, // .foo
    path: [][]const u8, // .foo.bar.baz
    select: *SelectExpr, // select(.foo > 10)
};

const SelectExpr = struct {
    path: [][]const u8,
    op: enum { gt, lt, eq, ne, exists },
    value: CompareValue,
};

fn parseExpr(allocator: std.mem.Allocator, expr: []const u8) !Expr {
    const trimmed = std.mem.trim(u8, expr, " \t");

    // Identity
    if (std.mem.eql(u8, trimmed, ".")) {
        return .identity;
    }

    // Select expression
    if (std.mem.startsWith(u8, trimmed, "select(") and std.mem.endsWith(u8, trimmed, ")")) {
        const inner = trimmed[7 .. trimmed.len - 1];
        const select_expr = try allocator.create(SelectExpr);

        // Parse select condition: .field > value, .field == value, .field (exists)
        if (std.mem.indexOf(u8, inner, " > ")) |pos| {
            select_expr.path = try parsePath(allocator, inner[0..pos]);
            select_expr.op = .gt;
            select_expr.value = try parseValue(inner[pos + 3 ..]);
        } else if (std.mem.indexOf(u8, inner, " < ")) |pos| {
            select_expr.path = try parsePath(allocator, inner[0..pos]);
            select_expr.op = .lt;
            select_expr.value = try parseValue(inner[pos + 3 ..]);
        } else if (std.mem.indexOf(u8, inner, " == ")) |pos| {
            select_expr.path = try parsePath(allocator, inner[0..pos]);
            select_expr.op = .eq;
            select_expr.value = try parseValue(inner[pos + 4 ..]);
        } else if (std.mem.indexOf(u8, inner, " != ")) |pos| {
            select_expr.path = try parsePath(allocator, inner[0..pos]);
            select_expr.op = .ne;
            select_expr.value = try parseValue(inner[pos + 4 ..]);
        } else {
            // Just .field means exists/truthy
            select_expr.path = try parsePath(allocator, inner);
            select_expr.op = .exists;
            select_expr.value = .none;
        }

        return .{ .select = select_expr };
    }

    // Field path: .foo or .foo.bar
    if (trimmed[0] == '.') {
        const path = try parsePath(allocator, trimmed);
        if (path.len == 1) {
            return .{ .field = path[0] };
        }
        return .{ .path = path };
    }

    return error.InvalidExpression;
}

fn parsePath(allocator: std.mem.Allocator, expr: []const u8) ![][]const u8 {
    var parts = std.ArrayList([]const u8).init(allocator);
    var rest = if (expr[0] == '.') expr[1..] else expr;

    var iter = std.mem.splitScalar(u8, rest, '.');
    while (iter.next()) |part| {
        if (part.len > 0) {
            try parts.append(part);
        }
    }

    return parts.toOwnedSlice();
}

fn parseValue(str: []const u8) !CompareValue {
    const trimmed = std.mem.trim(u8, str, " \t");

    // Boolean
    if (std.mem.eql(u8, trimmed, "true")) return .{ .boolean = true };
    if (std.mem.eql(u8, trimmed, "false")) return .{ .boolean = false };

    // String (quoted)
    if (trimmed.len >= 2 and trimmed[0] == '"' and trimmed[trimmed.len - 1] == '"') {
        return .{ .string = trimmed[1 .. trimmed.len - 1] };
    }

    // Integer
    if (std.fmt.parseInt(i64, trimmed, 10)) |i| {
        return .{ .int = i };
    } else |_| {}

    // Float
    if (std.fmt.parseFloat(f64, trimmed)) |f| {
        return .{ .float = f };
    } else |_| {}

    return error.InvalidValue;
}

fn getPath(value: std.json.Value, path: [][]const u8) ?std.json.Value {
    var current = value;
    for (path) |key| {
        switch (current) {
            .object => |obj| {
                if (obj.get(key)) |v| {
                    current = v;
                } else {
                    return null;
                }
            },
            else => return null,
        }
    }
    return current;
}

fn evalSelect(select: *const SelectExpr, value: std.json.Value) bool {
    const field_val = getPath(value, select.path) orelse return false;

    switch (select.op) {
        .exists => {
            return switch (field_val) {
                .null => false,
                .bool => |b| b,
                else => true,
            };
        },
        .gt => {
            const cmp_val = select.value;
            switch (field_val) {
                .integer => |i| {
                    switch (cmp_val) {
                        .int => |ci| return i > ci,
                        .float => |cf| return @as(f64, @floatFromInt(i)) > cf,
                        else => return false,
                    }
                },
                .float => |f| {
                    switch (cmp_val) {
                        .int => |ci| return f > @as(f64, @floatFromInt(ci)),
                        .float => |cf| return f > cf,
                        else => return false,
                    }
                },
                else => return false,
            }
        },
        .lt => {
            const cmp_val = select.value;
            switch (field_val) {
                .integer => |i| {
                    switch (cmp_val) {
                        .int => |ci| return i < ci,
                        .float => |cf| return @as(f64, @floatFromInt(i)) < cf,
                        else => return false,
                    }
                },
                .float => |f| {
                    switch (cmp_val) {
                        .int => |ci| return f < @as(f64, @floatFromInt(ci)),
                        .float => |cf| return f < cf,
                        else => return false,
                    }
                },
                else => return false,
            }
        },
        .eq => {
            const cmp_val = select.value;
            switch (field_val) {
                .integer => |i| {
                    switch (cmp_val) {
                        .int => |ci| return i == ci,
                        else => return false,
                    }
                },
                .float => |f| {
                    switch (cmp_val) {
                        .float => |cf| return f == cf,
                        else => return false,
                    }
                },
                .bool => |b| {
                    switch (cmp_val) {
                        .boolean => |cb| return b == cb,
                        else => return false,
                    }
                },
                .string => |s| {
                    switch (cmp_val) {
                        .string => |cs| return std.mem.eql(u8, s, cs),
                        else => return false,
                    }
                },
                else => return false,
            }
        },
        .ne => {
            return !evalSelect(&SelectExpr{
                .path = select.path,
                .op = .eq,
                .value = select.value,
            }, value);
        },
    }
}

fn writeJson(writer: anytype, value: std.json.Value) !void {
    try std.json.stringify(value, .{}, writer);
}

pub fn main() !void {
    // Use page allocator for expression parsing (one-time)
    const page_alloc = std.heap.page_allocator;

    const args = try std.process.argsAlloc(page_alloc);
    defer std.process.argsFree(page_alloc, args);

    if (args.len < 2) {
        std.debug.print("Usage: zq <expression>\n", .{});
        std.debug.print("Expressions: . | .field | .a.b.c | select(.x > N)\n", .{});
        std.process.exit(1);
    }

    const expr = try parseExpr(page_alloc, args[1]);

    const stdin = std.io.getStdIn();
    const stdout = std.io.getStdOut();
    var buf_reader = std.io.bufferedReader(stdin.reader());
    var buf_writer = std.io.bufferedWriter(stdout.writer());
    const reader = buf_reader.reader();
    const writer = buf_writer.writer();

    var line_buf: [1024 * 1024]u8 = undefined; // 1MB line buffer

    // Arena allocator for JSON parsing - reset each iteration
    var arena = std.heap.ArenaAllocator.init(page_alloc);
    defer arena.deinit();

    while (reader.readUntilDelimiterOrEof(&line_buf, '\n')) |maybe_line| {
        const line = maybe_line orelse break;
        if (line.len == 0) continue;

        // Reset arena each iteration - free all at once
        _ = arena.reset(.retain_capacity);

        const parsed = std.json.parseFromSlice(std.json.Value, arena.allocator(), line, .{}) catch continue;
        const value = parsed.value;

        switch (expr) {
            .identity => {
                try writeJson(writer, value);
                try writer.writeByte('\n');
            },
            .field => |field| {
                switch (value) {
                    .object => |obj| {
                        if (obj.get(field)) |v| {
                            try writeJson(writer, v);
                            try writer.writeByte('\n');
                        }
                    },
                    else => {},
                }
            },
            .path => |path| {
                if (getPath(value, path)) |v| {
                    try writeJson(writer, v);
                    try writer.writeByte('\n');
                }
            },
            .select => |sel| {
                if (evalSelect(sel, value)) {
                    try writeJson(writer, value);
                    try writer.writeByte('\n');
                }
            },
        }
    } else |err| {
        if (err != error.EndOfStream) {
            std.debug.print("Read error: {}\n", .{err});
            std.process.exit(1);
        }
    }

    try buf_writer.flush();
}

test "parse identity" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".");
    try std.testing.expect(expr == .identity);
}

test "parse field" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".name");
    try std.testing.expect(expr == .field);
    try std.testing.expectEqualStrings("name", expr.field);
}

test "parse path" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".foo.bar.baz");
    try std.testing.expect(expr == .path);
    try std.testing.expectEqual(@as(usize, 3), expr.path.len);
}

test "parse select gt" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "select(.id > 50000)");
    try std.testing.expect(expr == .select);
    try std.testing.expect(expr.select.op == .gt);
    try std.testing.expect(expr.select.value.int == 50000);
}
