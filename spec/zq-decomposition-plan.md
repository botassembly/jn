# ZQ Parser Decomposition Plan

> **Status**: Proposed
> **Current**: Single 4316-line `main.zig`
> **Target**: Modular structure with clear separation of concerns

---

## Current Structure Analysis

The current `zq/src/main.zig` contains everything in one file:

| Section | Lines | Responsibility |
|---------|-------|----------------|
| Types | 1-280 | Expression AST, conditions, config |
| Feature Detection | 280-470 | Unsupported jq features detection |
| Expression Parser | 470-830 | `parseExprWithContext`, operators |
| Condition Parser | 830-1060 | Boolean logic, comparisons |
| Value/Path Parser | 1060-1200 | Paths, literal values |
| Sprint 03 Parsers | 1200-1300 | String funcs, by-funcs, arrays |
| Evaluator Core | 1300-1730 | `evalExpr`, dispatch |
| Evaluator Builtins | 1730-2200 | `evalBuiltin`, type functions |
| Evaluator Advanced | 2200-2600 | String funcs, by-funcs, del |
| Output & Main | 2600-3200 | JSON output, CLI, main loop |
| Tests | 3200-4316 | All test cases |

---

## Proposed Module Structure

```
zq/src/
├── main.zig           # CLI entry, main loop, arg parsing (~200 lines)
├── types.zig          # AST types: Expr, Condition, Config (~300 lines)
├── parser/
│   ├── root.zig       # Parser entry point, re-exports
│   ├── expr.zig       # Expression parser (~400 lines)
│   ├── condition.zig  # Condition/boolean parser (~250 lines)
│   ├── value.zig      # Value/path/literal parser (~150 lines)
│   ├── features.zig   # Unsupported feature detection (~200 lines)
│   └── funcs.zig      # Sprint 03 function parsers (~150 lines)
├── eval/
│   ├── root.zig       # Evaluator entry point, re-exports
│   ├── expr.zig       # Main evalExpr dispatch (~300 lines)
│   ├── builtin.zig    # Built-in functions (tonumber, keys, etc.) (~400 lines)
│   ├── string.zig     # String functions (split, join, etc.) (~200 lines)
│   ├── array.zig      # Array/by functions (map, sort_by, etc.) (~300 lines)
│   └── object.zig     # Object operations (del, construction) (~200 lines)
├── output.zig         # JSON output formatting (~200 lines)
└── tests/
    ├── parser_test.zig
    ├── eval_test.zig
    └── integration_test.zig
```

---

## Module Descriptions

### 1. `main.zig` (~200 lines)
- CLI argument parsing
- Main processing loop (read stdin, parse, eval, output)
- Config handling (--compact, --raw, --slurp, etc.)
- Error reporting

### 2. `types.zig` (~300 lines)
- All AST types: `Expr`, `Condition`, `CompareOp`, etc.
- `Config` struct
- `EvalResult` type
- Error types: `ParseError`, `EvalError`
- No dependencies on other ZQ modules

### 3. `parser/root.zig`
```zig
pub const expr = @import("expr.zig");
pub const condition = @import("condition.zig");
pub const value = @import("value.zig");
pub const features = @import("features.zig");

pub const parseExpr = expr.parse;
pub const parseCondition = condition.parse;
pub const ErrorContext = expr.ErrorContext;
```

### 4. `parser/expr.zig` (~400 lines)
Main expression parser handling:
- Pipe operator (`|`)
- Alternative operator (`//`)
- Arithmetic operators
- Field access, iteration
- Object/array construction
- Conditional expressions
- Builtin function names
- `del()`, `select()`, `map()`

**Key function**: `parseExprWithContext(allocator, expr, err_ctx) !Expr`

### 5. `parser/condition.zig` (~250 lines)
Boolean condition parsing:
- `parseCondition` - compound conditions
- `parseSimpleCondition` - comparisons
- Boolean operators: `and`, `or`, `not`
- Parenthesized grouping

### 6. `parser/value.zig` (~150 lines)
- `parsePath` - dot-separated field paths
- `parseValue` - literal values (strings, numbers, booleans, null)
- Index expressions (single, slice, iterate)

### 7. `parser/features.zig` (~200 lines)
- `checkUnsupportedFeatures` - detect jq features not supported
- Error context generation for helpful messages
- Pattern matching for variables, reduce, modules, etc.

### 8. `parser/funcs.zig` (~150 lines)
Sprint 03 function parsers:
- `parseStrFunc` - split, join, startswith, etc.
- `parseByFunc` - group_by, sort_by, unique_by, etc.
- `parseArrayLiteral` - `[.x, .y, .z]`

