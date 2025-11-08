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

### CLI Flags (Only Method)

```bash
jn run pipeline.json \
  --input-file data.csv \
  --min-amount 500 \
  --output-file result.json
```

**Flag naming**: Convert argument name to kebab-case
- `input_file` → `--input-file`
- `minAmount` → `--min-amount`

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

**That's it** - no complex validation rules. Keep it simple.

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
        # Just ensure it's a string - don't validate existence
        value = str(value)

    return value
```

### CLI Argument Parsing

```python
import typer

def run(
    config_path: Path,
    **kwargs  # Capture all --name value pairs
):
    # Load config
    config = json.loads(config_path.read_text())

    # Validate arguments
    validated_args = validate_arguments(kwargs, config.get('arguments', {}))

    # Substitute variables
    final_config = substitute_variables(config, validated_args)

    # Run pipeline
    run_pipeline(final_config)
```

## Config Schema Extension

Add `arguments` as optional top-level key in pipeline JSON:

```json
{
  "arguments": {
    "arg_name": {
      "type": "string|number|boolean|path",
      "required": true|false,
      "default": <value>,
      "description": "Help text"
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

## Testing Strategy

### Unit Tests
- Variable substitution (simple cases, nested, edge cases)
- Type validation (each type)
- Default values
- Error messages

### Integration Tests
- Run pipeline with arguments
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

def test_number_type_validation():
    spec = {"type": "number"}
    with pytest.raises(ValueError, match="must be a number"):
        validate_argument("threshold", "abc", spec)
```

## Future Enhancements

**Phase 2** (not in initial implementation):
- Environment variables (`JN_ARG_INPUT_FILE`)
- JSON file input (`--args args.json`)
- Stdin for chaining (`--args-stdin`)
- Advanced validation (min/max, enum, file existence checks)

## Success Criteria

- [x] Can declare arguments in JSON config
- [x] Can pass arguments via CLI flags
- [x] Variable substitution works in all config fields
- [x] Type validation works for all types (string, number, boolean, path)
- [x] Required arguments enforced
- [x] Clear error messages for common mistakes
- [x] Help text auto-generated from argument definitions
- [x] Backward compatible (configs without arguments still work)
- [x] Test coverage >85%
- [x] Documentation with examples
