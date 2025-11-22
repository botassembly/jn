# JN Project Review: The Agent-Native ETL Framework

## 1. Executive Summary

**JN (Junction)** is a command-line ETL (Extract, Transform, Load) framework designed specifically for **AI Agents** and **Data Engineers**. unlike traditional ETL tools that rely on heavy runtimes (Java/JVM) or complex async event loops (Python asyncio), JN leverages the operating system's native capabilities—processes, pipes, and signals—to create high-performance, constant-memory data pipelines.

The core philosophy is simple: **Everything is a stream of JSON objects (NDJSON).**

Whether reading a CSV file, querying a REST API, listening to a Gmail inbox, or scraping a website, JN normalizes the input into newline-delimited JSON, allows transformation via tools like `jq`, and then formats the output to the desired destination.

## 2. Why JN Was Created

The project addresses specific friction points in modern data engineering and AI agent tool use:

1.  **Dependency Hell:** Python tools often conflict. JN uses **UV** (a fast Python package manager) to run every plugin in an isolated environment via PEP 723 script headers.
2.  **Memory Bloat:** Loading a 10GB CSV into Pandas crashes most laptops. JN streams data row-by-row using Unix pipes, keeping memory usage constant (~1MB) regardless of dataset size.
3.  **Agent Discoverability:** AI Agents struggle to import complex Python libraries. JN exposes tools as standalone files with regex-based matching, making them easily discoverable and executable without writing Python code.
4.  **Protocol Fatigue:** Users shouldn't need to write boilerplate `requests` code or handle OAuth tokens manually every time they want to query an API. JN uses a hierarchical **Profile System** to curate these interactions.

---

## 3. The Universal Addressing System

One of JN's most powerful features is its addressing syntax, which creates a uniform way to access data regardless of its location or format.

**Syntax:** `address[~format][?parameters]`

*   **Address:** The source (File path, URL, Profile reference, or Stdin).
*   **~ (Tilde):** Format override (Force a specific parser).
*   **? (Question Mark):** Configuration parameters.

### Examples

````bash
# 1. Standard File (Auto-detect format)
jn cat data.csv

# 2. Format Override (Force text file to be parsed as CSV)
jn cat "data.txt~csv"

# 3. Configuration Parameters (Pass args to the plugin)
jn cat "data.csv?delimiter=;&header=false"

# 4. Profile Reference (Curated API endpoint)
jn cat "@genomoncology/alterations?gene=BRAF&limit=10"

# 5. Protocol URL (Direct access)
jn cat "s3://my-bucket/logs.json.gz"
````

---

## 4. Architectural Deep Dive

### A. Process-Based Parallelism (Not Async)

JN explicitly rejects Python's `asyncio` for data pipelines. Instead, it uses `subprocess.Popen` to chain scripts together.

**Why?**
1.  **True Parallelism:** Each stage of the pipeline (Read -> Transform -> Write) runs in its own process, utilizing multiple CPU cores.
2.  **Automatic Backpressure:** The OS pipe buffer (typically 64KB) naturally blocks a fast producer if the consumer is slow. No complex code is required to manage flow control.
3.  **SIGPIPE Propagation:** If a downstream process stops (e.g., `head -n 10`), the pipe closes, sending a signal up the chain to stop downloads immediately.

**Code Snippet (Core Pipeline Logic):**
````python
# src/jn/core/pipeline.py structure (simplified)

# 1. Start the Reader
reader = subprocess.Popen(
    [sys.executable, reader_plugin_path, "--mode", "read"],
    stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE,  # Output to pipe
)

# 2. Start the Writer (reading from reader's stdout)
writer = subprocess.Popen(
    [sys.executable, writer_plugin_path, "--mode", "write"],
    stdin=reader.stdout,     # Input from reader
    stdout=sys.stdout,
)

# 3. CRITICAL: Close the parent's handle to the pipe
# This ensures that if writer dies, reader gets SIGPIPE
reader.stdout.close()

# 4. Wait for finish
writer.wait()
reader.wait()
````

### B. Plugin Isolation via PEP 723 & UV

Plugins are standalone Python scripts. They declare their own dependencies in comments at the top of the file. JN uses `uv run` to execute them, ensuring they never conflict with the framework or other plugins.

**Plugin Example (`csv_.py`):**
````python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# [tool.jn]
# matches = [".*\\.csv$", ".*\\.tsv$"]
# ///

import sys, csv, json

def reads(config=None):
    # Implementation to read stdin and yield dicts
    pass

def writes(config=None):
    # Implementation to read NDJSON from stdin and write CSV
    pass

if __name__ == "__main__":
    # CLI boilerplate to handle --mode read/write
    pass
````

### C. The Checker (Static Analysis)

