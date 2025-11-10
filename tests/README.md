# JN v5 Tests

Simple, focused tests for JN's core functionality.

## Test Structure

```
tests/
├── data/                # Test data files
│   └── people.csv      # Sample CSV with 5 records
├── test_plugins.py     # Plugin isolation tests
├── test_filter.py      # jq filter tests
└── test_cli.py         # End-to-end CLI tests
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_cli.py -v

# Run single test
uv run pytest tests/test_cli.py::test_cat_csv_to_json -v
```

## Test Coverage

### Plugin Tests (`test_plugins.py`)
Tests each format plugin in isolation using subprocess:
- CSV read/write
- JSON read/write (array and NDJSON)
- YAML read/write (multi-document)
- CSV roundtrip (read → write → verify)

### Filter Tests (`test_filter.py`)
Tests jq filter plugin:
- Field selection (`.name`)
- Conditional filtering (`select(.age > 25)`)
- Object transformation (`{user: .name}`)

### CLI Tests (`test_cli.py`)
Tests full pipeline using `uv run jn` commands:
- `jn cat file.csv` → NDJSON to stdout
- `jn cat file.csv file.json` → CSV to JSON conversion
- `jn cat file.csv file.yaml` → CSV to multi-doc YAML
- `jn cat | jn filter | jn put` → Full pipeline with filtering
- `jn head N` / `jn tail N` → Stream utilities
- `jn run input output` → Shorthand command

## Design Principles

All tests follow JN's core principles:

1. **Real data, no mocks** - Tests use actual files and subprocess execution
2. **Outside-in testing** - CLI tests run the actual `jn` command
3. **Streaming verification** - Tests confirm NDJSON flows correctly
4. **Simple assertions** - Focus on correctness, not exhaustive edge cases

## Backpressure Compliance

The CLI implementation follows Unix backpressure principles from `spec/arch/backpressure.md`:

✅ **Uses Popen** - `subprocess.Popen()` for all plugin execution
✅ **Closes stdout in parent** - `reader.stdout.close()` enables SIGPIPE
✅ **Waits for processes** - `process.wait()` before checking results
✅ **Checks stderr** - Error messages captured and reported
✅ **Streams incrementally** - No buffering entire files in memory

See `src/jn/cli.py:99-134` for reference implementation.

## Test Data

`data/people.csv`:
- 5 records (Alice, Bob, Carol, David, Eve)
- 4 fields (name, age, city, salary)
- Used for all conversion and filtering tests
