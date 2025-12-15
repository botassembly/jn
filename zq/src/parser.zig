const std = @import("std");
const types = @import("types.zig");

// Import types
const CompareValue = types.CompareValue;
const CompareOp = types.CompareOp;
const BoolOp = types.BoolOp;
const Condition = types.Condition;
const SimpleCondition = types.SimpleCondition;
const CompoundCondition = types.CompoundCondition;
const IndexExpr = types.IndexExpr;
const SliceExpr = types.SliceExpr;
const Expr = types.Expr;
const LiteralExpr = types.LiteralExpr;
const PipeExpr = types.PipeExpr;
const KeyType = types.KeyType;
const ObjectField = types.ObjectField;
const ObjectExpr = types.ObjectExpr;
const BuiltinKind = types.BuiltinKind;
const BuiltinExpr = types.BuiltinExpr;
const AlternativeExpr = types.AlternativeExpr;
const ConditionalExpr = types.ConditionalExpr;
const ArithOp = types.ArithOp;
const ArithmeticExpr = types.ArithmeticExpr;
const FieldExpr = types.FieldExpr;
const PathExpr = types.PathExpr;
const IterateExpr = types.IterateExpr;
const StrFuncKind = types.StrFuncKind;
const StrFuncExpr = types.StrFuncExpr;
const MapExpr = types.MapExpr;
const ByFuncKind = types.ByFuncKind;
const ByFuncExpr = types.ByFuncExpr;
const ArrayExpr = types.ArrayExpr;
const DelExpr = types.DelExpr;
const ParseError = types.ParseError;
const ErrorContext = types.ErrorContext;
const MAX_PARSE_DEPTH = types.MAX_PARSE_DEPTH;

// Whitespace characters for trimming (includes newlines for multi-line expressions)
const whitespace = " \t\n\r";

// ============================================================================
// Parser
// ============================================================================

