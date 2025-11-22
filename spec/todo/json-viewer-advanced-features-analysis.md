# JSON Viewer Advanced Features - Analysis & Ranking

**Purpose:** Comprehensive analysis of polished features for the Textual JSON Viewer

---

## All Potential Features (Unfiltered)

### 1. Streaming/Incremental Rendering
**What:** Display records as they arrive on stdin, not after reading entire stream
**Why:** JN's philosophy is streaming - viewer should start showing data immediately
**Complexity:** Medium - Textual is async-native, supports this pattern
**Value:** HIGH - Critical for large datasets, feels fast

### 2. Statistics Panel
**What:** Side panel showing: record count, field distributions, null %, unique values
**Why:** Data exploration tool - users need to understand data shape before diving in
**Complexity:** Low - Just aggregation and a Static widget
**Value:** HIGH - Essential for data analysis workflows

### 3. Value Formatting
**What:** Smart display of dates, currencies, large numbers (1234567 → 1.2M)
**Why:** Raw values are hard to read - formatting improves comprehension
**Complexity:** Low - Just format functions
**Value:** HIGH - Professional polish, much better UX

### 4. Copy JSONPath to Current Node
**What:** Press 'p' to copy `$.users[0].address.city` to clipboard
**Why:** Users exploring data need to reference paths for jq/filter commands
**Complexity:** Low - Track path during tree building, use clipboard library
**Value:** HIGH - Perfect fit for JN workflow (explore → filter → transform)

### 5. Quick Stats in Table Mode
**What:** Footer row showing sum/avg/min/max for numeric columns
**Why:** Table viewers without aggregations feel incomplete
**Complexity:** Low - DataTable supports footer rows
**Value:** HIGH - Expected feature for tabular data

### 6. Command Palette
**What:** Press Ctrl+P → fuzzy search all commands ("exp" → "Expand All")
**Why:** Discoverability - users don't memorize 30 keyboard shortcuts
**Complexity:** Medium - Textual's Input widget + fuzzy matching
**Value:** MEDIUM-HIGH - Modern UX pattern, great for new users

### 7. Export Current View
**What:** Export visible data (with current filters/collapsed nodes) to JSON/CSV
**Why:** "I filtered down to 10 interesting records, now save them"
**Complexity:** Low - Just write visible records to file
**Value:** HIGH - Natural workflow: explore → filter → export

### 8. Split View / Compare Mode
**What:** View two records side by side, highlighting differences
**Why:** "Why did record A succeed but record B fail?" - debugging workflow
**Complexity:** Medium - Two tree widgets side by side, diff highlighting
**Value:** MEDIUM-HIGH - Powerful for debugging, API responses

### 9. Type Inference Display
**What:** Show inferred schema: `{id: int, name: string, age: int|null}`
**Why:** Understand data shape at a glance, find type inconsistencies
**Complexity:** Medium - Scan all records, infer types, display in panel
**Value:** MEDIUM - Very useful for heterogeneous/dirty data

### 10. Smart Column Width Allocation
**What:** Dynamically size columns based on content length, not fixed width
**Why:** `id` column doesn't need 20 chars, `description` needs more
**Complexity:** Low - Calculate max length per column
**Value:** MEDIUM - Professional polish, better space utilization

### 11. Pattern Highlighting
**What:** Highlight duplicates, outliers, nulls in different colors
**Why:** Visual scanning - spot issues quickly
**Complexity:** Medium - Statistical analysis + conditional styling
**Value:** MEDIUM - Good for data quality checks

### 12. Bookmarks
**What:** Press 'm' to bookmark current record, 'b' to list bookmarks
**Why:** "I found 5 interesting records in 10K dataset, mark them"
**Complexity:** Low - Just maintain a set of indices
**Value:** MEDIUM - Useful for large datasets

### 13. Responsive Layouts
**What:** Wide terminal → tree+stats side-by-side, narrow → stack vertically
**Why:** Adapt to user's environment, maximize info density
**Complexity:** Medium - Textual's responsive containers
**Value:** MEDIUM - Professional polish

### 14. Filter History / Undo
**What:** Undo last filter, see filter history, reapply previous filters
**Why:** "Oops, filtered too much, go back"
**Complexity:** Low - Stack of previous states
**Value:** MEDIUM - Nice UX, not critical

