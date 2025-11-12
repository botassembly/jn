# Addressability Implementation Plan

**Reference:** universal-addressability-strategy.md
**Status:** Ready for implementation
**Approach:** Clean rip-and-replace

---

## Overview

This document provides the **exact code changes** needed to implement the universal addressability strategy. All changes are breaking - no migration or deprecation.

---

## Part 1: Code to Remove

### 1.1 Remove `-p` Flag from Commands

**File:** `src/jn/cli/commands/cat.py`

**Remove these lines:**

```python
# Line 13-17: Remove option decorator and help text
@click.option(
    "--param", "-p",
    multiple=True,
    help="Profile parameter (format: key=value, can be used multiple times)"
)

# Line 19: Remove param argument
def cat(ctx, input_file, param):

# Lines 29-43: Remove entire parameter parsing block
    # Parse parameters into dict
    params = {}
    for p in param:
        if "=" not in p:
            click.echo(f"Error: Invalid parameter format '{p}'. Use: key=value", err=True)
            sys.exit(1)
        key, value = p.split("=", 1)

        # Support multiple values for same key (becomes list)
        if key in params:
            if not isinstance(params[key], list):
                params[key] = [params[key]]
            params[key].append(value)
        else:
            params[key] = value
```

**File:** `src/jn/cli/commands/filter.py`

**Remove these lines:**

```python
# Find and remove:
@click.option(
    "--param", "-p",
    multiple=True,
    help="Profile parameter..."
)

# Remove param argument from function signature
def filter(ctx, query, param):

# Remove parameter parsing block (similar to cat.py)
```

### 1.2 Remove `--tablefmt` Flag from put

**File:** `src/jn/cli/commands/put.py`

**Remove these lines:**

```python
# Line 14: Remove option decorator
@click.option("--tablefmt", default="simple", help="Table format for table plugin")

# Line 16: Remove tablefmt argument
def put(ctx, output_file, plugin, tablefmt):

# Line 32: Remove hardcoded table config
plugin_config={"tablefmt": tablefmt} if plugin in ("table", "table_") else None
```

### 1.3 Remove `--plugin` Flag (Redundant)

**File:** `src/jn/cli/commands/put.py`

**Keep `--plugin` for now** - it's useful for explicit overrides and backwards compatibility during transition. We can remove it later if query string syntax proves sufficient.

---

## Part 2: Code to Add

### 2.1 Add Query String Parser Utility

**File:** `src/jn/util.py` (NEW FILE)

**Add entire file:**

```python
"""Utility functions for JN framework."""

from typing import Dict, Tuple
from urllib.parse import parse_qs


def parse_address_with_query(address: str) -> Tuple[str, Dict]:
    """Parse address and extract query string parameters.

    Supports URL-style query strings for passing parameters to profiles,
    plugins, and format configurations.

    Args:
        address: Address that may contain query string (e.g., "@api/src?gene=BRAF")

    Returns:
        Tuple of (address_without_query, params_dict)

    Examples:
        parse_address_with_query("@api/src?gene=BRAF&limit=10")
        # Returns: ("@api/src", {"gene": "BRAF", "limit": "10"})

        parse_address_with_query("@api/src?gene=BRAF&gene=EGFR")
        # Returns: ("@api/src", {"gene": ["BRAF", "EGFR"]})

        parse_address_with_query("file.csv")
        # Returns: ("file.csv", {})
    """
    if "?" not in address:
        return address, {}

    # Split at first ? only
    ref, query_string = address.split("?", 1)

    # Parse query string (supports multiple values for same key)
    parsed = parse_qs(query_string)

    # Flatten single values, keep lists for multiple values
    params = {}
    for key, values in parsed.items():
        if len(values) == 1:
            params[key] = values[0]
        else:
            params[key] = values

    return ref, params


def extract_special_params(params: Dict) -> Tuple[Dict, Dict]:
    """Extract special framework parameters from params dict.

    Special parameters are reserved by the framework and not passed to plugins:
    - fmt: Force format plugin
    - plugin: Force specific plugin
    - table_fmt: Table output format (plugin config)

    All other parameters are passed through to plugins/profiles.

    Args:
        params: Parameter dict from query string

    Returns:
        Tuple of (special_params, remaining_params)

    Examples:
        extract_special_params({"fmt": "csv", "gene": "BRAF"})
        # Returns: ({"fmt": "csv"}, {"gene": "BRAF"})
    """
    special_keys = {"fmt", "plugin"}
    special = {k: params[k] for k in special_keys if k in params}
    remaining = {k: v for k, v in params.items() if k not in special_keys}

    return special, remaining
```

