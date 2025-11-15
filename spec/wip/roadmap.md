# JN Development Roadmap

## Phase 0: Foundation ✅ COMPLETE

### Essential Formats & Filters
- [x] [Markdown Format Plugin](work/10-markdown-format.md) - Read/write markdown files, extract frontmatter
- [x] [JQ Profile System](work/11-jq-profile.md) - Named jq filters with pivot table support
- [x] [TOML Format Plugin](work/12-toml-format.md) - Read/write TOML config files

### Core Plugin Architecture
- [x] PEP 723 dependency isolation with UV
- [x] Regex-based plugin discovery (no imports)
- [x] Format plugins: CSV, JSON, YAML, Markdown, TOML, Tabulate (display-only)
- [x] Filter plugins: JQ with profile support
- [x] Protocol plugins: HTTP with streaming + error records
- [x] Generic profile resolution (works for any plugin)

### Architecture Patterns Established
- [x] Popen + pipes for streaming (constant memory)
- [x] Error records (not exceptions) for pipeline data
- [x] Profile system: hierarchical _meta.json + source files
- [x] Direct function args (not config dicts)

---

## Phase 1: Current Work (In Progress)

### 1.1 GenomOncology Profile Enhancement
**Status:** ✅ COMPLETE
**Goal:** Real-world example of hierarchical profiles with sources, filters, and source augmentation

Tasks:
- [x] Create hierarchical profile structure (_meta.json + sources)
- [x] Define sources: annotations, alterations, genes, diseases, therapies, clinical_trials
- [x] Create by_transcript filter (pivot transcript arrays)
- [x] Add extract-hgvs filter (extract HGVS nomenclature)
- [x] Add extract-alterations filter refinement
- [x] Document complete workflows with examples
- [x] Test with real API calls (pwb-demo.genomoncology.io)

**Dependencies:** None (can work standalone)
**Deliverables:**
- `jn_home/profiles/jq/genomoncology/extract-hgvs.jq` - Extract and parse HGVS notations
- `jn_home/profiles/jq/genomoncology/extract-alterations.jq` - Normalize alteration records
- `spec/workflows/genomoncology-examples.md` - 10 complete real-world workflows

### 1.2 Plugin Checker Tool
**Status:** Design complete, not implemented
**Goal:** AST-based static analysis to detect architectural violations

Tasks:
- [ ] Create src/jn/checker/ infrastructure
  - [ ] ast_checker.py - AST traversal engine
  - [ ] scanner.py - File discovery (core, plugins, specific)
  - [ ] report.py - Error formatting
- [ ] Implement detection rules:
  - [ ] Rule 1: subprocess.run with capture_output
  - [ ] Rule 2: Missing stdout.close()
  - [ ] Rule 3: Reading all data before processing
  - [ ] Rule 4: Missing wait() calls
  - [ ] Rule 5: subprocess.run instead of Popen
  - [ ] Rule 6: Missing PEP 723 dependencies
  - [ ] Rule 7: Overly broad try-catch
  - [ ] Rule 8: Using threads instead of processes
  - [ ] Rule 9: Config dict pattern (warning)
- [ ] Create `jn check` CLI command
- [ ] Write tests for each rule
- [ ] Test against all bundled plugins
- [ ] CI/CD integration

**Dependencies:** None (can work standalone)

### 1.3 HTTP Profile System Refinement
**Status:** Basic version done, needs enhancement
**Goal:** Support POST sources, form data, method specifications in profiles

Tasks:
- [ ] Update profile loader to handle method field
- [ ] Support POST with form data (annotations endpoint)
- [ ] Add content_type field to source definitions
- [ ] Update resolve_profile_reference to return method + body
- [ ] Update HTTP plugin to accept method from profile
- [ ] Document POST source patterns
- [ ] Test with GenomOncology annotations endpoint

**Dependencies:** Minor overlap with 1.1 (same profiles), but can work in parallel

---

## Phase 2: Core Protocols & Advanced Formats

### Protocol Plugins
- [x] [HTTP Protocol Plugin](work/01-http-protocol.md) - Basic GET/POST ✅
- [x] [Gmail Protocol Plugin](work/21-gmail-plugin.md) - Read Gmail messages with OAuth2 ✅
- [ ] HTTP Protocol - Advanced (multipart, file uploads, session management)
- [ ] [XLSX Format Plugin](work/02-xlsx-format.md) - Read Excel spreadsheets
- [ ] [S3 Protocol Plugin](work/03-s3-protocol.md) - Read from AWS S3 buckets
- [ ] [FTP Protocol Plugin](work/04-ftp-protocol.md) - Read from FTP servers
- [ ] [Google Sheets Plugin](work/18-google-sheets.md) - Read/write Google Sheets via API

