# JN Zig Refactor Documentation

This folder contains the architecture and design documentation for the JN Zig refactor - migrating JN from Python to a pure Zig core with Python plugin extensibility.

## Document Inventory

### Implementation Plan

| Document | Purpose |
|----------|---------|
| [00-plan.md](00-plan.md) | **Start here.** Phase-based implementation plan with deliverables and document references |

### Architecture Documents

| # | Document | Purpose |
|---|----------|---------|
| 01 | [01-vision.md](01-vision.md) | Why JN exists, core philosophy, design principles, non-goals |
| 02 | [02-architecture.md](02-architecture.md) | System overview, component responsibilities, data flow, concurrency model |
| 03 | [03-users-guide.md](03-users-guide.md) | How to use JN: commands, address syntax, common workflows |
| 04 | [04-project-layout.md](04-project-layout.md) | Repository structure, where components live, build system |
| 05 | [05-plugin-system.md](05-plugin-system.md) | Plugin roles, modes, metadata, discovery, interface |
| 06 | [06-matching-resolution.md](06-matching-resolution.md) | Address parsing, pattern matching, multi-stage resolution |
| 07 | [07-profiles.md](07-profiles.md) | Profile types, hierarchy, environment substitution, CLI |
| 08 | [08-streaming-backpressure.md](08-streaming-backpressure.md) | Pipes, backpressure, SIGPIPE, memory characteristics |
| 09 | [09-joining-operations.md](09-joining-operations.md) | jn-join hash join, jn-merge concatenation, use cases |
| 10 | [10-python-plugins.md](10-python-plugins.md) | PEP 723 plugins, bundled plugins, writing Python plugins |

## Reading Order

### For New Contributors
1. [01-vision.md](01-vision.md) - Understand why JN exists
2. [02-architecture.md](02-architecture.md) - Learn the component model
3. [04-project-layout.md](04-project-layout.md) - Know where things go
4. [05-plugin-system.md](05-plugin-system.md) - Understand the core abstraction

### For Understanding Performance
- [08-streaming-backpressure.md](08-streaming-backpressure.md) - The key insight

### For Plugin Development
1. [05-plugin-system.md](05-plugin-system.md) - Plugin interface
2. [10-python-plugins.md](10-python-plugins.md) - Python specifics
3. [06-matching-resolution.md](06-matching-resolution.md) - Pattern matching

### For Implementation
1. [00-plan.md](00-plan.md) - Phase-by-phase plan
2. Follow document references in each phase

## Document Conventions

Each document follows a consistent structure:

1. **Purpose** - One-sentence summary
2. **Core Concepts** - The "what"
3. **How It Works** - The "how" (conceptually, not code)
4. **Design Decisions** - Trade-offs and rationale
5. **See Also** - Related documents

Documents are conceptual - they explain architecture and design, not implementation details. For implementation, refer to the source code in the locations specified by [04-project-layout.md](04-project-layout.md).

## Key Locations

| Component | Location |
|-----------|----------|
| Shared Zig libraries | `libs/zig/` |
| Zig CLI tools | `tools/zig/` |
| Zig plugins | `plugins/zig/` |
| Python plugins | `plugins/python/` |
| ZQ filter engine | `zq/` |
| Bundled defaults | `jn_home/` |
