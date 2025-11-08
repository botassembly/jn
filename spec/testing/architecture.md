# JN Testing Architecture

## Philosophy

All tests in JN follow an **outside-in, CLI-first** approach. We test what users actually do, not internal implementation details. Tests should be good partners to each other, reusing configurations where possible without breaking other tests.

## Core Principles

### 1. Outside-In Testing

Tests invoke the CLI through the Typer CliRunner, exactly as users would interact with the tool. We test the entire stack from CLI command through to file output.

**Good**: runner.invoke(app, ["run", "pipeline_name", "--jn", str(config_file)])

**Bad**: Calling internal functions directly (pipeline.run(), adapter.convert(), etc.)

### 2. Pure Functions, No Classes

All test functions are pure functions with descriptive names. No test classes unless absolutely necessary for fixture scoping.

**Good**: def test_csv_to_yaml_conversion(runner, test_config)

**Bad**: class TestFormatAdapters with methods

### 3. Fixture-Based Configuration

Tests use PyTest fixtures that set up comprehensive, reusable configurations. The fixture creates actual jn.json files in tmp_path, mimicking real user setups.

**Primary Pattern**: Comprehensive JSON config fixture (tests/fixtures/test_config.json)
- Single source of truth for test configurations
- Contains multiple sources, targets, converters, and pipelines
- Tests select which pipeline to run from this config
- Easy to extend: just add new pipelines to the JSON

**Secondary Pattern**: Helper functions (tests/helpers.py)
- For tests that need dynamic config generation
- Use init_config, add_exec_source, add_converter, etc.
- Still uses CLI commands under the hood

### 4. Good Test Citizenship

Tests must be good partners:
- Reuse sources and targets from shared config when possible
- Don't modify shared fixtures in ways that break other tests
- Use isolated tmp_path for all file I/O
- Clean up is automatic via tmp_path fixture

### 5. No Tautological Unit Tests

Avoid tests that simply verify "the code does what the code says it does" without adding value.

**Acceptable Unit Tests**:
- Edge case handling (empty input, malformed data, encoding issues)
- Complex logic with multiple branches
- Error conditions and validation
- Security-critical code paths

**Avoid**:
- Tests that just call a function and assert it returns what it returns
- Tests that duplicate type checking Pydantic already does
- Tests that verify dict keys exist when the schema enforces it

## Test File Organization

### Integration Tests (tests/integration/)

Primary test suite. Tests complete workflows through the CLI.

**Current Exemplar**: test_format_adapters.py
- Uses format_test_config fixture from conftest.py
- Each test runs a named pipeline from tests/fixtures/test_config.json
- Pure functions, no classes
- Minimal boilerplate

**Patterns in Use**:

1. **Fixture-based** (PREFERRED): test_format_adapters.py
   - Uses comprehensive JSON config
   - Tests select pipelines by name
   - ~10 lines per test

2. **Helper-based** (ACCEPTABLE): test_run_pipeline.py, test_explain.py
   - Uses CLI helper functions
   - init_config, add_exec_source, add_pipeline, etc.
   - More verbose but flexible

3. **Direct CLI** (GOOD): test_new_source.py, test_init.py
   - Invokes jn init, jn new source, etc. directly
   - Tests CLI command behavior
   - Good for testing CLI commands themselves

4. **Class-based** (LEGACY): test_cat_commands.py
   - Uses TestCatCommand class
   - Should be refactored to pure functions

### Unit Tests (tests/unit/)

Rare. Only for edge cases and internal utilities that warrant isolated testing.

**Current Use**: test_curl_driver.py
- Mocks subprocess.run to test argv construction
- Validates edge cases without network calls
- Acceptable because it tests complex argv building logic

## Fixture Architecture

### conftest.py

Central fixture definitions shared across all tests.

**Key Fixtures**:

- runner: CliRunner instance for all tests
- tmp_config: Creates tmp_path with data/ and out/ directories
- format_test_config: Sets up comprehensive test config with all format conversion pipelines
- echo_source, numbers_source, etc.: Reusable source definitions
- pass_converter, double_converter: Reusable converter definitions

### tests/fixtures/

**test_config.json**: Comprehensive configuration containing:
- Multiple exec-based sources (two_records, people_records, empty, etc.)
- File-based sources (csv_file, yaml_file, etc.)
- All format conversion targets (json_array, yaml_output, csv_output, etc.)
- Named pipelines for every test scenario
- Serves as both test data AND documentation

## Test Data Strategy

### File-Based Test Data

Located in tmp_path created per-test. The format_test_config fixture creates:

- tmp_path/data/input.csv (created in fixture)
- tmp_path/out/ (for all output files)
- tmp_path/jn.json (config file)

### Inline Test Data

For simple tests, generate data inline with exec sources:

python -c "import json; print(json.dumps({'x': 1}))"

This is fine for simple cases. For complex data, use file fixtures.

## Adding New Tests

### For Format Conversion Tests

1. Add a new pipeline to tests/fixtures/test_config.json
2. Create test function in test_format_adapters.py
3. Run pipeline by name, verify output

Example (no code block, just description):
Function test_new_format takes runner and format_test_config, invokes app with run command specifying the new pipeline name, asserts exit code is 0, reads output file from format_test_config.parent / out / filename, makes assertions on content.

### For CLI Command Tests

Test the command directly by invoking it:

Function test_new_command takes runner and tmp_path, invokes app with the command and arguments, asserts exit code and output contain expected strings, optionally reads generated files to verify.

### For Complex Workflows

Use helper functions if config needs to be dynamically built:

Function test_complex_workflow takes runner and tmp_path, calls init_config, calls add_exec_source with name and argv, calls add_converter, calls add_pipeline with steps list, invokes app with run command, verifies results.

## Migration Path for Existing Tests

### Priority 1: Eliminate Classes

test_cat_commands.py uses TestCatCommand class. Refactor to pure functions.

### Priority 2: Consider Fixture Consolidation

Several tests use helpers to build configs programmatically. Evaluate if they could use a shared fixture instead:
- test_run_pipeline.py
- test_explain.py
- test_shell_driver.py

### Priority 3: Keep Good Tests

These are already well-structured, leave as-is:
- test_new_source.py
- test_new_target.py
- test_new_pipeline.py
- test_new_converter.py
- test_init.py

### Priority 4: Evaluate Unit Tests

Review tests/unit/ for tautological tests. Keep edge case tests, remove redundant ones.

## Test Execution

Run all tests:
pytest tests/

Run integration only:
pytest tests/integration/

Run with coverage:
pytest tests/ --cov=jn --cov-report=term-missing

Target: 85%+ coverage, but quality over quantity. 100% coverage of trivial getters/setters is not the goal.

## Success Metrics

A well-tested feature has:

1. **Integration test** that exercises the full CLI workflow
2. **Realistic test data** either from fixture or inline
3. **Clear assertions** about user-visible behavior
4. **Edge cases covered** (empty input, errors, etc.)
5. **No internal implementation details** leaked into assertions

A test should fail when user-facing behavior changes, not when refactoring internals.
