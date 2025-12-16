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

## Demo Conversion Status

All demos have been converted to the integration test pattern:

| Demo | Status | Notes |
|------|--------|-------|
| csv-filtering | ✅ Done | |
| join | ✅ Done | |
| shell-commands | ✅ Done | Uses `jc` for parsing |
| glob | ✅ Done | Creates test data dynamically |
| http-api | ✅ Done | Uses local mock data |
| xlsx-files | ✅ Done | |
| table-rendering | ✅ Done | |
| markdown-skills | ✅ Done | Pattern reference |
| adapter-merge | ✅ Done | |
| code-lcov | ✅ Done | |
| folder-profiles | ✅ Done | Simplified output with jq |
| jn-grep | ✅ Done | Creates deterministic test data |
| json-editing | ✅ Done | Simplified to 8 examples |
| todo | ✅ Done | Uses fixed XIDs, strips colors |
| zq-functions | ✅ Done | Only deterministic functions |
| genomoncology | ✅ Done | Shows profile config (no API calls) |

All 16 demos pass `./run_all.sh`

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
