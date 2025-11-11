# JN Development Roadmap

## Overview
This roadmap outlines the implementation plan for extending JN with new protocol plugins, format handlers, database connectors, and profile system enhancements. The work is organized into phases that build upon each other, starting with foundational protocols and progressing to advanced features.

## Phase 1: Core Protocol & Format Plugins
Foundation for remote data access and common file formats.

- [ ] [HTTP Protocol Plugin](work/01-http-protocol.md) - Basic GET/POST using curl, HTTPBin testing
- [ ] [XLSX Format Plugin](work/02-xlsx-format.md) - Excel file reading using openpyxl
- [ ] [S3 Protocol Plugin](work/03-s3-protocol.md) - AWS S3 access via AWS CLI
- [ ] [FTP Protocol Plugin](work/04-ftp-protocol.md) - FTP server access (if environment allows)

**Goal:** Enable fetching data from HTTP, S3, and FTP sources, plus reading XLSX files.

**Milestone:** Can run `jn cat https://example.com/data.xlsx | jn filter '...' | jn put output.csv`

---

## Phase 2: Profile System Foundation
Demonstrate profile system with real HTTP API example.

- [ ] [RESTful API Dev Profile](work/05-restful-api-profile.md) - HTTP profile for restful-api.dev, demonstrates path resolution and config

**Goal:** Working profile system with `@profile/path` syntax for HTTP APIs.

**Milestone:** Can run `jn cat @restful-api-dev/objects | jn filter '...' | jn put results.json`

**Dependencies:** Requires HTTP protocol plugin from Phase 1.

---

## Phase 3: Database Plugins
SQL database access with parameterized queries and profiles.

- [ ] [SQLite Database Plugin](work/06-sqlite-database.md) - Local SQLite databases with aiosql
- [ ] [PostgreSQL Database Plugin](work/07-postgres-database.md) - Remote Postgres with connection pooling

**Goal:** Query databases with named SQL queries from profiles.

**Milestone:** Can run `jn cat @mydb/active-users.sql --limit 10 --dept engineering | jn put users.csv`

**Note:** These are **separate plugins** due to different dependencies and connection handling.

---

## Phase 4: Rendering & Display
Human-readable output for data exploration.

- [ ] [JTBL Renderer Plugin](work/08-jtbl-renderer.md) - Table formatting using jtbl library

**Goal:** Display query results and pipeline output as formatted tables.

**Milestone:** Can run `jn cat @mydb/users.sql | jn filter '.active == true' | jn jtbl`

---

## Phase 5: Shell Command Integration
Vendor JC project parsers for Unix command output.

- [ ] [JC Shell Plugins](work/09-jc-shell-plugins.md) - Vendor ls, ps, df, du, netstat, etc. from JC project

**Goal:** Parse common Unix commands into NDJSON for filtering and processing.

**Milestone:** Can run `jn ls /var/log | jn filter '.size > 1000000' | jn jtbl`

---

## Future Enhancements (Post-Initial Release)

### Additional Protocols
- [ ] MCP (Model Context Protocol) plugin
- [ ] SSH/SFTP protocol plugin
- [ ] Git protocol plugin (read commits, diffs, etc.)
- [ ] WebSocket protocol plugin

### Additional Formats
- [ ] Parquet format (big data)
- [ ] Avro format
- [ ] Protocol Buffers (protobuf)
- [ ] MessagePack format

### Additional Databases
- [ ] MySQL/MariaDB plugin
- [ ] Oracle plugin (if licensing allows)
- [ ] MongoDB plugin
- [ ] Redis plugin (key-value operations)

### Profile Enhancements
- [ ] Profile discovery and caching system
- [ ] Environment variable substitution (`${VAR}`)
- [ ] Profile shortcuts with collision detection
- [ ] Profile inheritance (base + override configs)
- [ ] Encrypted credential storage

### Performance & Reliability
- [ ] Connection pooling for HTTP/DB
- [ ] Retry logic with exponential backoff
- [ ] Rate limiting support
- [ ] Response caching
- [ ] Parallel pipeline execution

### Developer Experience
- [ ] Plugin generator CLI (`jn plugin new`)
- [ ] Profile generator CLI (`jn profile new`)
- [ ] Plugin testing framework
- [ ] Documentation generator from PEP 723 metadata

---

## Implementation Order Rationale

1. **HTTP first** - Most common protocol, foundation for APIs
2. **XLSX early** - Common format, useful for testing HTTP/S3
3. **S3 + FTP** - Additional protocols while HTTP patterns fresh
4. **RESTful API profile** - Demonstrates profile system with working example
5. **Databases** - Complex but high value, builds on profile work
6. **JTBL** - Nice-to-have for user experience, not blocking
7. **JC vendoring** - Large task, benefits from all other work being stable

---

## Success Metrics

**Phase 1-2 Complete:**
- Can fetch data from HTTP, S3, FTP
- Can read XLSX files
- Profile system working for HTTP APIs
- 80% test coverage for new plugins

**Phase 3 Complete:**
- Can query SQLite and PostgreSQL databases
- Named queries work from profiles
- Parameterized queries with NULL-safe handling
- Streaming cursors for large result sets

**Phase 4-5 Complete:**
- Table rendering for data exploration
- 10+ shell commands vendored and working
- Documentation complete for all plugins
- Example profiles for common use cases

---

## Dependencies & Prerequisites

**System Tools:**
- `curl` - HTTP/FTP protocols
- `aws` CLI - S3 protocol (install separately)
- `sqlite3` - SQLite plugin (usually built-in)
- `psql` - PostgreSQL verification (optional)

**Python Packages:**
- `openpyxl` - XLSX format
- `aiosql` - SQL query management
- `psycopg2-binary` - PostgreSQL driver
- `jtbl` - Table rendering

**Development:**
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `ruff` - Linting and formatting

---

## Related Documentation
- [Architecture Design](arch/design.md) - v5 architecture with profiles
- [Backpressure Explanation](arch/backpressure.md) - Why Popen > async
- [CLAUDE.md](../CLAUDE.md) - Project overview and principles
