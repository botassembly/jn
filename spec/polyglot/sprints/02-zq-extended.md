# Sprint 02: ZQ Extended Features

**Goal:** Add object construction, type functions, and control flow to ZQ

**Prerequisite:** Sprint 01 complete

**Status:** COMPLETE

---

## Deliverables

1. Object construction expressions
2. Type conversion functions
3. Alternative operator (//)
4. Pipe support (|)
5. Conditional expressions (if-then-else)
6. Arithmetic operators

---

## Phase 1: Object Construction

### Basic Object Literals
- [x] `{a: .x, b: .y}` - object with field access
- [x] `{name: .user.name, id: .uuid}` - nested paths
- [x] `{a: 1, b: "str"}` - literal values
- [x] `{a, b}` - shorthand for `{a: .a, b: .b}`

### Dynamic Keys
- [x] `{(.key): .value}` - computed key from field
- [x] `{(.type): .data}` - dynamic object creation

### Quality Gate
- [x] `echo '{"x":1,"y":2}' | zq '{a:.x,b:.y}'` → `{"a":1,"b":2}`
- [x] All object tests pass

---

## Phase 2: Type Functions

### Conversion
- [x] `tonumber` - string → number
- [x] `tostring` - any → string
- [x] `type` - returns type name

### Type Checking
- [x] `isnumber` - true if number
- [x] `isstring` - true if string
- [x] `isboolean` - true if boolean
- [x] `isnull` - true if null
- [x] `isarray` - true if array
- [x] `isobject` - true if object

### Additional Functions
- [x] `length` - string/array/object length
- [x] `keys` - object keys as array
- [x] `values` - object values as array

### Quality Gate
- [x] `echo '{"x":"42"}' | zq '.x | tonumber'` → `42`
- [x] Type functions work in select conditions

---

## Phase 3: Control Flow

### Alternative Operator
- [x] `.x // .y` - first non-null
- [x] `.x // "default"` - default value
- [x] `.x // .y // .z` - chain

### Conditional
- [x] `if .x then .a else .b end` - basic conditional
- [x] `if .x > 0 then "positive" else "negative" end`
- [x] Nested conditionals

### Quality Gate
- [x] `echo '{"x":null,"y":1}' | zq '.x // .y'` → `1`
- [x] Conditionals work with all comparison operators

---

## Phase 4: Pipe Support

### Basic Pipes
- [x] `.x | tonumber` - chain operations
- [x] `select(.active) | .name` - filter then extract
- [x] `.[] | .name` - iterate then extract

### Multi-stage Pipes
- [x] `.data | .[] | select(.x > 0) | {id: .id}`
- [x] Proper short-circuit evaluation

### Quality Gate
- [x] All piped expressions work
- [x] Performance within 20% of non-piped equivalents

---

## Phase 5: Additional Operators

### Arithmetic (in expressions)
- [x] `.x + .y` - addition
- [x] `.x - .y` - subtraction
- [x] `.x * .y` - multiplication
- [x] `.x / .y` - division
- [x] `.x % .y` - modulo

### String Operations
- [x] `.x + .y` - string concatenation
- [x] `length` - string/array length

### Quality Gate
- [x] `echo '{"x":1,"y":2}' | zq '.x + .y'` → `3`
- [x] String concat works

---

## Phase 6: Testing

### New Tests
- [x] Object construction tests
- [x] Type function tests
- [x] Pipe tests
- [x] Conditional tests
- [x] Arithmetic tests
- [x] Literal expression tests

### Compatibility Tests
- [x] Compare ZQ output to jq for all new features
- [x] Document any intentional differences

### Quality Gate
- [x] All new features have tests
- [x] jq compatibility verified

---

## Success Criteria

| Feature | Status |
|---------|--------|
| `{a: .x}` object literals | Complete |
| `{(.key): .value}` dynamic keys | Complete |
| `tonumber`, `tostring`, `type` | Complete |
| `length`, `keys`, `values` | Complete |
| `isnumber`, `isstring`, etc. | Complete |
| `.x // default` alternative | Complete |
| `if-then-else` | Complete |
| `.x \| .y` pipes | Complete |
| Arithmetic operators | Complete |
| Literal expressions | Complete |
| All tests pass | Yes |

---

## Implementation Notes

### Zig Error Handling
The implementation required explicit error types for recursive functions. Zig's inferred error sets don't work well with recursive calls, so we defined:

```zig
const ParseError = error{
    InvalidExpression,
    InvalidConditional,
    InvalidValue,
    OutOfMemory,
};

const EvalError = error{
    OutOfMemory,
};
```

### Expression Evaluation Architecture
The recursive `evalExpr` function handles all expression types and returns an `EvalResult` struct that can contain zero, one, or multiple values (for iteration):

```zig
const EvalResult = struct {
    values: []std.json.Value,
    allocator: std.mem.Allocator,
};
```

This design supports:
- Single value expressions (`.field`)
- Multi-value expressions (`.[]` iteration)
- Piping (left results feed into right expression)

### KeyType Union
Object fields use a separate `KeyType` union to avoid nested anonymous unions:

```zig
const KeyType = union(enum) {
    literal: []const u8,
    dynamic: *Expr,
};
```

---

## Deferred to Sprint 03
- Array slicing (`.[2:5]`)
- Aggregation functions (`add`, `min`, `max`)
- Advanced iteration (`map`, `reduce`)
- Slurp mode (`-s`)