### 15. Visual Filter Builder
**What:** UI for building filters: dropdowns for fields, operators, values
**Why:** Non-technical users, discoverability
**Complexity:** HIGH - Complex UI, many edge cases
**Value:** LOW-MEDIUM - Keyboard/text is faster for target users

### 16. Minimap
**What:** Tiny overview of entire dataset (like VSCode minimap)
**Why:** "Where am I in 10K records?"
**Complexity:** MEDIUM-HIGH - Render compressed view
**Value:** LOW-MEDIUM - Cool but takes precious screen space

### 17. Multi-Select & Bulk Actions
**What:** Select multiple records (Shift+Click), then export/delete/compare
**Why:** "Export these 10 records I found"
**Complexity:** HIGH - Complex interaction model, state management
**Value:** MEDIUM - Powerful but niche

### 18. Custom Themes
**What:** User-configurable color schemes, save as profiles
**Why:** Personalization, accessibility (color blindness)
**Complexity:** MEDIUM - Theme system, config files
**Value:** LOW-MEDIUM - Nice to have, not essential

### 19. Linked Navigation
**What:** Click on `user_id: 123` → jump to user record with id=123
**Why:** Explore relationships between records
**Complexity:** HIGH - Requires understanding data relationships
**Value:** LOW-MEDIUM - Very cool but complex, niche

### 20. Auto-Refresh / Watch Mode
**What:** Watch file for changes, auto-reload viewer
**Why:** Monitor logs, live data
**Complexity:** MEDIUM - File watching, incremental updates
**Value:** MEDIUM - Useful for specific workflows (already in future plans)

### 21. Record Diffing (Internal)
**What:** Select two records in the viewer, show diff
**Why:** In-viewer comparison without external tools
**Complexity:** MEDIUM - Diff algorithm, highlighting
**Value:** MEDIUM - Convenient but Split View covers this

### 22. Fold Similar Records
**What:** "100 records with status=pending" → collapsed into one expandable node
**Why:** Reduce visual noise in repetitive data
**Complexity:** MEDIUM-HIGH - Similarity detection, grouping
**Value:** LOW-MEDIUM - Clever but confusing UX

### 23. Value Truncation with Hover
**What:** Long strings show "..." but hovering shows full value in tooltip
**Why:** See truncated values without expanding entire node
**Complexity:** MEDIUM - Textual tooltip support
**Value:** MEDIUM - Nice polish

### 24. Saved Filter Profiles
**What:** Save common filters as named profiles, load with hotkey
**Why:** "I always filter users by status=active, save this"
**Complexity:** LOW-MEDIUM - Config files, UI for managing
**Value:** LOW-MEDIUM - Advanced users only

### 25. JSONPath Search Mode
**What:** Search using JSONPath expressions, not just text
**Why:** Powerful querying - `$.users[?(@.age > 25)]`
**Complexity:** MEDIUM - JSONPath library, integration
**Value:** MEDIUM-HIGH - Power user feature (mentioned in future plans)

---

## Force Ranking by Value/Complexity Ratio

### Tier 1: Must-Have Polish (Include in Main Design)
1. **Streaming/Incremental Rendering** - Philosophy fit, large dataset support
2. **Copy JSONPath** - Perfect workflow integration with jq/filter
3. **Value Formatting** - Professional polish, easy win
4. **Statistics Panel** - Data exploration essential
5. **Quick Stats (Table Mode)** - Table stakes for tabular views
6. **Export Current View** - Natural workflow completion

### Tier 2: Strong Nice-to-Haves (Include in Enhanced Phase)
7. **Command Palette** - Discoverability boost
8. **Split View / Compare** - Debugging power tool
9. **Smart Column Widths** - Professional polish
10. **Type Inference Display** - Data understanding aid
11. **Pattern Highlighting** - Visual data quality

### Tier 3: Good Ideas (Future Enhancements)
12. **Bookmarks** - Useful for large datasets
13. **Responsive Layouts** - Adaptive UX
14. **Filter History** - Nice UX safety net
15. **JSONPath Search** - Power user feature

