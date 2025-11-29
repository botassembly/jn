const std = @import("std");

pub const version = "0.1.0";

// ============================================================================
// Types
// ============================================================================

const CompareValue = union(enum) {
    int: i64,
    float: f64,
    string: []const u8,
    boolean: bool,
    null_val,
    none,
};

const CompareOp = enum {
    gt, // >
    lt, // <
    gte, // >=
    lte, // <=
    eq, // ==
    ne, // !=
    exists, // truthy check
};

const BoolOp = enum {
    and_op,
    or_op,
};

const Condition = union(enum) {
    simple: SimpleCondition,
    compound: CompoundCondition,
    negated: *Condition,
};

const SimpleCondition = struct {
    path: [][]const u8,
    index: ?IndexExpr = null,
    op: CompareOp,
    value: CompareValue,
};

const CompoundCondition = struct {
    left: *Condition,
    op: BoolOp,
    right: *Condition,
};

const IndexExpr = union(enum) {
    single: i64, // .[0] or .[-1]
    iterate, // .[]
};

const Expr = union(enum) {
    identity, // .
    field: FieldExpr, // .foo or .foo[0]
    path: PathExpr, // .foo.bar.baz or .foo.bar[0]
    select: *Condition, // select(.foo > 10)
    iterate: IterateExpr, // .items[] or .[]
};

const FieldExpr = struct {
    name: []const u8,
    index: ?IndexExpr = null,
};

const PathExpr = struct {
    parts: [][]const u8,
    index: ?IndexExpr = null,
};

const IterateExpr = struct {
    path: [][]const u8, // empty means root
};

const Config = struct {
    compact: bool = true,
    raw_strings: bool = false,
    exit_on_empty: bool = false,
    skip_invalid: bool = true,
};

// ============================================================================
// Parser
// ============================================================================

fn parseExpr(allocator: std.mem.Allocator, expr: []const u8) !Expr {
    const trimmed = std.mem.trim(u8, expr, " \t");

    // Identity
    if (std.mem.eql(u8, trimmed, ".")) {
        return .identity;
    }

    // Root iteration: .[]
    if (std.mem.eql(u8, trimmed, ".[]")) {
        return .{ .iterate = .{ .path = &[_][]const u8{} } };
    }

    // Select expression
    if (std.mem.startsWith(u8, trimmed, "select(") and std.mem.endsWith(u8, trimmed, ")")) {
        const inner = trimmed[7 .. trimmed.len - 1];
        const condition = try parseCondition(allocator, inner);
        return .{ .select = condition };
    }

    // Field path with optional iteration: .foo or .foo.bar or .items[]
    if (trimmed[0] == '.') {
        // Check for iteration at end
        if (std.mem.endsWith(u8, trimmed, "[]")) {
            const path_part = trimmed[0 .. trimmed.len - 2];
            const path = try parsePath(allocator, path_part);
            return .{ .iterate = .{ .path = path } };
        }

        // Check for array index at end
        var path_end = trimmed.len;
        var index: ?IndexExpr = null;
        if (std.mem.lastIndexOf(u8, trimmed, "[")) |bracket_pos| {
            if (std.mem.endsWith(u8, trimmed, "]") and bracket_pos > 0) {
                const idx_str = trimmed[bracket_pos + 1 .. trimmed.len - 1];
                if (std.fmt.parseInt(i64, idx_str, 10)) |idx| {
                    index = .{ .single = idx };
                    path_end = bracket_pos;
                } else |_| {}
            }
        }

        const path = try parsePath(allocator, trimmed[0..path_end]);
        if (path.len == 1) {
            return .{ .field = .{ .name = path[0], .index = index } };
        }
        return .{ .path = .{ .parts = path, .index = index } };
    }

    return error.InvalidExpression;
}

