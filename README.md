# JN (Junction) - Agent-Native ETL with JSON Pipelines

**Version:** 4.0.0-alpha1
**Status:** Active Development

A lightweight ETL framework where JSON Lines is the universal data format. Built for agents and humans who need to move data between formats, APIs, databases, and commands without writing bespoke scripts.

## Philosophy

**Three core principles:**

1. **JSON Lines Everywhere** - Universal data interchange format on the CLI
2. **Discoverable Without Execution** - Tools are files on disk with parseable headers
3. **Automatic Pipeline Construction** - Framework wires together sources → filters → targets

Inspired by Kelly Brazil's [jc](https://github.com/kellyjonbrazil/jc) philosophy: make every command line tool speak JSON.

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/jn.git
cd jn

# Install in development mode
pip install -e .

# Verify installation
jn --version
```

### Your First Pipeline

```bash
# Convert CSV to JSON
jn cat data.csv | jn put output.json

# Preview first 5 records
jn cat data.csv --limit 5

# Transform and filter
echo '{"name":"Alice","age":30}' | jn cat - | jq '.age' | jn put -
```

## Core Commands

### Data Exploration

**`jn cat <source>`** - Read any source, output NDJSON
```bash
jn cat data.csv              # CSV file
jn cat config.yaml           # YAML file
jn cat https://api.com/data  # HTTP API
jn cat data.json --limit 10  # Preview first 10 records
```

**`jn put <output>`** - Write NDJSON to any format
```bash
jn cat data.csv | jn put output.json    # CSV → JSON
jn cat api | jn put data.yaml            # API → YAML
echo '{"x":1}' | jn put -                # Format to stdout
```

**`jn run <input> [filters...] <output>`** - Automatic pipeline
```bash
jn run data.csv output.json              # Simple conversion
jn run data.csv '.name' summary.xml      # With jq filter
jn run 'ls -la' output.csv               # Command output
```

### Plugin Discovery

**`jn discover`** - List all available plugins
```bash
jn discover                   # All plugins
jn discover --type source     # Only sources
jn discover --category readers # Only readers
```

**`jn show <plugin>`** - Plugin details
```bash
jn show csv_reader           # Show plugin info
jn show csv_reader --examples # Show usage examples
jn show csv_reader --test    # Run plugin tests
```

**`jn which <extension>`** - Find plugin for extension
```bash
jn which .csv                # → csv_reader
jn which .yaml               # → yaml_reader
```

### Plugin Development

**`jn create <type> <name>`** - Scaffold new plugin
```bash
jn create source my_reader --handles .txt
jn create filter my_transform
jn create target my_writer --handles .out
```

**`jn test <plugin>`** - Run plugin tests
```bash
jn test csv_reader           # Run built-in tests
jn test my_plugin --verbose  # Detailed output
```

**`jn validate <file>`** - Check plugin structure
```bash
jn validate plugins/readers/my_reader.py
jn validate my_plugin.py --strict
```

## Supported Formats

| Format | Extension | Reader | Writer |
|--------|-----------|--------|--------|
| CSV    | .csv      | ✅     | ✅     |
| TSV    | .tsv      | ✅     | ✅     |
| JSON   | .json     | ✅     | ✅     |
| NDJSON | .jsonl    | ✅     | ✅     |
| YAML   | .yaml,.yml| ✅     | ✅     |
| XML    | .xml      | ✅     | ✅     |
| TOML   | .toml     | ✅     | ⬜     |

## Plugin Ecosystem

**19 Built-in Plugins:**

**Readers (8):**
- `csv_reader` - CSV/TSV files
- `json_reader` - JSON/NDJSON files
- `yaml_reader` - YAML files
- `xml_reader` - XML files
- `toml_reader` - TOML config files
- `http_get` - HTTP APIs (GET)
- `ls` - Directory listings
- Plus 6 more shell command parsers (ps, find, env, df, ping, netstat, dig)

**Writers (6):**
- `csv_writer` - CSV/TSV output
- `json_writer` - JSON array output
- `yaml_writer` - YAML output
- `xml_writer` - XML output

**Filters (1):**
- `jq_filter` - jq expression evaluation

## Examples

### Data Conversion

```bash
# CSV to multiple formats
jn cat sales.csv | jn put sales.json
jn cat sales.csv | jn put sales.yaml
jn cat sales.csv | jn put sales.xml

# API to database-ready CSV
jn cat https://api.com/users | jq '.items[]' | jn put users.csv

# Config file normalization
jn cat config.yaml | jn put config.json
```

### System Monitoring

```bash
# Process list to JSON
jn cat 'ps aux' | jn put processes.json

# Disk usage analysis
jn cat 'df -h' | jq 'select(.use_percent > 80)' | jn put full_disks.csv

# Network connections
jn cat 'netstat -an' | jn put connections.json
```

### Data Pipelines

```bash
# Filter and transform
jn run users.csv 'select(.age > 18)' adults.json

# Multi-step processing
jn cat data.csv | \
  jq 'select(.amount > 100)' | \
  jq '{customer, total: .amount}' | \
  jn put high_value.xml

# Combine sources
cat <(jn cat file1.csv) <(jn cat file2.yaml) | jn put combined.json
```

## Creating Custom Plugins

### 1. Scaffold Plugin

```bash
jn create source my_api --description "Custom API reader"
# Created: plugins/readers/my_api.py
```

### 2. Implement Logic

Edit `plugins/readers/my_api.py`:

```python
def run(config: Optional[dict] = None) -> Iterator[dict]:
    """Fetch data from custom API."""
    import requests

    response = requests.get('https://my-api.com/data')
    data = response.json()

    for item in data['items']:
        yield item
```

### 3. Add Tests

```python
def examples() -> list[dict]:
    return [
        {
            "description": "Fetch user data",
            "input": "",
            "expected": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"}
            ]
        }
    ]
```

### 4. Test & Validate

```bash
jn test my_api
jn validate plugins/readers/my_api.py
```

### 5. Use in Pipelines

```bash
jn cat my_api | jn put users.csv
```

## Architecture

**Function-Based Plugins** - No classes, just functions:
- `run(config)` - Main processing logic
- `examples()` - Test cases (optional)
- `test()` - Built-in tests (optional)

**Regex-Based Discovery** - No Python imports needed:
- Plugins discovered by scanning filesystem
- Metadata parsed from `# META:` headers
- Fast discovery (~10ms for 19 plugins)

**Subprocess Isolation** - Each plugin runs independently:
- PEP 723 inline dependencies
- UV manages per-plugin environments
- No dependency conflicts

**Unix Pipes** - Standard composition:
```bash
plugin1 < input.txt | plugin2 | plugin3 > output.json
```

## Development Status

**Current (v4.0.0-alpha1):**
- ✅ Core pipeline framework
- ✅ 19 working plugins
- ✅ Full CLI (10 commands)
- ✅ Plugin creation tools
- ✅ 105 tests passing (78% coverage)

**Coming Soon:**
- Excel reader/writer
- Database plugins (PostgreSQL, MySQL, SQLite)
- S3 integration
- API authentication
- Advanced filters (aggregations, group-by)

## Contributing

See [docs/plugins.md](docs/plugins.md) for plugin authoring guide.

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- **Kelly Brazil** - jc philosophy and JSON CLI tooling
- **Anthropic** - MCP inspiration for agent-native design
- **UV** - Modern Python packaging