### 2.2 Update `cat` Command

**File:** `src/jn/cli/commands/cat.py`

**Replace entire file:**

```python
"""Cat command - read files and output NDJSON."""

import sys

import click

from ...context import pass_context
from ...core.pipeline import PipelineError, read_source
from ...util import parse_address_with_query, extract_special_params


@click.command()
@click.argument("input_files", nargs=-1, required=True)
@pass_context
def cat(ctx, input_files):
    """Read one or more files and output NDJSON to stdout.

    Supports multiple input sources including files, URLs, and profile references.
    Sources are processed sequentially and concatenated in NDJSON format.

    Query String Syntax:
        Use ?key=value&key2=value2 to pass parameters:
        - Profile params: @api/source?gene=BRAF&limit=10
        - Format hints: -?fmt=csv (for stdin)
        - Multiple values: ?gene=BRAF&gene=EGFR

    Examples:
        jn cat data.csv
            Read CSV file, output NDJSON

        jn cat file1.csv file2.json file3.yaml
            Concatenate multiple files to NDJSON

        jn cat "@genomoncology/alterations?gene=BRAF&limit=10"
            Read from HTTP profile with parameters

        jn cat local.csv "@api/remote?limit=100"
            Mix local files and remote profiles

        jn cat "-?fmt=csv"
            Read from stdin with explicit CSV format

        jn cat "@gmail/inbox?from=boss&newer_than=7d"
            Read from Gmail profile (requires gmail plugin)
    """
    try:
        for input_file in input_files:
            # Parse query string from address
            source_ref, all_params = parse_address_with_query(input_file)

            # Extract special framework params
            special, params = extract_special_params(all_params)

            # Pass remaining params to read_source
            read_source(
                source_ref,
                ctx.plugin_dir,
                ctx.cache_path,
                output_stream=sys.stdout,
                params=params if params else None,
                fmt=special.get("fmt"),
                explicit_plugin=special.get("plugin")
            )

    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
```

### 2.3 Update `put` Command

**File:** `src/jn/cli/commands/put.py`

**Replace entire file:**

```python
"""Put command - write NDJSON to file."""

import sys

import click

from ...context import pass_context
from ...core.pipeline import PipelineError, write_destination
from ...util import parse_address_with_query, extract_special_params


@click.command()
@click.argument("output_file")
@click.option("--plugin", help="Explicitly specify plugin to use (e.g., 'table', 'csv', 'json')")
@pass_context
def put(ctx, output_file, plugin):
    """Read NDJSON from stdin, write to file or stdout.

    Query String Syntax:
        Use ?key=value to pass plugin configuration:
        - Table format: -?table_fmt=grid
        - Plugin config: output.csv?delimiter=;
        - Multiple configs: -?table_fmt=grid&maxcolwidths=20

    Examples:
        jn cat data.csv | jn put output.json
            Convert CSV to JSON

        jn cat data.csv | jn put -
            Output NDJSON to stdout

        jn cat data.json | jn put "-?table_fmt=grid"
            Output as formatted table to stdout

        jn cat data.json | jn put "output.table?table_fmt=markdown"
            Write table in markdown format

        jn cat data.json | jn put "output.csv?delimiter=;"
            Write CSV with semicolon delimiter

        jn cat data.json | jn put --plugin table "-?table_fmt=grid&maxcolwidths=20"
            Explicit plugin with multiple config options
    """
    try:
        # Parse query string for plugin config
        dest, all_params = parse_address_with_query(output_file)

        # Extract special framework params
        special, plugin_config = extract_special_params(all_params)

        # Override plugin if specified in query string
        if special.get("plugin"):
            plugin = special["plugin"]

        # Format hint (e.g., -?fmt=table)
        fmt = special.get("fmt")

        # Pass stdin to write_destination
        write_destination(
            dest,
            ctx.plugin_dir,
            ctx.cache_path,
            input_stream=sys.stdin,
            plugin_name=plugin or fmt,  # Use fmt as plugin if no explicit plugin
            plugin_config=plugin_config if plugin_config else None
        )

    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
```

