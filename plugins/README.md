# JN Plugins

Bundled plugins shipped with the JN package.

## Organization

```
plugins/
  readers/          Source plugins (file format → NDJSON)
  writers/          Target plugins (NDJSON → file format)
  filters/          Transform plugins (NDJSON → NDJSON)
  shell/            Shell command wrappers (command → NDJSON)
  http/             HTTP/API plugins (future)
```

## Usage

### Direct Execution
```bash
# Run plugin directly
python3 plugins/readers/csv_reader.py < data.csv

# Test plugin
python3 plugins/readers/csv_reader.py --test

# Show help
python3 plugins/readers/csv_reader.py --help
```

### Via JN CLI (when implemented)
```bash
# Auto-detected based on file extension
jn run data.csv filter.jq output.json

# Explicit plugin selection
jn run --source csv_reader data.csv
```

## Plugin Pattern

All plugins follow the same pattern:

```python
#!/usr/bin/env python3
# /// script
# dependencies = []  # PEP 723 inline deps
# ///
# META: type=source, handles=[".csv"]

def run(config=None):
    """Core logic."""
    # ... implementation ...
    yield record

def examples():
    """Test cases."""
    return [...]

def test():
    """Built-in test runner."""
    # ... test logic ...

if __name__ == '__main__':
    # argparse CLI
    # ... argument parsing ...
```

## Available Plugins

### Readers
- **csv_reader.py** - CSV/TSV → NDJSON
- **json_reader.py** - JSON/NDJSON → NDJSON (passthrough)

### Writers
- **csv_writer.py** - NDJSON → CSV/TSV

### Shell
- **ls.py** - Parse ls output to NDJSON

## Testing

Each plugin has built-in tests:
```bash
for plugin in plugins/*/*.py; do
    echo "Testing $plugin..."
    python3 "$plugin" --test
done
```

## License

Individual parsing logic may be inspired by various open-source projects (noted in plugin headers).
All plugin wrappers are MIT licensed.
