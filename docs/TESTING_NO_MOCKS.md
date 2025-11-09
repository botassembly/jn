# Plugin Testing - NO MOCKS Approach

**Philosophy:** Test real things, ignore dynamic fields, validate structure with JSON Schema.

---

## Core Principles

### 1. NO MOCKS
- Test REAL HTTP endpoints (httpbin.org)
- Test REAL shell commands (ps, df, ls, etc.)
- Test REAL file operations
- Never mock anything

### 2. Ignore Dynamic Fields
- PIDs, timestamps, IP addresses, UUIDs - all change
- Use `ignore_fields` to skip exact value checks
- Focus on **structure/shape** validation

### 3. JSON Schema Validation
- Define expected structure declaratively
- Automatic type/range/format validation
- Better than hardcoded assertions

### 4. External Test Tool
- `tools/jn-test-plugin` - standalone UV script
- Has jsonschema dependency (main project stays clean)
- No dependencies added to main project (just click)

---

## Architecture

### Test Tool (`tools/jn-test-plugin`)

Standalone UV script with PEP 723 dependencies:

```bash
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "jsonschema>=4.0.0",
# ]
# ///
```

**Usage:**
```bash
# Test a plugin
tools/jn-test-plugin plugins/readers/csv_reader.py --verbose

# Get schema only
tools/jn-test-plugin plugins/readers/csv_reader.py --schema-only
```

**What it does:**
1. Loads plugin module
2. Calls `plugin.schema()` if available
3. Runs `plugin.examples()` test cases
4. Validates against schema
5. Checks shape/structure (ignoring dynamic fields)

---

## Plugin Structure

### Required Functions

```python
def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Main plugin logic."""
    pass

def schema() -> dict:
    """JSON schema for output validation."""
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
    """Test cases with ignore_fields for dynamic values."""
    return [...]
```

---

## Example 1: HTTP Plugin (NO MOCKS)

```python
def examples() -> list[dict]:
    """Real httpbin tests - NO MOCKS!"""
    return [
        {
            "description": "GET UUID endpoint",
            "config": {
                "url": "https://httpbin.org/uuid",
                "timeout": 10
            },
            "expected": [
                {
                    "uuid": ""  # Changes every time!
                }
            ],
            # UUID is dynamic - only validate structure
            "ignore_fields": {"uuid"}
        },
        {
            "description": "GET IP address",
            "config": {
                "url": "https://httpbin.org/ip"
            },
            "expected": [
                {
                    "origin": ""  # Our IP (dynamic)
                }
            ],
            "ignore_fields": {"origin"}
        }
    ]
```

**What gets tested:**
- ✓ Real HTTP request via curl
- ✓ JSON parsing works
- ✓ Output structure matches schema
- ✗ NOT the exact UUID/IP value (dynamic!)

---

## Example 2: Shell Commands (NO MOCKS)

```python
def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Run REAL ps command."""
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    # Parse output...

def schema() -> dict:
    """Schema with type constraints."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "pid": {"type": "integer", "minimum": 1},
            "cpu_percent": {"type": "number", "minimum": 0},
            "mem_percent": {"type": "number", "minimum": 0}
        },
        "required": ["pid"]
    }

def examples() -> list[dict]:
    """For variable output, use empty expected."""
    return [
        {
            "description": "Parse real ps output",
            "config": {},
            "input": "",
            "expected": [],  # Empty = schema-only validation
        }
    ]
```

**When `expected` is empty:**
- Tool runs plugin and validates schema on ALL results
- Doesn't check exact count (commands return variable results)
- Perfect for ps, ls, df, etc.

---

## Example 3: File Readers (Known Input/Output)

```python
def examples() -> list[dict]:
    return [
        {
            "description": "Basic CSV",
            "input": "name,age\nAlice,30\nBob,25\n",
            "expected": [
                {"name": "Alice", "age": "30"},
                {"name": "Bob", "age": "25"}
            ],
            # CSV values are deterministic - check everything
            "ignore_fields": set()
        }
    ]
```

**For deterministic inputs:**
- Don't ignore fields
- Check exact values
- Verify count matches

---

## Benefits

### vs. Mocks

| Aspect | Mocks | NO MOCKS |
|--------|-------|----------|
| **Reality** | Fake | Real |
| **Coverage** | Mock behavior only | Actual HTTP/subprocess/parsing |
| **Maintenance** | Update mocks + code | Just code |
| **Confidence** | Low | High |
| **Flakiness** | Zero | Some (acceptable) |