/// Check for jq features not supported by ZQ and provide helpful error messages.
/// The err_ctx output parameter receives error details if an unsupported feature is found.
pub fn checkUnsupportedFeatures(expr: []const u8, err_ctx: *ErrorContext) ParseError!void {
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

pub fn parseExprWithContext(allocator: std.mem.Allocator, expr: []const u8, err_ctx: *ErrorContext) ParseError!Expr {
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
    // Sprint 07: More math functions
    if (std.mem.eql(u8, trimmed, "abs")) return .{ .builtin = .{ .kind = .abs } };
    if (std.mem.eql(u8, trimmed, "exp")) return .{ .builtin = .{ .kind = .exp } };
    if (std.mem.eql(u8, trimmed, "ln")) return .{ .builtin = .{ .kind = .ln } };
    if (std.mem.eql(u8, trimmed, "log10")) return .{ .builtin = .{ .kind = .log10 } };
    if (std.mem.eql(u8, trimmed, "log2")) return .{ .builtin = .{ .kind = .log2 } };
    if (std.mem.eql(u8, trimmed, "sqrt")) return .{ .builtin = .{ .kind = .sqrt } };
    // Sprint 07: Trigonometry functions
    if (std.mem.eql(u8, trimmed, "sin")) return .{ .builtin = .{ .kind = .sin } };
    if (std.mem.eql(u8, trimmed, "cos")) return .{ .builtin = .{ .kind = .cos } };
    if (std.mem.eql(u8, trimmed, "tan")) return .{ .builtin = .{ .kind = .tan } };
    if (std.mem.eql(u8, trimmed, "asin")) return .{ .builtin = .{ .kind = .asin } };
    if (std.mem.eql(u8, trimmed, "acos")) return .{ .builtin = .{ .kind = .acos } };
    if (std.mem.eql(u8, trimmed, "atan")) return .{ .builtin = .{ .kind = .atan } };
    // Sprint 06: Generator functions - Date/Time
    if (std.mem.eql(u8, trimmed, "now")) return .{ .builtin = .{ .kind = .now } };
    if (std.mem.eql(u8, trimmed, "today")) return .{ .builtin = .{ .kind = .today } };
    if (std.mem.eql(u8, trimmed, "epoch")) return .{ .builtin = .{ .kind = .epoch } };
    if (std.mem.eql(u8, trimmed, "epoch_ms")) return .{ .builtin = .{ .kind = .epoch_ms } };
    // Sprint 07: Date/Time component generators
    if (std.mem.eql(u8, trimmed, "year")) return .{ .builtin = .{ .kind = .year } };
    if (std.mem.eql(u8, trimmed, "month")) return .{ .builtin = .{ .kind = .month } };
    if (std.mem.eql(u8, trimmed, "day")) return .{ .builtin = .{ .kind = .day } };
    if (std.mem.eql(u8, trimmed, "hour")) return .{ .builtin = .{ .kind = .hour } };
    if (std.mem.eql(u8, trimmed, "minute")) return .{ .builtin = .{ .kind = .minute } };
    if (std.mem.eql(u8, trimmed, "second")) return .{ .builtin = .{ .kind = .second } };
    if (std.mem.eql(u8, trimmed, "time")) return .{ .builtin = .{ .kind = .time } };
    if (std.mem.eql(u8, trimmed, "week")) return .{ .builtin = .{ .kind = .week } };
    if (std.mem.eql(u8, trimmed, "weekday")) return .{ .builtin = .{ .kind = .weekday } };
    if (std.mem.eql(u8, trimmed, "weekday_num")) return .{ .builtin = .{ .kind = .weekday_num } };
    // Sprint 06: Generator functions - IDs
    if (std.mem.eql(u8, trimmed, "uuid")) return .{ .builtin = .{ .kind = .uuid } };
    if (std.mem.eql(u8, trimmed, "shortid")) return .{ .builtin = .{ .kind = .shortid } };
    if (std.mem.eql(u8, trimmed, "sid")) return .{ .builtin = .{ .kind = .sid } };
    // Sprint 07: More ID generators
    if (std.mem.eql(u8, trimmed, "nanoid")) return .{ .builtin = .{ .kind = .nanoid } };
    if (std.mem.eql(u8, trimmed, "ulid")) return .{ .builtin = .{ .kind = .ulid } };
    if (std.mem.eql(u8, trimmed, "uuid7")) return .{ .builtin = .{ .kind = .uuid7 } };
    if (std.mem.eql(u8, trimmed, "xid")) return .{ .builtin = .{ .kind = .xid } };
    // Sprint 06: Generator functions - Random/Sequence
    if (std.mem.eql(u8, trimmed, "random")) return .{ .builtin = .{ .kind = .random } };
    if (std.mem.eql(u8, trimmed, "seq")) return .{ .builtin = .{ .kind = .seq } };
    // Sprint 06: Transform functions - Numeric
    if (std.mem.eql(u8, trimmed, "incr")) return .{ .builtin = .{ .kind = .incr } };
    if (std.mem.eql(u8, trimmed, "decr")) return .{ .builtin = .{ .kind = .decr } };
    if (std.mem.eql(u8, trimmed, "negate")) return .{ .builtin = .{ .kind = .negate } };
    if (std.mem.eql(u8, trimmed, "toggle")) return .{ .builtin = .{ .kind = .toggle } };
    // Sprint 06: Transform functions - String
    if (std.mem.eql(u8, trimmed, "trim")) return .{ .builtin = .{ .kind = .trim } };
    if (std.mem.eql(u8, trimmed, "ltrim")) return .{ .builtin = .{ .kind = .ltrim } };
    if (std.mem.eql(u8, trimmed, "rtrim")) return .{ .builtin = .{ .kind = .rtrim } };
    // Sprint 06: Type coercion
    if (std.mem.eql(u8, trimmed, "int")) return .{ .builtin = .{ .kind = .@"int" } };
    if (std.mem.eql(u8, trimmed, "float")) return .{ .builtin = .{ .kind = .@"float" } };
    if (std.mem.eql(u8, trimmed, "bool")) return .{ .builtin = .{ .kind = .@"bool" } };
    // Sprint 06: Case functions
    if (std.mem.eql(u8, trimmed, "capitalize")) return .{ .builtin = .{ .kind = .capitalize } };
    if (std.mem.eql(u8, trimmed, "titlecase")) return .{ .builtin = .{ .kind = .titlecase } };
    if (std.mem.eql(u8, trimmed, "snakecase")) return .{ .builtin = .{ .kind = .snakecase } };
    if (std.mem.eql(u8, trimmed, "camelcase")) return .{ .builtin = .{ .kind = .camelcase } };
    if (std.mem.eql(u8, trimmed, "kebabcase")) return .{ .builtin = .{ .kind = .kebabcase } };
    // Sprint 06: Predicates
    if (std.mem.eql(u8, trimmed, "empty")) return .{ .builtin = .{ .kind = .empty } };
    // Sprint 06: String splitting
    if (std.mem.eql(u8, trimmed, "words")) return .{ .builtin = .{ .kind = .words } };
    if (std.mem.eql(u8, trimmed, "lines")) return .{ .builtin = .{ .kind = .lines } };
    if (std.mem.eql(u8, trimmed, "chars")) return .{ .builtin = .{ .kind = .chars } };
    // Sprint 06: Slug
    if (std.mem.eql(u8, trimmed, "slugify")) return .{ .builtin = .{ .kind = .slugify } };

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
pub fn parseExpr(allocator: std.mem.Allocator, expr: []const u8) ParseError!Expr {
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
    var paren_depth: u32 = 0;
    var brace_depth: u32 = 0;
    var i: usize = 0;

    while (i <= inner.len) : (i += 1) {
        const at_end = i == inner.len;
        const c = if (at_end) ',' else inner[i];

        if (c == '(') paren_depth += 1;
        if (c == ')') paren_depth -|= 1; // Saturating subtraction for safety
        if (c == '{') brace_depth += 1;
        if (c == '}') brace_depth -|= 1; // Saturating subtraction for safety

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
    var paren_depth: u32 = 0;
    var i: usize = 0;
    while (i < trimmed.len) : (i += 1) {
        if (trimmed[i] == '(') paren_depth += 1;
        if (trimmed[i] == ')') paren_depth -|= 1; // Saturating subtraction for safety
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

pub fn parseCondition(allocator: std.mem.Allocator, expr: []const u8, err_ctx: *ErrorContext) ParseError!*Condition {
    const trimmed = std.mem.trim(u8, expr, whitespace);

    // Check for boolean operators (lowest precedence)
    // Find "and" or "or" not inside parentheses
    var paren_depth: u32 = 0;
    var i: usize = 0;
    while (i < trimmed.len) : (i += 1) {
        if (trimmed[i] == '(') {
            paren_depth += 1;
        } else if (trimmed[i] == ')') {
            paren_depth -|= 1; // Saturating subtraction for safety
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
    var paren_depth: u32 = 0;
    var i: usize = 0;
    while (i + op.len <= str.len) : (i += 1) {
        if (str[i] == '(') {
            paren_depth += 1;
        } else if (str[i] == ')') {
            paren_depth -|= 1; // Saturating subtraction for safety
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

pub fn parsePath(allocator: std.mem.Allocator, expr: []const u8) ParseError![][]const u8 {
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

pub fn parseValue(str: []const u8) ParseError!CompareValue {
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
    if (std.fmt.parseInt(i64, trimmed, 10)) |int| {
        return .{ .int = int };
    } else |_| {}

    // Float
    if (std.fmt.parseFloat(f64, trimmed)) |float| {
        return .{ .float = float };
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
    var paren_depth: u32 = 0;
    var brace_depth: u32 = 0;
    var bracket_depth: u32 = 0;
    var i: usize = 0;

    while (i <= inner.len) : (i += 1) {
        const at_end = i == inner.len;
        const c = if (at_end) ',' else inner[i];

        if (c == '(') paren_depth += 1;
        if (c == ')') paren_depth -|= 1; // Saturating subtraction for safety
        if (c == '{') brace_depth += 1;
        if (c == '}') brace_depth -|= 1; // Saturating subtraction for safety
        if (c == '[') bracket_depth += 1;
        if (c == ']') bracket_depth -|= 1; // Saturating subtraction for safety

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
// Parser Tests
// ============================================================================

test "parse identity" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".", &err_ctx);
    try std.testing.expect(expr == .identity);
}

test "parse field" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".name", &err_ctx);
    try std.testing.expect(expr == .field);
    try std.testing.expectEqualStrings("name", expr.field.name);
}

test "parse path" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".foo.bar.baz", &err_ctx);
    try std.testing.expect(expr == .path);
    try std.testing.expectEqual(@as(usize, 3), expr.path.parts.len);
}

test "parse depth limit prevents stack overflow" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    // Create a deeply nested expression that exceeds MAX_PARSE_DEPTH
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

    var err_ctx: ErrorContext = .{};
    const result = parseExprWithContext(arena.allocator(), deeply_nested[0..pos], &err_ctx);
    try std.testing.expectError(error.UnsupportedFeature, result);
    try std.testing.expectEqualStrings("expression nesting too deep", err_ctx.feature);
}

test "parse select gt" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "select(.id > 50000)", &err_ctx);
    try std.testing.expect(expr == .select);
    try std.testing.expect(expr.select.* == .simple);
    try std.testing.expect(expr.select.simple.op == .gt);
    try std.testing.expect(expr.select.simple.value.int == 50000);
}

test "parse select gte" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "select(.age >= 18)", &err_ctx);
    try std.testing.expect(expr == .select);
    try std.testing.expect(expr.select.simple.op == .gte);
    try std.testing.expect(expr.select.simple.value.int == 18);
}

test "parse select lte" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "select(.score <= 100)", &err_ctx);
    try std.testing.expect(expr == .select);
    try std.testing.expect(expr.select.simple.op == .lte);
    try std.testing.expect(expr.select.simple.value.int == 100);
}

test "parse select and" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "select(.active and .verified)", &err_ctx);
    try std.testing.expect(expr == .select);
    try std.testing.expect(expr.select.* == .compound);
    try std.testing.expect(expr.select.compound.op == .and_op);
}

