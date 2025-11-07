# jc Overview and Python Library Guide

This guide explains what `jc` is, how it works at a high level, and how to use it as a Python library (SDK) with both built‑in parsers and your own custom parsers.

## What Is `jc`?

`jc` (JSON Convert) turns the text output of common command‑line tools and file formats into structured Python objects (lists/dicts). It lets you parse command output in a predictable way without writing one‑off regexes. You can use it:

- As a CLI tool (e.g., `ls | jc --ls | jq ...`), or
- As a Python library (e.g., `jc.parse('ls', text)`), which this guide focuses on.

Key ideas:
- Parsers are small Python modules (one per command/format) that expose two things:
  - `class info:` metadata (name, version, tags, compatibility, etc.)
  - `def parse(...)` that returns structured data
- There are two kinds of parsers:
  - Standard parsers: consume a string/bytes and return dict/list
  - Streaming parsers: consume an iterable of lines and yield dicts lazily
- You can add local “plugin” parsers and even override built‑ins without patching `jc`.

## Install

Typical install via pip:

```bash
pip install jc
```

Or vendor the package in your project if you prefer to pin the version tightly.

## High‑Level Architecture

- Built‑in parsers live under `jc.parsers`.
- Local plugin parsers live in a `jcparsers` package located in a user‑specific directory (configurable; see “Custom Parsers” below).
- The high‑level API `jc.parse(name_or_module, data, ...)` finds the right parser (built‑in or plugin), runs it, and returns structured data.
- Utility APIs:
  - `jc.get_parser('name')` → returns the module object
  - `jc.parser_mod_list()` / `jc.plugin_parser_mod_list()` → list available parser names
  - `jc.parser_info('name')` / `jc.all_parser_info()` → metadata
  - `jc.get_help('name')` → view parser docs

## Using `jc` as a Library (Built‑in Parsers)

### Standard Parsers (string/bytes input)

```python
import jc

text = "Tue Jan 18 10:23:07 PST 2022"  # output of `date`
data = jc.parse('date', text)
print(data[0]['year'])
```

Notes:
- `raw=True` returns minimally processed structures (pre‑postprocessing): `jc.parse('date', text, raw=True)`
- `quiet=True` suppresses warnings (e.g., platform compatibility): `jc.parse('date', text, quiet=True)`

### Streaming Parsers (iterable of lines)

```python
import jc

lines = some_command_output.splitlines()  # or sys.stdin
for item in jc.parse('ping_s', lines):
    print(item['time_ms'])
```

Options:
- `ignore_exceptions=True` yields `_jc_meta` entries rather than raising on bad lines.

### Using Module Objects Directly

```python
import jc

mod = jc.get_parser('date')
data = mod.parse("Tue Jan 18 10:23:07 PST 2022")
```

Or import directly:

```python
import jc.parsers.date as jc_date
data = jc_date.parse("Tue Jan 18 10:23:07 PST 2022")
```

### Discoverability & Metadata

```python
import jc

print(jc.parser_mod_list())            # all available parsers
print(jc.plugin_parser_mod_list())     # plugin parsers only
print(jc.parser_info('ls'))            # metadata for a single parser
print(jc.all_parser_info())            # metadata for all parsers
jc.get_help('ls')                      # print help/docstring for a parser
```

## Custom Parsers

You can provide your own parser modules without modifying `jc` itself. A plugin parser is just a `.py` module placed under a `jcparsers` package. You can either use the default per‑user plugin location or configure a custom location.

### Where Plugins Live (Default)

By default, `jc` looks for a `jcparsers` folder in your user’s app‑data directory:

- Linux/Unix: `~/.local/share/jc/jcparsers`
- macOS: `~/Library/Application Support/jc/jcparsers`
- Windows: `%LOCALAPPDATA%\jc\jc\jcparsers`

Place one `.py` file per parser in that `jcparsers/` directory. Filenames must be valid Python module names (start with a letter; alphanumerics/underscores only).

### Configure Plugin Location

If you want `jc` to load plugins from a specific directory:

- Environment variables (read at import time):
  - `JC_PLUGIN_DIR`: Either the `jcparsers` folder itself or a parent folder that contains `jcparsers/`.
  - `JC_DATA_DIR`: Overrides the app‑data parent directory; `jcparsers` is loaded from `$JC_DATA_DIR/jcparsers`.
  - Linux also respects `XDG_DATA_HOME` for the default app‑data base.

- Runtime API (per‑process):
  ```python
  import jc
  jc.set_plugin_dir('/opt/myapp/jcparsers')
  # or: jc.set_plugin_dir('/opt/myapp')  # must contain jcparsers/
  ```

Built‑ins remain available; your plugins are added on top. If a plugin name matches a built‑in, your plugin takes precedence. If a plugin fails to import, `jc` disables that parser and logs a warning.

### Writing a Custom Parser

Use the templates in the source tree as a starting point:
- Standard (string input): `jc/parsers/foo.py`
- Streaming (iterable input): `jc/parsers/foo_s.py`

Minimal example (`jcparsers/mycmd.py`):

```python
class info:
    version = '0.1'
    description = 'example parser'
    author = 'you'
    author_email = 'you@example.com'
    compatible = ['linux', 'darwin', 'win32', 'cygwin', 'aix', 'freebsd']
    tags = ['command']

def parse(data, raw=False, quiet=False):
    # parse text and return a list or dict
    return [{'ok': True}]
```

Use it in Python:

```python
import jc

# If not using the default plugin path:
# jc.set_plugin_dir('/path/to/jcparsers')

print(jc.plugin_parser_mod_list())  # should include 'mycmd'
print(jc.parse('mycmd', 'some text'))
```

### Overriding a Built‑in Parser

Create a plugin module with the same name as a built‑in (e.g., `ls.py`). `jc` prefers the local plugin over the built‑in. If your plugin raises an import error, the parser is disabled and a warning is emitted.

## API Cheatsheet

- Parse by name: `jc.parse('date', text)`
- Parse by module: `jc.parse(jc.get_parser('date'), text)`
- Streaming parse: `for item in jc.parse('ping_s', lines): ...`
- Quiet/raw: `jc.parse('date', text, quiet=True, raw=True)`
- Configure plugins: `jc.set_plugin_dir('/opt/myapp/jcparsers')`
- List parsers: `jc.parser_mod_list()` / `jc.plugin_parser_mod_list()`
- Metadata: `jc.parser_info('ls')` / `jc.all_parser_info()`
- Help: `jc.get_help('ls')`

## Tips

- Set locale appropriately for parsers sensitive to formatting (e.g., `LC_ALL=C`).
- Prefer the high‑level `jc.parse(...)` API; it auto‑selects plugins and simplifies streaming parser use.
- For streaming parsers, pass an iterable of lines (e.g., `sys.stdin` or `text.splitlines()`).

