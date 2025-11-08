# JN — Exit Code Conventions

**Status:** Design / Implementation Ready
**Updated:** 2025-11-08

---

## Purpose

Standardize exit codes across all JN commands for **reliable automation** and **clear error diagnosis**.

**Use cases:**
- **Shell scripts**: `jn run pipeline && next-step || handle-error`
- **CI/CD**: Distinguish transient failures from config errors
- **Monitoring**: Alert on specific error types
- **Retry logic**: Retry connection errors but not validation errors

**Key principle:** Exit codes should be **meaningful** and **actionable**.

---

## Exit Code Table

| Code | Name | Meaning | Retry? | Examples |
|------|------|---------|--------|----------|
| 0 | Success | Command completed successfully | N/A | Pipeline ran, component created |
| 1 | Usage Error | Invalid arguments or flags | ❌ No | Missing required flag, invalid format |
| 2 | Validation Error | Config or data validation failed | ❌ No | Invalid jq syntax, schema mismatch, malformed JSON |
| 3 | Connection Error | Network or I/O failure | ✅ Yes | HTTP timeout, DNS failure, file not found |
| 4 | Not Found | Resource doesn't exist | ❌ No | Pipeline/source/converter/target not found |
| 5 | Auth Error | Authentication or authorization failed | ⚠️ Maybe | Invalid API key, 401/403 HTTP status |
| 6 | Runtime Error | Unexpected execution failure | ⚠️ Maybe | Process crash, OOM, jq runtime error |

---

## Exit Code Details

### 0: Success

**Meaning:** Command completed as intended.

**Examples:**
- Pipeline executed successfully
- Component created in config
- List/explain commands returned data

**Shell behavior:**
```bash
jn run pipeline && echo "Success"
# Output: Success

if jn list pipelines > /dev/null; then
  echo "Config has pipelines"
fi
```

---

### 1: Usage Error

**Meaning:** User provided invalid arguments, wrong flag combinations, or missing required values.

**Examples:**
```bash
# Missing required argument
$ jn run
Error: Missing argument 'PIPELINE'
Exit code: 1

# Invalid flag combination
$ jn try converter
Error: Either --expr or --file required
Exit code: 1

# Wrong format
$ jn run pipeline --param invalid
Error: --param must be in KEY=VALUE format
Got: 'invalid'
Exit code: 1
```

**When to use:**
- Missing required arguments
- Invalid flag values
- Wrong format (e.g., KEY=VALUE parsing)
- Conflicting flags

**Retry?** ❌ No - User must fix command

---

### 2: Validation Error

**Meaning:** Config or data failed validation (syntax, schema, types).

**Examples:**
```bash
# Invalid jq syntax
$ jn new converter bad '.invalid syntax here'
Error: jq syntax error: ...
Exit code: 2

# Malformed JSON in pipeline
$ jn run pipeline < invalid.json
Error: JSON parse error at line 5
Exit code: 2

# Schema validation failure
$ jn shape --in data.json --validate schema.json
Error: Validation failed: missing required field 'email'
Exit code: 2

# Invalid config
$ jn list
Error: jn.json validation error: duplicate pipeline name 'test'
Exit code: 2
```

**When to use:**
- jq syntax errors
- JSON parse errors
- Schema validation failures
- Config validation errors (duplicate names, invalid structure)

**Retry?** ❌ No - Data or config must be fixed

---

### 3: Connection Error

**Meaning:** Network, file system, or external process I/O failed.

**Examples:**
```bash
# HTTP request timeout
$ jn run api-pipeline
Error: Connection timeout: https://api.example.com/data
curl: (28) Operation timeout after 30000ms
Exit code: 3

# DNS failure
$ jn try source --driver curl --url "https://nonexistent.invalid"
Error: Could not resolve host: nonexistent.invalid
curl: (6) Could not resolve host
Exit code: 3

# File not found
$ jn try source --driver file --path /nonexistent/file.json
Error: File not found: /nonexistent/file.json
Exit code: 3

# Process not found
$ jn run pipeline
Error: Command not found: nonexistent-command
Exit code: 3
```

