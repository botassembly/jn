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
        \\GENERATOR FUNCTIONS:
        \\  now                ISO 8601 timestamp (UTC)
        \\  today              Date only (YYYY-MM-DD)
        \\  epoch              Unix timestamp (seconds)
        \\  epoch_ms           Unix timestamp (milliseconds)
        \\  uuid               UUID v4 (random)
        \\  shortid            Base62 ID (8 chars)
        \\  sid                Base62 ID (6 chars)
        \\  random             Random float 0.0-1.0
        \\  seq                Incrementing counter (1, 2, 3...)
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
        \\  # Generator functions:
        \\  echo '{}' | zq '{id: uuid, created: now}'  # Add ID and timestamp
        \\  cat data.ndjson | zq '{row: seq, data: .}' # Add row numbers
        \\  echo '{}' | zq 'shortid'                   # Generate 8-char ID
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
    var stdout_writer_wrapper = std.fs.File.stdout().writerStreaming(&stdout_buffer);
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
