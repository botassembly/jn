# JN — Cat/Head/Tail Commands (Source Exploration)

**Status:** Design
**Updated:** 2025-11-08

---

## Purpose

The `jn cat`, `jn head`, and `jn tail` commands enable **immediate source exploration** without configuration. They auto-detect drivers and adapters based on the source pattern, making it trivial to inspect data from any source.

**Key principle:** Minimal syntax for maximum insight.

---

## Core Concept

These commands are **ephemeral source executors** that:
- Auto-detect driver (file, curl, exec) from source pattern
- Auto-detect adapter (csv, json, jc parser) from source type
- Apply optional slicing (head/tail semantics)
- Output JSON/NDJSON to stdout for piping to jq

**Workflow:**
```bash
# 1. Quick exploration
jn cat data.csv

# 2. Pipe through jq to refine
jn cat data.csv | jq '.[] | select(.age > 30)'

# 3. Try different sources
jn cat https://api.github.com/users/octocat
jn cat dig example.com

# 4. When satisfied, save to config
jn new source file users --path data.csv --adapter csv
```

---

## Command Syntax

### Cat - Output All
```bash
jn cat [OPTIONS] <source> [source-args...]

# Examples:
jn cat data.csv
jn cat https://api.github.com/users/octocat
jn cat dig example.com
jn cat ps aux
jn cat --slice 10:20 /var/log/syslog
jn cat --adapter csv --delimiter ';' data.txt
```

### Head - First N Lines
```bash
jn head [OPTIONS] <source> [source-args...]

# Examples:
jn head data.csv                    # default: 10 lines
jn head -n 20 data.csv              # first 20 lines
jn head -n 100 https://api.github.com/data
jn head dig example.com
```

### Tail - Last N Lines
```bash
jn tail [OPTIONS] <source> [source-args...]

# Examples:
jn tail data.csv                    # default: 10 lines
jn tail -n 20 data.csv              # last 20 lines
jn tail -n 100 netstat -an          # exec + jc --netstat, last 100
```

---

## Auto-Detection Strategy

Sources are detected in priority order:

### 1. URL Pattern → curl driver
```bash
jn cat https://api.github.com/users/octocat
jn cat http://localhost:3000/api/data
jn cat ftp://example.com/data.json
```
- **Pattern:** Starts with `http://`, `https://`, `ftp://`, `s3://`, etc.
- **Driver:** curl
- **Adapter:** json (default, can override)

### 2. File Exists → file driver + extension-based adapter
```bash
jn cat ./data.csv          # file + csv adapter
jn cat /var/log/syslog     # file + text adapter
jn cat users.json          # file + json adapter (passthrough)
jn cat report.xlsx         # file + excel adapter
```
- **Check:** `Path(source).exists()`
- **Driver:** file
- **Adapter:** Detected by extension (see table below)