**When to use:**
- HTTP timeouts, connection refused, DNS errors
- File not found, permission denied
- External command not found
- Process execution failures (non-zero exit from subprocess)

**Retry?** ✅ Yes - Transient failures often resolve

**Automation pattern:**
```bash
# Retry with exponential backoff
for i in 1 2 3; do
  jn run api-pipeline && break
  if [ $? -eq 3 ]; then
    echo "Connection error, retrying in ${i}s..."
    sleep $i
  else
    exit $?  # Don't retry non-connection errors
  fi
done
```

---

### 4: Not Found

**Meaning:** Referenced resource (pipeline, source, converter, target) doesn't exist in config.

**Examples:**
```bash
# Pipeline not found
$ jn run nonexistent
Error: Pipeline 'nonexistent' not found

Available pipelines:
  - etl-job
  - api-sync

Try: jn list pipelines
Exit code: 4

# Source not found in pipeline
$ jn explain broken-pipeline
Error: Source 'api-source' not found (referenced by pipeline 'broken-pipeline')

Available sources:
  - github-api
  - local-file

Try: jn list sources
Exit code: 4

# Converter not found
$ jn new pipeline test --source api --converter nonexistent --target stdout
Error: Converter 'nonexistent' not found

Available converters:
  - filter-active
  - extract-fields

Try: jn list converters
Exit code: 4
```

**When to use:**
- Pipeline/source/converter/target not found
- Config file not found (distinct from validation error)

**Retry?** ❌ No - Config must be updated

**Note:** HTTP 404 responses should use exit code 3 (connection error), not 4. Exit code 4 is for **config resources**, not **data resources**.

---

### 5: Auth Error

**Meaning:** Authentication or authorization failed (invalid credentials, expired tokens, insufficient permissions).

**Examples:**
```bash
# HTTP 401 Unauthorized
$ jn run secure-api
Error: Authentication failed: 401 Unauthorized
Check API_KEY environment variable
curl: (22) HTTP error 401
Exit code: 5

# HTTP 403 Forbidden
$ jn run admin-endpoint
Error: Authorization failed: 403 Forbidden
Insufficient permissions for endpoint
Exit code: 5

# Missing auth token
$ jn run pipeline
Error: Missing required environment variable: API_KEY
Required by: source 'secure-api'
Try: export API_KEY=your_token
Exit code: 5
```

**When to use:**
- HTTP 401/403 status codes
- Missing required environment variables (auth-related)
- Invalid/expired credentials

**Retry?** ⚠️ Maybe - If using short-lived tokens that refresh

**Automation pattern:**
```bash
jn run secure-api
if [ $? -eq 5 ]; then
  # Refresh token and retry
  get-new-token
  export API_KEY=$NEW_TOKEN
  jn run secure-api
fi
```

---

### 6: Runtime Error

**Meaning:** Unexpected failure during execution (crashes, resource exhaustion, internal errors).

**Examples:**
```bash
# jq runtime error (type mismatch)
$ echo '{"x":"not-a-number"}' | jn try converter --expr '.x + 1'
Error: jq runtime error: string ("not-a-number") cannot be added
Exit code: 6

# Out of memory (rare, OS-level)
$ jn run huge-pipeline
Error: Process killed (likely OOM)
Exit code: 6

# Unexpected subprocess crash
$ jn run pipeline
Error: Source process crashed with signal SIGSEGV
Exit code: 6

# Internal assertion failure
$ jn run pipeline
Error: Internal error: unexpected state in pipeline execution
Please report this bug at https://github.com/your/repo/issues
Exit code: 6
```

**When to use:**
- jq runtime errors (type mismatches, index out of bounds)
- Process crashes (signals)
- Resource exhaustion
- Internal assertion failures

**Retry?** ⚠️ Maybe - Depends on root cause

---

## Exit Code by Command

### `jn run`

