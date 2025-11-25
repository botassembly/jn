# Table Rendering Analysis

## Executive Summary

JN's table rendering functionality is more capable than documented. The `table_.py` plugin supports **bidirectional** conversion (NDJSON ↔ tables), not just write-only as stated in design docs. However, the CLI ergonomics are poor, several bugs exist, and documentation is outdated.

**Key Findings:**
- Plugin is full-featured but underutilized
- CLI requires awkward `-- "-~table"` syntax
- Boolean parameter bug affects multiple plugins
- Design docs don't match implementation
- No demo existed (now created)

**Recommendation:** Create a dedicated `jn table` command to improve UX.

---

## Current State

### What Works Well

1. **Full Round-Trip Support**
   ```bash
   # NDJSON → Table
   echo '{"name":"Alice","age":30}' | jn put -- "-~table.grid"

   # Table → NDJSON (parsing!)
   echo '| name | age |
   |------|-----|
   | Alice| 30  |' | jn cat -- "-~table"
   ```

2. **25+ Output Formats** via tabulate library:
   - `grid`, `fancy_grid` - ASCII box tables
   - `github`, `pipe` - Markdown tables
   - `html`, `latex` - Export formats
   - `psql`, `rst`, `simple` - Various styles

3. **Shorthand Syntax**
   ```bash
   -~table.grid      # Expands to: -~table?tablefmt=grid
   -~table.github    # Expands to: -~table?tablefmt=github
   -~table.fancy_grid
   ```

4. **Auto-Detection** when reading tables:
   - Markdown/pipe tables (`| col |`)
   - Grid tables (`+----+`)
   - HTML tables (`<table>`)

5. **Type Preservation** in round-trip:
   - Numbers → int/float
   - Booleans → true/false
   - Null handling

6. **Comprehensive Tests**: 15 test cases in `test_plugin_call_table.py`

### Implementation Details

**Plugin Location:** `jn_home/plugins/formats/table_.py`

**Dependencies:** `tabulate>=0.9.0`

**Pattern Matches:**
```python
matches = [
    ".*\\.table$",   # .table files
    ".*\\.tbl$",     # .tbl files
    "^-$",           # stdin/stdout
    "^stdout$"       # explicit stdout
]
```

---

## Problems & Gaps

### 1. CLI Ergonomics (Major)

**Problem:** The `-~table` syntax conflicts with Click's option parsing.

```bash
# This fails:
jn put "-~table"
# Error: No such option: -~

# Must use awkward workaround:
jn put -- "-~table"
```

**Impact:** Every table usage requires the `--` separator, which is unintuitive and easy to forget.

### 2. Boolean Parameter Bug (Critical)

**Problem:** `action="store_true"` flags don't work via URL parameters.

```bash
# This fails:
jn put -- "-~table?showindex=true"
# Error: unrecognized arguments: True
```

**Root Cause:** The CLI converts `showindex=true` to Python `True`, then passes `--showindex True`. But argparse expects just `--showindex` (no value).

**Affected Plugins:**
| Plugin | Broken Flags |
|--------|--------------|
| table_ | `--showindex` |
| json_ | `--sort-keys` |
| markdown_ | `--include-frontmatter`, `--parse-structure` |
| xml_ | `--indent` |
| gmail_ | `--include-spam-trash` |
| watch_shell | `--recursive`, `--initial` |
| toml_ | `--preserve-comments` |

**Fix Location:** `src/jn/cli/commands/put.py` and `cat.py` need to handle booleans specially:
```python
# Current (broken):
cmd.extend([f"--{key}", str(value)])

# Fixed:
if isinstance(value, bool):
    if value:
        cmd.append(f"--{key}")  # No value for store_true
else:
    cmd.extend([f"--{key}", str(value)])
```

### 3. Documentation Mismatch (Medium)

