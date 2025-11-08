# JN — Plan Mode Architecture

**Status:** Design / Implementation Ready
**Updated:** 2025-11-07

---

## Purpose

Plan mode provides **dry-run introspection** for JN pipelines. It shows what *would* execute without actually executing it.

**Use cases:**
- **Debugging**: Understand execution plan before running
- **Validation**: Verify pipeline correctness
- **Documentation**: Auto-generate pipeline diagrams
- **Agents**: Inspect pipelines programmatically
- **CI/CD**: Validate configs in pull requests

**Key principle:** Show the execution plan in a machine-readable format.

---

## Command Syntax

Add `--plan` flag to any execution command:

```bash
jn run <pipeline> --plan
jn explain <pipeline> --plan  # Alternative: explain already shows plan
```

**Output:** Normalized execution plan as JSON to stdout.

---

## Output Format

### Basic Plan Structure

```json
{
  "apiVersion": "jn/v1",
  "kind": "PipelinePlan",
  "metadata": {
    "name": "my-pipeline",
    "created": "2025-11-07T22:00:00Z"
  },
  "spec": {
    "source": {
      "name": "api-source",
      "driver": "curl",
      "command": "curl -sS -X GET 'https://api.example.com/data'"
    },
    "converters": [
      {
        "name": "filter-active",
        "engine": "jq",
        "command": "jq -c 'select(.active == true)'"
      }
    ],
    "target": {
      "name": "stdout",
      "driver": "exec",
      "command": "cat"
    }
  },
  "env": {
    "API_KEY": "***REDACTED***",
    "PATH": "/usr/bin:/bin"
  }
}
```

### Plan with Template Expansion

**Config:**
```json
{
  "sources": [{
    "name": "api",
    "driver": "curl",
    "curl": {
      "url": "https://api.example.com/${params.endpoint}",
      "headers": {"Authorization": "Bearer ${env.API_KEY}"}
    }
  }]
}
```

**Command:**
```bash
jn run pipeline --param endpoint=users --plan
```

**Output:**
```json
{
  "spec": {
    "source": {
      "name": "api",
      "driver": "curl",
      "url": "https://api.example.com/users",
      "headers": {
        "Authorization": "Bearer ***REDACTED***"
      },
      "command": "curl -sS -X GET -H 'Authorization: Bearer sk_...' 'https://api.example.com/users'"
    }
  },
  "params": {
    "endpoint": "users"
  },
  "env": {
    "API_KEY": "***REDACTED***"
  }
}
```

**Key features:**
- Templates are **expanded** (shows final values)
- Secrets are **redacted** (shows `***REDACTED***`)
- Command shows **exact execution** (what would run)

---

## Implementation

### CLI Integration

```python
# src/jn/cli/run.py

@app.command()
def run(
    pipeline: str,
    jn: ConfigPathType = ConfigPath,
    param: Optional[List[str]] = None,
    env: Optional[List[str]] = None,
    unsafe_shell: bool = False,
    plan: bool = typer.Option(False, "--plan", help="Show execution plan without running"),
) -> None:
    """Execute a pipeline (or show plan with --plan)."""
    try:
        config.set_config_path(jn)
        params = config.parse_key_value_pairs(param or [])
        env_overrides = config.parse_key_value_pairs(env or [])

        if plan:
            # Generate plan instead of running
            plan_obj = config.explain_pipeline(
                pipeline,
                params=params,
                env=env_overrides,
                unsafe_shell=unsafe_shell,
                show_commands=True,
                show_env=True
            )
            # Output as JSON
            print(json.dumps(plan_obj.dict(), indent=2))
        else:
            # Normal execution
            output = config.run_pipeline(
                pipeline,
                params=params,
                env=env_overrides,
                unsafe_shell=unsafe_shell,
            )
            sys.stdout.buffer.write(output)

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
```

### Plan Generation

Extend `config/pipeline.py`:

```python
def explain_pipeline(
    pipeline_name: str,
    *,
    path: Optional[Path | str] = None,
    params: Optional[Dict[str, str]] = None,
    env: Optional[Dict[str, str]] = None,
    unsafe_shell: bool = False,
    show_commands: bool = False,
    show_env: bool = False,
) -> PipelinePlan:
    """Generate execution plan for a pipeline."""

    config_obj = ensure(path)
    pipeline = _lookup(config_obj.pipelines, pipeline_name, "pipeline")

    # Merge env with os.environ
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)

    # Build plan
    plan = PipelinePlan(
        apiVersion="jn/v1",
        kind="PipelinePlan",
        metadata={
            "name": pipeline_name,
            "created": datetime.utcnow().isoformat() + "Z"
        },
        spec={
            "source": _explain_source(pipeline.steps[0], config_obj, params, merged_env, show_commands),
            "converters": [
                _explain_converter(step, config_obj, show_commands)
                for step in pipeline.steps[1:-1]
            ],
            "target": _explain_target(pipeline.steps[-1], config_obj, params, merged_env, show_commands)
        }
    )

    if params:
        plan.params = params

    if show_env:
        # Redact secrets (anything with KEY, TOKEN, SECRET, PASSWORD in name)
        plan.env = _redact_env(merged_env)

    return plan


def _redact_env(env: Dict[str, str]) -> Dict[str, str]:
    """Redact secret-like environment variables."""
    redacted = {}
    SECRET_PATTERNS = ["KEY", "TOKEN", "SECRET", "PASSWORD", "PASS"]

    for key, value in env.items():
        if any(pattern in key.upper() for pattern in SECRET_PATTERNS):
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = value

    return redacted
```

---

## Use Cases

### 1. Debugging Pipeline

```bash
# See what commands will actually run
jn run etl-pipeline --plan

# Output shows:
# - Source: curl -sS -X GET 'https://...'
# - Converter: jq -c '.items[] | select(...)'
# - Target: curl -sS -X POST --data-binary @- 'https://...'
```

### 2. Validating Template Expansion

```bash
# Check that templates expanded correctly
jn run api-pipeline --param endpoint=users --env API_KEY=test --plan | jq '.spec.source.url'
# Output: "https://api.example.com/users"
```

### 3. CI/CD Config Validation

```yaml
# .github/workflows/validate.yml
- name: Validate JN configs
  run: |
    for pipeline in $(jn list pipelines); do
      jn run $pipeline --plan > /dev/null || exit 1
    done
```

### 4. Agent Introspection

```python
# Agent code
plan_json = subprocess.check_output([
    "jn", "run", "pipeline", "--plan"
])
plan = json.loads(plan_json)

# Inspect what will execute
if "https://production" in plan["spec"]["target"]["url"]:
    # Confirm before running production pipeline
    confirm = input("This will write to production. Continue? [y/N] ")
    if confirm.lower() != "y":
        sys.exit(0)

# Actually run it
subprocess.run(["jn", "run", "pipeline"])
```

### 5. Documentation Generation

```bash
# Generate docs for all pipelines
for pipeline in $(jn list pipelines); do
  jn run $pipeline --plan > docs/plans/$pipeline.json
done

# Then render as diagrams/tables
```

---

## Security Considerations

### Secret Redaction

**Problem:** Plans may contain sensitive data (API keys, tokens, passwords)

**Solution:** Redact environment variables matching patterns:

```python
SECRET_PATTERNS = [
    "KEY", "TOKEN", "SECRET", "PASSWORD",
    "PASS", "AUTH", "CREDENTIAL"
]
```

**Example:**
```json
{
  "env": {
    "API_KEY": "***REDACTED***",
    "DB_PASSWORD": "***REDACTED***",
    "HOME": "/home/user"
  }
}
```

### Opt-in Full Disclosure

Add `--show-secrets` flag for debugging (use with caution):

```bash
jn run pipeline --plan --show-secrets
# Shows actual values (use in secure contexts only)
```

---

## Output Modes

### JSON (Default)

```bash
jn run pipeline --plan
# Outputs valid JSON to stdout
```

**Use:** Agents, CI/CD, programmatic inspection

### Human-Readable (Optional)

```bash
jn run pipeline --plan --format text
```

**Output:**
```
Pipeline: etl-pipeline

Source: api-source (curl)
  Command: curl -sS -X GET 'https://api.example.com/data'
  Headers: Authorization: Bearer ***REDACTED***

Converter: filter-active (jq)
  Command: jq -c 'select(.active == true)'

Target: webhook (curl)
  Command: curl -sS -X POST --data-binary @- 'https://webhook.site/...'
  Headers: Content-Type: application/x-ndjson

Environment:
  API_KEY: ***REDACTED***
  WEBHOOK_URL: https://webhook.site/...
```

**Decision:** Start with JSON only, add text format if requested.

---

## Relationship to `jn explain`

### Current `jn explain` Behavior

