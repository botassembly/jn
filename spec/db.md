# JN Tool `db` Design Document

## 1. Summary

This document specifies the design for a new JN “utility tool”:

* **Invocation:** `jn tool db ...`
* **Tool name:** `db`
* **Implementation:** a standalone executable Bash script at `jn_home/tools/db`
* **Purpose:** a **contention-safe, accuracy-first JSONL “document database” shell** powered by existing JN primitives:

  * `jn-edit` for surgical JSON mutation
  * `zq` for selection, filtering, projection, and aggregation

The system is **not** a high-throughput database. It is intentionally a **single-file NDJSON document store** that supports:

* dynamic fields (JSON object documents)
* enforced internal metadata (the “metafield thing”)
* CRUD with **canonical one-record-per-line** storage (no multi-version append log for canonical state)
* **soft delete** + explicit hard delete (“purge”)
* correctness under contention (multi-process writers) via **locking + atomic rewrite**
* integrity tooling: `check`, `repair`, `reindex`, backups, optional audit log

Target scale/usage:

* **hundreds to low thousands of records**
* **< 10 updates/day**
* performance is secondary; **durability and contention correctness** are primary

---

## 2. Context: JN tool architecture and conventions

### 2.1 Dispatcher

`jn` is a Zig orchestrator. Utility tools are executed via:

* `jn tool <name> [args...]`
* handled in `tools/zig/jn/main.zig`:

  * `main()` routes `"tool" → runUserTool(...)`
  * `runUserTool()` resolves tool path using `findUserTool()` and execs it with inherited stdio

### 2.2 Tool location (must conform)

The DB tool will live at:

* `jn_home/tools/db` (executable Bash script)

Resolution works in:

* dev layout (`./jn_home/tools/db`)
* dist layout (`dist/libexec/jn/jn_home/tools/db`)
* user install (`~/.local/jn/tools/db`)

### 2.3 Dist activation wrapper (recommended)

`dist/activate.sh` currently defines:

* `todo() { jn tool todo "$@"; }`

We will add:

* `db() { jn tool db "$@"; }`

(Implement via the Makefile’s `dist:` recipe in the same style as `todo`.)

### 2.4 Tool dependency resolution pattern (must match `todo`)

The tool must locate `jn-edit` and `zq` in this priority order:

1. If `jn-edit` and `zq` are on `PATH`, use them.
2. Else, try libexec layout relative to the tool script:

   * `jn_home/tools/db` → `SCRIPT_DIR/../..` → `dist/libexec/jn/`
   * expect executables:

     * `$LIBEXEC_DIR/jn-edit`
     * `$LIBEXEC_DIR/zq`
3. Else, dev fallback:

   * add `zq/zig-out/bin` + `tools/zig/jn-edit/bin` to `PATH`

The DB tool should follow the exact pattern used by `jn_home/tools/todo`.

---

## 3. Goals and non-goals

### 3.1 Goals

1. **Canonical state**: exactly one line per record in the database file.
2. **Dynamic schema**: user documents may include any JSON fields.
3. **Reserved metadata**: record metadata is stored under a reserved metafield (see §4).
4. **Serialized IDs**: by default, integer IDs assigned as `max(id)+1`.
5. **Timestamps**: created/updated timestamps automatically managed.
6. **Soft delete**: records are marked deleted, not removed, by default.
7. **Hard delete**: explicit “purge” step permanently removes soft-deleted records.
8. **Contention correctness**:

   * multiple writers must not clobber each other
   * ID assignment must not race
   * updates must be atomic
9. **Durability & crash-safety**:

   * update operations must be implemented as atomic rewrite via temp file + rename
   * backups must exist for destructive operations
10. **First-class integrity tooling**: `check`, `repair`, `reindex`, and optional audit.

### 3.2 Non-goals

