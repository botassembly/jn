# JN Specification Documentation

This directory contains all specification and design documents for the JN project, organized by implementation status.

## Directory Structure

```
spec/
├── roadmap.md   # Project roadmap (top level for easy access)
├── done/        # Implemented features
└── todo/        # Planned features
```

### `roadmap.md` - Project Roadmap

High-level project roadmap with current status (✅/🚧/🔲). Located at top level for easy access.

### `/done/` - Implemented Features

Specifications for features that have been fully implemented. These documents accurately reflect the current state of the project and serve as reference documentation.

**Core architecture:**
- `arch-design.md` - v5 architecture (PEP 723, UV, NDJSON, Unix pipes)
- `arch-backpressure.md` - Backpressure and streaming architecture
- `addressability.md` - Universal addressing (`address[~format][?params]`)
- `addressability-filtering.md` - Filtering with universal addressing

**Plugin system:**
- `plugin-specification.md` - Plugin development standards
- `plugin-checker.md` - AST-based static analysis
- `checker-whitelist.md` - Plugin checker whitelisting

**Profile system:**
- `profile-usage.md` - Hierarchical profile system
- `gmail-profile-architecture.md` - Gmail profiles
- `restful-api-profile.md` - REST API profiles
- `jq-profile.md` - JQ filter profiles

**Formats:**
- `format-design.md` - Format plugin architecture
- `xlsx-format.md` - Excel format
- `markdown-format.md` - Markdown format
- `toml-format.md` - TOML format

**Protocols:**
- `http-design.md` - HTTP protocol plugin
- `http-protocol.md` - HTTP protocol implementation
- `mcp.md` - Model Context Protocol integration
- `mcp-protocol.md` - MCP implementation
- `gmail-plugin.md` - Gmail plugin

**Commands:**
- `inspect-design.md` - Unified inspect command
- `shell-commands.md` - Shell command handling (custom + jc fallback)
- `jc-shell-plugins.md` - JC shell integration

**Utilities:**
- `jtbl-renderer.md` - Table rendering
- `ls-folder-reader.md` - Folder listing
- `tail-file-follower.md` - File following
- `watchdog-monitor.md` - File monitoring

**Refactors:**
- `addressability-refactor.md` - Addressability refactor
- `mcp-naked-access-refactor.md` - MCP naked access

**Workflows:**
- `workflows-genomoncology-examples.md` - Real-world API examples
- `workflows-gmail-examples.md` - Gmail workflows

### `/todo/` - Planned Features

Specifications for features that are designed but not yet implemented. Developer-ready specs with complete designs and code examples.

**Databases:**
- `duckdb-profiles.md` - **DuckDB profile system (comprehensive spec + code)**
- `duckdb-implementation-guide.md` - **DuckDB developer guide (7-day plan)**
- `duckdb-database.md` - DuckDB overview (points to other specs)
- `sqlite-database.md` - SQLite plugin
- `postgres-database.md` - PostgreSQL plugin

**Protocols:**
- `s3-protocol.md` - S3 protocol plugin
- `ftp-protocol.md` - FTP protocol plugin

**Formats:**
- `parquet-format.md` - Parquet format plugin
- `google-sheets.md` - Google Sheets plugin

**Features:**
- `debug-explain-mode.md` - Debug and explain mode
- `profile-cli.md` - Profile management CLI

## Document Lifecycle

1. **Design** → Create in `/todo/`
2. **Implementation** → Work from spec in `/todo/`
3. **Complete** → Move to `/done/`

Simple and clear: TODO → DONE.

## Quick Reference

### Core Architecture
- **v5 Design**: `done/arch-design.md`
- **Backpressure**: `done/arch-backpressure.md`
- **Addressing**: `done/addressability.md`
- **Plugin System**: `done/plugin-specification.md`

### Development
- **Roadmap**: `wip/roadmap.md`
- **Plugin Checker**: `done/plugin-checker.md`
- **Whitelisting**: `done/checker-whitelist.md`

### Feature Documentation
- **Profiles**: `done/profile-usage.md`
- **Formats**: `done/format-design.md`
- **Protocols**: `done/http-design.md`, `done/mcp.md`
- **Shell Commands**: `done/shell-commands.md`
- **Inspect**: `done/inspect-design.md`

## Contributing

When creating new specifications:

1. **Start with a clear problem statement** - What are we solving?
2. **Define the architecture** - How does it fit with Unix pipes, NDJSON, and PEP 723?
3. **Create work tickets** - Break down implementation into manageable tasks
4. **Place in `/plan/`** - New specs start here
5. **Update as you build** - Move to `/wip/` during implementation if needed
6. **Mark as done** - Move to `/done/` when fully implemented

## Organizational Principles

This reorganization was done to:
- **Improve discoverability** - Easy to find what's implemented vs. planned
- **Maintain accuracy** - Specs match code reality
- **Support development** - Clear roadmap of what's next
- **Reduce confusion** - No ambiguity about feature status

All documents preserve their original content and commit history via `git mv`.
