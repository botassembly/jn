const std = @import("std");

// ============================================================================
// Types
// ============================================================================

pub const CompareValue = union(enum) {
    int: i64,
    float: f64,
    string: []const u8,
    boolean: bool,
    null_val,
    none,
};

pub const CompareOp = enum {
    gt, // >
    lt, // <
    gte, // >=
    lte, // <=
    eq, // ==
    ne, // !=
    exists, // truthy check
};

pub const BoolOp = enum {
    and_op,
    or_op,
};

pub const Condition = union(enum) {
    simple: SimpleCondition,
    compound: CompoundCondition,
    negated: *Condition,
};

pub const SimpleCondition = struct {
    // Left side can be an expression (e.g., ".revenue | tonumber") or a simple path
    left_expr: ?*Expr = null,
    path: [][]const u8 = &[_][]const u8{},
    index: ?IndexExpr = null,
    op: CompareOp,
    value: CompareValue,
};

pub const CompoundCondition = struct {
    left: *Condition,
    op: BoolOp,
    right: *Condition,
};

pub const IndexExpr = union(enum) {
    single: i64, // .[0] or .[-1]
    iterate, // .[]
    slice: SliceExpr, // .[n:m]
};

pub const SliceExpr = struct {
    start: ?i64, // null means from beginning
    end: ?i64, // null means to end
};