* High-throughput ingestion or frequent writes
* Complex query optimizer, secondary indexes (optional future)
* Full SQL engine (we may add SQL-like sugar later, but v1 is zq/JQ-style)
* Multi-file storage / sharding (future only)
* Background compaction (not needed)

---

## 4. Data model: record format (“metafield thing”)

### 4.1 Canonical record shape

Each line in the DB file is a **single JSON object** representing exactly one record.

Every record must include a reserved metadata object:

* **Reserved key:** `_meta`
* `_meta` is an object owned by `db` and treated as **system-managed** by default.

**Required `_meta` fields (v1):**

| Field              | Type              | Meaning                                                                     |
| ------------------ | ----------------- | --------------------------------------------------------------------------- |
| `_meta.id`         | integer           | Stable record identifier. Immutable after creation.                         |
| `_meta.created_at` | string (ISO-8601) | Created timestamp. Immutable after creation.                                |
| `_meta.updated_at` | string (ISO-8601) | Last update timestamp. Updated on every mutation.                           |
| `_meta.deleted`    | boolean           | Soft delete flag.                                                           |
| `_meta.deleted_at` | string or null    | Timestamp when soft deleted; null if not deleted.                           |
| `_meta.version`    | integer           | Starts at 1 on insert; increments on each mutation that changes the record. |

**Optional `_meta` fields (future-compatible, allowed but not required):**

* `_meta.source` (string) – provenance / import source
* `_meta.notes` (string) – internal comment
* `_meta.schema` (string) – user-defined “collection” or schema tag (see §4.4)

### 4.2 Example record

```json
{"_meta":{"id":12,"created_at":"2025-12-19T18:22:10Z","updated_at":"2025-12-19T18:22:10Z","deleted":false,"deleted_at":null,"version":1},"name":"Alice","age":30,"tags":["#team-a","@work"],"prefs":{"dark_mode":true}}
```

### 4.3 Metadata ownership rules

Default behavior is **safe mode**:

* `db` **overwrites/repairs** `_meta` on insert
* `db` **controls** `_meta.updated_at`, `_meta.version`, `_meta.deleted`, `_meta.deleted_at`
* `db` **disallows changes** to `_meta.id` and `_meta.created_at` (unless `--unsafe`)

Rationale: correctness + preventing accidental corruption.

### 4.4 Collections / “tables” (optional but supported by design)

The DB is a document store. If the user wants multiple “tables” in one file:

* Recommend a convention using `_meta.schema` (string), e.g.:

  * `"users"`, `"orders"`, `"tasks"`

Tool support (v1):

* `--schema <name>` option on insert and query, implemented as:

  * inserts include `_meta.schema=<name>`
  * default query filters by schema when `--schema` is used

No schema enforcement is performed.

---

## 5. Storage layout

### 5.1 Database file format

* **NDJSON / JSONL**: one JSON object per line
* always terminated by newline (preferred)
* no “header records” in v1 (no special meta lines), so log viewers remain straightforward

### 5.2 Default file naming

The tool is generic; it must work with arbitrary file paths.

**Default** (when user does not specify a file):

* `DB_FILE="./.db.jsonl"`

Overrides:

* `db --file path/to/my.db.jsonl ...`
* env var fallback: `JN_DB_FILE` (if set and `--file` absent)

### 5.3 Sidecar files

All sidecars are derived from `DB_FILE` path:

| Purpose                | Path pattern                               |
| ---------------------- | ------------------------------------------ |
| Lock file              | `${DB_FILE}.lock`                          |
| Backup 1 (most recent) | `${DB_FILE}.bak`                           |
| Backup 2 (previous)    | `${DB_FILE}.bak2`                          |
| Temp rewrite file      | `${DB_FILE}.tmp.<pid>` (in same directory) |
| Integrity quarantine   | `${DB_FILE}.bad.jsonl`                     |
| Optional audit log     | `${DB_FILE}.audit.jsonl`                   |

Notes:

* Temp file must be created **in the same directory** to guarantee atomic rename.
* Backups are created for operations that rewrite the DB file.