### 2.4 Update `filter` Command

**File:** `src/jn/cli/commands/filter.py`

**Update to use query string parsing:**

```python
"""Filter command - filter NDJSON using jq expressions or profiles."""

import sys

import click

from ...context import pass_context
from ...core.pipeline import PipelineError, filter_stream
from ...util import parse_address_with_query, extract_special_params


@click.command()
@click.argument("query")
@pass_context
def filter(ctx, query):
    """Filter NDJSON stream using jq expression or profile reference.

    Query String Syntax:
        Use ?key=value to pass parameters to filter profiles:
        - @builtin/pivot?row=product&col=month
        - @analytics/custom?by=status

    Examples:
        jn cat data.json | jn filter '.'
            Identity filter (pass through)

        jn cat data.json | jn filter '.[] | select(.active)'
            Filter with jq expression

        jn cat data.json | jn filter "@builtin/pivot?row=product&col=month"
            Use profile with parameters

        jn cat data.json | jn filter "@genomoncology/extract-hgvs"
            Use profile without parameters
    """
    try:
        # Parse query string from query (if it's a profile reference)
        query_ref, all_params = parse_address_with_query(query)

        # Extract special params (none expected for filter, but parse anyway)
        _, params = extract_special_params(all_params)

        # Pass stdin and stdout to filter_stream
        filter_stream(
            query_ref,
            ctx.plugin_dir,
            ctx.cache_path,
            params=params if params else None,
            input_stream=sys.stdin,
            output_stream=sys.stdout
        )

    except PipelineError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
```

### 2.5 Update `pipeline.py` Signatures

**File:** `src/jn/core/pipeline.py`

**Add new parameters to `read_source`:**

```python
def read_source(
    source: str,
    plugin_dir: Path,
    cache_path: Optional[Path],
    output_stream: TextIO = sys.stdout,
    params: Optional[Dict] = None,
    fmt: Optional[str] = None,              # NEW: Force format
    explicit_plugin: Optional[str] = None   # NEW: Force plugin
) -> None:
    """Read a source file or URL and output NDJSON to stream.

    Args:
        source: Path to source file, HTTP(S) URL, or special ("-", "stdin")
        plugin_dir: Plugin directory
        cache_path: Cache file path
        output_stream: Where to write output (default: stdout)
        params: Optional parameters for profile resolution (e.g., {"gene": "BRAF"})
        fmt: Optional format hint (overrides auto-detection)
        explicit_plugin: Optional plugin name (overrides registry matching)

    Raises:
        PipelineError: If plugin not found or execution fails
    """
    # Check UV availability
    _check_uv_available()

    # Handle stdin specially
    if source in ("-", "stdin"):
        return _read_stdin(output_stream, fmt, explicit_plugin, plugin_dir, cache_path)

    # Check if source is a profile reference
    headers_json = None
    if source.startswith("@"):
        try:
            url, headers = resolve_profile_reference(source, params)
            source = url  # Replace with resolved URL
            headers_json = json.dumps(headers)
        except HTTPProfileError as e:
            raise PipelineError(f"Profile error: {e}")

    # Continue with existing logic...
    # (rest of function unchanged)
```

