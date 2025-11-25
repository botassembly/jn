# JN Viewer v2: The Data Lens

**Date:** 2025-11-25
**Status:** Design Specification
**Author:** Claude

---

## Executive Summary

The JN Viewer transforms from a single-record tree browser into a **professional data exploration tool** - a "Data Lens" that sits naturally in Unix pipelines. The core insight: **tables first, trees on demand**. Users scan data in table mode, drill into records when needed, and copy paths back to the pipeline for transformation.

**The Philosophy:**
This is not an application. It's a lens. Data flows in, understanding flows out.

---

## Table of Contents

1. [Strategy](#1-strategy)
2. [Core Principles](#2-core-principles)
3. [User Experience Flow](#3-user-experience-flow)
4. [View Modes](#4-view-modes)
5. [Navigation System](#5-navigation-system)
6. [Search & Filter](#6-search--filter)
7. [Clipboard & Export](#7-clipboard--export)
8. [Smart Cells](#8-smart-cells)
9. [Statistics & Analysis](#9-statistics--analysis)
10. [Architecture](#10-architecture)
11. [Implementation Roadmap](#11-implementation-roadmap)
12. [Keyboard Reference](#12-keyboard-reference)

---

## 1. Strategy

### The Problem

Current state: A tree viewer that shows one record at a time. Users must press `n` repeatedly to scan data. With 70,000 gene records, this is unusable for exploration.

### The Solution

**Table-first, tree-on-demand.**

```
┌─────────────────────────────────────────────────────────────────────┐
│  JN Viewer                                    Record 1-50 of 70,234 │
├────┬──────────┬────────────┬───────────────────────────────────────┤
│ #  │ Symbol   │ chromosome │ description                           │
├────┼──────────┼────────────┼───────────────────────────────────────┤
│  1 │ A1BG     │ 19         │ alpha-1-B glycoprotein                │
│  2 │ A1CF     │ 10         │ APOBEC1 complementation factor        │
│  3 │ A2M      │ 12         │ alpha-2-macroglobulin                 │
│  4 │ A2ML1    │ 12         │ alpha-2-macroglobulin like 1          │
│ ▶5 │ BRAF     │ 7          │ B-Raf proto-oncogene, serine/threo... │
│  6 │ BRCA1    │ 17         │ BRCA1 DNA repair associated           │
├────┴──────────┴────────────┴───────────────────────────────────────┤
│ / Filter  ↵ Drill Down  t Tree  s Stats  y Copy  ? Help  q Quit   │
└─────────────────────────────────────────────────────────────────────┘
```

Press `Enter` on row 5 → Modal opens with full tree view of BRAF record.

### Success Criteria

1. **Instant feedback**: First 50 rows visible in <500ms
2. **Zero hang**: Search/filter completes in <100ms for 100K records
3. **Pipeline integration**: Copy JSONPath, export filtered data back to `jn filter`
4. **Muscle memory**: Vim bindings work as expected

---

## 2. Core Principles

### P1: Table First, Tree on Demand

The table is the **overview**. The tree is the **detail view**. Users scan horizontally across records, then dive vertically into structure.

| Mode | Purpose | When to Use |
|------|---------|-------------|
| Table | Scan many records | Default view, flat/tabular data |
| Tree | Inspect one record | Nested objects, deep structures |
| Compare | Diff two records | Debugging, finding differences |

### P2: In-Memory Operations

**Never spawn subprocesses for per-record operations.** All search, filter, and navigation happens in Python on the loaded dataset.

```python
# BAD: O(N) subprocess spawns
for record in records:
    subprocess.run(['jq', expr, record])  # 70,000 processes!

# GOOD: O(N) Python iteration
matches = [r for r in records if term.lower() in json.dumps(r).lower()]
```

### P3: Progressive Disclosure

Simple by default. Power features discoverable via `?` help or `Ctrl+P` command palette.

- **Level 1**: Navigate with arrows, quit with `q`
- **Level 2**: Vim keys `j/k/h/l`, search with `/`
- **Level 3**: Copy JSONPath with `p`, export with `x`
- **Level 4**: Compare mode with `c`, regex search

### P4: Pipeline Integration

The viewer is exploration. Transformation happens back in the pipeline.

```bash
# Explore
jn cat genes.csv | jn view

# In viewer: find interesting pattern, copy JSONPath: .chromosome

# Transform
jn cat genes.csv | jn filter '.chromosome == "7"' | jn put braf_genes.json
```

---

## 3. User Experience Flow

### Primary Flow: Explore → Find → Extract

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   LOAD      │───▶│   SCAN      │───▶│   FILTER    │───▶│   EXPORT    │
│ jn view ... │    │ Table mode  │    │ / search    │    │ Copy/Save   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  DRILL DOWN │
                   │  Tree modal │
                   └─────────────┘
```

### Secondary Flow: Compare → Understand

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   MARK      │───▶│   SELECT    │───▶│   COMPARE   │
│ Bookmark    │    │ Second row  │    │ Side-by-side│
└─────────────┘    └─────────────┘    └─────────────┘
```

---

## 4. View Modes

### 4.1 Table Mode (Default)

The primary view for scanning data.

**Layout:**
```
┌──────────────────────────────────────────────────────────────────┐
│ Header: Title + Position + Mode Indicator                        │
├──────────────────────────────────────────────────────────────────┤
│ Column Headers: Sortable, Resizable, Pinnable                    │
├────┬──────────┬────────────┬─────────────────────────────────────┤
│  1 │ value    │ value      │ value (truncated with ...)          │
│ ▶2 │ value    │ value      │ value                               │ ← Selected
│  3 │ value    │ value      │ value                               │
├────┴──────────┴────────────┴─────────────────────────────────────┤
│ Footer: Stats (when column selected) or Key Hints               │
└──────────────────────────────────────────────────────────────────┘
```

**Behavior:**
- Auto-detect column widths from content
- Truncate long values with `...`
- Highlight selected row
- Show row numbers on left (optional, toggle with `#`)

**Column Features:**
- Click header to sort (or `s` key)
- Drag separator to resize
- Right-click to hide/pin
- Double-click separator to auto-fit

### 4.2 Tree Mode

Single-record deep inspection.

**Layout:**
```
┌──────────────────────────────────────────────────────────────────┐
│ JSON Viewer                              Record 5 of 70,234       │
├──────────────────────────────────────────────────────────────────┤
│ ▼ Root                                                            │
│ └── ▼ Record                                                      │
│     ├── Symbol: "BRAF"                          [green: string]   │
│     ├── GeneID: "673"                           [cyan: number]    │
│     ├── chromosome: "7"                                           │
│     ├── ▼ dbXrefs (object, 4 keys)                               │
│     │   ├── MIM: "164757"                                        │
│     │   ├── HGNC: "HGNC:1097"                                    │
│     │   └── Ensembl: "ENSG00000157764"                           │
│     └── description: "B-Raf proto-oncogene, serine/threonine..." │
├──────────────────────────────────────────────────────────────────┤
│ n Next  p Prev  t Table  Space Toggle  y Copy  ? Help            │
└──────────────────────────────────────────────────────────────────┘
```

**Syntax Highlighting:**
- Strings: Green
- Numbers: Cyan
- Booleans: Yellow
- Null: Dim/Italic
- Keys: White/Bold

### 4.3 Detail Modal

When user presses `Enter` on a row in table mode.

```
┌─ Record Detail ───────────────────────────────────────────────────┐
│                                                                    │
│ ▼ Root                                                             │
│ └── ▼ Record                                                       │
│     ├── Symbol: "BRAF"                                             │
│     ├── ...                                                        │
│                                                                    │
│ ─────────────────────────────────────────────────────────────────  │
│ Esc Close  n/p Navigate  y Copy Record  p Copy Path                │
└────────────────────────────────────────────────────────────────────┘
```

### 4.4 Compare Mode

Side-by-side diff of two records.

```
┌─ Compare: Record 5 vs Record 42 ──────────────────────────────────┐
│                                                                    │
│ Record 5                     │ Record 42                           │
│ ────────────────────────────┼────────────────────────────────────  │
│ Symbol: "BRAF"               │ Symbol: "EGFR"              [DIFF]  │
│ chromosome: "7"              │ chromosome: "7"                     │
│ type_of_gene: "protein-cod…" │ type_of_gene: "protein-coding"      │
│ status: "active"             │ status: "pending"           [DIFF]  │
│                                                                    │
│ ─────────────────────────────────────────────────────────────────  │
│ Differences: 2 fields  │  Esc Close  │  n/p Swap records           │
└────────────────────────────────────────────────────────────────────┘
```

**Diff Highlighting:**
- Green background: Only in left
- Red background: Only in right
- Yellow background: Different values
- No highlight: Same values

---

## 5. Navigation System

### 5.1 Movement Keys

| Key | Table Mode | Tree Mode |
|-----|------------|-----------|
| `j` / `↓` | Next row | Next node |
| `k` / `↑` | Prev row | Prev node |
| `h` / `←` | Scroll left | Collapse node |
| `l` / `→` | Scroll right | Expand node |
| `g` / `Home` | First row/record | First node |
| `G` / `End` | Last row/record | Last node |
| `Ctrl+D` | Page down (half screen) | Page down |
| `Ctrl+U` | Page up (half screen) | Page up |

### 5.2 Jump Navigation

| Key | Action |
|-----|--------|
| `:` or `#` | Open "Go to record" prompt |
| `'` | Jump to bookmarked record |
| `[` | History: Go back |
| `]` | History: Go forward |

### 5.3 Mode Switching

| Key | Action |
|-----|--------|
| `t` | Toggle Table ↔ Tree mode |
| `Enter` | Table: Open detail modal / Tree: N/A |
| `Esc` | Close modal, clear search, exit mode |
| `c` | Enter compare mode (mark first, then second) |
| `s` | Toggle statistics panel |

### 5.4 Bookmarks

| Key | Action |
|-----|--------|
| `m` | Mark/bookmark current record |
| `u` | Unmark current record |
| `'` | Jump to next bookmark (cycles) |

---

## 6. Search & Filter

### 6.1 Quick Search (In-Memory)

Press `/` to open search bar. Filters visible rows in real-time.

```
┌──────────────────────────────────────────────────────────────────┐
│ / BRAF█                                              [Esc Cancel]│
├──────────────────────────────────────────────────────────────────┤
│  5 │ BRAF     │ 7  │ B-Raf proto-oncogene...        │ [MATCH]    │
│ 42 │ BRAF1    │ 7  │ BRAF pseudogene 1              │ [MATCH]    │
├──────────────────────────────────────────────────────────────────┤
│ 2 matches found (↵ jump to first, n/N navigate)                  │
└──────────────────────────────────────────────────────────────────┘
```

**Search Modes:**
- Default: Case-insensitive substring match across all fields
- `:field=value`: Match specific field
- `/regex/`: Regex mode (toggle with `Ctrl+R`)

### 6.2 Field Filter

Press `f` to open field filter dialog.

```
┌─ Filter by Field ─────────────────────────────────────────────────┐
│                                                                    │
│ Field: chromosome = 7█                                             │
│                                                                    │
│ Operators: = (equals), != (not), > < >= <= (compare)              │
│ Examples: chromosome = 7, age > 30, Symbol = BRAF                  │
│                                                                    │
│ ─────────────────────────────────────────────────────────────────  │
│ Enter Apply  │  Esc Cancel                                         │
└────────────────────────────────────────────────────────────────────┘
```

### 6.3 Context Actions

Right-click on a cell (or `F` while selected):
- **Filter to this value**: Add filter `.field == "value"`
- **Exclude this value**: Add filter `.field != "value"`
- **Copy value**: Copy cell content
- **Copy as filter**: Copy `.field == "value"` expression

### 6.4 Filter Indicators

When filters are active:
```
┌──────────────────────────────────────────────────────────────────┐
│ JN Viewer │ 234 of 70,234 (filtered: chromosome == "7") │ [x]    │
└──────────────────────────────────────────────────────────────────┘
```

Press `x` or `Esc` to clear filters.

---

## 7. Clipboard & Export

### 7.1 Copy Operations

| Key | Action |
|-----|--------|
| `y` | Copy current row as JSON |
| `Y` | Copy current row as minified JSON |
| `yy` | Copy selected rows (multi-select) |
| `yc` | Copy current cell value only |
| `yp` | Copy JSONPath to current node (tree mode) |
| `yf` | Copy as `jn filter` expression |

### 7.2 Copy JSONPath

When viewing a nested object in tree mode, pressing `yp` copies the path:

```
Cursor on: .users[0].address.city
Copies: .users[0].address.city
Toast: "Copied: .users[0].address.city"
```

**Usage in pipeline:**
```bash
jn cat data.json | jn filter '.users[0].address.city == "NYC"'
```

### 7.3 Export Dialog

Press `x` to open export dialog:

```
┌─ Export ──────────────────────────────────────────────────────────┐
│                                                                    │
│ Export: ○ Current record  ● Filtered records (234)  ○ All        │
│                                                                    │
│ Format: ● JSON  ○ NDJSON  ○ CSV                                   │
│                                                                    │
│ Filename: filtered_genes.json█                                     │
│                                                                    │
│ ─────────────────────────────────────────────────────────────────  │
│ Enter Export  │  Esc Cancel                                        │
└────────────────────────────────────────────────────────────────────┘
```

### 7.4 Pipe to Command

Press `|` to pipe selected data to a shell command:

```
┌─ Pipe to Command ─────────────────────────────────────────────────┐
│                                                                    │
│ Pipe 234 records to: jq '.Symbol' | sort | uniq -c█               │
│                                                                    │
│ ─────────────────────────────────────────────────────────────────  │
│ Enter Execute  │  Esc Cancel                                       │
└────────────────────────────────────────────────────────────────────┘
```

---

## 8. Smart Cells

### 8.1 Content Detection

When drilling into a cell, detect content type and render appropriately:

| Content | Detection | Rendering |
|---------|-----------|-----------|
| JSON string | `json.loads()` succeeds | Nested tree view |
| Markdown | Contains `#`, `*`, `-` patterns | Rich markdown |
| Code | `def `, `import `, `function`, `{` | Syntax highlighted |
| URL | Starts with `http://` or `https://` | Clickable link |
| Hex color | Matches `#[0-9A-Fa-f]{6}` | Color swatch |
| Long text | Length > 100 chars | Word-wrapped modal |

### 8.2 Smart Cell Modal

Press `Enter` on a cell with long/special content:

```
┌─ description ─────────────────────────────────────────────────────┐
│                                                                    │
│ B-Raf proto-oncogene, serine/threonine kinase                     │
│                                                                    │
│ This gene encodes a protein belonging to the RAF family of        │
│ serine/threonine protein kinases. This protein plays a role       │
│ in regulating the MAP kinase/ERK signaling pathway, which         │
│ affects cell division, differentiation, and secretion.            │
│                                                                    │
│ Mutations in this gene, most commonly the V600E mutation,         │
│ are the most frequently identified cancer-causing mutations       │
│ in melanoma, and have been identified in various other            │
│ cancers as well.                                                   │
│                                                                    │
│ ─────────────────────────────────────────────────────────────────  │
│ y Copy  │  Esc Close                                               │
└────────────────────────────────────────────────────────────────────┘
```

### 8.3 Recursive JSON Parsing

If a cell contains a stringified JSON object:

```
Cell value: "{\"nested\": {\"data\": 123}}"

Renders as:
▼ (parsed from string)
  └── ▼ nested
      └── data: 123
```

---

## 9. Statistics & Analysis

### 9.1 Statistics Panel

Toggle with `s`. Shows on right side (or bottom on narrow terminals).

```
┌─ Table ────────────────────────────────┬─ Statistics ─────────────┐
│ ...                                     │ Records: 70,234          │
│                                         │ Fields: 16               │
│                                         │                          │
│                                         │ Selected: chromosome     │
│                                         │ ───────────────────────  │
│                                         │ Type: string             │
│                                         │ Unique: 25               │
│                                         │ Nulls: 0 (0%)            │
│                                         │                          │
│                                         │ Top Values:              │
│                                         │ ████████ 1 (10,234)      │
│                                         │ ██████   2 (8,421)       │
│                                         │ █████    X (7,123)       │
│                                         │ ...                      │
└─────────────────────────────────────────┴──────────────────────────┘
```

### 9.2 Footer Aggregations

When a numeric column is selected, footer shows:

```
┌────┬──────────┬────────────┬───────────────────────────────────────┐
│ Sum: 1,234,567 │ Avg: 45.2 │ Min: 1 │ Max: 99,999 │ Nulls: 5      │
└────┴──────────┴────────────┴───────────────────────────────────────┘
```

### 9.3 Type Indicators

Column headers show inferred types:

```
│ Symbol Ⓣ │ GeneID Ⓝ │ active Ⓑ │ metadata Ⓞ │
```

- Ⓣ = String (Text)
- Ⓝ = Number
- Ⓑ = Boolean
- Ⓞ = Object
- Ⓐ = Array
- Ⓧ = Mixed types (warning)

---

## 10. Architecture

### 10.1 Module Structure

```
src/jn/tui/
├── __init__.py
├── app.py                    # Main JSONViewerApp
├── model/
│   ├── __init__.py
│   ├── store.py              # RecordStore (loading, caching)
│   ├── navigator.py          # Position tracking, bookmarks
│   └── stats.py              # Statistics aggregation
├── views/
│   ├── __init__.py
│   ├── table_view.py         # DataTable-based view
│   ├── tree_view.py          # Tree-based view
│   └── compare_view.py       # Side-by-side diff
├── widgets/
│   ├── __init__.py
│   ├── smart_cell.py         # Content detection + rendering
│   ├── stats_panel.py        # Statistics sidebar
│   └── search_bar.py         # Filter input
├── screens/
│   ├── __init__.py
│   ├── main.py               # Primary layout
│   ├── detail.py             # Record detail modal
│   ├── export.py             # Export dialog
│   ├── help.py               # Help overlay
│   └── command_palette.py    # Ctrl+P palette
├── controllers/
│   ├── __init__.py
│   ├── search.py             # In-memory search/filter
│   ├── clipboard.py          # Copy operations
│   └── keybindings.py        # Key dispatch
└── formatters/
    ├── __init__.py
    ├── value.py              # Date/number/byte formatting
    ├── syntax.py             # Code syntax highlighting
    └── path.py               # JSONPath generation
```

### 10.2 Plugin Wrapper

The plugin remains a thin wrapper:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["textual>=0.90.0", "rich>=13.9.0"]
# [tool.jn]
# matches = [".*\\.viewer$", "^-$", "^stdout$"]
# ///

from jn.tui.app import JSONViewerApp

def writes(config=None):
    app = JSONViewerApp(config=config)
    app.run()

if __name__ == "__main__":
    # CLI parsing...
    writes(config)
```

### 10.3 Data Flow

```
stdin (NDJSON)
     │
     ▼
┌─────────────────┐
│ RecordStore     │  ← Streaming load, disk-backed for large datasets
│ - records[]     │
│ - load_worker   │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ SearchController│  ← In-memory filtering (Python, not subprocess)
│ - filter()      │
│ - matches[]     │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ View Layer      │  ← Table/Tree/Compare
│ - render()      │
│ - navigate()    │
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ Clipboard/Export│  ← Copy, save, pipe
│ - copy_json()   │
│ - export_file() │
└─────────────────┘
```

---

## 11. Implementation Roadmap

### Phase 1: Foundation (Week 1)
**Goal:** Table mode works, navigation is solid

- [ ] Refactor `json_viewer.py` into `src/jn/tui/` package
- [ ] Implement `RecordStore` with streaming load
- [ ] Implement basic `TableView` with DataTable widget
- [ ] Implement Vim navigation (j/k/g/G)
- [ ] Toggle between Table and Tree mode (`t` key)

**Deliverable:** `jn view data.json` shows table, `t` switches to tree

### Phase 2: Search & Filter (Week 2)
**Goal:** Find data fast

- [ ] In-memory search with `/` key
- [ ] Real-time filtering (no subprocess)
- [ ] Field filter dialog (`f` key)
- [ ] Filter indicators in header
- [ ] Clear filter with `Esc` or `x`

**Deliverable:** `/BRAF` instantly filters to matching rows

### Phase 3: Drill-Down & Export (Week 3)
**Goal:** Pipeline integration

- [ ] Detail modal on `Enter`
- [ ] Copy current row (`y`)
- [ ] Copy JSONPath (`yp`)
- [ ] Export dialog (`x`)
- [ ] Smart cell content detection

**Deliverable:** Copy path from viewer, paste into `jn filter`

### Phase 4: Statistics (Week 4)
**Goal:** Understand data at a glance

- [ ] Statistics panel (`s` toggle)
- [ ] Column type inference
- [ ] Footer aggregations for numeric columns
- [ ] Null/unique counts

**Deliverable:** Stats panel shows distribution like `jn inspect`

### Phase 5: Power Features (Week 5+)
**Goal:** Power user efficiency

- [ ] Compare mode (`c`)
- [ ] Command palette (`Ctrl+P`)
- [ ] Bookmarks persistence
- [ ] Column sorting/pinning
- [ ] Regex search toggle

**Deliverable:** Full-featured data exploration tool

---

## 12. Keyboard Reference

### Navigation

| Key | Action |
|-----|--------|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `h` / `←` | Move left / Collapse |
| `l` / `→` | Move right / Expand |
| `g` / `Home` | Go to first |
| `G` / `End` | Go to last |
| `Ctrl+D` | Page down |
| `Ctrl+U` | Page up |
| `:` / `#` | Go to record number |

### Mode

| Key | Action |
|-----|--------|
| `t` | Toggle Table/Tree |
| `Enter` | Open detail modal |
| `Esc` | Close modal / Clear filter |
| `c` | Compare mode |
| `s` | Toggle stats panel |
| `?` | Help screen |
| `q` | Quit |

### Search

| Key | Action |
|-----|--------|
| `/` | Quick search |
| `f` | Field filter |
| `n` | Next match |
| `N` | Previous match |
| `Ctrl+R` | Toggle regex |

### Copy/Export

| Key | Action |
|-----|--------|
| `y` | Copy row as JSON |
| `yc` | Copy cell value |
| `yp` | Copy JSONPath |
| `yf` | Copy as filter expr |
| `x` | Export dialog |
| `\|` | Pipe to command |

### Bookmarks

| Key | Action |
|-----|--------|
| `m` | Mark record |
| `u` | Unmark record |
| `'` | Jump to bookmark |

---

## Why This Design

### 1. Tables Are the Right Default

Gene data has 16 flat columns. Showing one record at a time forces users to press `n` 70,000 times. Tables let you scan hundreds of rows at once.

### 2. In-Memory Search Eliminates Hangs

The original implementation spawned a subprocess per record. With 70,000 records, that's 70,000 process spawns - guaranteed hang. This design mandates Python-only filtering.

### 3. Pipeline Integration Is First-Class

The ability to copy a JSONPath and paste it into `jn filter` closes the explore→transform loop. This is what makes viewer a "lens" in the pipeline, not a standalone app.

### 4. Progressive Disclosure Prevents Overwhelm

New users see: arrows to move, `q` to quit. Power users discover vim keys, regex, compare mode. Everyone gets what they need.

### 5. Architecture Enables Evolution

Separating into `model/`, `views/`, `controllers/` means we can add features without growing a 1000-line monolith. Each concern is isolated and testable.

---

## Comparison to Prior Documents

| Aspect | Original Pro Design | This Design |
|--------|--------------------| ------------|
| Default view | Auto-detect (table if flat) | Always table (simpler) |
| Search | jq expressions | In-memory Python (no hang) |
| Architecture | Mentioned modularization | Detailed module structure |
| Pipeline integration | Copy JSONPath | + Copy as filter expr, pipe to command |
| Smart cells | Listed as Tier 3 | Core feature (content detection) |
| Statistics | Side panel | + Footer aggregations |

**This document is the synthesis:** It takes the best UX ideas from the original (table mode, stats panel, vim keys) and combines them with the performance fixes (in-memory search) and pipeline integration (copy path/filter) that emerged from real-world testing with 70,000-record gene datasets.