| Exit Code | Scenario |
|-----------|----------|
| 0 | Pipeline executed successfully |
| 1 | Missing pipeline name, invalid --param format |
| 2 | jq syntax error, JSON parse error in stream |
| 3 | HTTP timeout, curl error, file not found, subprocess failed |
| 4 | Pipeline not found, source/converter/target not found |
| 5 | HTTP 401/403, missing auth env var |
| 6 | jq runtime error, process crash |

### `jn new source/converter/target/pipeline`

| Exit Code | Scenario |
|-----------|----------|
| 0 | Component created successfully |
| 1 | Missing required flag (e.g., --url for curl), invalid format |
| 2 | Config validation error (duplicate name, invalid structure) |
| 4 | Referenced component not found (pipeline creation only) |

### `jn list`

| Exit Code | Scenario |
|-----------|----------|
| 0 | List displayed successfully (even if empty) |
| 1 | Invalid component type argument |
| 2 | Config file validation error |

### `jn explain`

| Exit Code | Scenario |
|-----------|----------|
| 0 | Explanation displayed successfully |
| 1 | Invalid flags |
| 2 | Config validation error |
| 4 | Pipeline not found |

### `jn try source/converter/target`

| Exit Code | Scenario |
|-----------|----------|
| 0 | Component executed successfully |
| 1 | Missing required flag, invalid driver |
| 2 | jq syntax error, JSON parse error |
| 3 | HTTP error, file not found, subprocess failed |
| 5 | HTTP 401/403 |
| 6 | jq runtime error |

### `jn shape`

| Exit Code | Scenario |
|-----------|----------|
| 0 | Analysis completed successfully |
| 1 | Missing --in or --source, invalid flags |
| 2 | JSON parse error, schema validation failed |
| 3 | File not found, source execution failed |
| 4 | Source not found (when using --source) |

### `jn init`

| Exit Code | Scenario |
|-----------|----------|
| 0 | Config created successfully |
| 1 | File already exists (use --force) |
| 2 | Write error (permissions, disk full) |

---

## Implementation Strategy

### Exception Hierarchy

```python
# src/jn/errors.py

class JNError(Exception):
    """Base exception for all JN errors."""

    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


class UsageError(JNError):
    """Invalid command-line usage (exit code 1)."""

    def __init__(self, message: str):
        super().__init__(message, exit_code=1)


class ValidationError(JNError):
    """Config or data validation failed (exit code 2)."""

    def __init__(self, message: str):
        super().__init__(message, exit_code=2)


class ConnectionError(JNError):
    """Network or I/O failure (exit code 3)."""

    def __init__(self, message: str):
        super().__init__(message, exit_code=3)


class NotFoundError(JNError):
    """Resource not found (exit code 4)."""

    def __init__(self, message: str):
        super().__init__(message, exit_code=4)


class AuthError(JNError):
    """Authentication/authorization failed (exit code 5)."""

    def __init__(self, message: str):
        super().__init__(message, exit_code=5)


class RuntimeError(JNError):
    """Unexpected execution failure (exit code 6)."""

    def __init__(self, message: str):
        super().__init__(message, exit_code=6)
```

### Error Handling in CLI

```python
# src/jn/cli/run.py

@app.command()
def run(pipeline: str, ...) -> None:
    try:
        # Execute pipeline
        output = config.run_pipeline(pipeline, ...)
        sys.stdout.buffer.write(output)

    except JNError as e:
        # JN-specific errors (already have exit codes)
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=e.exit_code)

    except typer.Abort:
        # User interrupted (Ctrl-C)
        raise typer.Exit(code=130)  # Standard SIGINT exit code

    except Exception as e:
        # Unexpected errors
        typer.echo(f"Error: Unexpected failure: {e}", err=True)
        raise typer.Exit(code=6)
```

### Subprocess Exit Code Mapping