fn parseCondition(allocator: std.mem.Allocator, expr: []const u8) !*Condition {
    const trimmed = std.mem.trim(u8, expr, " \t");

    // Check for boolean operators (lowest precedence)
    // Find "and" or "or" not inside parentheses
    var paren_depth: i32 = 0;
    var i: usize = 0;
    while (i < trimmed.len) : (i += 1) {
        if (trimmed[i] == '(') {
            paren_depth += 1;
        } else if (trimmed[i] == ')') {
            paren_depth -= 1;
        } else if (paren_depth == 0) {
            // Check for " and " (with spaces)
            if (i + 5 <= trimmed.len and std.mem.eql(u8, trimmed[i .. i + 5], " and ")) {
                const left = try parseCondition(allocator, trimmed[0..i]);
                const right = try parseCondition(allocator, trimmed[i + 5 ..]);
                const cond = try allocator.create(Condition);
                cond.* = .{ .compound = .{
                    .left = left,
                    .op = .and_op,
                    .right = right,
                } };
                return cond;
            }
            // Check for " or " (with spaces)
            if (i + 4 <= trimmed.len and std.mem.eql(u8, trimmed[i .. i + 4], " or ")) {
                const left = try parseCondition(allocator, trimmed[0..i]);
                const right = try parseCondition(allocator, trimmed[i + 4 ..]);
                const cond = try allocator.create(Condition);
                cond.* = .{ .compound = .{
                    .left = left,
                    .op = .or_op,
                    .right = right,
                } };
                return cond;
            }
        }
    }

    // Check for "not " prefix
    if (std.mem.startsWith(u8, trimmed, "not ")) {
        const inner = try parseCondition(allocator, trimmed[4..]);
        const cond = try allocator.create(Condition);
        cond.* = .{ .negated = inner };
        return cond;
    }

    // Check for parenthesized expression
    if (trimmed[0] == '(' and trimmed[trimmed.len - 1] == ')') {
        return parseCondition(allocator, trimmed[1 .. trimmed.len - 1]);
    }

    // Simple condition
    const simple = try parseSimpleCondition(allocator, trimmed);
    const cond = try allocator.create(Condition);
    cond.* = .{ .simple = simple };
    return cond;
}

fn parseSimpleCondition(allocator: std.mem.Allocator, expr: []const u8) !SimpleCondition {
    // Order matters: check >= and <= before > and <
    if (std.mem.indexOf(u8, expr, " >= ")) |pos| {
        return SimpleCondition{
            .path = try parsePath(allocator, expr[0..pos]),
            .op = .gte,
            .value = try parseValue(expr[pos + 4 ..]),
        };
    }
    if (std.mem.indexOf(u8, expr, " <= ")) |pos| {
        return SimpleCondition{
            .path = try parsePath(allocator, expr[0..pos]),
            .op = .lte,
            .value = try parseValue(expr[pos + 4 ..]),
        };
    }
    if (std.mem.indexOf(u8, expr, " > ")) |pos| {
        return SimpleCondition{
            .path = try parsePath(allocator, expr[0..pos]),
            .op = .gt,
            .value = try parseValue(expr[pos + 3 ..]),
        };
    }
    if (std.mem.indexOf(u8, expr, " < ")) |pos| {
        return SimpleCondition{
            .path = try parsePath(allocator, expr[0..pos]),
            .op = .lt,
            .value = try parseValue(expr[pos + 3 ..]),
        };
    }
    if (std.mem.indexOf(u8, expr, " == ")) |pos| {
        return SimpleCondition{
            .path = try parsePath(allocator, expr[0..pos]),
            .op = .eq,
            .value = try parseValue(expr[pos + 4 ..]),
        };
    }
    if (std.mem.indexOf(u8, expr, " != ")) |pos| {
        return SimpleCondition{
            .path = try parsePath(allocator, expr[0..pos]),
            .op = .ne,
            .value = try parseValue(expr[pos + 4 ..]),
        };
    }

    // Just .field means exists/truthy
    return SimpleCondition{
        .path = try parsePath(allocator, expr),
        .op = .exists,
        .value = .none,
    };
}

