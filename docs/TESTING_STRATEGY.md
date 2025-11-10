# JN Plugin Testing Strategy

**Version:** 4.0.0-alpha1+
**Status:** Proposed Improvement

---

## Problem Statement

Current plugin tests have significant issues:
- **Boilerplate heavy** - Each plugin reimplements test logic
- **Low value** - Many tests are no-ops or "goofy" (just check structure)
- **No reuse** - Copy-paste between plugins
- **Poor for agents** - No schema for introspection
- **Missing integration tests** - HTTP plugin has no real tests

## Proposed Solution

### Three-Part Testing Architecture

1. **JSON Schema** - Declarative output validation
2. **Reusable Framework** - `src/jn/testing.py` handles all test logic
3. **Smart Field Matching** - Exact for static, semantic for dynamic

---

## Architecture

### 1. Plugin Structure (New)

Every plugin should have these functions:

```python
def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Main plugin logic - unchanged."""
    pass

def schema() -> dict:
    """NEW: Return JSON schema for output.

    Enables:
    - Automatic validation
    - Agent introspection
    - Type checking
    """
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer", "minimum": 0}
        },
        "required": ["name"]
    }

def examples() -> list[dict]:
    """Return test cases with smart field checking.

    New format includes:
    - checks.exact: Fields that must match exactly
    - checks.types: Fields that must match type only
    - checks.patterns: Fields that must match regex
    - checks.ranges: Numeric fields with min/max
    """
    return [
        {
            "description": "Test case description",
            "input": "test input data",
            "config": {},  # Optional plugin config
            "expected": [
                {"name": "Alice", "age": 30}
            ],
            "checks": {
                "exact": ["name", "age"],  # Must match exactly
                "types": [],               # Must match type only
                "patterns": {},            # Field: regex pattern
                "ranges": {}               # Field: {min, max}
            }
        }
    ]

def test() -> bool:
    """Run tests using reusable framework."""
    from jn.testing import run_plugin_tests

    return run_plugin_tests(
        run_func=run,
        examples_func=examples,
        schema_func=schema,
        verbose=True
    )
```

### 2. Testing Framework (`src/jn/testing.py`)

Central reusable test logic:

```python
def run_plugin_tests(
    run_func: Callable,
    examples_func: Callable,
    schema_func: Optional[Callable] = None,
    verbose: bool = False
) -> bool:
    """Run all plugin tests with smart validation."""

    # For each test case:
    # 1. Run plugin with input
    # 2. Validate against schema (if provided)
    # 3. Check exact fields
    # 4. Check type-only fields
    # 5. Check pattern fields
    # 6. Check range fields

    return all_passed
```

**Benefits:**
- Zero boilerplate per plugin
- Consistent test behavior
- Easy to improve (one place)
- Well-tested framework code

### 3. Smart Field Matching

Different validation strategies for different field types:

| Check Type | Use Case | Example |
|------------|----------|---------|
| **exact** | Static values | `name`, `constant_field` |
| **types** | Dynamic values, check type only | `timestamp`, `id` |
| **patterns** | Format validation | `email`, `ip_address`, `uuid` |
| **ranges** | Numeric bounds | `age: {min: 0, max: 150}` |

**Example:**

```python
"checks": {
    # These must match exactly
    "exact": ["name"],

    # These must be correct type only
    "types": ["timestamp", "id"],

    # These must match regex
    "patterns": {
        "email": r"^[^@]+@[^@]+\.[^@]+$",
        "ip_address": r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
    },

    # These must be in range
    "ranges": {
        "age": {"min": 0, "max": 150},
        "score": {"min": 0.0, "max": 1.0}
    }
}
```

---

## Agent Introspection

Agents can understand plugins without running them:

```bash
# Get plugin schema
jn show csv_reader --schema

# Returns:
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "patternProperties": {
    ".*": {"type": "string"}
  },
  "description": "CSV row as key-value pairs"
}

# Get examples
jn show csv_reader --examples

# Returns test cases with input/output examples
```

**Agent workflow:**
1. Discover plugins: `jn discover --type source`
2. Get capabilities: `jn show <plugin> --schema`
3. See usage: `jn show <plugin> --examples`
4. Use plugin: `jn cat data.csv`

---

## Integration Tests

### Real HTTP Tests (httpbin.org)

```python
def examples() -> list[dict]:
    """Real integration tests."""
    return [
        {
            "description": "GET JSON from httpbin",
            "config": {
                "url": "https://httpbin.org/json",
                "timeout": 10
            },
            "expected": [{"slideshow": {}}],
            "checks": {
                # httpbin response varies, check structure only
                "types": ["slideshow"]
            }
        },
        {
            "description": "GET with headers",
            "config": {
                "url": "https://httpbin.org/headers",
                "headers": {"X-Test": "value"}
            },
            "expected": [{"headers": {}}],
            "checks": {
                "types": ["headers"]
            }
        },
        {
            "description": "UUID endpoint (dynamic)",
            "config": {
                "url": "https://httpbin.org/uuid"
            },
            "expected": [{"uuid": ""}],
            "checks": {
                # UUID changes each time, check pattern
                "patterns": {
                    "uuid": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
                }
            }
        }
    ]
```

