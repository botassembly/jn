# JN — Help System Architecture

**Status:** Design / Implementation Ready
**Updated:** 2025-11-08

---

## Purpose

Provide **actionable, example-driven help** for every JN command. Help should answer:

1. **What does this do?** - Clear purpose statement
2. **How do I use it?** - Syntax with placeholders
3. **Show me examples** - 3+ realistic use cases
4. **What can go wrong?** - Common errors with fixes

**Key principle:** Users should learn by example, not by reading abstractions.

---

## Design Philosophy

### Current Problem: Generic Help

Traditional CLI help is **prescriptive but not demonstrative**:

```bash
$ jn run --help
Usage: jn run PIPELINE [OPTIONS]

Options:
  --jn PATH         Config file path
  --param KEY=VAL   Set parameter
  --env KEY=VAL     Set environment variable
  --unsafe-shell    Allow shell execution
  --plan            Show execution plan
```

**Problem:** Users still don't know *what to actually type*.

### Solution: Example-First Help

**Every command shows 3 examples minimum:**

```bash
$ jn run --help
Usage: jn run PIPELINE [OPTIONS]

Run a configured pipeline and output results to stdout.

Examples:
  # Run a simple pipeline
  jn run my-pipeline

  # Run with parameters
  jn run api-fetch --param endpoint=users --param limit=100

  # Run with environment variable
  jn run secure-api --env API_KEY=sk_test_123

  # Show what would execute (dry-run)
  jn run etl-job --plan

  # Run with shell commands (use with caution)
  jn run shell-pipeline --unsafe-shell

Options:
  --jn PATH         Path to jn.json config (default: ./jn.json)
  --param KEY=VAL   Set pipeline parameter (repeatable)
  --env KEY=VAL     Override environment variable (repeatable)
  --unsafe-shell    Allow shell driver execution
  --plan            Output execution plan as JSON without running
  -h, --help        Show this help message

For more info: jn explain PIPELINE --show-commands
Exit codes: 0=success, 1=usage error, 3=connection error, 4=not found
```

**Benefits:**
- Users see **concrete commands** they can copy/paste
- Examples demonstrate **flag combinations**
- Context shows **when to use** each option

---

## Implementation Strategy

### Help Text Structure

**Every command follows this template:**

```
Usage: jn <command> <required-args> [OPTIONS]

<One-sentence purpose statement>

Examples:
  # <Use case 1: Basic usage>
  jn <command> <example-1>

  # <Use case 2: Common variation>
  jn <command> <example-2>

  # <Use case 3: Advanced feature>
  jn <command> <example-3>

Options:
  <flag>  <description> (default: <value>)
  ...

<Optional: Related commands or links>
Exit codes: <code>=<meaning>, ...
```

### Implementation: Typer Rich Help

Use Typer's `help` and `epilog` parameters:

```python
# src/jn/cli/run.py

@app.command(
    help="Run a configured pipeline and output results to stdout.",
    epilog="""
Examples:
  \b
  # Run a simple pipeline
  jn run my-pipeline

  \b
  # Run with parameters
  jn run api-fetch --param endpoint=users --param limit=100

  \b
  # Show what would execute (dry-run)
  jn run etl-job --plan

Exit codes: 0=success, 1=usage error, 3=connection error, 4=not found
    """.strip()
)
def run(
    pipeline: str = typer.Argument(..., help="Name of pipeline to execute"),
    jn: ConfigPathType = ConfigPath,
    param: Optional[List[str]] = typer.Option(
        None,
        "--param",
        help="Set pipeline parameter (format: KEY=VALUE, repeatable)"
    ),
    env: Optional[List[str]] = typer.Option(
        None,
        "--env",
        help="Override environment variable (format: KEY=VALUE, repeatable)"
    ),
    unsafe_shell: bool = typer.Option(
        False,
        "--unsafe-shell",
        help="Allow shell driver execution (use with caution)"
    ),
    plan: bool = typer.Option(
        False,
        "--plan",
        help="Output execution plan as JSON without running"
    ),
) -> None:
    # Implementation...
```

