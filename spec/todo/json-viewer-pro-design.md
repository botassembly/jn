# JSON Viewer: From Simple to Pro

**Date:** 2025-11-22
**Status:** Design / Roadmap
**Type:** Display Plugin Evolution
**Author:** Claude

---

## Table of Contents

1. [Vision](#vision)
2. [Evolution Path](#evolution-path)
3. [Core Features (Always)](#core-features-always)
4. [Tier 1: Essential Pro Features](#tier-1-essential-pro-features)
5. [Tier 2: Power User Features](#tier-2-power-user-features)
6. [Tier 3: Advanced Features](#tier-3-advanced-features)
7. [Architecture Evolution](#architecture-evolution)
8. [Implementation Roadmap](#implementation-roadmap)

---

## Vision

**The Goal:**
Transform the simple single-record viewer into a professional data exploration tool that feels natural in the terminal, integrates seamlessly with JN pipelines, and makes JSON data comprehensible at a glance.

**Not Building:**
A full-fledged application or IDE. This is a **data viewer** that lives in pipelines, not a standalone app. It's more like `less` for JSON than like a database GUI.

**Guiding Principle:**
Every feature must answer the question: **"What makes exploring JSON data faster, clearer, or less frustrating?"**

---

## Evolution Path

### Stage 1: Single-Record Viewer (MVP)
**What:** One record at a time, expandable tree, keyboard navigation
**Why:** Validate core concept, learn Textual, ship something useful
**Timeline:** Week 1

### Stage 2: Multi-Record Viewing
**What:** Add table mode for viewing many records at once
**Why:** Users need to scan multiple records, not just one
**Timeline:** Week 2-3

### Stage 3: Data Understanding
**What:** Add statistics panel, value formatting, type inference
**Why:** Users need context ("What am I looking at?")
**Timeline:** Week 4-5

### Stage 4: Workflow Integration
**What:** Add copy JSONPath, export current view, command palette
**Why:** Bridge exploration → transformation gap
**Timeline:** Week 6-7

### Stage 5: Advanced Analysis
**What:** Add compare mode, pattern highlighting, smart navigation
**Why:** Power users want deeper analysis capabilities
**Timeline:** Week 8+

---

## Core Features (Always)

These features are **always present**, from MVP to Pro:

### 1. Tree View with Syntax Highlighting

**What:**
Expandable/collapsible tree showing JSON structure with color-coded values.

**Why:**
JSON's hierarchical nature demands tree visualization. Colors make types obvious at a glance.

**Visual:**
```
▼ Record
  ├─ id: 1                              [cyan: number]
  ├─ name: "Alice Johnson"              [green: string]
  ├─ active: true                       [yellow: boolean]
  ├─ deleted_at: null                   [red: null]
  ▼ address
  │ ├─ city: "New York"
  │ └─ zip: "10001"
  └─ ▶ tags (array, 3 items)
```

**Components:**
- Textual `Tree` widget
- Rich `Text` styling for colors
- Recursive tree building from JSON

---

### 2. Keyboard Navigation

**What:**
Vim-inspired keyboard shortcuts for fast navigation.

**Why:**
Mouse is slow. Keyboard shortcuts make power users fast.

**Bindings:**
- **Tree**: `↑↓/jk` (move), `Space` (toggle), `←→/hl` (collapse/expand)
- **Records**: `n/p` (next/prev), `g/G` (first/last), `Ctrl+D/U` (jump ±10)
- **Actions**: `:` (goto), `?` (help), `q` (quit)

---

### 3. Status Information

**What:**
Always show: current position, total count (if known), loading state.

**Why:**
Users need orientation: "Where am I in the dataset?"

**Visual:**
```
┌─────────────────────────────────────────────┐
│ JSON Viewer          Record 5 of 1,234      │  ← Always visible
└─────────────────────────────────────────────┘
```

---

### 4. Error Handling

**What:**
Malformed JSON becomes a visible error record, not a crash.

**Why:**
Real data is messy. Viewer should show problems, not die.

**Example:**
```
▼ Record 47 [ERROR]
  ├─ _error: true
  ├─ type: "json_decode_error"
  ├─ message: "Unexpected token at line 1 col 15"
  └─ raw: "{\"invalid: json}"
```

---

## Tier 1: Essential Pro Features

These features transform the viewer from "useful" to "professional tool". Prioritize implementing these first after MVP.

---

### 1. Table Mode (Multi-Record View)

**What:**
Switch from tree (one record) to table (many records) for scanning datasets.

**Why:**
- **Single-record view**: Great for deep inspection
- **Table view**: Great for scanning, spotting patterns, comparing values

**When to Use:**
- **Tree mode**: API responses, nested objects, deep structures
- **Table mode**: Flat records, homogeneous data, quick scanning

**Visual:**
```
┌────────────────────────────────────────────────────────┐
│ JSON Viewer - Table Mode         1,234 records         │
├────┬─────────────────┬───────┬──────────┬─────────────┤
│ id │ name            │ age   │ city     │ status      │
├────┼─────────────────┼───────┼──────────┼─────────────┤
│ 1  │ Alice Johnson   │ 30    │ New York │ active      │
│ 2  │ Bob Smith       │ 25    │ Boston   │ active      │
│ 3  │ Carol Davis     │ 35    │ Chicago  │ pending     │
│ 4  │ Dave Wilson     │ 28    │ Seattle  │ inactive    │
│... │ ...             │ ...   │ ...      │ ...         │
└────┴─────────────────┴───────┴──────────┴─────────────┘

Press 't' to switch to tree mode
Press 'Enter' on a row to view full record
```

**How It Works:**
- Auto-detect: flat + homogeneous records → default to table mode
- Manual toggle: Press `t` to switch between tree/table modes
- Table → Tree transition: Press Enter on a row to see full record in tree view

**Components:**
- Textual `DataTable` widget (built-in)
- Mode switcher (tree ↔ table)
- Schema detector (check if records are flat/homogeneous)

**Configuration:**
```bash
# Force table mode
jn cat data.json | jn put "-~viewer?mode=table"

# Auto-detect (default)
jn cat data.json | jn put "-~viewer"  # Uses heuristics
```

---

### 2. Statistics Panel

**What:**
Collapsible side panel showing dataset overview: record count, field stats, null counts, unique values.

**Why:**
First question is always: **"What am I looking at?"**

Stats answer this immediately without manual exploration.

**Visual:**
```
┌─────────────────────┬──────────────────────────────┐
│ ▼ Statistics        │ ▼ Record 1                   │
│ Records: 1,234      │   ├─ id: 1                   │
│ Fields: 15          │   ├─ name: "Alice"           │
│                     │   └─ ...                     │
│ Field      Null%    │                              │
│ ─────────────────   │                              │
│ id         0%       │                              │
│ name       0%       │                              │
│ email      15%      │                              │
│ age        5%       │                              │
│ status     0%       │                              │
│   unique: 3         │                              │
│   (active: 80%)     │                              │
│   (pending: 15%)    │                              │
│   (inactive: 5%)    │                              │
└─────────────────────┴──────────────────────────────┘

Press 's' to toggle statistics panel
```

**Key Metrics:**
- Total records
- Field count
- Null percentage per field
- Unique value count (for low-cardinality fields)
- Type distribution (if heterogeneous)

**When to Show:**
- **Wide terminals** (>120 cols): Show by default
- **Narrow terminals** (<120 cols): Collapsed by default, toggle with `s`

**Components:**
- Textual `Container` with `Collapsible` widget
- Statistics aggregator (computes during load)
- Reactive updates (incremental if streaming)

---

### 3. Value Formatting

**What:**
Smart display formatting for dates, numbers, currencies, bytes, percentages.

**Why:**
Raw values are hard to comprehend. Formatting makes data readable.

**Examples:**
```
Before formatting:
  created_at: "2024-11-22T13:30:00Z"
  file_size: 1073741824
  revenue: 1234567.89
  success_rate: 0.453

After formatting:
  created_at: Nov 22, 1:30pm (2 hours ago)
  file_size: 1.0 GB
  revenue: $1.2M
  success_rate: 45.3%
```

**Detection Heuristics:**
- **Dates**: ISO 8601 format, field names like `*_at`, `*_date`
- **Bytes**: Field names like `*_size`, `*_bytes`, values > 1024
- **Currency**: Field names like `*price*`, `*amount*`, `*revenue*`
- **Percentage**: Field names like `*_rate`, `*_percent`, values 0-1

**Configuration:**
```bash
# Enable formatting (default)
jn cat data.json | jn put "-~viewer"

# Disable formatting (show raw)
jn cat data.json | jn put "-~viewer?format_values=false"
```

**Components:**
- `ValueFormatter` module with type-specific formatters
- Pattern detection (regex for dates, field name matching)
- Toggle: Press `f` to switch between formatted/raw display

---

### 4. Copy JSONPath

**What:**
Press `p` (or `y` for "yank") to copy the JSONPath of the currently selected node to clipboard.

**Why:**
**Workflow integration**: Viewer is exploration, `jn filter` is transformation.

Users explore data in viewer, find interesting fields, then need to reference those fields in filter commands. Copy JSONPath bridges this gap.

**Example Workflow:**
```
Step 1: Explore in viewer
  $ jn cat data.json | jn put "-~viewer"

  ▼ Record 0
    ▼ user
      ▼ address
        ▶ city: "New York"  ← Navigate here, press 'p'

  [Toast] Copied: $.user.address.city

Step 2: Use in filter
  $ jn cat data.json | jn filter '.user.address.city == "New York"'
  # Paste from clipboard: .user.address.city
```

**Visual Feedback:**
```
┌─────────────────────────────────────────────┐
│ ✓ Copied: $.records[0].user.address.city   │  ← Toast notification
└─────────────────────────────────────────────┘
```

**Components:**
- Path tracker (build JSONPath during tree construction)
- Clipboard integration (`pyperclip` or Textual clipboard API)
- Toast notification widget

**Configuration:**
```bash
# Works automatically, no config needed
# Just navigate to any node and press 'p'
```

---

### 5. Streaming/Incremental Rendering

**What:**
Display records as they arrive from stdin, don't wait to buffer the entire stream.

**Why:**
**JN philosophy**: Tools process incrementally, users see progress immediately.

Buffering 1M records before showing anything violates Unix pipe principles and feels broken.

**Experience:**
```
$ jn cat huge.json | jn put "-~viewer"

# 100ms later:
┌─────────────────────────────────────────────┐
│ JSON Viewer          Record 1 (loading...)  │  ← Shows immediately
├─────────────────────────────────────────────┤
│ ▼ Record                                    │
│   ├─ id: 1                                  │
│   └─ ...                                    │
└─────────────────────────────────────────────┘

# 1 second later:
┌─────────────────────────────────────────────┐
│ JSON Viewer          Record 1 (1,234 loaded)│  ← Updates live
└─────────────────────────────────────────────┘

# 10 seconds later:
┌─────────────────────────────────────────────┐
│ JSON Viewer          Record 1 of 1,234,567  │  ← Complete
└─────────────────────────────────────────────┘
```

**How It Works:**
- Start Textual app immediately (async loading)
- Read stdin in background task
- Display first record as soon as it arrives
- Update count as more records stream in
- User can navigate already-loaded records while rest still loading

**Components:**
- Textual async data loading (`App.run()` with async callback)
- Reactive state updates (record count, loading status)
- Progress indicator in header

---

## Tier 2: Power User Features

These features make the viewer more efficient for frequent users. Implement after Tier 1 is stable.

---

### 6. Quick Stats in Table Mode

**What:**
Footer row showing aggregations: sum, avg, min, max for numeric columns.

**Why:**
Every spreadsheet and database tool has column totals. Tables feel incomplete without aggregations.

**Visual:**
```
┌────┬─────────────────┬─────┬──────────┐
│ id │ name            │ age │ revenue  │
├────┼─────────────────┼─────┼──────────┤
│ 1  │ Alice Johnson   │ 30  │ $50,000  │
│ 2  │ Bob Smith       │ 25  │ $45,000  │
│ 3  │ Carol Davis     │ 35  │ $60,000  │
├────┼─────────────────┼─────┼──────────┤
│ 3  │ 3 unique names  │ avg │ sum      │  ← Footer row
│    │                 │ 30  │ $155,000 │
└────┴─────────────────┴─────┴──────────┘
```

**Aggregations:**
- **Numeric columns**: sum, avg, min, max
- **String columns**: unique count
- **All columns**: null count, total count

**Components:**
- Aggregation module (compute stats per column)
- DataTable footer row (distinct styling)
- Toggle: Press `a` to show/hide aggregations

---

### 7. Export Current View

**What:**
Press `x` to export currently visible data to a file (JSON, CSV, or NDJSON).

**Why:**
**Complete the workflow**: Explore → filter → collapse → export subset.

Users find 10 interesting records in 10K dataset and want to save them for later analysis.

**Visual:**
```
User presses 'x':

┌─ Export Current View ─────────────────┐
│ Filename: interesting_records.json    │
│ Format:  ◉ JSON  ○ CSV  ○ NDJSON     │
│                                       │
│ Records to export: 10 of 1,234        │
│ (respects current filters/collapsed)  │
│                                       │
│          [Export]  [Cancel]           │
└───────────────────────────────────────┘

After export:
  [Toast] ✓ Exported 10 records to interesting_records.json
```

**What Gets Exported:**
- In tree mode: Current record only (or all records if configured)
- In table mode: All visible rows (respects filtering)
- Collapsed nodes: Not included (export what you see)

**Components:**
- Export dialog (Textual `Screen` with `Input` and radio buttons)
- File writer (reuse existing json_/csv_ plugin logic)
- Format selector

---

### 8. Command Palette

**What:**
Press `Ctrl+P` to open fuzzy-searchable list of all available commands.

**Why:**
**Discoverability**: 30+ keyboard shortcuts is overwhelming. Fuzzy search makes features discoverable.

**Modern pattern**: VSCode, GitHub, Slack all use command palettes.

**Visual:**
```
User presses Ctrl+P:

┌─ Command Palette ──────────────────────┐
│ > _                                    │
├────────────────────────────────────────┤
│ ▶ Toggle Table/Tree Mode               │
│   Toggle Statistics Panel              │
│   Export Current View                  │
│   Copy JSONPath                        │
│   Expand All Nodes                     │
│   Collapse All Nodes                   │
│   Go to Record...                      │
│   Show Help                            │
└────────────────────────────────────────┘

User types "exp":

┌─ Command Palette ──────────────────────┐
│ > exp_                                 │
├────────────────────────────────────────┤
│ ▶ Expand All Nodes                     │  ← Fuzzy match
│   Export Current View                  │
│   Explore in Detail Mode               │
└────────────────────────────────────────┘
```

**Benefits:**
- **New users**: Don't need to memorize shortcuts
- **Power users**: Faster than reaching for menu
- **Accessibility**: Keyboard-accessible always

**Components:**
- Textual `Screen` (modal overlay)
- Textual `Input` widget (fuzzy search)
- Textual `ListView` (filtered commands)
- Command registry (maps names → actions)

---

### 9. Smart Field Selection

**What:**
Auto-hide low-importance fields when screen is narrow. Show only high-value fields.

**Why:**
JSON records with 50+ fields don't fit on 80-column terminals.

Smart selection shows what matters, hides noise.

**Selection Strategy:**

**1. Explicit filters** (highest priority):
```bash
jn cat data.json | jn put "-~viewer?fields=name,email,age"
jn cat data.json | jn put "-~viewer?exclude=_id,metadata"
```

**2. Priority hints**:
```bash
jn cat data.json | jn put "-~viewer?priority=name,status"
# Shows priority fields first, others if space permits
```

**3. Heuristics** (auto-scoring):
- Field names: `id`, `name`, `email`, `status` → high score
- Short names (≤5 chars) → higher score
- Non-null values → higher score
- Primitive types → higher score
- Starts with `_` → lower score

**4. Terminal adaptation**:
- Wide terminal (>120 cols): Show all fields
- Medium (80-120 cols): Show top 50% by score
- Narrow (<80 cols): Show top 25% by score

**Visual (narrow terminal):**
```
Terminal width: 80 columns
Record has 20 fields, showing top 6:

▼ Record 1
  ├─ id: 1
  ├─ name: "Alice Johnson"
  ├─ email: "alice@example.com"
  ├─ status: "active"
  ├─ age: 30
  └─ ... (14 more fields - press 'a' to show all)
```

**Components:**
- Field scorer (importance heuristics)
- Terminal size detector
- Field selector (choose top N by score)

---

## Tier 3: Advanced Features

These are powerful but niche. Implement only if users request them.

---

### 10. Split View / Compare Mode

**What:**
View two records side by side with differences highlighted.

**Why:**
**Debugging workflow**: "Why did request A succeed but B fail?"

Comparing API responses, finding data inconsistencies, debugging errors.

**Visual:**
```
User selects record 0, presses 'c', then selects record 5:

┌─ Compare: Record 0 vs Record 5 ────────────────┐
│ Record 0            │ Record 5                 │
├─────────────────────┼──────────────────────────┤
│ ▼ Data              │ ▼ Data                   │
│   id: 1             │   id: 6                  │
│   name: "Alice"     │   name: "Alice"          │
│   status: "active"  │   status: "failed" [!]   │ ← Highlighted
│   error: null       │   error: "Timeout" [!]   │ ← Highlighted
│   ...               │   ...                    │
└─────────────────────┴──────────────────────────┘

Colors:
  - Green: Only in left
  - Red: Only in right
  - Yellow: Different values
  - White: Same values
```

**Components:**
- Textual `Horizontal` container (two Tree widgets side by side)
- Diff algorithm (deep object comparison)
- Conditional styling (color differences)

---

### 11. Type Inference Display

**What:**
Show inferred schema: field names, types, nullability, enums.

**Why:**
**Understand data shape** at a glance. Find type inconsistencies.

**Visual:**
```
Press 'i' to toggle schema view:

┌─ Inferred Schema ────────────────────┐
│ {                                    │
│   id: int,                           │
│   name: string,                      │
│   email: string | null (15% null),   │
│   age: int | null (5% null),         │
│   status: enum(                      │
│     "active" (80%),                  │
│     "pending" (15%),                 │
│     "inactive" (5%)                  │
│   ),                                 │
│   address: {                         │
│     city: string,                    │
│     zip: string | int [MIXED!]       │ ← Type mismatch warning
│   },                                 │
│   tags: array<string>                │
│ }                                    │
└──────────────────────────────────────┘
```

**Inference Rules:**
- Scan all records, track observed types per field
- Detect enums (≤10 unique values)
- Flag type mismatches (field is sometimes string, sometimes int)
- Compute null percentage

**Components:**
- Type inference module (scan values, aggregate types)
- Schema display widget (formatted output)
- Modal view (toggle on/off)

---

### 12. Pattern Highlighting

**What:**
Automatically highlight duplicates, outliers, nulls, type mismatches.

**Why:**
**Visual data quality checks**. Spot issues without reading every value.

**Visual:**
```
┌─ Records (Pattern Highlighting: ON) ──┐
│ ▼ Record 0                             │
│   id: 1                                │
│   name: "Alice"                        │
│   status: "active" [PURPLE]            │ ← Duplicate (80% of records)
│   age: 30                              │
│                                        │
│ ▼ Record 1                             │
│   id: 2                                │
│   name: "Bob"                          │
│   status: "active" [PURPLE]            │ ← Duplicate
│   age: "unknown" [ORANGE]              │ ← Type mismatch (should be int)
│                                        │
│ ▼ Record 2                             │
│   id: 3                                │
│   name: "Carol"                        │
│   status: "pending"                    │
│   age: 150 [YELLOW]                    │ ← Outlier (>2 std dev)
└────────────────────────────────────────┘
```

**Patterns Detected:**
- **Duplicates**: Value appears 5+ times → purple background
- **Outliers**: Numeric value >2 std deviations → yellow background
- **Nulls**: Null in mostly-populated field → dim red
- **Type mismatches**: String in int column → orange background

**Components:**
- Pattern detector (statistical analysis)
- Conditional styling (Rich text styling)
- Toggle: Press `h` to enable/disable highlighting

---

### 13. Smart Column Widths (Table Mode)

**What:**
Dynamically size columns based on content, not fixed widths.

**Why:**
`id` column doesn't need 20 characters. `description` needs more space.

**Visual:**
```
Before (fixed widths):
┌────────────────────┬────────────────────┬────────────────────┐
│ id                 │ name               │ description        │
├────────────────────┼────────────────────┼────────────────────┤
│ 1                  │ Alice Johnson      │ Senior Engineer... │

After (smart widths):
┌────┬─────────────────┬─────────────────────────────────────┐
│ id │ name            │ description                         │
├────┼─────────────────┼─────────────────────────────────────┤
│ 1  │ Alice Johnson   │ Senior Engineer with 10 years exp   │
```

**Algorithm:**
1. Scan all values in each column
2. Compute max content length per column
3. Allocate width proportionally (with min/max constraints)
4. Respect terminal width

**Components:**
- Column width calculator
- Proportional allocation algorithm
- DataTable column configuration

---

## Architecture Evolution

### MVP Architecture (Single-Record Viewer)

```
JSONViewerApp
├─ Header (title + position)
├─ TreeView (single record)
└─ Footer (key hints)

Data: List[dict] + current_index
```

**Simple and focused.**

---

### Pro Architecture (Full-Featured)

```
JSONViewerApp (Textual App)
├─ Header
│  └─ Title + Record Position + Status
├─ MainContainer (responsive layout)
│  ├─ StatisticsPanel (collapsible, optional)
│  └─ ContentView (one of:)
│     ├─ TreeView (single-record tree)
│     ├─ TableView (multi-record table)
│     └─ CompareView (side-by-side diff)
├─ Footer
│  └─ Key Hints + Status
└─ Modals (conditional)
   ├─ CommandPalette (Ctrl+P)
   ├─ ExportDialog (x)
   ├─ GotoDialog (:)
   └─ HelpScreen (?)

Data Model:
├─ RecordStore (all records, streaming)
├─ ViewState (current mode, filters, position)
├─ Statistics (aggregated metrics)
└─ Settings (user preferences)
```

**Modular and extensible.**

---

### Key Modules

**Core:**
- `json_viewer.py` - Main plugin entry, CLI interface
- `app.py` - JSONViewerApp (Textual App)
- `data_model.py` - RecordStore, Statistics, ViewState

**Views:**
- `tree_view.py` - TreeView component
- `table_view.py` - TableView component
- `compare_view.py` - CompareView component (split screen)

**Components:**
- `statistics_panel.py` - Statistics sidebar
- `status_bar.py` - Status and key hints
- `command_palette.py` - Command search
- `export_dialog.py` - Export UI
- `goto_dialog.py` - Jump to record N

**Utilities:**
- `formatters.py` - Value formatting (dates, numbers, bytes)
- `path_tracker.py` - JSONPath tracking
- `type_inference.py` - Schema inference
- `pattern_detector.py` - Anomaly detection (duplicates, outliers)
- `aggregators.py` - Statistics (sum, avg, min, max)
- `field_selector.py` - Smart field prioritization

---

## Implementation Roadmap

### Sprint 1: MVP (Week 1)
**Goal:** Working single-record viewer

- [ ] Basic Textual app structure
- [ ] RecordStore (load, navigate)
- [ ] TreeView (recursive JSON → Tree)
- [ ] Syntax highlighting
- [ ] Keyboard bindings (n, p, g, G, q, Space)
- [ ] Test with real data

**Deliverable:** `jn cat data.json | jn put "-~viewer"` works

---

### Sprint 2: Table Mode (Week 2)
**Goal:** View multiple records

- [ ] TableView component (DataTable widget)
- [ ] Mode detection (flat/homogeneous → table)
- [ ] Mode switcher (`t` key)
- [ ] Row → Tree transition (Enter on row)

**Deliverable:** Can scan many records at once

---

### Sprint 3: Data Understanding (Week 3)
**Goal:** Context and clarity

- [ ] Statistics panel (records, fields, nulls, uniques)
- [ ] Value formatting (dates, numbers, currencies)
- [ ] Responsive layout (stats panel collapses on narrow screens)

**Deliverable:** Users understand datasets at a glance

---

### Sprint 4: Workflow Integration (Week 4)
**Goal:** Bridge exploration → transformation

- [ ] Copy JSONPath (`p` key, clipboard)
- [ ] Export current view (`x` key, dialog)
- [ ] Command palette (Ctrl+P, fuzzy search)
- [ ] Streaming/incremental rendering

**Deliverable:** Seamless JN pipeline integration

---

### Sprint 5: Power User Features (Week 5)
**Goal:** Efficiency for frequent users

- [ ] Quick stats in table mode (footer aggregations)
- [ ] Smart field selection (auto-hide low-value fields)
- [ ] Jump navigation (Ctrl+D/U, `:123`)

**Deliverable:** Fast, efficient data exploration

---

### Sprint 6+: Advanced Features (Week 6+)
**Goal:** Deep analysis capabilities

- [ ] Split view / compare mode
- [ ] Type inference display
- [ ] Pattern highlighting
- [ ] Smart column widths

**Deliverable:** Professional analysis tool

---

## Configuration Reference

### CLI Arguments

```bash
jn put "-~viewer?<params>"
```

**Params:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | `auto\|tree\|table` | `auto` | View mode |
| `depth` | int | 2 | Initial tree expansion depth |
| `start_at` | int | 0 | Start at record N (0-based) |
| `fields` | string | (all) | Comma-separated fields to show |
| `exclude` | string | (none) | Comma-separated fields to hide |
| `priority` | string | (auto) | Comma-separated priority fields |
| `format_values` | bool | true | Apply value formatting |
| `show_stats` | bool | auto | Show statistics panel |
| `max_records` | int | 10000 | Max records to load |

**Examples:**

```bash
# Basic
jn cat data.json | jn put "-~viewer"

# Force table mode
jn cat data.json | jn put "-~viewer?mode=table"

# Start at record 100
jn cat data.json | jn put "-~viewer?start_at=100"

# Show only specific fields
jn cat users.json | jn put "-~viewer?fields=name,email,city"

# Hide metadata
jn cat data.json | jn put "-~viewer?exclude=_id,_metadata"

# Deep tree view
jn cat nested.json | jn put "-~viewer?depth=5"

# Disable formatting
jn cat data.json | jn put "-~viewer?format_values=false"
```

---

## Why This Roadmap Works

### Incremental Value
Each sprint delivers working, useful features. Users get value early, provide feedback, guide direction.

### Clear Priorities
Tier 1 features are must-haves. Tier 2 are nice-to-haves. Tier 3 are build-if-requested.

### Learning Curve
Start simple (one widget), learn patterns, add complexity gradually.

### User-Driven
Build core, ship it, listen to users. They'll tell us what features matter most.

### Manageable Scope
Each sprint is 1 week. Features are independent. Can pause/pivot anytime.

---

## Summary

**The Journey:**

1. **Week 1**: Single-record viewer (MVP) - Validate concept
2. **Week 2**: Add table mode - View many records
3. **Week 3**: Add stats + formatting - Understand data
4. **Week 4**: Add copy/export/palette - Workflow integration
5. **Week 5**: Add power features - Efficiency boost
6. **Week 6+**: Add advanced features - Deep analysis

**The Vision:**

A professional JSON data viewer that:
- **Feels natural** in the terminal
- **Integrates seamlessly** with JN pipelines
- **Makes data comprehensible** at a glance
- **Grows with user needs** (simple → powerful)

**The Philosophy:**

Not building an app. Building a **data lens** that sits in pipelines and makes JSON visible.

Simple by default. Powerful when needed. Always composable.

```bash
# The simplest use case
jn cat data.json | jn put "-~viewer"

# The most complex use case
jn cat @api/complex | \
  jn filter '.status == "error"' | \
  jn put "-~viewer?mode=table&fields=id,message,timestamp&show_stats=true"
```

**Both work. Both feel natural. That's the goal.**