fn parsePath(allocator: std.mem.Allocator, expr: []const u8) ![][]const u8 {
    var parts = std.ArrayList([]const u8).init(allocator);
    const rest = if (expr.len > 0 and expr[0] == '.') expr[1..] else expr;

    var iter = std.mem.splitScalar(u8, rest, '.');
    while (iter.next()) |part| {
        if (part.len > 0) {
            // Strip any array index notation for now
            const clean = if (std.mem.indexOf(u8, part, "[")) |idx| part[0..idx] else part;
            if (clean.len > 0) {
                try parts.append(clean);
            }
        }
    }

    return parts.toOwnedSlice();
}

fn parseValue(str: []const u8) !CompareValue {
    const trimmed = std.mem.trim(u8, str, " \t");

    // Null
    if (std.mem.eql(u8, trimmed, "null")) return .null_val;

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

// ============================================================================
// Evaluator
// ============================================================================

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

fn getIndex(value: std.json.Value, index: i64) ?std.json.Value {
    switch (value) {
        .array => |arr| {
            const len = arr.items.len;
            if (len == 0) return null;

            const actual_idx: usize = if (index < 0)
                if (@as(usize, @intCast(-index)) <= len)
                    len - @as(usize, @intCast(-index))
                else
                    return null
            else if (@as(usize, @intCast(index)) < len)
                @as(usize, @intCast(index))
            else
                return null;

            return arr.items[actual_idx];
        },
        else => return null,
    }
}

fn evalCondition(cond: *const Condition, value: std.json.Value) bool {
    switch (cond.*) {
        .simple => |simple| return evalSimpleCondition(&simple, value),
        .compound => |compound| {
            const left_result = evalCondition(compound.left, value);
            return switch (compound.op) {
                .and_op => left_result and evalCondition(compound.right, value),
                .or_op => left_result or evalCondition(compound.right, value),
            };
        },
        .negated => |inner| return !evalCondition(inner, value),
    }
}

fn evalSimpleCondition(cond: *const SimpleCondition, value: std.json.Value) bool {
    var field_val = getPath(value, cond.path) orelse return false;

    // Apply index if present
    if (cond.index) |idx| {
        switch (idx) {
            .single => |i| {
                field_val = getIndex(field_val, i) orelse return false;
            },
            .iterate => return false, // Can't iterate in condition
        }
    }

    switch (cond.op) {
        .exists => {
            return switch (field_val) {
                .null => false,
                .bool => |b| b,
                else => true,
            };
        },
        .gt => return compareGt(field_val, cond.value),
        .lt => return compareLt(field_val, cond.value),
        .gte => return compareGt(field_val, cond.value) or compareEq(field_val, cond.value),
        .lte => return compareLt(field_val, cond.value) or compareEq(field_val, cond.value),
        .eq => return compareEq(field_val, cond.value),
        .ne => return !compareEq(field_val, cond.value),
    }
}

fn compareGt(field_val: std.json.Value, cmp_val: CompareValue) bool {
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
        .string => |s| {
            switch (cmp_val) {
                .string => |cs| return std.mem.order(u8, s, cs) == .gt,
                else => return false,
            }
        },
        else => return false,
    }
}

fn compareLt(field_val: std.json.Value, cmp_val: CompareValue) bool {
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
        .string => |s| {
            switch (cmp_val) {
                .string => |cs| return std.mem.order(u8, s, cs) == .lt,
                else => return false,
            }
        },
        else => return false,
    }
}