**Note:** `\b` prevents Typer from reflowing text (preserves formatting).

---

## Help Text for Each Command

### `jn run`

```bash
$ jn run --help
Usage: jn run PIPELINE [OPTIONS]

Run a configured pipeline and output results to stdout.

Examples:
  # Run a simple pipeline
  jn run my-pipeline

  # Run with parameters
  jn run api-fetch --param endpoint=users --param limit=100

  # Run with environment variable
  jn run secure-api --env API_KEY=sk_test_123

  # Show execution plan without running
  jn run etl-job --plan

Options:
  PIPELINE          Name of pipeline to execute (required)
  --jn PATH         Path to jn.json config (default: ./jn.json)
  --param KEY=VAL   Set pipeline parameter (repeatable)
  --env KEY=VAL     Override environment variable (repeatable)
  --unsafe-shell    Allow shell driver execution
  --plan            Output execution plan as JSON without running
  -h, --help        Show this help message

Related: jn explain PIPELINE, jn list pipelines
Exit codes: 0=success, 1=usage error, 3=connection error, 4=not found
```

### `jn new source`

```bash
$ jn new source --help
Usage: jn new source DRIVER NAME [OPTIONS]

Create a new data source in the config.

Examples:
  # Create exec source (safe, argv-based)
  jn new source exec my-source --argv echo --argv '{"x":1}'

  # Create curl source for API
  jn new source curl api-users \
    --url "https://api.example.com/users" \
    --header "Authorization: Bearer \${env.API_KEY}"

  # Create file source with CSV adapter
  jn new source file users-csv --path data/users.csv --adapter csv

  # Create shell source (requires --unsafe-shell)
  jn new source shell git-log --cmd "git log --oneline" --unsafe-shell

Options:
  DRIVER            Source driver: exec, curl, file, shell
  NAME              Unique name for this source
  --jn PATH         Path to jn.json config (default: ./jn.json)

  # Exec driver
  --argv ARG        Command argument (repeatable, required for exec)

  # Curl driver
  --url URL         HTTP endpoint (required for curl)
  --method METHOD   HTTP method (default: GET)
  --header H        HTTP header KEY:VALUE (repeatable)

  # File driver
  --path PATH       File path (required for file)
  --adapter NAME    Format adapter: csv, jc (optional)

  # Shell driver
  --cmd COMMAND     Shell command (required for shell)
  --unsafe-shell    Allow shell execution (required for shell)

Related: jn list sources, jn try source, jn explain PIPELINE
Exit codes: 0=success, 1=usage error, 2=validation error
```

### `jn new converter`

```bash
$ jn new converter --help
Usage: jn new converter NAME EXPRESSION [OPTIONS]

Create a new jq-based converter in the config.

Examples:
  # Simple field extraction
  jn new converter extract-name '.name'

  # Filter records
  jn new converter active-only 'select(.status == "active")'

  # Transform structure
  jn new converter flatten '.items[] | {id, name, email:.contact.email}'

  # Load from file
  jn new converter complex-transform --file transforms/process.jq

Options:
  NAME              Unique name for this converter
  EXPRESSION        jq expression to apply (or use --file)
  --jn PATH         Path to jn.json config (default: ./jn.json)
  --file PATH       Load jq expression from file (alternative to EXPRESSION)
  --raw             Output raw strings instead of JSON (jq -r flag)

Related: jn list converters, jn try converter
Exit codes: 0=success, 1=usage error, 2=validation error
```

### `jn new target`