---

## 6. Concurrency, contention, and durability model

### 6.1 Hard requirement: serialize writers

**All write operations must acquire an exclusive lock** on `${DB_FILE}.lock`.

Write operations include (at minimum):

* `insert`
* `update`, `set`, `unset`
* `delete` (soft)
* `undelete`
* `purge`
* `repair`
* `reindex`
* any batch mutation or import

### 6.2 Locking mechanism

Preferred:

* `flock` on a file descriptor (portable on Linux; available on many systems)

Fallback (if `flock` missing):

* atomic `mkdir "${DB_FILE}.lockdir"` pattern with `trap` cleanup

Design must support both; `flock` is preferred because it auto-releases on process exit.

**Lock scope**:

* Lock must be held from:

  * reading current DB state (for selection, max id, etc.)
  * through temp file generation
  * through validation
  * until after atomic rename completes

### 6.3 Read operations

Reads do not strictly require locks because writes are atomic rename:

* A reader sees either the old file or the new file.
* It never sees a partially written DB file.

However, an optional `--lock-read` can be offered for users who want a consistent snapshot across multiple sequential operations inside a script.

### 6.4 Atomic rewrite protocol (the core correctness mechanism)

All mutations rewrite the database file as follows:

1. Acquire exclusive lock.
2. Ensure DB file exists (`touch` if missing).
3. Create backups (`.bak`, `.bak2`) as applicable.
4. Generate temp file:

   * stream-read original DB line-by-line
   * rewrite each line either unchanged or updated depending on operation
   * ensure every output record is a single valid JSON object on one line
5. Validate temp file:

   * parse every line as JSON using `zq` (details in §10)
   * verify invariants as required (`_meta.id` uniqueness, etc.)
6. Atomically replace:

   * `mv "${tmp}" "${DB_FILE}"` (same directory)
7. Optionally `--durable`:

   * `fsync` temp file and directory pre/post rename where possible (platform-specific)
8. Release lock.

This prevents corruption and eliminates “in-place partial edit” hazards.

### 6.5 Backups and undo

Given low update frequency, backups are cheap and valuable.

Backup policy:

* Before any mutating rewrite:

  * If `${DB_FILE}.bak` exists, rotate to `.bak2`
  * Copy `${DB_FILE}` to `.bak`
* Provide `db undo`:

  * restore `.bak` → `${DB_FILE}`
  * optionally rotate current DB to `.undo.<timestamp>.jsonl` (nice-to-have)

---

## 7. Command-line interface (CLI) specification

### 7.1 Global options (apply to most commands)

* `--file <path>`: DB file path (default `./.db.jsonl`)
* `--schema <name>`: filter/assign `_meta.schema`
* `--json`: machine-readable output (where human output exists)
* `--quiet`: suppress non-essential messages
* `--unsafe`: allow editing `_meta` (strongly discouraged)
* `--lock-read`: take shared/read lock (if supported)
* `--durable`: stronger durability mode (best-effort fsync)
* `--include-deleted`: include soft-deleted records in output
* `--only-deleted`: only soft-deleted records

### 7.2 Output conventions

* Querying commands output **NDJSON to stdout** by default (pipe-friendly).
* Human-readable summaries (counts, status messages) go to stderr unless explicitly a “report” command.
* `db get` may default to printing a single JSON object (not NDJSON stream), but should support `--ndjson`.

### 7.3 Command set (v1)

#### 7.3.1 `db help`

* Print tool usage and command list.
* Include examples and note that records are NDJSON.

#### 7.3.2 `db init`

Creates an empty DB file if missing.

* `db init [--file path]`
* Creates file and writes nothing (empty file) or optionally writes a comment-free empty file.
* Also may initialize sidecars (optional), but not required.

#### 7.3.3 `db insert` / `db add`

Insert a new record.

**Inputs:**