### 9. `eval/root.zig`
```zig
pub const expr = @import("expr.zig");
pub const builtin = @import("builtin.zig");
pub const string = @import("string.zig");
pub const array = @import("array.zig");
pub const object = @import("object.zig");

pub const evalExpr = expr.eval;
pub const EvalResult = @import("../types.zig").EvalResult;
```

### 10. `eval/expr.zig` (~300 lines)
Main evaluator dispatch:
- `evalExpr` - switch on Expr type
- `evalCondition` - boolean evaluation
- `getPath`, `getIndex`, `getSlice` helpers
- Delegates to specialized modules

### 11. `eval/builtin.zig` (~400 lines)
Built-in function evaluation:
- Type functions: `tonumber`, `tostring`, `type`
- Type checks: `isnumber`, `isstring`, etc.
- Collection: `length`, `keys`, `values`
- Array: `first`, `last`, `reverse`, `sort`, `unique`, `flatten`
- Aggregation: `add`, `min`, `max`
- Math: `floor`, `ceil`, `round`, `fabs`
- Object: `to_entries`, `from_entries`

### 12. `eval/string.zig` (~200 lines)
String function evaluation:
- `evalStrFunc` dispatcher
- `split`, `join`
- `startswith`, `endswith`, `contains`
- `ltrimstr`, `rtrimstr`
- `has`, `test`
- `ascii_downcase`, `ascii_upcase`

### 13. `eval/array.zig` (~300 lines)
Array operations:
- `evalMap` - map(expr)
- `evalByFunc` - group_by, sort_by, unique_by, min_by, max_by
- `evalArrayLiteral` - [.x, .y]
- Sorting comparator helpers

### 14. `eval/object.zig` (~200 lines)
Object operations:
- `evalObject` - object construction `{a: .x}`
- `evalDel` - del(.key)
- `evalArithmetic` - +, -, *, /, %

### 15. `output.zig` (~200 lines)
- `outputValue` - format JSON for output
- Compact vs pretty printing
- Raw string mode
- Null handling

---

## Implementation Phases

### Phase 1: Extract Types (Low Risk)
1. Create `types.zig` with all type definitions
2. Update `main.zig` to import from `types.zig`
3. Run tests to verify no regressions

### Phase 2: Extract Output (Low Risk)
1. Create `output.zig` with output formatting
2. Keep main loop in `main.zig`
3. Run tests

### Phase 3: Extract Parser (Medium Risk)
1. Create `parser/` directory structure
2. Move parser functions one at a time:
   - Start with `value.zig` (least dependencies)
   - Then `features.zig`
   - Then `funcs.zig`
   - Then `condition.zig`
   - Finally `expr.zig`
3. Run tests after each move

### Phase 4: Extract Evaluator (Medium Risk)
1. Create `eval/` directory structure
2. Move evaluator functions one at a time:
   - Start with `string.zig` (isolated)
   - Then `builtin.zig`
   - Then `array.zig`
   - Then `object.zig`
   - Finally `expr.zig`
3. Run tests after each move

### Phase 5: Reorganize Tests
1. Move tests to separate files
2. Group by functionality
3. Add integration tests

---

## Benefits

1. **Maintainability**: Each module has single responsibility
2. **Testability**: Modules can be tested in isolation
3. **Discoverability**: Clear file names indicate purpose
4. **Compilation**: Incremental compilation for faster builds
5. **Extensibility**: New functions can be added to specific modules
6. **Code Review**: Smaller files are easier to review

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Circular dependencies | Types module has no deps; others import only types or lower-level modules |
| Test breakage | Run full test suite after each extraction |
| Performance regression | Profile before/after; all changes are structural |
| Import complexity | Use `root.zig` pattern to provide clean public API |

---

## Estimated Effort

| Phase | Estimated Time | Risk Level |
|-------|----------------|------------|
| Phase 1: Types | 1-2 hours | Low |
| Phase 2: Output | 1 hour | Low |
| Phase 3: Parser | 4-6 hours | Medium |
| Phase 4: Evaluator | 4-6 hours | Medium |
| Phase 5: Tests | 2-3 hours | Low |
| **Total** | **12-18 hours** | |

---

## Acceptance Criteria

1. All existing tests pass
2. No performance regression (benchmark before/after)
3. Each module compiles independently
4. No circular dependencies
5. Clear public API via root.zig files
6. Each file < 500 lines (except tests)
