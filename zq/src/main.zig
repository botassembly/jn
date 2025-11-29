const std = @import("std");

pub const version = "0.2.0";

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
    pipe: PipeExpr, // .x | .y
    object: ObjectExpr, // {a: .x, b: .y}
    builtin: BuiltinExpr, // tonumber, tostring, type, length, etc.
    alternative: AlternativeExpr, // .x // .y
    conditional: ConditionalExpr, // if .x then .a else .b end
    arithmetic: ArithmeticExpr, // .x + .y
    literal: LiteralExpr, // "string", 123, true, false, null
};

const LiteralExpr = union(enum) {
    string: []const u8,
    integer: i64,
    float: f64,
    boolean: bool,
    null_val,
};

const PipeExpr = struct {
    left: *Expr,
    right: *Expr,
};

const KeyType = union(enum) {
    literal: []const u8, // "a" in {a: .x}
    dynamic: *Expr, // (.key) in {(.key): .value}
};

const ObjectField = struct {
    key: KeyType,
    value: *Expr,
};

const ObjectExpr = struct {
    fields: []ObjectField,
};

const BuiltinKind = enum {
    tonumber,
    tostring,
    @"type",
    length,
    keys,
    values,
    // Type checks
    isnumber,
    isstring,
    isboolean,
    isnull,
    isarray,
    isobject,
};

const BuiltinExpr = struct {
    kind: BuiltinKind,
};

const AlternativeExpr = struct {
    primary: *Expr,
    fallback: *Expr,
};

const ConditionalExpr = struct {
    condition: *Condition,
    then_branch: *Expr,
    else_branch: *Expr,
};

const ArithOp = enum {
    add, // +
    sub, // -
    mul, // *
    div, // /
    mod, // %
};

