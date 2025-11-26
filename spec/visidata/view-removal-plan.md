# JN View Removal Plan

**Date:** 2025-11-25
**Status:** Planned
**Rationale:** VisiData provides all planned `jn view` functionality and more

---

## Summary

Remove the Textual-based `jn view` command and related code in favor of VisiData integration via `jn vd`. VisiData is a mature, feature-rich tool that exceeds our original design goals.

---

## What's Being Removed

### Code Files

```
src/jn/cli/commands/view.py          # The view command
jn_home/plugins/formats/json_viewer.py  # The Textual-based viewer plugin
```

### Spec Documents (Archive or Delete)

```
spec/done/single-record-json-viewer.md    # MVP viewer design
spec/done/textual-stdin-architecture.md   # Textual stdin handling
spec/todo/json-viewer-pro-design.md       # Pro viewer design
spec/wip/viewer-ux-brainstorm.md          # UX brainstorm
spec/wip/viewer-v2-design.md              # Viewer v2 design
```

### Dependencies

Remove from `pyproject.toml` (if not used elsewhere):
- `textual` (check if other commands use it)
- Any viewer-specific dependencies

---

## What's Being Kept

### VisiData Integration

```
src/jn/cli/commands/vd.py           # jn vd command
spec/visidata/                       # All VisiData documentation
```

### Main.py Updates

The `jn vd` command is already registered. Remove `jn view`:

```python
# Remove these lines from main.py:
from .commands.view import view
cli.add_command(view)
```

---

## Migration Guide

### For Users

| Old Command | New Command |
|-------------|-------------|
| `jn view data.json` | `jn vd data.json` |
| `jn cat data.csv \| jn view` | `jn cat data.csv \| jn vd` |
| `jn view --filter '.x > 10'` | `jn vd --filter '.x > 10'` |

### Feature Mapping

| jn view Feature | VisiData Equivalent |
|-----------------|---------------------|
| Tree navigation | `z^Y` (pyobj-cell) or `(` expand |
| Record n/p navigation | `j/k` row navigation |
| Jump to record | `zr N` |
| Search | `/` or `g/` |
| Bookmarks | `s` select, `"` open as sheet |
| Help | `Ctrl+H` |

---

## Removal Steps

### Phase 1: Deprecation Notice (Optional)

If backward compatibility is important:

1. Add deprecation warning to `jn view`:
   ```python
   click.echo("Warning: 'jn view' is deprecated. Use 'jn vd' instead.", err=True)
   ```
2. Keep for 1-2 releases

### Phase 2: Code Removal

1. **Remove view command:**
   ```bash
   rm src/jn/cli/commands/view.py
   ```

2. **Remove viewer plugin:**
   ```bash
   rm jn_home/plugins/formats/json_viewer.py
   ```

3. **Update main.py:**
   Remove view imports and registration

4. **Update pyproject.toml:**
   Remove textual dependency if not used elsewhere

5. **Run tests:**
   ```bash
   make test
   ```

### Phase 3: Spec Cleanup

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
   Remove references to `jn view` and Textual TUI architecture

3. **Update any README or docs:**
   Search for "jn view" references and update to "jn vd"

### Phase 4: Documentation Update

1. Update main README with VisiData info
2. Add migration note to changelog
3. Update any tutorials or examples

---

## Grep Commands for Cleanup

```bash
# Find all references to jn view
grep -r "jn view" --include="*.md" --include="*.py" .

# Find all references to textual
grep -r "textual" --include="*.md" --include="*.py" .

# Find all references to json_viewer
grep -r "json_viewer" --include="*.md" --include="*.py" .

# Find viewer-related specs
find spec -name "*viewer*" -o -name "*textual*"
```

---

## Risks & Mitigations

### Risk: Users depend on jn view

**Mitigation:**
- `jn vd` provides same functionality
- Document migration path
- Optional deprecation period

### Risk: Textual used elsewhere

**Mitigation:**
- Check before removing dependency
- `grep -r "textual" src/`

### Risk: Tree view for nested JSON

**Mitigation:**
- VisiData's `z^Y` (pyobj-cell) provides similar functionality
- Document this clearly in cheat sheet

---

## Timeline

1. **Immediate:** Create this plan, document VisiData alternatives
2. **Next release:** Add deprecation warning (optional)
3. **Following release:** Remove code and specs

---

## Checklist

- [ ] Remove `src/jn/cli/commands/view.py`
- [ ] Remove `jn_home/plugins/formats/json_viewer.py`
- [ ] Update `src/jn/cli/main.py`
- [ ] Check and update `pyproject.toml`
- [ ] Archive old spec documents
- [ ] Update CLAUDE.md
- [ ] Search and update all "jn view" references
- [ ] Run full test suite
- [ ] Update changelog
