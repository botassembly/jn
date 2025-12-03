# Plugin Matching and Format Resolution

> **Question**: How do regex-based `matches` patterns work, how do we handle CSV variations, and how does override work?

---

## Current System (Python)

### Pattern Matching Rules

```python
# Registry stores: (regex, plugin_name, specificity, role, is_binary)
# Specificity = len(pattern_string)  ← longer patterns win

patterns sorted by:
1. Specificity (longest first)
2. is_binary (Zig/Rust before Python at same specificity)
```

**Example Resolution:**
```
Source: "data.csv"

Patterns checked in order:
  ".*special.*\.csv$"  (specificity=18) ← checked first
  ".*\.csv$"           (specificity=10) ← matches, wins
  ".*\.txt$"           (specificity=10) ← not checked (already matched)
```

### Override Mechanisms

| Mechanism | Syntax | Priority |
|-----------|--------|----------|
| Format override | `data.txt~csv` | Highest - bypasses pattern matching |
| Profile reference | `@myapi/users` | Routes to profile's plugin type |
| Pattern matching | `data.csv` | Default - uses regex matches |

---

## Porting to Zig

### 1. Regex Library

Zig doesn't have a built-in regex engine. Options:

| Option | Pros | Cons |
|--------|------|------|
| **zig-regex** | Pure Zig, no dependencies | Limited features, may have bugs |
| **PCRE2 binding** | Battle-tested, full regex | C dependency, larger binary |
| **Glob patterns** | Simpler, covers 90% of cases | Can't handle complex patterns |
| **Hybrid approach** | Simple glob + special cases | Best of both worlds |

**Recommendation: Hybrid Approach**

Most plugin patterns are simple extension matches:
```
".*\.csv$"   → glob: "*.csv"
".*\.json$"  → glob: "*.json"
"^https?://" → special case: starts_with("http://") or starts_with("https://")
```

Only a few need real regex:
```
".*\.json[l]?$"      → Complex (optional 'l')
".*\.(ya?ml)$"       → Complex (optional 'a')
```

### 2. Proposed Zig Implementation

```zig
// libs/zig/jn-discovery/pattern.zig

const PatternKind = enum {
    extension,      // "*.csv" - simple extension match
    prefix,         // "http://*" - starts with
    suffix,         // "*_test.json" - ends with
    contains,       // "*foo*" - contains substring
    regex,          // Full regex (if needed)
};

const Pattern = struct {
    raw: []const u8,          // Original pattern string
    kind: PatternKind,
    value: []const u8,        // Extracted match value
    specificity: usize,

    pub fn matches(self: Pattern, source: []const u8) bool {
        return switch (self.kind) {
            .extension => std.mem.endsWith(u8, source, self.value),
            .prefix => std.mem.startsWith(u8, source, self.value),
            .suffix => std.mem.endsWith(u8, source, self.value),
            .contains => std.mem.indexOf(u8, source, self.value) != null,
            .regex => self.matchRegex(source),  // Fallback
        };
    }

    pub fn parse(pattern_str: []const u8) Pattern {
        // Convert regex-style to optimized pattern
        // ".*\.csv$" → extension(".csv")
        // "^https?://" → prefix("http://") OR prefix("https://")
        // etc.
    }
};
```

### 3. Pattern Conversion Examples

| Regex Pattern | Converted To | Kind |
|---------------|--------------|------|
| `.*\.csv$` | `.csv` | extension |
| `.*\.tsv$` | `.tsv` | extension |
| `.*\.json$` | `.json` | extension |
| `^https?://` | `http://`, `https://` | prefix (two patterns) |
| `^duckdb://` | `duckdb://` | prefix |
| `.*_test\.json$` | `_test.json` | suffix |

**For complex patterns**: Keep regex fallback using zig-regex or PCRE2

---

## CSV Variations: The Hard Problem

### Current Handling

The Python CSV plugin handles variations through:

1. **Pattern Matching**: `*.csv`, `*.tsv`, `*.txt`
2. **Delimiter Auto-Detection**: Analyzes first 50 lines
3. **Explicit Override**: `?delimiter=;`

### Delimiter Detection Algorithm

```python
def detect_delimiter(sample_lines, candidates=",;\t|"):
    scores = {}
    for delim in candidates:
        # Count columns per line
        col_counts = [line.count(delim) + 1 for line in sample_lines]

        # Score = consistency - variance - empty_penalty
        consistency = len(set(col_counts)) == 1  # All lines same columns?
        variance = max(col_counts) - min(col_counts)
        empty_penalty = sum(1 for c in col_counts if c <= 1)

        scores[delim] = (consistency * 10) - variance - empty_penalty

    return max(scores, key=scores.get)
```

### Zig CSV Implementation

The existing Zig CSV plugin (`plugins/zig/csv/main.zig`) already handles:

- ✅ Configurable delimiter (`--delimiter=,` or `--delimiter=tab`)
- ✅ Quoted fields with escaped quotes (`""`)
- ✅ Streaming (constant memory)
- ✅ RFC 4180 compliance

**Missing**: Auto-detection (currently requires explicit delimiter)

### Proposed: Delimiter Auto-Detection in Zig

```zig
// plugins/zig/csv/detect.zig

const DetectionResult = struct {
    delimiter: u8,
    confidence: f32,  // 0.0 to 1.0
    has_header: bool,
};

pub fn detectDelimiter(reader: anytype, sample_size: usize) !DetectionResult {
    const candidates = [_]u8{ ',', '\t', ';', '|' };
    var scores: [4]i32 = .{ 0, 0, 0, 0 };

    var sample_lines: [50][]const u8 = undefined;
    var line_count: usize = 0;

    // Read sample lines
    while (line_count < 50) : (line_count += 1) {
        const line = reader.readLine() orelse break;
        sample_lines[line_count] = line;
    }

    // Score each candidate
    for (candidates, 0..) |delim, i| {
        var col_counts: [50]usize = undefined;

        for (sample_lines[0..line_count], 0..) |line, j| {
            col_counts[j] = countFields(line, delim);
        }

        // Calculate consistency score
        scores[i] = calculateScore(col_counts[0..line_count]);
    }

    // Return best candidate
    const best_idx = argmax(scores);
    return .{
        .delimiter = candidates[best_idx],
        .confidence = @as(f32, scores[best_idx]) / 100.0,
        .has_header = detectHeader(sample_lines[0], candidates[best_idx]),
    };
}
```

---

## Override Mechanisms in Zig

### 1. Format Override (`~format`)

```zig
// libs/zig/jn-address/parser.zig

pub fn parseAddress(raw: []const u8) !Address {
    var result = Address{};

    // Extract format override (after last ~)
    if (std.mem.lastIndexOf(u8, raw, "~")) |tilde_pos| {
        result.base = raw[0..tilde_pos];
        const format_part = raw[tilde_pos + 1..];

        // Extract parameters from format part
        if (std.mem.indexOf(u8, format_part, "?")) |q_pos| {
            result.format_override = format_part[0..q_pos];
            result.parameters = parseQueryString(format_part[q_pos + 1..]);
        } else {
            result.format_override = format_part;
        }
    }

    return result;
}
```

### 2. Resolution Priority

```zig
// libs/zig/jn-discovery/resolver.zig

pub fn findPlugin(address: Address, mode: Mode, registry: *Registry) !?PluginInfo {
    // Priority 1: Explicit format override
    if (address.format_override) |format| {
        return registry.findByName(format, mode);
    }

    // Priority 2: Protocol (http://, duckdb://, etc.)
    if (address.isProtocol()) {
        return registry.findByProtocol(address.protocol(), mode);
    }

    // Priority 3: Profile reference (@namespace/name)
    if (address.isProfile()) {
        // Profile resolution determines plugin type
        return resolveProfilePlugin(address, mode);
    }

    // Priority 4: Pattern matching
    return registry.matchPattern(address.base, mode);
}
```

### 3. Pattern Registry

```zig
// libs/zig/jn-discovery/registry.zig

const PluginEntry = struct {
    name: []const u8,
    path: []const u8,
    patterns: []const Pattern,
    modes: ?[]const Mode,
    is_binary: bool,
    specificity: usize,  // Max of pattern specificities
};

pub const Registry = struct {
    entries: std.ArrayList(PluginEntry),

    pub fn matchPattern(self: *Registry, source: []const u8, mode: Mode) ?PluginInfo {
        var best_match: ?PluginEntry = null;
        var best_specificity: usize = 0;

        for (self.entries.items) |entry| {
            // Check mode support
            if (entry.modes) |modes| {
                if (std.mem.indexOf(Mode, modes, mode) == null) continue;
            }

            // Check patterns
            for (entry.patterns) |pattern| {
                if (pattern.matches(source)) {
                    // Specificity tie-breaker: binary wins
                    if (pattern.specificity > best_specificity or
                        (pattern.specificity == best_specificity and entry.is_binary))
                    {
                        best_match = entry;
                        best_specificity = pattern.specificity;
                    }
                    break;  // First matching pattern for this plugin
                }
            }
        }

        return if (best_match) |m| m.toPluginInfo() else null;
    }
};
```

---

## CSV-Specific Considerations

### Quote Handling

The Zig CSV plugin already handles RFC 4180 quoting:

