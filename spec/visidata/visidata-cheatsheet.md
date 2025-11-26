# VisiData Cheat Sheet for JN Users

**Date:** 2025-11-25
**Status:** Reference Documentation
**Purpose:** Complete mapping of planned jn view features to VisiData equivalents

---

## Quick Start

```bash
# Install VisiData
uv tool install visidata

# Basic usage with jn
jn cat data.csv | jn vd
jn vd data.json
jn vd "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz"

# With pre-filtering
jn cat data.csv | jn filter '.revenue > 1000' | jn vd
```

---

## Feature Mapping: Planned jn view vs VisiData

This section maps every feature from the `json-viewer-pro-design.md` and `viewer-v2-design.md` specs to VisiData equivalents.

### Core Features (MVP)

| Planned Feature | VisiData Equivalent | Keys |
|-----------------|---------------------|------|
| Tree view with syntax highlighting | Column view (flat) or `z(` to expand nested | `z(` expand, `z)` collapse |
| Record navigation (next/prev) | Row navigation | `j/k` or `↓/↑` |
| Jump to first/last record | Go to top/bottom | `gg` / `G` |
| Jump to record N | Go to row | `zr N` then Enter |
| Quit | Quit | `q` |
| Help | Help menu | `Ctrl+H` or `Alt+H` |

### Table Mode (Tier 1)

| Planned Feature | VisiData Equivalent | Keys |
|-----------------|---------------------|------|
| **Table view (default)** | Native behavior | (default) |
| Auto-detect column widths | Auto-fit width | `_` (underscore) |
| Sort ascending | Sort ascending | `[` |
| Sort descending | Sort descending | `]` |
| Multi-column sort | Sort by key columns | Mark keys with `!`, then `g[` |
| Hide column | Hide column | `-` |
| Show all columns | Unhide | `gv` |
| Resize column | Set width | `_` auto-fit, or Shift+arrow |
| Row numbers | Toggle row index | Built-in (leftmost column) |

### Statistics Panel (Tier 1)

| Planned Feature | VisiData Equivalent | Keys |
|-----------------|---------------------|------|
| **Record count** | Shown in status bar | (always visible) |
| **Field count** | Column count in status | (always visible) |
| **Null percentage** | Describe sheet | `Shift+I` |
| **Unique value count** | Describe sheet or Frequency | `Shift+I` or `Shift+F` |
| **Type distribution** | Describe sheet | `Shift+I` |
| **Column statistics** | Describe sheet | `Shift+I` shows min/max/mean/etc |
| **Top values** | Frequency table | `Shift+F` |

**VisiData Describe Sheet (`Shift+I`):**
```
Shows per column: type, nulls, unique count, mode, min, max, mean, median, stdev
```

### Value Formatting (Tier 1)

| Planned Feature | VisiData Equivalent | Keys |
|-----------------|---------------------|------|
| Date formatting | Set column type to date | `@` |
| Number formatting | Set column type | `#` (int), `%` (float), `$` (currency) |
| String type | Set column type to text | `~` |
| Length display | Set column type to length | `z#` |

### Search & Filter (Tier 1)

| Planned Feature | VisiData Equivalent | Keys |
|-----------------|---------------------|------|
| **Quick search (substring)** | Regex search | `/` + pattern |
| **Search all columns** | Global search | `g/` + pattern |
| **Next/prev match** | Navigate matches | `n` / `N` |
| **Field equals value** | Select by cell value | `"` select matching, then `gd` to delete non-selected |
| **Python expression filter** | Select by expression | `z\|` + Python expr |
| **Regex filter** | Select by regex | `\|` + regex (current col) or `g\|` (all cols) |
| **Clear filter** | Unselect all | `gu` |
| **Filter to selected** | Delete unselected | `gd` (deletes unselected rows) |

**Example: Filter to rows where Symbol contains "BRAF":**
```
1. Press |
2. Type: BRAF
3. Press Enter (selects matching rows)
4. Press " to open selected rows as new sheet
```

### Copy & Export (Tier 1)

| Planned Feature | VisiData Equivalent | Keys |
|-----------------|---------------------|------|
| **Copy current row** | Yank row | `y` |
| **Copy cell value** | Yank cell | `zy` |
| **Copy selected rows** | Yank selected | `gy` |
| **Copy as JSON** | Save to JSON | `Ctrl+S`, then type filename.json |
| **Export filtered data** | Save sheet | `Ctrl+S` |
| **Export to CSV** | Save as CSV | `Ctrl+S`, then filename.csv |
| **Export to NDJSON** | Save as JSONL | `Ctrl+S`, then filename.jsonl |

### Aggregation (Tier 2)

