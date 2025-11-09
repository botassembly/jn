# JN Next-Gen Implementation Plan

**Approach:** Ground-up rebuild with code harvesting
**Started:** 2025-11-09
**Target:** Production-ready agent-native ETL framework

---

## Progress Overview

**Week 1: Foundation** ⚙️ IN PROGRESS
**Week 2-4: Core Features** 📋 PLANNED
**Week 5-8: Advanced Features** 📋 PLANNED
**Week 9-12: Polish & Ecosystem** 📋 PLANNED

---

## Week 1: Foundation & Core Plugins

### Day 1-2: Project Bootstrap ✅ COMPLETE

- [x] Move old implementation to `oldgen/`
  - Archived 3,500 LOC for reference
  - Tests preserved in `oldgen/tests/`

- [x] Create new directory structure
  ```
  src/jn/          # Core library
  plugins/         # Bundled plugins
  tests/           # New test suite
  docs/harvest/    # Documentation
  ```

- [x] Harvest code patterns
  - `src/jn/detection.py` - Auto-detection logic (160 LOC)
  - `src/jn/subprocess_utils.py` - Safe subprocess patterns (120 LOC)
  - Documentation in `docs/harvest/code-harvest.md`

- [x] CLI framework decision
  - **Click for core** - Lightweight, composable
  - **argparse for plugins** - Zero dependencies
  - Rationale documented in code-harvest.md

- [x] Update package configuration
  - Version: 4.0.0-alpha1
  - Dependencies: Just `click>=8.0.0` (minimal!)
  - Plugins included in package distribution

**Status:** ✅ Complete | **LOC:** 280 | **Tests:** N/A

---

### Day 3-4: Essential Plugins ✅ COMPLETE

- [x] Plugin organization
  ```
  plugins/
    readers/     # File format → NDJSON
    writers/     # NDJSON → file format
    filters/     # NDJSON → NDJSON
    shell/       # Command → NDJSON
    http/        # HTTP/API (future)
  ```

- [x] CSV reader/writer
  - `plugins/readers/csv_reader.py` - CSV/TSV → NDJSON
  - `plugins/writers/csv_writer.py` - NDJSON → CSV/TSV
  - Tests: 5/5 passing

- [x] JSON passthrough
  - `plugins/readers/json_reader.py` - Smart JSON/NDJSON detection
  - Tests: 3/3 passing

- [x] First shell plugin
  - `plugins/shell/ls.py` - Parse ls output to NDJSON
  - Vendored parsing logic from JC concepts
  - Tests: 1/1 passing

- [x] Plugin documentation
  - `docs/harvest/plugin-organization.md` - Strategy & roadmap
  - `plugins/README.md` - Usage guide
  - JC vendoring tiers (15+ commands planned)

**Status:** ✅ Complete | **LOC:** 570 | **Tests:** 9/9 passing (100%)

---

### Day 5: Plugin Discovery System ✅ COMPLETE

- [x] Filesystem scanner (`src/jn/discovery.py`)
  - Scan plugin paths (user → project → package → system)
  - Parse `# META:` headers with regex (no Python imports!)
  - Track modification times for cache invalidation
  - Return plugin registry dict

- [x] Extension registry (`src/jn/registry.py`)
  - Load/save `~/.jn/registry.json`
  - Map extensions to plugins (`.csv` → `csv_reader`)
  - Map URL patterns to plugins (`https://` → `http_get`)
  - Default registry with built-in mappings

- [x] Plugin metadata parser
  - Extract `type`, `handles`, `streaming` from headers
  - Parse examples() docstring (regex, no exec)
  - Read `.schema.json` if exists
  - Cache results with mtime

- [x] Discovery tests
  - `tests/unit/test_discovery.py` - 16 tests
  - `tests/unit/test_registry.py` - 18 tests
  - Test regex parsing
  - Test extension resolution
  - Test modification tracking

**Status:** ✅ Complete | **LOC:** 218 | **Tests:** 34 passing (100%)

---

### Week 1 Summary Goals

