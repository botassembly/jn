const std = @import("std");
const zig_builtin = @import("builtin");
const types = @import("types.zig");
const output = @import("output.zig");
const parser = @import("parser.zig");
const eval = @import("eval.zig");

// Re-export types for internal use
const Config = types.Config;
const ParseError = types.ParseError;
const ErrorContext = types.ErrorContext;
const EvalError = types.EvalError;
const EvalResult = types.EvalResult;
const MAX_PARSE_DEPTH = types.MAX_PARSE_DEPTH;

// Re-export output functions for internal use
const writeJson = output.writeJson;
const writeJsonValue = output.writeJsonValue;

// Re-export parser functions for internal use
const checkUnsupportedFeatures = parser.checkUnsupportedFeatures;
const parseExprWithContext = parser.parseExprWithContext;
const parseExpr = parser.parseExpr;
const parseCondition = parser.parseCondition;

// Re-export eval functions for internal use
const evalExpr = eval.evalExpr;
const evalCondition = eval.evalCondition;
const getIndex = eval.getIndex;

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
