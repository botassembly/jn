# JN Development Roadmap

## Phase 0: Essential Formats & Filters (Early Priority)

- [ ] [Markdown Format Plugin](work/10-markdown-format.md) - Read/write markdown files, extract frontmatter
- [ ] [JQ Profile System](work/11-jq-profile.md) - Named jq filters with pivot table support
- [ ] [TOML Format Plugin](work/12-toml-format.md) - Read/write TOML config files

**Why:** Enable documentation processing, named filter libraries, and config file handling from day one.

---

## Phase 1: Core Protocols & Formats

- [ ] [HTTP Protocol Plugin](work/01-http-protocol.md) - Fetch data from HTTP/HTTPS endpoints
- [ ] [XLSX Format Plugin](work/02-xlsx-format.md) - Read Excel spreadsheets
- [ ] [S3 Protocol Plugin](work/03-s3-protocol.md) - Read from AWS S3 buckets
- [ ] [FTP Protocol Plugin](work/04-ftp-protocol.md) - Read from FTP servers

**Why:** Enable remote data access and common business file formats.

---

## Phase 2: Profile System

- [ ] [RESTful API Dev Profile](work/05-restful-api-profile.md) - HTTP profile example with `@profile/path` syntax

**Why:** Demonstrate reusable connection configs and path resolution for APIs.

---

## Phase 3: SQL Databases

- [ ] [SQLite Database Plugin](work/06-sqlite-database.md) - Local SQLite with named queries
- [ ] [PostgreSQL Database Plugin](work/07-postgres-database.md) - Remote Postgres with connection pooling
- [ ] [DuckDB Database Plugin](work/13-duckdb-database.md) - Analytical database for OLAP queries

**Why:** Query structured data with SQL, from local files to production databases to analytics workloads.

---

## Phase 4: Display & Shell Integration

- [ ] [JTBL Renderer Plugin](work/08-jtbl-renderer.md) - Format data as tables
- [ ] [JC Shell Plugins](work/09-jc-shell-plugins.md) - Vendor ls, ps, df parsers from JC project
- [ ] [LS Folder Reader](work/14-ls-folder-reader.md) - Read directory contents as NDJSON
- [ ] [Tail File Follower](work/15-tail-file-follower.md) - Follow log files (tail -f)
- [ ] [Watchdog File Monitor](work/16-watchdog-monitor.md) - Monitor file/directory changes

**Why:** Human-readable output and real-time system monitoring capabilities.

---

## Phase 5: Data Formats & Cloud Services

- [ ] [Parquet Format Plugin](work/17-parquet-format.md) - Read/write columnar Parquet files
- [ ] [Google Sheets Plugin](work/18-google-sheets.md) - Read/write Google Sheets via API

**Why:** Big data formats and cloud-based spreadsheets for collaboration.

---

## Phase 6: Advanced Protocols

- [ ] [MCP Protocol Plugin](work/19-mcp-protocol.md) - Model Context Protocol for AI tool integration

**Why:** Enable JN to function as data source/sink for AI agents and tools.
