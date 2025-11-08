# JN — Try Command Architecture

**Status:** DEPRECATED - Use `jn cat/head/tail` instead
**Updated:** 2025-11-08

---

## Deprecation Notice

**This command design has been superseded by `jn cat`, `jn head`, and `jn tail`.**

**Why deprecated:**
- `jn cat/head/tail` provides the same exploration capability with minimal syntax
- Auto-detection removes the need for explicit `--driver` and `--adapter` flags
- 2-word syntax (`jn cat data.csv`) vs 7+ words (`jn try source --driver file --path data.csv`)
- Unix-familiar command names (cat/head/tail) are more intuitive than "try"

**Migration:**
- `jn try source --driver file --path data.csv` → `jn cat data.csv`
- `jn try source --driver curl --url https://...` → `jn cat https://...`
- `jn try source --driver exec --argv dig --argv example.com` → `jn cat dig example.com`

**See:** `spec/arch/cat-command.md` for the replacement design.

---

## Original Purpose (Archived)

The `jn try` command enables **quick, ad-hoc testing** of pipeline components without persisting them to config. It's designed for:

- **Exploration**: Test an API endpoint before creating a source
- **Debugging**: Verify a jq expression before saving as converter
- **Prototyping**: Try different URLs/queries/transforms rapidly
- **Validation**: Check if a target accepts your data format

**Key principle:** Test first, save when it works.

---

## Core Concept

`jn try` is a **temporary component executor**:
- Takes component definition as CLI flags (not config)
- Runs immediately without persisting
- Outputs results to stdout for inspection
- Provides same behavior as saved components

**Workflow:**
```bash
# 1. Try a source
jn try source --driver curl --url "https://api.example.com/data"

# 2. Refine the query
jn try source --driver curl --url "https://api.example.com/data?limit=10"

# 3. Pipe through jq to test transform
jn try source --driver curl --url "..." | jq '.items[].name'

# 4. When satisfied, save to config
jn new source curl api-data --url "https://api.example.com/data?limit=10"
```

---

## Command Syntax

### Try Source

```bash
jn try source --driver <driver> [driver-specific-flags]

# Examples:
jn try source --driver exec --argv echo --argv '{"x":1}'
jn try source --driver curl --url "https://api.example.com/data"
jn try source --driver file --path data.json
jn try source --driver shell --cmd "cat file.json" --unsafe-shell
```

### Try Converter

```bash
jn try converter --expr <jq-expression>
jn try converter --file <path-to-jq-file>

# Examples:
echo '{"x":1}' | jn try converter --expr '.x * 2'
cat data.ndjson | jn try converter --expr 'select(.status == "ok")'
cat data.ndjson | jn try converter --file transform.jq
```

### Try Target

```bash
jn try target --driver <driver> [driver-specific-flags]

# Examples:
echo '{"test":"data"}' | jn try target --driver exec --argv cat
echo '{"test":"data"}' | jn try target --driver curl --method POST --url "https://httpbin.org/post"
echo '{"test":"data"}' | jn try target --driver file --path /tmp/output.json
```

---

## Implementation Strategy

### Architecture

`jn try` creates **ephemeral components** that exist only in memory:

```python
# Pseudocode for jn try source
def try_source(driver: str, **kwargs):
    # 1. Build component model from CLI args (don't validate name/uniqueness)
    source = Source(
        name="_ephemeral_source",  # Temporary name
        driver=driver,
        **parse_driver_spec(driver, kwargs)
    )

    # 2. Execute using existing pipeline code
    output = _run_source(source, params=None, env=os.environ, unsafe_shell=unsafe_shell)

    # 3. Write to stdout
    sys.stdout.buffer.write(output)
```

**Key insight:** Reuse `_run_source`, `_run_converter`, `_run_target` from `config/pipeline.py`. No new execution logic needed.

### CLI Structure

```python
# src/jn/cli/try.py

@app.command()
def try_source(
    driver: str,
    # Exec driver
    argv: Optional[List[str]] = None,
    # Shell driver
    cmd: Optional[str] = None,
    unsafe_shell: bool = False,
    # Curl driver
    url: Optional[str] = None,
    method: Optional[str] = "GET",
    header: Optional[List[str]] = None,
    # File driver
    path: Optional[str] = None,
    # Common
    env: Optional[List[str]] = None,
):
    """Test a source without saving to config."""
    # Build ephemeral source
    # Execute and output to stdout

@app.command()
def try_converter(
    expr: Optional[str] = None,
    file: Optional[str] = None,
    raw: bool = False,
):
    """Test a converter (reads from stdin)."""
    # Build ephemeral converter
    # Execute and output to stdout

@app.command()
def try_target(
    driver: str,
    # Same flags as try_source
    ...
):
    """Test a target (reads from stdin)."""
    # Build ephemeral target
    # Execute and output to stdout
```