### Profile System
- [x] [RESTful API Profile](work/05-restful-api-profile.md) - Hierarchical structure ✅
- [ ] OpenAPI/Swagger profile auto-generation
- [ ] Profile inheritance and composition
- [ ] Profile validation tool

**Why:** Enable remote data access and common business file formats.

---

## Phase 3: SQL Databases

- [ ] [SQLite Database Plugin](work/06-sqlite-database.md) - Local SQLite with named queries
- [ ] [PostgreSQL Database Plugin](work/07-postgres-database.md) - Remote Postgres with connection pooling
- [ ] [DuckDB Database Plugin](work/13-duckdb-database.md) - Analytical database for OLAP queries

**Why:** Query structured data with SQL, from local files to production databases to analytics workloads.

---

## Phase 4: Display & Shell Integration

- [x] Tabulate Renderer - Pretty tables for display ✅
- [ ] [Table Reading Plugin](work/20-table-reading.md) - Parse HTML/Markdown/ASCII tables to NDJSON
- [ ] [JC Shell Plugins](work/09-jc-shell-plugins.md) - Vendor ls, ps, df parsers from JC project
- [ ] [LS Folder Reader](work/14-ls-folder-reader.md) - Read directory contents as NDJSON
- [ ] [Tail File Follower](work/15-tail-file-follower.md) - Follow log files (tail -f)
- [ ] [Watchdog File Monitor](work/16-watchdog-monitor.md) - Monitor file/directory changes

**Why:** Human-readable output, table ingestion, and real-time system monitoring capabilities.

---

## Phase 5: Data Formats

- [ ] [Parquet Format Plugin](work/17-parquet-format.md) - Read/write columnar Parquet files

**Why:** Big data formats for analytics workloads.

---

## Phase 6: Advanced Protocols

- [ ] [MCP Protocol Plugin](work/19-mcp-protocol.md) - Model Context Protocol for AI tool integration

**Why:** Enable JN to function as data source/sink for AI agents and tools.

---

## Future Considerations

Features that may be developed based on user demand or other development efforts that require them:

### Debug and Explain Mode
**Status:** Design exists (spec/design/debug-explain-mode.md), not prioritized
**Potential Value:** Transparency into profile resolution, filter transformations, and pipeline execution
**When to Revisit:** If users request visibility into how JN processes data, or if debugging complex pipelines becomes a pain point

**Proposed Features:**
- `--explain`: Show profile resolution without executing (which file, parameter substitution)
- `--debug`: Show sample input/output transformations with before/after examples
- `--verbose`: Show pipeline structure, process IDs, command lines
- `--dry-run`: Validate configuration without execution

**Current Position:** Not implementing unless there's clear demand. Prefer to keep JN simple and focused on core ETL functionality.

---

## Completed Milestones

### v0.1 - Foundation (COMPLETE)
- ✅ Core framework with Popen + pipes architecture
- ✅ Plugin discovery system (regex-based, no imports)
- ✅ Format plugins: CSV, JSON, YAML, Markdown, TOML, Tabulate
- ✅ Filter plugin: JQ with generic profile system
- ✅ Protocol plugin: HTTP with streaming
- ✅ Error record pattern (errors as data)
- ✅ Generic profile resolution (any plugin can have profiles)
- ✅ Hierarchical profile structure (_meta + sources)

### Documentation & Design
- ✅ spec/arch/design.md - v5 architecture
- ✅ spec/arch/backpressure.md - Why Popen > async
- ✅ spec/design/http-design.md - HTTP plugin architecture
- ✅ spec/design/rest-api-profiles.md - Profile system
- ✅ spec/design/format-design.md - Format plugins
- ✅ spec/design/genomoncology-api.md - Real-world example
- ✅ spec/design/plugin-checker.md - AST-based checker tool

---

## Next Steps (Parallel Work)

### Track 1: GenomOncology Profile (Design → Implementation)
**Focus:** Complete real-world profile example
**Effort:** Small (1-2 days)
**Skills:** API design, JQ filters, documentation

### Track 2: Plugin Checker (Design → Implementation)
**Focus:** Build AST-based checking tool
**Effort:** Medium (3-5 days)
**Skills:** Python AST, rule engines, CLI tools

### Track 3: XLSX Format Plugin (New Feature)
**Focus:** Read Excel files to NDJSON
**Effort:** Medium (2-4 days)
**Skills:** Excel parsing (openpyxl), streaming, format conversion
**Why independent:** Completely separate from profiles and checker

**OR**

### Track 3 Alternative: Table Reading Plugin (New Feature)
**Focus:** Parse HTML/Markdown/ASCII tables → NDJSON
**Effort:** Medium (3-5 days)
**Skills:** HTML parsing, regex, table detection
**Why independent:** Different domain from profiles/checker
**User value:** Round-trip table workflows (read tables, transform, write tables)