**Add new helper function for stdin:**

```python
def _read_stdin(
    output_stream: TextIO,
    fmt: Optional[str],
    explicit_plugin: Optional[str],
    plugin_dir: Path,
    cache_path: Optional[Path]
) -> None:
    """Read from stdin with optional format hint.

    Args:
        output_stream: Where to write output
        fmt: Format hint (e.g., "csv", "json")
        explicit_plugin: Explicit plugin name
        plugin_dir: Plugin directory
        cache_path: Cache file path

    Raises:
        PipelineError: If format cannot be detected or plugin not found
    """
    plugins, registry = _load_plugins_and_registry(plugin_dir, cache_path)

    # Determine plugin to use
    if explicit_plugin:
        plugin_name = _resolve_plugin_name(explicit_plugin, plugins)
        if not plugin_name:
            raise PipelineError(f"Plugin '{explicit_plugin}' not found")
    elif fmt:
        # Use format hint to find plugin
        plugin_name = registry.match(f"file.{fmt}")
        if not plugin_name:
            raise PipelineError(f"No plugin found for format '{fmt}'")
    else:
        # Try auto-detection (JSON/NDJSON only)
        plugin_name = _auto_detect_stdin_format(sys.stdin, plugins)

    plugin = plugins[plugin_name]

    # Execute plugin
    proc = subprocess.Popen(
        ["uv", "run", "--script", plugin.path, "--mode", "read"],
        stdin=sys.stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Copy stdout to output_stream
    for line in proc.stdout:
        output_stream.write(line)

    proc.wait()

    if proc.returncode != 0:
        error_msg = proc.stderr.read()
        raise PipelineError(f"Reader error: {error_msg}")


def _auto_detect_stdin_format(stream: TextIO, plugins: Dict) -> str:
    """Auto-detect format from stdin content.

    Currently only supports JSON/NDJSON auto-detection.
    Raises helpful error if detection fails.

    Args:
        stream: Input stream to detect
        plugins: Available plugins

    Returns:
        Plugin name (e.g., "json_")

    Raises:
        PipelineError: If format cannot be detected
    """
    # For now, default to JSON/NDJSON
    # TODO: More sophisticated detection (peek at first line)
    if "json_" in plugins:
        return "json_"

    # Cannot auto-detect
    raise PipelineError(
        "Cannot auto-detect stdin format. "
        "Use format hint:\n"
        '  jn cat "-?fmt=csv"  # for CSV\n'
        '  jn cat "-?fmt=json" # for JSON'
    )
```

---

## Part 3: Test Updates

### 3.1 Fix Test Pollution

**File:** `tests/profiles/test_http_profiles.py`

**Problem:** Imports old API that doesn't exist anymore.

**Fix:** Replace old imports:

```python
# OLD (remove):
from jn.profiles.http import (
    HTTPProfile,        # ❌ Doesn't exist
    load_profile,       # ❌ Doesn't exist
    ProfileError,       # ✅ Keep
    find_profile_paths, # ✅ Keep
    resolve_profile_reference  # ✅ Keep
)

# NEW (use):
from jn.profiles.http import (
    ProfileError,
    find_profile_paths,
    resolve_profile_reference,
    load_hierarchical_profile,  # Use this instead of HTTPProfile
    substitute_env_vars
)
```

**Update test cases:**

```python
# OLD test:
def test_load_profile():
    profile = HTTPProfile("test", config, path)
    url = profile.resolve_path("/users", {"id": "123"})

# NEW test:
def test_load_hierarchical_profile():
    profile = load_hierarchical_profile("genomoncology", "alterations")
    assert "base_url" in profile
    assert "path" in profile

def test_resolve_profile_reference():
    url, headers = resolve_profile_reference("@genomoncology/alterations")
    assert url.startswith("https://")
    assert "Authorization" in headers or "X-API-Key" in headers
```

