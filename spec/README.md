# JN Specification Documentation

This directory contains all specification and design documents for the JN project, organized by implementation status.

## Directory Structure

### `/done/` - Fully Implemented Specifications

Contains specifications and design documents for features that have been fully or almost fully implemented in the codebase. These documents accurately reflect the current state of the project and serve as reference documentation.

**Key documents:**
- `arch-design.md` - Core v5 architecture (PEP 723, UV, NDJSON, Unix pipes)
- `arch-backpressure.md` - Backpressure and streaming architecture
- `addressability.md` - Universal addressing system (`address[~format][?params]`)
- `plugin-specification.md` - Plugin development standards
- `plugin-checker.md` - AST-based static analysis tool
- `profile-usage.md` - Hierarchical profile system
- `format-design.md` - Format plugin architecture
- `http-design.md` - HTTP protocol plugin
- `mcp.md` - Model Context Protocol integration
- `gmail-profile-architecture.md` - Gmail plugin architecture
- `shell-commands.md` - Shell command handling (custom + jc fallback)
- `inspect-design.md` - Unified inspect command
- `checker-whitelist.md` - Plugin checker whitelisting mechanism

**Completed work tickets:**
- `work-01-http-protocol.md` through `work-23-mcp-naked-access-refactor.md`
- See individual files for implementation details

**Example workflows:**
- `workflows-genomoncology-examples.md` - Real-world API integration examples
- `workflows-gmail-examples.md` - Gmail data extraction workflows

### `/wip/` - Work in Progress

Contains living documents that are actively being updated as the project evolves. These documents contain both completed and planned items.

**Documents:**
- `roadmap.md` - Project roadmap with current status (✅/🚧/🔲)
- `design-index.md` - Index of all design documents (needs status updates)

### `/plan/` - Planned Features

Contains specifications for features that have been designed but not yet implemented. These documents represent the project's future direction.

**Planned designs:**
- `debug-explain-mode.md` - Debug and explain mode for pipelines
- `profile-cli.md` - Profile management CLI commands

**Planned work tickets:**
- `work-03-s3-protocol.md` - S3 protocol plugin
- `work-04-ftp-protocol.md` - FTP protocol plugin
- `work-06-sqlite-database.md` - SQLite plugin
- `work-07-postgres-database.md` - PostgreSQL plugin
- `work-13-duckdb-database.md` - DuckDB plugin
- `work-17-parquet-format.md` - Parquet format plugin
- `work-18-google-sheets.md` - Google Sheets plugin

## Document Lifecycle

As features are implemented, documents should be moved between directories:

1. **Initial design** → Create in `/plan/`
2. **Implementation starts** → Move to `/wip/` (if it's a large, multi-phase feature)
3. **Implementation complete** → Move to `/done/`

For simple features, documents can move directly from `/plan/` to `/done/` upon completion.

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
