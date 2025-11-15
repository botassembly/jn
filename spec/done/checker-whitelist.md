# Checker Whitelist Support

## Overview

The JN checker supports whitelisting violations that have legitimate architectural justifications. This prevents false positives while maintaining strict checking for the general codebase.

## Whitelist Mechanisms

### 1. Project-Level Config (`.jncheck.toml`)

Place a `.jncheck.toml` file in the project root:

```toml
# XLSX Plugin: ZIP archives require complete file buffering
[[whitelist]]
file = "jn_home/plugins/formats/xlsx_.py"
rule = "stdin_buffer_read"
lines = [38]
reason = "ZIP archives require complete file access (central directory at EOF)"

# CLI Commands: Legitimate use of sys.exit()
[[whitelist]]
file = "src/jn/cli/commands/*.py"
rule = "sys_exit_in_function"
reason = "CLI command functions legitimately use sys.exit() for process exit codes"
```

**Fields:**
- `file`: Glob pattern or specific file path (relative to project root)
- `rule`: Rule name to whitelist (or `"*"` for all rules)
- `lines`: Optional list of specific line numbers (omit to whitelist entire file)
- `reason`: Justification (required for documentation)

**Pattern Matching:**
- Supports glob patterns: `*.py`, `**/*.py`, `src/*/commands/*.py`
- Works with both absolute and relative paths
- Basename matching: `xlsx_.py` matches anywhere

### 2. Inline Comments

Add `# jn:ignore` comments directly in code:

```python
# Ignore all rules on this line
xlsx_data = sys.stdin.buffer.read()  # jn:ignore: ZIP format requires buffering

# Ignore specific rule
sys.exit(1)  # jn:ignore[sys_exit_in_function]: CLI error handling

# Ignore multiple rules
proc.wait()  # jn:ignore[missing_wait,missing_stdout_close]
```

**Formats:**
- `# jn:ignore` - Ignore all rules
- `# jn:ignore[rule_name]` - Ignore specific rule
- `# jn:ignore[rule1,rule2]` - Ignore multiple rules
- `# jn:ignore: reason` - Optional reason

## Legitimate Exemptions

### Binary Format Buffering

**Problem:** Some file formats cannot be streamed due to internal structure.

**Examples:**
- **XLSX**: ZIP archives with central directory at EOF
- **PDF**: Cross-reference table at EOF
- **Parquet**: Columnar format with footer metadata
- **ZIP/GZ**: Compression requires full context

**Solution:**
```toml
[[whitelist]]
file = "jn_home/plugins/formats/xlsx_.py"
rule = "stdin_buffer_read"
lines = [38]
reason = "ZIP archives require complete file access (no streaming alternative exists)"
```

**Code:**
```python
def reads(config=None):
    # ZIP format requires complete file (central directory at EOF)
    xlsx_data = sys.stdin.buffer.read()  # jn:ignore[stdin_buffer_read]: ZIP format
    workbook = openpyxl.load_workbook(io.BytesIO(xlsx_data))
    # ... stream output as NDJSON
```

### CLI Command Exit Codes

**Problem:** CLI commands need to exit with proper error codes.

**Solution:**
```toml
[[whitelist]]
file = "src/jn/cli/commands/*.py"
rule = "sys_exit_in_function"
reason = "CLI command functions legitimately use sys.exit() for process exit codes"
```

**Code:**
```python
@click.command()
def cat(ctx, source):
    try:
        # ... process data
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)  # Legitimate CLI exit
```

### Stdout Consumed Directly

**Problem:** Checker warns about missing `stdout.close()` when stdout is consumed directly.

**Distinction:**
- **Piping to another process**: MUST call `stdout.close()` for SIGPIPE
- **Consuming directly**: No `.close()` needed (false positive)

**Solution:**
```toml
[[whitelist]]
file = "src/jn/core/pipeline.py"
rule = "missing_stdout_close"
lines = [522]
reason = "Stdout consumed directly via 'for line in proc.stdout' (not piped)"
```

