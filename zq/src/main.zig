const std = @import("std");
const zig_builtin = @import("builtin");

pub const version = "0.4.0";

// Helper to read a line from reader, compatible with both Zig 0.15.1 and 0.15.2
// In 0.15.2+, use takeDelimiter which returns null at EOF
// In 0.15.1, use takeDelimiterExclusive which throws EndOfStream at EOF
fn readLine(reader: anytype) ?[]u8 {
    // Use comptime version check to select the right API
    if (comptime zig_builtin.zig_version.order(.{ .major = 0, .minor = 15, .patch = 2 }) != .lt) {
        // Zig 0.15.2+ has takeDelimiter which returns null at EOF
        return reader.takeDelimiter('\n') catch |err| {
            std.debug.print("Read error: {}\n", .{err});
            std.process.exit(1);
        };
    } else {
        // Zig 0.15.1 uses takeDelimiterExclusive which throws EndOfStream
        return reader.takeDelimiterExclusive('\n') catch |err| switch (err) {
            error.EndOfStream => return null,
            else => {
                std.debug.print("Read error: {}\n", .{err});
                std.process.exit(1);
            },
        };
    }
}

// Whitespace characters for trimming (includes newlines for multi-line expressions)
const whitespace = " \t\n\r";

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
    // Left side can be an expression (e.g., ".revenue | tonumber") or a simple path
    left_expr: ?*Expr = null,
    path: [][]const u8 = &[_][]const u8{},
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
    slice: SliceExpr, // .[n:m]
};

const SliceExpr = struct {
    start: ?i64, // null means from beginning
    end: ?i64, // null means to end
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
    // Sprint 03 additions
    str_func: StrFuncExpr, // split(sep), join(sep), etc.
    map: MapExpr, // map(expr)
    by_func: ByFuncExpr, // group_by(.field), sort_by(.field), etc.
    array: ArrayExpr, // [.x, .y, .z]
    del: DelExpr, // del(.key)
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
    type,
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
    // Array functions (Sprint 03)
    first,
    last,
    reverse,
    sort,
    unique,
    flatten,
    // Aggregation functions (Sprint 03)
    add,
    min,
    max,
    // String functions (Sprint 03)
    ascii_downcase,
    ascii_upcase,
    to_entries,
    from_entries,
    // Math functions (Sprint 05)
    floor,
    ceil,
    round,
    fabs,
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
    optional: bool = false, // .foo? syntax
};

const PathExpr = struct {
    parts: [][]const u8,
    index: ?IndexExpr = null,
    optional: bool = false, // .foo.bar? syntax
};

const IterateExpr = struct {
    path: [][]const u8, // empty means root
};

// Sprint 03: String functions with string argument
const StrFuncKind = enum {
    split, // split(",")
    join, // join(",")
    startswith, // startswith("http")
    endswith, // endswith(".json")
    contains, // contains("foo")
    ltrimstr, // ltrimstr("prefix")
    rtrimstr, // rtrimstr("suffix")
    has, // has("key")
    @"test", // test("pattern") - regex-like matching
};

const StrFuncExpr = struct {
    kind: StrFuncKind,
    arg: []const u8,
};

// Sprint 03: map(expr)
const MapExpr = struct {
    inner: *Expr,
};

// Sprint 03: group_by, sort_by, unique_by, min_by, max_by
const ByFuncKind = enum {
    group_by,
    sort_by,
    unique_by,
    min_by,
    max_by,
};

const ByFuncExpr = struct {
    kind: ByFuncKind,
    path: [][]const u8,
};

// Sprint 03: Array literal [.x, .y, .z]
const ArrayExpr = struct {
    elements: []*Expr,
};

const DelExpr = struct {
    paths: [][]const u8, // paths to delete (e.g., ["x"] or ["a", "b"] for .a.b)
    index: ?i64 = null, // optional array index (e.g., 0 for del(.arr[0]))
};

const Config = struct {
    compact: bool = true,
    raw_strings: bool = false,
    exit_on_empty: bool = false,
    skip_invalid: bool = true,
    slurp: bool = false,
};

// ============================================================================
// Parser
// ============================================================================

const ParseError = error{
    InvalidExpression,
    InvalidConditional,
    InvalidValue,
    OutOfMemory,
    UnsupportedFeature,
};

/// Maximum recursion depth for expression parsing to prevent stack overflow
/// from maliciously crafted deeply nested expressions
const MAX_PARSE_DEPTH: u32 = 100;

/// Error context for better error messages when parsing fails.
/// Passed as an output parameter to avoid global mutable state.
const ErrorContext = struct {
    expression: []const u8 = "",
    feature: []const u8 = "",
    suggestion: []const u8 = "",
    /// Current parsing recursion depth
    depth: u32 = 0,
};

/// Check for jq features not supported by ZQ and provide helpful error messages.
/// The err_ctx output parameter receives error details if an unsupported feature is found.
fn checkUnsupportedFeatures(expr: []const u8, err_ctx: *ErrorContext) ParseError!void {
    const trimmed = std.mem.trim(u8, expr, whitespace);

    // Check for variable declarations ($var)
    if (std.mem.indexOf(u8, trimmed, " as $")) |_| {
        err_ctx.* = .{
            .expression = trimmed,
            .feature = "variable binding (as $var)",
            .suggestion = "Use pipes instead: .items[] | select(.x > 0) | .name",
        };
        return error.UnsupportedFeature;
    }

    // Check for variable references ($var) - but not string interpolation
    var i: usize = 0;
    while (i < trimmed.len) : (i += 1) {
        if (trimmed[i] == '$' and i + 1 < trimmed.len) {
            const next = trimmed[i + 1];
            // Check if it's a variable (letter or underscore after $)
            if ((next >= 'a' and next <= 'z') or (next >= 'A' and next <= 'Z') or next == '_') {
                err_ctx.* = .{
                    .expression = trimmed,
                    .feature = "variables ($var)",
                    .suggestion = "ZQ doesn't support variables. Restructure with pipes.",
                };
                return error.UnsupportedFeature;
            }
        }
    }

    // Check for regex functions (test() is supported with basic patterns)
    const regex_funcs = [_][]const u8{ "match(", "capture(", "scan(", "splits(", "sub(", "gsub(" };
    for (regex_funcs) |func| {
        if (std.mem.indexOf(u8, trimmed, func)) |_| {
            err_ctx.* = .{
                .expression = trimmed,
                .feature = func[0 .. func.len - 1],
                .suggestion = "Use test(), contains(), startswith(), or endswith() instead",
            };
            return error.UnsupportedFeature;
        }
    }

    // Check for module imports
    if (std.mem.startsWith(u8, trimmed, "import ") or std.mem.startsWith(u8, trimmed, "include ")) {
        err_ctx.* = .{
            .expression = trimmed,
            .feature = "module imports",
            .suggestion = "ZQ doesn't support modules. Use inline expressions.",
        };
        return error.UnsupportedFeature;
    }

    // Check for reduce
    if (std.mem.startsWith(u8, trimmed, "reduce ")) {
        err_ctx.* = .{
            .expression = trimmed,
            .feature = "reduce",
            .suggestion = "Use add, min, max, or group_by instead",
        };
        return error.UnsupportedFeature;
    }

    // Check for limit
    if (std.mem.startsWith(u8, trimmed, "limit(")) {
        err_ctx.* = .{
            .expression = trimmed,
            .feature = "limit()",
            .suggestion = "Use 'head -n N' after the pipeline: zq '.' | head -n 10",
        };
        return error.UnsupportedFeature;
    }

    // Check for recursive descent (..)
    if (std.mem.indexOf(u8, trimmed, "..")) |pos| {
        // Make sure it's not // (alternative operator)
        if (pos == 0 or trimmed[pos - 1] != '/') {
            err_ctx.* = .{
                .expression = trimmed,
                .feature = "recursive descent (..)",
                .suggestion = "Use explicit paths instead: .items[].nested",
            };
            return error.UnsupportedFeature;
        }
    }

    // Check for recurse/walk
    if (std.mem.indexOf(u8, trimmed, "recurse") != null or std.mem.indexOf(u8, trimmed, "walk(") != null) {
        err_ctx.* = .{
            .expression = trimmed,
            .feature = "recurse/walk",
            .suggestion = "Use explicit iteration: .items[] | .children[]",
        };
        return error.UnsupportedFeature;
    }

    // Check for path functions
    const path_funcs = [_][]const u8{ "path(", "getpath(", "setpath(", "delpaths(" };
    for (path_funcs) |func| {
        if (std.mem.indexOf(u8, trimmed, func)) |_| {
            err_ctx.* = .{
                .expression = trimmed,
                .feature = func[0 .. func.len - 1],
                .suggestion = "Use direct field access: .path.to.field",
            };
            return error.UnsupportedFeature;
        }
    }

    // Check for debug/input functions
    if (std.mem.indexOf(u8, trimmed, "debug") != null) {
        err_ctx.* = .{
            .expression = trimmed,
            .feature = "debug",
            .suggestion = "ZQ doesn't have debug output. Use stderr redirection.",
        };
        return error.UnsupportedFeature;
    }

    if (std.mem.eql(u8, trimmed, "input") or std.mem.eql(u8, trimmed, "inputs")) {
        err_ctx.* = .{
            .expression = trimmed,
            .feature = "input/inputs",
            .suggestion = "ZQ reads from stdin automatically. Just use '.'",
        };
        return error.UnsupportedFeature;
    }

    // Check for @base64 and other format strings
    if (std.mem.indexOf(u8, trimmed, "@base64") != null or
        std.mem.indexOf(u8, trimmed, "@uri") != null or
        std.mem.indexOf(u8, trimmed, "@csv") != null or
        std.mem.indexOf(u8, trimmed, "@html") != null or
        std.mem.indexOf(u8, trimmed, "@json") != null or
        std.mem.indexOf(u8, trimmed, "@text") != null or
        std.mem.indexOf(u8, trimmed, "@sh") != null)
    {
        err_ctx.* = .{
            .expression = trimmed,
            .feature = "format strings (@base64, @uri, etc.)",
            .suggestion = "Use jn put or external tools for format conversion",
        };
        return error.UnsupportedFeature;
    }

    // Check for try-catch
    if (std.mem.indexOf(u8, trimmed, "try ") != null or std.mem.indexOf(u8, trimmed, " catch ") != null) {
        err_ctx.* = .{
            .expression = trimmed,
            .feature = "try-catch",
            .suggestion = "Use optional access (.field?) or alternative operator (//)",
        };
        return error.UnsupportedFeature;
    }

    // Check for def (function definitions)
    if (std.mem.startsWith(u8, trimmed, "def ")) {
        err_ctx.* = .{
            .expression = trimmed,
            .feature = "function definitions (def)",
            .suggestion = "ZQ doesn't support custom functions. Use pipes.",
        };
        return error.UnsupportedFeature;
    }
}