**`spec/done/jtbl-renderer.md`** references:
- `jn jtbl` command (doesn't exist)
- "jtbl library by Kelly Brazil" (we use tabulate)

**`spec/done/format-design.md`** states:
- Tables are "write-only" (false - we have bidirectional support)
- `tabulate_` plugin (actual name is `table_`)

### 4. SIGPIPE Handling (Minor)

**Problem:** Pipeline breaks produce ugly errors:

```bash
echo '{"a":1}' | jn put -- "-~table" | head -1
# Error: Writer error: BrokenPipeError: [Errno 32] Broken pipe
```

**Fix:** Add signal handler in `table_.py`:
```python
import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
```

### 5. Nested Data Handling (Minor)

**Problem:** Nested objects render as Python dict strings:

```bash
echo '{"user":{"name":"Alice"}}' | jn put -- "-~table"
# | user                    |
# | {'name': 'Alice'}       |  # Not helpful!
```

**Options:**
1. Flatten: `user.name` columns
2. JSON string: `{"name":"Alice"}`
3. Error with helpful message

### 6. No Terminal Width Detection

The plugin doesn't detect terminal width. Wide tables wrap awkwardly.

---

## Proposal: `jn table` Command

### Rationale

Tables are fundamentally different from other formats:
- **Terminal endpoint** - for human viewing
- **Not data interchange** - can't reliably pipe table output
- **Needs options** - format, width, alignment

A dedicated command would:
1. Eliminate `-- "-~"` awkwardness
2. Provide natural option syntax
3. Show in `jn --help` for discoverability
4. Enable terminal-aware features

### Proposed Interface

```bash
# Basic usage (what we want)
jn cat data.csv | jn table
jn cat data.csv | jn table --format github
jn cat data.csv | jn table --format grid --width 80

# Compare to current (awkward)
jn cat data.csv | jn put -- "-~table"
jn cat data.csv | jn put -- "-~table.github"
jn cat data.csv | jn put -- "-~table?maxcolwidths=80"
```

### Command Options

```
jn table [OPTIONS]

Options:
  -f, --format TEXT     Table format: grid, github, simple, fancy_grid, etc.
                        [default: grid]
  -w, --width INT       Max column width (auto-wraps text)
  --index               Show row numbers
  --align TEXT          Column alignment: left, right, center, decimal
  --no-header           Don't show header row
  -h, --help            Show this message and exit.
```

### Implementation Sketch

```python
# src/jn/cli/commands/table.py
@click.command()
@click.option("-f", "--format", "tablefmt", default="grid")
@click.option("-w", "--width", "maxcolwidths", type=int)
@click.option("--index", "showindex", is_flag=True)
def table(tablefmt, maxcolwidths, showindex):
    """Format NDJSON as a pretty table.

    Examples:
        jn cat data.csv | jn table
        jn cat data.csv | jn table -f github
        jn cat data.csv | jn table -f fancy_grid -w 40
    """
    # Import and call table plugin's writes() function directly
    # Or invoke via subprocess for isolation
```

### Pros and Cons

**Pros:**
- Clean syntax: `jn table` vs `jn put -- "-~table"`
- Natural options: `--format` vs `?tablefmt=`
- Discoverable: Shows in `jn --help`
- Can add terminal features (auto-width, colors)
- Matches mental model (tables are terminal output)

**Cons:**
- Redundant functionality (exists in `jn put`)
- More code to maintain
- Inconsistent (why not `jn csv`, `jn json`?)
- Two ways to do same thing

**Verdict:** Worth adding. Tables are special - they're for humans, not machines. The UX improvement justifies the redundancy.

---

## Action Items

### High Priority (Bugs)

1. **Fix boolean parameter bug** in `put.py` and `cat.py`
   - Handle `action="store_true"` flags specially
   - Affects 7+ plugins

2. **Update outdated design docs**
   - `jtbl-renderer.md` → reference actual `table_` plugin
   - `format-design.md` → document bidirectional support

### Medium Priority (UX)

3. **Create `jn table` command**
   - Clean interface without `-- "-~"` workaround
   - Natural options syntax
   - Terminal width detection

4. **Add SIGPIPE handler** to `table_.py`
   - Graceful handling of pipeline breaks

### Low Priority (Polish)

5. **Improve nested data handling**
   - Option to flatten or JSON-stringify

6. **Add terminal colorization**
   - Highlight headers
   - Alternate row colors

---

## Files Changed/Created

### Created
- `demos/table-rendering/run_examples.sh` - Comprehensive demo
- `spec/wip/table-analysis.md` - This document

### Updated
- `demos/README.md` - Added table-rendering demo

### Should Update
- `spec/done/jtbl-renderer.md` - Outdated references
- `spec/done/format-design.md` - Claims tables are write-only
- `src/jn/cli/commands/put.py` - Boolean flag bug fix
- `src/jn/cli/commands/cat.py` - Boolean flag bug fix

---

## Test Commands

```bash
# Verify table works
echo '{"a":1,"b":2}' | jn put -- "-~table"

# Verify shorthand works
echo '{"a":1,"b":2}' | jn put -- "-~table.github"

# Verify round-trip
echo '| a | b |
|---|---|
| 1 | 2 |' | jn cat -- "-~table"

# Bug: Boolean flags (currently broken)
echo '{"a":1}' | jn put -- "-~table?showindex=true"

# Run demo
cd demos/table-rendering && ./run_examples.sh
```