### 3.2 Update Integration Tests

**Files:** All test files that use `-p` flags

**Find and replace:**

```bash
# Find all tests using -p:
grep -r "\-p " tests/

# Replace with query string syntax:
# OLD: jn cat @api/src -p gene=BRAF
# NEW: jn cat "@api/src?gene=BRAF"
```

**Example updates:**

```python
# OLD:
result = runner.invoke(cli, ["cat", "@genomoncology/alterations", "-p", "gene=BRAF"])

# NEW:
result = runner.invoke(cli, ["cat", "@genomoncology/alterations?gene=BRAF"])
```

### 3.3 Add New Tests

**File:** `tests/util/test_util.py` (NEW)

```python
"""Tests for utility functions."""

import pytest
from jn.util import parse_address_with_query, extract_special_params


def test_parse_address_simple():
    """Test parsing address without query string."""
    ref, params = parse_address_with_query("file.csv")
    assert ref == "file.csv"
    assert params == {}


def test_parse_address_with_query():
    """Test parsing address with query string."""
    ref, params = parse_address_with_query("@api/src?gene=BRAF&limit=10")
    assert ref == "@api/src"
    assert params == {"gene": "BRAF", "limit": "10"}


def test_parse_address_multiple_values():
    """Test parsing multiple values for same key."""
    ref, params = parse_address_with_query("@api/src?gene=BRAF&gene=EGFR")
    assert ref == "@api/src"
    assert params == {"gene": ["BRAF", "EGFR"]}


def test_extract_special_params():
    """Test extracting special framework params."""
    special, remaining = extract_special_params({
        "fmt": "csv",
        "plugin": "csv_",
        "gene": "BRAF"
    })
    assert special == {"fmt": "csv", "plugin": "csv_"}
    assert remaining == {"gene": "BRAF"}


def test_extract_special_params_empty():
    """Test when no special params present."""
    special, remaining = extract_special_params({"gene": "BRAF", "limit": "10"})
    assert special == {}
    assert remaining == {"gene": "BRAF", "limit": "10"}
```

**File:** `tests/cli/test_cat_multifile.py` (NEW)

```python
"""Tests for multi-file cat functionality."""

import pytest
from click.testing import CliRunner
from jn.cli.main import cli


def test_cat_multiple_files(tmp_path):
    """Test concatenating multiple files."""
    # Create test files
    file1 = tmp_path / "data1.json"
    file1.write_text('{"a": 1}\n{"a": 2}')

    file2 = tmp_path / "data2.json"
    file2.write_text('{"a": 3}\n{"a": 4}')

    # Run cat with multiple files
    runner = CliRunner()
    result = runner.invoke(cli, ["cat", str(file1), str(file2)])

    assert result.exit_code == 0
    lines = result.output.strip().split("\n")
    assert len(lines) == 4
    assert '{"a": 1}' in lines[0]
    assert '{"a": 4}' in lines[3]


def test_cat_no_files():
    """Test cat with no files (should error)."""
    runner = CliRunner()
    result = runner.invoke(cli, ["cat"])

    assert result.exit_code != 0
    assert "required" in result.output.lower() or "missing" in result.output.lower()
```

---

## Part 4: Documentation Updates

### 4.1 README.md

**Find and replace all examples:**

```bash
# OLD:
jn cat @genomoncology/alterations -p gene=BRAF -p limit=10
jn cat data.json | jn put --tablefmt grid -

# NEW:
jn cat "@genomoncology/alterations?gene=BRAF&limit=10"
jn cat data.json | jn put "-?table_fmt=grid"
```

### 4.2 CLAUDE.md

**Update examples in project instructions:**

```bash
# OLD:
jn cat @api/source -p gene=BRAF

# NEW:
jn cat "@api/source?gene=BRAF"
```

### 4.3 Spec Documents

**Files to update:**

