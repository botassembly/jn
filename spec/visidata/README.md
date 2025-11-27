# VisiData Integration

This folder contains all documentation for JN's VisiData integration.

## Documents

| Document | Description |
|----------|-------------|
| [visidata-integration.md](visidata-integration.md) | Core integration: `jn vd` command |
| [visidata-cheatsheet.md](visidata-cheatsheet.md) | Comprehensive cheat sheet for jn users |
| [visidata-plugin-design.md](visidata-plugin-design.md) | Bidirectional plugin (`vd-jn`) design |
| [view-removal-plan.md](view-removal-plan.md) | Plan to remove `jn view` in favor of VisiData |
| [agentic-data-analysis.md](agentic-data-analysis.md) | Treatise: Agentic Data Analysis with VisiData |

## Quick Start

```bash
# Install VisiData
uv tool install visidata

# Use with jn
jn cat data.csv | jn vd
jn vd https://api.example.com/data~json
```

## Why VisiData?

VisiData replaces the planned `jn view` TUI with a battle-tested tool that provides:

- Sorting, filtering, frequency tables
- Statistics and aggregation
- Multi-sheet operations and joins
- 40+ export formats
- Undo/redo, macros, plotting

See [agentic-data-analysis.md](agentic-data-analysis.md) for the full philosophy.