fn compareEq(field_val: std.json.Value, cmp_val: CompareValue) bool {
    switch (field_val) {
        .integer => |i| {
            switch (cmp_val) {
                .int => |ci| return i == ci,
                .float => |cf| return @as(f64, @floatFromInt(i)) == cf,
                else => return false,
            }
        },
        .float => |f| {
            switch (cmp_val) {
                .int => |ci| return f == @as(f64, @floatFromInt(ci)),
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
        .null => {
            return cmp_val == .null_val;
        },
        else => return false,
    }
}

// ============================================================================
// Output
// ============================================================================

fn writeJson(writer: anytype, value: std.json.Value, config: Config) !void {
    if (config.raw_strings) {
        switch (value) {
            .string => |s| {
                try writer.writeAll(s);
                return;
            },
            else => {},
        }
    }
    try std.json.stringify(value, .{}, writer);
}

// ============================================================================
// CLI
// ============================================================================

fn printUsage() void {
    const usage =
        \\Usage: zq [OPTIONS] <expression>
        \\
        \\ZQ is a high-performance NDJSON filter for JN pipelines.
        \\
        \\EXPRESSIONS:
        \\  .                  Pass through unchanged (identity)
        \\  .field             Extract single field
        \\  .a.b.c             Nested field path
        \\  .[0]               Array index (positive)
        \\  .[-1]              Array index (negative, from end)
        \\  .[]                Iterate array elements
        \\  .items[]           Iterate nested array
        \\
        \\  select(.field)     Filter by truthy value
        \\  select(.x > N)     Greater than comparison
        \\  select(.x < N)     Less than comparison
        \\  select(.x >= N)    Greater or equal
        \\  select(.x <= N)    Less or equal
        \\  select(.x == val)  Equality (string, number, bool, null)
        \\  select(.x != val)  Inequality
        \\
        \\  select(.a and .b)  Logical AND
        \\  select(.a or .b)   Logical OR
        \\  select(not .x)     Negation
        \\
        \\OPTIONS:
        \\  -c          Compact output (default, NDJSON compatible)
        \\  -r          Raw string output (no quotes around strings)
        \\  -e          Exit with error code if no output produced
        \\  --version   Print version and exit
        \\  --help      Print this help message
        \\
        \\EXAMPLES:
        \\  echo '{"name":"Alice","age":30}' | zq '.name'
        \\  cat data.ndjson | zq 'select(.age >= 18)'
        \\  cat data.ndjson | zq 'select(.active and .verified)'
        \\  cat data.ndjson | zq '.items[]'
        \\
    ;
    std.debug.print("{s}", .{usage});
}

fn printVersion() void {
    std.debug.print("zq {s}\n", .{version});
}

pub fn main() !void {
    const page_alloc = std.heap.page_allocator;

    const args = try std.process.argsAlloc(page_alloc);
    defer std.process.argsFree(page_alloc, args);

    var config = Config{};
    var expr_arg: ?[]const u8 = null;

    // Parse arguments
    var i: usize = 1;
    while (i < args.len) : (i += 1) {
        const arg = args[i];
        if (std.mem.eql(u8, arg, "--help") or std.mem.eql(u8, arg, "-h")) {
            printUsage();
            return;
        } else if (std.mem.eql(u8, arg, "--version")) {
            printVersion();
            return;
        } else if (std.mem.eql(u8, arg, "-c")) {
            config.compact = true;
        } else if (std.mem.eql(u8, arg, "-r")) {
            config.raw_strings = true;
        } else if (std.mem.eql(u8, arg, "-e")) {
            config.exit_on_empty = true;
        } else if (arg[0] != '-') {
            expr_arg = arg;
        } else {
            std.debug.print("Unknown option: {s}\n", .{arg});
            std.process.exit(1);
        }
    }

    if (expr_arg == null) {
        std.debug.print("Error: expression required\n\n", .{});
        printUsage();
        std.process.exit(1);
    }

    const expr = parseExpr(page_alloc, expr_arg.?) catch |err| {
        std.debug.print("Error parsing expression: {}\n", .{err});
        std.process.exit(1);
    };

    const stdin = std.io.getStdIn();
    const stdout = std.io.getStdOut();
    var buf_reader = std.io.bufferedReader(stdin.reader());
    var buf_writer = std.io.bufferedWriter(stdout.writer());
    const reader = buf_reader.reader();
    const writer = buf_writer.writer();

    var line_buf: [1024 * 1024]u8 = undefined; // 1MB line buffer
    var arena = std.heap.ArenaAllocator.init(page_alloc);
    defer arena.deinit();

    var output_count: usize = 0;

    while (reader.readUntilDelimiterOrEof(&line_buf, '\n')) |maybe_line| {
        const line = maybe_line orelse break;
        if (line.len == 0) continue;

        _ = arena.reset(.retain_capacity);

        const parsed = std.json.parseFromSlice(std.json.Value, arena.allocator(), line, .{}) catch {
            if (!config.skip_invalid) {
                std.debug.print("Error: malformed JSON\n", .{});
                std.process.exit(1);
            }
            continue;
        };
        const value = parsed.value;

        switch (expr) {
            .identity => {
                try writeJson(writer, value, config);
                try writer.writeByte('\n');
                output_count += 1;
            },
            .field => |field| {
                if (getFieldValue(value, field)) |v| {
                    try writeJson(writer, v, config);
                    try writer.writeByte('\n');
                    output_count += 1;
                }
            },
            .path => |path_expr| {
                if (getPathValue(value, path_expr)) |v| {
                    try writeJson(writer, v, config);
                    try writer.writeByte('\n');
                    output_count += 1;
                }
            },
            .select => |cond| {
                if (evalCondition(cond, value)) {
                    try writeJson(writer, value, config);
                    try writer.writeByte('\n');
                    output_count += 1;
                }
            },
            .iterate => |iter| {
                var target = value;
                if (iter.path.len > 0) {
                    target = getPath(value, iter.path) orelse continue;
                }
                switch (target) {
                    .array => |arr| {
                        for (arr.items) |item| {
                            try writeJson(writer, item, config);
                            try writer.writeByte('\n');
                            output_count += 1;
                        }
                    },
                    else => {},
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

    if (config.exit_on_empty and output_count == 0) {
        std.process.exit(1);
    }
}

fn getFieldValue(value: std.json.Value, field: FieldExpr) ?std.json.Value {
    var result: std.json.Value = undefined;
    switch (value) {
        .object => |obj| {
            result = obj.get(field.name) orelse return null;
        },
        else => return null,
    }

    if (field.index) |idx| {
        switch (idx) {
            .single => |i| return getIndex(result, i),
            .iterate => return null, // Use iterate expression instead
        }
    }

    return result;
}

fn getPathValue(value: std.json.Value, path_expr: PathExpr) ?std.json.Value {
    var result = getPath(value, path_expr.parts) orelse return null;

    if (path_expr.index) |idx| {
        switch (idx) {
            .single => |i| return getIndex(result, i),
            .iterate => return null,
        }
    }

    return result;
}

// ============================================================================
// Tests
// ============================================================================

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
    try std.testing.expectEqualStrings("name", expr.field.name);
}

test "parse path" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".foo.bar.baz");
    try std.testing.expect(expr == .path);
    try std.testing.expectEqual(@as(usize, 3), expr.path.parts.len);
}

test "parse select gt" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "select(.id > 50000)");
    try std.testing.expect(expr == .select);
    try std.testing.expect(expr.select.* == .simple);
    try std.testing.expect(expr.select.simple.op == .gt);
    try std.testing.expect(expr.select.simple.value.int == 50000);
}

test "parse select gte" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "select(.age >= 18)");
    try std.testing.expect(expr == .select);
    try std.testing.expect(expr.select.simple.op == .gte);
    try std.testing.expect(expr.select.simple.value.int == 18);
}