- `spec/design/api-parameter-patterns.md` - Mark as DEPRECATED, point to universal-addressability-strategy.md
- `spec/design/rest-api-profiles.md` - Update examples to use query strings
- `spec/design/genomoncology-api.md` - Update examples
- `spec/workflows/genomoncology-examples.md` - Update examples

### 4.4 Profile README Files

**If any exist in:**

- `jn_home/profiles/http/*/README.md`
- `jn_home/profiles/jq/*/README.md`

**Update examples to use query string syntax.**

---

## Part 5: Error Messages for Old Syntax

### 5.1 Temporary Compatibility Errors

**Add to `cat.py` temporarily (remove after transition):**

```python
@click.option("--param", "-p", multiple=True, hidden=True)  # Hidden from help
def cat(ctx, input_files, param):
    """..."""
    # Check if old syntax used
    if param:
        click.echo(
            "Error: The -p flag is no longer supported.\n"
            "\n"
            "Use query string syntax instead:\n"
            '  Old: jn cat @api/src -p gene=BRAF\n'
            '  New: jn cat "@api/src?gene=BRAF"\n'
            "\n"
            "See: spec/design/universal-addressability-strategy.md",
            err=True
        )
        sys.exit(1)

    # Continue with normal logic...
```

**Add to `put.py` temporarily:**

```python
@click.option("--tablefmt", hidden=True)  # Hidden from help
def put(ctx, output_file, plugin, tablefmt):
    """..."""
    # Check if old syntax used
    if tablefmt:
        click.echo(
            "Error: The --tablefmt flag is no longer supported.\n"
            "\n"
            "Use query string syntax instead:\n"
            '  Old: jn put --tablefmt grid -\n'
            '  New: jn put "-?table_fmt=grid"\n'
            "\n"
            "See: spec/design/universal-addressability-strategy.md",
            err=True
        )
        sys.exit(1)

    # Continue with normal logic...
```

**Remove these after 1-2 releases** once users have migrated.

---

## Part 6: Validation & Testing

### 6.1 Manual Testing Checklist

**Before committing, test these scenarios:**

```bash
# Basic file reading
jn cat data.csv
jn cat data.json
jn cat data.yaml

# Multi-file cat
jn cat file1.csv file2.json file3.yaml

# HTTP profiles with params
jn cat "@genomoncology/alterations?gene=BRAF&limit=10"

# Filter profiles with params
jn cat data.json | jn filter "@builtin/pivot?row=product&col=month"

# Table output
jn cat data.json | jn put "-?table_fmt=grid"
jn cat data.json | jn put "output.table?table_fmt=markdown"

# Stdin with format hint
cat data.csv | jn cat "-?fmt=csv"
echo '{"a":1}' | jn cat - | jn put output.json

# Multiple values
jn cat "@api/data?gene=BRAF&gene=EGFR"

# Old syntax (should error helpfully)
jn cat @api/src -p gene=BRAF  # Should show helpful error
jn put --tablefmt grid -      # Should show helpful error
```

### 6.2 Test Suite

**Run full test suite:**

```bash
make test
```

**Expected:**
- Some tests will fail initially (those using `-p` syntax)
- Fix tests one by one
- All tests should pass before committing

### 6.3 Performance Testing

**Ensure query string parsing doesn't add overhead:**

```bash
# Benchmark: 10k lines, should complete in <1s
time jn cat large.csv | jn put "-?table_fmt=simple" > /dev/null
```

---

## Part 7: Implementation Order

**Follow this order to minimize breakage:**

### Step 1: Add New Code (Non-Breaking)
1. ✅ Create `src/jn/util.py` with query string parsing
2. ✅ Add tests for `util.py` functions
3. ✅ Test query string parsing in isolation

### Step 2: Update Commands (Breaking)
4. ✅ Update `cat.py` - add multi-file support, query string parsing
5. ✅ Update `put.py` - remove tablefmt hardcoding, add query string
6. ✅ Update `filter.py` - add query string parsing
7. ✅ Update `pipeline.py` - add fmt/explicit_plugin params, stdin handling