* `db insert '{"name":"Alice","age":30}'`
* `db insert --stdin` (read JSON object from stdin)
* `db insert --file my.db.jsonl --schema users '{"name":"Bob"}'`

**Semantics:**

* Assign `_meta.id = max(existing ids) + 1` (including deleted)
* Set `_meta.created_at = now()`
* Set `_meta.updated_at = created_at`
* Set `_meta.deleted = false`, `_meta.deleted_at = null`
* Set `_meta.version = 1`
* If `--schema` provided: `_meta.schema=<schema>`

**Validation:**

* input must be a JSON object (not array, number, string)
* if input includes `_meta`, it is ignored/overwritten (safe mode)

**Output:**

* Print inserted record (NDJSON or JSON) and/or print new id:

  * default: print inserted record as NDJSON to stdout
  * `--id-only`: print id only

#### 7.3.4 `db get <id>`

Fetch one record by id.

* `db get 12`
* `db get 12 --include-deleted`
* `db get 12 --field name` (optional convenience)

Default: exclude deleted unless `--include-deleted`.

Output:

* default: JSON object to stdout
* `--ndjson`: output as NDJSON line (for pipelines)

Exit codes:

* 0 if found
* 1 if not found (or 2, choose consistently and document)

#### 7.3.5 `db list`

List records, optionally filtered.

* `db list`
* `db list --include-deleted`
* `db list --only-deleted`
* `db list --schema users`

By default: list non-deleted records.

Output: NDJSON to stdout.

#### 7.3.6 `db query <zq_expr>`

General-purpose querying using zq expressions.

Examples:

* `db query 'select(.age >= 21)'`
* `db query 'select(._meta.deleted == false) | {id: ._meta.id, name}'`
* `db query --schema users 'select(.tags | any(. == "#vip"))'`

Implementation approach:

* Start with base filter:

  * exclude deleted unless `--include-deleted` or `--only-deleted`
  * apply schema filter if provided
* Then pipe through user query expression

Output: NDJSON.

Notes:

* Query expression is user-provided; tool must pass it to `zq` without using `eval`.

#### 7.3.7 `db update <id> <jn-edit-expr...>`

Update a record by applying one or more `jn-edit` expressions.

Examples:

* `db update 12 '.age=31'`
* `db update 12 '.prefs.dark_mode=true' '.tags += ["#new"]'`
* `db update 12 --unsafe '._meta.deleted=true'` (discouraged)

Semantics (safe mode):

* Apply user edit expressions to the record **excluding `_meta` mutation**:

  * After edits, enforce:

    * `_meta.id` unchanged
    * `_meta.created_at` unchanged
    * `_meta.updated_at = now()`
    * `_meta.version += 1`
    * `_meta.deleted` / `_meta.deleted_at` unchanged unless using delete commands
* If record not found: exit non-zero

Output:

* `--print`: print updated record
* default: print nothing (or print id + status to stderr)

#### 7.3.8 `db set <id> <path> <json_value>`

Convenience wrapper around update for common usage.

Examples:

* `db set 12 name '"Alice Smith"'`
* `db set 12 age '31'`
* `db set 12 prefs.dark_mode 'true'`

Notes:

* `<json_value>` is JSON literal, not shell-typed value.
* Tool should validate that `<json_value>` parses.

Semantics:

* Equivalent to `db update <id> '.<path> = <json_value>'` with safe `_meta` enforcement.

#### 7.3.9 `db unset <id> <path>`

Remove a field.

Example:

* `db unset 12 prefs.legacy_setting`

Semantics:

* Equivalent to `db update <id> 'del(.prefs.legacy_setting)'` (depending on jn-edit syntax)
* Safe `_meta` enforcement applies.

#### 7.3.10 `db delete <id>` (soft delete)

Marks record as deleted.

Semantics:

* `_meta.deleted = true`
* `_meta.deleted_at = now()`
* `_meta.updated_at = now()`
* `_meta.version += 1`

Record remains in file, still one line.

