# Testing Strategy

> **Purpose**: How to test JN with an outside-in approach that validates actual behavior.

---

## Testing Philosophy

### Outside-In Testing

Tests should verify **behavior**, not implementation details:

```bash
# GOOD: Test actual CLI behavior
echo '{"x":1}' | jn filter '.x > 0'  # Should output {"x":1}

# BAD: Test internal function with mocked dependencies
mock_stdin = Mock()
filter_internal(mock_stdin, ".x > 0")  # Tautological
```

**Principle**: If you can't describe what the test verifies to a user, it's probably testing implementation, not behavior.

### Avoid Tautological Tests

Don't test that code does what it obviously does:

```python
# BAD: Tautological
def test_config_has_value():
    config = Config(value=5)
    assert config.value == 5  # Of course it does!

# GOOD: Test meaningful behavior
def test_filter_excludes_non_matching():
    input = '{"x":1}\n{"x":5}\n{"x":3}'
    result = run_jn("filter", ".x > 2", input=input)
    assert result == '{"x":5}\n{"x":3}\n'
```

### Real Data, No Mocks

Tests should use actual files and subprocess execution:

```python
# GOOD: Real subprocess, real data
def test_csv_to_json(tmp_path):
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("name,age\nAlice,30\n")

    result = subprocess.run(
        ["jn", "cat", str(csv_file)],
        capture_output=True, text=True
    )

    assert '{"name":"Alice","age":"30"}' in result.stdout
```

---

## Test Categories

### 1. CLI Integration Tests

Test the actual `jn` commands via subprocess:

```
tests/cli/
├── test_cat.py           # jn cat behavior
├── test_put.py           # jn put behavior
├── test_filter.py        # jn filter with ZQ
├── test_head.py          # jn head early termination
├── test_tail.py          # jn tail buffering
├── test_join.py          # jn join hash join
├── test_table.py         # jn table formatting
├── test_analyze.py       # jn analyze statistics
└── test_inspect.py       # jn inspect discovery
```

**Pattern**:
```python
def test_cat_csv_outputs_ndjson(tmp_path):
    # Setup: Create real file
    csv = tmp_path / "data.csv"
    csv.write_text("a,b\n1,2\n3,4\n")

    # Act: Run actual CLI
    result = subprocess.run(
        ["jn", "cat", str(csv)],
        capture_output=True, text=True
    )

    # Assert: Verify behavior
    assert result.returncode == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"a": "1", "b": "2"}
```

### 2. Plugin Tests

Test plugins in isolation:

```
tests/plugins/
├── test_csv_plugin.py    # CSV format plugin
├── test_json_plugin.py   # JSON format plugin
├── test_gz_plugin.py     # Gzip compression
├── test_http_plugin.py   # HTTP protocol
└── test_xlsx_plugin.py   # Excel (Python plugin)
```

**Pattern** (Zig plugins):
```python
def test_csv_plugin_read(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("x,y\n1,2\n")

    result = subprocess.run(
        ["plugins/zig/csv/bin/csv", "--mode=read"],
        stdin=open(csv), capture_output=True, text=True
    )

    assert '{"x":"1","y":"2"}' in result.stdout
```

**Pattern** (Python plugins):
```python
def test_xlsx_plugin_read(tmp_path):
    # Python plugins use uv run
    result = subprocess.run(
        ["uv", "run", "--script", "plugins/python/xlsx_.py", "--mode=read"],
        stdin=open("test.xlsx", "rb"), capture_output=True
    )
    assert result.returncode == 0
```

### 3. Pipeline Tests

Test multi-stage pipelines:

```
tests/pipelines/
├── test_backpressure.py     # Early termination
├── test_multi_stage.py      # Protocol → decompress → format
├── test_error_propagation.py # Error handling across stages
└── test_memory.py           # Memory stays constant
```

**Pattern**:
```python
def test_head_triggers_early_termination():
    """Verify that head -n 10 stops upstream processing."""
    start = time.time()

    # 1GB file, but only 10 records requested
    result = subprocess.run(
        ["jn", "cat", "huge.csv", "|", "jn", "head", "-n", "10"],
        shell=True, capture_output=True, text=True, timeout=5
    )

    elapsed = time.time() - start
    assert elapsed < 1.0  # Should be fast, not read whole file
    assert result.returncode == 0
```

### 4. Profile Tests

Test profile resolution and usage:

```
tests/profiles/
├── test_http_profiles.py    # HTTP profile loading
├── test_zq_profiles.py      # ZQ filter profiles
├── test_env_substitution.py # ${VAR} replacement
└── test_hierarchy.py        # _meta.json merging
```