### vs. Hardcoded Assertions

| Aspect | Hardcoded | Schema |
|--------|-----------|--------|
| **Dynamic values** | Fails | Ignores with ignore_fields |
| **Type checking** | Manual | Automatic |
| **Range validation** | Manual | Declarative |
| **Agent introspection** | None | Schema available |

---

## Test Strategies by Plugin Type

### HTTP Plugins
- Test real endpoints (httpbin.org)
- Ignore: IPs, timestamps, UUIDs, URLs, headers
- Validate: Structure, required fields
- `expected`: Define shape with empty dynamic fields
- `ignore_fields`: All dynamic values

### Shell Commands (Variable Output)
- Run real commands (ps, df, ls, etc.)
- Ignore: ALL fields (PIDs, timestamps, paths, etc.)
- Validate: Schema only
- `expected`: Empty list `[]`
- Schema ensures correct types/ranges

### Shell Commands (Fixed Output)
- Run real commands (env)
- Ignore: Values (environment changes)
- Validate: Structure has name/value pairs
- `expected`: Template record
- `ignore_fields`: Specific dynamic fields

### File Readers
- Real input strings
- No ignoring (deterministic)
- Validate: Exact output
- `expected`: Full expected records
- `ignore_fields`: Empty set

### Writers
- Real NDJSON input
- Check output format/structure
- May need to parse output back
- Validate: Round-trip works

---

## When to Ignore Fields

| Field Type | Strategy | Example |
|------------|----------|---------|
| **Timestamps** | Ignore | `"timestamp": ""` |
| **IDs/PIDs** | Ignore | `"pid": 0` |
| **IP Addresses** | Ignore | `"origin": ""` |
| **UUIDs** | Ignore | `"uuid": ""` |
| **URLs** | Ignore (if dynamic) | `"url": ""` |
| **Static values** | Check exact | `"name": "Alice"` |
| **Computed values** | Ignore or range | `"cpu_percent": 0.0` |

---

## Migration Guide

### Before (Boilerplate + Mocks)

```python
def test() -> bool:
    """70 lines of boilerplate + mocks."""
    from unittest.mock import patch, MagicMock

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            stdout='{"test": "data"}'
        )
        # More boilerplate...
```

### After (NO MOCKS)

```python
# Plugin just needs schema + examples
def schema() -> dict:
    return {"type": "object", ...}

def examples() -> list[dict]:
    return [{
        "description": "Real test",
        "config": {"url": "https://httpbin.org/uuid"},
        "expected": [{"uuid": ""}],
        "ignore_fields": {"uuid"}
    }]

# Test with external tool
# $ tools/jn-test-plugin plugins/http/http_get.py --verbose
```

**Reduct

ion:**
- 70 lines → 0 lines (testing logic external)
- Mocks → Real commands
- Maintenance → Just schema + examples

---

## FAQ

### Q: What if httpbin is down?

**A:** Tests fail. That's OK! We're testing real integration. If tests fail 5% of the time due to network, that's acceptable. We know when they pass, they REALLY work.

### Q: What if dynamic fields change format?

**A:** Update the schema! Schema describes the current format. If httpbin changes `/uuid` format, schema catches it.

### Q: How do I test error cases?

**A:** Add test cases with expected errors. Tool can be extended to handle `expected_error` field.

### Q: Don't we need unit tests for plugin internals?

**A:** No! Plugins are small (50-200 LOC). Schema + integration tests are sufficient. If plugin is complex enough to need unit tests, it's too complex - simplify it.

### Q: What about flaky tests in CI?

**A:** Retry failed tests 2-3 times. If still failing, real issue. Flakiness <5% is acceptable for integration tests.

---

## Summary

**NO MOCKS approach:**
1. External test tool (`tools/jn-test-plugin`) with jsonschema
2. Test real things (HTTP, shell, files)
3. Ignore dynamic fields explicitly
4. Validate structure with JSON Schema
5. Main project stays dependency-free

**Benefits:**
- Higher confidence (testing reality)
- Less code (no test boilerplate per plugin)
- Better for agents (schema introspection)
- Simpler maintenance (no mock updates)

**Trade-offs:**
- Occasional flakiness (acceptable)
- Requires network for HTTP tests (worth it)
- Tests are slower (still fast enough)

**Result:** Simple, real, maintainable tests that actually verify plugins work.
