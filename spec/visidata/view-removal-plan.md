# JN View Migration Plan

**Date:** 2025-11-25
**Status:** Completed
**Rationale:** VisiData provides all planned `jn view` functionality and more

---

## Summary

The `jn view` command has been repurposed to launch VisiData instead of the Textual-based viewer. Both `jn view` and `jn vd` now launch VisiData as a separate process.

**Key change:** Rather than removing `jn view`, we kept it as an alias for `jn vd`.

---

## What Changed

### Repurposed Files

```
src/jn/cli/commands/view.py   # Now launches VisiData (was Textual-based)
src/jn/cli/commands/vd.py     # VisiData command (unchanged)
```

### Files to Remove (Optional Cleanup)

The Textual-based viewer plugin is no longer used:

```
jn_home/plugins/formats/json_viewer.py  # The Textual-based viewer plugin
```

### Dependencies to Remove

Remove from `pyproject.toml` (if not used elsewhere):
- `textual` (check if other commands use it)

---

## Migration for Users

Both commands work identically:

| Command | Description |
|---------|-------------|
| `jn view data.json` | Opens VisiData |
| `jn vd data.json` | Opens VisiData |
| `jn cat data.csv \| jn view` | Pipes to VisiData |
| `jn cat data.csv \| jn vd` | Pipes to VisiData |

### Removed Options

The following Textual-specific options were removed from `jn view`:
- `--depth` - VisiData uses `(` to expand nested data
- `--start-at` - VisiData uses `zr N` to jump to row N

### Feature Mapping

| Old jn view Feature | VisiData Equivalent |
|---------------------|---------------------|
| Tree navigation | `z^Y` (pyobj-cell) or `(` expand |
| Record n/p navigation | `j/k` row navigation |
| Jump to record N | `zr N` |
| Search | `/` or `g/` |
| Bookmarks | `s` select, `"` open as sheet |
| Help | `Ctrl+H` |

---

## Cleanup Steps

### Phase 1: Remove Unused Code (Optional)

1. **Remove unused viewer plugin:**
   ```bash
   rm jn_home/plugins/formats/json_viewer.py
   ```

2. **Update pyproject.toml:**
   Remove textual dependency if not used elsewhere

3. **Run tests:**
   ```bash
   make test
   ```

### Phase 2: Spec Cleanup

1. **Archive old specs:**
   ```bash
   mkdir -p spec/archive/textual-viewer
   mv spec/done/single-record-json-viewer.md spec/archive/textual-viewer/
   mv spec/done/textual-stdin-architecture.md spec/archive/textual-viewer/
   mv spec/todo/json-viewer-pro-design.md spec/archive/textual-viewer/
   mv spec/wip/viewer-ux-brainstorm.md spec/archive/textual-viewer/
   mv spec/wip/viewer-v2-design.md spec/archive/textual-viewer/
   ```

2. **Update CLAUDE.md:**
   Remove references to Textual TUI architecture

3. **Update any README or docs:**
   Search for Textual references and update

---

## Grep Commands for Cleanup

```bash
# Find all references to textual
grep -r "textual" --include="*.md" --include="*.py" .

# Find all references to json_viewer
grep -r "json_viewer" --include="*.md" --include="*.py" .

# Find viewer-related specs
find spec -name "*viewer*" -o -name "*textual*"
```

---

## Architecture Notes

### Why VisiData as a Separate Process?

1. **GPL v3 License:** VisiData is GPL v3; keeping it as a subprocess avoids any licensing concerns with JN's MIT license
2. **No Dependencies:** No need to add visidata to pyproject.toml
3. **Clean Exit:** VisiData manages its own terminal state
4. **Parallel Execution:** Pipeline stages run concurrently

### Process Flow

```
jn cat source | [jn filter] | vd -f jsonl -
     │              │            │
     └── Phase 1    └── Phase 2  └── VisiData
         (read)        (filter)      (display)
```

---

## Checklist

- [x] Modify `src/jn/cli/commands/view.py` to launch VisiData
- [x] Keep `jn view` as alias for `jn vd`
- [x] Remove Textual-specific options (--depth, --start-at)
- [x] Add VisiData quick reference to help text
- [ ] Remove `jn_home/plugins/formats/json_viewer.py` (optional)
- [ ] Check and update `pyproject.toml` (optional)
- [ ] Archive old spec documents
- [ ] Update CLAUDE.md
- [ ] Run full test suite