test "parse select or" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "select(.admin or .moderator)", &err_ctx);
    try std.testing.expect(expr == .select);
    try std.testing.expect(expr.select.* == .compound);
    try std.testing.expect(expr.select.compound.op == .or_op);
}

test "parse select not" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "select(not .deleted)", &err_ctx);
    try std.testing.expect(expr == .select);
    try std.testing.expect(expr.select.* == .negated);
}

test "parse iterate" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".[]", &err_ctx);
    try std.testing.expect(expr == .iterate);
    try std.testing.expectEqual(@as(usize, 0), expr.iterate.path.len);
}

test "parse iterate nested" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".items[]", &err_ctx);
    try std.testing.expect(expr == .iterate);
    try std.testing.expectEqual(@as(usize, 1), expr.iterate.path.len);
}

test "parse array index" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".items[0]", &err_ctx);
    try std.testing.expect(expr == .field);
    try std.testing.expect(expr.field.index != null);
    try std.testing.expectEqual(@as(i64, 0), expr.field.index.?.single);
}

test "parse negative array index" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".items[-1]", &err_ctx);
    try std.testing.expect(expr == .field);
    try std.testing.expect(expr.field.index != null);
    try std.testing.expectEqual(@as(i64, -1), expr.field.index.?.single);
}

test "parse pipe" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".x | tonumber", &err_ctx);
    try std.testing.expect(expr == .pipe);
}