Output:

* status to stderr; optionally print record with `--print`

#### 7.3.11 `db undelete <id>`

Restores soft-deleted record.

Semantics:

* `_meta.deleted = false`
* `_meta.deleted_at = null`
* `_meta.updated_at = now()`
* `_meta.version += 1`

#### 7.3.12 `db purge`

Hard-delete soft-deleted records.

Examples:

* `db purge` (remove all deleted)
* `db purge --before 2025-01-01T00:00:00Z` (optional, based on `_meta.deleted_at`)
* `db purge --id 12` (optional targeted purge)

Semantics:

* rewrite file excluding deleted records (or those matching criteria)
* create backups
* validate output

#### 7.3.13 `db count`

Counts records by status.

Output example (human):

* total: N
* active: N
* deleted: N
* schema breakdown if `--schema` absent (optional)

Implementation:

* compute via `zq` counts

#### 7.3.14 `db stats`

More detailed report:

* counts
* max id
* schema distribution
* basic field presence heuristics (optional)
* could be extended later

#### 7.3.15 `db check`

Validate file integrity and invariants (non-mutating).

Checks:

1. Every non-empty line is valid JSON object.
2. Every record has `_meta` object.
3. `_meta.id` exists and is integer.
4. `_meta.id` uniqueness.
5. `_meta.created_at`, `_meta.updated_at` are present and parseable strings (basic check).
6. `_meta.deleted` is boolean; `_meta.deleted_at` is null or string.

Output:

* machine-readable summary if `--json`
* human summary otherwise
* exit non-zero if any failure

#### 7.3.16 `db repair`

Conservative repair tool. Mutating.

Actions:

* Quarantine invalid JSON lines into `${DB_FILE}.bad.jsonl` (append or replace; document behavior).
* For records missing `_meta`:

  * either fail (strict) or generate `_meta` with new id (dangerous)
  * **v1 recommendation:** fail by default; require `--repair-missing-meta` to auto-generate
* For duplicate ids:

  * deterministic resolution:

    * default keep first occurrence and quarantine others
    * optionally `--keep last`
* Recompute and fix obvious `_meta` type issues (e.g., `"deleted":"false"` → `false`) only if safe and explicit flag is provided

Given the risk, `repair` must be explicit and conservative.

#### 7.3.17 `db reindex`

Recompute ID allocator state and optionally normalize metadata.

Since v1 does not keep a separate meta counter file, `reindex` is primarily:

* verify max id and uniqueness
* optionally rewrite records with normalized `_meta` ordering/shape (cosmetic)
* optionally fix `next_id` in a future meta file if you add one later

**In v1:** `reindex` can simply run `check` plus an optional “normalize” pass.

#### 7.3.18 `db undo`

Restore previous DB state from `.bak`.

Semantics:

* requires `.bak` to exist
* copies `.bak` → `${DB_FILE}`
* should take lock

#### 7.3.19 `db export`

Export records in alternate formats.

Minimum:

* `db export ndjson` (default: same as `list`)
* `db export json` (wrap into array)
* `db export csv` (best-effort; flattening rules documented)

Given JN already has format plugins, you can keep this minimal in v1:

* `db list | jn put ...` is the recommended pipeline approach
* but having `export` convenience is reasonable

---

## 8. Core algorithms and invariants

### 8.1 ID allocation: `max(id)+1`

On insert (with lock held):

* compute `max_id` across all records (including deleted):

  * if DB empty, `max_id = 0`
  * next id = `max_id + 1`

Important invariants:

* IDs are never reused, even if records are deleted.
* `_meta.id` is immutable in safe mode.

### 8.2 Timestamp format

Use UTC ISO-8601 consistently.

Recommended format:

* `"YYYY-MM-DDTHH:MM:SSZ"`

Implementation detail:

* prefer a portable timestamp function:

  * on GNU date: `date -u +%Y-%m-%dT%H:%M:%SZ`
  * on BSD/macOS: `date -u +%Y-%m-%dT%H:%M:%SZ`

