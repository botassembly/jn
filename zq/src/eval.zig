const std = @import("std");
const types = @import("types.zig");

// Import types for internal use
const CompareValue = types.CompareValue;
const CompareOp = types.CompareOp;
const BoolOp = types.BoolOp;
const Condition = types.Condition;
const SimpleCondition = types.SimpleCondition;
const IndexExpr = types.IndexExpr;
const SliceExpr = types.SliceExpr;
const Expr = types.Expr;
const ObjectExpr = types.ObjectExpr;
const BuiltinKind = types.BuiltinKind;
const ArithmeticExpr = types.ArithmeticExpr;
const StrFuncExpr = types.StrFuncExpr;
const MapExpr = types.MapExpr;
const ByFuncExpr = types.ByFuncExpr;
const ArrayExpr = types.ArrayExpr;
const DelExpr = types.DelExpr;
const EvalError = types.EvalError;
const EvalResult = types.EvalResult;

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

pub fn getIndex(value: std.json.Value, index: i64) ?std.json.Value {
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

pub fn evalCondition(allocator: std.mem.Allocator, cond: *const Condition, value: std.json.Value) bool {
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

pub fn evalExpr(allocator: std.mem.Allocator, expr: *const Expr, value: std.json.Value) EvalError!EvalResult {
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
        .fabs, .abs => {
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
        // Sprint 07: More math functions
        .exp => {
            const f = switch (value) {
                .integer => |i| @as(f64, @floatFromInt(i)),
                .float => |f| f,
                else => return EvalResult.empty(allocator),
            };
            return try EvalResult.single(allocator, .{ .float = @exp(f) });
        },
        .ln => {
            const f = switch (value) {
                .integer => |i| @as(f64, @floatFromInt(i)),
                .float => |f| f,
                else => return EvalResult.empty(allocator),
            };
            if (f <= 0) return try EvalResult.single(allocator, .null);
            return try EvalResult.single(allocator, .{ .float = @log(f) });
        },
        .log10 => {
            const f = switch (value) {
                .integer => |i| @as(f64, @floatFromInt(i)),
                .float => |f| f,
                else => return EvalResult.empty(allocator),
            };
            if (f <= 0) return try EvalResult.single(allocator, .null);
            return try EvalResult.single(allocator, .{ .float = std.math.log10(f) });
        },
        .log2 => {
            const f = switch (value) {
                .integer => |i| @as(f64, @floatFromInt(i)),
                .float => |f| f,
                else => return EvalResult.empty(allocator),
            };
            if (f <= 0) return try EvalResult.single(allocator, .null);
            return try EvalResult.single(allocator, .{ .float = std.math.log2(f) });
        },
        .sqrt => {
            const f = switch (value) {
                .integer => |i| @as(f64, @floatFromInt(i)),
                .float => |f| f,
                else => return EvalResult.empty(allocator),
            };
            if (f < 0) return try EvalResult.single(allocator, .null);
            return try EvalResult.single(allocator, .{ .float = @sqrt(f) });
        },
        // Sprint 07: Trigonometry functions
        .sin => {
            const f = switch (value) {
                .integer => |i| @as(f64, @floatFromInt(i)),
                .float => |f| f,
                else => return EvalResult.empty(allocator),
            };
            return try EvalResult.single(allocator, .{ .float = @sin(f) });
        },
        .cos => {
            const f = switch (value) {
                .integer => |i| @as(f64, @floatFromInt(i)),
                .float => |f| f,
                else => return EvalResult.empty(allocator),
            };
            return try EvalResult.single(allocator, .{ .float = @cos(f) });
        },
        .tan => {
            const f = switch (value) {
                .integer => |i| @as(f64, @floatFromInt(i)),
                .float => |f| f,
                else => return EvalResult.empty(allocator),
            };
            return try EvalResult.single(allocator, .{ .float = @tan(f) });
        },
        .asin => {
            const f = switch (value) {
                .integer => |i| @as(f64, @floatFromInt(i)),
                .float => |f| f,
                else => return EvalResult.empty(allocator),
            };
            // asin is only valid for [-1, 1]
            if (f < -1 or f > 1) return try EvalResult.single(allocator, .null);
            return try EvalResult.single(allocator, .{ .float = std.math.asin(f) });
        },
        .acos => {
            const f = switch (value) {
                .integer => |i| @as(f64, @floatFromInt(i)),
                .float => |f| f,
                else => return EvalResult.empty(allocator),
            };
            // acos is only valid for [-1, 1]
            if (f < -1 or f > 1) return try EvalResult.single(allocator, .null);
            return try EvalResult.single(allocator, .{ .float = std.math.acos(f) });
        },
        .atan => {
            const f = switch (value) {
                .integer => |i| @as(f64, @floatFromInt(i)),
                .float => |f| f,
                else => return EvalResult.empty(allocator),
            };
            return try EvalResult.single(allocator, .{ .float = std.math.atan(f) });
        },
        // Sprint 06: Generator functions - Date/Time
        .now => {
            // ISO 8601 timestamp in UTC: "2024-12-15T17:30:00Z"
            const timestamp = std.time.timestamp();
            const epoch_seconds = safeTimestampToU64(timestamp) orelse return EvalResult.empty(allocator);
            const epoch_day = epoch_seconds / 86400;
            const day_seconds = epoch_seconds % 86400;
            const hours = day_seconds / 3600;
            const minutes = (day_seconds % 3600) / 60;
            const seconds = day_seconds % 60;

            // Calculate year, month, day from epoch day
            const ymd = epochDayToYmd(epoch_day);

            const str = try std.fmt.allocPrint(allocator, "{d:0>4}-{d:0>2}-{d:0>2}T{d:0>2}:{d:0>2}:{d:0>2}Z", .{
                ymd.year, ymd.month, ymd.day, hours, minutes, seconds,
            });
            return try EvalResult.single(allocator, .{ .string = str });
        },
        .today => {
            // Date only: "2024-12-15"
            const timestamp = std.time.timestamp();
            const epoch_seconds = safeTimestampToU64(timestamp) orelse return EvalResult.empty(allocator);
            const epoch_day = epoch_seconds / 86400;
            const ymd = epochDayToYmd(epoch_day);

            const str = try std.fmt.allocPrint(allocator, "{d:0>4}-{d:0>2}-{d:0>2}", .{
                ymd.year, ymd.month, ymd.day,
            });
            return try EvalResult.single(allocator, .{ .string = str });
        },
        .epoch => {
            // Unix timestamp in seconds
            const timestamp = std.time.timestamp();
            return try EvalResult.single(allocator, .{ .integer = timestamp });
        },
        .epoch_ms => {
            // Unix timestamp in milliseconds
            const timestamp_ns = std.time.nanoTimestamp();
            const timestamp_ms: i64 = @intCast(@divFloor(timestamp_ns, std.time.ns_per_ms));
            return try EvalResult.single(allocator, .{ .integer = timestamp_ms });
        },
        // Sprint 07: Date/Time component generators
        .year => {
            const secs = safeTimestampToU64(std.time.timestamp()) orelse return EvalResult.empty(allocator);
            const epoch_day = secs / 86400;
            const ymd = epochDayToYmd(epoch_day);
            return try EvalResult.single(allocator, .{ .integer = @intCast(ymd.year) });
        },
        .month => {
            const secs = safeTimestampToU64(std.time.timestamp()) orelse return EvalResult.empty(allocator);
            const epoch_day = secs / 86400;
            const ymd = epochDayToYmd(epoch_day);
            return try EvalResult.single(allocator, .{ .integer = @intCast(ymd.month) });
        },
        .day => {
            const secs = safeTimestampToU64(std.time.timestamp()) orelse return EvalResult.empty(allocator);
            const epoch_day = secs / 86400;
            const ymd = epochDayToYmd(epoch_day);
            return try EvalResult.single(allocator, .{ .integer = @intCast(ymd.day) });
        },
        .hour => {
            const secs = safeTimestampToU64(std.time.timestamp()) orelse return EvalResult.empty(allocator);
            const day_seconds = @mod(secs, 86400);
            const hour_val = day_seconds / 3600;
            return try EvalResult.single(allocator, .{ .integer = @intCast(hour_val) });
        },
        .minute => {
            const secs = safeTimestampToU64(std.time.timestamp()) orelse return EvalResult.empty(allocator);
            const day_seconds = @mod(secs, 86400);
            const minute_val = @mod(day_seconds / 60, 60);
            return try EvalResult.single(allocator, .{ .integer = @intCast(minute_val) });
        },
        .second => {
            const secs = safeTimestampToU64(std.time.timestamp()) orelse return EvalResult.empty(allocator);
            const second_val = @mod(secs, 60);
            return try EvalResult.single(allocator, .{ .integer = @intCast(second_val) });
        },
        .time => {
            // HH:MM:SS format
            const secs = safeTimestampToU64(std.time.timestamp()) orelse return EvalResult.empty(allocator);
            const day_seconds = @mod(secs, 86400);
            const hour_val = day_seconds / 3600;
            const minute_val = @mod(day_seconds / 60, 60);
            const second_val = @mod(day_seconds, 60);
            const str = try std.fmt.allocPrint(allocator, "{d:0>2}:{d:0>2}:{d:0>2}", .{ hour_val, minute_val, second_val });
            return try EvalResult.single(allocator, .{ .string = str });
        },
        .week => {
            // ISO week number (1-53)
            const secs = safeTimestampToU64(std.time.timestamp()) orelse return EvalResult.empty(allocator);
            const epoch_day = secs / 86400;
            const week_num = epochDayToIsoWeek(epoch_day);
            return try EvalResult.single(allocator, .{ .integer = @intCast(week_num) });
        },
        .weekday => {
            // Day of week name (Sunday, Monday, etc.)
            const secs = safeTimestampToU64(std.time.timestamp()) orelse return EvalResult.empty(allocator);
            const epoch_day = secs / 86400;
            // Jan 1, 1970 was Thursday (4)
            const day_of_week: usize = @intCast(@mod(epoch_day + 4, 7));
            const day_names = [_][]const u8{ "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday" };
            return try EvalResult.single(allocator, .{ .string = day_names[day_of_week] });
        },
        .weekday_num => {
            // Day of week number (0=Sunday, 6=Saturday)
            const secs = safeTimestampToU64(std.time.timestamp()) orelse return EvalResult.empty(allocator);
            const epoch_day = secs / 86400;
            // Jan 1, 1970 was Thursday (4)
            const day_of_week = @mod(epoch_day + 4, 7);
            return try EvalResult.single(allocator, .{ .integer = @intCast(day_of_week) });
        },
        // Sprint 06: Generator functions - IDs
        .uuid => {
            // UUID v4 (random): "550e8400-e29b-41d4-a716-446655440000"
            var bytes: [16]u8 = undefined;
            std.crypto.random.bytes(&bytes);
            // Set version 4 and variant bits
            bytes[6] = (bytes[6] & 0x0f) | 0x40; // Version 4
            bytes[8] = (bytes[8] & 0x3f) | 0x80; // Variant 1

            const str = try std.fmt.allocPrint(allocator, "{x:0>2}{x:0>2}{x:0>2}{x:0>2}-{x:0>2}{x:0>2}-{x:0>2}{x:0>2}-{x:0>2}{x:0>2}-{x:0>2}{x:0>2}{x:0>2}{x:0>2}{x:0>2}{x:0>2}", .{
                bytes[0],  bytes[1],  bytes[2],  bytes[3],
                bytes[4],  bytes[5],  bytes[6],  bytes[7],
                bytes[8],  bytes[9],  bytes[10], bytes[11],
                bytes[12], bytes[13], bytes[14], bytes[15],
            });
            return try EvalResult.single(allocator, .{ .string = str });
        },
        .shortid => {
            // Base62 8-char ID
            const str = try generateBase62(allocator, 8);
            return try EvalResult.single(allocator, .{ .string = str });
        },
        .sid => {
            // Base62 6-char ID
            const str = try generateBase62(allocator, 6);
            return try EvalResult.single(allocator, .{ .string = str });
        },
        // Sprint 07: More ID generators
        .nanoid => {
            // NanoID: 21 chars, URL-safe alphabet
            // Alphabet: A-Za-z0-9_-
            const str = try generateNanoId(allocator, 21);
            return try EvalResult.single(allocator, .{ .string = str });
        },
        .ulid => {
            // ULID: 26 chars, Crockford Base32, time-sortable
            // Format: TTTTTTTTTTRRRRRRRRRRRRRRR (10 time + 16 random chars)
            const str = try generateUlid(allocator);
            return try EvalResult.single(allocator, .{ .string = str });
        },
        .uuid7 => {
            // UUID v7: 36 chars with dashes, time-sortable
            // Based on Unix timestamp milliseconds
            const str = try generateUuid7(allocator);
            return try EvalResult.single(allocator, .{ .string = str });
        },
        .xid => {
            // XID: 20 chars, URL-safe Base32, sortable
            // 4 bytes time + 3 bytes machine + 2 bytes PID + 3 bytes counter
            const str = try generateXid(allocator);
            return try EvalResult.single(allocator, .{ .string = str });
        },
        // Sprint 06: Generator functions - Random/Sequence
        .random => {
            // Random float between 0.0 and 1.0
            const rand_int = std.crypto.random.int(u64);
            const rand_float = @as(f64, @floatFromInt(rand_int)) / @as(f64, @floatFromInt(std.math.maxInt(u64)));
            return try EvalResult.single(allocator, .{ .float = rand_float });
        },
        .seq => {
            // Incrementing counter (thread-local, resets each run)
            const current = seq_counter;
            seq_counter += 1;
            return try EvalResult.single(allocator, .{ .integer = current });
        },
        // Sprint 06: Transform functions - Numeric
        .incr => {
            switch (value) {
                .integer => |i| {
                    // Handle maxInt(i64) specially to avoid overflow
                    if (i == std.math.maxInt(i64)) {
                        return try EvalResult.single(allocator, .{ .float = @as(f64, @floatFromInt(i)) + 1.0 });
                    }
                    return try EvalResult.single(allocator, .{ .integer = i + 1 });
                },
                .float => |f| return try EvalResult.single(allocator, .{ .float = f + 1.0 }),
                else => return EvalResult.empty(allocator),
            }
        },
        .decr => {
            switch (value) {
                .integer => |i| {
                    // Handle minInt(i64) specially to avoid overflow
                    if (i == std.math.minInt(i64)) {
                        return try EvalResult.single(allocator, .{ .float = @as(f64, @floatFromInt(i)) - 1.0 });
                    }
                    return try EvalResult.single(allocator, .{ .integer = i - 1 });
                },
                .float => |f| return try EvalResult.single(allocator, .{ .float = f - 1.0 }),
                else => return EvalResult.empty(allocator),
            }
        },
        .negate => {
            switch (value) {
                .integer => |i| {
                    // Handle minInt(i64) specially to avoid overflow
                    // since -minInt(i64) cannot be represented as i64
                    if (i == std.math.minInt(i64)) {
                        return try EvalResult.single(allocator, .{ .float = @as(f64, @floatFromInt(std.math.maxInt(i64))) + 1.0 });
                    }
                    return try EvalResult.single(allocator, .{ .integer = -i });
                },
                .float => |f| return try EvalResult.single(allocator, .{ .float = -f }),
                else => return EvalResult.empty(allocator),
            }
        },
        .toggle => {
            switch (value) {
                .bool => |b| return try EvalResult.single(allocator, .{ .bool = !b }),
                else => return EvalResult.empty(allocator),
            }
        },
        // Sprint 06: Transform functions - String
        .trim => {
            switch (value) {
                .string => |s| {
                    const trimmed = std.mem.trim(u8, s, " \t\n\r");
                    return try EvalResult.single(allocator, .{ .string = trimmed });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .ltrim => {
            switch (value) {
                .string => |s| {
                    const trimmed = std.mem.trimLeft(u8, s, " \t\n\r");
                    return try EvalResult.single(allocator, .{ .string = trimmed });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .rtrim => {
            switch (value) {
                .string => |s| {
                    const trimmed = std.mem.trimRight(u8, s, " \t\n\r");
                    return try EvalResult.single(allocator, .{ .string = trimmed });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        // Sprint 06: Type coercion
        .@"int" => {
            switch (value) {
                .integer => return try EvalResult.single(allocator, value),
                .float => |f| {
                    if (f >= @as(f64, @floatFromInt(std.math.minInt(i64))) and
                        f <= @as(f64, @floatFromInt(std.math.maxInt(i64))))
                    {
                        return try EvalResult.single(allocator, .{ .integer = @as(i64, @intFromFloat(f)) });
                    }
                    return try EvalResult.single(allocator, .{ .null = {} });
                },
                .string => |s| {
                    if (std.fmt.parseInt(i64, s, 10)) |i| {
                        return try EvalResult.single(allocator, .{ .integer = i });
                    } else |_| {
                        // Try parsing as float then truncating
                        if (std.fmt.parseFloat(f64, s)) |f| {
                            return try EvalResult.single(allocator, .{ .integer = @as(i64, @intFromFloat(f)) });
                        } else |_| {
                            return try EvalResult.single(allocator, .{ .null = {} });
                        }
                    }
                },
                .bool => |b| return try EvalResult.single(allocator, .{ .integer = if (b) 1 else 0 }),
                .null => return try EvalResult.single(allocator, .{ .null = {} }),
                else => return try EvalResult.single(allocator, .{ .null = {} }),
            }
        },
        .@"float" => {
            switch (value) {
                .float => return try EvalResult.single(allocator, value),
                .integer => |i| return try EvalResult.single(allocator, .{ .float = @as(f64, @floatFromInt(i)) }),
                .string => |s| {
                    if (std.fmt.parseFloat(f64, s)) |f| {
                        return try EvalResult.single(allocator, .{ .float = f });
                    } else |_| {
                        return try EvalResult.single(allocator, .{ .null = {} });
                    }
                },
                .bool => |b| return try EvalResult.single(allocator, .{ .float = if (b) 1.0 else 0.0 }),
                .null => return try EvalResult.single(allocator, .{ .null = {} }),
                else => return try EvalResult.single(allocator, .{ .null = {} }),
            }
        },
        .@"bool" => {
            // Truthy: true, non-zero numbers, non-empty strings, non-empty arrays/objects
            // Falsy: false, 0, "", null, [], {}
            const result = switch (value) {
                .bool => |b| b,
                .integer => |i| i != 0,
                .float => |f| f != 0.0,
                .string => |s| s.len > 0,
                .array => |arr| arr.items.len > 0,
                .object => |obj| obj.count() > 0,
                .null => false,
                else => false,
            };
            return try EvalResult.single(allocator, .{ .bool = result });
        },
        // Sprint 06: Case functions
        .capitalize => {
            switch (value) {
                .string => |s| {
                    if (s.len == 0) return try EvalResult.single(allocator, value);
                    var result = try allocator.alloc(u8, s.len);
                    @memcpy(result, s);
                    if (result[0] >= 'a' and result[0] <= 'z') {
                        result[0] = result[0] - 32;
                    }
                    return try EvalResult.single(allocator, .{ .string = result });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .titlecase => {
            switch (value) {
                .string => |s| {
                    if (s.len == 0) return try EvalResult.single(allocator, value);
                    var result = try allocator.alloc(u8, s.len);
                    var capitalize_next = true;
                    for (s, 0..) |c, i| {
                        if (c == ' ' or c == '\t' or c == '\n' or c == '-' or c == '_') {
                            result[i] = c;
                            capitalize_next = true;
                        } else if (capitalize_next and c >= 'a' and c <= 'z') {
                            result[i] = c - 32;
                            capitalize_next = false;
                        } else if (!capitalize_next and c >= 'A' and c <= 'Z') {
                            result[i] = c + 32;
                            capitalize_next = false;
                        } else {
                            result[i] = c;
                            capitalize_next = false;
                        }
                    }
                    return try EvalResult.single(allocator, .{ .string = result });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .snakecase => {
            switch (value) {
                .string => |s| {
                    const result = try toSnakeCase(allocator, s);
                    return try EvalResult.single(allocator, .{ .string = result });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .camelcase => {
            switch (value) {
                .string => |s| {
                    const result = try toCamelCase(allocator, s, false);
                    return try EvalResult.single(allocator, .{ .string = result });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .kebabcase => {
            switch (value) {
                .string => |s| {
                    const result = try toKebabCase(allocator, s);
                    return try EvalResult.single(allocator, .{ .string = result });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        // Sprint 07: More case functions
        .pascalcase => {
            switch (value) {
                .string => |s| {
                    // PascalCase is just camelCase with first letter uppercase
                    const result = try toCamelCase(allocator, s, true);
                    return try EvalResult.single(allocator, .{ .string = result });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .screamcase => {
            switch (value) {
                .string => |s| {
                    // SCREAMING_SNAKE_CASE: snake_case but uppercase
                    const snake = try toSnakeCase(allocator, s);
                    // Convert to uppercase
                    for (snake) |*c| {
                        if (c.* >= 'a' and c.* <= 'z') {
                            c.* = c.* - 32;
                        }
                    }
                    return try EvalResult.single(allocator, .{ .string = snake });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        // Sprint 06: Predicates
        .empty => {
            const result = switch (value) {
                .string => |s| s.len == 0,
                .array => |arr| arr.items.len == 0,
                .object => |obj| obj.count() == 0,
                else => false,
            };
            return try EvalResult.single(allocator, .{ .bool = result });
        },
        // Sprint 06: String splitting
        .words => {
            switch (value) {
                .string => |s| {
                    var words_list: std.ArrayListUnmanaged(std.json.Value) = .empty;
                    var iter = std.mem.tokenizeAny(u8, s, " \t\n\r");
                    while (iter.next()) |word| {
                        try words_list.append(allocator, .{ .string = word });
                    }
                    const result_slice = try words_list.toOwnedSlice(allocator);
                    return try EvalResult.single(allocator, .{ .array = .{
                        .items = result_slice,
                        .capacity = result_slice.len,
                        .allocator = allocator,
                    } });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .lines => {
            switch (value) {
                .string => |s| {
                    var lines_list: std.ArrayListUnmanaged(std.json.Value) = .empty;
                    var iter = std.mem.splitSequence(u8, s, "\n");
                    while (iter.next()) |line| {
                        // Trim \r from line endings
                        const trimmed_line = std.mem.trimRight(u8, line, "\r");
                        try lines_list.append(allocator, .{ .string = trimmed_line });
                    }
                    const result_slice = try lines_list.toOwnedSlice(allocator);
                    return try EvalResult.single(allocator, .{ .array = .{
                        .items = result_slice,
                        .capacity = result_slice.len,
                        .allocator = allocator,
                    } });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .chars => {
            switch (value) {
                .string => |s| {
                    var chars_list: std.ArrayListUnmanaged(std.json.Value) = .empty;
                    for (s) |c| {
                        const char_str = try allocator.alloc(u8, 1);
                        char_str[0] = c;
                        try chars_list.append(allocator, .{ .string = char_str });
                    }
                    const result_slice = try chars_list.toOwnedSlice(allocator);
                    return try EvalResult.single(allocator, .{ .array = .{
                        .items = result_slice,
                        .capacity = result_slice.len,
                        .allocator = allocator,
                    } });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        // Sprint 06: Slug
        .slugify => {
            switch (value) {
                .string => |s| {
                    const result = try toSlug(allocator, s);
                    return try EvalResult.single(allocator, .{ .string = result });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        // Sprint 08: Time functions
        .xid_time => {
            // Extract epoch seconds from XID string (20 chars total, first 4 bytes = timestamp)
            switch (value) {
                .string => |s| {
                    if (s.len < 20) return try EvalResult.single(allocator, .null);
                    const timestamp = decodeXidTimestamp(s) orelse return try EvalResult.single(allocator, .null);
                    return try EvalResult.single(allocator, .{ .integer = @intCast(timestamp) });
                },
                else => return EvalResult.empty(allocator),
            }
        },
        .delta => {
            // Seconds since a timestamp (accepts epoch int or ISO string)
            const now_secs: i64 = std.time.timestamp();
            const then_secs: i64 = switch (value) {
                .integer => |i| i,
                .string => |s| parseIsoTimestamp(s) orelse return try EvalResult.single(allocator, .null),
                else => return EvalResult.empty(allocator),
            };
            return try EvalResult.single(allocator, .{ .integer = now_secs - then_secs });
        },
        .ago => {
            // Human-friendly relative time string
            const now_secs: i64 = std.time.timestamp();
            const then_secs: i64 = switch (value) {
                .integer => |i| i,
                .string => |s| parseIsoTimestamp(s) orelse return try EvalResult.single(allocator, .null),
                else => return EvalResult.empty(allocator),
            };
            const diff = now_secs - then_secs;
            const ago_str = try formatAgo(allocator, diff);
            return try EvalResult.single(allocator, .{ .string = ago_str });
        },
    }
}

/// Thread-local sequence counter for the `seq` generator function.
///
/// IMPORTANT: Thread-local state behavior:
/// - Counter starts at 1 for each thread
/// - Persists across all records processed within the same thread/process
/// - Resets when the process exits (not between pipeline invocations within the same process)
/// - For single-threaded CLI use (jn filter), this means the counter increments
///   monotonically for the entire pipeline run
/// - NOT suitable for generating unique IDs across separate process invocations
threadlocal var seq_counter: i64 = 1;

// Helper: Safely convert timestamp to u64, returning null for negative values
// (negative timestamps can occur with misconfigured system clocks)
fn safeTimestampToU64(timestamp: i64) ?u64 {
    if (timestamp < 0) return null;
    return @intCast(timestamp);
}

// Helper: Convert epoch day (days since 1970-01-01) to year/month/day
const YearMonthDay = struct { year: u32, month: u32, day: u32 };

fn epochDayToYmd(epoch_day: u64) YearMonthDay {
    // Algorithm from http://howardhinnant.github.io/date_algorithms.html
    const z = epoch_day + 719468;
    const era = z / 146097;
    const doe = z - era * 146097;
    const yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    const y = yoe + era * 400;
    const doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    const mp = (5 * doy + 2) / 153;
    const d = doy - (153 * mp + 2) / 5 + 1;
    const m = if (mp < 10) mp + 3 else mp - 9;
    const year = if (m <= 2) y + 1 else y;

    return .{
        .year = @intCast(year),
        .month = @intCast(m),
        .day = @intCast(d),
    };
}

// Helper: Calculate ISO week number (1-53)
fn epochDayToIsoWeek(epoch_day: u64) u32 {
    // ISO 8601 week number formula
    // Week 1 is the week containing the first Thursday of the year

    const ymd = epochDayToYmd(epoch_day);

    // Calculate day of year (1-indexed)
    const days_in_months = [_]u32{ 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334 };
    var day_of_year: u32 = days_in_months[ymd.month - 1] + ymd.day;

    // Add leap day if after Feb in a leap year
    if (ymd.month > 2 and isLeapYear(ymd.year)) {
        day_of_year += 1;
    }

    // Day of week: 1=Monday, 7=Sunday (ISO)
    // Jan 1, 1970 was Thursday
    const dow: u32 = @intCast(@mod(epoch_day + 3, 7) + 1);

    // ISO week number formula:
    // week = (day_of_year - dow + 10) / 7
    // This formula accounts for the Thursday rule
    const week_calc: i32 = @divFloor(@as(i32, @intCast(day_of_year)) - @as(i32, @intCast(dow)) + 10, 7);

    if (week_calc < 1) {
        // Week belongs to previous year - calculate weeks in previous year
        return weeksInYear(ymd.year - 1);
    } else if (week_calc > weeksInYear(ymd.year)) {
        // Week belongs to next year
        return 1;
    }

    return @intCast(week_calc);
}

fn isLeapYear(year: u32) bool {
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0);
}

fn weeksInYear(year: u32) u32 {
    // A year has 53 weeks if Jan 1 is Thursday, or
    // Jan 1 is Wednesday and it's a leap year
    const jan1_dow = getJan1Weekday(year);
    if (jan1_dow == 4) return 53; // Thursday
    if (jan1_dow == 3 and isLeapYear(year)) return 53; // Wednesday + leap
    return 52;
}

fn getJan1Weekday(year: u32) u32 {
    // Day of week for Jan 1 of given year (1=Monday, 7=Sunday)
    // Using a standard formula
    const y = year - 1;
    const day = (1 + 5 * (y % 4) + 4 * (y % 100) + 6 * (y % 400)) % 7;
    // Result: 0=Sunday, 1=Monday, ..., 6=Saturday
    // Convert to ISO: 1=Monday, 7=Sunday
    return if (day == 0) 7 else day;
}

// Base62 alphabet for shortid/sid
const base62_alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

fn generateBase62(allocator: std.mem.Allocator, len: usize) ![]u8 {
    var result = try allocator.alloc(u8, len);
    var rand_bytes: [16]u8 = undefined;
    std.crypto.random.bytes(&rand_bytes);

    for (0..len) |i| {
        const rand_idx = rand_bytes[i % 16] % 62;
        result[i] = base62_alphabet[rand_idx];
    }
    return result;
}

// Sprint 07: NanoID - URL-safe alphabet
const nanoid_alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-";

fn generateNanoId(allocator: std.mem.Allocator, len: usize) ![]u8 {
    var result = try allocator.alloc(u8, len);
    var rand_bytes: [32]u8 = undefined;
    std.crypto.random.bytes(&rand_bytes);

    for (0..len) |i| {
        const rand_idx = rand_bytes[i % 32] % 64;
        result[i] = nanoid_alphabet[rand_idx];
    }
    return result;
}

// Sprint 07: ULID - Crockford Base32, time-sortable
const crockford_alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

fn generateUlid(allocator: std.mem.Allocator) ![]u8 {
    var result = try allocator.alloc(u8, 26);

    // Get timestamp in milliseconds
    const timestamp_ns = std.time.nanoTimestamp();
    var timestamp_ms: u64 = @intCast(@divFloor(timestamp_ns, std.time.ns_per_ms));

    // Encode 48-bit timestamp as first 10 characters (Crockford Base32)
    var i: usize = 9;
    while (i < 10) : (i -%= 1) {
        result[i] = crockford_alphabet[@intCast(timestamp_ms & 0x1f)];
        timestamp_ms >>= 5;
        if (i == 0) break;
    }

    // Generate 80 bits of randomness for remaining 16 characters
    var rand_bytes: [10]u8 = undefined;
    std.crypto.random.bytes(&rand_bytes);

    // Encode random bytes as Base32
    // Each char is 5 bits, so 16 chars = 80 bits = 10 bytes
    var rand_bits: u80 = 0;
    for (rand_bytes) |b| {
        rand_bits = (rand_bits << 8) | b;
    }

    var j: usize = 25;
    while (j >= 10) : (j -%= 1) {
        result[j] = crockford_alphabet[@intCast(rand_bits & 0x1f)];
        rand_bits >>= 5;
        if (j == 10) break;
    }

    return result;
}

// Sprint 07: UUID v7 - time-sortable UUID
fn generateUuid7(allocator: std.mem.Allocator) ![]u8 {
    // UUID v7: xxxxxxxx-xxxx-7xxx-yxxx-xxxxxxxxxxxx
    // First 48 bits: Unix timestamp in milliseconds
    // Next 4 bits: version (7)
    // Next 12 bits: random
    // Next 2 bits: variant (10)
    // Remaining 62 bits: random

    const timestamp_ns = std.time.nanoTimestamp();
    const timestamp_ms: u64 = @intCast(@divFloor(timestamp_ns, std.time.ns_per_ms));

    var bytes: [16]u8 = undefined;

    // Timestamp (48 bits, big-endian)
    bytes[0] = @intCast((timestamp_ms >> 40) & 0xff);
    bytes[1] = @intCast((timestamp_ms >> 32) & 0xff);
    bytes[2] = @intCast((timestamp_ms >> 24) & 0xff);
    bytes[3] = @intCast((timestamp_ms >> 16) & 0xff);
    bytes[4] = @intCast((timestamp_ms >> 8) & 0xff);
    bytes[5] = @intCast(timestamp_ms & 0xff);

    // Random bytes for the rest
    std.crypto.random.bytes(bytes[6..]);

    // Set version 7
    bytes[6] = (bytes[6] & 0x0f) | 0x70;
    // Set variant (10xx)
    bytes[8] = (bytes[8] & 0x3f) | 0x80;

    return try std.fmt.allocPrint(allocator, "{x:0>2}{x:0>2}{x:0>2}{x:0>2}-{x:0>2}{x:0>2}-{x:0>2}{x:0>2}-{x:0>2}{x:0>2}-{x:0>2}{x:0>2}{x:0>2}{x:0>2}{x:0>2}{x:0>2}", .{
        bytes[0],  bytes[1],  bytes[2],  bytes[3],
        bytes[4],  bytes[5],  bytes[6],  bytes[7],
        bytes[8],  bytes[9],  bytes[10], bytes[11],
        bytes[12], bytes[13], bytes[14], bytes[15],
    });
}

/// Sprint 07: XID - compact, sortable ID
/// XID alphabet is lowercase hex-extended with more URL-safe chars
const xid_alphabet = "0123456789abcdefghijklmnopqrstuv";

/// Thread-local XID counter (24-bit, wraps at 16 million).
///
/// IMPORTANT: Thread-local state behavior:
/// - Counter wraps around after 2^24 (16,777,216) XIDs within the same thread
/// - Combined with machine_id and timestamp, provides uniqueness within a process
/// - Resets to 0 when the process exits
/// - For single-threaded CLI use, XIDs are unique within a single pipeline run
threadlocal var xid_counter: u24 = 0;

/// Thread-local machine ID for XID generation (3 random bytes, cached).
///
/// Initialized once per thread on first XID generation. Provides uniqueness
/// across different processes generating XIDs at the same timestamp.
threadlocal var xid_machine_id: ?[3]u8 = null;

fn generateXid(allocator: std.mem.Allocator) ![]u8 {
    var result = try allocator.alloc(u8, 20);

    // 4 bytes: unix timestamp (seconds)
    const timestamp: u32 = @intCast(std.time.timestamp());

    // 3 bytes: machine ID (random, cached)
    if (xid_machine_id == null) {
        var machine: [3]u8 = undefined;
        std.crypto.random.bytes(&machine);
        xid_machine_id = machine;
    }
    const machine_id = xid_machine_id.?;

    // 2 bytes: PID (use random since we don't have easy PID access)
    var pid_bytes: [2]u8 = undefined;
    std.crypto.random.bytes(&pid_bytes);

    // 3 bytes: counter
    xid_counter +%= 1;
    const counter = xid_counter;

    // Pack into 12 bytes
    var bytes: [12]u8 = undefined;
    bytes[0] = @intCast((timestamp >> 24) & 0xff);
    bytes[1] = @intCast((timestamp >> 16) & 0xff);
    bytes[2] = @intCast((timestamp >> 8) & 0xff);
    bytes[3] = @intCast(timestamp & 0xff);
    bytes[4] = machine_id[0];
    bytes[5] = machine_id[1];
    bytes[6] = machine_id[2];
    bytes[7] = pid_bytes[0];
    bytes[8] = pid_bytes[1];
    bytes[9] = @intCast((counter >> 16) & 0xff);
    bytes[10] = @intCast((counter >> 8) & 0xff);
    bytes[11] = @intCast(counter & 0xff);

    // Encode as base32 (20 chars for 12 bytes * 8 bits / 5 bits per char = 19.2, round to 20)
    // Actually XID uses a specific encoding: 12 bytes -> 20 chars
    // Each 5 bits becomes one character
    var bits: u96 = 0;
    for (bytes) |b| {
        bits = (bits << 8) | b;
    }

    var i: usize = 19;
    while (i < 20) : (i -%= 1) {
        result[i] = xid_alphabet[@intCast(bits & 0x1f)];
        bits >>= 5;
        if (i == 0) break;
    }

    return result;
}

// Sprint 06: Case conversion helpers

/// Convert string to snake_case
/// "HelloWorld" -> "hello_world"
/// "hello-world" -> "hello_world"
/// "Hello World" -> "hello_world"
fn toSnakeCase(allocator: std.mem.Allocator, s: []const u8) ![]u8 {
    if (s.len == 0) return try allocator.alloc(u8, 0);

    // First pass: count output length
    var output_len: usize = 0;
    var prev_lower = false;
    for (s) |c| {
        if (c == ' ' or c == '-' or c == '_') {
            if (output_len > 0) output_len += 1; // add underscore
            prev_lower = false;
        } else if (c >= 'A' and c <= 'Z') {
            if (prev_lower and output_len > 0) output_len += 1; // add underscore before uppercase
            output_len += 1;
            prev_lower = false;
        } else {
            output_len += 1;
            prev_lower = (c >= 'a' and c <= 'z');
        }
    }

    // Second pass: build output
    var result = try allocator.alloc(u8, output_len);
    var pos: usize = 0;
    prev_lower = false;

    for (s) |c| {
        if (c == ' ' or c == '-' or c == '_') {
            if (pos > 0) {
                result[pos] = '_';
                pos += 1;
            }
            prev_lower = false;
        } else if (c >= 'A' and c <= 'Z') {
            if (prev_lower and pos > 0) {
                result[pos] = '_';
                pos += 1;
            }
            result[pos] = c + 32; // lowercase
            pos += 1;
            prev_lower = false;
        } else {
            result[pos] = c;
            pos += 1;
            prev_lower = (c >= 'a' and c <= 'z');
        }
    }

    return result[0..pos];
}

/// Convert string to camelCase or PascalCase
/// "hello_world" -> "helloWorld" (pascal=false)
/// "hello_world" -> "HelloWorld" (pascal=true)
fn toCamelCase(allocator: std.mem.Allocator, s: []const u8, pascal: bool) ![]u8 {
    if (s.len == 0) return try allocator.alloc(u8, 0);

    // First pass: count output length (skip separators)
    var output_len: usize = 0;
    for (s) |c| {
        if (c != ' ' and c != '-' and c != '_') {
            output_len += 1;
        }
    }

    var result = try allocator.alloc(u8, output_len);
    var pos: usize = 0;
    var capitalize_next = pascal;

    for (s) |c| {
        if (c == ' ' or c == '-' or c == '_') {
            capitalize_next = true;
        } else if (capitalize_next) {
            if (c >= 'a' and c <= 'z') {
                result[pos] = c - 32;
            } else {
                result[pos] = c;
            }
            pos += 1;
            capitalize_next = false;
        } else {
            if (c >= 'A' and c <= 'Z') {
                result[pos] = c + 32;
            } else {
                result[pos] = c;
            }
            pos += 1;
        }
    }

    return result[0..pos];
}

/// Convert string to kebab-case
/// "HelloWorld" -> "hello-world"
/// "hello_world" -> "hello-world"
fn toKebabCase(allocator: std.mem.Allocator, s: []const u8) ![]u8 {
    if (s.len == 0) return try allocator.alloc(u8, 0);

    // First pass: count output length
    var output_len: usize = 0;
    var prev_lower = false;
    for (s) |c| {
        if (c == ' ' or c == '-' or c == '_') {
            if (output_len > 0) output_len += 1;
            prev_lower = false;
        } else if (c >= 'A' and c <= 'Z') {
            if (prev_lower and output_len > 0) output_len += 1;
            output_len += 1;
            prev_lower = false;
        } else {
            output_len += 1;
            prev_lower = (c >= 'a' and c <= 'z');
        }
    }

    // Second pass: build output
    var result = try allocator.alloc(u8, output_len);
    var pos: usize = 0;
    prev_lower = false;

    for (s) |c| {
        if (c == ' ' or c == '-' or c == '_') {
            if (pos > 0) {
                result[pos] = '-';
                pos += 1;
            }
            prev_lower = false;
        } else if (c >= 'A' and c <= 'Z') {
            if (prev_lower and pos > 0) {
                result[pos] = '-';
                pos += 1;
            }
            result[pos] = c + 32;
            pos += 1;
            prev_lower = false;
        } else {
            result[pos] = c;
            pos += 1;
            prev_lower = (c >= 'a' and c <= 'z');
        }
    }

    return result[0..pos];
}

/// Convert string to URL-safe slug
/// "Hello World!" -> "hello-world"
/// "This & That" -> "this-that"
fn toSlug(allocator: std.mem.Allocator, s: []const u8) ![]u8 {
    if (s.len == 0) return try allocator.alloc(u8, 0);

    // First pass: count output length
    var output_len: usize = 0;
    var prev_dash = true; // Start true to avoid leading dash

    for (s) |c| {
        if ((c >= 'a' and c <= 'z') or (c >= '0' and c <= '9')) {
            output_len += 1;
            prev_dash = false;
        } else if (c >= 'A' and c <= 'Z') {
            output_len += 1;
            prev_dash = false;
        } else if (!prev_dash) {
            // Any non-alphanumeric becomes a dash
            output_len += 1;
            prev_dash = true;
        }
    }

    // Remove trailing dash if present
    if (output_len > 0 and prev_dash) output_len -= 1;

    var result = try allocator.alloc(u8, output_len);
    var pos: usize = 0;
    prev_dash = true;

    for (s) |c| {
        if ((c >= 'a' and c <= 'z') or (c >= '0' and c <= '9')) {
            result[pos] = c;
            pos += 1;
            prev_dash = false;
        } else if (c >= 'A' and c <= 'Z') {
            result[pos] = c + 32; // lowercase
            pos += 1;
            prev_dash = false;
        } else if (!prev_dash and pos < output_len) {
            result[pos] = '-';
            pos += 1;
            prev_dash = true;
        }
    }

    return result[0..pos];
}

// Sprint 08: XID timestamp decoding
fn decodeXidTimestamp(s: []const u8) ?u32 {
    // XID is 20 chars base32 encoding 12 bytes (96 bits)
    // First 4 bytes (32 bits) are the timestamp
    // We need to decode all 20 chars and extract the top 32 bits
    if (s.len < 20) return null;

    // Decode all 20 characters to 96 bits
    var bits: u128 = 0; // Use u128 to hold 96 bits safely
    for (s[0..20]) |c| {
        const val: u128 = if (c >= '0' and c <= '9')
            c - '0'
        else if (c >= 'a' and c <= 'v')
            c - 'a' + 10
        else
            return null; // Invalid character
        bits = (bits << 5) | val;
    }

    // 20 chars * 5 bits = 100 bits, but we only have 96 bits of data
    // The encoding uses the full 100 bits, so top 4 bits are padding
    // Extract timestamp from bits 64-95 (after removing 4 padding bits from top)
    const timestamp: u32 = @truncate(bits >> 64);
    return timestamp;
}

// Sprint 08: Parse ISO timestamp to epoch seconds
fn parseIsoTimestamp(s: []const u8) ?i64 {
    // Parse "2024-12-15T17:30:00Z" or "2024-12-15T17:30:00" or "2024-12-15"
    if (s.len < 10) return null;

    // Parse year
    const year = std.fmt.parseInt(u32, s[0..4], 10) catch return null;
    if (s[4] != '-') return null;

    // Parse month
    const month = std.fmt.parseInt(u32, s[5..7], 10) catch return null;
    if (month < 1 or month > 12) return null;
    if (s[7] != '-') return null;

    // Parse day
    const day = std.fmt.parseInt(u32, s[8..10], 10) catch return null;
    if (day < 1 or day > 31) return null;

    // Calculate days since epoch
    var days: i64 = 0;

    // Years since 1970
    var y: u32 = 1970;
    while (y < year) : (y += 1) {
        days += if (isLeapYear(y)) 366 else 365;
    }

    // Months
    const days_in_months = [_]u32{ 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };
    var m: u32 = 1;
    while (m < month) : (m += 1) {
        days += days_in_months[m - 1];
        if (m == 2 and isLeapYear(year)) days += 1;
    }

    // Days
    days += day - 1;

    // Convert to seconds
    var secs = days * 86400;

    // Parse time if present
    if (s.len >= 19 and s[10] == 'T') {
        const hour = std.fmt.parseInt(u32, s[11..13], 10) catch return null;
        if (hour > 23) return null;
        const minute = std.fmt.parseInt(u32, s[14..16], 10) catch return null;
        if (minute > 59) return null;
        const second = std.fmt.parseInt(u32, s[17..19], 10) catch return null;
        if (second > 59) return null;
        secs += hour * 3600 + minute * 60 + second;
    }

    return secs;
}

// Sprint 08: Format seconds as human-friendly "ago" string
fn formatAgo(allocator: std.mem.Allocator, diff: i64) ![]u8 {
    const abs_diff: u64 = if (diff < 0) @intCast(-diff) else @intCast(diff);
    const suffix = if (diff < 0) " from now" else " ago";

    if (abs_diff < 60) {
        return try std.fmt.allocPrint(allocator, "{d} second{s}{s}", .{
            abs_diff,
            if (abs_diff == 1) "" else "s",
            suffix,
        });
    }

    const minutes = abs_diff / 60;
    if (minutes < 60) {
        return try std.fmt.allocPrint(allocator, "{d} minute{s}{s}", .{
            minutes,
            if (minutes == 1) "" else "s",
            suffix,
        });
    }

    const hours = abs_diff / 3600;
    const remaining_mins = (abs_diff % 3600) / 60;
    if (hours < 24) {
        if (remaining_mins > 0) {
            return try std.fmt.allocPrint(allocator, "{d} hour{s}, {d} minute{s}{s}", .{
                hours,
                if (hours == 1) "" else "s",
                remaining_mins,
                if (remaining_mins == 1) "" else "s",
                suffix,
            });
        } else {
            return try std.fmt.allocPrint(allocator, "{d} hour{s}{s}", .{
                hours,
                if (hours == 1) "" else "s",
                suffix,
            });
        }
    }

    const days = abs_diff / 86400;
    const remaining_hours = (abs_diff % 86400) / 3600;
    if (days < 30) {
        if (remaining_hours > 0) {
            return try std.fmt.allocPrint(allocator, "{d} day{s}, {d} hour{s}{s}", .{
                days,
                if (days == 1) "" else "s",
                remaining_hours,
                if (remaining_hours == 1) "" else "s",
                suffix,
            });
        } else {
            return try std.fmt.allocPrint(allocator, "{d} day{s}{s}", .{
                days,
                if (days == 1) "" else "s",
                suffix,
            });
        }
    }

    const months = days / 30;
    const remaining_days = days % 30;
    if (months < 12) {
        if (remaining_days > 0) {
            return try std.fmt.allocPrint(allocator, "{d} month{s}, {d} day{s}{s}", .{
                months,
                if (months == 1) "" else "s",
                remaining_days,
                if (remaining_days == 1) "" else "s",
                suffix,
            });
        } else {
            return try std.fmt.allocPrint(allocator, "{d} month{s}{s}", .{
                months,
                if (months == 1) "" else "s",
                suffix,
            });
        }
    }

    const years = days / 365;
    const remaining_months = (days % 365) / 30;
    if (remaining_months > 0) {
        return try std.fmt.allocPrint(allocator, "{d} year{s}, {d} month{s}{s}", .{
            years,
            if (years == 1) "" else "s",
            remaining_months,
            if (remaining_months == 1) "" else "s",
            suffix,
        });
    } else {
        return try std.fmt.allocPrint(allocator, "{d} year{s}{s}", .{
            years,
            if (years == 1) "" else "s",
            suffix,
        });
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
// Evaluator Tests
// ============================================================================

const parser = @import("parser.zig");
const parseExprWithContext = parser.parseExprWithContext;
const parseCondition = parser.parseCondition;
const ErrorContext = types.ErrorContext;

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
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[1,2,3]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    // std.math.minInt(i64) is -9223372036854775808
    // Negating it would overflow since max i64 is 9223372036854775807
    // This should return null, not crash
    try std.testing.expect(getIndex(parsed.value, std.math.minInt(i64)) == null);
}

test "eval pipe" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":\"42\"}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".x | tonumber", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 42), result.values[0].integer);
}

test "eval object construction" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":1,\"y\":2}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "{a: .x, b: .y}", &err_ctx);
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

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".x // .y", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 1), result.values[0].integer);
}

test "eval arithmetic" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"a\":10,\"b\":3}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".a + .b", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 13), result.values[0].integer);
}

test "eval string concatenation" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"a\":\"foo\",\"b\":\"bar\"}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".a + .b", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqualStrings("foobar", result.values[0].string);
}

test "eval conditional true" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":10}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "if .x > 5 then .x else .y end", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 10), result.values[0].integer);
}

test "eval type function" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":1}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "type", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqualStrings("object", result.values[0].string);
}

test "eval length function" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "length", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expectEqual(@as(i64, 5), result.values[0].integer);
}

test "eval slice" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"items\":[0,1,2,3,4,5,6]}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".items[2:5]", &err_ctx);
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

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), ".items[-2:]", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const arr = result.values[0].array;
    try std.testing.expectEqual(@as(usize, 2), arr.items.len);
    try std.testing.expectEqual(@as(i64, 2), arr.items[0].integer);
    try std.testing.expectEqual(@as(i64, 3), arr.items[1].integer);
}

test "eval has true" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":1}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "has(\"x\")", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool);
}

test "eval has false" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":1}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "has(\"y\")", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(!result.values[0].bool);
}

test "eval has null value" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":null}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "has(\"x\")", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool); // key exists even if null
}

test "eval del" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"x\":1,\"y\":2}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "del(.x)", &err_ctx);
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

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "del(.z)", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const obj = result.values[0].object;
    try std.testing.expect(obj.get("x") != null); // x still there
}

test "eval del array index" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"arr\":[1,2,3]}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "del(.arr[0])", &err_ctx);
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

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "del(.arr[-1])", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const obj = result.values[0].object;
    const arr = obj.get("arr").?.array;
    try std.testing.expectEqual(@as(usize, 2), arr.items.len);
    try std.testing.expectEqual(@as(i64, 1), arr.items[0].integer);
    try std.testing.expectEqual(@as(i64, 2), arr.items[1].integer);
}

test "eval to_entries" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "{\"a\":1,\"b\":2}";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "to_entries", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const arr = result.values[0].array;
    try std.testing.expectEqual(@as(usize, 2), arr.items.len);
    try std.testing.expect(arr.items[0].object.get("key") != null);
    try std.testing.expect(arr.items[0].object.get("value") != null);
}

test "eval from_entries" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "[{\"key\":\"x\",\"value\":1},{\"key\":\"y\",\"value\":2}]";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "from_entries", &err_ctx);
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

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "from_entries", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    const obj = result.values[0].object;
    try std.testing.expectEqual(@as(i64, 1), obj.get("x").?.integer);
}

test "eval test contains" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello world\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "test(\"wor\")", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool);
}

test "eval test starts with" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello world\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "test(\"^hello\")", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool);
}

test "eval test ends with" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello world\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "test(\"world$\")", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool);
}

test "eval test exact match" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "test(\"^hello$\")", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(result.values[0].bool);
}

test "eval test no match" {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit();

    const json = "\"hello world\"";
    const parsed = try std.json.parseFromSlice(std.json.Value, arena.allocator(), json, .{});

    var err_ctx: ErrorContext = .{};
    const expr = try parseExprWithContext(arena.allocator(), "test(\"^world\")", &err_ctx);
    const result = try evalExpr(arena.allocator(), &expr, parsed.value);

    try std.testing.expectEqual(@as(usize, 1), result.values.len);
    try std.testing.expect(!result.values[0].bool);
}