### Tier 4: Cool But Not Critical
16. **Minimap** - Screen space trade-off
17. **Value Truncation Hover** - Marginal improvement
18. **Watch Mode** - Already planned separately
19. **Record Diffing** - Covered by Split View
20. **Multi-Select** - Complex for benefit

### Tier 5: Skip for Now
21. **Visual Filter Builder** - Wrong audience
22. **Custom Themes** - Low priority
23. **Linked Navigation** - Too complex
24. **Fold Similar** - Confusing UX
25. **Saved Filters** - Over-engineering

---

## Recommended Additions to Design

### Add to Main Design (Core Features):
1. **Streaming/Incremental Rendering**
2. **Statistics Panel**
3. **Value Formatting**
4. **Copy JSONPath**

### Add to Phase 2 (Enhanced):
5. **Quick Stats in Table Mode**
6. **Export Current View**
7. **Command Palette**

### Add to Phase 3 (Advanced):
8. **Split View / Compare Mode**
9. **Type Inference Display**
10. **Smart Column Widths**
11. **Pattern Highlighting**

---

## Rationale for Top Picks

### Why Streaming/Incremental Rendering?
- **JN's core philosophy**: Unix pipes stream data, tools process incrementally
- **User expectation**: `jn cat huge.json | jn put "-~viewer"` should start showing data immediately
- **Real-world impact**: Difference between 0.1s and 30s to first record
- **Technical fit**: Textual is async-native, supports this naturally

### Why Statistics Panel?
- **Data exploration**: First question is "what am I looking at?"
- **Informs decisions**: "10K records, 50% have null emails" → filter strategy
- **Low cost**: Just aggregation, doesn't slow rendering
- **Professional feel**: Tools like DBeaver, Excel always show stats

### Why Value Formatting?
- **Readability**: `2024-11-22T15:30:00Z` vs "Nov 22, 3:30pm"
- **Comprehension**: `1234567` vs "1.2M"
- **Easy win**: Pure display logic, no complexity
- **Expected feature**: Users assume dates/numbers will be formatted

### Why Copy JSONPath?
- **Workflow integration**: Viewer is exploration step, jq/filter is manipulation step
- **Bridge the gap**: "I found the field I want" → copy path → use in filter
- **Developer-friendly**: JSONPath is precise, no ambiguity
- **Low complexity**: Just track path during tree traversal

### Why Quick Stats (Table Mode)?
- **Table stakes**: Every spreadsheet/DB tool has this
- **Immediate value**: "Sum of revenue: $1.2M" without leaving viewer
- **Low cost**: Single aggregation pass, footer row
- **Expected UX**: Tables without totals feel incomplete

### Why Export Current View?
- **Complete the workflow**: Explore → filter → collapse → export subset
- **Real use case**: "Found 10 anomalies in 10K records, save for later"
- **JN philosophy**: Data flows, transformations are visible
- **Simple**: Just write currently visible records to file

### Why Command Palette?
- **Discoverability**: 30 keyboard shortcuts is too much to memorize
- **Modern pattern**: VSCode, GitHub, Slack all have this
- **Fuzzy search**: "exp" → "Expand All", "col" → "Collapse to Depth"
- **New user friendly**: No need to learn shortcuts first

---

## Why NOT Include Others?

### Visual Filter Builder
- **Wrong audience**: JN users are technical, prefer keyboard
- **Slower**: Building `age > 25 AND status='active'` is faster as text
- **Maintenance burden**: Complex UI, many edge cases

### Minimap
- **Screen space**: Terminal is already cramped, sidebar takes columns
- **Limited value**: Scrollbar already shows position
- **Implementation cost**: Rendering compressed view is non-trivial

### Custom Themes
- **Personalization ≠ Priority**: Nice to have, not blocking workflows
- **Accessibility**: Better to ensure defaults work (high contrast)
- **Complexity**: Theme system, validation, persistence

### Multi-Select
- **Interaction complexity**: Shift+Click, Ctrl+Click, visual feedback
- **State management**: Track selection across filtering, collapsing
- **Alternative exists**: Export with filters achieves same goal

---

**Conclusion:** The top 6-7 features (Tier 1 + top of Tier 2) add significant polish without over-engineering. They align with JN's philosophy, complete workflows, and provide professional UX.