test "parse object literal" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "{a: .x, b: .y}", &err_ctx);
    try std.testing.expect(expr == .object);
    try std.testing.expectEqual(@as(usize, 2), expr.object.fields.len);
}

test "parse alternative" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".x // .y", &err_ctx);
    try std.testing.expect(expr == .alternative);
}

test "parse conditional" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "if .x > 5 then .a else .b end", &err_ctx);
    try std.testing.expect(expr == .conditional);
}

test "parse arithmetic add" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".x + .y", &err_ctx);
    try std.testing.expect(expr == .arithmetic);
    try std.testing.expect(expr.arithmetic.op == .add);
}

test "parse builtin tonumber" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "tonumber", &err_ctx);
    try std.testing.expect(expr == .builtin);
    try std.testing.expect(expr.builtin.kind == .tonumber);
}

test "parse literal string" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "\"hello\"", &err_ctx);
    try std.testing.expect(expr == .literal);
    try std.testing.expect(expr.literal == .string);
    try std.testing.expectEqualStrings("hello", expr.literal.string);
}

test "parse literal number" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "42", &err_ctx);
    try std.testing.expect(expr == .literal);
    try std.testing.expect(expr.literal == .integer);
    try std.testing.expectEqual(@as(i64, 42), expr.literal.integer);
}