```bash
$ jn new target --help
Usage: jn new target DRIVER NAME [OPTIONS]

Create a new data target in the config.

Examples:
  # Write to stdout
  jn new target exec stdout --argv cat

  # POST to webhook
  jn new target curl webhook \
    --method POST \
    --url "https://webhook.site/..." \
    --header "Content-Type: application/x-ndjson"

  # Write to file
  jn new target file output --path results/data.ndjson

  # Process with shell utility
  jn new target shell sorter --cmd "sort -r" --unsafe-shell

Options:
  DRIVER            Target driver: exec, curl, file, shell
  NAME              Unique name for this target
  --jn PATH         Path to jn.json config (default: ./jn.json)

  # Exec driver
  --argv ARG        Command argument (repeatable, required for exec)

  # Curl driver
  --url URL         HTTP endpoint (required for curl)
  --method METHOD   HTTP method (default: POST)
  --header H        HTTP header KEY:VALUE (repeatable)

  # File driver
  --path PATH       File path (required for file)

  # Shell driver
  --cmd COMMAND     Shell command (required for shell)
  --unsafe-shell    Allow shell execution (required for shell)

Related: jn list targets, jn try target
Exit codes: 0=success, 1=usage error, 2=validation error
```

### `jn new pipeline`

```bash
$ jn new pipeline --help
Usage: jn new pipeline NAME --source S [--converter C ...] --target T

Create a new pipeline from existing components.

Examples:
  # Simple source → target
  jn new pipeline basic --source api --target stdout

  # With single converter
  jn new pipeline filtered \
    --source api \
    --converter filter-active \
    --target webhook

  # Multi-stage pipeline
  jn new pipeline etl \
    --source db \
    --converter extract \
    --converter transform \
    --converter validate \
    --target storage

Options:
  NAME              Unique name for this pipeline
  --source NAME     Source component (required)
  --converter NAME  Converter component (repeatable, optional)
  --target NAME     Target component (required)
  --jn PATH         Path to jn.json config (default: ./jn.json)

Related: jn run PIPELINE, jn explain PIPELINE, jn list pipelines
Exit codes: 0=success, 1=usage error, 2=validation error, 4=component not found
```

### `jn list`

```bash
$ jn list --help
Usage: jn list [COMPONENT_TYPE]

List configured components.

Examples:
  # List all components
  jn list

  # List only sources
  jn list sources

  # List pipelines
  jn list pipelines

  # List converters
  jn list converters

Options:
  COMPONENT_TYPE    Filter by type: sources, converters, targets, pipelines
  --jn PATH         Path to jn.json config (default: ./jn.json)
  --json            Output as JSON (default: human-readable table)

Exit codes: 0=success, 1=usage error
```

### `jn explain`

```bash
$ jn explain --help
Usage: jn explain PIPELINE [OPTIONS]

Show detailed execution plan for a pipeline.

Examples:
  # Show high-level plan
  jn explain my-pipeline

  # Show actual commands that would run
  jn explain my-pipeline --show-commands

  # Show environment variables
  jn explain my-pipeline --show-env

  # Show everything (commands + env)
  jn explain etl-job --show-commands --show-env

Options:
  PIPELINE          Name of pipeline to explain
  --jn PATH         Path to jn.json config (default: ./jn.json)
  --show-commands   Display actual command-line invocations
  --show-env        Display environment variables (secrets redacted)
  --param KEY=VAL   Set parameter for template expansion (repeatable)
  --env KEY=VAL     Override environment variable (repeatable)

Related: jn run PIPELINE --plan (for JSON output)
Exit codes: 0=success, 1=usage error, 4=pipeline not found
```

### `jn try source`

```bash
$ jn try source --help
Usage: jn try source --driver DRIVER [OPTIONS]

Test a source without saving to config.

Examples:
  # Try curl API request
  jn try source --driver curl --url "https://api.github.com/users/octocat"

  # Try exec command
  jn try source --driver exec --argv echo --argv '{"test":"data"}'

  # Try file with CSV adapter
  jn try source --driver file --path data.csv --adapter csv

  # Try shell command
  jn try source --driver shell --cmd "ls -la | head" --unsafe-shell

Options:
  --driver NAME     Source driver: exec, curl, file, shell (required)

  # Exec driver
  --argv ARG        Command argument (repeatable)

  # Curl driver
  --url URL         HTTP endpoint
  --method METHOD   HTTP method (default: GET)
  --header H        HTTP header KEY:VALUE (repeatable)

  # File driver
  --path PATH       File path
  --adapter NAME    Format adapter: csv, jc

  # Shell driver
  --cmd COMMAND     Shell command
  --unsafe-shell    Allow shell execution

When it works, save with: jn new source DRIVER NAME [same-options]
Exit codes: 0=success, 1=usage error, 3=connection error
```