**Handling flakiness:**
- Network tests may fail ~5% of the time (that's OK!)
- Test considers success if ≥80% pass
- Skip tests on timeout/connection errors
- Report success rate

```python
def test_basic() -> bool:
    """Allow some network failures."""
    passed, failed, skipped = run_tests()

    success_rate = passed / (passed + failed) if (passed + failed) > 0 else 0

    print(f"Success rate: {100 * success_rate:.1f}%")

    # 80% success is acceptable for integration tests
    return success_rate >= 0.8
```

---

## Migration Path

### Phase 1: Framework + Examples (Current)

1. ✅ Create `src/jn/testing.py` framework
2. ✅ Create example plugins:
   - `csv_reader_v2_example.py` - Schema + smart checks
   - `http_get_v2_example.py` - Real httpbin tests
3. ✅ Document new approach

### Phase 2: Template Updates

1. Update plugin templates:
   - Add `schema()` function
   - Update `examples()` format
   - Use `run_plugin_tests()` in `test()`

2. Add `--schema` flag to CLI:
   - `jn show <plugin> --schema`
   - Agents can introspect

### Phase 3: Plugin Migration

Migrate existing plugins one by one:

**Priority order:**
1. HTTP plugins (needs real tests)
2. File format readers (CSV, JSON, YAML, XML, TOML)
3. Shell plugins (harder to test, can use mocks)
4. Writers
5. Filters

**Migration per plugin:**
1. Add `schema()` function
2. Update `examples()` with checks
3. Replace `test()` with `run_plugin_tests()`
4. Add integration tests if applicable
5. Remove boilerplate

### Phase 4: Validation

1. Add CLI command: `jn validate <plugin> --strict`
   - Check `schema()` exists
   - Validate examples against schema
   - Ensure test coverage

2. CI integration:
   - Run `jn test <plugin>` for all plugins
   - Require ≥80% test success rate
   - Track coverage

---

## Benefits

### For Developers
- **Less code** - No boilerplate per plugin
- **Better tests** - Schema + smart checks catch more bugs
- **Faster iteration** - Framework handles edge cases
- **Consistent** - All plugins tested the same way

### For Agents
- **Introspection** - Schema describes capabilities
- **Examples** - See usage without execution
- **Validation** - Know output structure upfront
- **Composition** - Chain plugins with confidence

### For Users
- **Reliability** - Real integration tests
- **Debugging** - Better error messages from schema validation
- **Documentation** - Examples show real usage
- **Confidence** - High test coverage

---

## Examples

### Before (Boilerplate Hell)

```python
def test() -> bool:
    """73 lines of boilerplate per plugin."""
    from io import StringIO

    passed = 0
    failed = 0

    for test_case in examples():
        desc = test_case['description']
        test_input = test_case['input']
        expected = test_case.get('expected_pattern', '')

        old_stdin = sys.stdin
        old_stdout = sys.stdout
        sys.stdin = StringIO(test_input)
        sys.stdout = StringIO()

        try:
            config = test_case.get('config', {})
            run(config)
            output = sys.stdout.getvalue()

            if expected_pattern in output:
                print(f"✓ Test {i}: {desc}", file=sys.stderr)
                passed += 1
            else:
                print(f"✗ Test {i}: {desc}", file=sys.stderr)
                failed += 1

        except Exception as e:
            print(f"✗ Test {i}: {desc} - {e}", file=sys.stderr)
            failed += 1
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout

    print(f"\n{passed} passed, {failed} failed", file=sys.stderr)
    return failed == 0
```

### After (Clean)

```python
def test() -> bool:
    """3 lines - framework does the work."""
    from jn.testing import run_plugin_tests

    return run_plugin_tests(run, examples, schema, verbose=True)
```

**Reduction: 73 → 3 lines (96% less code!)**

---

## Next Steps

1. **Review this proposal** - Get feedback
2. **Test framework** - Ensure `src/jn/testing.py` works
3. **Update templates** - New plugins use this pattern
4. **Migrate HTTP** - Fix the "no tests" problem
5. **Migrate readers** - CSV, JSON, YAML, XML, TOML
6. **Document** - Update plugin development guide

---

## Questions for Discussion

1. **JSON Schema dependency** - Should we require `jsonschema` package or use basic validation?
2. **Integration test flakiness** - Is 80% success rate acceptable?
3. **Migration timeline** - All at once or gradual?
4. **Breaking changes** - Should we version the plugin interface?

---

## References

- **JSON Schema** - https://json-schema.org/
- **httpbin.org** - https://httpbin.org/ (HTTP testing service)
- **Example plugins:**
  - `plugins/readers/csv_reader_v2_example.py`
  - `plugins/http/http_get_v2_example.py`
- **Framework:** `src/jn/testing.py`