const ArithmeticExpr = struct {
    left: *Expr,
    op: ArithOp,
    right: *Expr,
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

const ParseError = error{
    InvalidExpression,
    InvalidConditional,
    InvalidValue,
    OutOfMemory,
};

fn parseExpr(allocator: std.mem.Allocator, expr: []const u8) ParseError!Expr {
    const trimmed = std.mem.trim(u8, expr, " \t");

    // Check for pipe operator first (lowest precedence)
    // Need to find " | " not inside parentheses or braces
    var paren_depth: i32 = 0;
    var brace_depth: i32 = 0;
    var i: usize = 0;
    while (i < trimmed.len) : (i += 1) {
        const c = trimmed[i];
        if (c == '(') {
            paren_depth += 1;
        } else if (c == ')') {
            paren_depth -= 1;
        } else if (c == '{') {
            brace_depth += 1;
        } else if (c == '}') {
            brace_depth -= 1;
        } else if (c == '|' and paren_depth == 0 and brace_depth == 0) {
            // Check it's not // (alternative operator)
            if (i + 1 < trimmed.len and trimmed[i + 1] == '/') continue;
            if (i > 0 and trimmed[i - 1] == '/') continue;

            const left_str = std.mem.trim(u8, trimmed[0..i], " \t");
            const right_str = std.mem.trim(u8, trimmed[i + 1 ..], " \t");

            if (left_str.len > 0 and right_str.len > 0) {
                const left = try allocator.create(Expr);
                left.* = try parseExpr(allocator, left_str);
                const right = try allocator.create(Expr);
                right.* = try parseExpr(allocator, right_str);
                return .{ .pipe = .{ .left = left, .right = right } };
            }
        }
    }

    // Check for alternative operator (//)
    i = 0;
    paren_depth = 0;
    brace_depth = 0;
    while (i + 1 < trimmed.len) : (i += 1) {
        const c = trimmed[i];
        if (c == '(') {
            paren_depth += 1;
        } else if (c == ')') {
            paren_depth -= 1;
        } else if (c == '{') {
            brace_depth += 1;
        } else if (c == '}') {
            brace_depth -= 1;
        } else if (c == '/' and trimmed[i + 1] == '/' and paren_depth == 0 and brace_depth == 0) {
            const left_str = std.mem.trim(u8, trimmed[0..i], " \t");
            const right_str = std.mem.trim(u8, trimmed[i + 2 ..], " \t");

            if (left_str.len > 0 and right_str.len > 0) {
                const primary = try allocator.create(Expr);
                primary.* = try parseExpr(allocator, left_str);
                const fallback = try allocator.create(Expr);
                fallback.* = try parseExpr(allocator, right_str);
                return .{ .alternative = .{ .primary = primary, .fallback = fallback } };
            }
        }
    }

    // Check for arithmetic operators (+ - * / %) - with spaces around them
    // Lower precedence operators first (+ -)
    i = 0;
    paren_depth = 0;
    brace_depth = 0;
    while (i + 2 < trimmed.len) : (i += 1) {
        const c = trimmed[i];
        if (c == '(') {
            paren_depth += 1;
        } else if (c == ')') {
            paren_depth -= 1;
        } else if (c == '{') {
            brace_depth += 1;
        } else if (c == '}') {
            brace_depth -= 1;
        } else if (paren_depth == 0 and brace_depth == 0) {
            // Check for " + " or " - " (with spaces to avoid confusion with select comparisons)
            if (i > 0 and trimmed[i] == ' ' and (trimmed[i + 1] == '+' or trimmed[i + 1] == '-') and i + 2 < trimmed.len and trimmed[i + 2] == ' ') {
                const op: ArithOp = if (trimmed[i + 1] == '+') .add else .sub;
                const left_str = std.mem.trim(u8, trimmed[0..i], " \t");
                const right_str = std.mem.trim(u8, trimmed[i + 3 ..], " \t");

                if (left_str.len > 0 and right_str.len > 0) {
                    const left = try allocator.create(Expr);
                    left.* = try parseExpr(allocator, left_str);
                    const right = try allocator.create(Expr);
                    right.* = try parseExpr(allocator, right_str);
                    return .{ .arithmetic = .{ .left = left, .op = op, .right = right } };
                }
            }
        }
    }

    // Higher precedence operators (* / %)
    i = 0;
    paren_depth = 0;
    brace_depth = 0;
    while (i + 2 < trimmed.len) : (i += 1) {
        const c = trimmed[i];
        if (c == '(') {
            paren_depth += 1;
        } else if (c == ')') {
            paren_depth -= 1;
        } else if (c == '{') {
            brace_depth += 1;
        } else if (c == '}') {
            brace_depth -= 1;
        } else if (paren_depth == 0 and brace_depth == 0) {
            if (i > 0 and trimmed[i] == ' ' and (trimmed[i + 1] == '*' or trimmed[i + 1] == '/' or trimmed[i + 1] == '%') and i + 2 < trimmed.len and trimmed[i + 2] == ' ') {
                // Make sure it's not // (already handled)
                if (trimmed[i + 1] == '/' and i + 3 < trimmed.len and trimmed[i + 2] == '/') continue;

                const op: ArithOp = switch (trimmed[i + 1]) {
                    '*' => .mul,
                    '/' => .div,
                    '%' => .mod,
                    else => unreachable,
                };
                const left_str = std.mem.trim(u8, trimmed[0..i], " \t");
                const right_str = std.mem.trim(u8, trimmed[i + 3 ..], " \t");

                if (left_str.len > 0 and right_str.len > 0) {
                    const left = try allocator.create(Expr);
                    left.* = try parseExpr(allocator, left_str);
                    const right = try allocator.create(Expr);
                    right.* = try parseExpr(allocator, right_str);
                    return .{ .arithmetic = .{ .left = left, .op = op, .right = right } };
                }
            }
        }
    }

    // Identity
    if (std.mem.eql(u8, trimmed, ".")) {
        return .identity;
    }

    // Root iteration: .[]
    if (std.mem.eql(u8, trimmed, ".[]")) {
        return .{ .iterate = .{ .path = &[_][]const u8{} } };
    }

    // Builtin functions (no arguments)
    if (std.mem.eql(u8, trimmed, "tonumber")) return .{ .builtin = .{ .kind = .tonumber } };
    if (std.mem.eql(u8, trimmed, "tostring")) return .{ .builtin = .{ .kind = .tostring } };
    if (std.mem.eql(u8, trimmed, "type")) return .{ .builtin = .{ .kind = .@"type" } };
    if (std.mem.eql(u8, trimmed, "length")) return .{ .builtin = .{ .kind = .length } };
    if (std.mem.eql(u8, trimmed, "keys")) return .{ .builtin = .{ .kind = .keys } };
    if (std.mem.eql(u8, trimmed, "values")) return .{ .builtin = .{ .kind = .values } };
    if (std.mem.eql(u8, trimmed, "isnumber")) return .{ .builtin = .{ .kind = .isnumber } };
    if (std.mem.eql(u8, trimmed, "isstring")) return .{ .builtin = .{ .kind = .isstring } };
    if (std.mem.eql(u8, trimmed, "isboolean")) return .{ .builtin = .{ .kind = .isboolean } };
    if (std.mem.eql(u8, trimmed, "isnull")) return .{ .builtin = .{ .kind = .isnull } };
    if (std.mem.eql(u8, trimmed, "isarray")) return .{ .builtin = .{ .kind = .isarray } };
    if (std.mem.eql(u8, trimmed, "isobject")) return .{ .builtin = .{ .kind = .isobject } };

    // If-then-else conditional
    if (std.mem.startsWith(u8, trimmed, "if ")) {
        return try parseConditional(allocator, trimmed);
    }

    // Select expression
    if (std.mem.startsWith(u8, trimmed, "select(") and std.mem.endsWith(u8, trimmed, ")")) {
        const inner = trimmed[7 .. trimmed.len - 1];
        const condition = try parseCondition(allocator, inner);
        return .{ .select = condition };
    }

    // Object construction: {a: .x, b: .y}
    if (trimmed[0] == '{' and trimmed[trimmed.len - 1] == '}') {
        return try parseObject(allocator, trimmed);
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

    // String literal: "..."
    if (trimmed.len >= 2 and trimmed[0] == '"' and trimmed[trimmed.len - 1] == '"') {
        return .{ .literal = .{ .string = trimmed[1 .. trimmed.len - 1] } };
    }

    // Boolean literals
    if (std.mem.eql(u8, trimmed, "true")) {
        return .{ .literal = .{ .boolean = true } };
    }
    if (std.mem.eql(u8, trimmed, "false")) {
        return .{ .literal = .{ .boolean = false } };
    }

    // Null literal
    if (std.mem.eql(u8, trimmed, "null")) {
        return .{ .literal = .null_val };
    }

    // Number literal (integer)
    if (std.fmt.parseInt(i64, trimmed, 10)) |int_val| {
        return .{ .literal = .{ .integer = int_val } };
    } else |_| {}

    // Number literal (float)
    if (std.fmt.parseFloat(f64, trimmed)) |float_val| {
        return .{ .literal = .{ .float = float_val } };
    } else |_| {}

    return error.InvalidExpression;
}

fn parseConditional(allocator: std.mem.Allocator, expr: []const u8) ParseError!Expr {
    // Format: if <condition> then <expr> else <expr> end
    const trimmed = std.mem.trim(u8, expr, " \t");

    // Find "then" keyword
    var then_pos: ?usize = null;
    var paren_depth: i32 = 0;
    var i: usize = 3; // Skip "if "
    while (i + 4 < trimmed.len) : (i += 1) {
        if (trimmed[i] == '(') paren_depth += 1;
        if (trimmed[i] == ')') paren_depth -= 1;
        if (paren_depth == 0 and std.mem.eql(u8, trimmed[i .. i + 5], " then")) {
            then_pos = i;
            break;
        }
    }

    if (then_pos == null) return error.InvalidConditional;

    // Find "else" keyword
    var else_pos: ?usize = null;
    i = then_pos.? + 5;
    paren_depth = 0;
    while (i + 4 < trimmed.len) : (i += 1) {
        if (trimmed[i] == '(') paren_depth += 1;
        if (trimmed[i] == ')') paren_depth -= 1;
        if (paren_depth == 0 and std.mem.eql(u8, trimmed[i .. i + 5], " else")) {
            else_pos = i;
            break;
        }
    }

    if (else_pos == null) return error.InvalidConditional;

    // Check for "end" at the end
    if (!std.mem.endsWith(u8, trimmed, " end") and !std.mem.endsWith(u8, trimmed, "end")) {
        return error.InvalidConditional;
    }

    const end_pos = if (std.mem.endsWith(u8, trimmed, " end"))
        trimmed.len - 4
    else
        trimmed.len - 3;

    const cond_str = std.mem.trim(u8, trimmed[3..then_pos.?], " \t");
    const then_str = std.mem.trim(u8, trimmed[then_pos.? + 5 .. else_pos.?], " \t");
    const else_str = std.mem.trim(u8, trimmed[else_pos.? + 5 .. end_pos], " \t");

    const condition = try parseCondition(allocator, cond_str);
    const then_branch = try allocator.create(Expr);
    then_branch.* = try parseExpr(allocator, then_str);
    const else_branch = try allocator.create(Expr);
    else_branch.* = try parseExpr(allocator, else_str);

    return .{ .conditional = .{
        .condition = condition,
        .then_branch = then_branch,
        .else_branch = else_branch,
    } };
}

fn parseObject(allocator: std.mem.Allocator, expr: []const u8) ParseError!Expr {
    // Format: {key1: val1, key2: val2, ...}
    const inner = std.mem.trim(u8, expr[1 .. expr.len - 1], " \t");

    if (inner.len == 0) {
        // Empty object
        return .{ .object = .{ .fields = &[_]ObjectField{} } };
    }

    var fields = std.ArrayList(ObjectField).init(allocator);

    // Split by comma (respecting nesting)
    var start: usize = 0;
    var paren_depth: i32 = 0;
    var brace_depth: i32 = 0;
    var i: usize = 0;

    while (i <= inner.len) : (i += 1) {
        const at_end = i == inner.len;
        const c = if (at_end) ',' else inner[i];

        if (c == '(') paren_depth += 1;
        if (c == ')') paren_depth -= 1;
        if (c == '{') brace_depth += 1;
        if (c == '}') brace_depth -= 1;

        if ((c == ',' or at_end) and paren_depth == 0 and brace_depth == 0) {
            const field_str = std.mem.trim(u8, inner[start..i], " \t");
            if (field_str.len > 0) {
                const field = try parseObjectField(allocator, field_str);
                try fields.append(field);
            }
            start = i + 1;
        }
    }

    return .{ .object = .{ .fields = try fields.toOwnedSlice() } };
}

fn parseObjectField(allocator: std.mem.Allocator, field_str: []const u8) ParseError!ObjectField {
    // Format: key: value or (expr): value or shorthand key
    const trimmed = std.mem.trim(u8, field_str, " \t");

    // Find colon (respecting parentheses)
    var colon_pos: ?usize = null;
    var paren_depth: i32 = 0;
    var i: usize = 0;
    while (i < trimmed.len) : (i += 1) {
        if (trimmed[i] == '(') paren_depth += 1;
        if (trimmed[i] == ')') paren_depth -= 1;
        if (trimmed[i] == ':' and paren_depth == 0) {
            colon_pos = i;
            break;
        }
    }

    if (colon_pos) |pos| {
        const key_part = std.mem.trim(u8, trimmed[0..pos], " \t");
        const val_part = std.mem.trim(u8, trimmed[pos + 1 ..], " \t");

        var key: KeyType = undefined;
        if (key_part[0] == '(' and key_part[key_part.len - 1] == ')') {
            // Dynamic key: (.field)
            const key_expr = try allocator.create(Expr);
            key_expr.* = try parseExpr(allocator, key_part[1 .. key_part.len - 1]);
            key = .{ .dynamic = key_expr };
        } else {
            // Literal key
            key = .{ .literal = key_part };
        }

        const value = try allocator.create(Expr);
        value.* = try parseExpr(allocator, val_part);

        return ObjectField{ .key = key, .value = value };
    } else {
        // Shorthand: just "foo" means {foo: .foo}
        const value = try allocator.create(Expr);
        const field_path = try std.fmt.allocPrint(allocator, ".{s}", .{trimmed});
        value.* = try parseExpr(allocator, field_path);
        return ObjectField{ .key = .{ .literal = trimmed }, .value = value };
    }
}

fn parseCondition(allocator: std.mem.Allocator, expr: []const u8) ParseError!*Condition {
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

fn parseSimpleCondition(allocator: std.mem.Allocator, expr: []const u8) ParseError!SimpleCondition {
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

fn parsePath(allocator: std.mem.Allocator, expr: []const u8) ParseError![][]const u8 {
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

fn parseValue(str: []const u8) ParseError!CompareValue {
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
// Expression Evaluation
// ============================================================================

const EvalError = error{
    OutOfMemory,
};

const EvalResult = struct {
    values: []std.json.Value,
    allocator: std.mem.Allocator,

    fn single(alloc: std.mem.Allocator, value: std.json.Value) EvalError!EvalResult {
        var vals = try alloc.alloc(std.json.Value, 1);
        vals[0] = value;
        return EvalResult{ .values = vals, .allocator = alloc };
    }

    fn empty(alloc: std.mem.Allocator) EvalResult {
        return EvalResult{ .values = &[_]std.json.Value{}, .allocator = alloc };
    }

    fn multi(alloc: std.mem.Allocator, values: []std.json.Value) EvalResult {
        return EvalResult{ .values = values, .allocator = alloc };
    }
};

fn evalExpr(allocator: std.mem.Allocator, expr: *const Expr, value: std.json.Value) EvalError!EvalResult {
    switch (expr.*) {
        .identity => return try EvalResult.single(allocator, value),

        .field => |field| {
            if (getFieldValue(value, field)) |v| {
                return try EvalResult.single(allocator, v);
            }
            return EvalResult.empty(allocator);
        },

        .path => |path_expr| {
            if (getPathValue(value, path_expr)) |v| {
                return try EvalResult.single(allocator, v);
            }
            return EvalResult.empty(allocator);
        },

        .select => |cond| {
            if (evalCondition(cond, value)) {
                return try EvalResult.single(allocator, value);
            }
            return EvalResult.empty(allocator);
        },

        .iterate => |iter| {
            var target = value;
            if (iter.path.len > 0) {
                target = getPath(value, iter.path) orelse return EvalResult.empty(allocator);
            }
            switch (target) {
                .array => |arr| {
                    var results = try allocator.alloc(std.json.Value, arr.items.len);
                    for (arr.items, 0..) |item, i| {
                        results[i] = item;
                    }
                    return EvalResult.multi(allocator, results);
                },
                else => return EvalResult.empty(allocator),
            }
        },

        .pipe => |pipe| {
            // Evaluate left side, then for each result evaluate right side
            const left_results = try evalExpr(allocator, pipe.left, value);
            var all_results = std.ArrayList(std.json.Value).init(allocator);

            for (left_results.values) |left_val| {
                const right_results = try evalExpr(allocator, pipe.right, left_val);
                try all_results.appendSlice(right_results.values);
            }

            return EvalResult.multi(allocator, try all_results.toOwnedSlice());
        },

        .builtin => |builtin| {
            return evalBuiltin(allocator, builtin.kind, value);
        },

        .alternative => |alt| {
            const primary_result = try evalExpr(allocator, alt.primary, value);
            // If primary produces non-null, non-false results, use them
            for (primary_result.values) |v| {
                switch (v) {
                    .null => continue,
                    .bool => |b| if (!b) continue,
                    else => return try EvalResult.single(allocator, v),
                }
            }
            // Fall back to secondary
            return evalExpr(allocator, alt.fallback, value);
        },

        .conditional => |cond| {
            if (evalCondition(cond.condition, value)) {
                return evalExpr(allocator, cond.then_branch, value);
            } else {
                return evalExpr(allocator, cond.else_branch, value);
            }
        },

        .object => |obj| {
            return try evalObject(allocator, obj, value);
        },

        .arithmetic => |arith| {
            return try evalArithmetic(allocator, arith, value);
        },

        .literal => |lit| {
            const json_val: std.json.Value = switch (lit) {
                .string => |s| .{ .string = s },
                .integer => |i| .{ .integer = i },
                .float => |f| .{ .float = f },
                .boolean => |b| .{ .bool = b },
                .null_val => .null,
            };
            return try EvalResult.single(allocator, json_val);
        },
    }
}

fn evalBuiltin(allocator: std.mem.Allocator, kind: BuiltinKind, value: std.json.Value) EvalError!EvalResult {
    switch (kind) {
        .tonumber => {
            switch (value) {
                .integer => return try EvalResult.single(allocator, value),
                .float => return try EvalResult.single(allocator, value),
                .string => |s| {
                    // Try to parse as number
                    if (std.fmt.parseInt(i64, s, 10)) |i| {
                        return try EvalResult.single(allocator, .{ .integer = i });
                    } else |_| {
                        if (std.fmt.parseFloat(f64, s)) |f| {
                            return try EvalResult.single(allocator, .{ .float = f });
                        } else |_| {
                            return EvalResult.empty(allocator);
                        }
                    }
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .tostring => {
            switch (value) {
                .string => return try EvalResult.single(allocator, value),
                .integer => |i| {
                    const str = try std.fmt.allocPrint(allocator, "{d}", .{i});
                    return try EvalResult.single(allocator, .{ .string = str });
                },
                .float => |f| {
                    const str = try std.fmt.allocPrint(allocator, "{d}", .{f});
                    return try EvalResult.single(allocator, .{ .string = str });
                },
                .bool => |b| {
                    return try EvalResult.single(allocator, .{ .string = if (b) "true" else "false" });
                },
                .null => {
                    return try EvalResult.single(allocator, .{ .string = "null" });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .@"type" => {
            const type_str: []const u8 = switch (value) {
                .null => "null",
                .bool => "boolean",
                .integer, .float => "number",
                .string => "string",
                .array => "array",
                .object => "object",
                else => "unknown",
            };
            return try EvalResult.single(allocator, .{ .string = type_str });
        },
        .length => {
            switch (value) {
                .string => |s| {
                    return try EvalResult.single(allocator, .{ .integer = @as(i64, @intCast(s.len)) });
                },
                .array => |arr| {
                    return try EvalResult.single(allocator, .{ .integer = @as(i64, @intCast(arr.items.len)) });
                },
                .object => |obj| {
                    return try EvalResult.single(allocator, .{ .integer = @as(i64, @intCast(obj.count())) });
                },
                .null => {
                    return try EvalResult.single(allocator, .{ .integer = 0 });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .keys => {
            switch (value) {
                .object => |obj| {
                    var keys = try allocator.alloc(std.json.Value, obj.count());
                    var i: usize = 0;
                    var iter = obj.iterator();
                    while (iter.next()) |entry| {
                        keys[i] = .{ .string = entry.key_ptr.* };
                        i += 1;
                    }
                    return try EvalResult.single(allocator, .{ .array = .{ .items = keys, .capacity = keys.len, .allocator = allocator } });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .values => {
            switch (value) {
                .object => |obj| {
                    var vals = try allocator.alloc(std.json.Value, obj.count());
                    var i: usize = 0;
                    var iter = obj.iterator();
                    while (iter.next()) |entry| {
                        vals[i] = entry.value_ptr.*;
                        i += 1;
                    }
                    return try EvalResult.single(allocator, .{ .array = .{ .items = vals, .capacity = vals.len, .allocator = allocator } });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .isnumber => {
            const result = switch (value) {
                .integer, .float => true,
                else => false,
            };
            return try EvalResult.single(allocator, .{ .bool = result });
        },
        .isstring => {
            const result = value == .string;
            return try EvalResult.single(allocator, .{ .bool = result });
        },
        .isboolean => {
            const result = value == .bool;
            return try EvalResult.single(allocator, .{ .bool = result });
        },
        .isnull => {
            const result = value == .null;
            return try EvalResult.single(allocator, .{ .bool = result });
        },
        .isarray => {
            const result = value == .array;
            return try EvalResult.single(allocator, .{ .bool = result });
        },
        .isobject => {
            const result = value == .object;
            return try EvalResult.single(allocator, .{ .bool = result });
        },
    }
}

fn evalObject(allocator: std.mem.Allocator, obj: ObjectExpr, value: std.json.Value) EvalError!EvalResult {
    var map = std.json.ObjectMap.init(allocator);

    for (obj.fields) |field| {
        // Evaluate key
        const key: []const u8 = switch (field.key) {
            .literal => |lit| lit,
            .dynamic => |key_expr| blk: {
                const key_result = try evalExpr(allocator, key_expr, value);
                if (key_result.values.len == 0) continue;
                switch (key_result.values[0]) {
                    .string => |s| break :blk s,
                    else => continue,
                }
            },
        };

        // Evaluate value
        const val_result = try evalExpr(allocator, field.value, value);
        if (val_result.values.len > 0) {
            try map.put(key, val_result.values[0]);
        }
    }

    return try EvalResult.single(allocator, .{ .object = map });
}

fn evalArithmetic(allocator: std.mem.Allocator, arith: ArithmeticExpr, value: std.json.Value) EvalError!EvalResult {
    const left_result = try evalExpr(allocator, arith.left, value);
    const right_result = try evalExpr(allocator, arith.right, value);

    if (left_result.values.len == 0 or right_result.values.len == 0) {
        return EvalResult.empty(allocator);
    }

    const left_val = left_result.values[0];
    const right_val = right_result.values[0];

    // String concatenation with +
    if (arith.op == .add) {
        if (left_val == .string and right_val == .string) {
            const result = try std.fmt.allocPrint(allocator, "{s}{s}", .{ left_val.string, right_val.string });
            return try EvalResult.single(allocator, .{ .string = result });
        }
    }

    // Numeric operations
    const left_num = getNumeric(left_val) orelse return EvalResult.empty(allocator);
    const right_num = getNumeric(right_val) orelse return EvalResult.empty(allocator);

    const result: f64 = switch (arith.op) {
        .add => left_num + right_num,
        .sub => left_num - right_num,
        .mul => left_num * right_num,
        .div => if (right_num != 0) left_num / right_num else return EvalResult.empty(allocator),
        .mod => @mod(left_num, right_num),
    };

    // Return integer if both inputs were integers and result is whole
    if (left_val == .integer and right_val == .integer and @trunc(result) == result) {
        return try EvalResult.single(allocator, .{ .integer = @as(i64, @intFromFloat(result)) });
    }
    return try EvalResult.single(allocator, .{ .float = result });
}

fn getNumeric(value: std.json.Value) ?f64 {
    return switch (value) {
        .integer => |i| @as(f64, @floatFromInt(i)),
        .float => |f| f,
        else => null,
    };
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
        \\PIPES:
        \\  .x | .y            Chain expressions
        \\  .x | tonumber      Transform values
        \\  select(.a) | .b    Filter then extract
        \\
        \\OBJECT CONSTRUCTION:
        \\  {a: .x, b: .y}     Create object with fields
        \\  {a, b}             Shorthand for {a: .a, b: .b}
        \\  {(.key): .value}   Dynamic key from field
        \\
        \\TYPE FUNCTIONS:
        \\  tonumber           String to number
        \\  tostring           Any to string
        \\  type               Returns type name
        \\  length             String/array/object length
        \\  keys               Object keys as array
        \\  values             Object values as array
        \\
        \\TYPE CHECKS:
        \\  isnumber           True if number
        \\  isstring           True if string
        \\  isboolean          True if boolean
        \\  isnull             True if null
        \\  isarray            True if array
        \\  isobject           True if object
        \\
        \\CONTROL FLOW:
        \\  .x // .y           Alternative (first non-null)
        \\  if .x then .a else .b end
        \\
        \\ARITHMETIC:
        \\  .x + .y            Addition / string concat
        \\  .x - .y            Subtraction
        \\  .x * .y            Multiplication
        \\  .x / .y            Division
        \\  .x % .y            Modulo
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
        \\  echo '{"x":"42"}' | zq '.x | tonumber'
        \\  echo '{"a":1,"b":2}' | zq '{sum: .a + .b}'
        \\  echo '{"x":null,"y":1}' | zq '.x // .y'
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

        const results = evalExpr(arena.allocator(), &expr, value) catch |err| {
            std.debug.print("Evaluation error: {}\n", .{err});
            continue;
        };

        for (results.values) |result| {
            try writeJson(writer, result, config);
            try writer.writeByte('\n');
            output_count += 1;
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
            .single => |ind| return getIndex(result, ind),
            .iterate => return null, // Use iterate expression instead
        }
    }

    return result;
}

fn getPathValue(value: std.json.Value, path_expr: PathExpr) ?std.json.Value {
    var result = getPath(value, path_expr.parts) orelse return null;

    if (path_expr.index) |idx| {
        switch (idx) {
            .single => |ind| return getIndex(result, ind),
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

// ============================================================================
// Sprint 02 Tests: Pipes, Objects, Type Functions, etc.
// ============================================================================

test "parse pipe" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".x | tonumber");
    try std.testing.expect(expr == .pipe);
}

test "parse object literal" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "{a: .x, b: .y}");
    try std.testing.expect(expr == .object);
    try std.testing.expectEqual(@as(usize, 2), expr.object.fields.len);
}

test "parse alternative" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".x // .y");
    try std.testing.expect(expr == .alternative);
}

test "parse conditional" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "if .x > 5 then .a else .b end");
    try std.testing.expect(expr == .conditional);
}

test "parse arithmetic add" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".x + .y");
    try std.testing.expect(expr == .arithmetic);
    try std.testing.expect(expr.arithmetic.op == .add);
}

test "parse builtin tonumber" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "tonumber");
    try std.testing.expect(expr == .builtin);
    try std.testing.expect(expr.builtin.kind == .tonumber);
}

test "parse literal string" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "\"hello\"");
    try std.testing.expect(expr == .literal);
    try std.testing.expect(expr.literal == .string);
    try std.testing.expectEqualStrings("hello", expr.literal.string);
}

test "parse literal number" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "42");
    try std.testing.expect(expr == .literal);
    try std.testing.expect(expr.literal == .integer);
    try std.testing.expectEqual(@as(i64, 42), expr.literal.integer);
}

test "eval pipe" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":\"42\"}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), ".x | tonumber");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 42), result.values[0].integer);
}

test "eval object construction" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":1,\"y\":2}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "{a: .x, b: .y}");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0] == .object);
    try std.testing.expectEqual(@as(i64, 1), result.values[0].object.get("a").?.integer);
    try std.testing.expectEqual(@as(i64, 2), result.values[0].object.get("b").?.integer);
}

test "eval alternative with null" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":null,\"y\":1}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), ".x // .y");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 1), result.values[0].integer);
}

test "eval arithmetic" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"a\":10,\"b\":3}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), ".a + .b");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 13), result.values[0].integer);
}

test "eval string concatenation" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"a\":\"foo\",\"b\":\"bar\"}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), ".a + .b");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqualStrings("foobar", result.values[0].string);
}

test "eval conditional true" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":10}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "if .x > 5 then .x else .y end");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 10), result.values[0].integer);
}

test "eval type function" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":1}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "type");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqualStrings("object", result.values[0].string);
}

test "eval length function" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "length");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 5), result.values[0].integer);
}