test "parse split" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "split(\",\")", &err_ctx);
    try std.testing.expect(expr == .str_func);
    try std.testing.expect(expr.str_func.kind == .split);
    try std.testing.expectEqualStrings(",", expr.str_func.arg);
}

test "parse map" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "map(.name)", &err_ctx);
    try std.testing.expect(expr == .map);
}

test "parse sort_by" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "sort_by(.age)", &err_ctx);
    try std.testing.expect(expr == .by_func);
    try std.testing.expect(expr.by_func.kind == .sort_by);
}

test "parse array literal" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "[.x, .y]", &err_ctx);
    try std.testing.expect(expr == .array);
    try std.testing.expectEqual(@as(usize, 2), expr.array.elements.len);
}

test "parse slice" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".[2:5]", &err_ctx);
    try std.testing.expect(expr == .path);
    try std.testing.expect(expr.path.index != null);
    try std.testing.expect(expr.path.index.? == .slice);
    try std.testing.expectEqual(@as(?i64, 2), expr.path.index.?.slice.start);
    try std.testing.expectEqual(@as(?i64, 5), expr.path.index.?.slice.end);
}

test "parse slice unbounded start" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".[:5]", &err_ctx);
    try std.testing.expect(expr == .path);
    try std.testing.expect(expr.path.index.?.slice.start == null);
    try std.testing.expectEqual(@as(?i64, 5), expr.path.index.?.slice.end);
}

test "parse slice unbounded end" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".[3:]", &err_ctx);
    try std.testing.expect(expr == .path);
    try std.testing.expectEqual(@as(?i64, 3), expr.path.index.?.slice.start);
    try std.testing.expect(expr.path.index.?.slice.end == null);
}

test "parse optional" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".foo?", &err_ctx);
    try std.testing.expect(expr == .field);
    try std.testing.expect(expr.field.optional);
    try std.testing.expectEqualStrings("foo", expr.field.name);
}

test "parse has" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "has(\"x\")", &err_ctx);
    try std.testing.expect(expr == .str_func);
    try std.testing.expect(expr.str_func.kind == .has);
    try std.testing.expectEqualStrings("x", expr.str_func.arg);
}

test "parse del" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "del(.x)", &err_ctx);
    try std.testing.expect(expr == .del);
    try std.testing.expectEqual(@as(usize, 1), expr.del.paths.len);
    try std.testing.expectEqualStrings("x", expr.del.paths[0]);
}

test "parse del array index" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "del(.arr[0])", &err_ctx);
    try std.testing.expect(expr == .del);
    try std.testing.expectEqual(@as(usize, 1), expr.del.paths.len);
    try std.testing.expectEqualStrings("arr", expr.del.paths[0]);
    try std.testing.expectEqual(@as(?i64, 0), expr.del.index);
}

test "parse to_entries" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "to_entries", &err_ctx);
    try std.testing.expect(expr == .builtin);
    try std.testing.expect(expr.builtin.kind == .to_entries);
}

test "parse from_entries" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "from_entries", &err_ctx);
    try std.testing.expect(expr == .builtin);
    try std.testing.expect(expr.builtin.kind == .from_entries);
}

test "parse test" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();
    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "test(\"^hello\")", &err_ctx);
    try std.testing.expect(expr == .str_func);
    try std.testing.expect(expr.str_func.kind == .@"test");
    try std.testing.expectEqualStrings("^hello", expr.str_func.arg);
}