---

## Python Plugin Testing

Python plugins (xlsx, gmail, mcp, duckdb, watch) require special handling.

### Watch Files Plugin

The `watch_shell.py` plugin is timing-sensitive and can be flaky:

```python
@pytest.mark.flaky(reruns=2)
def test_watch_emits_on_change(tmp_path):
    """Watch should emit event when file created."""
    proc = subprocess.Popen(
        ["jn", "sh", "watch", str(tmp_path), "--exit-after", "1"],
        stdout=subprocess.PIPE, text=True
    )

    time.sleep(2)  # Wait for watcher initialization
    (tmp_path / "new.txt").write_text("x")

    out, _ = proc.communicate(timeout=15)
    assert "created" in out or "modified" in out
```

**Mitigation strategies**:
- Use `--exit-after N` to bound execution
- Allow reruns for timing-sensitive tests
- Skip on CI if too flaky

### Reference

See [10-python-plugins.md](10-python-plugins.md) for Python plugin details.

---

## Zig Testing

### Unit Tests

Zig has built-in test support:

```bash
# Run ZQ unit tests
cd zq && zig test src/main.zig

# Run plugin unit tests
cd plugins/zig/csv && zig test main.zig
```

**Pattern**:
```zig
test "csv parser handles quoted fields" {
    const input = "\"hello, world\",123";
    var parser = CsvParser.init(input);
    const fields = parser.parseLine();
    try std.testing.expectEqualStrings("hello, world", fields[0]);
}
```

### Integration Tests

```bash
# ZQ integration tests
cd zq && zig test tests/integration.zig
```

---

## Test Data

### Standard Test Files

```
tests/data/
├── people.csv          # 5 records, basic CSV
├── products.json       # JSON array
├── config.yaml         # YAML with nesting
├── report.xlsx         # Excel spreadsheet
└── compressed.csv.gz   # Gzipped CSV
```

### Generated Test Data

For large file tests:
```python
def create_large_csv(path, rows=1_000_000):
    with open(path, "w") as f:
        f.write("id,value\n")
        for i in range(rows):
            f.write(f"{i},{i*2}\n")
```

---

## Test Markers

### Skip Markers

```python
@pytest.mark.skip(reason="Requires network")
def test_github_api():
    ...

@pytest.mark.skipif(not shutil.which("jc"), reason="jc not installed")
def test_shell_commands():
    ...
```

### Slow Tests

```python
@pytest.mark.slow
def test_large_file_processing():
    ...
```

Run without slow tests:
```bash
pytest -m "not slow"
```

### Flaky Tests

```python
@pytest.mark.flaky(reruns=2)
def test_timing_sensitive():
    ...
```

---

## Running Tests

### Quick Tests

```bash
# Fast feedback
pytest -q

# Specific file
pytest tests/cli/test_cat.py -v
```

### Full Suite

```bash
# All tests
make test

# With coverage
make coverage
```

### Zig Tests

```bash
# ZQ tests
make zq-test

# Plugin tests
make zig-plugins-test
```

---

## CI/CD Integration

### GitHub Actions

```yaml
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Install Zig
      run: make install-zig
    - name: Install Python deps
      run: uv sync --all-extras
    - name: Build Zig components
      run: make zq zig-plugins
    - name: Run Python tests
      run: make test
    - name: Run Zig tests
      run: make zq-test zig-plugins-test
```

### Test Matrix

| Test Type | Python Tests | Zig Tests |
|-----------|--------------|-----------|
| CLI integration | pytest | - |
| Plugin behavior | pytest (subprocess) | zig test |
| Pipeline | pytest | - |
| Unit | - | zig test |

---

## Anti-Patterns to Avoid

### 1. Mocking the System Under Test

```python
# BAD: Mocking defeats the purpose
@patch("jn.cli.cat")
def test_cat(mock_cat):
    mock_cat.return_value = "..."
    # This tests nothing useful
```

### 2. Testing Private Functions

```python
# BAD: Testing implementation details
def test_internal_parser():
    from jn.core._internal import _parse_line
    # If _internal changes, test breaks but behavior is fine
```

### 3. Excessive Edge Cases

```python
# BAD: Testing every possible input
def test_csv_with_emoji_in_header():
def test_csv_with_null_bytes():
def test_csv_with_bom():
# ... 50 more edge cases
```

**Better**: Test representative cases that cover actual user scenarios.

---

## See Also

- [11-demo-migration.md](11-demo-migration.md) - Demos as integration tests
- [13-code-quality.md](13-code-quality.md) - Coverage requirements
- [10-python-plugins.md](10-python-plugins.md) - Python plugin testing