---

## Use Cases

### 1. Test API Endpoint

```bash
# Try different endpoints/params without config bloat
jn try source --driver curl --url "https://api.github.com/users/octocat"
jn try source --driver curl --url "https://api.github.com/users/octocat/repos"
jn try source --driver curl --url "https://api.github.com/users/octocat/repos?per_page=5"

# When satisfied, save
jn new source curl github-repos \
  --url "https://api.github.com/users/octocat/repos?per_page=5"
```

### 2. Debug jq Expression

```bash
# Test transform on sample data
echo '{"user":{"name":"Alice","age":30}}' | jn try converter --expr '.user.name'
# Output: "Alice"

echo '{"user":{"name":"Alice","age":30}}' | jn try converter --expr '{name:.user.name, age:.user.age}'
# Output: {"name":"Alice","age":30}

# Save when working
jn new converter extract-user --expr '{name:.user.name, age:.user.age}'
```

### 3. Prototype Pipeline

```bash
# Try end-to-end before saving anything
jn try source --driver curl --url "https://api.example.com/data" \
| jn try converter --expr '.items[] | select(.status == "ok")' \
| jn try target --driver curl --method POST --url "https://webhook.site/..."

# If it works, save components and create pipeline
jn new source curl api --url "..."
jn new converter filter-ok --expr '...'
jn new target curl webhook --url "..."
jn new pipeline api-to-webhook --source api --converter filter-ok --target webhook
```

### 4. Validate Data Format

```bash
# Check if target accepts your data
cat sample.ndjson | jn try target --driver curl \
  --method POST \
  --url "https://api.example.com/ingest" \
  --header "Content-Type: application/x-ndjson" \
  --header "Authorization: Bearer ${API_KEY}"

# Check response status/errors before committing to config
```

### 5. Test File Parsing

```bash
# Try CSV adapter before saving
jn try source --driver file --path data.csv --adapter csv
# See if it parses correctly

# Try with different delimiter
jn try source --driver file --path data.tsv --adapter csv --csv-delimiter $'\t'

# Save when parsing looks good
jn new source file users --path data.csv --adapter csv
```

---

## Output Behavior

### Success Case

```bash
$ jn try source --driver curl --url "https://httpbin.org/json"
{
  "slideshow": {
    "author": "Yours Truly",
    "date": "date of publication",
    "slides": [...]
  }
}
```

**Exit code:** 0

### Error Case

```bash
$ jn try source --driver curl --url "https://httpbin.org/status/404"
Error: ('source', '_ephemeral_source', 22, 'curl: (22) The requested URL returned error: 404')
```

**Exit code:** 1

### Validation Error

```bash
$ jn try converter
Error: Either --expr or --file required
Usage: jn try converter (--expr <jq> | --file <path>)
```

**Exit code:** 1

---

## Error Messages

**Prescriptive errors** that show the fix:

```bash
$ jn try source --driver curl
Error: --url required for curl driver
Try: jn try source --driver curl --url "https://api.example.com/data"

$ jn try converter
Error: Either --expr or --file required
Try: jn try converter --expr '.field'
Try: jn try converter --file transform.jq

$ jn try target --driver shell --cmd "cat > /tmp/out"
Error: shell driver requires --unsafe-shell flag
Try: jn try target --driver shell --cmd "..." --unsafe-shell
```

---

## Template Substitution

