# Pipeline Arguments

## Overview

Add argument support to JN pipelines, allowing configs to be parameterized and reused with different inputs. This enables pipelines to be triggered by external orchestration tools (watchdog, cron, Airflow) with runtime parameters.

## The Problem

Current pipelines have hardcoded paths:

```json
{
  "source": {
    "driver": "file",
    "path": "data/sales.csv",
    "parser": "csv"
  },
  "converter": {
    "query": "select(.amount > 100)"
  },
  "target": {
    "driver": "file",
    "path": "output/filtered.json",
    "format": "json"
  }
}
```

This means:
- Need separate config for each input file
- Can't be triggered by external tools with dynamic inputs
- Can't reuse logic across different datasets

## The Solution: Variable Substitution

Declare arguments and use `${variable}` syntax for substitution.

### Config with Arguments

```json
{
  "arguments": {
    "input_file": {
      "type": "path",
      "required": true,
      "description": "Path to input CSV file"
    },
    "min_amount": {
      "type": "number",
      "default": 100
    },
    "output_file": {
      "type": "path",
      "required": true
    }
  },
  "source": {
    "driver": "file",
    "path": "${input_file}",
    "parser": "csv"
  },
  "converter": {
    "query": "select(.amount >= ${min_amount})"
  },
  "target": {
    "driver": "file",
    "path": "${output_file}",
    "format": "json"
  }
}
```

### Running with Arguments

```bash
# Via CLI flags
jn run pipeline.json \
  --input-file data/sales.csv \
  --min-amount 500 \
  --output-file output/high-value.json

# Short form with positional args (if defined in config)
jn run pipeline.json data/sales.csv output/high-value.json
```

## Argument Types

Keep it simple - just 4 types:

### `path`
File or directory path.

```json
{
  "input_file": {
    "type": "path",
    "required": true,
    "description": "Input CSV file"
  }
}
```

Optional validation:
```json
{
  "input_file": {
    "type": "path",
    "required": true,
    "must_exist": true  // Validate file exists before running
  }
}
```

### `string`
Text value.

```json
{
  "category": {
    "type": "string",
    "default": "all",
    "description": "Category to filter"
  }
}
```

Optional constraints:
```json
{
  "mode": {
    "type": "string",
    "default": "append",
    "enum": ["append", "overwrite", "skip"]  // Limited choices
  }
}
```

### `number`
Integer or float.

```json
{
  "threshold": {
    "type": "number",
    "default": 100,
    "description": "Minimum value threshold"
  }
}
```

Optional constraints:
```json
{
  "threshold": {
    "type": "number",
    "default": 100,
    "min": 0,
    "max": 1000
  }
}
```

### `boolean`
True/false flag.

```json
{
  "include_header": {
    "type": "boolean",
    "default": true,
    "description": "Include header row in output"
  }
}
```

Usage:
```bash
jn run pipeline.json --include-header        # true
jn run pipeline.json --no-include-header     # false
```

## Variable Substitution

Use `${variable_name}` anywhere in the config:

### In Paths
```json
{
  "source": {
    "path": "${input_dir}/${input_file}"
  },
  "target": {
    "path": "${output_dir}/${output_file}"
  }
}
```

### In Query Strings
```json
{
  "converter": {
    "query": "select(.${filter_field} >= ${filter_value})"
  }
}
```

### In Options
```json
{
  "source": {
    "parser": "${input_format}",
    "options": {
      "delimiter": "${delimiter}"
    }
  }
}
```

## Passing Arguments

### Method 1: CLI Flags (Primary)

```bash
jn run pipeline.json \
  --input-file data.csv \
  --min-amount 500 \
  --output-file result.json
```

**Flag naming**: Convert argument name to kebab-case
- `input_file` → `--input-file`
- `minAmount` → `--min-amount`

### Method 2: Environment Variables

```bash
export INPUT_FILE=data.csv
export MIN_AMOUNT=500
jn run pipeline.json
```

**Variable naming**: Convert to UPPER_SNAKE_CASE
- `input_file` → `INPUT_FILE`
- `minAmount` → `MIN_AMOUNT`

Prefix with `JN_ARG_` to avoid conflicts:
```bash
export JN_ARG_INPUT_FILE=data.csv
```

### Method 3: JSON File

```bash
# args.json
{
  "input_file": "data.csv",
  "min_amount": 500,
  "output_file": "result.json"
}

jn run pipeline.json --args args.json
```

### Method 4: Stdin (for chaining)

```bash
# Generate args dynamically
jq -n '{input_file: "data.csv", min_amount: 500}' | \
  jn run pipeline.json --args-stdin
```

**Priority** (highest to lowest):
1. CLI flags
2. JSON file (--args)
3. Environment variables
4. Default values in config