fn parseExprWithContext(allocator: std.mem.Allocator, expr: []const u8, err_ctx: *ErrorContext) ParseError!Expr {
    // Check recursion depth to prevent stack overflow from deeply nested expressions
    err_ctx.depth += 1;
    defer err_ctx.depth -= 1;
    if (err_ctx.depth > MAX_PARSE_DEPTH) {
        err_ctx.* = .{
            .expression = expr,
            .feature = "expression nesting too deep",
            .suggestion = "Simplify the expression or break it into smaller parts",
            .depth = err_ctx.depth,
        };
        return error.UnsupportedFeature;
    }

    const trimmed = std.mem.trim(u8, expr, whitespace);

    // Check for unsupported jq features first
    try checkUnsupportedFeatures(trimmed, err_ctx);

    // Check for parenthesized expression (grouping)
    // Must match balanced parens at start and end
    if (trimmed.len > 2 and trimmed[0] == '(') {
        var depth: i32 = 1;
        var end_idx: usize = 1;
        while (end_idx < trimmed.len and depth > 0) : (end_idx += 1) {
            if (trimmed[end_idx] == '(') depth += 1;
            if (trimmed[end_idx] == ')') depth -= 1;
        }
        // If the closing paren is at the end, this is a grouped expression
        if (end_idx == trimmed.len and depth == 0) {
            return parseExprWithContext(allocator, trimmed[1 .. trimmed.len - 1], err_ctx);
        }
    }

    // Check for pipe operator first (lowest precedence)
    // Need to find " | " not inside parentheses or braces
    // Using u32 with saturating ops to avoid underflow with malformed input
    var paren_depth: u32 = 0;
    var brace_depth: u32 = 0;
    var i: usize = 0;
    while (i < trimmed.len) : (i += 1) {
        const c = trimmed[i];
        if (c == '(') {
            paren_depth += 1;
        } else if (c == ')') {
            paren_depth -|= 1; // Saturating subtraction
        } else if (c == '{') {
            brace_depth += 1;
        } else if (c == '}') {
            brace_depth -|= 1; // Saturating subtraction
        } else if (c == '|' and paren_depth == 0 and brace_depth == 0) {
            // Check it's not // (alternative operator)
            if (i + 1 < trimmed.len and trimmed[i + 1] == '/') continue;
            if (i > 0 and trimmed[i - 1] == '/') continue;

            const left_str = std.mem.trim(u8, trimmed[0..i], whitespace);
            const right_str = std.mem.trim(u8, trimmed[i + 1 ..], whitespace);

            if (left_str.len > 0 and right_str.len > 0) {
                const left = try allocator.create(Expr);
                left.* = try parseExprWithContext(allocator, left_str, err_ctx);
                const right = try allocator.create(Expr);
                right.* = try parseExprWithContext(allocator, right_str, err_ctx);
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
            paren_depth -|= 1;
        } else if (c == '{') {
            brace_depth += 1;
        } else if (c == '}') {
            brace_depth -|= 1;
        } else if (c == '/' and trimmed[i + 1] == '/' and paren_depth == 0 and brace_depth == 0) {
            const left_str = std.mem.trim(u8, trimmed[0..i], whitespace);
            const right_str = std.mem.trim(u8, trimmed[i + 2 ..], whitespace);

            if (left_str.len > 0 and right_str.len > 0) {
                const primary = try allocator.create(Expr);
                primary.* = try parseExprWithContext(allocator, left_str, err_ctx);
                const fallback = try allocator.create(Expr);
                fallback.* = try parseExprWithContext(allocator, right_str, err_ctx);
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
            paren_depth -|= 1;
        } else if (c == '{') {
            brace_depth += 1;
        } else if (c == '}') {
            brace_depth -|= 1;
        } else if (paren_depth == 0 and brace_depth == 0) {
            // Check for " + " or " - " (with spaces to avoid confusion with select comparisons)
            if (i > 0 and trimmed[i] == ' ' and (trimmed[i + 1] == '+' or trimmed[i + 1] == '-') and i + 2 < trimmed.len and trimmed[i + 2] == ' ') {
                const op: ArithOp = if (trimmed[i + 1] == '+') .add else .sub;
                const left_str = std.mem.trim(u8, trimmed[0..i], whitespace);
                const right_str = std.mem.trim(u8, trimmed[i + 3 ..], whitespace);

                if (left_str.len > 0 and right_str.len > 0) {
                    const left = try allocator.create(Expr);
                    left.* = try parseExprWithContext(allocator, left_str, err_ctx);
                    const right = try allocator.create(Expr);
                    right.* = try parseExprWithContext(allocator, right_str, err_ctx);
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
            paren_depth -|= 1;
        } else if (c == '{') {
            brace_depth += 1;
        } else if (c == '}') {
            brace_depth -|= 1;
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
                const left_str = std.mem.trim(u8, trimmed[0..i], whitespace);
                const right_str = std.mem.trim(u8, trimmed[i + 3 ..], whitespace);

                if (left_str.len > 0 and right_str.len > 0) {
                    const left = try allocator.create(Expr);
                    left.* = try parseExprWithContext(allocator, left_str, err_ctx);
                    const right = try allocator.create(Expr);
                    right.* = try parseExprWithContext(allocator, right_str, err_ctx);
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
    if (std.mem.eql(u8, trimmed, "type")) return .{ .builtin = .{ .kind = .type } };
    if (std.mem.eql(u8, trimmed, "length")) return .{ .builtin = .{ .kind = .length } };
    if (std.mem.eql(u8, trimmed, "keys")) return .{ .builtin = .{ .kind = .keys } };
    if (std.mem.eql(u8, trimmed, "values")) return .{ .builtin = .{ .kind = .values } };
    if (std.mem.eql(u8, trimmed, "isnumber")) return .{ .builtin = .{ .kind = .isnumber } };
    if (std.mem.eql(u8, trimmed, "isstring")) return .{ .builtin = .{ .kind = .isstring } };
    if (std.mem.eql(u8, trimmed, "isboolean")) return .{ .builtin = .{ .kind = .isboolean } };
    if (std.mem.eql(u8, trimmed, "isnull")) return .{ .builtin = .{ .kind = .isnull } };
    if (std.mem.eql(u8, trimmed, "isarray")) return .{ .builtin = .{ .kind = .isarray } };
    if (std.mem.eql(u8, trimmed, "isobject")) return .{ .builtin = .{ .kind = .isobject } };
    // Sprint 03: Array/Aggregation functions (no arguments)
    if (std.mem.eql(u8, trimmed, "first")) return .{ .builtin = .{ .kind = .first } };
    if (std.mem.eql(u8, trimmed, "last")) return .{ .builtin = .{ .kind = .last } };
    if (std.mem.eql(u8, trimmed, "reverse")) return .{ .builtin = .{ .kind = .reverse } };
    if (std.mem.eql(u8, trimmed, "sort")) return .{ .builtin = .{ .kind = .sort } };
    if (std.mem.eql(u8, trimmed, "unique")) return .{ .builtin = .{ .kind = .unique } };
    if (std.mem.eql(u8, trimmed, "flatten")) return .{ .builtin = .{ .kind = .flatten } };
    if (std.mem.eql(u8, trimmed, "add")) return .{ .builtin = .{ .kind = .add } };
    if (std.mem.eql(u8, trimmed, "min")) return .{ .builtin = .{ .kind = .min } };
    if (std.mem.eql(u8, trimmed, "max")) return .{ .builtin = .{ .kind = .max } };
    if (std.mem.eql(u8, trimmed, "ascii_downcase")) return .{ .builtin = .{ .kind = .ascii_downcase } };
    if (std.mem.eql(u8, trimmed, "ascii_upcase")) return .{ .builtin = .{ .kind = .ascii_upcase } };
    if (std.mem.eql(u8, trimmed, "to_entries")) return .{ .builtin = .{ .kind = .to_entries } };
    if (std.mem.eql(u8, trimmed, "from_entries")) return .{ .builtin = .{ .kind = .from_entries } };
    // Sprint 05: Math functions
    if (std.mem.eql(u8, trimmed, "floor")) return .{ .builtin = .{ .kind = .floor } };
    if (std.mem.eql(u8, trimmed, "ceil")) return .{ .builtin = .{ .kind = .ceil } };
    if (std.mem.eql(u8, trimmed, "round")) return .{ .builtin = .{ .kind = .round } };
    if (std.mem.eql(u8, trimmed, "fabs")) return .{ .builtin = .{ .kind = .fabs } };

    if (std.mem.startsWith(u8, trimmed, "del(") and std.mem.endsWith(u8, trimmed, ")")) {
        const inner_str = trimmed[4 .. trimmed.len - 1];
        // Parse the path expression inside del()
        if (std.mem.startsWith(u8, inner_str, ".")) {
            // Check for array index at end: del(.arr[0])
            var path_str = inner_str;
            var del_index: ?i64 = null;
            if (std.mem.lastIndexOf(u8, inner_str, "[")) |bracket_pos| {
                if (std.mem.endsWith(u8, inner_str, "]")) {
                    const idx_str = inner_str[bracket_pos + 1 .. inner_str.len - 1];
                    if (std.fmt.parseInt(i64, idx_str, 10)) |idx| {
                        del_index = idx;
                        path_str = inner_str[0..bracket_pos];
                    } else |_| {}
                }
            }
            const path = try parsePath(allocator, path_str);
            return .{ .del = .{ .paths = path, .index = del_index } };
        }
    }

    // Sprint 03: String functions with argument - split("sep"), join("sep"), etc.
    if (try parseStrFunc(allocator, trimmed)) |str_func| {
        return str_func;
    }

    // Sprint 03: map(expr)
    if (std.mem.startsWith(u8, trimmed, "map(") and std.mem.endsWith(u8, trimmed, ")")) {
        const inner_str = trimmed[4 .. trimmed.len - 1];
        const inner = try allocator.create(Expr);
        inner.* = try parseExprWithContext(allocator, inner_str, err_ctx);
        return .{ .map = .{ .inner = inner } };
    }

    // Sprint 03: group_by(.field), sort_by(.field), etc.
    if (try parseByFunc(allocator, trimmed)) |by_func| {
        return by_func;
    }

    // Sprint 03: Array literal [.x, .y, .z]
    if (trimmed[0] == '[' and trimmed[trimmed.len - 1] == ']') {
        return try parseArrayLiteral(allocator, trimmed, err_ctx);
    }

    // If-then-else conditional
    if (std.mem.startsWith(u8, trimmed, "if ")) {
        return try parseConditional(allocator, trimmed, err_ctx);
    }

    // Select expression
    if (std.mem.startsWith(u8, trimmed, "select(") and std.mem.endsWith(u8, trimmed, ")")) {
        const inner = trimmed[7 .. trimmed.len - 1];
        const condition = try parseCondition(allocator, inner, err_ctx);
        return .{ .select = condition };
    }

    // Object construction: {a: .x, b: .y}
    if (trimmed[0] == '{' and trimmed[trimmed.len - 1] == '}') {
        return try parseObject(allocator, trimmed, err_ctx);
    }

    // Field path with optional iteration: .foo or .foo.bar or .items[]
    if (trimmed[0] == '.') {
        var optional = false;
        var expr_str = trimmed;
        if (std.mem.endsWith(u8, trimmed, "?")) {
            optional = true;
            expr_str = trimmed[0 .. trimmed.len - 1];
        }

        // Check for iteration at end
        if (std.mem.endsWith(u8, expr_str, "[]")) {
            const path_part = expr_str[0 .. expr_str.len - 2];
            const path = try parsePath(allocator, path_part);
            return .{ .iterate = .{ .path = path } };
        }

        // Check for array index or slice at end
        var path_end = expr_str.len;
        var index: ?IndexExpr = null;
        if (std.mem.lastIndexOf(u8, expr_str, "[")) |bracket_pos| {
            if (std.mem.endsWith(u8, expr_str, "]") and bracket_pos > 0) {
                const idx_str = expr_str[bracket_pos + 1 .. expr_str.len - 1];

                if (std.mem.indexOf(u8, idx_str, ":")) |colon_pos| {
                    // Parse slice: [n:m], [:m], [n:], [:]
                    const start_str = idx_str[0..colon_pos];
                    const end_str = idx_str[colon_pos + 1 ..];

                    const start: ?i64 = if (start_str.len > 0)
                        std.fmt.parseInt(i64, start_str, 10) catch null
                    else
                        null;

                    const end: ?i64 = if (end_str.len > 0)
                        std.fmt.parseInt(i64, end_str, 10) catch null
                    else
                        null;

                    index = .{ .slice = .{ .start = start, .end = end } };
                    path_end = bracket_pos;
                } else if (std.fmt.parseInt(i64, idx_str, 10)) |idx| {
                    index = .{ .single = idx };
                    path_end = bracket_pos;
                } else |_| {}
            }
        }

        const path = try parsePath(allocator, expr_str[0..path_end]);
        if (path.len == 1) {
            return .{ .field = .{ .name = path[0], .index = index, .optional = optional } };
        }
        return .{ .path = .{ .parts = path, .index = index, .optional = optional } };
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

/// Convenience wrapper for tests - uses a dummy error context
fn parseExpr(allocator: std.mem.Allocator, expr: []const u8) ParseError!Expr {
    var dummy_ctx: ErrorContext = .{};
    return parseExprWithContext(allocator, expr, &dummy_ctx);
}

fn parseConditional(allocator: std.mem.Allocator, expr: []const u8, err_ctx: *ErrorContext) ParseError!Expr {
    // Format: if <condition> then <expr> else <expr> end
    const trimmed = std.mem.trim(u8, expr, whitespace);

    // Find "then" keyword
    // Using u32 with saturating ops to avoid underflow with malformed input
    var then_pos: ?usize = null;
    var paren_depth: u32 = 0;
    var i: usize = 3; // Skip "if "
    while (i + 4 < trimmed.len) : (i += 1) {
        if (trimmed[i] == '(') paren_depth += 1;
        if (trimmed[i] == ')') paren_depth -|= 1;
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
        if (trimmed[i] == ')') paren_depth -|= 1;
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

    const cond_str = std.mem.trim(u8, trimmed[3..then_pos.?], whitespace);
    const then_str = std.mem.trim(u8, trimmed[then_pos.? + 5 .. else_pos.?], whitespace);
    const else_str = std.mem.trim(u8, trimmed[else_pos.? + 5 .. end_pos], whitespace);

    const condition = try parseCondition(allocator, cond_str, err_ctx);
    const then_branch = try allocator.create(Expr);
    then_branch.* = try parseExprWithContext(allocator, then_str, err_ctx);
    const else_branch = try allocator.create(Expr);
    else_branch.* = try parseExprWithContext(allocator, else_str, err_ctx);

    return .{ .conditional = .{
        .condition = condition,
        .then_branch = then_branch,
        .else_branch = else_branch,
    } };
}

fn parseObject(allocator: std.mem.Allocator, expr: []const u8, err_ctx: *ErrorContext) ParseError!Expr {
    // Format: {key1: val1, key2: val2, ...}
    const inner = std.mem.trim(u8, expr[1 .. expr.len - 1], whitespace);

    if (inner.len == 0) {
        // Empty object
        return .{ .object = .{ .fields = &[_]ObjectField{} } };
    }

    var fields: std.ArrayListUnmanaged(ObjectField) = .empty;
    // Clean up allocated fields on error
    errdefer {
        for (fields.items) |field| {
            // Free the value expression
            allocator.destroy(field.value);
            // Free dynamic key expression if present
            switch (field.key) {
                .dynamic => |key_expr| allocator.destroy(key_expr),
                .literal => {},
            }
        }
        fields.deinit(allocator);
    }

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
            const field_str = std.mem.trim(u8, inner[start..i], whitespace);
            if (field_str.len > 0) {
                const field = try parseObjectField(allocator, field_str, err_ctx);
                try fields.append(allocator, field);
            }
            start = i + 1;
        }
    }

    return .{ .object = .{ .fields = try fields.toOwnedSlice(allocator) } };
}

fn parseObjectField(allocator: std.mem.Allocator, field_str: []const u8, err_ctx: *ErrorContext) ParseError!ObjectField {
    // Format: key: value or (expr): value or shorthand key
    const trimmed = std.mem.trim(u8, field_str, whitespace);

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
        const key_part = std.mem.trim(u8, trimmed[0..pos], whitespace);
        const val_part = std.mem.trim(u8, trimmed[pos + 1 ..], whitespace);

        var key: KeyType = undefined;
        if (key_part[0] == '(' and key_part[key_part.len - 1] == ')') {
            // Dynamic key: (.field)
            const key_expr = try allocator.create(Expr);
            key_expr.* = try parseExprWithContext(allocator, key_part[1 .. key_part.len - 1], err_ctx);
            key = .{ .dynamic = key_expr };
        } else if (key_part.len >= 2 and key_part[0] == '"' and key_part[key_part.len - 1] == '"') {
            // Quoted literal key: "foo" -> foo
            key = .{ .literal = key_part[1 .. key_part.len - 1] };
        } else {
            // Unquoted literal key: foo
            key = .{ .literal = key_part };
        }

        const value = try allocator.create(Expr);
        value.* = try parseExprWithContext(allocator, val_part, err_ctx);

        return ObjectField{ .key = key, .value = value };
    } else {
        // Shorthand: just "foo" means {foo: .foo}
        const value = try allocator.create(Expr);
        const field_path = try std.fmt.allocPrint(allocator, ".{s}", .{trimmed});
        value.* = try parseExprWithContext(allocator, field_path, err_ctx);
        return ObjectField{ .key = .{ .literal = trimmed }, .value = value };
    }
}

fn parseCondition(allocator: std.mem.Allocator, expr: []const u8, err_ctx: *ErrorContext) ParseError!*Condition {
    const trimmed = std.mem.trim(u8, expr, whitespace);

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
                const left = try parseCondition(allocator, trimmed[0..i], err_ctx);
                const right = try parseCondition(allocator, trimmed[i + 5 ..], err_ctx);
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
                const left = try parseCondition(allocator, trimmed[0..i], err_ctx);
                const right = try parseCondition(allocator, trimmed[i + 4 ..], err_ctx);
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
        const inner = try parseCondition(allocator, trimmed[4..], err_ctx);
        const cond = try allocator.create(Condition);
        cond.* = .{ .negated = inner };
        return cond;
    }

    // Check for parenthesized expression
    if (trimmed[0] == '(' and trimmed[trimmed.len - 1] == ')') {
        return parseCondition(allocator, trimmed[1 .. trimmed.len - 1], err_ctx);
    }

    // Simple condition
    const simple = try parseSimpleCondition(allocator, trimmed, err_ctx);
    const cond = try allocator.create(Condition);
    cond.* = .{ .simple = simple };
    return cond;
}

/// Find operator position outside parentheses
fn findOperatorOutsideParens(str: []const u8, op: []const u8) ?usize {
    var paren_depth: i32 = 0;
    var i: usize = 0;
    while (i + op.len <= str.len) : (i += 1) {
        if (str[i] == '(') {
            paren_depth += 1;
        } else if (str[i] == ')') {
            paren_depth -= 1;
        } else if (paren_depth == 0 and std.mem.eql(u8, str[i .. i + op.len], op)) {
            return i;
        }
    }
    return null;
}

/// Check if expression is a simple path (no pipes, no parens)
fn isSimplePath(expr: []const u8) bool {
    const trimmed = std.mem.trim(u8, expr, whitespace);
    if (trimmed.len == 0) return false;
    if (trimmed[0] != '.') return false;
    for (trimmed) |c| {
        if (c == '|' or c == '(' or c == ')') return false;
    }
    return true;
}

fn parseSimpleCondition(allocator: std.mem.Allocator, expr: []const u8, err_ctx: *ErrorContext) ParseError!SimpleCondition {
    // Operators to check, in order of precedence (longer first)
    const operators = [_]struct { str: []const u8, op: CompareOp, len: usize }{
        .{ .str = " >= ", .op = .gte, .len = 4 },
        .{ .str = " <= ", .op = .lte, .len = 4 },
        .{ .str = " != ", .op = .ne, .len = 4 },
        .{ .str = " == ", .op = .eq, .len = 4 },
        .{ .str = " > ", .op = .gt, .len = 3 },
        .{ .str = " < ", .op = .lt, .len = 3 },
    };

    // Find an operator outside parentheses
    for (operators) |op_info| {
        if (findOperatorOutsideParens(expr, op_info.str)) |pos| {
            const left_str = std.mem.trim(u8, expr[0..pos], whitespace);
            const right_str = expr[pos + op_info.len ..];

            // Check if left side is a simple path or a complex expression
            if (isSimplePath(left_str)) {
                // Simple path like .revenue
                return SimpleCondition{
                    .path = try parsePath(allocator, left_str),
                    .op = op_info.op,
                    .value = try parseValue(right_str),
                };
            } else {
                // Complex expression like (.revenue | tonumber)
                const left_expr = try allocator.create(Expr);
                left_expr.* = try parseExprWithContext(allocator, left_str, err_ctx);
                return SimpleCondition{
                    .left_expr = left_expr,
                    .op = op_info.op,
                    .value = try parseValue(right_str),
                };
            }
        }
    }

    // Just .field means exists/truthy
    if (isSimplePath(expr)) {
        return SimpleCondition{
            .path = try parsePath(allocator, expr),
            .op = .exists,
            .value = .none,
        };
    } else {
        // Complex expression for truthy check
        const left_expr = try allocator.create(Expr);
        left_expr.* = try parseExprWithContext(allocator, expr, err_ctx);
        return SimpleCondition{
            .left_expr = left_expr,
            .op = .exists,
            .value = .none,
        };
    }
}

fn parsePath(allocator: std.mem.Allocator, expr: []const u8) ParseError![][]const u8 {
    var parts: std.ArrayListUnmanaged([]const u8) = .empty;
    const rest = if (expr.len > 0 and expr[0] == '.') expr[1..] else expr;

    var iter = std.mem.splitScalar(u8, rest, '.');
    while (iter.next()) |part| {
        if (part.len > 0) {
            // Strip any array index notation for now
            const clean = if (std.mem.indexOf(u8, part, "[")) |idx| part[0..idx] else part;
            if (clean.len > 0) {
                try parts.append(allocator, clean);
            }
        }
    }

    return parts.toOwnedSlice(allocator);
}

fn parseValue(str: []const u8) ParseError!CompareValue {
    const trimmed = std.mem.trim(u8, str, whitespace);

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
// Sprint 03: Additional Parsers
// ============================================================================

fn parseStrFunc(allocator: std.mem.Allocator, expr: []const u8) ParseError!?Expr {
    _ = allocator;
    const funcs = [_]struct { name: []const u8, kind: StrFuncKind }{
        .{ .name = "split", .kind = .split },
        .{ .name = "join", .kind = .join },
        .{ .name = "startswith", .kind = .startswith },
        .{ .name = "endswith", .kind = .endswith },
        .{ .name = "contains", .kind = .contains },
        .{ .name = "ltrimstr", .kind = .ltrimstr },
        .{ .name = "rtrimstr", .kind = .rtrimstr },
        .{ .name = "has", .kind = .has },
        .{ .name = "test", .kind = .@"test" },
    };

    for (funcs) |func| {
        if (std.mem.startsWith(u8, expr, func.name)) {
            const after_name = expr[func.name.len..];
            if (after_name.len >= 4 and after_name[0] == '(' and
                after_name[1] == '"' and
                after_name[after_name.len - 1] == ')' and
                after_name[after_name.len - 2] == '"')
            {
                const arg = after_name[2 .. after_name.len - 2];
                return .{ .str_func = .{ .kind = func.kind, .arg = arg } };
            }
        }
    }
    return null;
}

fn parseByFunc(allocator: std.mem.Allocator, expr: []const u8) ParseError!?Expr {
    const funcs = [_]struct { name: []const u8, kind: ByFuncKind }{
        .{ .name = "group_by", .kind = .group_by },
        .{ .name = "sort_by", .kind = .sort_by },
        .{ .name = "unique_by", .kind = .unique_by },
        .{ .name = "min_by", .kind = .min_by },
        .{ .name = "max_by", .kind = .max_by },
    };

    for (funcs) |func| {
        if (std.mem.startsWith(u8, expr, func.name)) {
            const after_name = expr[func.name.len..];
            if (after_name.len >= 3 and after_name[0] == '(' and
                after_name[1] == '.' and
                after_name[after_name.len - 1] == ')')
            {
                const path_str = after_name[1 .. after_name.len - 1];
                const path = try parsePath(allocator, path_str);
                return .{ .by_func = .{ .kind = func.kind, .path = path } };
            }
        }
    }
    return null;
}

fn parseArrayLiteral(allocator: std.mem.Allocator, expr: []const u8, err_ctx: *ErrorContext) ParseError!Expr {
    const inner = std.mem.trim(u8, expr[1 .. expr.len - 1], whitespace);

    if (inner.len == 0) {
        return .{ .array = .{ .elements = &[_]*Expr{} } };
    }

    var elements: std.ArrayListUnmanaged(*Expr) = .empty;

    // Split by comma (respecting nesting)
    var start: usize = 0;
    var paren_depth: i32 = 0;
    var brace_depth: i32 = 0;
    var bracket_depth: i32 = 0;
    var i: usize = 0;

    while (i <= inner.len) : (i += 1) {
        const at_end = i == inner.len;
        const c = if (at_end) ',' else inner[i];

        if (c == '(') paren_depth += 1;
        if (c == ')') paren_depth -= 1;
        if (c == '{') brace_depth += 1;
        if (c == '}') brace_depth -= 1;
        if (c == '[') bracket_depth += 1;
        if (c == ']') bracket_depth -= 1;

        if ((c == ',' or at_end) and paren_depth == 0 and brace_depth == 0 and bracket_depth == 0) {
            const elem_str = std.mem.trim(u8, inner[start..i], whitespace);
            if (elem_str.len > 0) {
                const elem = try allocator.create(Expr);
                elem.* = try parseExprWithContext(allocator, elem_str, err_ctx);
                try elements.append(allocator, elem);
            }
            start = i + 1;
        }
    }

    return .{ .array = .{ .elements = try elements.toOwnedSlice(allocator) } };
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

fn getFieldValueBase(value: std.json.Value, name: []const u8) ?std.json.Value {
    switch (value) {
        .object => |obj| {
            return obj.get(name);
        },
        else => return null,
    }
}

fn getIndex(value: std.json.Value, index: i64) ?std.json.Value {
    switch (value) {
        .array => |arr| {
            const len = arr.items.len;
            if (len == 0) return null;

            const actual_idx: usize = if (index < 0) blk: {
                // Handle MIN_I64 specially to avoid overflow when negating
                // MIN_I64 is so large negative that no array could have that index
                const neg_index = std.math.negate(index) catch return null;
                if (@as(usize, @intCast(neg_index)) <= len)
                    break :blk len - @as(usize, @intCast(neg_index))
                else
                    return null;
            } else if (@as(usize, @intCast(index)) < len)
                @as(usize, @intCast(index))
            else
                return null;

            return arr.items[actual_idx];
        },
        else => return null,
    }
}

fn getSlice(allocator: std.mem.Allocator, value: std.json.Value, slice: SliceExpr) !?std.json.Value {
    switch (value) {
        .array => |arr| {
            const len = arr.items.len;
            if (len == 0) {
                // Return empty array
                return .{ .array = .{ .items = &.{}, .capacity = 0, .allocator = allocator } };
            }

            // Resolve start index (handle negative)
            var start_idx: usize = 0;
            if (slice.start) |s| {
                if (s < 0) {
                    // Handle MIN_I64 specially to avoid overflow when negating
                    const neg = std.math.negate(s) catch 0;
                    start_idx = if (@as(usize, @intCast(neg)) <= len) len - @as(usize, @intCast(neg)) else 0;
                } else {
                    start_idx = @min(@as(usize, @intCast(s)), len);
                }
            }

            // Resolve end index (handle negative)
            var end_idx: usize = len;
            if (slice.end) |e| {
                if (e < 0) {
                    // Handle MIN_I64 specially to avoid overflow when negating
                    const neg = std.math.negate(e) catch 0;
                    end_idx = if (@as(usize, @intCast(neg)) <= len) len - @as(usize, @intCast(neg)) else 0;
                } else {
                    end_idx = @min(@as(usize, @intCast(e)), len);
                }
            }

            // Ensure start <= end
            if (start_idx > end_idx) {
                return .{ .array = .{ .items = &.{}, .capacity = 0, .allocator = allocator } };
            }

            // Create slice - copy the items to a new array
            const slice_items = arr.items[start_idx..end_idx];
            const new_items = try allocator.dupe(std.json.Value, slice_items);
            return .{ .array = .{ .items = new_items, .capacity = new_items.len, .allocator = allocator } };
        },
        else => return null,
    }
}

fn evalCondition(allocator: std.mem.Allocator, cond: *const Condition, value: std.json.Value) bool {
    switch (cond.*) {
        .simple => |simple| return evalSimpleCondition(allocator, &simple, value),
        .compound => |compound| {
            const left_result = evalCondition(allocator, compound.left, value);
            return switch (compound.op) {
                .and_op => left_result and evalCondition(allocator, compound.right, value),
                .or_op => left_result or evalCondition(allocator, compound.right, value),
            };
        },
        .negated => |inner| return !evalCondition(allocator, inner, value),
    }
}

fn evalSimpleCondition(allocator: std.mem.Allocator, cond: *const SimpleCondition, value: std.json.Value) bool {
    // Get the left side value(s) - either from expression or path
    if (cond.left_expr) |expr| {
        // Evaluate the expression - may produce multiple values
        const results = evalExpr(allocator, expr, value) catch return false;
        if (results.values.len == 0) return false;

        // For select conditions, return true if ANY result satisfies the condition
        // This matches jq semantics: select(.items[] > 5) is true if any item > 5
        for (results.values) |field_val| {
            if (evalConditionForValue(field_val, cond.op, cond.value)) {
                return true;
            }
        }
        return false;
    } else {
        // Use path-based lookup (single value)
        var field_val = getPath(value, cond.path) orelse return false;

        // Apply index if present
        if (cond.index) |idx| {
            switch (idx) {
                .single => |i| {
                    field_val = getIndex(field_val, i) orelse return false;
                },
                .iterate => return false, // Can't iterate in condition
                .slice => return false, // Slices not supported in conditions
            }
        }

        return evalConditionForValue(field_val, cond.op, cond.value);
    }
}

/// Evaluate a condition for a single value
fn evalConditionForValue(field_val: std.json.Value, op: CompareOp, cmp_value: CompareValue) bool {
    switch (op) {
        .exists => {
            return switch (field_val) {
                .null => false,
                .bool => |b| b,
                else => true,
            };
        },
        .gt => return compareGt(field_val, cmp_value),
        .lt => return compareLt(field_val, cmp_value),
        .gte => return compareGt(field_val, cmp_value) or compareEq(field_val, cmp_value),
        .lte => return compareLt(field_val, cmp_value) or compareEq(field_val, cmp_value),
        .eq => return compareEq(field_val, cmp_value),
        .ne => return !compareEq(field_val, cmp_value),
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
            const base_result = getFieldValueBase(value, field.name);
            if (base_result) |base_val| {
                // Handle index if present
                if (field.index) |idx| {
                    switch (idx) {
                        .single => |ind| {
                            if (getIndex(base_val, ind)) |v| {
                                return try EvalResult.single(allocator, v);
                            }
                            return EvalResult.empty(allocator);
                        },
                        .iterate => return EvalResult.empty(allocator),
                        .slice => |slice| {
                            if (try getSlice(allocator, base_val, slice)) |v| {
                                return try EvalResult.single(allocator, v);
                            }
                            return EvalResult.empty(allocator);
                        },
                    }
                }
                return try EvalResult.single(allocator, base_val);
            }
            return EvalResult.empty(allocator);
        },

        .path => |path_expr| {
            const base_result = getPath(value, path_expr.parts);
            if (base_result) |base_val| {
                // Handle index if present
                if (path_expr.index) |idx| {
                    switch (idx) {
                        .single => |ind| {
                            if (getIndex(base_val, ind)) |v| {
                                return try EvalResult.single(allocator, v);
                            }
                            return EvalResult.empty(allocator);
                        },
                        .iterate => return EvalResult.empty(allocator),
                        .slice => |slice| {
                            if (try getSlice(allocator, base_val, slice)) |v| {
                                return try EvalResult.single(allocator, v);
                            }
                            return EvalResult.empty(allocator);
                        },
                    }
                }
                return try EvalResult.single(allocator, base_val);
            }
            return EvalResult.empty(allocator);
        },

        .select => |cond| {
            if (evalCondition(allocator, cond, value)) {
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
            var all_results: std.ArrayListUnmanaged(std.json.Value) = .empty;

            for (left_results.values) |left_val| {
                const right_results = try evalExpr(allocator, pipe.right, left_val);
                try all_results.appendSlice(allocator, right_results.values);
            }

            return EvalResult.multi(allocator, try all_results.toOwnedSlice(allocator));
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
            if (evalCondition(allocator, cond.condition, value)) {
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

        // Sprint 03: String functions with argument
        .str_func => |sf| {
            return evalStrFunc(allocator, sf, value);
        },

        // Sprint 03: map(expr)
        .map => |m| {
            return evalMap(allocator, m, value);
        },

        // Sprint 03: group_by, sort_by, etc.
        .by_func => |bf| {
            return evalByFunc(allocator, bf, value);
        },

        // Sprint 03: Array literal [.x, .y]
        .array => |arr_expr| {
            return evalArrayLiteral(allocator, arr_expr, value);
        },

        .del => |del_expr| {
            return evalDel(allocator, del_expr, value);
        },
    }
}

fn evalDel(allocator: std.mem.Allocator, del_expr: DelExpr, value: std.json.Value) EvalError!EvalResult {
    switch (value) {
        .object => |obj| {
            if (del_expr.paths.len == 1) {
                const key = del_expr.paths[0];
                // Check if we need to delete an array element: del(.arr[0])
                if (del_expr.index) |idx| {
                    var new_obj = std.json.ObjectMap.init(allocator);
                    var it = obj.iterator();
                    while (it.next()) |entry| {
                        if (std.mem.eql(u8, entry.key_ptr.*, key)) {
                            // Delete element from array
                            switch (entry.value_ptr.*) {
                                .array => |arr| {
                                    var new_arr = std.json.Array.init(allocator);
                                    const len = arr.items.len;
                                    // Handle MIN_I64 specially to avoid overflow when negating
                                    const actual_idx: ?usize = if (idx < 0) blk: {
                                        const neg_idx = std.math.negate(idx) catch break :blk null;
                                        if (@as(usize, @intCast(neg_idx)) <= len)
                                            break :blk len - @as(usize, @intCast(neg_idx))
                                        else
                                            break :blk null;
                                    } else if (@as(usize, @intCast(idx)) < len)
                                        @as(usize, @intCast(idx))
                                    else
                                        null;
                                    for (arr.items, 0..) |item, i| {
                                        if (actual_idx == null or i != actual_idx.?) {
                                            try new_arr.append(item);
                                        }
                                    }
                                    try new_obj.put(entry.key_ptr.*, .{ .array = new_arr });
                                },
                                else => try new_obj.put(entry.key_ptr.*, entry.value_ptr.*),
                            }
                        } else {
                            try new_obj.put(entry.key_ptr.*, entry.value_ptr.*);
                        }
                    }
                    return try EvalResult.single(allocator, .{ .object = new_obj });
                }
                // Simple delete: del(.key)
                var new_obj = std.json.ObjectMap.init(allocator);
                var it = obj.iterator();
                while (it.next()) |entry| {
                    if (!std.mem.eql(u8, entry.key_ptr.*, key)) {
                        try new_obj.put(entry.key_ptr.*, entry.value_ptr.*);
                    }
                }
                return try EvalResult.single(allocator, .{ .object = new_obj });
            } else if (del_expr.paths.len > 1) {
                // Nested delete: del(.a.b) or del(.a.arr[0])
                var new_obj = std.json.ObjectMap.init(allocator);
                var it = obj.iterator();
                while (it.next()) |entry| {
                    if (std.mem.eql(u8, entry.key_ptr.*, del_expr.paths[0])) {
                        // Recurse with remaining path
                        const nested_del = DelExpr{ .paths = del_expr.paths[1..], .index = del_expr.index };
                        const inner_result = try evalDel(allocator, nested_del, entry.value_ptr.*);
                        if (inner_result.values.len > 0) {
                            try new_obj.put(entry.key_ptr.*, inner_result.values[0]);
                        }
                    } else {
                        try new_obj.put(entry.key_ptr.*, entry.value_ptr.*);
                    }
                }
                return try EvalResult.single(allocator, .{ .object = new_obj });
            }
            return try EvalResult.single(allocator, value);
        },
        .array => |arr| {
            // Direct array deletion: del(.[0]) on an array value
            if (del_expr.paths.len == 0 and del_expr.index != null) {
                const idx = del_expr.index.?;
                var new_arr = std.json.Array.init(allocator);
                const len = arr.items.len;
                const actual_idx: ?usize = if (idx < 0)
                    if (@as(usize, @intCast(-idx)) <= len)
                        len - @as(usize, @intCast(-idx))
                    else
                        null
                else if (@as(usize, @intCast(idx)) < len)
                    @as(usize, @intCast(idx))
                else
                    null;
                for (arr.items, 0..) |item, i| {
                    if (actual_idx == null or i != actual_idx.?) {
                        try new_arr.append(item);
                    }
                }
                return try EvalResult.single(allocator, .{ .array = new_arr });
            }
            return try EvalResult.single(allocator, value);
        },
        else => return try EvalResult.single(allocator, value),
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
        .type => {
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
        // Sprint 03: Array functions
        .first => {
            switch (value) {
                .array => |arr| {
                    if (arr.items.len > 0) {
                        return try EvalResult.single(allocator, arr.items[0]);
                    }
                    return EvalResult.empty(allocator);
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .last => {
            switch (value) {
                .array => |arr| {
                    if (arr.items.len > 0) {
                        return try EvalResult.single(allocator, arr.items[arr.items.len - 1]);
                    }
                    return EvalResult.empty(allocator);
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .reverse => {
            switch (value) {
                .array => |arr| {
                    var reversed = try allocator.alloc(std.json.Value, arr.items.len);
                    for (arr.items, 0..) |item, i| {
                        reversed[arr.items.len - 1 - i] = item;
                    }
                    return try EvalResult.single(allocator, .{ .array = .{ .items = reversed, .capacity = reversed.len, .allocator = allocator } });
                },
                .string => |s| {
                    var reversed = try allocator.alloc(u8, s.len);
                    for (s, 0..) |c, i| {
                        reversed[s.len - 1 - i] = c;
                    }
                    return try EvalResult.single(allocator, .{ .string = reversed });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .sort => {
            switch (value) {
                .array => |arr| {
                    const sorted = try allocator.alloc(std.json.Value, arr.items.len);
                    @memcpy(sorted, arr.items);
                    std.mem.sort(std.json.Value, sorted, {}, jsonLessThan);
                    return try EvalResult.single(allocator, .{ .array = .{ .items = sorted, .capacity = sorted.len, .allocator = allocator } });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .unique => {
            switch (value) {
                .array => |arr| {
                    if (arr.items.len == 0) {
                        return try EvalResult.single(allocator, .{ .array = .{ .items = &.{}, .capacity = 0, .allocator = allocator } });
                    }

                    // O(n log n) implementation: sort then remove consecutive duplicates
                    // This matches jq's behavior where unique returns sorted output
                    var sorted = try allocator.dupe(std.json.Value, arr.items);
                    std.mem.sort(std.json.Value, sorted, {}, jsonLessThan);

                    // Linear pass to remove consecutive duplicates
                    var result_list: std.ArrayListUnmanaged(std.json.Value) = .empty;
                    try result_list.append(allocator, sorted[0]);
                    for (sorted[1..]) |item| {
                        if (!jsonEqual(item, result_list.items[result_list.items.len - 1])) {
                            try result_list.append(allocator, item);
                        }
                    }

                    // Free the temporary sorted array
                    allocator.free(sorted);

                    const result_slice = try result_list.toOwnedSlice(allocator);
                    return try EvalResult.single(allocator, .{ .array = .{ .items = result_slice, .capacity = result_slice.len, .allocator = allocator } });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .flatten => {
            switch (value) {
                .array => |arr| {
                    var result_list: std.ArrayListUnmanaged(std.json.Value) = .empty;
                    for (arr.items) |item| {
                        switch (item) {
                            .array => |inner| {
                                try result_list.appendSlice(allocator, inner.items);
                            },
                            else => try result_list.append(allocator, item),
                        }
                    }
                    const result_slice = try result_list.toOwnedSlice(allocator);
                    return try EvalResult.single(allocator, .{ .array = .{ .items = result_slice, .capacity = result_slice.len, .allocator = allocator } });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        // Sprint 03: Aggregation functions
        .add => {
            switch (value) {
                .array => |arr| {
                    // Sum numbers or concatenate strings
                    if (arr.items.len == 0) return try EvalResult.single(allocator, .null);

                    // Check first element type
                    switch (arr.items[0]) {
                        .integer, .float => {
                            var sum: f64 = 0;
                            var all_int = true;
                            for (arr.items) |item| {
                                switch (item) {
                                    .integer => |i| sum += @as(f64, @floatFromInt(i)),
                                    .float => |f| {
                                        sum += f;
                                        all_int = false;
                                    },
                                    else => {},
                                }
                            }
                            if (all_int) {
                                return try EvalResult.single(allocator, .{ .integer = @as(i64, @intFromFloat(sum)) });
                            }
                            return try EvalResult.single(allocator, .{ .float = sum });
                        },
                        .string => {
                            var total_len: usize = 0;
                            for (arr.items) |item| {
                                switch (item) {
                                    .string => |s| total_len += s.len,
                                    else => {},
                                }
                            }
                            var result_str = try allocator.alloc(u8, total_len);
                            var pos: usize = 0;
                            for (arr.items) |item| {
                                switch (item) {
                                    .string => |s| {
                                        @memcpy(result_str[pos..][0..s.len], s);
                                        pos += s.len;
                                    },
                                    else => {},
                                }
                            }
                            return try EvalResult.single(allocator, .{ .string = result_str });
                        },
                        .array => {
                            // Flatten arrays
                            var result_list: std.ArrayListUnmanaged(std.json.Value) = .empty;
                            for (arr.items) |item| {
                                switch (item) {
                                    .array => |inner| try result_list.appendSlice(allocator, inner.items),
                                    else => {},
                                }
                            }
                            const result_slice = try result_list.toOwnedSlice(allocator);
                            return try EvalResult.single(allocator, .{ .array = .{ .items = result_slice, .capacity = result_slice.len, .allocator = allocator } });
                        },
                        else => return EvalResult.empty(allocator),
                    }
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .min => {
            switch (value) {
                .array => |arr| {
                    if (arr.items.len == 0) return try EvalResult.single(allocator, .null);
                    var min_val = arr.items[0];
                    for (arr.items[1..]) |item| {
                        if (jsonLessThan({}, item, min_val)) {
                            min_val = item;
                        }
                    }
                    return try EvalResult.single(allocator, min_val);
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .max => {
            switch (value) {
                .array => |arr| {
                    if (arr.items.len == 0) return try EvalResult.single(allocator, .null);
                    var max_val = arr.items[0];
                    for (arr.items[1..]) |item| {
                        if (jsonLessThan({}, max_val, item)) {
                            max_val = item;
                        }
                    }
                    return try EvalResult.single(allocator, max_val);
                },
                else => return EvalResult.empty(allocator),
            }
        },
        // Sprint 03: String functions (no args)
        .ascii_downcase => {
            switch (value) {
                .string => |s| {
                    var lower = try allocator.alloc(u8, s.len);
                    for (s, 0..) |c, i| {
                        lower[i] = std.ascii.toLower(c);
                    }
                    return try EvalResult.single(allocator, .{ .string = lower });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .ascii_upcase => {
            switch (value) {
                .string => |s| {
                    var upper = try allocator.alloc(u8, s.len);
                    for (s, 0..) |c, i| {
                        upper[i] = std.ascii.toUpper(c);
                    }
                    return try EvalResult.single(allocator, .{ .string = upper });
                },
                else => return EvalResult.empty(allocator),
            }
        },

        .to_entries => {
            switch (value) {
                .object => |obj| {
                    var entries = std.json.Array.init(allocator);
                    var it = obj.iterator();
                    while (it.next()) |entry| {
                        var entry_obj = std.json.ObjectMap.init(allocator);
                        try entry_obj.put("key", .{ .string = entry.key_ptr.* });
                        try entry_obj.put("value", entry.value_ptr.*);
                        try entries.append(.{ .object = entry_obj });
                    }
                    return try EvalResult.single(allocator, .{ .array = entries });
                },
                else => return EvalResult.empty(allocator),
            }
        },

        .from_entries => {
            switch (value) {
                .array => |arr| {
                    var result_obj = std.json.ObjectMap.init(allocator);
                    for (arr.items) |item| {
                        switch (item) {
                            .object => |entry_obj| {
                                // Support {key, value}, {k, v}, and {name, value} forms
                                const key_val = entry_obj.get("key") orelse
                                    entry_obj.get("k") orelse
                                    entry_obj.get("name") orelse continue;
                                const val = entry_obj.get("value") orelse
                                    entry_obj.get("v") orelse continue;
                                switch (key_val) {
                                    .string => |key| {
                                        try result_obj.put(key, val);
                                    },
                                    else => {},
                                }
                            },
                            else => {},
                        }
                    }
                    return try EvalResult.single(allocator, .{ .object = result_obj });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        // Sprint 05: Math functions
        .floor => {
            switch (value) {
                .integer => return try EvalResult.single(allocator, value),
                .float => |f| {
                    const floored = @floor(f);
                    // Return as integer if it fits
                    if (floored >= @as(f64, @floatFromInt(std.math.minInt(i64))) and
                        floored <= @as(f64, @floatFromInt(std.math.maxInt(i64))))
                    {
                        return try EvalResult.single(allocator, .{ .integer = @as(i64, @intFromFloat(floored)) });
                    }
                    return try EvalResult.single(allocator, .{ .float = floored });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .ceil => {
            switch (value) {
                .integer => return try EvalResult.single(allocator, value),
                .float => |f| {
                    const ceiled = @ceil(f);
                    if (ceiled >= @as(f64, @floatFromInt(std.math.minInt(i64))) and
                        ceiled <= @as(f64, @floatFromInt(std.math.maxInt(i64))))
                    {
                        return try EvalResult.single(allocator, .{ .integer = @as(i64, @intFromFloat(ceiled)) });
                    }
                    return try EvalResult.single(allocator, .{ .float = ceiled });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .round => {
            switch (value) {
                .integer => return try EvalResult.single(allocator, value),
                .float => |f| {
                    const rounded = @round(f);
                    if (rounded >= @as(f64, @floatFromInt(std.math.minInt(i64))) and
                        rounded <= @as(f64, @floatFromInt(std.math.maxInt(i64))))
                    {
                        return try EvalResult.single(allocator, .{ .integer = @as(i64, @intFromFloat(rounded)) });
                    }
                    return try EvalResult.single(allocator, .{ .float = rounded });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .fabs => {
            switch (value) {
                .integer => |i| {
                    // Handle minInt(i64) specially to avoid overflow
                    // since -minInt(i64) cannot be represented as i64
                    if (i == std.math.minInt(i64)) {
                        // Return as float since the absolute value exceeds i64 max
                        return try EvalResult.single(allocator, .{ .float = @as(f64, @floatFromInt(std.math.maxInt(i64))) + 1.0 });
                    }
                    const abs_val = if (i < 0) -i else i;
                    return try EvalResult.single(allocator, .{ .integer = abs_val });
                },
                .float => |f| {
                    return try EvalResult.single(allocator, .{ .float = @abs(f) });
                },
                else => return EvalResult.empty(allocator),
            }
        },
    }
}

// Sprint 03: Helper functions for sorting/comparing JSON values
fn jsonLessThan(_: void, a: std.json.Value, b: std.json.Value) bool {
    // Compare by type first, then value
    const type_order = struct {
        fn order(v: std.json.Value) u8 {
            return switch (v) {
                .null => 0,
                .bool => 1,
                .integer, .float => 2,
                .string => 3,
                .array => 4,
                .object => 5,
                else => 6,
            };
        }
    };

    const a_type = type_order.order(a);
    const b_type = type_order.order(b);

    if (a_type != b_type) return a_type < b_type;

    return switch (a) {
        .null => false, // null == null
        .bool => |ab| !ab and b.bool,
        .integer => |ai| blk: {
            const af: f64 = @floatFromInt(ai);
            const bf: f64 = switch (b) {
                .integer => |bi| @floatFromInt(bi),
                .float => |bf| bf,
                else => unreachable,
            };
            break :blk af < bf;
        },
        .float => |af| blk: {
            const bf: f64 = switch (b) {
                .integer => |bi| @floatFromInt(bi),
                .float => |bf| bf,
                else => unreachable,
            };
            break :blk af < bf;
        },
        .string => |as| std.mem.order(u8, as, b.string) == .lt,
        else => false,
    };
}

fn jsonEqual(a: std.json.Value, b: std.json.Value) bool {
    if (@intFromEnum(a) != @intFromEnum(b)) return false;
    return switch (a) {
        .null => true,
        .bool => |ab| ab == b.bool,
        .integer => |ai| ai == b.integer,
        .float => |af| af == b.float,
        .string => |as| std.mem.eql(u8, as, b.string),
        .array => |aa| blk: {
            const ba = b.array;
            if (aa.items.len != ba.items.len) break :blk false;
            for (aa.items, ba.items) |av, bv| {
                if (!jsonEqual(av, bv)) break :blk false;
            }
            break :blk true;
        },
        else => false,
    };
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
        // Object merge with + (jq semantics: right overrides left)
        if (left_val == .object and right_val == .object) {
            var merged = std.json.ObjectMap.init(allocator);
            // Copy all from left
            var left_iter = left_val.object.iterator();
            while (left_iter.next()) |entry| {
                try merged.put(entry.key_ptr.*, entry.value_ptr.*);
            }
            // Copy all from right (overrides left)
            var right_iter = right_val.object.iterator();
            while (right_iter.next()) |entry| {
                try merged.put(entry.key_ptr.*, entry.value_ptr.*);
            }
            return try EvalResult.single(allocator, .{ .object = merged });
        }
        // Array concatenation with +
        if (left_val == .array and right_val == .array) {
            var result_list: std.ArrayListUnmanaged(std.json.Value) = .empty;
            try result_list.appendSlice(allocator, left_val.array.items);
            try result_list.appendSlice(allocator, right_val.array.items);
            const result_slice = try result_list.toOwnedSlice(allocator);
            return try EvalResult.single(allocator, .{ .array = .{ .items = result_slice, .capacity = result_slice.len, .allocator = allocator } });
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
        .mod => if (right_num != 0) @mod(left_num, right_num) else return EvalResult.empty(allocator),
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
// Sprint 03: Additional Evaluators
// ============================================================================

fn evalStrFunc(allocator: std.mem.Allocator, sf: StrFuncExpr, value: std.json.Value) EvalError!EvalResult {
    switch (sf.kind) {
        .split => {
            switch (value) {
                .string => |s| {
                    var result_list: std.ArrayListUnmanaged(std.json.Value) = .empty;
                    var iter = std.mem.splitSequence(u8, s, sf.arg);
                    while (iter.next()) |part| {
                        try result_list.append(allocator, .{ .string = part });
                    }
                    const result_slice = try result_list.toOwnedSlice(allocator);
                    return try EvalResult.single(allocator, .{ .array = .{ .items = result_slice, .capacity = result_slice.len, .allocator = allocator } });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .join => {
            switch (value) {
                .array => |arr| {
                    var total_len: usize = 0;
                    var str_count: usize = 0;
                    for (arr.items) |item| {
                        switch (item) {
                            .string => |s| {
                                total_len += s.len;
                                str_count += 1;
                            },
                            else => {},
                        }
                    }
                    if (str_count == 0) return try EvalResult.single(allocator, .{ .string = "" });

                    const sep_len = sf.arg.len * (str_count - 1);
                    var result_str = try allocator.alloc(u8, total_len + sep_len);
                    var pos: usize = 0;
                    var first = true;
                    for (arr.items) |item| {
                        switch (item) {
                            .string => |s| {
                                if (!first) {
                                    @memcpy(result_str[pos..][0..sf.arg.len], sf.arg);
                                    pos += sf.arg.len;
                                }
                                @memcpy(result_str[pos..][0..s.len], s);
                                pos += s.len;
                                first = false;
                            },
                            else => {},
                        }
                    }
                    return try EvalResult.single(allocator, .{ .string = result_str[0..pos] });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .startswith => {
            switch (value) {
                .string => |s| {
                    return try EvalResult.single(allocator, .{ .bool = std.mem.startsWith(u8, s, sf.arg) });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .endswith => {
            switch (value) {
                .string => |s| {
                    return try EvalResult.single(allocator, .{ .bool = std.mem.endsWith(u8, s, sf.arg) });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .contains => {
            switch (value) {
                .string => |s| {
                    return try EvalResult.single(allocator, .{ .bool = std.mem.indexOf(u8, s, sf.arg) != null });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .ltrimstr => {
            switch (value) {
                .string => |s| {
                    if (std.mem.startsWith(u8, s, sf.arg)) {
                        return try EvalResult.single(allocator, .{ .string = s[sf.arg.len..] });
                    }
                    return try EvalResult.single(allocator, value);
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .rtrimstr => {
            switch (value) {
                .string => |s| {
                    if (std.mem.endsWith(u8, s, sf.arg)) {
                        return try EvalResult.single(allocator, .{ .string = s[0 .. s.len - sf.arg.len] });
                    }
                    return try EvalResult.single(allocator, value);
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .has => {
            switch (value) {
                .object => |obj| {
                    const exists = obj.get(sf.arg) != null;
                    return try EvalResult.single(allocator, .{ .bool = exists });
                },
                .array => |arr| {
                    // jq: has("0") on arrays checks for index 0 as string
                    if (std.fmt.parseInt(usize, sf.arg, 10)) |idx| {
                        const exists = idx < arr.items.len;
                        return try EvalResult.single(allocator, .{ .bool = exists });
                    } else |_| {
                        return try EvalResult.single(allocator, .{ .bool = false });
                    }
                },
                else => return try EvalResult.single(allocator, .{ .bool = false }),
            }
        },
        .@"test" => {
            // Simplified regex matching supporting:
            // - ^pattern  : starts with
            // - pattern$  : ends with
            // - ^pattern$ : exact match
            // - pattern   : contains (default)
            switch (value) {
                .string => |s| {
                    const pattern = sf.arg;
                    const starts_anchor = pattern.len > 0 and pattern[0] == '^';
                    const ends_anchor = pattern.len > 0 and pattern[pattern.len - 1] == '$';

                    // Extract the literal part (without anchors)
                    var literal = pattern;
                    if (starts_anchor) literal = literal[1..];
                    if (ends_anchor and literal.len > 0) literal = literal[0 .. literal.len - 1];

                    const matches = if (starts_anchor and ends_anchor) blk: {
                        // Exact match: ^pattern$
                        break :blk std.mem.eql(u8, s, literal);
                    } else if (starts_anchor) blk: {
                        // Starts with: ^pattern
                        break :blk std.mem.startsWith(u8, s, literal);
                    } else if (ends_anchor) blk: {
                        // Ends with: pattern$
                        break :blk std.mem.endsWith(u8, s, literal);
                    } else blk: {
                        // Contains: pattern (default)
                        break :blk std.mem.indexOf(u8, s, literal) != null;
                    };

                    return try EvalResult.single(allocator, .{ .bool = matches });
                },
                else => return EvalResult.empty(allocator),
            }
        },
    }
}

fn evalMap(allocator: std.mem.Allocator, m: MapExpr, value: std.json.Value) EvalError!EvalResult {
    switch (value) {
        .array => |arr| {
            var result_list: std.ArrayListUnmanaged(std.json.Value) = .empty;
            for (arr.items) |item| {
                const item_result = try evalExpr(allocator, m.inner, item);
                try result_list.appendSlice(allocator, item_result.values);
            }
            const result_slice = try result_list.toOwnedSlice(allocator);
            return try EvalResult.single(allocator, .{ .array = .{ .items = result_slice, .capacity = result_slice.len, .allocator = allocator } });
        },
        else => return EvalResult.empty(allocator),
    }
}

fn evalByFunc(allocator: std.mem.Allocator, bf: ByFuncExpr, value: std.json.Value) EvalError!EvalResult {
    switch (value) {
        .array => |arr| {
            switch (bf.kind) {
                .group_by => {
                    // Group by the path value
                    // Use type-prefixed keys to prevent collisions between different types
                    // e.g., string "1" vs integer 1 should group separately
                    var groups = std.StringHashMap(std.ArrayListUnmanaged(std.json.Value)).init(allocator);

                    for (arr.items) |item| {
                        const key_val = getPath(item, bf.path) orelse continue;
                        var key_str: []const u8 = undefined;
                        switch (key_val) {
                            // Prefix with type indicator to prevent hash collisions
                            .string => |s| key_str = try std.fmt.allocPrint(allocator, "s:{s}", .{s}),
                            .integer => |i| key_str = try std.fmt.allocPrint(allocator, "i:{d}", .{i}),
                            .float => |f| key_str = try std.fmt.allocPrint(allocator, "f:{d}", .{f}),
                            .bool => |b| key_str = if (b) "b:true" else "b:false",
                            .null => key_str = "n:null",
                            else => continue,
                        }

                        const entry = try groups.getOrPut(key_str);
                        if (!entry.found_existing) {
                            entry.value_ptr.* = .empty;
                        }
                        try entry.value_ptr.*.append(allocator, item);
                    }

                    // Convert to array of arrays
                    var result_list: std.ArrayListUnmanaged(std.json.Value) = .empty;
                    var iter = groups.valueIterator();
                    while (iter.next()) |group| {
                        const items = try group.toOwnedSlice(allocator);
                        try result_list.append(allocator, .{ .array = .{ .items = items, .capacity = items.len, .allocator = allocator } });
                    }
                    const result_slice = try result_list.toOwnedSlice(allocator);
                    return try EvalResult.single(allocator, .{ .array = .{ .items = result_slice, .capacity = result_slice.len, .allocator = allocator } });
                },
                .sort_by => {
                    const sorted = try allocator.alloc(std.json.Value, arr.items.len);
                    @memcpy(sorted, arr.items);

                    const SortCtx = struct {
                        path: [][]const u8,

                        fn lessThan(ctx: @This(), a: std.json.Value, b: std.json.Value) bool {
                            const a_key = getPath(a, ctx.path) orelse return false;
                            const b_key = getPath(b, ctx.path) orelse return true;
                            return jsonLessThan({}, a_key, b_key);
                        }
                    };

                    std.mem.sort(std.json.Value, sorted, SortCtx{ .path = bf.path }, SortCtx.lessThan);
                    return try EvalResult.single(allocator, .{ .array = .{ .items = sorted, .capacity = sorted.len, .allocator = allocator } });
                },
                .unique_by => {
                    var result_list: std.ArrayListUnmanaged(std.json.Value) = .empty;
                    var seen = std.StringHashMap(void).init(allocator);

                    for (arr.items) |item| {
                        const key_val = getPath(item, bf.path) orelse continue;
                        var key_str: []const u8 = undefined;
                        switch (key_val) {
                            // Prefix with type indicator to prevent hash collisions
                            .string => |s| key_str = try std.fmt.allocPrint(allocator, "s:{s}", .{s}),
                            .integer => |i| key_str = try std.fmt.allocPrint(allocator, "i:{d}", .{i}),
                            .float => |f| key_str = try std.fmt.allocPrint(allocator, "f:{d}", .{f}),
                            .bool => |b| key_str = if (b) "b:true" else "b:false",
                            .null => key_str = "n:null",
                            else => continue,
                        }

                        const entry = try seen.getOrPut(key_str);
                        if (!entry.found_existing) {
                            try result_list.append(allocator, item);
                        }
                    }
                    const result_slice = try result_list.toOwnedSlice(allocator);
                    return try EvalResult.single(allocator, .{ .array = .{ .items = result_slice, .capacity = result_slice.len, .allocator = allocator } });
                },
                .min_by => {
                    if (arr.items.len == 0) return try EvalResult.single(allocator, .null);

                    var min_item = arr.items[0];
                    var min_key = getPath(min_item, bf.path) orelse return EvalResult.empty(allocator);

                    for (arr.items[1..]) |item| {
                        const key = getPath(item, bf.path) orelse continue;
                        if (jsonLessThan({}, key, min_key)) {
                            min_key = key;
                            min_item = item;
                        }
                    }
                    return try EvalResult.single(allocator, min_item);
                },
                .max_by => {
                    if (arr.items.len == 0) return try EvalResult.single(allocator, .null);

                    var max_item = arr.items[0];
                    var max_key = getPath(max_item, bf.path) orelse return EvalResult.empty(allocator);

                    for (arr.items[1..]) |item| {
                        const key = getPath(item, bf.path) orelse continue;
                        if (jsonLessThan({}, max_key, key)) {
                            max_key = key;
                            max_item = item;
                        }
                    }
                    return try EvalResult.single(allocator, max_item);
                },
            }
        },
        else => return EvalResult.empty(allocator),
    }
}

fn evalArrayLiteral(allocator: std.mem.Allocator, arr_expr: ArrayExpr, value: std.json.Value) EvalError!EvalResult {
    var result_list: std.ArrayListUnmanaged(std.json.Value) = .empty;

    for (arr_expr.elements) |elem| {
        const elem_result = try evalExpr(allocator, elem, value);
        for (elem_result.values) |v| {
            try result_list.append(allocator, v);
        }
    }

    const result_slice = try result_list.toOwnedSlice(allocator);
    return try EvalResult.single(allocator, .{ .array = .{ .items = result_slice, .capacity = result_slice.len, .allocator = allocator } });
}

// ============================================================================
// Output
// ============================================================================

fn writeJson(allocator: std.mem.Allocator, writer: anytype, value: std.json.Value, config: Config) !void {
    _ = allocator; // Arena allocator available if needed
    if (config.raw_strings) {
        switch (value) {
            .string => |s| {
                try writer.writeAll(s);
                return;
            },
            else => {},
        }
    }
    try writeJsonValue(writer, value);
}

fn writeJsonValue(writer: anytype, value: std.json.Value) !void {
    switch (value) {
        .null => try writer.writeAll("null"),
        .bool => |b| try writer.writeAll(if (b) "true" else "false"),
        .integer => |i| try writer.print("{d}", .{i}),
        .float => |f| {
            // Handle special cases for JSON compatibility
            if (std.math.isNan(f) or std.math.isInf(f)) {
                try writer.writeAll("null");
            } else {
                try writer.print("{d}", .{f});
            }
        },
        .number_string => |s| try writer.writeAll(s),
        .string => |s| {
            try writer.writeByte('"');
            for (s) |c| {
                switch (c) {
                    '"' => try writer.writeAll("\\\""),
                    '\\' => try writer.writeAll("\\\\"),
                    '\n' => try writer.writeAll("\\n"),
                    '\r' => try writer.writeAll("\\r"),
                    '\t' => try writer.writeAll("\\t"),
                    else => {
                        if (c < 0x20) {
                            try writer.print("\\u{x:0>4}", .{c});
                        } else {
                            try writer.writeByte(c);
                        }
                    },
                }
            }
            try writer.writeByte('"');
        },
        .array => |arr| {
            try writer.writeByte('[');
            for (arr.items, 0..) |item, i| {
                if (i > 0) try writer.writeByte(',');
                try writeJsonValue(writer, item);
            }
            try writer.writeByte(']');
        },
        .object => |obj| {
            try writer.writeByte('{');
            var first = true;
            var iter = obj.iterator();
            while (iter.next()) |entry| {
                if (!first) try writer.writeByte(',');
                first = false;
                try writer.writeByte('"');
                try writer.writeAll(entry.key_ptr.*);
                try writer.writeAll("\":");
                try writeJsonValue(writer, entry.value_ptr.*);
            }
            try writer.writeByte('}');
        },
    }
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
        \\ARRAY FUNCTIONS:
        \\  first              First element of array
        \\  last               Last element of array
        \\  reverse            Reverse array or string
        \\  sort               Sort array
        \\  unique             Remove duplicates
        \\  flatten            Flatten nested arrays
        \\  [.x, .y]           Construct array from expressions
        \\
        \\AGGREGATION (use with -s):
        \\  add                Sum numbers / concat strings
        \\  min                Minimum value
        \\  max                Maximum value
        \\  group_by(.field)   Group by field value
        \\  sort_by(.field)    Sort by field value
        \\  unique_by(.field)  Unique by field value
        \\  min_by(.field)     Item with min field
        \\  max_by(.field)     Item with max field
        \\  map(expr)          Apply expr to each element
        \\
        \\STRING FUNCTIONS:
        \\  ascii_downcase     Lowercase string
        \\  ascii_upcase       Uppercase string
        \\  split("sep")       Split string to array
        \\  join("sep")        Join array to string
        \\  startswith("s")    Test string prefix
        \\  endswith("s")      Test string suffix
        \\  contains("s")      Test substring
        \\  test("pattern")    Regex-like match (^start, end$, ^exact$)
        \\  ltrimstr("s")      Remove prefix
        \\  rtrimstr("s")      Remove suffix
        \\
        \\OBJECT FUNCTIONS:
        \\  has("key")         Test if object has key
        \\  del(.key)          Delete key from object
        \\  to_entries         Object → [{key,value},...]
        \\  from_entries       [{key,value},...] → object
        \\  .foo?              Optional access (no error if missing)
        \\  .[n:m]             Array slice (e.g., .[2:5], .[-3:])
        \\
        \\OPTIONS:
        \\  -c          Compact output (default, NDJSON compatible)
        \\  -r          Raw string output (no quotes around strings)
        \\  -s          Slurp mode: read all input into array first
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
        \\  cat data.ndjson | zq -s 'length'           # Count records
        \\  cat data.ndjson | zq -s '.[] | .name'      # Iterate slurped array
        \\
        \\  # Sprint 03 features:
        \\  echo '[1,3,2]' | zq 'sort'                 # Sort array
        \\  echo '[1,1,2]' | zq 'unique'               # Remove duplicates
        \\  cat data.ndjson | zq -s 'add'              # Sum all values
        \\  cat data.ndjson | zq -s 'sort_by(.age)'    # Sort by field
        \\  cat data.ndjson | zq -s 'group_by(.type)'  # Group by field
        \\  cat data.ndjson | zq -s 'map(.name)'       # Extract all names
        \\  echo '"HELLO"' | zq 'ascii_downcase'       # Lowercase
        \\  echo '"a,b,c"' | zq 'split(",")'           # Split string
        \\  echo '["a","b"]' | zq 'join("-")'          # Join array
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
        } else if (std.mem.eql(u8, arg, "-s")) {
            config.slurp = true;
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

    // Local error context - avoids global mutable state for thread safety
    var err_ctx: ErrorContext = .{};

    const expr = parseExprWithContext(page_alloc, expr_arg.?, &err_ctx) catch |err| {
        switch (err) {
            error.UnsupportedFeature => {
                std.debug.print("Error: Unsupported jq feature: {s}\n", .{err_ctx.feature});
                std.debug.print("  Expression: {s}\n", .{err_ctx.expression});
                std.debug.print("  Suggestion: {s}\n", .{err_ctx.suggestion});
            },
            error.InvalidExpression => {
                std.debug.print("Error: Invalid expression: '{s}'\n", .{expr_arg.?});
                std.debug.print("  Run 'zq --help' for supported syntax.\n", .{});
            },
            error.InvalidConditional => {
                std.debug.print("Error: Invalid conditional syntax: '{s}'\n", .{expr_arg.?});
                std.debug.print("  Expected: if <condition> then <expr> else <expr> end\n", .{});
            },
            error.InvalidValue => {
                std.debug.print("Error: Invalid value in expression: '{s}'\n", .{expr_arg.?});
            },
            error.OutOfMemory => {
                std.debug.print("Error: Out of memory while parsing expression\n", .{});
            },
        }
        std.process.exit(1);
    };

    // Zig 0.15.2 I/O with buffered reader/writer
    // Buffer for reading JSON lines (64KB max line)
    var stdin_buffer: [64 * 1024]u8 = undefined;
    var stdin_reader_wrapper = std.fs.File.stdin().reader(&stdin_buffer);
    const reader = &stdin_reader_wrapper.interface;

    var stdout_buffer: [8192]u8 = undefined;
    var stdout_writer_wrapper = std.fs.File.stdout().writer(&stdout_buffer);
    const writer = &stdout_writer_wrapper.interface;

    var arena = std.heap.ArenaAllocator.init(page_alloc);
    defer arena.deinit();

    var output_count: usize = 0;

    if (config.slurp) {
        // Slurp mode: collect all JSON values into an array, then apply expression
        var slurp_values: std.ArrayListUnmanaged(std.json.Value) = .empty;

        // Read lines until EOF (compatible with Zig 0.15.1+)
        while (true) {
            const maybe_line = readLine(reader);
            if (maybe_line) |line| {
                if (line.len == 0) continue;

                // Make a copy of the line since the reader buffer gets reused
                const line_copy = try arena.allocator().dupe(u8, line);

                const parsed = std.json.parseFromSlice(std.json.Value, arena.allocator(), line_copy, .{}) catch {
                    if (!config.skip_invalid) {
                        std.debug.print("Error: malformed JSON\n", .{});
                        std.process.exit(1);
                    }
                    continue;
                };
                try slurp_values.append(arena.allocator(), parsed.value);
            } else {
                // EOF reached
                break;
            }
        }

        // Create array from collected values
        const array_value = std.json.Value{ .array = std.json.Array{
            .items = slurp_values.items,
            .capacity = slurp_values.capacity,
            .allocator = arena.allocator(),
        } };

        // Apply expression to the array
        const results = evalExpr(arena.allocator(), &expr, array_value) catch |err| {
            std.debug.print("Evaluation error: {}\n", .{err});
            std.process.exit(1);
        };

        for (results.values) |result| {
            try writeJson(arena.allocator(), writer, result, config);
            try writer.writeByte('\n');
            output_count += 1;
        }
    } else {
        // Normal streaming mode
        // Read lines until EOF (compatible with Zig 0.15.1+)
        while (true) {
            const maybe_line = readLine(reader);
            if (maybe_line) |line| {
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
                    try writeJson(arena.allocator(), writer, result, config);
                    try writer.writeByte('\n');
                    output_count += 1;
                }
            } else {
                // EOF reached
                break;
            }
        }
    }

    try writer.flush();

    if (config.exit_on_empty and output_count == 0) {
        std.process.exit(1);
    }
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

test "parse depth limit prevents stack overflow" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    // Create a deeply nested expression that exceeds MAX_PARSE_DEPTH
    // Each parenthesis pair adds one level of recursion
    // Buffer needs: (depth) open parens + 1 dot + (depth) close parens
    const depth = MAX_PARSE_DEPTH + 5;
    var deeply_nested: [depth * 2 + 1]u8 = undefined;
    var pos: usize = 0;
    for (0..depth) |_| {
        deeply_nested[pos] = '(';
        pos += 1;
    }
    deeply_nested[pos] = '.';
    pos += 1;
    for (0..depth) |_| {
        deeply_nested[pos] = ')';
        pos += 1;
    }

    // Should return error.UnsupportedFeature (not stack overflow)
    var err_ctx: ErrorContext = .{};
    const result = parseExprWithContext(arena.allocator(), deeply_nested[0..pos], &err_ctx);
    try std.testing.expectError(error.UnsupportedFeature, result);
    try std.testing.expectEqualStrings("expression nesting too deep", err_ctx.feature);
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

    var err_ctx: ErrorContext = .{};
    const cond = try parseCondition(arena.allocator(), ".active and .verified", &err_ctx);

    const parsed_true = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json_true, .{});
    const parsed_false = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json_false, .{});

    try std.testing.expect(evalCondition(arena.allocator(), cond, parsed_true.value));
    try std.testing.expect(!evalCondition(arena.allocator(), cond, parsed_false.value));
}

test "eval condition or" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json_admin = "{\"admin\":true,\"moderator\":false}";
    const json_mod = "{\"admin\":false,\"moderator\":true}";
    const json_neither = "{\"admin\":false,\"moderator\":false}";

    var err_ctx: ErrorContext = .{};
    const cond = try parseCondition(arena.allocator(), ".admin or .moderator", &err_ctx);

    const parsed_admin = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json_admin, .{});
    const parsed_mod = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json_mod, .{});
    const parsed_neither = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json_neither, .{});

    try std.testing.expect(evalCondition(arena.allocator(), cond, parsed_admin.value));
    try std.testing.expect(evalCondition(arena.allocator(), cond, parsed_mod.value));
    try std.testing.expect(!evalCondition(arena.allocator(), cond, parsed_neither.value));
}

test "eval condition not" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json_deleted = "{\"deleted\":true}";
    const json_active = "{\"deleted\":false}";

    var err_ctx: ErrorContext = .{};
    const cond = try parseCondition(arena.allocator(), "not .deleted", &err_ctx);

    const parsed_deleted = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json_deleted, .{});
    const parsed_active = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json_active, .{});

    try std.testing.expect(!evalCondition(arena.allocator(), cond, parsed_deleted.value));
    try std.testing.expect(evalCondition(arena.allocator(), cond, parsed_active.value));
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

test "getIndex MIN_I64 does not overflow" {
    // MIN_I64 negation would overflow - this tests the safety check
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[1,2,3]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    // std.math.minInt(i64) is -9223372036854775808
    // Negating it would overflow since max i64 is 9223372036854775807
    // This should return null, not crash
    try std.testing.expect(getIndex(parsed.value, std.math.minInt(i64)) == null);
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

// ============================================================================
// Sprint 03 Tests
// ============================================================================

test "eval first" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[1,2,3]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "first");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 1), result.values[0].integer);
}

test "eval last" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[1,2,3]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "last");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 3), result.values[0].integer);
}

test "eval reverse array" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[1,2,3]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "reverse");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const arr = result.values[0].array;
    try std.testing.expectEqual(@as(usize, 3), arr.items.len);
    try std.testing.expectEqual(@as(i64, 3), arr.items[0].integer);
    try std.testing.expectEqual(@as(i64, 2), arr.items[1].integer);
    try std.testing.expectEqual(@as(i64, 1), arr.items[2].integer);
}

test "eval sort" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[3,1,2]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "sort");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const arr = result.values[0].array;
    try std.testing.expectEqual(@as(i64, 1), arr.items[0].integer);
    try std.testing.expectEqual(@as(i64, 2), arr.items[1].integer);
    try std.testing.expectEqual(@as(i64, 3), arr.items[2].integer);
}

test "eval unique" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[1,2,1,3,2]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "unique");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const arr = result.values[0].array;
    try std.testing.expectEqual(@as(usize, 3), arr.items.len);
}

test "eval add numbers" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[1,2,3,4]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "add");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 10), result.values[0].integer);
}

test "eval add strings" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[\"a\",\"b\",\"c\"]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "add");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqualStrings("abc", result.values[0].string);
}

test "eval min" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[3,1,4,1,5]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "min");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 1), result.values[0].integer);
}

test "eval max" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[3,1,4,1,5]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "max");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 5), result.values[0].integer);
}

test "eval ascii_downcase" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"HELLO\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "ascii_downcase");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqualStrings("hello", result.values[0].string);
}

test "eval ascii_upcase" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "ascii_upcase");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqualStrings("HELLO", result.values[0].string);
}

test "parse split" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "split(\",\")");
    try std.testing.expect(expr == .str_func);
    try std.testing.expect(expr.str_func.kind == .split);
    try std.testing.expectEqualStrings(",", expr.str_func.arg);
}

test "eval split" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"a,b,c\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "split(\",\")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const arr = result.values[0].array;
    try std.testing.expectEqual(@as(usize, 3), arr.items.len);
    try std.testing.expectEqualStrings("a", arr.items[0].string);
    try std.testing.expectEqualStrings("b", arr.items[1].string);
    try std.testing.expectEqualStrings("c", arr.items[2].string);
}

test "eval join" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[\"a\",\"b\",\"c\"]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "join(\"-\")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqualStrings("a-b-c", result.values[0].string);
}

test "eval startswith" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello world\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "startswith(\"hello\")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool);
}

test "eval endswith" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello.json\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "endswith(\".json\")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool);
}

test "eval contains string" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello world\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "contains(\"wor\")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool);
}

test "eval ltrimstr" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello world\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "ltrimstr(\"hello \")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqualStrings("world", result.values[0].string);
}

test "eval rtrimstr" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello world\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "rtrimstr(\" world\")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqualStrings("hello", result.values[0].string);
}

test "parse map" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "map(.name)");
    try std.testing.expect(expr == .map);
}

test "eval map" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[{\"name\":\"alice\"},{\"name\":\"bob\"}]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "map(.name)");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const arr = result.values[0].array;
    try std.testing.expectEqual(@as(usize, 2), arr.items.len);
    try std.testing.expectEqualStrings("alice", arr.items[0].string);
    try std.testing.expectEqualStrings("bob", arr.items[1].string);
}

test "parse sort_by" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "sort_by(.age)");
    try std.testing.expect(expr == .by_func);
    try std.testing.expect(expr.by_func.kind == .sort_by);
}

test "eval sort_by" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[{\"name\":\"bob\",\"age\":30},{\"name\":\"alice\",\"age\":25}]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "sort_by(.age)");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const arr = result.values[0].array;
    try std.testing.expectEqual(@as(usize, 2), arr.items.len);
    // Alice (age 25) should come first
    try std.testing.expectEqualStrings("alice", arr.items[0].object.get("name").?.string);
}

test "parse array literal" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "[.x, .y]");
    try std.testing.expect(expr == .array);
    try std.testing.expectEqual(@as(usize, 2), expr.array.elements.len);
}

test "eval array literal" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":1,\"y\":2}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "[.x, .y]");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const arr = result.values[0].array;
    try std.testing.expectEqual(@as(usize, 2), arr.items.len);
    try std.testing.expectEqual(@as(i64, 1), arr.items[0].integer);
    try std.testing.expectEqual(@as(i64, 2), arr.items[1].integer);
}

test "eval flatten" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[[1,2],[3,4]]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "flatten");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const arr = result.values[0].array;
    try std.testing.expectEqual(@as(usize, 4), arr.items.len);
}

test "parse slice" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".[2:5]");
    // .[2:5] parses as path with empty parts (root slice)
    try std.testing.expect(expr == .path);
    try std.testing.expect(expr.path.index != null);
    try std.testing.expect(expr.path.index.? == .slice);
    try std.testing.expectEqual(@as(?i64, 2), expr.path.index.?.slice.start);
    try std.testing.expectEqual(@as(?i64, 5), expr.path.index.?.slice.end);
}

test "parse slice unbounded start" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".[:5]");
    try std.testing.expect(expr == .path);
    try std.testing.expect(expr.path.index.?.slice.start == null);
    try std.testing.expectEqual(@as(?i64, 5), expr.path.index.?.slice.end);
}

test "parse slice unbounded end" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".[3:]");
    try std.testing.expect(expr == .path);
    try std.testing.expectEqual(@as(?i64, 3), expr.path.index.?.slice.start);
    try std.testing.expect(expr.path.index.?.slice.end == null);
}

test "eval slice" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"items\":[0,1,2,3,4,5,6]}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), ".items[2:5]");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const arr = result.values[0].array;
    try std.testing.expectEqual(@as(usize, 3), arr.items.len);
    try std.testing.expectEqual(@as(i64, 2), arr.items[0].integer);
    try std.testing.expectEqual(@as(i64, 3), arr.items[1].integer);
    try std.testing.expectEqual(@as(i64, 4), arr.items[2].integer);
}

test "eval slice negative" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"items\":[0,1,2,3]}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), ".items[-2:]");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const arr = result.values[0].array;
    try std.testing.expectEqual(@as(usize, 2), arr.items.len);
    try std.testing.expectEqual(@as(i64, 2), arr.items[0].integer);
    try std.testing.expectEqual(@as(i64, 3), arr.items[1].integer);
}

test "parse optional" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), ".foo?");
    try std.testing.expect(expr == .field);
    try std.testing.expect(expr.field.optional);
    try std.testing.expectEqualStrings("foo", expr.field.name);
}

test "parse has" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "has(\"x\")");
    try std.testing.expect(expr == .str_func);
    try std.testing.expect(expr.str_func.kind == .has);
    try std.testing.expectEqualStrings("x", expr.str_func.arg);
}

test "eval has true" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":1}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "has(\"x\")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool);
}

test "eval has false" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":1}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "has(\"y\")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(!result.values[0].bool);
}

test "eval has null value" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":null}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "has(\"x\")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool); // key exists even if null
}

test "parse del" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "del(.x)");
    try std.testing.expect(expr == .del);
    try std.testing.expectEqual(@as(usize, 1), expr.del.paths.len);
    try std.testing.expectEqualStrings("x", expr.del.paths[0]);
}

test "eval del" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":1,\"y\":2}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "del(.x)");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const obj = result.values[0].object;
    try std.testing.expect(obj.get("x") == null);
    try std.testing.expect(obj.get("y") != null);
}

test "eval del missing key" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":1}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "del(.z)");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const obj = result.values[0].object;
    try std.testing.expect(obj.get("x") != null); // x still there
}

test "parse del array index" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "del(.arr[0])");
    try std.testing.expect(expr == .del);
    try std.testing.expectEqual(@as(usize, 1), expr.del.paths.len);
    try std.testing.expectEqualStrings("arr", expr.del.paths[0]);
    try std.testing.expectEqual(@as(?i64, 0), expr.del.index);
}

test "eval del array index" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"arr\":[1,2,3]}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "del(.arr[0])");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const obj = result.values[0].object;
    const arr = obj.get("arr").?.array;
    try std.testing.expectEqual(@as(usize, 2), arr.items.len);
    try std.testing.expectEqual(@as(i64, 2), arr.items[0].integer);
    try std.testing.expectEqual(@as(i64, 3), arr.items[1].integer);
}

test "eval del array negative index" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"arr\":[1,2,3]}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "del(.arr[-1])");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const obj = result.values[0].object;
    const arr = obj.get("arr").?.array;
    try std.testing.expectEqual(@as(usize, 2), arr.items.len);
    try std.testing.expectEqual(@as(i64, 1), arr.items[0].integer);
    try std.testing.expectEqual(@as(i64, 2), arr.items[1].integer);
}

test "parse to_entries" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "to_entries");
    try std.testing.expect(expr == .builtin);
    try std.testing.expect(expr.builtin.kind == .to_entries);
}