`jn try` supports **${env.*}** substitution (not ${params.*}, since there's no config):

```bash
# Environment variables work
export API_KEY="sk_test_123"
jn try source --driver curl \
  --url "https://api.example.com/data" \
  --header "Authorization: Bearer ${env.API_KEY}"

# Params don't apply (no pipeline context)
# Use shell variables instead:
ENDPOINT="https://api.example.com/data"
jn try source --driver curl --url "$ENDPOINT"
```

---

## Integration with Pipeline Workflow

**Recommended workflow:**

1. **Explore** with `jn try`
2. **Refine** via iteration
3. **Save** with `jn new`
4. **Compose** with `jn new pipeline`
5. **Run** with `jn run`

**Example:**

```bash
# Phase 1: Explore
jn try source --driver curl --url "https://hn.algolia.com/api/v1/search?query=python"
# See the data structure

# Phase 2: Refine transform
jn try source --driver curl --url "..." \
| jn try converter --expr '.hits[] | {title, url, points}'
# Looks good!

# Phase 3: Save
jn new source curl hn --url "https://hn.algolia.com/api/v1/search?query=python"
jn new converter extract --expr '.hits[] | {title, url, points}'
jn new target exec stdout --argv cat

# Phase 4: Compose
jn new pipeline hn-search --source hn --converter extract --target stdout

# Phase 5: Run repeatedly
jn run hn-search
jn run hn-search | head -5
jn explain hn-search --show-commands
```

---

## Testing Strategy

### Unit Tests

```python
def test_try_source_exec(runner):
    """Test jn try source with exec driver."""
    result = runner.invoke(app, [
        "try", "source",
        "--driver", "exec",
        "--argv", "echo",
        "--argv", '{"x":1}'
    ])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"x": 1}

def test_try_converter(runner):
    """Test jn try converter."""
    result = runner.invoke(
        app,
        ["try", "converter", "--expr", ".x * 2"],
        input='{"x":5}\n'
    )
    assert result.exit_code == 0
    assert result.output.strip() == "10"

def test_try_source_missing_url(runner):
    """Test error message for missing required flag."""
    result = runner.invoke(app, [
        "try", "source",
        "--driver", "curl"
    ])
    assert result.exit_code == 1
    assert "--url required" in result.output
```

### Integration Tests

```python
def test_try_source_curl_to_try_target(runner):
    """Test try source → try target pipeline."""
    # Get data from httpbin
    source_result = runner.invoke(app, [
        "try", "source",
        "--driver", "curl",
        "--url", "https://httpbin.org/json"
    ])
    assert source_result.exit_code == 0

    # POST it back to httpbin
    target_result = runner.invoke(
        app,
        [
            "try", "target",
            "--driver", "curl",
            "--method", "POST",
            "--url", "https://httpbin.org/post"
        ],
        input=source_result.output
    )
    assert target_result.exit_code == 0
    assert "slideshow" in target_result.output
```

---

## Relationship to Other Commands

### vs `jn new`

| Command | Purpose | Persists | Output |
|---------|---------|----------|--------|
| `jn try source` | Test before saving | ❌ No | stdout (data) |
| `jn new source` | Define component | ✅ Yes | Saved to config |

### vs `jn run`

| Command | Purpose | Requires Config | Output |
|---------|---------|-----------------|--------|
| `jn try source` | Ad-hoc test | ❌ No | stdout (data) |
| `jn run pipeline` | Execute saved pipeline | ✅ Yes | stdout (data) |

### vs `jn explain`

| Command | Purpose | Executes | Output |
|---------|---------|----------|--------|
| `jn try` | Test and execute | ✅ Yes | Data to stdout |
| `jn explain` | Show plan | ❌ No | Plan description |

---

## Implementation Checklist

- [ ] Create `src/jn/cli/try.py`
- [ ] Implement `try source` with all drivers
- [ ] Implement `try converter` with expr/file
- [ ] Implement `try target` with all drivers
- [ ] Add prescriptive error messages
- [ ] Support ${env.*} template substitution
- [ ] Write unit tests for each driver
- [ ] Write integration tests for pipelines
- [ ] Update help text with examples
- [ ] Add to roadmap

---

## Future Enhancements

### Try Pipeline (Inline Spec)

```bash
# Try a multi-step pipeline without config
jn try pipeline - <<EOF
source:
  driver: curl
  url: https://api.example.com/data
converter:
  expr: '.items[] | select(.active)'
target:
  driver: exec
  argv: [cat]
EOF
```

**Decision:** Defer until `jn try <component>` proves valuable. Don't over-engineer.

### Save from Try

```bash
# Try something
jn try source --driver curl --url "..." --save-as api-data
# Automatically runs: jn new source curl api-data --url "..."
```

**Decision:** Defer. Current workflow (try → new) is explicit and clear.

---

## Summary

`jn try` enables **rapid iteration** without config pollution:

**Use when:**
- Exploring new APIs/data sources
- Debugging transforms
- Prototyping pipelines
- Validating data formats

**Don't use when:**
- Building production pipelines (use `jn new` + `jn run`)
- Need repeatable execution (save to config)
- Need version control (save to config)

**Implementation:** Reuse existing execution logic, just skip config persistence.

**Estimated effort:** 4-6 hours (CLI wiring + tests)