To maintain architectural integrity, JN includes a custom AST-based linter (`jn check`). It scans plugins to ensure they don't violate streaming principles.

**What it checks for:**
1.  Using `subprocess.run(capture_output=True)` (Banned: buffers memory).
2.  Missing `stdout.close()` (Banned: breaks backpressure).
3.  Forbidden framework imports (Plugins must be self-contained).
4.  Missing PEP 723 metadata.

**Config (`.jncheck.toml`):**
````toml
# Whitelist legitimate violations (e.g., ZIP files must be read fully)
[[whitelist]]
file = "jn_home/plugins/formats/xlsx_.py"
rule = "stdin_buffer_read"
reason = "ZIP archives require complete file access (central directory at EOF)."
````

---

## 5. The Profile System

Profiles allow JN to curate complex APIs into simple, addressable resources. They use a hierarchical directory structure.

**Structure:**
````text
jn_home/profiles/
├── http/
│   └── genomoncology/
│       ├── _meta.json          # Connection details (Base URL, Auth)
│       ├── alterations.json    # Endpoint definition
│       └── annotations.json
└── mcp/
    └── biomcp/
        ├── _meta.json          # How to launch the MCP server
        └── search.json         # Tool definition
````

**Example `_meta.json` (Templated Config):**
````json
{
  "base_url": "https://${GENOMONCOLOGY_URL}/api",
  "headers": {
    "Authorization": "Token ${GENOMONCOLOGY_API_KEY}",
    "Accept": "application/json"
  },
  "timeout": 60
}
````

**Example `alterations.json` (Source Definition):**
````json
{
  "path": "/alterations",
  "method": "GET",
  "type": "source",
  "params": ["gene", "mutation_type", "limit"],
  "description": "Genetic alterations database"
}
````

This allows a user to simply run:
`jn cat @genomoncology/alterations?gene=BRAF`

### Profile Types

JN supports multiple profile types for different use cases:

**HTTP API Profiles** - Curated REST API endpoints with authentication
```bash
jn cat "@genomoncology/alterations?gene=BRAF"
```

**DuckDB Query Profiles** - Named SQL queries against analytical databases
```bash
jn cat "@analytics/sales-summary"
jn cat "@analytics/by-region?region=West"
```

**MCP Server Profiles** - Model Context Protocol tools with consistent parameters
```bash
jn cat "@biomcp/search?gene=EGFR"
```

**Gmail Profiles** - Email queries with saved filters
```bash
jn cat "@work/inbox?from=boss&newer_than=7d"
```

### Self-Contained Protocol Plugins

JN uses a **self-contained architecture** for protocol plugins (databases, APIs with complex profiles):

**Pattern:** Plugins vendor all profile-related logic and expose it via `--mode inspect-profiles`.

**Benefits:**
- Framework stays generic (no plugin-specific code)
- Plugins are independently testable
- Easy to add new database plugins (PostgreSQL, MySQL, SQLite)

**Example:** The DuckDB plugin scans for `.sql` files, parses SQL metadata, and returns profile info to the framework—all without the framework knowing anything about SQL or DuckDB specifics.

---

## 6. MCP (Model Context Protocol) Integration

JN embraces the Model Context Protocol to connect AI models to data.

*   **Naked URI Access:** Access MCP servers without configuration using `uvx` or `npx`.
    `jn cat "mcp+uvx://biomcp-python/biomcp?tool=search&gene=BRAF"`
*   **Unified Inspect:** The `jn inspect` command works on MCP servers just like it works on CSV files or API endpoints.

````bash
# List tools available on an MCP server
jn inspect "mcp+uvx://biomcp-python/biomcp"
````

---

## 7. Summary of Capabilities

| Feature | Description |
| :--- | :--- |
| **Streaming** | Constant memory usage via Unix pipes. |
| **Format Support** | CSV, JSON, NDJSON, YAML, TOML, Markdown, Excel (XLSX). |
| **Protocols** | HTTP/HTTPS, Gmail (OAuth2), MCP, DuckDB, Local Files. |
| **Shell Integration** | Fallback to `jc` to parse output of `ls`, `ps`, `dig`, etc. into JSON. |
| **Filtering** | Built-in `jq` wrapper via `jn filter`. |
| **Profile System** | HTTP APIs, DuckDB queries, MCP tools, Gmail—all addressable as `@namespace/name`. |
| **Profile Discovery** | `jn profile list`, `jn profile info`, `jn profile tree` for exploration. |
| **Isolation** | Every plugin runs in its own environment via `uv`. |
| **Self-Contained Plugins** | Protocol plugins vendor their own logic, independently testable. |

JN bridges the gap between the structured world of APIs/Databases and the unstructured world of CLI tools/Files, making them all speak a common language (NDJSON) that AI agents can easily read, write, and understand.