Do not use local time by default.

### 8.3 Record mutation normalization (“safe mode enforcement”)

Whenever a record is inserted or updated, normalize metadata:

**Insert:**

* overwrite `_meta` entirely
* enforce required `_meta` fields and types
* preserve user fields outside `_meta`

**Update / set / unset:**

* read existing record
* apply user edits
* reapply metadata enforcement:

  * `_meta.id` unchanged
  * `_meta.created_at` unchanged
  * `_meta.updated_at = now()`
  * `_meta.version += 1`
  * `_meta.deleted` / `_meta.deleted_at` unchanged unless the command is delete/undelete

**Delete:**

* apply delete semantics described in §7.3.10

**Undelete:**

* apply undelete semantics described in §7.3.11

### 8.4 Deleted record behavior defaults

* By default, commands that return “active records” exclude deleted.
* Commands must provide explicit flags:

  * `--include-deleted`
  * `--only-deleted`

Hard-delete (`purge`) operates only on soft-deleted by default.

---

## 9. File rewrite implementation plan (no full code, but complete mechanics)

### 9.1 High-level structure of `jn_home/tools/db`

Sections:

1. Header + usage docs
2. `set -euo pipefail`
3. Global config defaults
4. Dependency resolution (`jn-edit`, `zq`) using the todo pattern
5. Argument parsing:

   * global flags
   * command dispatch
6. Helper functions:

   * `now_utc()`
   * `ensure_db_file()`
   * `lock_write()` / `unlock_write()`
   * `backup_rotate()`
   * `validate_ndjson_file()`
   * `max_id()`
   * `select_by_id()`
   * rewrite helpers (`rewrite_with_transform`)
7. Commands implementation

### 9.2 Transform-based rewrite helper

Core helper concept:

`rewrite_db(transform_fn)`

* opens `${DB_FILE}` for reading
* writes `${TMP_FILE}` line-by-line
* for each input line:

  * if empty: skip (or treat as error; define policy)
  * parse minimal fields with `zq` where needed (id, deleted status)
  * decide:

    * write unchanged
    * write updated record
    * drop record (purge)
* at end:

  * validate `${TMP_FILE}`
  * atomic replace

**Policy decision (recommended):**

* Empty lines are ignored on read but removed on rewrite.

### 9.3 Validation: `validate_ndjson_file(path)`

Validation should be performed via `zq`:

Minimum:

* `zq -c '.' < file >/dev/null` should succeed

Stronger:

* verify every line is an object:

  * `zq -c 'select(type != "object") | error("non-object")'` (or equivalent)
* verify `_meta.id` uniqueness:

  * extract ids and check duplicates (details below)

### 9.4 Duplicate ID detection strategy

Given constraints, a simple approach is fine:

* Extract ids:

  * `zq -r '._meta.id'`
* Ensure all are integers and not null.
* Sort and detect duplicates:

  * `sort -n | uniq -d`

If duplicates exist, `check` fails; `repair` may quarantine.

### 9.5 Backups rotation plan

Before writing:

1. if `${DB_FILE}.bak` exists, move it to `.bak2` (overwrite `.bak2`)
2. copy `${DB_FILE}` → `.bak`

Ensure copy errors fail fast.

### 9.6 Contention safety requirement

All mutations follow:

* `lock_write`
* compute needed derived state (max id, etc.)
* rewrite
* validate
* rename
* `unlock_write`

No exceptions.

---

## 10. Query and aggregation model

### 10.1 zq as the query engine

`db query` and most list/report operations are implemented using `zq` expressions.

Rationale:

* consistent with JN toolchain
* NDJSON streaming-friendly
* user already thinks in jq-like terms

### 10.2 “Base filter” composition

To standardize behavior, the tool will generate an internal base filter expression depending on flags:

