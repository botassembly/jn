# Sprint 02: ZQ Extended Features

**Goal:** Add object construction, type functions, and control flow to ZQ

**Prerequisite:** Sprint 01 complete

---

## Deliverables

1. Object construction expressions
2. Type conversion functions
3. Alternative operator (//)
4. Pipe support (|)

---

## Phase 1: Object Construction

### Basic Object Literals
- [ ] `{a: .x, b: .y}` - object with field access
- [ ] `{name: .user.name, id: .uuid}` - nested paths
- [ ] `{a: 1, b: "str"}` - literal values
- [ ] `{a, b}` - shorthand for `{a: .a, b: .b}`

### Dynamic Keys
- [ ] `{(.key): .value}` - computed key from field
- [ ] `{(.type): .data}` - dynamic object creation

### Quality Gate
- [ ] `echo '{"x":1,"y":2}' | zq '{a:.x,b:.y}'` → `{"a":1,"b":2}`
- [ ] All object tests pass

---

## Phase 2: Type Functions

### Conversion
- [ ] `tonumber` - string → number
- [ ] `tostring` - any → string
- [ ] `type` - returns type name

### Type Checking
- [ ] `isnumber` - true if number
- [ ] `isstring` - true if string
- [ ] `isboolean` - true if boolean
- [ ] `isnull` - true if null
- [ ] `isarray` - true if array
- [ ] `isobject` - true if object

### Quality Gate
- [ ] `echo '{"x":"42"}' | zq '.x | tonumber'` → `42`
- [ ] Type functions work in select conditions

---

## Phase 3: Control Flow

### Alternative Operator
- [ ] `.x // .y` - first non-null
- [ ] `.x // "default"` - default value
- [ ] `.x // .y // .z` - chain

### Conditional
- [ ] `if .x then .a else .b end` - basic conditional
- [ ] `if .x > 0 then "positive" else "negative" end`
- [ ] Nested conditionals

### Quality Gate
- [ ] `echo '{"x":null,"y":1}' | zq '.x // .y'` → `1`
- [ ] Conditionals work with all comparison operators

---

## Phase 4: Pipe Support

### Basic Pipes
- [ ] `.x | tonumber` - chain operations
- [ ] `select(.active) | .name` - filter then extract
- [ ] `.[] | .name` - iterate then extract

### Multi-stage Pipes
- [ ] `.data | .[] | select(.x > 0) | {id: .id}`
- [ ] Proper short-circuit evaluation

### Quality Gate
- [ ] All piped expressions work
- [ ] Performance within 20% of non-piped equivalents

---

## Phase 5: Additional Operators

### Arithmetic (in expressions)
- [ ] `.x + .y` - addition
- [ ] `.x - .y` - subtraction
- [ ] `.x * .y` - multiplication
- [ ] `.x / .y` - division
- [ ] `.x % .y` - modulo

### String Operations
- [ ] `.x + .y` - string concatenation
- [ ] `length` - string/array length

### Quality Gate
- [ ] `echo '{"x":1,"y":2}' | zq '.x + .y'` → `3`
- [ ] String concat works

---

## Phase 6: Testing

### New Tests
- [ ] Object construction tests
- [ ] Type function tests
- [ ] Pipe tests
- [ ] Conditional tests
- [ ] Arithmetic tests

### Compatibility Tests
- [ ] Compare ZQ output to jq for all new features
- [ ] Document any intentional differences

### Quality Gate
- [ ] All new features have tests
- [ ] jq compatibility verified

---

## Success Criteria

| Feature | Status |
|---------|--------|
| `{a: .x}` object literals | Working |
| `{(.key): .value}` dynamic keys | Working |
| `tonumber`, `tostring`, `type` | Working |
| `.x // default` alternative | Working |
| `if-then-else` | Working |
| `.x \| .y` pipes | Working |
| All tests pass | Yes |

---

## Notes

**Deferred to Sprint 03:**
- Array operations (.[], map)
- Aggregation (group_by, sort_by)
- Slurp mode (-s)