pub const Expr = union(enum) {
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

pub const LiteralExpr = union(enum) {
    string: []const u8,
    integer: i64,
    float: f64,
    boolean: bool,
    null_val,
};

pub const PipeExpr = struct {
    left: *Expr,
    right: *Expr,
};

pub const KeyType = union(enum) {
    literal: []const u8, // "a" in {a: .x}
    dynamic: *Expr, // (.key) in {(.key): .value}
};

pub const ObjectField = struct {
    key: KeyType,
    value: *Expr,
};

pub const ObjectExpr = struct {
    fields: []ObjectField,
};

pub const BuiltinKind = enum {
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
    // More math functions (Sprint 07)
    abs, // Alias for fabs, works with integers too
    exp, // e^x
    ln, // Natural logarithm
    log10, // Base-10 logarithm
    log2, // Base-2 logarithm
    sqrt, // Square root
    // Trigonometry functions (Sprint 07)
    sin, // Sine (radians)
    cos, // Cosine (radians)
    tan, // Tangent (radians)
    asin, // Arc sine (radians)
    acos, // Arc cosine (radians)
    atan, // Arc tangent (radians)
    // Generator functions - Date/Time (Sprint 06)
    now, // ISO 8601 timestamp (UTC)
    today, // Date only (YYYY-MM-DD)
    epoch, // Unix timestamp in seconds
    epoch_ms, // Unix timestamp in milliseconds
    // Date/Time component generators (Sprint 07)
    year, // Current year (e.g., 2025)
    month, // Current month (1-12)
    day, // Current day of month (1-31)
    hour, // Current hour (0-23)
    minute, // Current minute (0-59)
    second, // Current second (0-59)
    time, // Time only (HH:MM:SS)
    week, // ISO week number (1-53)
    weekday, // Day of week name (Sunday, Monday, etc.)
    weekday_num, // Day of week number (0=Sunday, 6=Saturday)
    // Generator functions - IDs (Sprint 06)
    uuid, // UUID v4, 36 chars, random
    shortid, // Base62 8-char ID
    sid, // Base62 6-char ID
    // More ID generators (Sprint 07)
    nanoid, // NanoID, 21 chars, URL-safe
    ulid, // ULID, 26 chars, time-sortable
    uuid7, // UUID v7, 36 chars, time-sortable
    xid, // XID, 20 chars, compact and sortable
    // Generator functions - Random/Sequence (Sprint 06)
    random, // Random float 0.0-1.0
    seq, // Incrementing counter
    // Transform functions - Numeric (Sprint 06)
    incr, // Add 1
    decr, // Subtract 1
    negate, // Flip sign
    toggle, // Flip boolean
    // Transform functions - String (Sprint 06)
    trim, // Remove leading/trailing whitespace
    ltrim, // Remove leading whitespace
    rtrim, // Remove trailing whitespace
    // Type coercion (Sprint 06)
    @"int", // Coerce to integer
    @"float", // Coerce to float (note: using @"" to escape keyword-like name)
    @"bool", // Coerce to boolean
    // Case functions (Sprint 06)
    capitalize, // First letter uppercase
    titlecase, // Each word capitalized
    snakecase, // to_snake_case
    camelcase, // toCamelCase
    kebabcase, // to-kebab-case
    // More case functions (Sprint 07)
    pascalcase, // ToPascalCase (like camelCase but first letter uppercase)
    screamcase, // TO_SCREAMING_SNAKE_CASE
    // Predicate functions (Sprint 06)
    empty, // True if empty string/array/object
    // String splitting (Sprint 06)
    words, // Split string into words
    lines, // Split string into lines
    chars, // Split string into characters
    // Slug (Sprint 06)
    slugify, // Convert to URL-safe slug
};

pub const BuiltinExpr = struct {
    kind: BuiltinKind,
};

pub const AlternativeExpr = struct {
    primary: *Expr,
    fallback: *Expr,
};

pub const ConditionalExpr = struct {
    condition: *Condition,
    then_branch: *Expr,
    else_branch: *Expr,
};

pub const ArithOp = enum {
    add, // +
    sub, // -
    mul, // *
    div, // /
    mod, // %
};

pub const ArithmeticExpr = struct {
    left: *Expr,
    op: ArithOp,
    right: *Expr,
};

pub const FieldExpr = struct {
    name: []const u8,
    index: ?IndexExpr = null,
    optional: bool = false, // .foo? syntax
};

pub const PathExpr = struct {
    parts: [][]const u8,
    index: ?IndexExpr = null,
    optional: bool = false, // .foo.bar? syntax
};

pub const IterateExpr = struct {
    path: [][]const u8, // empty means root
};

// Sprint 03: String functions with string argument
pub const StrFuncKind = enum {
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

pub const StrFuncExpr = struct {
    kind: StrFuncKind,
    arg: []const u8,
};

// Sprint 03: map(expr)
pub const MapExpr = struct {
    inner: *Expr,
};

// Sprint 03: group_by, sort_by, unique_by, min_by, max_by
pub const ByFuncKind = enum {
    group_by,
    sort_by,
    unique_by,
    min_by,
    max_by,
};

pub const ByFuncExpr = struct {
    kind: ByFuncKind,
    path: [][]const u8,
};

// Sprint 03: Array literal [.x, .y, .z]
pub const ArrayExpr = struct {
    elements: []*Expr,
};

pub const DelExpr = struct {
    paths: [][]const u8, // paths to delete (e.g., ["x"] or ["a", "b"] for .a.b)
    index: ?i64 = null, // optional array index (e.g., 0 for del(.arr[0]))
};

pub const Config = struct {
    compact: bool = true,
    raw_strings: bool = false,
    exit_on_empty: bool = false,
    skip_invalid: bool = true,
    slurp: bool = false,
};

// ============================================================================
// Errors
// ============================================================================

pub const ParseError = error{
    InvalidExpression,
    InvalidConditional,
    InvalidValue,
    OutOfMemory,
    UnsupportedFeature,
};

/// Maximum recursion depth for expression parsing to prevent stack overflow
/// from maliciously crafted deeply nested expressions
pub const MAX_PARSE_DEPTH: u32 = 100;

/// Error context for better error messages when parsing fails.
/// Passed as an output parameter to avoid global mutable state.
pub const ErrorContext = struct {
    expression: []const u8 = "",
    feature: []const u8 = "",
    suggestion: []const u8 = "",
    /// Current parsing recursion depth
    depth: u32 = 0,
};

pub const EvalError = error{
    OutOfMemory,
};

pub const EvalResult = struct {
    values: []std.json.Value,
    allocator: std.mem.Allocator,

    pub fn single(alloc: std.mem.Allocator, value: std.json.Value) EvalError!EvalResult {
        var vals = try alloc.alloc(std.json.Value, 1);
        vals[0] = value;
        return EvalResult{ .values = vals, .allocator = alloc };
    }

    pub fn empty(alloc: std.mem.Allocator) EvalResult {
        return EvalResult{ .values = &[_]std.json.Value{}, .allocator = alloc };
    }

    pub fn multi(alloc: std.mem.Allocator, values: []std.json.Value) EvalResult {
        return EvalResult{ .values = values, .allocator = alloc };
    }
};