* default: `select(._meta.deleted == false)`
* `--include-deleted`: no deletion filter
* `--only-deleted`: `select(._meta.deleted == true)`
* schema filter (if `--schema <s>`): `select(._meta.schema == "<s>")`

Then it applies user expression afterwards.

### 10.3 Aggregations: minimal wrappers, rely on zq

Rather than inventing a DSL, provide a few convenience commands that expand to zq:

* `db count`
* `db stats`

Everything else:

* `db query '...' | zq ...` or `| jn filter ...` as appropriate

You can later add:

* `db agg 'group_by(.field) | ...'` as a convenience alias, but not required.

---

## 11. Optional audit log (recommended, separate from canonical DB)

You explicitly do **not** want multi-version canonical records, and that’s correct for your goals.

However, a separate **append-only audit file** provides huge safety value without changing the canonical model.

### 11.1 Audit file: `${DB_FILE}.audit.jsonl`

Each mutation appends exactly one audit event:

Example event:

```json
{"ts":"2025-12-19T18:30:00Z","op":"update","id":12,"schema":"users","version_before":2,"version_after":3}
```

Minimum fields:

* `ts`, `op`, `id`

Optional fields:

* `schema`
* `before_hash`, `after_hash` (hash of record line)
* `edits` (array of jn-edit expressions applied)

### 11.2 Audit is best-effort, not authoritative

* canonical DB remains the source of truth
* audit helps debugging and rollback strategies later

---

## 12. Safety, correctness, and security considerations

### 12.1 No `eval`

User expressions will be passed to `zq` and `jn-edit`.

Implementation must avoid:

* `eval`
* building shell command strings

Instead:

* invoke tools with argument arrays:

  * `"$ZQ" -c "$expr"`
  * `"$JN_EDIT" "$edit_expr"`

This avoids command injection via shell parsing.

### 12.2 Quoting and JSON literals

Commands like `db set` require JSON literals as inputs.

Document and enforce:

* user must pass JSON, including quotes for strings:

  * `db set 12 name '"Alice"'`
* tool should validate JSON literal by attempting to parse with `zq` before applying

### 12.3 Reserved field enforcement

In safe mode:

* disallow user mutation of:

  * `_meta.id`
  * `_meta.created_at`
* prevent accidental removal of `_meta`

Provide `--unsafe` to bypass, but clearly document it as dangerous.

### 12.4 Cross-platform caveats

* `flock` availability varies; provide fallback.
* `date` flags vary between GNU and BSD; implement `now_utc()` portably.
* `mv` atomicity relies on same filesystem; temp file must be in same directory as DB.

---

## 13. Integrity commands: behavior details

### 13.1 `db check` details

Should produce:

* file exists?
* readable?
* line count
* parse validity
* meta validity
* duplicate ids
* counts (active/deleted)

Exit codes:

* 0: OK
* 2: integrity error (parsing/invariant)
* 1: operational error (missing file, permission, etc.)

### 13.2 `db repair` details (conservative)

Recommended v1 behavior:

* If JSON parse errors exist:

  * move bad lines to `${DB_FILE}.bad.jsonl`
  * rewrite DB without them
  * report how many quarantined

* If duplicate ids exist:

  * default keep first, quarantine others
  * optional `--keep last`

* If `_meta` missing:

  * **default**: fail and instruct user to fix (do not invent ids automatically)
  * optional `--repair-missing-meta`:

    * assigns new ids for missing-meta records (this is inherently lossy); must be explicit

### 13.3 `db undo` details

* restores `${DB_FILE}.bak`
* must take lock
* must validate restored file before finalizing (optional but recommended)

---

## 14. Repository integration tasks (what to change in the repo)

### 14.1 Add the tool

* Create executable file: `jn_home/tools/db`
* Ensure it is executable (`chmod +x`)

### 14.2 Update dist activation wrapper

Modify the `dist:` recipe in `Makefile` to include:

* `db() { jn tool db "$$@"; }`