```python
# src/jn/drivers/exec.py

def run_exec(spec: ExecSpec, stdin: bytes | None = None) -> bytes:
    """Run exec driver and map exit codes."""
    try:
        result = subprocess.run(
            spec.argv,
            input=stdin,
            capture_output=True,
            cwd=spec.cwd,
            env=spec.env,
            timeout=30,
        )

        if result.returncode != 0:
            # Map subprocess errors to JN exit codes
            stderr = result.stderr.decode(errors="replace")

            # Check for specific error patterns
            if "command not found" in stderr.lower():
                raise ConnectionError(f"Command not found: {spec.argv[0]}")
            elif "permission denied" in stderr.lower():
                raise ConnectionError(f"Permission denied: {spec.argv[0]}")
            else:
                # Generic subprocess failure
                raise ConnectionError(
                    f"Command failed with exit code {result.returncode}:\n{stderr}"
                )

        return result.stdout

    except subprocess.TimeoutExpired as e:
        raise ConnectionError(f"Command timeout after 30s: {spec.argv[0]}")

    except FileNotFoundError as e:
        raise ConnectionError(f"Command not found: {spec.argv[0]}")
```

### Curl Exit Code Mapping

```python
# src/jn/drivers/curl.py

CURL_EXIT_CODE_MAP = {
    0: None,  # Success
    6: "Could not resolve host",
    7: "Failed to connect",
    22: "HTTP error (4xx/5xx)",
    28: "Operation timeout",
    35: "SSL connection error",
    52: "Server returned nothing",
}

def run_curl(spec: CurlSpec, stdin: bytes | None = None) -> bytes:
    """Run curl and map exit codes."""
    argv = build_curl_argv(spec)

    result = subprocess.run(argv, input=stdin, capture_output=True)

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        error_desc = CURL_EXIT_CODE_MAP.get(result.returncode, "Unknown error")

        # Check for auth errors
        if "401" in stderr or "403" in stderr:
            raise AuthError(f"HTTP authentication failed: {stderr}")

        # All other curl errors are connection errors
        raise ConnectionError(
            f"curl failed ({result.returncode}): {error_desc}\n{stderr}"
        )

    return result.stdout
```

---

## Testing Strategy

### Exit Code Tests

```python
def test_exit_code_success(runner, tmp_path):
    """Test exit code 0 on success."""
    jn_path = tmp_path / "jn.json"
    init_config(runner, jn_path)
    add_exec_source(runner, jn_path, "src", ["echo", '{"x":1}'])
    add_converter(runner, jn_path, "conv", ".")
    add_exec_target(runner, jn_path, "tgt", ["cat"])
    add_pipeline(runner, jn_path, "test", ["source:src", "converter:conv", "target:tgt"])

    result = runner.invoke(app, ["run", "test", "--jn", str(jn_path)])

    assert result.exit_code == 0


def test_exit_code_usage_error(runner, tmp_path):
    """Test exit code 1 for missing argument."""
    result = runner.invoke(app, ["run"])  # Missing pipeline name

    assert result.exit_code == 1
    assert "Missing argument" in result.output or "Usage:" in result.output


def test_exit_code_validation_error(runner, tmp_path):
    """Test exit code 2 for jq syntax error."""
    result = runner.invoke(app, ["try", "converter", "--expr", ".invalid syntax"])

    assert result.exit_code == 2
    assert "syntax" in result.output.lower()


def test_exit_code_connection_error(runner):
    """Test exit code 3 for connection failure."""
    result = runner.invoke(app, [
        "try", "source",
        "--driver", "curl",
        "--url", "https://nonexistent.invalid"
    ])

    assert result.exit_code == 3


def test_exit_code_not_found(runner, tmp_path):
    """Test exit code 4 for pipeline not found."""
    jn_path = tmp_path / "jn.json"
    init_config(runner, jn_path)

    result = runner.invoke(app, ["run", "nonexistent", "--jn", str(jn_path)])

    assert result.exit_code == 4
    assert "not found" in result.output.lower()


def test_exit_code_auth_error(runner):
    """Test exit code 5 for auth failure."""
    result = runner.invoke(app, [
        "try", "source",
        "--driver", "curl",
        "--url", "https://httpbin.org/status/401"
    ])

    assert result.exit_code == 5


def test_exit_code_runtime_error(runner):
    """Test exit code 6 for jq runtime error."""
    result = runner.invoke(
        app,
        ["try", "converter", "--expr", '.x + 1'],
        input='{"x":"not-a-number"}\n'
    )

    assert result.exit_code == 6
```