| Planned Feature | VisiData Equivalent | Keys |
|-----------------|---------------------|------|
| **Sum** | Add aggregator + view | `+` then `sum`, then `Shift+F` |
| **Average** | Add aggregator | `+` then `mean` |
| **Min/Max** | Add aggregator | `+` then `min` or `max` |
| **Count** | Frequency table | `Shift+F` |
| **Group by field** | Frequency table | `Shift+F` on grouping column |
| **Pivot table** | Pivot | `Shift+W` |

**Example: Sum revenue by region:**
```
1. Navigate to "region" column
2. Press ! to make it a key column
3. Navigate to "revenue" column
4. Press + and type "sum"
5. Press Shift+F to create frequency table with sums
```

### Compare Mode (Tier 3)

| Planned Feature | VisiData Equivalent | Keys |
|-----------------|---------------------|------|
| **Side-by-side diff** | Join sheets (diff) | `&` with `diff` join type |
| **Highlight differences** | Diff join shows only differences | Select rows, open as sheet, join |

**Compare two records:**
```
1. Mark first record with 's'
2. Press " to open selected as new sheet
3. Go back to main sheet (Shift+S, select)
4. Mark second record with 's'
5. Press " to open as another sheet
6. Use & to join/diff the two sheets
```

### Command Palette (Tier 2)

| Planned Feature | VisiData Equivalent | Keys |
|-----------------|---------------------|------|
| **Command palette** | Execute by longname | `Space` + command name |
| **Fuzzy search** | Type partial command | `Space` + type to filter |

**Example:** `Space` then type `freq` to find frequency-related commands.

### Smart Features (Tier 3)

| Planned Feature | VisiData Equivalent | Keys |
|-----------------|---------------------|------|
| **Type inference** | Auto-detect types | Types shown in column header |
| **Expand nested JSON** | Expand column | `(` on list/dict columns |
| **Contract nested** | Collapse | `)` |
| **Smart column widths** | Auto-fit all | `g_` |

---

## Deep Dive: VisiData's JSON Handling

VisiData has powerful built-in JSON capabilities that deserve special attention.

### JSON File Formats Supported

| Format | Description | Since |
|--------|-------------|-------|
| `json` | Standard JSON (arrays/objects) | v0.28 |
| `jsonl` / `ndjson` / `ldjson` | JSON Lines (one object per line) | v1.3 |
| `vdj` | VisiData command log (JSON) | v2.0 |

### JSON Column Expansion Commands

| Key | Command | Description |
|-----|---------|-------------|
| `(` | `expand-col` | Expand nested dict/list one level |
| `)` | `contract-col` | Collapse expanded columns |
| `z(` | `expand-col-depth` | Expand to specific depth (0 = fully flatten) |
| `gz(` | `expand-cols` | Expand ALL columns recursively |
| `z Shift+M` | `unfurl-col` | Row-wise expansion (creates new rows for list items) |
| `z^Y` | `pyobj-cell` | Open cell as Python object (explore nested structures) |

### Expand vs Unfurl: When to Use Which

**Expand (`(`)** - Column-wise expansion:
- Adds new columns for nested keys
- Row count stays the same
- Best for: Flattening nested objects