so users can `source dist/activate.sh` and run `db ...`.

### 14.3 Update tool list help (optional)

In `tools/zig/jn/main.zig`, update `printToolUsage()`:

* add `db` under “Available tools”

### 14.4 Update docs (recommended)

* `jn_home/tools/README.md`:

  * add `db` tool section
  * describe its storage model (JSONL doc store, `_meta`, soft delete, etc.)

---

## 15. Test plan (accuracy + contention first)

Given your priorities, tests should focus on:

### 15.1 Correctness tests

1. **Insert creates proper `_meta`**:

   * id increments correctly
   * timestamps present
   * version=1
2. **Update preserves immutable meta**:

   * `_meta.id` unchanged
   * `_meta.created_at` unchanged
   * updated_at changes
   * version increments
3. **Delete/undelete semantics** correct
4. **Purge removes deleted only**
5. **Check detects corruption**:

   * malformed JSON line
   * missing `_meta`
   * duplicate ids

### 15.2 Contention tests

1. Two concurrent inserts:

   * must produce two distinct ids
   * file must contain both records after both processes complete
2. Concurrent update + insert:

   * must preserve both changes
3. Lock cleanup:

   * lock released on normal exit and error exit

These can be implemented as integration tests in shell or a lightweight Python harness.

### 15.3 Crash-safety simulations

* forcibly kill during rewrite before rename:

  * DB file should remain intact (old version)
  * temp file may remain; tool should clean up on next run or ignore
* kill after rename:

  * DB should be new version, valid

---

## 16. Known sharp edges and how v1 addresses them

### 16.1 “One bad write poisons the DB”

Mitigations:

* always rewrite to temp
* validate temp before rename
* backups
* `check` and `repair`

### 16.2 Lost updates due to concurrent writers

Mitigation:

* mandatory exclusive lock around full write transaction

### 16.3 `_meta` corruption by user edits

Mitigation:

* safe mode enforcement; `--unsafe` only by explicit choice

### 16.4 Quoting pain for JSON literals

Mitigation:

* provide `--stdin` variants
* validate JSON literals early
* document usage clearly

---

## 17. Future extensions (explicitly out of scope for v1, but planned)

1. **Index sidecar** for faster `get` by id (non-authoritative, rebuildable)
2. **SQL-ish sugar**:

   * `db select --where 'age > 21'` translating to zq
3. **Schema-driven constraints** (optional, not default)
4. **Import/export improvements**:

   * CSV mapping with explicit field mapping
5. **Multi-DB directory support**:

   * `.jn/db/<name>.jsonl` layouts and named DBs

---

## 18. Final design decisions recap

This section enumerates the decisions we are committing to for v1:

1. **Canonical storage**: one record per line; updates rewrite canonical state (no append-only versioning for canonical DB).
2. **Metafield design**: system metadata stored in reserved `_meta` object.
3. **IDs**: sequential integer ids allocated as `max(_meta.id)+1` under an exclusive lock.
4. **Timestamps**: UTC ISO-8601 strings; `created_at` immutable, `updated_at` updated on mutation.
5. **Versioning**: `_meta.version` integer increments on every mutation.
6. **Soft delete first**: delete sets `_meta.deleted=true` and `_meta.deleted_at`; hard delete is explicit `purge`.
7. **Contention correctness**: all writers serialized with lock; no lost updates.
8. **Crash safety**: atomic rewrite via temp file + validate + rename; backups.
9. **Tool integration**: implemented as `jn_home/tools/db`; add wrapper in `dist/activate.sh`; optionally update tool usage list.
10. **Query model**: zq-based querying; tool provides convenience but does not replace zq.

---

If you want one additional v1 decision baked into this design (without changing the canonical model), the most valuable is:

* **Enable audit log by default** (`${DB_FILE}.audit.jsonl`), best-effort append-only, to make debugging and “what changed?” questions trivial—without reintroducing multi-version canonical records.
