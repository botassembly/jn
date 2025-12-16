# Future Ideas

> **Purpose**: Brainstormed enhancements that would strengthen JN without adding conceptual burden.

---

## Selection Principles

Ideas should be:

1. **Additive, not invasive** - New flags/commands, no changes to core model
2. **Familiar to Unix users** - Patterns like `tee`, `--dry-run`, progress bars already exist
3. **Streaming-compatible** - Work on infinite streams, constant memory
4. **Optional complexity** - Default behavior unchanged, power users opt-in
5. **Debuggability focus** - Help answer "what happened?" or "what will happen?"

The common thread: **make the invisible visible** without changing how pipelines work.

---

## Top 10 Ideas (Ranked)

### 1. Error Sidecar

Route failed records to a separate stream instead of killing the pipeline.

```bash
jn cat data.csv --errors=errors.ndjson | jn put output.json
```

Error records get structured context:
```json
{"_error": "parse failed at column 3", "_line": 42, "_raw": "bad,data,here"}
```

**Why**: Streaming pipelines need graceful degradation. One bad record shouldn't kill a 10GB pipeline. Very Unix (like `2>errors.log`). Low complexity—just routing.

---

### 2. Dry-run / Explain Mode

Show what a pipeline will do without executing it.

```bash
$ jn cat @myapi/users --explain
Address:    @myapi/users
Profile:    ~/.local/jn/profiles/http/myapi/users.json
Chain:      http (read) → json (parse) → stdout
URL:        https://api.example.com/v1/users
Headers:    Authorization: Bearer [REDACTED]
Format:     json (from Content-Type)
```

**Why**: Critical for debugging and trust. "What will this do?" before running. Shows resolved profile, plugin chain, inferred formats. Like `make -n` or `git diff --stat`. Zero runtime cost.

---

### 3. Progress Indicators

Show throughput and progress for long-running pipelines.

```bash
$ jn cat huge.csv | jn filter '.x > 10' | jn put output.json
⠋ 1.2M records | 340MB read | 45k/sec | 00:28 elapsed
```

Only shown when stderr is TTY. Hidden when piped or redirected.

**Why**: Long pipelines feel broken without feedback. Already standard in `curl`, `rsync`, `pv`. Respects Unix conventions.

---

### 4. Random Sample

Probabilistic sampling complements deterministic `head`/`tail`.

```bash
jn cat huge.csv | jn sample --rate=0.01 | jn analyze
```

Takes approximately 1% of records. Constant memory (no buffering). Each record independently selected.

**Why**: `head` and `tail` are biased (start/end of file). Statistical sampling gives representative subset. Essential for data exploration. Trivial reservoir sampling implementation.

---

### 5. Assertions

Inline quality gates that fail the pipeline on condition.

```bash
jn cat data.csv | jn assert 'count() > 0' | jn put output.json
jn cat data.csv | jn assert '.price >= 0' | jn put output.json
```

First form: aggregate assertion (requires buffering).
Second form: per-record assertion (streaming).

**Why**: Lightweight quality gates without external tools. Fits streaming model. Like `test` or `[ ]` in shell. Fail-fast prevents downstream corruption.

---

### 6. Rate Limiting

Throttle throughput for API-friendly streaming.

```bash
jn cat @api/paginated --rate=10/sec | jn put all_data.json
```

Token bucket algorithm. Prevents 429 errors from aggressive fetching.

**Why**: APIs need throttling. Essential for polite automation. Already common in HTTP clients. Simple implementation.

---

### 7. Shell Completions

Tab completion for commands, profiles, and formats.

```bash
jn plugin generate-completion bash > /etc/bash_completion.d/jn
jn plugin generate-completion zsh > ~/.zfunc/_jn
jn plugin generate-completion fish > ~/.config/fish/completions/jn.fish
```

Completes:
- Subcommands (`jn c<TAB>` → `cat`)
- Profile names (`jn cat @my<TAB>` → `@myapi/`)
- Format hints (`jn cat data.txt~<TAB>` → `csv`, `json`, ...)
- File paths with format awareness

**Why**: Massive discoverability boost. Low maintenance. Every serious CLI has this.

---

### 8. Tee / Split Output

Write to multiple destinations simultaneously.

```bash
jn cat data.csv | jn tee backup.ndjson | jn filter '.x > 10' | jn put filtered.json
```

Or split by condition:

```bash
jn cat data.csv | jn split --by='.status' --prefix=status_
# Creates: status_active.ndjson, status_pending.ndjson, ...
```

**Why**: Pure Unix pattern (`tee(1)`). No new concepts—just multi-output. Common need for backup-while-processing or conditional routing.

---

### 9. Diff Mode

Compare two sources record-by-record.

```bash
$ jn diff old.csv new.csv --key=id
+ {"id": 4, "name": "Diana", "status": "new"}
- {"id": 2, "name": "Bob", "status": "deleted"}
~ {"id": 1, "name": "Alice", "status": "active→inactive"}
```