```
Before:                          After (pressing `(` on address):
┌────────────────────────┐       ┌───────────────────────────────────────┐
│ name    │ address      │       │ name    │ address.city │ address.zip │
├─────────┼──────────────┤       ├─────────┼──────────────┼─────────────┤
│ Alice   │ {city, zip}  │  →    │ Alice   │ NYC          │ 10001       │
│ Bob     │ {city, zip}  │       │ Bob     │ Boston       │ 02101       │
└─────────┴──────────────┘       └─────────┴──────────────┴─────────────┘
```

**Unfurl (`z Shift+M`)** - Row-wise expansion:
- Creates new rows for each list item
- Duplicates other columns
- Best for: Exploding arrays into rows

```
Before:                          After (pressing `z Shift+M` on tags):
┌────────────────────────┐       ┌─────────────────────┐
│ name    │ tags         │       │ name    │ tags      │
├─────────┼──────────────┤       ├─────────┼───────────┤
│ Alice   │ [a, b, c]    │  →    │ Alice   │ a         │
│ Bob     │ [x, y]       │       │ Alice   │ b         │
└─────────┴──────────────┘       │ Alice   │ c         │
                                 │ Bob     │ x         │
                                 │ Bob     │ y         │
                                 └─────────┴───────────┘
```

### JSON Save Options

| Option | Default | Description |
|--------|---------|-------------|
| `json_indent` | None | Indentation for pretty-printing (None = minified) |
| `json_sort_keys` | False | Sort object keys alphabetically |
| `default_colname` | "" | Column name for non-dict rows |

### Exploring Deeply Nested JSON

For deeply nested structures, use `z^Y` (pyobj-cell) to open any cell as its own explorable sheet:

```
1. Navigate to cell containing nested data
2. Press z^Y
3. VisiData opens the cell contents as a new sheet
4. Navigate/expand as needed
5. Press q to return to parent sheet
```

This is VisiData's equivalent to jn view's tree navigation!

### JMESPath Support (Built-in since v2.12)

VisiData v2.12+ has built-in JMESPath support for JSON querying:

| Key | Command | Description |
|-----|---------|-------------|
| `z=` + expr | Add JMESPath column | Create new column from JMESPath expression |
| `z\|` + expr | Select by JMESPath | Select rows matching JMESPath expression |

**Note:** For older versions, install the [ajkerrigan/visidata-plugins](https://github.com/ajkerrigan/visidata-plugins) JMESPath plugin.

JMESPath is similar to jq but with a cleaner syntax for simple queries. Example:
```
JMESPath: user.address.city
jq:       .user.address.city
```

---

## VisiData Features NOT in Original jn view Plans

These are powerful features VisiData provides that weren't in the original specs:

### Frequency Tables (Game Changer)

```
Shift+F - Create frequency table showing value distribution

Example output for "chromosome" column:
┌────────────┬───────┬──────────┐
│ chromosome │ count │ percent  │
├────────────┼───────┼──────────┤
│ 1          │ 5,234 │ 7.5%     │
│ 2          │ 4,123 │ 5.9%     │
│ X          │ 2,345 │ 3.3%     │
│ ...        │       │          │
└────────────┴───────┴──────────┘
```

### Pivot Tables

```
Shift+W - Create pivot table (Excel-style cross-tabulation)
```

### Melt/Unpivot

```
Shift+M - Transform wide data to long format
```

### Transpose

```
Shift+T - Swap rows and columns
```

### Multi-Sheet Operations

```
Shift+S - View all open sheets
& - Join/merge sheets
```

### Undo/Redo

```
U - Undo last action
R - Redo
```

### Macros

```
m + key - Record macro
@ + key - Play macro
```

### Split Screen

```
Z - Split screen horizontally
```

### Canvas/Plotting

```
. - Plot current numeric column
g. - Plot all numeric columns
```

### Deferred Expensive Operations

VisiData computes aggregations lazily - you can work with huge datasets without waiting for full computation.

---

## Complete Keyboard Reference

### Movement

| Key | Action |
|-----|--------|
| `h/j/k/l` or arrows | Move left/down/up/right |
| `gh/gj/gk/gl` | Jump to edge (leftmost/bottom/top/rightmost) |
| `gg` / `G` | First row / Last row |
| `Ctrl+F` / `Ctrl+B` | Page down / Page up |
| `zz` | Center current row |
| `zr N` | Go to row N |

### Search

| Key | Action |
|-----|--------|
| `/` + pattern | Search forward in current column |
| `?` + pattern | Search backward |
| `g/` + pattern | Search all columns |
| `n` / `N` | Next / previous match |
| `c` + pattern | Jump to column matching pattern |

### Selection

| Key | Action |
|-----|--------|
| `s` | Select current row |
| `u` | Unselect current row |
| `t` | Toggle selection |
| `gs` / `gu` / `gt` | Select/unselect/toggle all |
| `\|` + regex | Select rows matching regex (current column) |
| `g\|` + regex | Select rows matching regex (any column) |
| `z\|` + expr | Select by Python expression |
| `,` | Select rows matching current cell |
| `"` | Open selected rows as new sheet |

### Sorting

| Key | Action |
|-----|--------|
| `[` | Sort ascending by current column |
| `]` | Sort descending |
| `g[` / `g]` | Sort by all key columns |

### Columns

| Key | Action |
|-----|--------|
| `-` | Hide current column |
| `gv` | Unhide all columns |
| `_` | Auto-fit column width |
| `g_` | Auto-fit all columns |
| `!` | Toggle key column (for grouping/sorting) |
| `^` | Rename column |
| `~` | Set type: string |
| `#` | Set type: integer |
| `%` | Set type: float |
| `$` | Set type: currency |
| `@` | Set type: date |
| `=` + expr | Add derived column |
| `(` | Expand list/dict column |
| `)` | Contract expanded column |

### Aggregation

| Key | Action |
|-----|--------|
| `Shift+F` | Frequency table |
| `Shift+I` | Describe sheet (statistics) |
| `Shift+W` | Pivot table |
| `+` + aggregator | Add aggregator to column |
| `z+` | Show aggregator for selected rows |

### Sheets

| Key | Action |
|-----|--------|
| `Shift+S` | Sheets sheet (list all open) |
| `q` | Close current sheet |
| `gq` | Quit VisiData |
| `^^` | Jump to previous sheet |
| `&` | Join sheets |

### Editing

| Key | Action |
|-----|--------|
| `e` | Edit cell |
| `a` | Add new row |
| `d` | Delete row |
| `gd` | Delete selected rows |
| `y` | Yank (copy) row |
| `gy` | Yank selected rows |
| `p` | Paste rows |

### File Operations

| Key | Action |
|-----|--------|
| `o` + path | Open file |
| `Ctrl+S` | Save current sheet |
| `g Ctrl+S` | Save all sheets |

### Help

| Key | Action |
|-----|--------|
| `Ctrl+H` | Open help menu |
| `Alt+H` | Activate help menu |
| `z Ctrl+H` | Show commands for current sheet type |
| `Space` | Command palette (type command name) |

---

## Common Workflows

### Explore Gene Data

```bash
jn head -n 10000 "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz" | jn vd
```

Then in VisiData:
1. `Shift+F` on "chromosome" to see distribution
2. `|` + `kinase` to select genes with "kinase" in current column
3. `"` to open selected as new sheet
4. `[` to sort
5. `Ctrl+S` to save filtered results

### Find Specific Records

```bash
jn cat data.json | jn vd
```

1. `g/` + `BRAF` - Search all columns
2. `n` to navigate matches
3. `s` to select interesting rows
4. `"` to isolate selected
5. `y` to copy a row

### Statistical Analysis

```bash
jn cat sales.csv | jn vd
```

1. `Shift+I` - See column statistics (min, max, mean, nulls)
2. Navigate to "region" column, press `!` (key column)
3. Navigate to "revenue" column, press `+`, type `sum`
4. `Shift+F` - Frequency table with sum by region

### Clean and Export

```bash
jn cat messy.csv | jn vd
```

1. `Shift+I` - Find columns with nulls
2. Navigate to bad column, press `-` to hide
3. `g_` - Auto-fit all columns
4. `[` - Sort by first column
5. `Ctrl+S`, type `clean.csv` - Export

---

## Comparison: jn view vs jn vd (VisiData)

| Capability | jn view (Textual) | jn vd (VisiData) |
|------------|-------------------|------------------|
| Tree view for nested JSON | Excellent | Limited (use `(` to expand) |
| Table view | Basic | Excellent |
| Sorting | No | Yes (one-key) |
| Filtering | Limited (Python only) | Excellent (regex, Python, cell match) |
| Frequency tables | No | Yes (`Shift+F`) |
| Statistics | No | Yes (`Shift+I`) |
| Pivot tables | No | Yes (`Shift+W`) |
| Multi-sheet | No | Yes |
| Joins | No | Yes (`&`) |
| Undo/redo | No | Yes (`U`/`R`) |
| Export formats | JSON only | 40+ formats |
| Memory handling | Disk-backed | Lazy loading |
| External dependency | Textual | VisiData (GPL) |
| Nested JSON drill-down | Excellent | Manual expansion |

**Recommendation:**
- Use `jn vd` (VisiData) for: tabular data, statistics, frequency analysis, sorting, filtering, multi-sheet operations
- Use `jn view` for: deeply nested JSON where tree navigation is essential

---

## Installation & Licensing Notes

**Installation:**
```bash
uv tool install visidata
```

**Licensing:**
- VisiData: GPL v3
- JN: MIT
- Safe to use together via pipes (no license contamination)
- VisiData is not bundled with JN - users install separately by choice

---

## References

### Official Documentation
- [VisiData Official Site](https://www.visidata.org/)
- [VisiData Manual](https://www.visidata.org/man/)
- [VisiData Cheat Sheet](https://jsvine.github.io/visidata-cheat-sheet/)
- [VisiData Loader API](https://www.visidata.org/docs/api/loaders)
- [VisiData Formats](https://www.visidata.org/docs/formats/)

### VisiData Plugins
- [ajkerrigan/visidata-plugins](https://github.com/ajkerrigan/visidata-plugins) - JMESPath, S3, and more
- [VisiData Plugin API](https://www.visidata.org/docs/api/)

### GitHub Discussions (Useful Examples)
- [Flatten structured data](https://github.com/saulpw/visidata/discussions/1605) - Using expand/unfurl
- [Stdin pipe usage](https://github.com/saulpw/visidata/discussions/1106) - Piping data to VisiData
- [Piping example](https://github.com/saulpw/visidata/discussions/1818) - Example workflows

### JN Documentation
- JN VisiData Integration: `spec/done/visidata-integration.md`
- JN VisiData Plugin Design: `spec/wip/visidata-plugin-design.md`