### 3. Known Command → exec driver + jc adapter
```bash
jn cat dig example.com       # exec + jc --dig parser
jn cat ps aux                # exec + jc --ps parser
jn cat netstat -an           # exec + jc --netstat parser
jn cat ls -la /tmp           # exec + jc --ls parser
```
- **Check:** First token is in `jc.parser_mod_list()`
- **Driver:** exec
- **Adapter:** jc (uses jc's magic mode)

### 4. Unknown → exec driver + generic streaming adapter
```bash
jn cat mycustomcmd arg1 arg2
```
- **Fallback:** If not URL, not existing file, not known jc command
- **Driver:** exec
- **Adapter:** generic (streams line-by-line with metadata)
- **Output format:**
  ```json
  {"command":"mycustomcmd","args":["arg1","arg2"],"line":1,"text":"output line 1"}
  {"command":"mycustomcmd","args":["arg1","arg2"],"line":2,"text":"output line 2"}
  ```

---

## Adapter Auto-Detection by File Extension

| Extension | Adapter | Description |
|-----------|---------|-------------|
| `.csv`, `.tsv` | csv | CSV/TSV files |
| `.json`, `.jsonl`, `.ndjson` | json | JSON files (passthrough) |
| `.yaml`, `.yml` | yaml | YAML files |
| `.xml` | xml | XML files |
| `.xlsx`, `.xls` | excel | Excel spreadsheets |
| `.toml` | toml | TOML files |
| `.ini` | ini | INI files |
| (other) | auto | Auto-detect or generic |

Future: Make this extensible via plugins.

---

## Options

### Common Options (all commands)
| Option | Description | Default |
|--------|-------------|---------|
| `--slice START:STOP` | Line slice (Python-style) | All lines |
| `--adapter NAME` | Force specific adapter | Auto-detect |
| `--driver NAME` | Force specific driver | Auto-detect |
| `--delimiter CHAR` | CSV delimiter | `,` |
| `--jc-raw` | Use jc raw mode (no processing) | `false` |
| `--quiet` | Suppress warnings | `false` |

### Head-Specific Options
| Option | Description | Default |
|--------|-------------|---------|
| `-n NUM` | Number of lines | `10` |

### Tail-Specific Options
| Option | Description | Default |
|--------|-------------|---------|
| `-n NUM` | Number of lines | `10` |

---

## Generic Streaming Adapter (Fallback)

When a command is unknown (not a file, not a URL, not in jc registry), use a **generic streaming adapter** that wraps each line:

```python
def generic_streaming_adapter(command: str, args: list[str], output_lines: Iterable[str]):
    """Yield JSON objects for each line of output."""
    for line_num, line_text in enumerate(output_lines, start=1):
        yield {
            "command": command,
            "args": args,
            "line": line_num,
            "text": line_text.rstrip('\n'),
        }
```

**Example:**
```bash
$ jn cat mycustomscript arg1 arg2
{"command":"mycustomscript","args":["arg1","arg2"],"line":1,"text":"Hello from script"}
{"command":"mycustomscript","args":["arg1","arg2"],"line":2,"text":"Second line"}
```

This ensures **everything is JSON** even without a specific parser.

---

## Use Cases

### 1. Quick File Inspection
```bash
# CSV file
jn cat data.csv | jq '.[] | {name, age}'

# JSON file
jn cat api-response.json | jq '.data[] | select(.active)'

# Excel file
jn cat report.xlsx | jq '.[0] | keys'  # see column names
```

### 2. API Exploration
```bash
# GitHub API
jn cat https://api.github.com/users/octocat | jq '.login'

# Local API
jn cat http://localhost:3000/api/users | jq '.[] | .email'

# With headers (future)
jn cat --header "Authorization: Bearer ${TOKEN}" https://api.example.com/data
```

### 3. Command Output Parsing
```bash
# Parse dig output
jn cat dig example.com | jq '.[] | .answer[] | .data'

# Parse ps output
jn cat ps aux | jq '.[] | select(.user == "root") | .command'

# Parse netstat
jn cat netstat -an | jq '.[] | select(.state == "LISTEN") | .local_address'
```

### 4. Log File Analysis
```bash
# First 100 lines of syslog
jn head -n 100 /var/log/syslog | jq 'select(.priority == "error")'

# Last 50 lines
jn tail -n 50 /var/log/syslog | jq '.message'
```

### 5. Pipeline Prototyping
```bash
# Test full pipeline before saving
jn cat https://api.example.com/data \
  | jq '.items[] | select(.status == "active")' \
  | jq -s 'map({id, name})' \
  | head -5

# When satisfied, save as pipeline
jn new source curl api --url https://api.example.com/data
jn new converter filter --expr '.items[] | select(.status == "active")'
jn new pipeline active-items --source api --converter filter
```

---

## Ambiguity Resolution

### File vs Command Name Collision
```bash
# Create a file named "ps"
touch ps

jn cat ps              # File wins (exists on disk)
jn cat --driver exec ps aux   # Force exec driver
```

**Priority:** File existence > Command registry

### Override Detection
```bash
# Force specific driver
jn cat --driver file ./mycmd     # Read as file even if executable

# Force specific adapter
jn cat --adapter csv data.txt    # Treat as CSV even without .csv extension

# Force both
jn cat --driver curl --adapter json http://example.com/data.csv
```

---

## Error Messages

Prescriptive errors that suggest the fix:

```bash
$ jn cat
Error: Missing source argument
Try: jn cat data.csv
Try: jn cat https://api.example.com/data
Try: jn cat dig example.com

$ jn cat nonexistent.csv
Error: File not found: nonexistent.csv
Did you mean to run a command? Use: jn cat --driver exec nonexistent.csv

$ jn cat --adapter unknown data.csv
Error: Unknown adapter: unknown
Available adapters: csv, json, yaml, xml, excel, jc
Try: jn cat --adapter csv data.csv
```

---

## Implementation Architecture

### CLI Command Structure
```python
# src/jn/cli/cat.py

from jn.adapters import detect_source, apply_adapter
from jn.drivers import run_source

@app.command()
def cat(
    source: str = typer.Argument(..., help="Source: URL, file, or command"),
    source_args: list[str] = typer.Argument(None),
    slice: str = typer.Option(None, "--slice"),
    adapter: str = typer.Option(None, "--adapter"),
    driver: str = typer.Option(None, "--driver"),
    delimiter: str = typer.Option(",", "--delimiter"),
    jc_raw: bool = typer.Option(False, "--jc-raw"),
):
    """Output source data as JSON (auto-detects driver and adapter)."""
    # 1. Auto-detect or use explicit driver/adapter
    if driver is None:
        driver, detected_adapter, full_args = detect_source(source, source_args or [])
        adapter = adapter or detected_adapter
    else:
        full_args = [source] + (source_args or [])

    # 2. Build ephemeral source (like jn try)
    ephemeral_source = build_source(driver, adapter, full_args, delimiter, jc_raw)

    # 3. Execute source
    raw_output = run_source(ephemeral_source)

    # 4. Apply slice if specified
    if slice:
        raw_output = apply_slice(raw_output, slice)

    # 5. Output to stdout
    sys.stdout.buffer.write(raw_output)
```

### Detection Logic
```python
# src/jn/adapters/detect.py

import jc
from pathlib import Path
from urllib.parse import urlparse

def detect_source(source: str, args: list[str]) -> tuple[str, str, list[str]]:
    """
    Returns: (driver, adapter, full_source_args)
    """
    # 1. URL pattern
    if source.startswith(("http://", "https://", "ftp://", "s3://")):
        return ("curl", "json", [source])

    # 2. File exists
    path = Path(source)
    if path.exists():
        adapter = detect_file_adapter(source)
        return ("file", adapter, [source])

    # 3. Known jc command
    if source in jc.parser_mod_list():
        return ("exec", "jc", [source] + args)

    # 4. Unknown command (generic streaming)
    return ("exec", "generic", [source] + args)

def detect_file_adapter(path: str) -> str:
    """Detect adapter by file extension."""
    ext = Path(path).suffix.lower()
    mapping = {
        ".csv": "csv",
        ".tsv": "csv",
        ".json": "json",
        ".jsonl": "json",
        ".ndjson": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".xml": "xml",
        ".xlsx": "excel",
        ".xls": "excel",
        ".toml": "toml",
        ".ini": "ini",
    }
    return mapping.get(ext, "auto")
```

---

## Relationship to Other Commands

### vs `jn new source`
| Command | Purpose | Persists | Auto-detect |
|---------|---------|----------|-------------|
| `jn cat` | Explore source | ❌ No | ✅ Yes |
| `jn new source` | Define component | ✅ Yes | ❌ No |

### vs `jn run`
| Command | Purpose | Requires Config | Output |
|---------|---------|-----------------|--------|
| `jn cat` | Ad-hoc exploration | ❌ No | JSON to stdout |
| `jn run` | Execute pipeline | ✅ Yes | JSON to target |

### vs `jn try source` (deprecated)
| Command | Syntax Complexity | Auto-detect |
|---------|-------------------|-------------|
| `jn cat data.csv` | ⭐ Minimal (2 words) | ✅ Yes |
| `jn try source --driver file --path data.csv` | ❌ Verbose (7 words) | ❌ No |

**Decision:** Deprecate `jn try` in favor of `jn cat/head/tail`.

---

## Integration with ETL Workflow

Recommended workflow:

1. **Explore** with `jn cat/head/tail`
2. **Refine** with `jq` pipes
3. **Save** with `jn new source`
4. **Compose** with `jn new pipeline`
5. **Run** with `jn run`

**Example:**
```bash
# Phase 1: Explore
jn cat https://api.github.com/users/octocat
# See the data structure

# Phase 2: Refine transform
jn cat https://api.github.com/users/octocat | jq '{login, name, public_repos}'
# Looks good!

# Phase 3: Save source
jn new source curl github-user --url https://api.github.com/users/octocat

# Phase 4: Save converter
jn new converter extract-user --expr '{login, name, public_repos}'

# Phase 5: Create pipeline
jn new pipeline user-info --source github-user --converter extract-user --target stdout

# Phase 6: Run repeatedly
jn run user-info
```

---

## Testing Strategy

### Unit Tests
```python
def test_cat_csv_file(runner, tmp_path):
    """Test jn cat with CSV file."""
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("name,age\nAlice,30\nBob,25\n")

    result = runner.invoke(app, ["cat", str(csv_file)])
    assert result.exit_code == 0

    data = [json.loads(line) for line in result.output.splitlines()]
    assert data[0] == {"name": "Alice", "age": "30"}

def test_cat_url(runner):
    """Test jn cat with URL."""
    result = runner.invoke(app, ["cat", "https://httpbin.org/json"])
    assert result.exit_code == 0
    assert "slideshow" in result.output

def test_cat_jc_command(runner):
    """Test jn cat with jc-supported command."""
    result = runner.invoke(app, ["cat", "echo", '{"x":1}'])
    assert result.exit_code == 0
    # Should parse via jc or generic adapter

def test_head_limits_lines(runner, tmp_path):
    """Test jn head -n option."""
    csv_file = tmp_path / "data.csv"
    lines = ["name,age"] + [f"User{i},{i}" for i in range(100)]
    csv_file.write_text("\n".join(lines))

    result = runner.invoke(app, ["head", "-n", "5", str(csv_file)])
    assert result.exit_code == 0

    data = [json.loads(line) for line in result.output.splitlines()]
    assert len(data) == 5
```

---

## Implementation Checklist

- [ ] Create `src/jn/cli/cat.py`
- [ ] Implement `cat` command with auto-detection
- [ ] Implement `head` command with -n option
- [ ] Implement `tail` command with -n option
- [ ] Create `src/jn/adapters/detect.py` for auto-detection logic
- [ ] Implement generic streaming adapter for unknown commands
- [ ] Add file extension → adapter mapping
- [ ] Support jc parser registry integration
- [ ] Add prescriptive error messages
- [ ] Write unit tests for all detection cases
- [ ] Write integration tests for cat/head/tail
- [ ] Update help text with examples
- [ ] Add to roadmap
- [ ] Update user guide

---

## Future Enhancements

### 1. Header Support (for HTTP)
```bash
jn cat --header "Authorization: Bearer ${TOKEN}" \
       --header "Accept: application/json" \
       https://api.example.com/data
```

### 2. Follow Mode (like tail -f)
```bash
jn tail -f /var/log/syslog  # continuous streaming
jn tail -f --adapter syslog /var/log/syslog | jq 'select(.level == "ERROR")'
```

### 3. Multiple Sources (concatenate)
```bash
jn cat file1.json file2.json file3.json  # concat all
```

### 4. Adapter Plugins
Allow users to register custom adapters:
```python
# ~/.jn/adapters/custom_format.py
def parse(content: str) -> Iterable[dict]:
    # Custom parsing logic
    yield {"parsed": "data"}
```

---

## Summary

`jn cat/head/tail` enables **instant source exploration** with minimal syntax:

**Use when:**
- Exploring new data sources
- Quick inspection of files/APIs/commands
- Prototyping pipelines
- Learning data structure

**Don't use when:**
- Building production pipelines (use `jn new` + `jn run`)
- Need repeatable execution (save to config)
- Need complex multi-step transforms (use pipelines)

**Key advantage:** 2-word syntax (`jn cat data.csv`) vs 7+ words (`jn try source --driver file --path data.csv`)

**Implementation:** Reuse adapter/driver architecture, add smart auto-detection, provide generic fallback.