test "parse select lte" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "select(.score <= 100)");
    try std.testing.expect(expr == .select);
    try std.testing.expect(expr.select.simple.op == .lte);
    try std.testing.expect(expr.select.simple.value.int == 100);
}

test "parse select and" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "select(.active and .verified)");
    try std.testing.expect(expr == .select);
    try std.testing.expect(expr.select.* == .compound);
    try std.testing.expect(expr.select.compound.op == .and_op);
}

test "parse select or" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "select(.admin or .moderator)");
    try std.testing.expect(expr == .select);
    try std.testing.expect(expr.select.* == .compound);
    try std.testing.expect(expr.select.compound.op == .or_op);
}

test "parse select not" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "select(not .deleted)");
    try std.testing.expect(expr == .select);
    try std.testing.expect(expr.select.* == .negated);
}

test "parse iterate" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".[]");
    try std.testing.expect(expr == .iterate);
    try std.testing.expectEqual(@as(usize, 0), expr.iterate.path.len);
}

test "parse iterate nested" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".items[]");
    try std.testing.expect(expr == .iterate);
    try std.testing.expectEqual(@as(usize, 1), expr.iterate.path.len);
}

test "parse array index" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".items[0]");
    try std.testing.expect(expr == .field);
    try std.testing.expect(expr.field.index != null);
    try std.testing.expectEqual(@as(i64, 0), expr.field.index.?.single);
}

