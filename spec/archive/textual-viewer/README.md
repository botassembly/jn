# Archived: Textual-based Viewer Specs

**Archived:** 2025-11-26
**Reason:** Replaced with VisiData integration

These specs documented the Textual-based `jn view` command which has been
replaced by VisiData. The `jn view` and `jn vd` commands now launch VisiData
as a separate process.

## Archived Files

| File | Description |
|------|-------------|
| `single-record-json-viewer.md` | Original single-record viewer design |
| `textual-stdin-architecture.md` | How to handle stdin + TUI conflict |
| `viewer-v2-design.md` | V2 viewer with tree navigation |
| `viewer-ux-brainstorm.md` | UX exploration for viewer |
| `json-viewer-pro-design.md` | Pro version with advanced features |

## Replacement

See `spec/visidata/` for the VisiData integration that replaces this:
- `visidata-integration.md` - Core integration docs
- `visidata-cheatsheet.md` - Feature mapping from planned viewer to VisiData
- `view-removal-plan.md` - Migration plan

## Why VisiData?

VisiData provides all planned features and more:
- Sorting, filtering, aggregation built-in
- Frequency tables (`Shift+F`)
- Column statistics (`Shift+I`)
- Nested JSON expansion (`(` and `)`)
- Save to multiple formats
- Extensible via Python plugins