## Validation

Validation happens **before** pipeline runs:

### Type Checking
```json
{"threshold": {"type": "number"}}
```

```bash
jn run pipeline.json --threshold abc
# Error: Argument 'threshold' must be a number, got 'abc'
```

### Required Arguments
```json
{"input_file": {"required": true}}
```

```bash
jn run pipeline.json
# Error: Required argument 'input_file' not provided
```

### File Existence
```json
{"input_file": {"type": "path", "must_exist": true}}
```

```bash
jn run pipeline.json --input-file missing.csv
# Error: File 'missing.csv' does not exist
```

### Range Validation
```json
{"threshold": {"type": "number", "min": 0, "max": 1000}}
```

```bash
jn run pipeline.json --threshold 5000
# Error: Argument 'threshold' must be between 0 and 1000, got 5000
```

### Enum Validation
```json
{"mode": {"type": "string", "enum": ["append", "overwrite"]}}
```

```bash
jn run pipeline.json --mode delete
# Error: Argument 'mode' must be one of: append, overwrite
```

## Help Text

Arguments automatically generate help:

```bash
jn run pipeline.json --help
```

Output:
```
Usage: jn run pipeline.json [OPTIONS]

Arguments:
  --input-file PATH      Path to input CSV file (required)
  --min-amount NUMBER    Minimum value threshold (default: 100)
  --output-file PATH     Output file path (required)

Examples:
  jn run pipeline.json --input-file data.csv --output-file out.json
  jn run pipeline.json --input-file data.csv --min-amount 500 --output-file out.json
```

Help text comes from `description` field in argument definition.

## Use Cases

### Use Case 1: External Watchdog

```bash
# watchdog watches ./inbox/ for new files
# When file appears, runs:
watchmedo shell-command \
  --patterns="*.csv" \
  --recursive \
  --command='jn run process.json --input-file ${watch_src_path}' \
  ./inbox/
```

### Use Case 2: Batch Processing

```bash
# Process all CSV files in a folder
for file in ./data/*.csv; do
  jn run pipeline.json \
    --input-file "$file" \
    --output-file "./output/$(basename $file .csv).json"
done
```

### Use Case 3: Cron Job

```bash
# crontab entry
0 2 * * * jn run daily-report.json --date $(date +\%Y-\%m-\%d)
```

### Use Case 4: Airflow DAG

```python
from airflow import DAG
from airflow.operators.bash import BashOperator

task = BashOperator(
    task_id='process_data',
    bash_command='jn run pipeline.json --input-file {{ ds }}.csv'
)
```

### Use Case 5: CI/CD Pipeline

```yaml
# .github/workflows/process.yml
- name: Process data
  run: |
    jn run pipeline.json \
      --input-file ${{ github.workspace }}/data.csv \
      --output-file ${{ github.workspace }}/result.json
```

## Integration with Existing Commands

### cat/head/tail with Arguments?

**Decision**: Arguments are **pipeline-only**, not for cat/head/tail.

**Reason**: cat/head/tail are ad-hoc exploration tools. Pipelines are repeatable workflows.

```bash
# This doesn't make sense - just pass the value directly
jn cat ${input_file}  # NO

# This makes sense - parameterized workflow
jn run pipeline.json --input-file data.csv  # YES
```

### Following Files with Arguments

If we add `jn follow`, it doesn't need arguments:

```bash
# Follow directly
jn follow access.log

# External tool can trigger pipeline when log updates
watchmedo shell-command \
  --patterns="access.log" \
  --command='jn run process-logs.json --log-file ${watch_src_path}' \
  /var/log/
```

## Implementation Notes

### Substitution Engine

Simple string replacement:

```python
import re

def substitute_variables(config, args):
    config_str = json.dumps(config)

    for name, value in args.items():
        pattern = r'\$\{' + re.escape(name) + r'\}'
        config_str = re.sub(pattern, str(value), config_str)

    # Check for unsubstituted variables
    remaining = re.findall(r'\$\{(\w+)\}', config_str)
    if remaining:
        raise ValueError(f"Missing arguments: {', '.join(remaining)}")

    return json.loads(config_str)
```

### Validation

```python
def validate_argument(name, value, spec):
    arg_type = spec.get('type', 'string')

    # Type checking
    if arg_type == 'number':
        try:
            value = float(value)
        except ValueError:
            raise ValueError(f"Argument '{name}' must be a number")

    elif arg_type == 'boolean':
        if isinstance(value, str):
            value = value.lower() in ('true', '1', 'yes')

    elif arg_type == 'path':
        if spec.get('must_exist') and not os.path.exists(value):
            raise ValueError(f"File '{value}' does not exist")

    # Range validation
    if 'min' in spec and value < spec['min']:
        raise ValueError(f"Argument '{name}' must be >= {spec['min']}")

    if 'max' in spec and value > spec['max']:
        raise ValueError(f"Argument '{name}' must be <= {spec['max']}")

    # Enum validation
    if 'enum' in spec and value not in spec['enum']:
        raise ValueError(f"Argument '{name}' must be one of: {', '.join(spec['enum'])}")

    return value
```