### `jn try converter`

```bash
$ jn try converter --help
Usage: jn try converter (--expr JQ | --file PATH)

Test a jq converter on stdin without saving to config.

Examples:
  # Test field extraction
  echo '{"x":1,"y":2}' | jn try converter --expr '.x'

  # Test filter
  cat data.ndjson | jn try converter --expr 'select(.status == "ok")'

  # Test transform from file
  cat data.ndjson | jn try converter --file transform.jq

Options:
  --expr JQ         jq expression to apply
  --file PATH       Load jq expression from file
  --raw             Output raw strings (jq -r flag)

When it works, save with: jn new converter NAME EXPRESSION
Exit codes: 0=success, 1=usage error, 2=jq syntax error
```

### `jn try target`

```bash
$ jn try target --help
Usage: jn try target --driver DRIVER [OPTIONS]

Test a target (reads from stdin) without saving to config.

Examples:
  # Test webhook POST
  echo '{"test":"data"}' | jn try target --driver curl \
    --method POST --url "https://httpbin.org/post"

  # Test file write
  echo '{"test":"data"}' | jn try target --driver file --path /tmp/out.json

  # Test shell utility
  cat data.ndjson | jn try target --driver shell --cmd "sort -r" --unsafe-shell

Options:
  --driver NAME     Target driver: exec, curl, file, shell (required)

  # Exec driver
  --argv ARG        Command argument (repeatable)

  # Curl driver
  --url URL         HTTP endpoint
  --method METHOD   HTTP method (default: POST)
  --header H        HTTP header KEY:VALUE (repeatable)

  # File driver
  --path PATH       File path

  # Shell driver
  --cmd COMMAND     Shell command
  --unsafe-shell    Allow shell execution

When it works, save with: jn new target DRIVER NAME [same-options]
Exit codes: 0=success, 1=usage error, 3=connection error
```

### `jn shape`

```bash
$ jn shape --help
Usage: jn shape (--in PATH | --source NAME) [OPTIONS]

Analyze data structure and generate profile/preview/schema.

Examples:
  # Analyze file and output all artifacts
  jn shape --in data/users.ndjson

  # Analyze with specific outputs
  jn shape --in data.json \
    --profile profile.json \
    --preview preview.json \
    --schema schema.json

  # Analyze configured source
  jn shape --source api-users --preview preview.json

  # Validate against schema
  cat new-data.ndjson | jn shape --validate schema.json

Options:
  --in PATH         Input file or URL to analyze
  --source NAME     Analyze configured source
  --profile PATH    Output profile (statistics) as JSON
  --preview PATH    Output shallow preview (truncated samples)
  --schema PATH     Output JSON Schema
  --truncate N      Truncate strings to N chars (default: 24)
  --depth N         Max object depth (default: 3)
  --records N       Process only first N records
  --validate PATH   Validate input against JSON Schema file
  --jn PATH         Path to jn.json config (default: ./jn.json)

Exit codes: 0=success, 1=usage error, 2=validation failed
```

### `jn init`

```bash
$ jn init --help
Usage: jn init [PATH]

Create a new jn.json configuration file.

Examples:
  # Create in current directory
  jn init

  # Create in specific location
  jn init /path/to/project/jn.json

  # Create and start adding components
  jn init && jn new source exec hello --argv echo --argv '{"msg":"Hello"}'

Options:
  PATH              Config file path (default: ./jn.json)
  --force           Overwrite existing file

Exit codes: 0=success, 1=file exists (use --force), 2=write error
```

---

## Error Message Improvements

### Prescriptive Error Messages

