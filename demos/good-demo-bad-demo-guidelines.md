# Good Demo / Bad Demo Guidelines

How to write demos that showcase JN effectively.

---

## The Golden Rules

1. **Short is better** - Demos should run in under 5 seconds
2. **Show, don't tell** - Let the output speak for itself
3. **Real data, real filtering** - Use meaningful examples
4. **Clean abstractions** - Hide complexity behind helpers

---

## Script Structure

### Good: `run.sh`

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== Demo Name ==="

# 1. First example
echo "1. What this does:"
jn cat data.csv | jn filter '.x > 10' | jq -c '{key, value}'

echo "=== Demo Complete ==="
```

### Bad: `run_examples_with_all_features_v2.sh`

```bash
#!/bin/bash
# 50 lines of environment setup...
export JN_HOME="${JN_HOME:-$(cd "$(dirname "$0")/../.." && pwd)}"
export PATH="$JN_HOME/tools/zig/jn/bin:$JN_HOME/tools/zig/jn-cat/bin:$PATH"
source "$JN_HOME/venv/bin/activate" 2>/dev/null || true
# ...more boilerplate
```

---

## 10 Simplification Principles

### 1. Name it `run.sh`, not `run_examples.sh`
- Shorter names are easier to type
- One obvious entry point

### 2. Use `cd "$(dirname "$0")"` once
- Let the script find itself
- Paths become relative from there

### 3. Create helper functions for plugins
```bash
# Good
md() { uv run ../../jn_home/plugins/formats/markdown_.py "$@" 2>/dev/null; }
cat sample.md | md --mode read

# Bad
cat sample.md | /path/to/uv run /another/path/to/jn_home/plugins/formats/markdown_.py --mode read 2>/dev/null
```

### 4. Assume environment is set up
- Don't re-source activate.sh
- Trust that PATH includes jn tools
- Document prerequisites in README, not the script

### 5. Filter long output with jq/zq
```bash
# Good - show what matters
jn cat data.json | jq -c '{id, name}'

# Bad - dump everything
jn cat data.json
```

### 6. Use `jq -c` for compact output
- One JSON object per line
- Easy to scan vertically
- Consistent formatting

### 7. Prefer `zq` for simple filters
```bash
# Good - streaming filter
jn cat data.csv | zq 'select(.amount > 100)'

# Acceptable - when you need aggregation
jn cat data.csv | jq -s 'group_by(.category)'
```

### 8. Number your examples
```bash
echo "1. Extract metadata:"
# command

echo "2. Filter by type:"
# command
```
- Clear progression
- Easy to reference in docs

### 9. No temp files unless necessary
```bash
# Good - use pipes
cat input.md | md --mode read | jq '.title'

# Bad - unnecessary files
md --mode read < input.md > /tmp/output.json
cat /tmp/output.json | jq '.title'
rm /tmp/output.json
```

### 10. Bookend with clear markers
```bash
echo "=== Demo Name ==="
# examples...
echo "=== Demo Complete ==="
```

---

## Output Guidelines

### Keep output short
- Max 10-20 lines per example
- Use `head`, `tail`, or `jq` to limit
- Truncate long strings: `.content[:80] + "..."`

### Show meaningful data
```bash
# Good - actionable info
{"level":2,"text":"Authentication"}
{"level":3,"text":"GET /users"}

# Bad - noise
{"type":"text","content":"\n\n\n"}
```

### One concept per example
```bash
# Good - single purpose
echo "1. List headings:"
... | zq 'select(.type == "heading")'

echo "2. List code blocks:"
... | zq 'select(.type == "code")'

# Bad - kitchen sink
echo "1. Everything:"
... | jq '.'
```

---

## Sample Data

### Inline for simple demos
```bash
SAMPLE='{"a":1}
{"a":2}'
echo "$SAMPLE" | jn filter '.a > 1'
```

### Separate file for complex data
```
demo/
  run.sh
  sample.md      # Test data
  README.md      # Optional docs
```

### Use realistic examples
- API responses
- Config files
- Log entries
- Not: `{"foo":"bar","baz":123}`

---

## What to Demonstrate

### Do show:
- Core JN commands: `cat`, `filter`, `put`
- Format conversion: CSV → JSON
- Data filtering with zq
- Plugin capabilities

### Don't show:
- Environment setup
- Error handling edge cases
- Every possible option
- Performance benchmarks (unless that's the point)

---

## README Template (optional)

```markdown
# Demo Name

What this demo shows in one sentence.

## Run

\`\`\`bash
./run.sh
\`\`\`

## Prerequisites

- JN tools in PATH (`source dist/activate.sh`)
- Python dependencies for plugins

## What You'll See

1. Example one - what it demonstrates
2. Example two - what it demonstrates
```

---

## Checklist

Before committing a demo:

- [ ] Script named `run.sh`
- [ ] Runs in under 5 seconds
- [ ] Output fits on one screen
- [ ] Uses `jq -c` for compact JSON
- [ ] No hardcoded absolute paths
- [ ] Helper functions hide plugin complexity
- [ ] Examples are numbered
- [ ] Uses realistic sample data
- [ ] Demonstrates one JN capability clearly