test "eval to_entries" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"a\":1,\"b\":2}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "to_entries");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const arr = result.values[0].array;
    try std.testing.expectEqual(@as(usize, 2), arr.items.len);
    // Each item should have key and value
    try std.testing.expect(arr.items[0].object.get("key") != null);
    try std.testing.expect(arr.items[0].object.get("value") != null);
}

test "parse from_entries" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "from_entries");
    try std.testing.expect(expr == .builtin);
    try std.testing.expect(expr.builtin.kind == .from_entries);
}

test "eval from_entries" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[{\"key\":\"x\",\"value\":1},{\"key\":\"y\",\"value\":2}]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "from_entries");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const obj = result.values[0].object;
    try std.testing.expectEqual(@as(i64, 1), obj.get("x").?.integer);
    try std.testing.expectEqual(@as(i64, 2), obj.get("y").?.integer);
}

test "eval from_entries k_v form" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[{\"k\":\"x\",\"v\":1}]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "from_entries");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const obj = result.values[0].object;
    try std.testing.expectEqual(@as(i64, 1), obj.get("x").?.integer);
}

test "parse test" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    const expr = try parseExpr(arena.allocator(), "test(\"^hello\")");
    try std.testing.expect(expr == .str_func);
    try std.testing.expect(expr.str_func.kind == .@"test");
    try std.testing.expectEqualStrings("^hello", expr.str_func.arg);
}

test "eval test contains" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello world\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "test(\"wor\")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool);
}

test "eval test starts with" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello world\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "test(\"^hello\")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool);
}

test "eval test ends with" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello world\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "test(\"world$\")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool);
}

test "eval test exact match" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "test(\"^hello$\")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool);
}

test "eval test no match" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello world\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    const expr = try parseExpr(arena.allocator(), "test(\"^world\")");
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(!result.values[0].bool);
}