Output modes:
- Human-readable (above)
- NDJSON with `_diff` field for programmatic use
- Stats only (`--stat`)

**Why**: Essential for debugging, migrations, audits. Natural complement to `merge` and `join`. Answers "what changed?"

---

### 10. Record Annotations

Add metadata fields to records.

```bash
jn cat data.csv --annotate=source | jn head -n 1
{"_source": "data.csv", "name": "Alice", "age": 30}

jn merge a.csv b.csv --annotate=source,line | jn head -n 1
{"_source": "a.csv", "_line": 1, "name": "Alice", "age": 30}
```

Available annotations:
- `source` - Filename or URL
- `line` - Line number in source
- `timestamp` - Processing time
- `index` - Record number in stream

**Why**: Know where records came from in merged streams. Opt-in, non-invasive. Debugging superpower for complex pipelines.

---

## Additional Ideas (Unranked)

### Developer Experience

| Idea | Description |
|------|-------------|
| Pipeline aliases | Named reusable pipelines in `.jn/pipelines/` |
| Interactive REPL | Explore data iteratively with persistent context |
| Colored output | Syntax highlighting for NDJSON in terminal |
| Plugin scaffolding | `jn plugin new csv-variant` generates template |

### Debugging & Observability

| Idea | Description |
|------|-------------|
| Stage timing | Show time spent in each pipeline stage |
| Record counter | Lightweight count without full `analyze` |
| Debug tap | Insert `jn tap` to log records without affecting flow |
| Memory monitor | Warn if any stage buffers excessively |

### Error Handling

| Idea | Description |
|------|-------------|
| Retry with backoff | Automatic retry for transient network failures |
| Partial failure mode | Continue on bad records, report summary at end |
| Error context | Include surrounding records when reporting parse errors |

### Streaming Enhancements

| Idea | Description |
|------|-------------|
| Parallel merge | Process multiple sources concurrently (not sequentially) |
| Checkpoint/resume | Resume interrupted pipelines from byte offset |
| Windowed aggregation | Tumbling windows for streaming stats |
| Record deduplication | Dedupe by key in constant memory (bloom filter) |

### Data Quality

| Idea | Description |
|------|-------------|
| Schema validation | Validate against JSON Schema inline |
| Schema diff | Detect schema changes between runs |
| Null audit | Report fields with unexpected nulls |
| Type coercion warnings | Flag when string "123" becomes number |

### Format & Protocol Extensions

| Idea | Description |
|------|-------------|
| Parquet native | Zig-native Parquet (no Python dependency) |
| Arrow streaming | Zero-copy IPC for high-performance integrations |
| Websocket source | Real-time streaming from websocket endpoints |
| SSE source | Server-sent events as streaming source |
| Glob profiles | `@logs/2024-*` expands to multiple profile endpoints |

### Composition & Reuse

| Idea | Description |
|------|-------------|
| Sub-pipelines | `jn run normalize` executes named pipeline |
| Conditional routing | Route records to different outputs by condition |
| Environment profiles | `@myapi.staging/users` vs `@myapi.prod/users` |
| Pipeline variables | `--set limit=100` with `$limit` substitution |

---

## Implementation Notes

### Error Sidecar Implementation

Two approaches:

**A. Built-in flag:**
```bash
jn cat data.csv --errors=errors.ndjson
```

Plugin protocol extended: errors written to fd 3 (if open), structured as NDJSON.

**B. Shell redirection (no JN changes):**
```bash
jn cat data.csv 2> >(jn put errors.ndjson)
```

Requires plugins to output parseable errors on stderr.

Recommendation: Approach A for better structure and cross-platform support.

### Progress Indicator Implementation

- Only active when stderr is a TTY (`isatty(2)`)
- Disable with `--quiet` or `JN_QUIET=1`
- Update at most 10Hz to avoid flicker
- Clear line on completion (no residual output)
- Show: record count, bytes, throughput, elapsed time

### Diff Implementation

Algorithm:
1. Load smaller source into hash map (keyed by `--key`)
2. Stream larger source, emit differences
3. Emit remaining (deleted) records from map

Memory: O(smaller source) — acceptable trade-off for utility.

For very large sources, consider sorted-merge approach (requires pre-sorted input).

---

## Ideas Explicitly Not Pursued

| Idea | Why Not |
|------|---------|
| DAG orchestration | Violates linear pipeline philosophy; use external orchestrator |
| Schema enforcement | Violates "pass-through any JSON"; use external validator |
| GUI/TUI | CLI-native by design; pipe to VisiData for visual |
| Workflow scheduling | Not JN's job; use cron/Airflow/Prefect |
| Distributed processing | Single-machine focus; use Spark for cluster scale |
| Persistent state | Stateless streaming is core feature, not limitation |

---

## See Also

- [01-vision.md](01-vision.md) - Core philosophy and non-goals
- [02-architecture.md](02-architecture.md) - Current system design
- [08-streaming-backpressure.md](08-streaming-backpressure.md) - Why pipes work