```zig
fn parseCSVRowFast(line: []const u8, delimiter: u8, starts: *[1024]usize, ends: *[1024]usize) usize {
    var in_quotes = false;
    var field_idx: usize = 0;
    var field_start: usize = 0;

    for (line, 0..) |char, i| {
        if (char == '"') {
            // Check for escaped quote ("")
            if (in_quotes and i + 1 < line.len and line[i + 1] == '"') {
                // Skip escaped quote
                continue;
            }
            in_quotes = !in_quotes;
        } else if (char == delimiter and !in_quotes) {
            // End of field
            starts[field_idx] = field_start;
            ends[field_idx] = i;
            field_idx += 1;
            field_start = i + 1;
        }
    }

    // Last field
    starts[field_idx] = field_start;
    ends[field_idx] = line.len;
    return field_idx + 1;
}
```

### Variation Handling Strategy

| Variation | Detection | Handling |
|-----------|-----------|----------|
| **Comma (,)** | Default, most common | Fallback if detection fails |
| **Tab (\t)** | Extension `.tsv` or detection | Auto-detect or `?delimiter=tab` |
| **Semicolon (;)** | Detection (European) | Auto-detect or `?delimiter=;` |
| **Pipe (\|)** | Detection (rare) | Auto-detect or `?delimiter=%7C` |
| **Quoted fields** | Always handled | RFC 4180 compliant |
| **Escaped quotes** | `""` pattern | Built into parser |
| **Newlines in fields** | Quoted newlines | Handled in quote mode |

### Extension-Based Hints

```zig
fn getDelimiterHint(source: []const u8) ?u8 {
    if (std.mem.endsWith(u8, source, ".tsv")) return '\t';
    if (std.mem.endsWith(u8, source, ".csv")) return ',';
    if (std.mem.endsWith(u8, source, ".psv")) return '|';
    return null;  // Use auto-detection
}
```

---

## User Override Examples

### Override Format (Pattern Bypass)

```bash
# Force CSV plugin on .txt file
jn cat data.txt~csv

# Force with specific delimiter
jn cat data.txt~csv?delimiter=;

# Force JSON on CSV file (maybe it's actually JSON lines)
jn cat weird.csv~jsonl
```

### Override Delimiter

```bash
# Semicolon-separated (European CSV)
jn cat data.csv?delimiter=;

# Tab-separated
jn cat data.csv?delimiter=tab
jn cat data.csv?delimiter=%09

# Pipe-separated
jn cat data.csv?delimiter=|
jn cat data.csv?delimiter=%7C
```

### Override Plugin Priority

User plugins in `~/.local/jn/plugins/` override bundled:

```
Priority:
1. ~/.local/jn/plugins/zig/csv/     ← User Zig (wins)
2. ~/.local/jn/plugins/python/csv_.py
3. $JN_HOME/plugins/zig/csv/
4. $JN_HOME/plugins/python/csv_.py  ← Bundled Python (lowest)
```

---

## Zig CSV Library Assessment

### Current Implementation

The existing `plugins/zig/csv/main.zig` (523 lines) is **custom-built**:

**Strengths:**
- Zero-allocation parsing (stack arrays)
- RFC 4180 quote handling
- Streaming (constant memory)
- 34x faster than Python

**Gaps:**
- No auto-detection (requires explicit delimiter)
- No encoding handling (assumes UTF-8)
- No header type inference

### External Libraries

| Library | Status | Notes |
|---------|--------|-------|
| **zig-csv** | Community | Basic, not widely used |
| **libcsv** (C) | Mature | Would need binding |
| **Custom** | Current | Best control, proven fast |

**Recommendation**: Extend current implementation with:
1. Delimiter auto-detection (50 line sample)
2. Header inference (first row analysis)
3. Keep zero-allocation design

---

## Implementation Plan Updates

### Add to Phase 8 (Plugin Discovery)

```markdown
### 8.8 Pattern Matching Engine
- [ ] Implement Pattern struct with kind (extension, prefix, suffix, contains)
- [ ] Convert regex patterns to optimized patterns at discovery time
- [ ] Fallback to zig-regex for complex patterns
- [ ] Benchmark pattern matching vs Python regex
```

### Add to Phase 2 (Plugin Refactor)

```markdown
### 2.5 CSV Delimiter Auto-Detection
- [ ] Implement detectDelimiter() in Zig
- [ ] Sample first 50 lines
- [ ] Score candidates (comma, tab, semicolon, pipe)
- [ ] Extension-based hints (.tsv → tab)
- [ ] Confidence threshold for fallback to default
```

---

## Summary

| Question | Answer |
|----------|--------|
| **How are matches ported?** | Hybrid approach: simple glob for 90%, regex fallback for complex |
| **How to override?** | `~format` syntax bypasses pattern matching entirely |
| **How to handle TSV/pipe?** | Auto-detection + explicit `?delimiter=` parameter |
| **Zig CSV library?** | Custom implementation (fast), needs auto-detection added |
| **Quote handling?** | Already implemented, RFC 4180 compliant |
| **User plugin override?** | Directory priority: user > bundled, Zig > Python |
