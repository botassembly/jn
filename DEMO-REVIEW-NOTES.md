# Demo Improvements - Review Notes

**Branch:** `claude/improve-markdown-demo-4msAK`
**Commits:** 4 (from cf794a9)

---

## What Was Done

### 1. New markdown-skills demo
- `demos/markdown-skills/run.sh` - Integration test for markdown plugin
- `demos/markdown-skills/input.md` - Sample API reference doc
- `demos/markdown-skills/expected.txt` - Golden output for diffing
- Shows: frontmatter extraction, heading parsing, zq filtering

### 2. SessionStart hook
- `.claude/settings.json` - Auto-setup jn on session start
- Downloads release or falls back to `make build`
- Sets PATH so `jn` commands just work

### 3. Demo guidelines
- `demos/good-demo-bad-demo-guidelines.md`
- Integration test pattern (expected.txt vs actual.txt)
- 10 simplification principles
- Checklist for new demos

---

## To Validate

### SessionStart Hook
```bash
# In a fresh Claude Code session on jn project:
# 1. Should auto-download/build jn
# 2. Should show "jn X.X.X ready"
# 3. Commands like `jn --version` should work immediately
```

### Demo Integration Test
```bash
cd demos/markdown-skills
source ../../dist/activate.sh  # or rely on hook
./run.sh
# Should show: PASS: Output matches expected
```

---

## Cleanup TODO: Convert Other Demos

Each demo in `demos/` should be converted to the integration test pattern:

| Demo | Status | Notes |
|------|--------|-------|
| markdown-skills | ✅ Done | New pattern reference |
| csv-filtering | ❌ TODO | Rename run_examples.sh → run.sh |
| join | ❌ TODO | Add expected.txt |
| shell-commands | ❌ TODO | Requires `jc` - note in expected |
| http-api | ❌ TODO | May need mocking for determinism |
| glob | ❌ TODO | |
| xlsx-files | ❌ TODO | |
| table-rendering | ❌ TODO | |
| code-lcov | ❌ TODO | |
| adapter-merge | ❌ TODO | |

### Conversion steps for each:
1. Rename `run_examples.sh` → `run.sh`
2. Rename sample data → `input.*`
3. Wrap output in `{ ... } > actual.txt`
4. Add diff check at end
5. Run once, `cp actual.txt expected.txt`
6. Add `.gitignore` with `actual.txt`
7. Verify `./run.sh` shows PASS

### Update run_all.sh
- Change script names from `run_examples.sh` to `run.sh`
- All demos should exit 0 on PASS, 1 on FAIL

---

## Files Changed

```
.claude/settings.json                    (new)
demos/good-demo-bad-demo-guidelines.md   (new)
demos/markdown-skills/run.sh             (new)
demos/markdown-skills/input.md           (new)
demos/markdown-skills/expected.txt       (new)
demos/markdown-skills/.gitignore         (new)
demos/README.md                          (updated)
demos/run_all.sh                         (updated)
```