- [x] Project structure and foundation
- [x] 4 working plugins with tests
- [x] Plugin discovery without imports
- [x] Extension registry system
- [ ] Foundation for CLI commands

**Week 1 Status:** ✅ Days 1-5 Complete
- LOC: 1,068 code (vs oldgen 3,500 = 69% reduction)
- Core library: detection.py, subprocess_utils.py, discovery.py, registry.py
- Plugins: 4 working (csv_reader, csv_writer, json_reader, ls)
- Tests: 34/34 passing (100%)
- Coverage: 92%

---

## Week 2: Pipeline Execution & CLI

### Day 1-2: Automatic Pipeline Builder ✅ COMPLETE

- [x] Auto-pipeline construction (`src/jn/pipeline.py`)
  - `build_pipeline(args)` - Detect source, filters, target
  - Use detection.py for source/target detection
  - Use registry for extension → plugin mapping
  - Support inline jq expressions
  - Extension-based detection (works even if files don't exist)
  - Command argument parsing for shell plugins

- [x] Pipeline executor (`src/jn/executor.py`)
  - Execute plugins as subprocesses
  - Chain with Unix pipes
  - Stream NDJSON between steps
  - Handle errors gracefully
  - File input redirection for source plugins
  - Proper stdout/stderr capture

- [x] UV integration
  - Execute plugins via `uv run plugin.py`
  - Respect PEP 723 dependencies
  - Automatic fallback to python if UV not available

- [x] Pipeline tests
  - `tests/integration/test_pipeline.py` - 17 tests
  - Test pipeline building (files, URLs, commands)
  - Test jq filter detection
  - Test output format detection
  - Test CSV → NDJSON execution
  - Test error handling

**Status:** ✅ Complete | **LOC:** 300 | **Tests:** 17/17 passing (100%)

---

### Day 3-4: Click-Based CLI ✅ COMPLETE

- [x] Core CLI (`src/jn/cli.py`)
  - Click application setup
  - Common options (--json, --debug, --version)
  - Error handling and exit codes
  - Additional commands: `paths`, `which`

- [x] `jn discover` command
  ```bash
  jn discover                    # List all plugins
  jn discover --type source      # Filter by type
  jn discover --category readers # Filter by category
  jn discover --changed-since    # Recent changes
  jn discover --json             # Machine-readable
  jn discover --verbose          # Detailed output
  ```

- [x] `jn show` command
  ```bash
  jn show csv_reader             # Show plugin details
  jn show csv_reader --examples  # Show examples
  jn show csv_reader --test      # Run plugin tests
  jn show csv_reader --json      # JSON output
  ```

- [x] `jn run` command
  ```bash
  jn run data.csv                # CSV to NDJSON (stdout)
  jn run data.csv output.json    # CSV to JSON file
  jn run data.csv '.name' out.json  # With jq filter
  jn run ls /tmp output.csv      # Shell command → CSV
  jn run --dry-run data.csv      # Show pipeline without executing
  jn run --verbose data.csv      # Show execution details
  ```

- [x] Additional commands
  - `jn paths` - Show plugin search paths
  - `jn which .csv` - Show which plugin handles an extension

- [x] CLI tests (`tests/unit/test_cli.py`)
  - 29 tests covering all commands
  - Test discovery with filters
  - Test show command variations
  - Test run command with real files
  - Test JSON output modes
  - Test error handling

**Status:** ✅ Complete | **LOC:** 203 | **Tests:** 29/29 passing (100%)

---

### Day 5: More Core Plugins ✅ COMPLETE

- [x] JQ filter wrapper (`plugins/filters/jq_filter.py`)
  - Execute jq subprocess
  - Pass query as argument
  - Stream NDJSON through
  - Support for field extraction, filtering, and transformations
  - Built-in tests (3/3 passing)

- [x] JSON writer (`plugins/writers/json_writer.py`)
  - NDJSON → JSON array
  - Pretty-print option (configurable indentation)
  - Compact mode support
  - Built-in tests (3/3 passing)

- [x] HTTP GET plugin (`plugins/http/http_get.py`)
  - Uses curl subprocess for HTTP requests
  - Support headers and timeout
  - Parse JSON responses (arrays and objects)
  - Falls back to text output for non-JSON
  - Structure tests (3/3 passing)

- [x] Plugin integration
  - All plugins discovered automatically
  - Full pipeline integration (NDJSON → jq filter → JSON)
  - CLI integration verified

**Status:** ✅ Complete | **LOC:** 400 | **Plugins:** 3 new, 7 total

---

### Week 2 Summary ✅ COMPLETE

- [x] Full pipeline execution working
- [x] Comprehensive CLI commands (discover, show, run, paths, which)
- [x] 7 working plugins
- [x] End-to-end integration tests
- [x] 80/80 tests passing (100%)
- [x] 71% code coverage

**Final Status:**
- LOC: 1,971 (vs oldgen 3,500 = 44% reduction!)
- Plugins: 7 working
- Tests: 80/80 passing
- Coverage: 71%

---

## Week 3: Shell Commands & Advanced Features

### Day 1-2: Shell Command Plugins ✅ COMPLETE

Vendor key commands from JC concepts:

- [x] `plugins/shell/ps.py` - Process listing (180 LOC)
  - Parse `ps aux` output
  - Fields: pid, ppid, user, cpu_percent, mem_percent, status, command
  - Built-in tests (5/5 passing)

- [x] `plugins/shell/find.py` - File search (200 LOC)
  - Parse `find` output with structured format
  - Fields: path, name, type, size, mode, user, group, mtime
  - Size conversions (KB, MB)
  - Built-in tests (5/5 passing)

- [x] `plugins/shell/env.py` - Environment variables (120 LOC)
  - Parse `env` output
  - Fields: name, value
  - Built-in tests (5/5 passing)

- [x] `plugins/shell/df.py` - Filesystem info (200 LOC)
  - Parse `df -k` output
  - Fields: filesystem, size, used, available, use_percent, mounted_on
  - Multiple size units (1K, MB, GB)
  - Built-in tests (5/5 passing)

**Status:** ✅ Complete | **LOC:** 700 | **Plugins:** 4 new, 11 total
**All plugin tests passing!**

---

### Day 3-4: Network Shell Commands ✅ COMPLETE

- [x] `plugins/shell/ping.py` - Network connectivity (200 LOC)
  - Parse ping output to structured JSON
  - Fields: host, packets_transmitted, packets_received, packet_loss_percent, replies[], rtt_min/avg/max/mdev_ms
  - Individual reply details (bytes, icmp_seq, ttl, time_ms)
  - Timeout and error handling
  - Structure tests (3/3 passing)

- [x] `plugins/shell/netstat.py` - Network connections (220 LOC)
  - Parse netstat output
  - Fields: protocol, recv_q, send_q, local_address, local_port, foreign_address, foreign_port, state
  - Support for process info (pid, program) when available
  - Flexible header parsing
  - Structure tests (3/3 passing)

- [x] `plugins/shell/dig.py` - DNS queries (230 LOC)
  - Parse dig output to structured JSON
  - Fields: domain, record_type, answers[], authority[], additional[]
  - Answer records with name, ttl, class, type, data
  - Query statistics (query_time_ms, server, when, msg_size)
  - Support for custom DNS servers
  - Structure tests (3/3 passing)

**Status:** ✅ Complete | **LOC:** 650 | **Plugins:** 3 new, 14 total
**All plugin structure tests passing!**

---

### Day 5: Advanced CLI Features

- [ ] `jn create` command
  ```bash
  jn create filter my-filter --query 'select(.amount > 100)'
  jn create source my-api --template http-json
  ```

- [ ] `jn test` command
  ```bash
  jn test csv_reader              # Run plugin tests
  jn test csv_reader --verbose    # Detailed output
  ```

- [ ] `jn validate` command
  ```bash
  jn validate my-plugin.py        # Lint + dry-run
  ```

**Target:** 250 LOC | **Tests:** 10-12 tests

---

### Week 3 Summary Goals

- [ ] 10+ shell command plugins
- [ ] Advanced CLI (create, test, validate)
- [ ] Rich plugin ecosystem

**Target Status:**
- LOC: 3,250
- Plugins: 14
- Tests: 60+ passing

---

## Week 4: Testing & Documentation

### Day 1-2: Test Infrastructure

- [ ] Port test patterns from oldgen
  - `tests/conftest.py` - CliRunner, fixtures
  - `tests/helpers.py` - Test data generators
  - Integration test structure

- [ ] Comprehensive test coverage
  - All plugins: 100% coverage
  - Core: 90%+ coverage
  - CLI: 80%+ coverage

- [ ] Plugin test runner
  ```bash
  make test-plugins    # Test all plugins
  make test-core       # Test core library
  make test-cli        # Test CLI
  ```

**Target:** 500 LOC (tests) | **Coverage:** 90%+

---

### Day 3-5: Documentation

- [ ] README.md - Quick start guide
- [ ] docs/architecture.md - Copy nextgen-redesign.md
- [ ] docs/plugins.md - Plugin authoring guide
- [ ] docs/agents.md - Guide for agents
- [ ] docs/examples/ - Working examples
  - basic-etl.md
  - agent-workflow.md
  - shell-commands.md

- [ ] Plugin templates
  - `templates/source_basic.py`
  - `templates/filter_basic.py`
  - `templates/target_basic.py`

**Target:** 2,000 LOC (docs)

---

### Week 4 Summary Goals

- [ ] 90%+ test coverage
- [ ] Complete documentation
- [ ] Plugin templates ready

**Target Status:**
- LOC: 3,750 (code) + 2,500 (docs/tests)
- Plugins: 14
- Tests: 100+ passing
- Coverage: 90%+

---

## Weeks 5-8: Advanced Features & Polish

### Week 5: Advanced Readers/Writers

- [ ] Excel reader/writer (openpyxl)
- [ ] YAML reader/writer
- [ ] XML reader/writer
- [ ] Parquet reader/writer
- [ ] Advanced filters (aggregations, group-by)

**Target:** 800 LOC | **Plugins:** 20

---

### Week 6: Database & Cloud

- [ ] Database plugins (postgres, mysql, sqlite)
- [ ] S3 plugins (read/write)
- [ ] HTTP POST/PUT plugins
- [ ] Streaming aggregations

**Target:** 600 LOC | **Plugins:** 25

---

### Week 7-8: Agent Optimization

- [ ] JSON output mode for all commands
- [ ] Example extraction (read without exec)
- [ ] Schema file support
- [ ] Performance optimization
  - Cache plugin discovery (<10ms)
  - Optimize UV subprocess spawning
  - Benchmark pipelines

**Target:** 400 LOC | **Performance:** <10ms discovery, >10k records/sec

---

## Weeks 9-12: Ecosystem & Release

### Week 9: Plugin Distribution

- [ ] Plugin packaging (pip installable)
- [ ] Entry points for plugins
- [ ] Plugin registry/directory
- [ ] Community templates

---

### Week 10: Advanced CLI

- [ ] `jn cat` (exploration command)
- [ ] `jn put` (output command)
- [ ] `jn shape` (schema inference)
- [ ] Shell completions (bash, zsh, fish)

---

### Week 11: Migration & Compatibility

- [ ] Migration tool from oldgen
- [ ] Backward compatibility mode (if needed)
- [ ] Migration guide documentation

---

### Week 12: Release Preparation

- [ ] Security audit
- [ ] Performance benchmarks
- [ ] Release documentation
- [ ] Packaging for PyPI
- [ ] GitHub release

---

## Success Metrics

### Code Quality
- [ ] <5,000 LOC total (vs oldgen 3,500)
- [ ] 90%+ test coverage
- [ ] Zero security vulnerabilities
- [ ] All plugins self-testing

### Performance
- [ ] <10ms plugin discovery (cached)
- [ ] <100ms pipeline overhead per step
- [ ] >10k records/sec throughput

### Functionality
- [ ] 25+ working plugins
- [ ] Full CLI feature parity
- [ ] Agent-friendly design validated

### Documentation
- [ ] Complete API documentation
- [ ] Plugin authoring guide
- [ ] Agent integration guide
- [ ] 10+ working examples

---

## Current Status (2025-11-09)

### ✅ Completed
- **Week 1, Days 1-5: Foundation Complete**
  - Foundation and core plugins
  - Plugin discovery system (regex-based, no imports)
  - Extension registry with caching
  - 4 working plugins (csv_reader, csv_writer, json_reader, ls)
  - Code harvesting and organization
  - Package configuration
  - Plugin organization strategy

### ✅ Completed
- **Week 1, Days 1-5: Foundation Complete**
  - Foundation and core plugins
  - Plugin discovery system (regex-based, no imports)
  - Extension registry with caching
  - 4 working plugins (csv_reader, csv_writer, json_reader, ls)

- **Week 2, Days 1-2: Pipeline System Complete**
  - Automatic pipeline builder
  - Subprocess-based executor with Unix pipes
  - UV integration for PEP 723 dependencies
  - End-to-end CSV→NDJSON execution

- **Week 2, Days 3-4: CLI Complete**
  - Full Click-based CLI
  - Commands: discover, show, run, paths, which
  - JSON and verbose output modes
  - Comprehensive CLI tests

- **Week 2, Day 5: Additional Plugins Complete**
  - JQ filter wrapper (jq_filter)
  - JSON writer (json_writer)
  - HTTP GET (http_get)
  - **Week 2 Complete!** 🎉

- **Week 3, Days 1-2: Shell Commands Complete**
  - Process listing (ps)
  - File search (find)
  - Environment variables (env)
  - Disk space (df)
  - **4 new shell plugins, 11 total!**

### 🔄 In Progress
- Week 3, Days 3-4: Network shell commands

### 📋 Next Up
- Network command plugins (dig, netstat, ping)
- Advanced CLI features
- Performance optimizations

### Metrics
- **LOC:** 2,671 (code) + 400 (docs)
- **Core modules:** 7 (detection, subprocess_utils, discovery, registry, pipeline, executor, cli)
- **Plugins:** 11 working
  - Readers: csv_reader, json_reader
  - Writers: csv_writer, json_writer
  - Filters: jq_filter
  - Shell: ls, ps, find, env, df
  - HTTP: http_get
- **Tests:** 80/80 passing (100%)
- **Coverage:** 71%
- **Dependencies:** 1 (click only!)
- **Code Reduction:** 24% smaller than oldgen!

---

## Daily Progress Log

### 2025-11-09 - Week 1 & 2 Days 1-2

**Week 1 (Complete):**
- ✅ Moved oldgen/ code
- ✅ Created new structure
- ✅ Harvested detection and subprocess utils
- ✅ Created 4 working plugins
- ✅ Organized plugins by category
- ✅ Updated pyproject.toml
- ✅ Created implementation plan
- ✅ Implemented plugin discovery system (src/jn/discovery.py - 110 LOC)
- ✅ Implemented extension registry (src/jn/registry.py - 108 LOC)
- ✅ Created comprehensive tests (34 tests, 92% coverage)
- ✅ Week 1 complete!

**Week 2 Days 1-2 (Complete):**
- ✅ Implemented automatic pipeline builder (src/jn/pipeline.py - 150 LOC)
  - Auto-detect sources (files, URLs, commands)
  - jq expression detection
  - Output format detection
  - Command argument parsing
- ✅ Implemented pipeline executor (src/jn/executor.py - 155 LOC)
  - Subprocess execution with Unix pipes
  - UV integration for PEP 723 dependencies
  - File I/O redirection
  - Error handling
- ✅ Created pipeline integration tests (17 tests, 100% passing)
- ✅ End-to-end CSV→NDJSON execution verified

**Week 2 Days 3-4 (Complete):**
- ✅ Implemented Click-based CLI (src/jn/cli.py - 203 LOC)
  - Core CLI application with Click
  - `jn discover` - List plugins with filtering (type, category, changed-since)
  - `jn show` - Display plugin details, examples, run tests
  - `jn run` - Execute pipelines with dry-run and verbose modes
  - `jn paths` - Show plugin search paths
  - `jn which` - Show which plugin handles an extension
  - JSON output mode for all commands
- ✅ Created comprehensive CLI tests (29 tests, 100% passing)
- ✅ Manual CLI testing verified
- ✅ End-to-end pipeline execution via CLI verified

**Week 2 Day 5 (Complete):**
- ✅ Implemented jq_filter plugin (plugins/filters/jq_filter.py - 200 LOC)
  - jq subprocess wrapper
  - Field extraction, filtering, transformations
  - Built-in tests (3/3 passing)
- ✅ Implemented json_writer plugin (plugins/writers/json_writer.py - 160 LOC)
  - NDJSON → JSON array conversion
  - Pretty-print and compact modes
  - Built-in tests (3/3 passing)
- ✅ Implemented http_get plugin (plugins/http/http_get.py - 170 LOC)
  - curl-based HTTP fetching
  - JSON response parsing
  - Header and timeout support
- ✅ Verified all 7 plugins discovered
- ✅ Tested end-to-end pipelines:
  - NDJSON → JSON conversion
  - NDJSON → jq filter → NDJSON
  - CSV → NDJSON → jq filter → JSON
- ✅ All 80 tests passing
- ✅ **Week 2 Complete!** 🎉

**Week 3 Days 1-2 (Complete):**
- ✅ Implemented ps plugin (plugins/shell/ps.py - 180 LOC)
  - Parse ps aux output
  - Fields: pid, ppid, user, cpu_percent, mem_percent, status, command
  - Built-in tests (5/5 passing)
- ✅ Implemented find plugin (plugins/shell/find.py - 200 LOC)
  - Parse find output with structured format (-printf)
  - Fields: path, name, type, size, mode, user, group, mtime
  - Size conversions (KB, MB)
  - Built-in tests (5/5 passing)
- ✅ Implemented env plugin (plugins/shell/env.py - 120 LOC)
  - Parse environment variables
  - Simple name/value pairs
  - Built-in tests (5/5 passing)
- ✅ Implemented df plugin (plugins/shell/df.py - 200 LOC)
  - Parse df -k output
  - Fields: filesystem, size, used, available, use_percent, mounted_on
  - Multiple size units (1K, MB, GB)
  - Built-in tests (5/5 passing)
- ✅ All 11 plugins now discovered
- ✅ Tested pipelines:
  - env → jq filter (select PATH variable)
  - df → jq filter (select full filesystems)
  - ps → jq filter → JSON
- ✅ All 80 tests still passing
- 🔄 Next: Network shell commands (dig, netstat, ping)

---

## Notes & Decisions

### Architecture Decisions
1. **Click over Typer** - Lighter, more composable
2. **argparse for plugins** - Zero dependencies
3. **Function-based, not classes** - Duck typing, simple
4. **Regex-based discovery** - No imports needed
5. **Bundled plugins** - Immediate value out of box

### JC Vendoring Strategy
- Not copying code verbatim
- Reimplementing as CLI plugins
- Attribution in headers
- MIT license compatible
- Tiers: 15+ commands over 3 weeks

### Key Differences from oldgen
- No Pydantic models
- No import-based config
- No 4-concept registry
- Plugins are standalone CLIs
- UV manages dependencies per-plugin

---

## Risk Mitigation

### Risk: UV dependency issues
**Mitigation:** Fallback to venv, document requirements

### Risk: Performance regression
**Mitigation:** Benchmark each phase, optimize hot paths

### Risk: Plugin API instability
**Mitigation:** Version plugin interface, support multiple versions

### Risk: Discovery complexity
**Mitigation:** Keep regex patterns simple, cache aggressively

---

## References

- `spec/arch/nextgen-redesign.md` - Core architecture
- `spec/arch/nextgen-groundup.md` - Original ground-up plan
- `docs/harvest/code-harvest.md` - Code harvesting analysis
- `docs/harvest/plugin-organization.md` - Plugin strategy
- Kelly Brazil's JC project - Parsing inspiration

---

**Last Updated:** 2025-11-09
**Current Phase:** Week 3, Days 1-2 Complete
**Milestone Reached:** 11 plugins including 5 shell commands! 🎉