---

## Documentation

### In Help Text

Every command should document exit codes in epilog:

```
Exit codes: 0=success, 1=usage error, 3=connection error, 4=not found
```

### In README

**Error Handling**

JN uses standard exit codes for automation:

| Code | Meaning | Retry? |
|------|---------|--------|
| 0 | Success | N/A |
| 1 | Usage error | ❌ No |
| 2 | Validation error | ❌ No |
| 3 | Connection error | ✅ Yes |
| 4 | Not found | ❌ No |
| 5 | Auth error | ⚠️ Maybe |
| 6 | Runtime error | ⚠️ Maybe |

**Example: Retry logic**

```bash
for i in 1 2 3; do
  jn run pipeline && break
  code=$?
  if [ $code -eq 3 ]; then
    echo "Retrying connection error..."
    sleep $i
  else
    exit $code
  fi
done
```

---

## Implementation Checklist

- [ ] Create exception hierarchy (`src/jn/errors.py`)
- [ ] Update all CLI commands to raise typed exceptions
- [ ] Map subprocess exit codes to JN exit codes
- [ ] Map curl exit codes (especially 401/403 → exit 5)
- [ ] Handle jq errors (syntax → exit 2, runtime → exit 6)
- [ ] Add exit code documentation to all help text
- [ ] Write tests for each exit code scenario
- [ ] Update README with exit code table
- [ ] Add prescriptive errors with exit codes

---

## Edge Cases

### Multiple Errors

**Scenario:** Pipeline has multiple issues (e.g., source not found AND converter has syntax error)

**Resolution:** Return **first error encountered** during validation/execution. Don't try to aggregate.

**Example:**
```bash
$ jn run broken-pipeline
Error: Source 'nonexistent' not found (referenced by pipeline 'broken-pipeline')
Exit code: 4
```

(Converter syntax error won't be checked until source is fixed)

### Ctrl-C (SIGINT)

**Scenario:** User interrupts execution with Ctrl-C

**Exit code:** 130 (standard for SIGINT)

**Implementation:**
```python
except KeyboardInterrupt:
    typer.echo("\nInterrupted", err=True)
    raise typer.Exit(code=130)
```

### Signal Handling

**Scenario:** Process receives SIGTERM, SIGKILL, etc.

**Exit code:** 128 + signal number (standard Unix convention)
- SIGTERM (15) → exit 143
- SIGKILL (9) → exit 137

**Note:** OS handles this automatically, no JN code needed.

---

## Comparison to Other Tools

### Exit Code Conventions

| Tool | Success | Usage | Not Found | Connection | Other |
|------|---------|-------|-----------|------------|-------|
| JN | 0 | 1 | 4 | 3 | 2,5,6 |
| curl | 0 | N/A | N/A | 6,7,28 | 1-90 |
| jq | 0 | 2 | N/A | N/A | 1,3,4,5 |
| git | 0 | 1 | 128 | N/A | Various |
| AWS CLI | 0 | 2 | 254 | 253 | 1,255 |

**JN philosophy:** Simpler than curl (90 codes), more structured than jq.

---

## Summary

**Exit code conventions enable reliable automation:**

- **0**: Success (continue)
- **1**: Usage error (fix command)
- **2**: Validation error (fix config/data)
- **3**: Connection error (retry)
- **4**: Not found (fix config)
- **5**: Auth error (check credentials)
- **6**: Runtime error (investigate)

**Implementation:** Typed exception hierarchy with explicit exit codes.

**Documentation:** Every command documents exit codes in help text.

**Estimated effort:** 4-5 hours (exception hierarchy + mapping + tests)
