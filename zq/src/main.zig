const std = @import("std");
const zig_builtin = @import("builtin");
const types = @import("types.zig");
const output = @import("output.zig");
const parser = @import("parser.zig");

// Re-export types for internal use
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
const parsePath = parser.parsePath;
const parseValue = parser.parseValue;

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