**Code:**
```python
# Pattern 1: Piping (MUST close stdout)
reader = subprocess.Popen(..., stdout=PIPE)
writer = subprocess.Popen(..., stdin=reader.stdout)
reader.stdout.close()  # ✅ Required for SIGPIPE
writer.wait()

# Pattern 2: Consuming directly (no close needed)
proc = subprocess.Popen(..., stdout=PIPE)
for line in proc.stdout:  # ✅ Consuming directly
    output_stream.write(line)
proc.wait()
```

## Implementation Details

### Whitelist Loading

1. Search for `.jncheck.toml` in current directory and parents
2. Parse TOML entries into `WhitelistEntry` objects
3. Compile patterns for efficient matching
4. Cache loaded whitelist for multiple file checks

### Violation Filtering

```python
# In checker/__init__.py
whitelist = Whitelist()  # Auto-loads .jncheck.toml
whitelist.parse_inline_ignores(file_path, source)

# Run all checks
violations = run_all_checks(tree)

# Filter whitelisted violations
filtered = [
    v for v in violations
    if not whitelist.is_whitelisted(file_path, v.rule, v.line)
]
```

### Pattern Matching Algorithm

1. **Direct match**: `/full/path/file.py` == pattern
2. **Suffix match**: Extract relative path from absolute path
3. **Glob expansion**: `*` matches any chars, `**` matches directories
4. **Basename match**: `file.py` matches anywhere

Example:
```python
# Absolute path: /home/user/jn/src/jn/cli/commands/cat.py
# Pattern: src/jn/cli/commands/*.py
# Match: Extract suffix "src/jn/cli/commands/cat.py" → fnmatch → True
```

## Usage Examples

### Check with Whitelist

```bash
# Whitelist automatically loaded from .jncheck.toml
jn check plugins
jn check core
jn check all

# Results show whitelisted violations are not reported
# 34 files | ✅ 34 passed
```

### Verify Whitelist Working

```python
# Test script
from jn.checker.whitelist import Whitelist

wl = Whitelist()
is_whitelisted = wl.is_whitelisted(
    "src/jn/cli/commands/cat.py",
    "sys_exit_in_function",
    27
)
print(f"Whitelisted: {is_whitelisted}")  # True

reason = wl.get_reason("src/jn/cli/commands/cat.py", "sys_exit_in_function", 27)
print(f"Reason: {reason}")  # "CLI command functions legitimately..."
```

## Best Practices

### When to Whitelist

✅ **Legitimate exemptions:**
- Binary formats that require buffering (ZIP, PDF, Parquet)
- CLI commands using `sys.exit()` for error codes
- Framework code that legitimately breaks plugin rules

❌ **Don't whitelist:**
- Lazy fixes ("I don't want to fix this")
- Unclear justifications
- Violations in plugin `reads`/`writes` functions

### Documentation Requirements

Every whitelist entry MUST have a `reason` field explaining:
1. **Why** the violation is necessary
2. **What** architectural constraint requires it
3. **Reference** to docs or specs if applicable

### Inline vs Config

**Use inline comments (`# jn:ignore`) when:**
- Single-line exemption
- Code is self-documenting
- Temporary exception

**Use config file (`.jncheck.toml`) when:**
- Multiple lines or files
- Systematic pattern (e.g., all CLI commands)
- Permanent architectural decision
- Needs detailed explanation

## Future Enhancements

### Auto-Fix Mode

```bash
jn check --fix  # Automatically apply suggested fixes
```

### Expiring Whitelists

```toml
[[whitelist]]
file = "temp_plugin.py"
rule = "*"
expires = "2024-12-31"
reason = "Temporary plugin for migration"
```

### Custom Rules

```toml
[[custom_rule]]
name = "no_global_state"
pattern = "^[A-Z_]+ = "
severity = "warning"
message = "Avoid global state in plugins"
```

## See Also

- `spec/design/plugin-checker.md` - Checker architecture
- `spec/design/plugin-specification.md` - Plugin rules
- `spec/arch/backpressure.md` - Streaming principles