### CLI Argument Parsing

```python
import typer

def run(
    config_path: Path,
    args_file: Optional[Path] = None,
    args_stdin: bool = False,
    **kwargs  # Capture all --name value pairs
):
    # Load config
    config = json.loads(config_path.read_text())

    # Collect arguments from various sources
    args = {}

    # 1. Environment variables
    for name in config.get('arguments', {}):
        env_var = f"JN_ARG_{name.upper()}"
        if env_var in os.environ:
            args[name] = os.environ[env_var]

    # 2. Args file
    if args_file:
        args.update(json.loads(args_file.read_text()))

    # 3. Stdin
    if args_stdin:
        args.update(json.loads(sys.stdin.read()))

    # 4. CLI flags (highest priority)
    args.update(kwargs)

    # Validate and substitute
    validated_args = validate_arguments(args, config['arguments'])
    final_config = substitute_variables(config, validated_args)

    # Run pipeline
    run_pipeline(final_config)
```

## Config Schema Extension

Add `arguments` as optional top-level key in `jn.json`:

```json
{
  "arguments": {
    "arg_name": {
      "type": "string|number|boolean|path",
      "required": true|false,
      "default": <value>,
      "description": "Help text",
      "must_exist": true|false,  // For path type
      "min": <number>,           // For number type
      "max": <number>,           // For number type
      "enum": [<values>]         // For string type
    }
  },
  "source": { ... },
  "converter": { ... },
  "target": { ... }
}
```

Backward compatible - if `arguments` is missing, config works as before.

## Error Messages

Clear, actionable errors:

```bash
# Missing required argument
$ jn run pipeline.json
Error: Required argument 'input_file' not provided

Try:
  jn run pipeline.json --input-file <path>

Or run with --help for more information.
```

```bash
# Type mismatch
$ jn run pipeline.json --threshold abc
Error: Argument 'threshold' must be a number, got 'abc'

Expected:
  --threshold 100
```

```bash
# File not found
$ jn run pipeline.json --input-file missing.csv
Error: File 'missing.csv' does not exist

Argument 'input_file' requires an existing file.
```

## Testing Strategy

### Unit Tests
- Variable substitution (simple cases, nested, edge cases)
- Type validation (each type)
- Range validation
- Enum validation
- Default values
- Error messages

### Integration Tests
- Run pipeline with arguments
- Multiple argument sources (flags, env, file)
- Priority resolution
- Missing required arguments
- Invalid arguments
- Help text generation

### Example Test Cases

```python
def test_substitute_variables():
    config = {"path": "${input_file}"}
    args = {"input_file": "data.csv"}
    result = substitute_variables(config, args)
    assert result == {"path": "data.csv"}

def test_missing_required_argument():
    config = {"arguments": {"input_file": {"required": true}}}
    with pytest.raises(ValueError, match="Required argument"):
        validate_arguments({}, config['arguments'])

def test_number_range_validation():
    spec = {"type": "number", "min": 0, "max": 100}
    with pytest.raises(ValueError, match="must be <= 100"):
        validate_argument("threshold", 500, spec)
```

## Future Enhancements

**Phase 2** (not in initial implementation):
- Argument templates (reusable argument sets)
- Computed defaults (`"default": "${other_arg}.json"`)
- Secret arguments (don't log values, read from vault)
- Array arguments (`--tags value1 value2 value3`)
- Conditional arguments (show arg2 only if arg1 is set)

## Comparison to Other Tools

### Airflow
Uses Jinja templating in config. More complex but more powerful.

### dbt
Uses Jinja + YAML. Complex syntax, steep learning curve.

### JN Arguments
Simple string substitution, JSON config, easy to understand. Good enough for 90% of use cases.

## Success Criteria

- [x] Can declare arguments in JSON config
- [x] Can pass arguments via CLI flags
- [x] Can pass arguments via environment variables
- [x] Can pass arguments via JSON file
- [x] Variable substitution works in all config fields
- [x] Type validation works for all types
- [x] Required arguments enforced
- [x] Clear error messages for common mistakes
- [x] Help text auto-generated from argument definitions
- [x] Backward compatible (configs without arguments still work)
- [x] Test coverage >85%
- [x] Documentation with examples