```bash
jn explain pipeline
# Shows high-level plan (steps, names)

jn explain pipeline --show-commands
# Shows what commands would run

jn explain pipeline --show-env
# Shows environment variables
```

### With `--plan` Flag

```bash
jn run pipeline --plan
# Equivalent to: jn explain pipeline --show-commands --show-env --json
```

**Recommendation:** Keep both. `jn explain` is more flexible (custom output), `--plan` is standardized JSON.

---

## Error Handling

### Invalid Pipeline

```bash
$ jn run nonexistent --plan
Error: Pipeline not found: nonexistent
```

**Exit code:** 4 (not found)

### Missing Required Param

```bash
$ jn run pipeline --plan
Error: Missing required parameter: endpoint
Available params: endpoint, limit
Try: jn run pipeline --param endpoint=users --plan
```

**Exit code:** 1 (usage error)

### Template Expansion Error

```bash
$ jn run pipeline --plan
Error: Environment variable not found: API_KEY
Required by: source api-source, header Authorization
Try: export API_KEY=your_key
```

**Exit code:** 3 (connection/auth error)

---

## Testing Strategy

### Unit Tests

```python
def test_plan_mode_basic(runner, tmp_path):
    """Test --plan flag outputs JSON."""
    jn_path = tmp_path / "jn.json"
    init_config(runner, jn_path)

    # Create simple pipeline
    add_exec_source(runner, jn_path, "echo", ["echo", '{"x":1}'])
    add_converter(runner, jn_path, "pass", ".")
    add_exec_target(runner, jn_path, "cat", ["cat"])
    add_pipeline(runner, jn_path, "test", [
        "source:echo", "converter:pass", "target:cat"
    ])

    # Run with --plan
    result = runner.invoke(app, ["run", "test", "--plan", "--jn", str(jn_path)])

    assert result.exit_code == 0
    plan = json.loads(result.output)
    assert plan["kind"] == "PipelinePlan"
    assert plan["metadata"]["name"] == "test"
    assert plan["spec"]["source"]["name"] == "echo"

def test_plan_mode_redacts_secrets(runner, tmp_path):
    """Test that secrets are redacted in plan output."""
    jn_path = tmp_path / "jn.json"
    init_config(runner, jn_path)

    # Create pipeline with env var
    add_exec_source(runner, jn_path, "curl", [
        "curl", "-H", "Authorization: Bearer ${env.API_KEY}",
        "https://api.example.com"
    ])
    add_converter(runner, jn_path, "pass", ".")
    add_exec_target(runner, jn_path, "cat", ["cat"])
    add_pipeline(runner, jn_path, "api", [
        "source:curl", "converter:pass", "target:cat"
    ])

    # Run with --plan
    result = runner.invoke(app, [
        "run", "api",
        "--env", "API_KEY=secret123",
        "--plan",
        "--jn", str(jn_path)
    ])

    assert result.exit_code == 0
    plan = json.loads(result.output)
    assert plan["env"]["API_KEY"] == "***REDACTED***"
    assert "secret123" not in result.output
```

---

## Implementation Checklist

- [ ] Add `--plan` flag to `jn run` command
- [ ] Implement `explain_pipeline` with plan generation
- [ ] Add secret redaction for env vars
- [ ] Support template expansion in plan
- [ ] Add `apiVersion` and metadata to output
- [ ] Write unit tests for plan mode
- [ ] Write integration tests with secrets
- [ ] Document JSON schema for PipelinePlan
- [ ] Add to help text with examples

---

## Future Enhancements

### Plan Diff

```bash
# Show what changed between configs
jn run pipeline --plan > plan1.json
# Make config changes
jn run pipeline --plan > plan2.json
diff plan1.json plan2.json
```

### Plan Visualization

```bash
# Generate diagram from plan
jn run pipeline --plan | jn-viz > pipeline.svg
```

### Plan Validation

```bash
# Validate plan against schema
jn run pipeline --plan | jn validate-plan
```

---

## Summary

Plan mode provides **dry-run introspection** via `--plan` flag:

**Benefits:**
- Debug before executing
- Validate configs in CI/CD
- Agent inspection
- Documentation generation
- Template verification

**Output:** Machine-readable JSON with:
- Normalized execution plan
- Expanded templates
- Redacted secrets
- Full command-line equivalents

**Implementation:** Extend `explain_pipeline` to generate structured JSON output.

**Estimated effort:** 2-3 hours (mostly JSON formatting + tests)