### Step 3: Fix Tests
8. ✅ Fix `test_http_profiles.py` - remove old API imports
9. ✅ Update all tests using `-p` flags
10. ✅ Add new tests for multi-file cat
11. ✅ Add tests for stdin format hints
12. ✅ Verify all tests pass

### Step 4: Update Docs
13. ✅ Update README examples
14. ✅ Update CLAUDE.md examples
15. ✅ Update spec documents
16. ✅ Mark old specs as deprecated

### Step 5: Add Error Messages (Temporary)
17. ✅ Add helpful errors for `-p` flag
18. ✅ Add helpful errors for `--tablefmt` flag
19. ✅ Test that old syntax shows good errors

### Step 6: Manual Testing
20. ✅ Test all examples from strategy doc
21. ✅ Test edge cases (empty files, errors, etc.)
22. ✅ Performance test (ensure no regression)

### Step 7: Cleanup (Later)
23. ⏸️ Remove compatibility error messages (after 1-2 releases)
24. ⏸️ Remove `--plugin` flag if no longer needed
25. ⏸️ Archive old spec documents

---

## Part 8: Git Commit Strategy

**Commit structure for clean history:**

### Commit 1: Add utility functions
```
feat: add query string parsing utilities

- Add parse_address_with_query() function
- Add extract_special_params() function
- Add tests for utility functions
- Non-breaking addition
```

### Commit 2: Update cat command
```
feat!: switch cat to query string parameters

BREAKING CHANGE: -p flag removed, use ?key=value syntax

- Remove -p flag from cat command
- Add multi-file support (nargs=-1)
- Parse query strings for parameters
- Update command help text
```

### Commit 3: Update put command
```
feat!: switch put to query string config

BREAKING CHANGE: --tablefmt flag removed, use ?table_fmt=value

- Remove --tablefmt flag
- Parse query strings for plugin config
- Generic config handling for all plugins
- Update command help text
```

### Commit 4: Update filter command
```
feat!: switch filter to query string parameters

BREAKING CHANGE: -p flag removed, use ?key=value syntax

- Remove -p flag from filter command
- Parse query strings for profile params
- Update command help text
```

### Commit 5: Fix tests
```
test: update tests for query string syntax

- Fix test_http_profiles.py (remove old API usage)
- Update all tests using -p flags
- Add tests for multi-file cat
- Add tests for stdin format hints
```

### Commit 6: Update documentation
```
docs: update all examples to query string syntax

- Update README.md examples
- Update CLAUDE.md examples
- Update spec documents
- Add universal-addressability-strategy.md
- Add addressability-implementation-plan.md
```

---

## Summary

**Total Changes:**

- **Files modified:** 7 (cat.py, put.py, filter.py, pipeline.py, test_http_profiles.py, README.md, CLAUDE.md)
- **Files added:** 3 (util.py, universal-addressability-strategy.md, addressability-implementation-plan.md, test_util.py)
- **Files deleted:** 0
- **Lines added:** ~500
- **Lines removed:** ~150
- **Net change:** +350 lines

**Risk Assessment:**

- ✅ **Low risk:** Utility functions (pure, tested)
- ⚠️ **Medium risk:** Command updates (breaking but clear)
- ⚠️ **Medium risk:** Test updates (some manual work)
- ✅ **Low risk:** Documentation (cosmetic)

**Timeline Estimate:**

- Part 1-2 (Code): 2-3 hours
- Part 3 (Tests): 2-3 hours
- Part 4-5 (Docs/Errors): 1 hour
- Part 6 (Testing): 1 hour
- **Total:** 6-8 hours of focused work

**Success Criteria:**

1. ✅ All tests pass
2. ✅ Old syntax shows helpful errors
3. ✅ New syntax works for all examples
4. ✅ Performance unchanged (no regression)
5. ✅ Documentation updated
6. ✅ Clean commit history
