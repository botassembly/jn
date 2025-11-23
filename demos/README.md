# JN Demos

Welcome to the JN demos! These examples demonstrate JN's capabilities for agent-native ETL operations.

## Available Demos

### 1. CSV Filtering (`csv-filtering/`)

Learn the basics of JN's ETL pipeline:
- Reading CSV files
- Filtering data with jq expressions
- Converting between formats
- Aggregating and transforming data

**Start here if you're new to JN!**

```bash
cd csv-filtering
./run_examples.sh
```

### 2. HTTP API (`http-api/`)

Fetch and process data from REST APIs:
- Fetching JSON from public APIs
- Using format hints and auto-detection
- Creating HTTP profiles for authenticated APIs
- Combining API data with local files

```bash
cd http-api
./run_examples.sh
```

### 3. Shell Commands (`shell-commands/`)

Convert shell command output to NDJSON:
- Processing `ls`, `ps`, `df` output
- Filtering system information
- Monitoring processes and resources
- 70+ supported commands via `jc`

```bash
cd shell-commands
./run_examples.sh
```

### 4. XLSX Files (`xlsx-files/`)

Work with Microsoft Excel spreadsheets:
- Reading Excel files into NDJSON
- Converting Excel ↔ CSV/JSON/YAML
- Filtering and transforming Excel data
- Creating reports from spreadsheets

```bash
cd xlsx-files
./run_examples.sh
```

### 5. MCP Integration (`mcp/`)

Connect to Model Context Protocol servers:
- Using bundled MCP profiles (BioMCP, Context7, etc.)
- Calling MCP tools and resources
- Creating custom MCP profiles
- Integrating LLM tools into pipelines

```bash
cd mcp
cat README.md
```

### 6. GenomOncology API (`genomoncology/`)

Access clinical genomic data:
- Querying genetic alterations
- Searching clinical trials
- Using HTTP profiles with authentication
- Real-world API integration example

```bash
cd genomoncology
cat README.md
# Requires API credentials - see README for setup
```

## Quick Examples

### Basic Pipeline

```bash
# Read CSV → Filter → Save as JSON
jn cat data.csv | \
  jn filter '.revenue > 1000' | \
  jn put output.json
```

### API Integration

```bash
# Fetch from API → Transform → Save as CSV
jn cat "https://api.github.com/users/octocat~json" | \
  jn filter '{name: .name, repos: .public_repos}' | \
  jn put github_user.csv
```

### Shell Commands

```bash
# Get processes → Filter high CPU → Save report
jn sh "ps aux" | \
  jn filter '(.pcpu | tonumber) > 10' | \
  jn put high_cpu_processes.json
```

### Multi-stage Pipeline

```bash
# Fetch → Filter → Transform → Aggregate → Save
jn cat "https://api.example.com/sales~json" | \
  jn filter '.region == "North"' | \
  jn filter '{product: .product, revenue: .revenue}' | \
  jq -s 'group_by(.product) | map({product: .[0].product, total: map(.revenue) | add})' | \
  jn put north_sales_summary.csv
```

## Demo Features Matrix

| Feature | CSV | HTTP | Shell | XLSX | MCP | GenomOncology |
|---------|-----|------|-------|------|-----|---------------|
| Basic I/O | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Filtering | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Format Conversion | ✅ | ✅ | ✅ | ✅ | - | - |
| Aggregation | ✅ | ✅ | ✅ | ✅ | - | - |
| API Access | - | ✅ | - | - | ✅ | ✅ |
| Authentication | - | ✅ | - | - | ✅ | ✅ |
| Profile System | - | ✅ | - | - | ✅ | ✅ |
| Working Example Data | ✅ | ✅ | ✅ | ✅ | - | - |

## Learning Path

**Beginner:**
1. Start with **CSV Filtering** to learn basic concepts
2. Try **XLSX Files** to see format conversion
3. Explore **HTTP API** for external data

**Intermediate:**
4. Check **Shell Commands** for system integration
5. Review **GenomOncology** for real-world profile usage

**Advanced:**
6. Experiment with **MCP Integration** for LLM tools
7. Create your own custom profiles and plugins

## Key Concepts Demonstrated

### Streaming Architecture

All demos show constant-memory streaming:
- Process files of any size
- First results appear immediately
- Early termination with `| head`

### Universal Addressing

Examples of JN's addressing system:
- Local files: `data.csv`, `report.xlsx`
- HTTP URLs: `https://api.com/data~json`
- Profile references: `@genomoncology/trials`
- MCP resources: `@biomcp/search?gene=BRAF`

### Pipeline Composition

Build complex workflows from simple commands:
```bash
jn cat source | \
  jn filter 'condition' | \
  jn filter '{transform}' | \
  jn put destination
```

### Format Flexibility

Convert between any supported formats:
- CSV ↔ JSON ↔ YAML ↔ XLSX ↔ NDJSON
- Automatic format detection
- Explicit format hints when needed

## Running All Demos

To run all demos with working examples:

```bash
# CSV filtering
cd csv-filtering && ./run_examples.sh && cd ..

# HTTP API (requires internet)
cd http-api && ./run_examples.sh && cd ..

# Shell commands (requires jc)
cd shell-commands && ./run_examples.sh && cd ..

# XLSX files (requires openpyxl)
cd xlsx-files && ./run_examples.sh && cd ..
```

## Requirements

Most demos work out of the box, but some have optional dependencies:

- **Shell Commands**: Requires `jc` (JSON Convert)
  ```bash
  pip install jc
  ```

- **XLSX Files**: Requires `openpyxl` (auto-installed by UV)

- **MCP**: Requires MCP servers to be installed (see demo README)

- **GenomOncology**: Requires API credentials (see demo README)

## Creating Your Own Demos

Use these demos as templates for your own workflows:

1. Copy a demo directory structure
2. Replace sample data with your data
3. Modify the examples for your use case
4. Share with your team!

## Documentation

- **Main README**: `/README.md` - Project overview
- **CLAUDE.md**: `/CLAUDE.md` - Complete guide for AI agents
- **Specs**: `/spec/done/` - Architecture documentation
- **Plugin Docs**: `/jn_home/plugins/` - Plugin source code

## Getting Help

- Run `jn --help` for CLI help
- Check individual demo READMEs for details
- See `/spec/done/` for architecture docs
- Report issues at https://github.com/anthropics/claude-code/issues

## Contributing

Found a bug or have an idea for a new demo?

1. Create an issue describing the demo
2. Submit a PR with the demo in `demos/`
3. Include a README and working examples
4. Make it easy for others to run

Happy data wrangling! 🚀
