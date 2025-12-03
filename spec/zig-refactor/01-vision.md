# Vision and Philosophy

> **Purpose**: Why JN exists and what makes it different from other ETL tools.

---

## The Problem

AI agents need to extract, transform, and load data from arbitrary sources. They encounter:
- CSV files with non-standard delimiters
- REST APIs with custom authentication
- Databases requiring specific drivers
- Proprietary formats needing specialized parsers

Traditional ETL tools fail agents because they're designed for humans:
- **Pandas**: Loads entire datasets into memory, requires Python expertise
- **Spark**: Cluster-oriented, massive startup overhead
- **dbt**: SQL-centric, requires pre-defined models
- **Airflow**: Workflow orchestration, not data transformation

Agents need something different: a toolkit they can compose on-the-fly, extend when needed, and run with predictable resource usage.

---

## The Solution: Agent-Native ETL

JN is an ETL framework designed for AI agents to create data tools on demand.

**Core insight**: Unix got this right 50 years ago. Small programs that do one thing well, connected via pipes, with text as the universal interface.

JN modernizes this for structured data:
- **NDJSON** as the universal format (one JSON object per line)
- **Plugins** as standalone executables (no framework imports)
- **Pipes** for streaming with automatic backpressure
- **Profiles** for reusable configurations

---

## Core Philosophy

### 1. Streaming by Default

Data flows through pipes, never accumulates in memory:

```
Source → Protocol → Decompress → Format → NDJSON → Filter → Output
         (HTTP)      (gzip)      (CSV)              (ZQ)
```

Each stage runs as a separate process. The OS manages:
- **Backpressure**: Slow consumers pause fast producers
- **Parallelism**: Multiple CPUs work simultaneously
- **Shutdown**: SIGPIPE propagates when downstream exits

**Result**: Process 10GB files with 1MB of RAM.

### 2. Plugins as Executables

Every plugin is a standalone script that can run independently:

```bash
# Direct execution (for testing)
./csv --mode=read < data.csv

# Via JN (for composition)
jn cat data.csv | jn filter '.x > 10' | jn put output.json
```

Plugins don't import a framework. They read stdin, write stdout, and follow a simple CLI convention.

### 3. NDJSON as Universal Format

Newline-Delimited JSON is the interchange format between all plugins:

```
{"name": "Alice", "age": 30}
{"name": "Bob", "age": 25}
{"name": "Carol", "age": 35}
```

Why NDJSON:
- **Streamable**: Process one record at a time (unlike JSON arrays)
- **Human-readable**: Easy to inspect and debug
- **Tool-friendly**: Works with grep, head, tail, jq
- **Self-describing**: No separate schema required

### 4. Profiles for Configuration

Credentials and endpoint details live in profiles, not commands:

```bash
# Without profiles (credentials exposed)
curl -H "Authorization: Bearer $TOKEN" https://api.example.com/users

# With profiles (configuration abstracted)
jn cat @myapi/users
```

Profiles support:
- Hierarchical inheritance (`_meta.json` + `endpoint.json`)
- Environment variable substitution (`${API_TOKEN}`)
- Parameter validation and defaults

### 5. Agent Extensibility

Agents can create new plugins on-demand. A plugin is just a Python script with:
- PEP 723 metadata (dependencies, patterns)
- `reads()` and/or `writes()` functions
- CLI argument handling

No compilation, no registration, no restart. Drop a file, it works.

---

## Design Principles

### Standard Over Custom

| Choice | Standard | Why |
|--------|----------|-----|
| Metadata | PEP 723 | Python ecosystem standard |
| Data format | NDJSON | Widely supported |
| Streaming | Unix pipes | OS-level, battle-tested |
| Isolation | UV/processes | No virtualenv complexity |

### Simple Over Clever

- No async/await (processes are simpler)
- No threading (GIL makes it pointless)
- No custom binary formats (NDJSON everywhere)
- No framework imports (standalone scripts)

### Composition Over Configuration

Instead of one tool that does everything:

```bash
# Monolithic (hypothetical)
mega-etl --source=csv --input=data.csv --filter=".x>10" --output=json --dest=out.json
```

Compose small tools:

```bash
# Unix philosophy
jn cat data.csv | jn filter '.x > 10' | jn put out.json
```

Each tool has one job. Complex pipelines emerge from composition.

---

## Non-Goals

JN deliberately does **not** aim to:

### Replace Databases
JN streams data; it doesn't store or index it. For queries over persistent data, use DuckDB, SQLite, or Postgres.

### Handle Petabyte Scale
JN targets gigabyte-scale data on single machines. For petabyte scale, use Spark or BigQuery.

### Provide a GUI
JN is CLI-native. For visual exploration, pipe to VisiData or export to tools with GUIs.

### Manage Workflows
JN transforms data; it doesn't schedule or orchestrate. For workflows, use Airflow, Prefect, or cron.

### Guarantee Schema
JN passes through whatever JSON it receives. For schema enforcement, use external validators.

---

## Success Criteria

JN succeeds when:

1. **Agents can create plugins**: A new data source should require only a simple Python script
2. **Memory stays constant**: 10MB and 10GB files use the same RAM
3. **First output is immediate**: Don't wait for full file processing
4. **Errors are clear**: Know exactly which stage failed and why
5. **Composition is natural**: Complex pipelines feel like simple pipes

---

## See Also

- [02-architecture.md](02-architecture.md) - How components fit together
- [05-plugin-system.md](05-plugin-system.md) - Plugin interface details
- [08-streaming-backpressure.md](08-streaming-backpressure.md) - Why pipes beat async
