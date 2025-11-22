# Textual JSON Viewer Design

**Date:** 2025-11-22
**Status:** Design / Planned
**Type:** Display Plugin
**Author:** Claude (based on user requirements)

---

## Table of Contents

1. [Overview](#overview)
2. [Current State Analysis](#current-state-analysis)
3. [Goals](#goals)
4. [Design Decisions](#design-decisions)
5. [Architecture](#architecture)
6. [Plugin Specification](#plugin-specification)
7. [UI Design](#ui-design)
8. [Implementation Details](#implementation-details)
9. [Usage Examples](#usage-examples)
10. [Future Enhancements](#future-enhancements)
11. [References](#references)

---

## Overview

**Problem Statement:**
Currently, JN users viewing JSON/NDJSON data must either:
- Use raw JSON output (hard to read, no hierarchy visualization)
- Use static table output (loses nested structure, no interactivity)
- Pipe to external tools like `jq` or `less` (breaks the JN pipeline UX)

**Solution:**
A Textual-based interactive JSON viewer plugin (`json_viewer.py`) that provides:
- Beautiful, hierarchical display of JSON structures
- Expandable/collapsible nodes for nested data
- Interactive navigation (keyboard/mouse)
- Smart field selection based on screen size
- User-configurable field filtering
- Multiple view modes (tree, table, detail)
- Responsive rendering that adapts to terminal dimensions

**Key Benefit:**
Users get a **git-diff-like experience for JSON data** - beautiful, interactive, and terminal-native.

---

## Current State Analysis

### Existing Table Plugin (`table_.py`)

**Architecture:**
```python
def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, write as formatted table to stdout."""
    # Uses tabulate library
    # Buffers all records in memory
    # Outputs static text table
```

**Strengths:**
- Simple, reliable
- Many output formats (grid, markdown, HTML, etc.)
- Handles heterogeneous schemas (union of all keys)

**Limitations:**
- ❌ No interactivity (static output)
- ❌ Loses nested structure (flattens objects)
- ❌ No navigation (once printed, can't explore)
- ❌ Poor handling of deep nesting (becomes unreadable)
- ❌ No filtering after display
- ❌ Fixed width - doesn't adapt to screen size intelligently

### Plugin Architecture Review

**JN Display Plugins:**
- **Type:** "writes-only" plugins (no `reads()` function)
- **Input:** NDJSON stream via stdin
- **Output:** Human-readable format to stdout
- **Execution:** `jn cat data.json | jn put "-~viewer"`
- **Pattern:** Invoke with `--mode write`

**Critical Requirements:**
1. PEP 723 metadata block
2. UV shebang for dependency isolation
3. Standalone executable (no framework imports)
4. Matches patterns in `[tool.jn]`
5. Works as subprocess in pipeline

---

## Goals

### Functional Goals

1. **Hierarchical Visualization**
   - Display JSON objects and arrays as expandable tree structures
   - Preserve parent-child relationships visually
   - Support unlimited nesting depth (with configurable limits)

2. **Interactive Navigation**
   - Keyboard: Arrow keys, Page Up/Down, Home/End, Space (expand/collapse), Enter (select)
   - Mouse: Click to expand/collapse, scroll
   - Search: `/` to search field names or values

3. **Smart Rendering**
   - Detect terminal dimensions (rows, columns)
   - Auto-truncate long strings with ellipsis
   - Auto-select most important fields when space is limited
   - Configurable field priority (user can specify which fields to show first)

4. **Multiple View Modes**
   - **Tree Mode** (default): Hierarchical, expandable tree
   - **Table Mode**: Flattened records in tabular format (for homogeneous arrays)
   - **Detail Mode**: Single-record deep inspection

5. **Field Filtering**
   - **Include filter**: `fields=name,email,address.city` (show only these)
   - **Exclude filter**: `exclude=metadata,_internal` (hide these)
   - **Priority filter**: `priority=name,email` (show these first when truncating)

6. **Collapsibility**
   - Collapse/expand individual nodes
   - Collapse all at depth N (e.g., show only 2 levels initially)
   - Remember expansion state during session

### Non-Functional Goals

1. **Performance**
   - Handle 10K+ records without lag (virtual scrolling)
   - Lazy rendering (only render visible rows)
   - Incremental loading (start displaying before full stream read)

2. **UX Excellence**
   - Syntax highlighting (different colors for keys, strings, numbers, booleans, null)
   - Clear visual hierarchy (indentation, guides)
   - Status bar with navigation hints
   - Error handling (malformed JSON → show error record)

3. **JN Integration**
   - Works in standard pipeline: `jn cat data.json | jn put "-~viewer"`
   - Accepts standard config params: `jn put "-~viewer?mode=tree&depth=3"`
   - Passes through errors gracefully

---

## Design Decisions

### 1. Textual vs. Alternatives

**Why Textual over Urwid/Blessed/Curses:**

| Library | Pros | Cons | Verdict |
|---------|------|------|---------|
| **Textual** | Modern (2025), async, rich styling, active development, great docs, built-in widgets (Tree, DataTable) | Newer (less battle-tested) | ✅ **CHOSEN** |
| Urwid | Mature, stable, pyfx uses it | Older API, less active, no built-in tree widget | ❌ |
| Blessed | Simple, lightweight | No high-level widgets, manual everything | ❌ |
| Rich | Beautiful output | Not interactive (static rendering only) | ❌ Used for styling only |

**Textual Advantages:**
- Built-in `Tree` widget (perfect for JSON hierarchy)
- Built-in `DataTable` widget (perfect for record arrays)
- Reactive programming model (easy to build interactive UIs)
- Excellent documentation and examples
- Active community (2025 updates)

### 2. View Modes

**Mode Selection Logic:**

```python
def detect_view_mode(records: List[dict]) -> str:
    """Auto-detect best view mode for data."""
    if len(records) == 0:
        return "empty"

    if len(records) == 1:
        # Single record → detail mode (show all fields)
        return "detail"

    # Check if records are homogeneous (same keys)
    first_keys = set(records[0].keys())
    if all(set(r.keys()) == first_keys for r in records[:min(100, len(records))]):
        # Check if records are flat (no nested objects/arrays)
        if all(_is_flat(r) for r in records[:min(10, len(records))]):
            return "table"  # Flat, homogeneous → table mode

    # Default: tree mode for heterogeneous or nested data
    return "tree"
```

**Override:** User can force mode with `mode=tree|table|detail` parameter

### 3. Field Selection Strategy

**Problem:** JSON records with 50+ fields don't fit on a 80-column terminal.

**Solution:** Multi-level field selection

**Level 1: Explicit Filters** (highest priority)
```bash
jn put "-~viewer?fields=name,email,age"  # Show only these
jn put "-~viewer?exclude=metadata,_id"   # Hide these
```

**Level 2: Priority Hints** (when screen too small for all fields)
```bash
jn put "-~viewer?priority=name,email"    # Show these first
```

**Level 3: Heuristics** (auto-detect important fields)
```python
def score_field_importance(field_name: str, value: Any) -> int:
    """Score field importance (higher = more important)."""
    score = 0

    # Common important field names
    if field_name in ['id', 'name', 'title', 'email', 'status']:
        score += 10

    # Short field names (likely important)
    if len(field_name) <= 5:
        score += 5

    # Non-null values
    if value is not None:
        score += 3

    # Primitive types (vs. nested objects)
    if isinstance(value, (str, int, float, bool)):
        score += 2

    # Penalize private/metadata fields
    if field_name.startswith('_'):
        score -= 5

    return score
```

**Level 4: Terminal Size Adaptation**
```python
def select_visible_fields(
    all_fields: List[str],
    terminal_width: int,
    avg_field_width: int = 20
) -> List[str]:
    """Select fields that fit on screen."""
    max_fields = max(3, terminal_width // avg_field_width)
    return all_fields[:max_fields]
```

### 4. Collapsibility & Depth

**Default Behavior:**
- **Tree Mode**: Expand to depth 2 initially (show structure, hide details)
- **Table Mode**: Always expanded (flat by definition)
- **Detail Mode**: Expand to depth 3 (show nested objects)

**User Controls:**
- `depth=N` parameter: Initial expansion depth
- **Space**: Expand/collapse current node
- **E**: Expand all
- **C**: Collapse all
- **1-9**: Collapse to depth N

**Implementation:**
```python
class JSONTreeNode:
    def __init__(self, data, depth=0, max_depth=2):
        self.data = data
        self.depth = depth
        self.expanded = depth < max_depth  # Auto-collapse beyond max_depth
        self.children = []
```

### 5. Performance Strategy

**Challenge:** Displaying 10K+ records in terminal without lag

**Solutions:**

**a) Virtual Scrolling** (only render visible rows)
```python
# Textual's Tree widget handles this automatically
# Only visible nodes are rendered
```

**b) Lazy Loading** (incremental rendering)
```python
def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, display interactively."""
    app = JSONViewerApp(config=config)

    # Start app BEFORE reading all records
    async def load_data():
        for line in sys.stdin:
            record = json.loads(line)
            app.add_record(record)  # Incremental update

    app.run(inline_async=load_data)
```

**c) Pagination** (for massive datasets)
```python
# Show first 10K records, allow "Load More" button
MAX_RECORDS = config.get('max_records', 10_000)
```

---

## Polished Features & Professional UX

This section describes advanced features that elevate the viewer from "functional" to "polished professional tool". These are prioritized by value/complexity ratio and alignment with JN's philosophy.

### Tier 1: Core Polish (Must-Have)

#### 1. Streaming/Incremental Rendering

**What:**
Display records as they arrive on stdin, not after buffering the entire stream.

**Why:**
- **JN's philosophy**: Unix pipes stream data, tools process incrementally
- **User expectation**: `jn cat huge.json | jn put "-~viewer"` should show first records within 100ms, not after 30 seconds
- **Real impact**: Difference between feeling "instant" vs "broken"
- **Large datasets**: Users with 1M+ records need to see progress

**How it Fits:**
Textual is async-native and supports this pattern naturally. The `App.run()` method accepts an async callback that can read stdin while the UI is rendering.

**Components:**
- Textual `App` with async data loading
- Reactive updates to tree/table as records arrive
- Progress indicator showing "Loaded 1,234 records..."

**User Experience:**
```bash
$ jn cat massive.json | jn put "-~viewer"
# Viewer opens immediately with "Loading..." message
# After 100ms: Shows first 10 records, "Loaded 10 records (streaming...)"
# After 1s: Shows first 1000 records, user can already start exploring
# After 10s: Full dataset loaded, "Loaded 1,234,567 records (complete)"
```

---

#### 2. Statistics Panel

**What:**
Side panel (or collapsible section) showing dataset statistics:
- Total record count
- Field name list with null counts
- Unique value counts for low-cardinality fields
- Type distribution (50% strings, 30% ints, 20% nulls)

**Why:**
- **First question**: "What am I looking at?" - stats answer this immediately
- **Informs decisions**: "90% have null emails" → filter strategy clear
- **Data quality**: Spot issues (unexpected nulls, type inconsistencies)
- **Professional expectation**: DBeaver, Excel, Pandas all show stats

**How it Fits:**
- Statistics are computed during data loading (single pass)
- Displayed in a `Static` widget (collapsible to save space)
- Updates incrementally if using streaming mode

**Components:**
- Textual `Container` with `Collapsible` widget
- Statistics aggregator module (computes stats during load)
- Reactive display that updates as records arrive

**User Experience:**
```
┌─ Statistics ────────────────────────┐
│ Records: 1,234                      │
│ Fields: 15                          │
│                                     │
│ Field          Null%   Unique      │
│ ──────────────────────────────────  │
│ id             0%      1,234        │
│ name           0%      892          │
│ email          15%     1,050        │
│ status         0%      3 (active,   │
│                          pending,   │
│                          inactive)  │
│ age            5%      45           │
└─────────────────────────────────────┘
```

---

#### 3. Value Formatting

**What:**
Smart display formatting for common data types:
- **Dates**: `2024-11-22T15:30:00Z` → `Nov 22, 3:30pm` (relative: "2 hours ago")
- **Large numbers**: `1234567` → `1.2M`, `1234` → `1.2K`
- **Currencies**: `1234.56` → `$1,234.56` (if field name contains "price"/"amount")
- **Bytes**: `1073741824` → `1.0 GB`
- **Percentages**: `0.453` → `45.3%` (if field name contains "percent"/"rate")
- **URLs**: Clickable links (if terminal supports)

**Why:**
- **Readability**: Formatted values are easier to comprehend
- **Context**: "2 hours ago" is more useful than ISO timestamp for recent data
- **Professional polish**: Raw values feel unfinished
- **Easy win**: Pure display logic, no architectural complexity

**How it Fits:**
Formatting layer sits between data model and display. Uses heuristics (field names, value patterns) to detect type and apply formatting.

**Components:**
- `ValueFormatter` module with formatters for each type
- Pattern detection (regex for dates, field name hints for currencies)
- Configuration option to disable formatting (show raw values)

**User Experience:**
```
Before:
  created_at: "2024-11-22T13:30:00Z"
  file_size: 1073741824
  price: 1234.56

After:
  created_at: Nov 22, 1:30pm (2 hours ago)
  file_size: 1.0 GB
  price: $1,234.56
```

---

#### 4. Copy JSONPath to Current Node

**What:**
Press `p` (or `y` for "yank") to copy the JSONPath to the currently selected node to clipboard.

**Why:**
- **Workflow integration**: Viewer is exploration, jq/filter is manipulation
- **Bridge the gap**: "Found the field!" → copy path → `jn filter '.users[0].address.city'`
- **Developer-friendly**: JSONPath is precise, machine-readable
- **Common task**: Every exploration session ends with "now filter on this field"

**How it Fits:**
During tree building, track the JSONPath to each node. When user presses `p`, copy current path to clipboard and show confirmation toast.

**Components:**
- Path tracking during tree construction (`$.users[0].address.city`)
- Clipboard integration (use `pyperclip` or Textual's clipboard API)
- Toast notification: "Copied: $.users[0].address.city"

**User Experience:**
```
User navigates tree:
  ▼ Record 0
    ▼ address
      ▶ city: "New York"  ← cursor here

User presses 'p':
  [Toast] Copied: $.records[0].address.city

User in terminal:
  $ jn cat data.json | jn filter '.records[0].address.city'
  # Paste from clipboard: $.records[0].address.city
```

---

### Tier 2: Enhanced Polish (Should-Have)

#### 5. Quick Stats in Table Mode

**What:**
Footer row in table mode showing aggregations:
- Numeric columns: sum, avg, min, max
- String columns: unique count
- All columns: null count

**Why:**
- **Table stakes**: Every spreadsheet/DB tool has column totals
- **Immediate insight**: "Revenue sum: $1.2M" without leaving viewer
- **Expected UX**: Tables without aggregations feel incomplete
- **Low cost**: Single aggregation pass, DataTable supports footers

**How it Fits:**
When rendering table mode, compute aggregations and add as footer row. DataTable widget supports this natively with `add_row()` and styling.

**Components:**
- Aggregation module (sum/avg/min/max per column)
- DataTable footer row with distinct styling
- Configuration to show/hide footer

**User Experience:**
```
┌──────────────────────────────────────────────────┐
│ id  │ name           │ age │ revenue            │
├─────┼────────────────┼─────┼────────────────────┤
│ 1   │ Alice Johnson  │ 30  │ $50,000            │
│ 2   │ Bob Smith      │ 25  │ $45,000            │
│ 3   │ Carol Davis    │ 35  │ $60,000            │
├─────┼────────────────┼─────┼────────────────────┤
│ 3   │ 3 unique       │ avg │ sum                │
│ recs│                │ 30  │ $155,000           │
└─────┴────────────────┴─────┴────────────────────┘
```

---

#### 6. Export Current View

**What:**
Press `x` to export currently visible data (respecting filters, collapsed nodes) to a file in JSON or CSV format.

**Why:**
- **Complete workflow**: Explore → filter → collapse → export subset
- **Real use case**: "Found 10 anomalies in 10K records, save for analysis"
- **JN philosophy**: Transformations are visible and exportable
- **User control**: Export what you see, not the entire dataset

**How it Fits:**
When user presses `x`, prompt for filename and format. Write currently visible records (those not filtered out or hidden by collapsed nodes) to file.

**Components:**
- Export dialog (Textual `Input` widget for filename)
- Format selector (JSON/CSV/NDJSON radio buttons)
- File writer using existing json_/csv_ plugin logic

**User Experience:**
```
User filters down to 10 interesting records, presses 'x':

┌─ Export Current View ─────────────────┐
│ Filename: anomalies.json              │
│ Format:  ◉ JSON  ○ CSV  ○ NDJSON     │
│                                       │
│ Records to export: 10 of 1,234        │
│                                       │
│ [Export]  [Cancel]                    │
└───────────────────────────────────────┘

After export:
  [Toast] Exported 10 records to anomalies.json
```

---

#### 7. Command Palette

**What:**
Press `Ctrl+P` to open fuzzy-searchable command palette listing all available actions.

**Why:**
- **Discoverability**: 30 keyboard shortcuts is overwhelming
- **Modern pattern**: VSCode, GitHub, Slack all use this
- **Fuzzy search**: "exp" → "Expand All", "col" → "Collapse to Depth"
- **New user friendly**: Don't need to memorize shortcuts upfront
- **Power user friendly**: Still faster than mousing to menus

**How it Fits:**
Textual supports modal dialogs and input widgets. Command palette is a filterable list that executes actions when selected.

**Components:**
- Textual `Screen` (modal overlay)
- Textual `Input` for fuzzy search
- Textual `ListView` for filtered commands
- Command registry mapping names to actions

**User Experience:**
```
User presses Ctrl+P:

┌─ Command Palette ──────────────────────┐
│ > exp_                                 │
├────────────────────────────────────────┤
│ ▶ Expand All                           │
│   Expand Current Node                  │
│   Export Current View                  │
│   Explore in Detail Mode               │
└────────────────────────────────────────┘

User types "col":

┌─ Command Palette ──────────────────────┐
│ > col_                                 │
├────────────────────────────────────────┤
│ ▶ Collapse All                         │
│   Collapse to Depth 1                  │
│   Collapse to Depth 2                  │
│   Collapse Current Node                │
└────────────────────────────────────────┘
```

---

### Tier 3: Advanced Polish (Nice-to-Have)

#### 8. Split View / Compare Mode

**What:**
View two records side by side with differences highlighted. Select a record and press `c` (compare), then select another record to see diff.

**Why:**
- **Debugging workflow**: "Why did request A succeed but B fail?"
- **API responses**: Compare expected vs actual
- **Data quality**: Find inconsistencies between similar records
- **Visual clarity**: Side-by-side is easier than toggling

**How it Fits:**
Split screen into two `Tree` widgets side by side. Build both trees simultaneously, highlighting differing values with color (green=only in A, red=only in B, yellow=different values).

**Components:**
- Textual `Horizontal` container with two `Tree` widgets
- Diff algorithm (deep comparison of objects)
- Conditional styling for highlighting differences

**User Experience:**
```
┌─ Compare: Record 0 vs Record 5 ────────────────────────┐
│ Record 0                │ Record 5                     │
├─────────────────────────┼──────────────────────────────┤
│ ▼ Data                  │ ▼ Data                       │
│   id: 1                 │   id: 6                      │
│   name: "Alice"         │   name: "Alice"              │
│   status: "active"      │   status: "failed"   [DIFF]  │
│   error: null           │   error: "Timeout"   [DIFF]  │
│   timestamp: ...        │   timestamp: ...             │
└─────────────────────────┴──────────────────────────────┘
```

---

#### 9. Type Inference Display

**What:**
Show inferred schema for the dataset: field names, types, and nullability.

**Why:**
- **Understand data shape**: Glance at schema, see structure
- **Type issues**: "Wait, `age` is sometimes a string?"
- **Documentation**: Schema is quick reference for fields
- **Heterogeneous data**: See all possible fields across records

**How it Fits:**
During data loading, infer type for each field by examining all records. Display schema in statistics panel or separate tab.

**Components:**
- Type inference module (scan values, track types per field)
- Schema display widget (tree or table showing `field: type`)
- Nullability tracking (% of nulls per field)

**User Experience:**
```
┌─ Inferred Schema ──────────────────────┐
│ {                                      │
│   id: int,                             │
│   name: string,                        │
│   email: string | null (15% null),     │
│   age: int | null (5% null),           │
│   status: enum("active", "pending",    │
│                 "inactive"),           │
│   address: {                           │
│     city: string,                      │
│     zip: string | int (mixed types!)   │
│   },                                   │
│   tags: array<string>                  │
│ }                                      │
└────────────────────────────────────────┘
```

---

#### 10. Smart Column Width Allocation

**What:**
In table mode, dynamically size columns based on content, not fixed widths. Short values (like `id`) get narrow columns, long values (like `description`) get more space.

**Why:**
- **Space efficiency**: Don't waste columns on narrow data
- **Readability**: Long text isn't truncated unnecessarily
- **Professional polish**: Fixed-width tables feel primitive
- **Adaptive**: Works on both wide (200 cols) and narrow (80 cols) terminals

**How it Fits:**
Before rendering table, scan all values in each column to compute max width. Allocate proportionally, with min/max constraints.

**Components:**
- Column width calculator (max content length per column)
- Proportional allocation algorithm (respect terminal width)
- DataTable column configuration

**User Experience:**
```
Before (fixed widths):
┌────────────────────┬────────────────────┬────────────────────┐
│ id                 │ name               │ description        │
├────────────────────┼────────────────────┼────────────────────┤
│ 1                  │ Alice Johnson      │ Senior Engineer... │
│ 2                  │ Bob Smith          │ Product Manager... │

After (smart widths):
┌────┬─────────────────┬─────────────────────────────────────┐
│ id │ name            │ description                         │
├────┼─────────────────┼─────────────────────────────────────┤
│ 1  │ Alice Johnson   │ Senior Engineer with 10 years exp   │
│ 2  │ Bob Smith       │ Product Manager focused on growth   │
```

---

#### 11. Pattern Highlighting

**What:**
Automatically highlight interesting patterns in data:
- **Duplicates**: Same value appears 5+ times → purple background
- **Outliers**: Value > 2 std deviations from mean → yellow background
- **Nulls**: Null values → dim red text
- **Type mismatches**: String in mostly-int column → orange background

**Why:**
- **Visual scanning**: Spot issues without reading every value
- **Data quality**: Find problems (duplicates, type errors, outliers)
- **Exploration aid**: "Why is this record highlighted?" → investigate
- **Low cognitive load**: Colors guide attention

**How it Fits:**
During data loading, compute statistics (value frequencies, type distributions, numeric stats). Apply conditional styling based on patterns.

**Components:**
- Pattern detection module (duplicates, outliers, type mismatches)
- Conditional styling in Tree/DataTable (Textual's `Rich` styling)
- Configuration to enable/disable highlighting

**User Experience:**
```
┌─ Records (Pattern Highlighting ON) ────────────────┐
│ ▼ Record 0                                         │
│   id: 1                                            │
│   name: "Alice"                                    │
│   status: "active"  [PURPLE: 80% of records]      │
│   age: 30                                          │
│                                                    │
│ ▼ Record 1                                         │
│   id: 2                                            │
│   name: "Bob"                                      │
│   status: "active"  [PURPLE: duplicate]           │
│   age: "unknown"    [ORANGE: type mismatch]       │
└────────────────────────────────────────────────────┘
```

---

## Integration Philosophy

All polished features follow these principles:

### 1. Progressive Disclosure
Don't overwhelm users. Statistics panel is collapsible, command palette is hidden until Ctrl+P, advanced features are in menus not default UI.

### 2. JN Workflow Integration
Features bridge viewer → pipeline gap. Copy JSONPath feeds into `jn filter`, export creates files for further processing, stats inform filtering decisions.

### 3. Keyboard-First, Mouse-Friendly
Primary interaction is keyboard (fast, precise), but mouse works for casual users (clicking to expand, scrolling).

### 4. Async & Responsive
UI never blocks. Streaming loads in background, statistics update incrementally, large computations show progress.

### 5. Graceful Degradation
If terminal doesn't support color → use symbols. If clipboard unavailable → show path in dialog. If screen too small → hide panels.

---

## Architectural Considerations

### Widget Hierarchy

```
JSONViewerApp (Textual App)
├─ Header (built-in)
├─ MainContainer (Horizontal or Vertical based on screen size)
│  ├─ DataView (Tree or DataTable)
│  └─ StatisticsPanel (Collapsible, optional)
├─ StatusBar (custom widget)
└─ Modals (conditional)
   ├─ CommandPalette (Screen, appears on Ctrl+P)
   ├─ ExportDialog (Screen, appears on 'x')
   └─ CompareView (Screen, appears on 'c')
```

### Data Flow

```
stdin (NDJSON stream)
  ↓
StreamReader (async generator)
  ↓
DataModel (stores records, computes stats)
  ├→ StatisticsPanel (reactive updates)
  ├→ TreeView (incremental rendering)
  └→ TableView (batch rendering)
  ↓
User interactions (keyboard/mouse)
  ↓
Actions (expand, filter, export, copy)
  ↓
State updates (reactive)
  ↓
UI re-renders (Textual handles diffing)
```

### Key Modules

**Core:**
- `json_viewer.py` - Main plugin entry point, CLI interface
- `app.py` - JSONViewerApp (Textual App subclass)
- `data_model.py` - DataModel (stores records, computes stats)

**Views:**
- `tree_view.py` - TreeView (hierarchical display)
- `table_view.py` - TableView (tabular display)
- `detail_view.py` - DetailView (single-record inspection)
- `compare_view.py` - CompareView (side-by-side diff)

**Components:**
- `statistics_panel.py` - StatisticsPanel (dataset stats)
- `status_bar.py` - StatusBar (hints, keybindings)
- `command_palette.py` - CommandPalette (fuzzy command search)
- `export_dialog.py` - ExportDialog (export UI)

**Utilities:**
- `formatters.py` - ValueFormatter (dates, numbers, bytes)
- `path_tracker.py` - JSONPathTracker (build paths during traversal)
- `type_inference.py` - TypeInferrer (infer schema from records)
- `pattern_detector.py` - PatternDetector (duplicates, outliers)
- `aggregators.py` - Aggregators (sum, avg, min, max)

### Configuration Schema

```python
{
  # View settings
  "mode": "auto" | "tree" | "table" | "detail",
  "depth": int,  # Initial expansion depth

  # Field filtering
  "fields": set[str],  # Include only these
  "exclude": set[str],  # Exclude these
  "priority": list[str],  # Show these first

  # Display settings
  "max_string_length": int,  # Truncate strings
  "max_records": int,  # Limit dataset size
  "show_stats": bool,  # Show statistics panel
  "format_values": bool,  # Apply value formatting
  "highlight_patterns": bool,  # Pattern highlighting

  # Performance
  "streaming": bool,  # Incremental rendering
  "virtual_scroll": bool,  # Only render visible

  # Export defaults
  "export_format": "json" | "csv" | "ndjson",
}
```

---

## Why This Approach?

### Focus on Workflows, Not Features

Every polished feature answers a real question:
- **Statistics panel**: "What am I looking at?"
- **Copy JSONPath**: "How do I filter on this field?"
- **Export current view**: "How do I save these 10 interesting records?"
- **Value formatting**: "What does this timestamp mean?"
- **Compare mode**: "Why did this request fail but that one succeed?"

### Leverage Textual's Strengths

We're not building a TUI framework - we're using one. Textual provides:
- **Tree widget**: Handles expansion, navigation, rendering
- **DataTable widget**: Handles sorting, selection, scrolling
- **Screen/Modal**: Command palette, dialogs
- **Reactive model**: State changes automatically update UI
- **Async support**: Streaming data, non-blocking operations

### Align with JN Philosophy

JN is about **composable data pipelines**. The viewer:
- **Fits in pipelines**: `jn cat | jn filter | jn put "-~viewer"`
- **Exports back to pipelines**: Export → JSON file → `jn cat` again
- **Bridges exploration & transformation**: Copy path → use in filter
- **Streams data**: Respects Unix philosophy of incremental processing

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    JN Pipeline                              │
│  jn cat data.json | jn filter '.x > 10' | jn put "-~viewer" │
└─────────────────────────┬───────────────────────────────────┘
                          │ NDJSON stream (stdin)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              json_viewer.py (Plugin)                        │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  writes(config) function                              │ │
│  │  - Parse config (mode, depth, fields, etc.)           │ │
│  │  - Read NDJSON from stdin                             │ │
│  │  - Launch Textual app                                 │ │
│  └──────────────────┬────────────────────────────────────┘ │
│                     │                                       │
│  ┌──────────────────▼────────────────────────────────────┐ │
│  │  JSONViewerApp (Textual App)                          │ │
│  │                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │ │
│  │  │  TreeView    │  │  TableView   │  │ DetailView  │ │ │
│  │  │  (Tree)      │  │  (DataTable) │  │  (Tree)     │ │ │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │ │
│  │                                                        │ │
│  │  ┌────────────────────────────────────────────────┐   │ │
│  │  │  StatusBar (navigation hints)                  │   │ │
│  │  └────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Class Structure

```python
# json_viewer.py

class JSONViewerApp(App):
    """Main Textual application."""

    CSS = """..."""  # Styling

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("t", "toggle_mode", "Toggle Mode"),
        ("/", "search", "Search"),
        ("e", "expand_all", "Expand All"),
        ("c", "collapse_all", "Collapse All"),
    ]

    def __init__(self, records: List[dict], config: dict):
        self.records = records
        self.config = config
        self.view_mode = config.get('mode', 'auto')
        self.current_view = None

    def compose(self):
        """Build UI layout."""
        yield Header()
        yield self._build_view()
        yield StatusBar(hints=self._get_key_hints())

    def _build_view(self):
        """Build view based on mode."""
        if self.view_mode == 'tree':
            return TreeView(self.records, self.config)
        elif self.view_mode == 'table':
            return TableView(self.records, self.config)
        elif self.view_mode == 'detail':
            return DetailView(self.records[0], self.config)


class TreeView(Static):
    """Tree-based hierarchical JSON view."""

    def __init__(self, records: List[dict], config: dict):
        self.records = records
        self.max_depth = config.get('depth', 2)
        self.fields = config.get('fields')  # Optional filter

    def compose(self):
        tree = Tree("JSON Data")
        tree.root.expand()

        for i, record in enumerate(self.records):
            self._add_json_node(tree.root, f"Record {i}", record, depth=0)

        yield tree

    def _add_json_node(self, parent, label, data, depth):
        """Recursively add JSON data to tree."""
        if isinstance(data, dict):
            node = parent.add(f"{label} (object, {len(data)} keys)")
            node.expand() if depth < self.max_depth else None

            # Apply field filtering
            keys = self._filter_fields(data.keys())

            for key in keys:
                self._add_json_node(node, key, data[key], depth + 1)

        elif isinstance(data, list):
            node = parent.add(f"{label} (array, {len(data)} items)")
            node.expand() if depth < self.max_depth else None

            for i, item in enumerate(data):
                self._add_json_node(node, f"[{i}]", item, depth + 1)

        else:
            # Leaf node (primitive value)
            styled_value = self._style_value(data)
            parent.add_leaf(f"{label}: {styled_value}")

    def _style_value(self, value):
        """Apply syntax highlighting to values."""
        if value is None:
            return Text("null", style="dim red")
        elif isinstance(value, bool):
            return Text(str(value).lower(), style="bold yellow")
        elif isinstance(value, int):
            return Text(str(value), style="cyan")
        elif isinstance(value, float):
            return Text(str(value), style="cyan")
        elif isinstance(value, str):
            # Truncate long strings
            if len(value) > 50:
                value = value[:47] + "..."
            return Text(f'"{value}"', style="green")
        else:
            return Text(str(value), style="white")

    def _filter_fields(self, keys):
        """Apply field filtering."""
        keys = list(keys)

        # Explicit include filter
        if self.fields:
            keys = [k for k in keys if k in self.fields]

        # Explicit exclude filter
        exclude = self.config.get('exclude', [])
        if exclude:
            keys = [k for k in keys if k not in exclude]

        # Priority sorting
        priority = self.config.get('priority', [])
        if priority:
            keys.sort(key=lambda k: priority.index(k) if k in priority else 999)

        # Screen size limiting (if needed)
        # (handled by parent component)

        return keys


class TableView(Static):
    """Table-based flat JSON view."""

    def __init__(self, records: List[dict], config: dict):
        self.records = records
        self.config = config

    def compose(self):
        table = DataTable()

        # Get all unique keys (union)
        all_keys = self._get_all_keys()

        # Add columns
        for key in all_keys:
            table.add_column(key, key=key)

        # Add rows
        for record in self.records:
            row = [record.get(key, "") for key in all_keys]
            table.add_row(*row)

        yield table

    def _get_all_keys(self):
        """Get union of all keys across records."""
        keys = []
        seen = set()
        for record in self.records:
            for key in record:
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
        return keys


class DetailView(TreeView):
    """Single-record detailed view (extends TreeView)."""

    def __init__(self, record: dict, config: dict):
        super().__init__([record], config)
        self.max_depth = config.get('depth', 3)  # Deeper default


class StatusBar(Static):
    """Status bar with navigation hints."""

    def __init__(self, hints: str):
        self.hints = hints

    def render(self):
        return Text(self.hints, style="black on white")


def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, display interactively."""
    config = config or {}

    # Read all records from stdin
    records = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                # Show error record
                records.append({
                    "_error": True,
                    "type": "json_decode_error",
                    "message": str(e),
                    "line": line[:100]
                })

    if not records:
        print("No records to display", file=sys.stderr)
        return

    # Auto-detect mode if not specified
    if config.get('mode') == 'auto' or 'mode' not in config:
        config['mode'] = _detect_view_mode(records)

    # Launch Textual app
    app = JSONViewerApp(records=records, config=config)
    app.run()
```

---

## Plugin Specification

### PEP 723 Metadata

```python
#!/usr/bin/env -S uv run --script
"""Interactive JSON viewer using Textual TUI framework."""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "textual>=0.90.0",
#   "rich>=13.9.0",
# ]
# [tool.jn]
# matches = [
#   ".*\\.viewer$",
#   "^-$",           # Stdout
#   "^stdout$",
# ]
# role = "display"
# ///
```

**Why these patterns:**
- `.*\\.viewer$`: Explicit viewer files (`output.viewer`)
- `^-$`, `^stdout$`: Allow `jn put "-~viewer"` syntax

### CLI Interface

```python
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Interactive JSON viewer with tree/table/detail modes"
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "tree", "table", "detail"],
        default="auto",
        help="Display mode (default: auto-detect)"
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        help="Initial expansion depth (default: 2)"
    )
    parser.add_argument(
        "--fields",
        help="Comma-separated list of fields to show (include filter)"
    )
    parser.add_argument(
        "--exclude",
        help="Comma-separated list of fields to hide (exclude filter)"
    )
    parser.add_argument(
        "--priority",
        help="Comma-separated list of priority fields (shown first)"
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=10_000,
        help="Maximum records to display (default: 10,000)"
    )
    parser.add_argument(
        "--max-string-length",
        type=int,
        default=50,
        help="Max string length before truncation (default: 50)"
    )

    args = parser.parse_args()

    # Build config
    config = {
        "mode": args.mode,
        "depth": args.depth,
        "max_records": args.max_records,
        "max_string_length": args.max_string_length,
    }

    if args.fields:
        config["fields"] = set(args.fields.split(","))

    if args.exclude:
        config["exclude"] = set(args.exclude.split(","))

    if args.priority:
        config["priority"] = args.priority.split(",")

    # Run viewer
    writes(config)
```

---

## UI Design

### Tree Mode Layout

```
┌─────────────────────────────────────────────────────────────┐
│ JSON Viewer - Tree Mode                    [Records: 1,234] │
├─────────────────────────────────────────────────────────────┤
│ ▼ JSON Data                                                 │
│   ▼ Record 0 (object, 5 keys)                               │
│     ├─ id: 1                                                │
│     ├─ name: "Alice Johnson"                                │
│     ├─ email: "alice@example.com"                           │
│     ▼ address (object, 4 keys)                              │
│     │ ├─ street: "123 Main St"                              │
│     │ ├─ city: "New York"                                   │
│     │ ├─ state: "NY"                                        │
│     │ └─ zip: "10001"                                       │
│     ▶ tags (array, 3 items)                                 │
│   ▼ Record 1 (object, 5 keys)                               │
│     ├─ id: 2                                                │
│     └─ ...                                                  │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ ↑/↓: Navigate  Space: Expand  Enter: Select  /: Search  q: Quit │
└─────────────────────────────────────────────────────────────┘
```

### Table Mode Layout

```
┌─────────────────────────────────────────────────────────────┐
│ JSON Viewer - Table Mode                   [Records: 1,234] │
├─────────────────────────────────────────────────────────────┤
│ ┃ id ┃ name           ┃ email               ┃ city      ┃  │
│ ┣━━━━╋━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━┫  │
│ ┃  1 ┃ Alice Johnson  ┃ alice@example.com   ┃ New York  ┃  │
│ ┃  2 ┃ Bob Smith      ┃ bob@example.com     ┃ Boston    ┃  │
│ ┃  3 ┃ Carol Davis    ┃ carol@example.com   ┃ Chicago   ┃  │
│ ┃  4 ┃ Dave Wilson    ┃ dave@example.com    ┃ Seattle   ┃  │
│ ┃... ┃ ...            ┃ ...                 ┃ ...       ┃  │
│                                                             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ ↑/↓: Navigate  Enter: Details  t: Tree Mode  /: Filter  q: Quit │
└─────────────────────────────────────────────────────────────┘
```

### Color Scheme

Following JSON syntax highlighting conventions:

| Element | Color | Style | Example |
|---------|-------|-------|---------|
| Object keys | Blue | Bold | `"name"` |
| Strings | Green | Normal | `"Alice Johnson"` |
| Numbers | Cyan | Normal | `42`, `3.14` |
| Booleans | Yellow | Bold | `true`, `false` |
| Null | Red | Dim | `null` |
| Array indices | Magenta | Dim | `[0]`, `[1]` |
| Collapsed indicator | White | Dim | `▶` |
| Expanded indicator | White | Bold | `▼` |

### Keyboard Shortcuts

| Key | Action | Description |
|-----|--------|-------------|
| **Navigation** |||
| `↑` / `k` | Move Up | Move cursor up |
| `↓` / `j` | Move Down | Move cursor down |
| `←` / `h` | Collapse | Collapse current node |
| `→` / `l` | Expand | Expand current node |
| `PageUp` | Page Up | Scroll up one page |
| `PageDown` | Page Down | Scroll down one page |
| `Home` | Top | Jump to top |
| `End` | Bottom | Jump to bottom |
| **Actions** |||
| `Space` | Toggle | Expand/collapse current node |
| `Enter` | Select | Show details for current item |
| `e` | Expand All | Expand all nodes |
| `c` | Collapse All | Collapse all nodes |
| `1`-`9` | Collapse to Depth | Collapse to depth N |
| **Views** |||
| `t` | Tree Mode | Switch to tree view |
| `T` | Table Mode | Switch to table view |
| `d` | Detail Mode | Show detailed view of current record |
| **Search** |||
| `/` | Search | Search field names or values |
| `n` | Next Match | Jump to next search result |
| `N` | Previous Match | Jump to previous search result |
| **Other** |||
| `?` | Help | Show keyboard shortcuts |
| `q` | Quit | Exit viewer |
| `Ctrl+C` | Force Quit | Emergency exit |

---

## Implementation Details

### Phase 1: MVP (Minimal Viable Product)

**Scope:**
- Tree mode only (no table/detail modes yet)
- Basic navigation (arrow keys, space to expand/collapse)
- Syntax highlighting
- Config params: `mode`, `depth`
- Fixed expansion depth (no dynamic toggling yet)

**Files:**
- `jn_home/plugins/formats/json_viewer.py` (~300 lines)

**Timeline:** 4-6 hours

**Testing:**
```bash
# Basic test
echo '{"name": "Alice", "age": 30}' | jn cat - | jn put "-~viewer"

# Nested data
jn cat examples/nested.json | jn put "-~viewer?depth=3"

# Large dataset
jn cat examples/large.json | jn put "-~viewer?max_records=1000"
```

### Phase 2: Enhanced Features

**Scope:**
- Add table mode
- Add detail mode
- Field filtering (`fields`, `exclude`, `priority`)
- Dynamic toggling (switch modes without restarting)
- Search functionality

**Timeline:** 6-8 hours

### Phase 3: Advanced Features

**Scope:**
- Lazy loading (incremental rendering)
- Virtual scrolling (handle 100K+ records)
- Advanced search (regex, JSONPath)
- Export current view (to file)
- Copy value to clipboard
- Session state persistence (remember collapsed nodes)

**Timeline:** 8-12 hours

### File Structure

```
jn_home/plugins/formats/
├── json_viewer.py           # Main plugin
└── _json_viewer/            # Helper modules (optional)
    ├── tree_view.py         # TreeView component
    ├── table_view.py        # TableView component
    ├── detail_view.py       # DetailView component
    └── utils.py             # Shared utilities

tests/plugins/formats/
└── test_json_viewer.py      # Unit tests
```

**Note:** Initially, keep everything in `json_viewer.py` for simplicity. Extract to modules if it grows beyond ~500 lines.

### Dependencies

```toml
# PEP 723 block
dependencies = [
  "textual>=0.90.0",    # TUI framework
  "rich>=13.9.0",       # Syntax highlighting (textual depends on this)
]
```

**Rationale:**
- `textual`: Core TUI framework, provides Tree, DataTable, App
- `rich`: Textual's dependency, used for Text styling

**No additional deps needed** (json is stdlib)

### Error Handling

**Malformed JSON:**
```python
try:
    record = json.loads(line)
    records.append(record)
except json.JSONDecodeError as e:
    # Show error record in viewer
    records.append({
        "_error": True,
        "type": "json_decode_error",
        "message": str(e),
        "line": line[:100],  # Show first 100 chars
        "_line_number": line_number
    })
```

**Empty Input:**
```python
if not records:
    print("No records to display", file=sys.stderr)
    sys.exit(0)  # Not an error, just empty
```

**Terminal Too Small:**
```python
def compose(self):
    width, height = self.console.size
    if width < 40 or height < 10:
        yield Static("Terminal too small. Please resize (min: 40x10)")
        return

    yield self._build_view()
```

### Testing Strategy

**Unit Tests:**
```python
def test_tree_view_rendering():
    """Test tree view renders JSON correctly."""
    records = [{"name": "Alice", "age": 30}]
    view = TreeView(records, config={"depth": 2})
    # Assert tree structure

def test_field_filtering():
    """Test field filtering works."""
    records = [{"a": 1, "b": 2, "c": 3}]
    config = {"fields": {"a", "b"}}
    view = TreeView(records, config)
    # Assert only a, b visible

def test_depth_limiting():
    """Test depth limiting works."""
    records = [{"a": {"b": {"c": {"d": 1}}}}]
    config = {"depth": 2}
    view = TreeView(records, config)
    # Assert only 2 levels expanded
```

**Integration Tests:**
```python
def test_plugin_invocation():
    """Test plugin can be invoked via jn put."""
    result = subprocess.run(
        ["jn", "cat", "test.json"],
        stdout=subprocess.PIPE
    )

    result = subprocess.run(
        ["jn", "put", "-~viewer"],
        stdin=result.stdout,
        stdout=subprocess.PIPE
    )

    assert result.returncode == 0
```

**Manual Tests:**
```bash
# Test large file
jn cat examples/large.json | jn put "-~viewer"

# Test nested structure
jn cat examples/nested.json | jn put "-~viewer?depth=5"

# Test filtering
jn cat examples/users.json | jn put "-~viewer?fields=name,email"
```

---

## Usage Examples

### Basic Usage

```bash
# View JSON file interactively
jn cat data.json | jn put "-~viewer"

# Force tree mode
jn cat data.json | jn put "-~viewer?mode=tree"

# Force table mode (for flat records)
jn cat users.json | jn put "-~viewer?mode=table"

# View with custom depth
jn cat nested.json | jn put "-~viewer?depth=3"
```

### Field Filtering

```bash
# Show only specific fields
jn cat users.json | jn put "-~viewer?fields=name,email,city"

# Hide metadata fields
jn cat data.json | jn put "-~viewer?exclude=_id,_metadata,_internal"

# Prioritize certain fields (show first)
jn cat data.json | jn put "-~viewer?priority=name,status,date"

# Combine filters
jn cat data.json | jn put "-~viewer?fields=a,b,c&priority=a&depth=2"
```

### Advanced Usage

```bash
# Limit records (for large datasets)
jn cat huge.json | jn head -n 1000 | jn put "-~viewer"
jn cat huge.json | jn put "-~viewer?max_records=5000"

# Truncate long strings
jn cat logs.json | jn put "-~viewer?max_string_length=30"

# View filtered data
jn cat users.json | jn filter '.age > 25' | jn put "-~viewer"

# View API response
jn cat http://api.example.com/users | jn put "-~viewer?mode=table"
```

### Pipeline Integration

```bash
# View Gmail messages interactively
jn cat @gmail/inbox | jn put "-~viewer?fields=from,subject,date"

# View GitHub API response
jn cat https://api.github.com/repos/owner/repo/issues | \
  jn put "-~viewer?fields=number,title,state,user.login"

# View database query results (future)
jn cat @db/users | jn filter '.status == "active"' | jn put "-~viewer"
```

### Real-World Examples

**Example 1: Explore API Response**
```bash
$ jn cat https://jsonplaceholder.typicode.com/users | jn put "-~viewer?mode=tree&depth=2"

# Opens interactive viewer:
# - See all users as expandable nodes
# - Expand to see nested address/company objects
# - Navigate with arrow keys
# - Press 't' to switch to table mode
# - Press '/' to search
```

**Example 2: Debug Nested Configuration**
```bash
$ jn cat config.json | jn put "-~viewer?depth=5"

# Opens deep view of config:
# - All nesting levels visible
# - Easy to find specific settings
# - Collapse uninteresting sections
```

**Example 3: Review Large Dataset**
```bash
$ jn cat transactions.json | jn put "-~viewer?mode=table&fields=id,date,amount,status"

# Opens table view:
# - Only relevant columns shown
# - Easy to scan rows
# - Press Enter on row to see full details
```

---

## Future Enhancements

### Phase 4: Power User Features

1. **JSONPath Search**
   - Search: `/$.users[?(@.age > 25)]`
   - Navigate to matching nodes

2. **Diff Mode**
   ```bash
   jn cat old.json | jn put diff.json
   jn cat diff.json | jn put "-~viewer?mode=diff&compare=new.json"
   ```
   - Highlight changed values
   - Show added/removed keys

3. **Export Current View**
   - `x` key: Export visible data to file
   - Formats: JSON, CSV, Markdown table

4. **Copy to Clipboard**
   - `y` key: Copy current value
   - `Y` key: Copy entire record

5. **Session Persistence**
   - Save expansion state to `~/.jn/viewer-state.json`
   - Restore on reopen

6. **Schema Inference**
   - Show type information (string|int|null)
   - Show value distributions (e.g., "90% not null")
   - Detect patterns (e.g., "all match email regex")

7. **Live Updates**
   - `--follow` flag: Watch file for changes
   - Auto-refresh on update
   - Similar to `tail -f`

8. **Aggregations**
   - In table mode: Show sum/avg/count per column
   - Group by field: `jn put "-~viewer?group_by=status"`

### Phase 5: Integration with JN Ecosystem

1. **Profile-Aware Filtering**
   ```bash
   jn cat @api/users | jn put "-~viewer"
   # Auto-apply profile's default field filters
   ```

2. **Saved Views**
   ```bash
   jn profile create viewer/users fields=name,email,status mode=table
   jn cat data.json | jn put "@viewer/users"
   ```

3. **MCP Integration**
   - View MCP resources interactively
   - Explore MCP tools/prompts in tree mode

---

## References

### External Resources

**Textual Documentation:**
- [Textual Homepage](https://textual.textualize.io/)
- [Tree Widget](https://textual.textualize.io/widgets/tree/)
- [DataTable Widget](https://textual.textualize.io/widgets/data_table/)
- [Textual GitHub](https://github.com/Textualize/textual)

**Similar Tools:**
- [pyfx](https://github.com/cielong/pyfx) - Python JSON Viewer (Urwid-based)
- [fx](https://github.com/antonmedv/fx) - Terminal JSON viewer (Node.js)
- [jq](https://jqlang.github.io/jq/) - JSON query language (inspiration)

**JN Specs:**
- `spec/done/plugin-specification.md` - Plugin requirements
- `spec/done/arch-backpressure.md` - Why Popen > async
- `spec/done/format-design.md` - Format plugin patterns

### Internal Files

**Existing Plugins to Reference:**
- `jn_home/plugins/formats/table_.py` - Current table plugin
- `jn_home/plugins/formats/json_.py` - JSON format plugin
- `jn_home/plugins/formats/csv_.py` - CSV format plugin (good example)

**CLI Commands:**
- `src/jn/cli/commands/put.py` - How plugins are invoked
- `src/jn/cli/commands/cat.py` - Pipeline setup

**Discovery:**
- `src/jn/plugins/discovery.py` - Plugin discovery logic
- `src/jn/addressing/resolver.py` - Address resolution

---

## Summary

**What We're Building:**
A Textual-based interactive JSON viewer plugin for JN that provides:
- 🌲 **Tree mode** - Hierarchical, collapsible view
- 📊 **Table mode** - Flat, tabular view for homogeneous data
- 🔍 **Detail mode** - Deep inspection of single records
- 🎨 **Syntax highlighting** - Beautiful, readable output
- ⌨️ **Keyboard navigation** - Vim-like shortcuts
- 📏 **Smart rendering** - Adapts to screen size
- 🔧 **Configurable** - Field filtering, depth control, etc.

**How It Fits into JN:**
```bash
jn cat data.json | jn filter '.x > 10' | jn put "-~viewer?mode=tree&depth=3"
                                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                              Our plugin!
```

**Key Design Principles:**
1. **Interactive** - Users can explore data, not just view it
2. **Smart defaults** - Auto-detect best mode, sensible depths
3. **Configurable** - Users can override everything
4. **Performant** - Handle large datasets without lag
5. **Beautiful** - Syntax highlighting, clean layout
6. **JN-native** - Follows plugin spec, works in pipelines

**Next Steps:**
1. ✅ Design approved → Create this document
2. ⏭️ Build MVP (Phase 1)
3. ⏭️ Test with real data
4. ⏭️ Iterate based on feedback
5. ⏭️ Add advanced features (Phase 2-5)

---

**End of Design Document**