**Bad (current):**
```
Error: Pipeline not found: my-pipeline
```

**Good (prescriptive):**
```
Error: Pipeline 'my-pipeline' not found

Available pipelines:
  - etl-job
  - api-sync
  - data-export

Try: jn list pipelines
Try: jn new pipeline my-pipeline --source ... --target ...
```

### Implementation Pattern

```python
def lookup_pipeline(config: Config, name: str) -> Pipeline:
    """Lookup pipeline by name with prescriptive error."""
    try:
        return next(p for p in config.pipelines if p.name == name)
    except StopIteration:
        # Build prescriptive error message
        available = [p.name for p in config.pipelines]

        if available:
            msg = f"Pipeline '{name}' not found\n\n"
            msg += "Available pipelines:\n"
            for p in available:
                msg += f"  - {p}\n"
            msg += "\nTry: jn list pipelines"
        else:
            msg = f"Pipeline '{name}' not found\n\n"
            msg += "No pipelines configured yet.\n"
            msg += f"Try: jn new pipeline {name} --source ... --target ..."

        raise JNError(msg, exit_code=4)
```

---

## Testing Strategy

### Help Text Tests

```python
def test_help_has_examples(runner):
    """Every command should have at least 3 examples."""
    commands = ["run", "new source", "list", "explain", "try source"]

    for cmd in commands:
        result = runner.invoke(app, cmd.split() + ["--help"])
        assert result.exit_code == 0

        # Check for "Examples:" section
        assert "Examples:" in result.output

        # Count example lines (start with '#' comment)
        examples = [line for line in result.output.split("\n") if line.strip().startswith("# ")]
        assert len(examples) >= 3, f"{cmd} needs at least 3 examples"

def test_help_has_exit_codes(runner):
    """Every command should document exit codes."""
    commands = ["run", "new source", "list", "explain"]

    for cmd in commands:
        result = runner.invoke(app, cmd.split() + ["--help"])
        assert "Exit codes:" in result.output

def test_prescriptive_error_not_found(runner, tmp_path):
    """Test prescriptive error when pipeline not found."""
    jn_path = tmp_path / "jn.json"
    init_config(runner, jn_path)

    result = runner.invoke(app, ["run", "nonexistent", "--jn", str(jn_path)])

    assert result.exit_code == 4
    assert "not found" in result.output.lower()
    assert "Try:" in result.output  # Prescriptive suggestion
```

---

## Implementation Checklist

- [ ] Update all command help text with 3+ examples
- [ ] Add exit code documentation to epilog
- [ ] Implement prescriptive error messages for:
  - [ ] Pipeline not found
  - [ ] Source not found
  - [ ] Converter not found
  - [ ] Target not found
  - [ ] Missing required flag (e.g., --url for curl)
  - [ ] Invalid parameter format
  - [ ] Missing environment variable
- [ ] Add "Related commands" to help text
- [ ] Write tests for help text coverage
- [ ] Write tests for prescriptive errors
- [ ] Update README with help examples

---

## Future Enhancements

### Interactive Help

```bash
# Guided help for beginners
jn help
# Prompts: "What do you want to do?"
# 1. Create a new pipeline
# 2. Run an existing pipeline
# 3. List configured components
```

### Command-Specific Tutorials

```bash
jn tutorial pipeline
# Step-by-step guide:
# Step 1: Create a source...
# Step 2: Add a converter...
# Step 3: Define a target...
```

### Man Pages

```bash
man jn-run
# Traditional Unix man page format
```

---

## Summary

**Help system principles:**

1. **Example-first**: Show 3+ concrete examples per command
2. **Prescriptive errors**: Tell users exactly how to fix problems
3. **Related commands**: Point to next logical steps
4. **Exit codes**: Document success/failure meanings
5. **Copy-pastable**: Users should be able to modify examples directly

**Implementation:** Use Typer's `help` and `epilog` parameters with `\b` formatting.

**Estimated effort:** 3-4 hours (update all commands + tests)
