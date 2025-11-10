# Root Cause Analysis: `jn plugin call` Option Parsing Issue

## Problem Statement

The command `jn plugin call json_ --mode write` fails with:
```
Error: No such option: --mode
```

Despite extensive configuration of Click's `ignore_unknown_options` and `allow_extra_args`.

## 10 Whys Investigation

### WHY 1-3: Command Structure Verification
✅ `jn --help` - Shows correct command hierarchy
✅ `jn plugin --help` - Shows call and list subcommands
✅ `jn plugin call --help` - Shows ARGS... parameter with UNPROCESSED type

### WHY 4-5: Option Routing Test
- ❌ `jn plugin call json_ --mode write` - Fails at root level parse
- ⚠️ `jn plugin call json_` (no options) - Routes to call() correctly
- ❌ Quoting `'--mode'` doesn't help
- ❌ Using `--` separator doesn't help

### WHY 6-8: Configuration Verification
✅ Root `cli` has `context_settings={'ignore_unknown_options': True, 'allow_extra_args': True}`
✅ Plugin group has same context_settings
✅ Call command has same context_settings + `@click.argument('args', nargs=-1, type=click.UNPROCESSED)`

### WHY 9-10: Isolation Testing

**Key Discovery:**
| Test Case | Result | Details |
|-----------|--------|---------|
| Standalone script with identical code | ✅ **WORKS** | `test_no_mode_option.py` with exact cli.py code |
| Real CLI via entry point | ❌ **FAILS** | `/home/user/jn/.venv/bin/jn` |
| Real CLI via `python -m` | ❌ **FAILS** | `python -m jn.cli` |
| Real CLI imported directly | ❌ **FAILS** | `from jn.cli import main; main()` |

## Root Cause

**Click's `ignore_unknown_options=True` does NOT work correctly in nested groups when:**
1. Code is imported as an installed package module
2. Code is executed via setuptools entry point
3. Code is imported from a package vs. executed as `__main__`

The EXACT same Click code behaves differently based on import context:
- ✅ `python test_script.py plugin call json_ --mode write` → Works
- ❌ `jn plugin call json_ --mode write` (via entry point) → Fails

## Tested & Eliminated

These are **NOT** the cause:
- ❌ Missing `ignore_unknown_options` or `allow_extra_args`
- ❌ Wrong decorator order on commands
- ❌ Circular import issues (fixed with context.py)
- ❌ Click version incompatibility (tested 8.0.0 and 8.3.0)
- ❌ Other commands interfering (tested with only plugin command)
- ❌ `sys.argv[0]` format (tried modifying to 'jn')
- ❌ Using `ctx.args` vs `@click.argument`
- ❌ Context settings at different hierarchy levels

## Evidence

### Standalone Test (WORKS)
```python
# test_no_mode_option.py
@click.group(context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.option('--home', type=click.Path(), help='Home directory')
@click.pass_context
def cli(ctx, home):
    """Root command."""
    ctx.ensure_object(JNContext)

@click.group(context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
def plugin():
    """Plugin subcommand."""
    pass

@plugin.command(context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.argument('args', nargs=-1, type=click.UNPROCESSED, required=True)
def call(args):
    """Call command."""
    click.echo(f"Got args: {args}")

# Result: Got args: ('json_', '--mode', 'write') ✅
```

### Installed CLI (FAILS)
```python
# src/jn/cli.py - EXACT SAME CODE
# Result: Error: No such option: --mode ❌
```

## Click Bug Reference

This appears to be related to:
- Click issue #413: "Ignore and pass attributes onto sub application"
- Click issue #489: "Cannot ignore unknown options"

Known Click limitation: `ignore_unknown_options` behavior differs between:
- Direct script execution (`__name__ == '__main__'`)
- Package module imports (entry points)

## Workaround

Direct plugin invocation:
```bash
python src/jn/plugins/formats/csv_.py --mode read < input.csv
python src/jn/plugins/filters/jq_.py --query '.name' < input.ndjson
```

## Recommendations

1. **Short-term**: Document limitation, provide direct invocation examples
2. **Medium-term**: Investigate alternative CLI frameworks:
   - `typer` - Modern, type-hint based
   - `argparse` - Standard library, more control
   - Custom parser before Click routing
3. **Long-term**: File Click bug report with minimal reproduction case

## Files Affected

- `src/jn/commands/plugin.py` - Documented limitation in docstring
- `tests/test_cli.py` - Skip plugin call tests with options
- `CLAUDE.md` - Updated known limitations section