test "parse negative array index" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".items[-1]");
    try std.testing.expect(expr == .field);
    try std.testing.expect(expr.field.index != null);
    try std.testing.expectEqual(@as(i64, -1), expr.field.index.?.single);
}

test "eval condition and" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json_true = "{\"active\":true,\"verified\":true}";
    const json_false = "{\"active\":true,\"verified\":false}";

    const cond = try parseCondition(arena.allocator(), ".active and .verified");

    const parsed_true = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json_true, .{});
    const parsed_false = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json_false, .{});

    try std.testing.expect(evalCondition(cond, parsed_true.value));
    try std.testing.expect(!evalCondition(cond, parsed_false.value));
}

test "eval condition or" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json_admin = "{\"admin\":true,\"moderator\":false}";
    const json_mod = "{\"admin\":false,\"moderator\":true}";
    const json_neither = "{\"admin\":false,\"moderator\":false}";

    const cond = try parseCondition(arena.allocator(), ".admin or .moderator");

    const parsed_admin = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json_admin, .{});
    const parsed_mod = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json_mod, .{});
    const parsed_neither = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json_neither, .{});

    try std.testing.expect(evalCondition(cond, parsed_admin.value));
    try std.testing.expect(evalCondition(cond, parsed_mod.value));
    try std.testing.expect(!evalCondition(cond, parsed_neither.value));
}

test "eval condition not" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json_deleted = "{\"deleted\":true}";
    const json_active = "{\"deleted\":false}";

    const cond = try parseCondition(arena.allocator(), "not .deleted");

    const parsed_deleted = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json_deleted, .{});
    const parsed_active = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json_active, .{});

    try std.testing.expect(!evalCondition(cond, parsed_deleted.value));
    try std.testing.expect(evalCondition(cond, parsed_active.value));
}

test "getIndex positive" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[1,2,3,4,5]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const first = getIndex(parsed.value, 0);
    try std.testing.expect(first != null);
    try std.testing.expectEqual(@as(i64, 1), first.?.integer);

    const third = getIndex(parsed.value, 2);
    try std.testing.expect(third != null);
    try std.testing.expectEqual(@as(i64, 3), third.?.integer);
}

test "getIndex negative" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[1,2,3,4,5]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const last = getIndex(parsed.value, -1);
    try std.testing.expect(last != null);
    try std.testing.expectEqual(@as(i64, 5), last.?.integer);

    const second_last = getIndex(parsed.value, -2);
    try std.testing.expect(second_last != null);
    try std.testing.expectEqual(@as(i64, 4), second_last.?.integer);
}

test "getIndex out of bounds" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[1,2,3]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    try std.testing.expect(getIndex(parsed.value, 10) == null);
    try std.testing.expect(getIndex(parsed.value, -10) == null);
}
