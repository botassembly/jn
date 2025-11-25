#!/usr/bin/env -S uv run --script
"""Data Lens - Table-first data exploration tool."""
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "textual>=0.90.0",
#   "rich>=13.9.0",
# ]
# [tool.jn]
# matches = [
#   ".*\\.viewer$",
#   "^-$",
#   "^stdout$"
# ]
# ///

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from typing import Any, Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Static, Tree


# =============================================================================
# Helpers
# =============================================================================

def format_value(value: Any, max_len: int = 50) -> str:
    """Format value for table cell display."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        clean = value.replace("\n", " ").replace("\r", "")
        return clean[:max_len-3] + "..." if len(clean) > max_len else clean
    if isinstance(value, dict):
        return f"{{...}} ({len(value)} keys)"
    if isinstance(value, list):
        return f"[...] ({len(value)} items)"
    s = str(value)
    return s[:max_len-3] + "..." if len(s) > max_len else s


def style_value(value: Any) -> Text:
    """Style value for tree display."""
    if value is None:
        return Text("null", style="dim italic")
    if isinstance(value, bool):
        return Text(str(value).lower(), style="bold yellow")
    if isinstance(value, (int, float)):
        return Text(str(value), style="cyan")
    if isinstance(value, str):
        display = value[:97] + "..." if len(value) > 100 else value
        return Text(f'"{display}"', style="green")
    return Text(str(value))


def compile_filter(expr: str):
    """Compile a simple filter expression to a Python function."""
    expr = expr.strip()
    # Strip select() wrapper
    m = re.match(r'^select\s*\(\s*(.*)\s*\)\s*$', expr)
    if m:
        expr = m.group(1)

    # .field == "value"
    m = re.match(r'^\.(\w+)\s*==\s*"([^"]*)"$', expr)
    if m:
        f, v = m.groups()
        return lambda r, f=f, v=v: r.get(f) == v

    # .field == number
    m = re.match(r'^\.(\w+)\s*==\s*(-?\d+(?:\.\d+)?)$', expr)
    if m:
        f, v = m.groups()
        n = float(v) if '.' in v else int(v)
        return lambda r, f=f, n=n: r.get(f) == n

    # .field > number
    m = re.match(r'^\.(\w+)\s*>\s*(-?\d+(?:\.\d+)?)$', expr)
    if m:
        f, v = m.groups()
        n = float(v) if '.' in v else int(v)
        return lambda r, f=f, n=n: r.get(f) is not None and r.get(f) > n

    # .field < number
    m = re.match(r'^\.(\w+)\s*<\s*(-?\d+(?:\.\d+)?)$', expr)
    if m:
        f, v = m.groups()
        n = float(v) if '.' in v else int(v)
        return lambda r, f=f, n=n: r.get(f) is not None and r.get(f) < n

    # .field (truthy)
    m = re.match(r'^\.(\w+)$', expr)
    if m:
        f = m.group(1)
        return lambda r, f=f: bool(r.get(f))

    return None


# =============================================================================
# Dialogs
# =============================================================================

class GotoDialog(ModalScreen[Optional[int]]):
    """Jump to record number."""

    CSS = """
    GotoDialog { align: center middle; }
    #container { width: 50; height: 7; border: thick $background 80%; background: $surface; padding: 1; }
    """

    def compose(self) -> ComposeResult:
        with Container(id="container"):
            yield Static("Go to record number:", id="label")
            yield Input(placeholder="Enter number (1-based)", id="input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            n = int(event.value)
            self.dismiss(n - 1 if n > 0 else None)
        except ValueError:
            self.dismiss(None)

    def key_escape(self) -> None:
        self.dismiss(None)


class FindDialog(ModalScreen[Optional[str]]):
    """Find by field value."""

    CSS = """
    FindDialog { align: center middle; }
    #container { width: 60; height: 9; border: thick $background 80%; background: $surface; padding: 1; }
    #help { color: $text-muted; margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        with Container(id="container"):
            yield Static("Find records where:", id="label")
            yield Input(placeholder='field = value (e.g., Symbol = BRAF)', id="input")
            yield Static("Use: =, >, <, field (truthy)", id="help")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            self.dismiss(None)
            return
        # Convert simple syntax to jq-style
        for op in ["!=", ">=", "<=", "==", "=", ">", "<"]:
            if op in query:
                parts = query.split(op, 1)
                if len(parts) == 2:
                    field = parts[0].strip()
                    value = parts[1].strip()
                    if not field.startswith("."):
                        field = f".{field}"
                    if op == "=":
                        op = "=="
                    # Auto-quote strings
                    if not (value.startswith('"') or value.replace(".", "").replace("-", "").isdigit()):
                        value = f'"{value}"'
                    self.dismiss(f"{field} {op} {value}")
                    return
        # Bare field name = truthy check
        self.dismiss(f".{query}" if not query.startswith(".") else query)

    def key_escape(self) -> None:
        self.dismiss(None)


class DetailScreen(ModalScreen):
    """Full record detail view."""

    CSS = """
    DetailScreen { align: center middle; }
    #container { width: 90%; height: 90%; border: thick $background 80%; background: $surface; }
    #header { dock: top; height: 3; background: $primary-background; content-align: center middle; }
    #tree { height: 100%; }
    #footer { dock: bottom; height: 1; background: $primary-background; }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    def __init__(self, record: dict, index: int, total: int):
        super().__init__()
        self.record = record
        self.index = index
        self.total = total

    def compose(self) -> ComposeResult:
        with Container(id="container"):
            yield Static(f"Record {self.index + 1} of {self.total}", id="header")
            yield Tree("Record", id="tree")
            yield Static("Esc: Close | Space: Toggle | e: Expand | c: Collapse", id="footer")

    def on_mount(self) -> None:
        tree = self.query_one("#tree", Tree)
        self._build_tree(tree.root, self.record)
        tree.root.expand()
        tree.focus()

    def _build_tree(self, node, data, depth=0):
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)) and v:
                    child = node.add(f"{k} ({type(v).__name__}, {len(v)})", expand=depth < 2)
                    self._build_tree(child, v, depth + 1)
                else:
                    node.add_leaf(f"{k}: {style_value(v)}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)) and item:
                    child = node.add(f"[{i}] ({type(item).__name__}, {len(item)})", expand=depth < 2)
                    self._build_tree(child, item, depth + 1)
                else:
                    node.add_leaf(f"[{i}]: {style_value(item)}")

    def action_close(self) -> None:
        self.dismiss()

    def key_space(self) -> None:
        tree = self.query_one("#tree", Tree)
        if tree.cursor_node:
            tree.cursor_node.toggle()

    def key_e(self) -> None:
        self.query_one("#tree", Tree).root.expand_all()

    def key_c(self) -> None:
        for child in self.query_one("#tree", Tree).root.children:
            child.collapse_all()


class HelpScreen(ModalScreen):
    """Help screen."""

    CSS = """
    HelpScreen { align: center middle; }
    #container { width: 70; height: 28; border: thick $background 80%; background: $surface; padding: 1 2; }
    """

    HELP = """[bold]Navigation[/]
  Arrows/j/k    Move cursor
  g / G         First / Last
  PgUp/PgDn     Page up/down
  #             Go to record number
  Enter         View record detail

[bold]Search[/]
  f             Find by field
  n / N         Next/prev match
  Esc           Clear search

[bold]View[/]
  t             Toggle table/tree
  s             Toggle stats panel

[bold]Other[/]
  m / u         Mark/unmark record
  '             Jump to next mark
  q             Quit
  ?             This help"""

    def compose(self) -> ComposeResult:
        with Container(id="container"):
            yield Static(self.HELP)

    def key_escape(self) -> None:
        self.dismiss()

    def key_question_mark(self) -> None:
        self.dismiss()


# =============================================================================
# Stats Panel
# =============================================================================

class StatsPanel(Static):
    """Statistics panel showing data summary."""

    DEFAULT_CSS = """
    StatsPanel {
        width: 30;
        height: 100%;
        border-left: solid $primary;
        padding: 1;
    }
    """

    def __init__(self, records: list, id: Optional[str] = None, classes: Optional[str] = None):
        super().__init__(id=id, classes=classes)
        self.records = records

    def on_mount(self) -> None:
        self.update_stats()

    def update_stats(self) -> None:
        if not self.records:
            self.update("[bold]No data[/]")
            return

        # Gather stats
        n = len(self.records)
        cols = set()
        types = Counter()
        for r in self.records[:1000]:  # Sample first 1000
            if isinstance(r, dict):
                cols.update(r.keys())
                for k, v in r.items():
                    types[type(v).__name__] += 1

        lines = [
            f"[bold]Statistics[/]",
            f"",
            f"Records: {n:,}",
            f"Columns: {len(cols)}",
            f"",
            f"[bold]Column Types[/]",
        ]
        for t, count in types.most_common(5):
            lines.append(f"  {t}: {count}")

        if len(cols) <= 10:
            lines.append(f"")
            lines.append(f"[bold]Columns[/]")
            for c in sorted(cols):
                lines.append(f"  {c}")

        self.update("\n".join(lines))


# =============================================================================
# Main App
# =============================================================================

class DataLensApp(App):
    """Data Lens - Table-first data exploration."""

    CSS = """
    Screen { background: $surface; }
    #main { height: 100%; }
    #table { height: 100%; }
    #tree { height: 100%; }
    .hidden { display: none; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("question_mark", "help", "?Help", show=True),
        Binding("t", "toggle_view", "Toggle", show=True),
        Binding("s", "toggle_stats", "Stats", show=True),
        Binding("f", "find", "Find", show=True),
        Binding("n", "next_match", "Next", show=False),
        Binding("N", "prev_match", "Prev", show=False),
        Binding("escape", "clear_search", "Clear", show=False),
        Binding("g", "first", "First", show=False),
        Binding("G", "last", "Last", show=False),
        Binding("number_sign", "goto", "#Goto", show=True),
        Binding("m", "mark", "Mark", show=False),
        Binding("u", "unmark", "Unmark", show=False),
        Binding("apostrophe", "next_mark", "Marks", show=False),
    ]

    show_tree: reactive[bool] = reactive(False)
    show_stats: reactive[bool] = reactive(False)

    def __init__(self, records: list):
        super().__init__()
        self.records = records
        self.columns = self._get_columns()
        self.filter_expr: Optional[str] = None
        self.matches: list[int] = []
        self.match_idx = 0
        self.bookmarks: set[int] = set()

    def _get_columns(self) -> list[str]:
        cols = set()
        for r in self.records[:100]:
            if isinstance(r, dict):
                cols.update(r.keys())
        return sorted(cols)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield DataTable(id="table", cursor_type="row", zebra_stripes=True)
            tree = Tree("Record", id="tree", classes="hidden")
            yield tree
            yield StatsPanel(self.records, id="stats", classes="hidden")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Data Lens"
        self._populate_table()
        self._update_subtitle()

    def _populate_table(self) -> None:
        table = self.query_one("#table", DataTable)
        table.clear(columns=True)
        table.add_column("#", key="__n")
        for col in self.columns:
            table.add_column(col, key=col)

        indices = self.matches if self.filter_expr else range(len(self.records))
        self._table_row_count = 0
        self._total_available = len(self.matches) if self.filter_expr else len(self.records)
        for i, idx in enumerate(indices):
            if i >= 10000:  # Limit rows for performance
                break
            if idx < len(self.records):
                r = self.records[idx]
                prefix = "* " if idx in self.bookmarks else ""
                row = [f"{prefix}{idx + 1}"] + [format_value(r.get(c) if isinstance(r, dict) else None) for c in self.columns]
                table.add_row(*row, key=str(idx))
                self._table_row_count += 1

    def _update_subtitle(self) -> None:
        idx = self._current_index()
        total = len(self.records)
        parts = [f"Record {idx + 1 if idx is not None else 0} of {total}"]

        # Show if table is capped
        if hasattr(self, '_table_row_count') and hasattr(self, '_total_available'):
            if self._table_row_count < self._total_available:
                parts.append(f"showing {self._table_row_count:,}")

        if self.filter_expr:
            parts.append(f"{len(self.matches)} matches")
        if self.bookmarks:
            parts.append(f"{len(self.bookmarks)} marked")
        self.sub_title = " | ".join(parts)

    def _current_index(self) -> Optional[int]:
        table = self.query_one("#table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            row_key = table.get_row_at(table.cursor_row)
            # Get the key which is the record index
            keys = list(table.rows.keys())
            if 0 <= table.cursor_row < len(keys):
                return int(keys[table.cursor_row].value)
        return 0 if self.records else None

    def _current_record(self) -> Optional[dict]:
        idx = self._current_index()
        return self.records[idx] if idx is not None and idx < len(self.records) else None

    def watch_show_tree(self, show: bool) -> None:
        self.query_one("#table").set_class(show, "hidden")
        self.query_one("#tree").set_class(not show, "hidden")
        if show:
            self._update_tree()
            self.query_one("#tree").focus()
        else:
            self.query_one("#table").focus()

    def watch_show_stats(self, show: bool) -> None:
        self.query_one("#stats").set_class(not show, "hidden")

    def _update_tree(self) -> None:
        record = self._current_record()
        if not record:
            return
        tree = self.query_one("#tree", Tree)
        tree.clear()
        tree.root.expand()
        self._build_tree_node(tree.root, record)

    def _build_tree_node(self, node, data, depth=0):
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)) and v:
                    child = node.add(f"{k} ({len(v)})", expand=depth < 2)
                    self._build_tree_node(child, v, depth + 1)
                else:
                    node.add_leaf(f"{k}: {style_value(v)}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)) and item:
                    child = node.add(f"[{i}]", expand=depth < 2)
                    self._build_tree_node(child, item, depth + 1)
                else:
                    node.add_leaf(f"[{i}]: {style_value(item)}")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._update_subtitle()
        if self.show_tree:
            self._update_tree()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter/double-click on row - show detail."""
        self.action_detail()

    def action_toggle_view(self) -> None:
        self.show_tree = not self.show_tree

    def action_toggle_stats(self) -> None:
        self.show_stats = not self.show_stats

    def action_detail(self) -> None:
        record = self._current_record()
        idx = self._current_index()
        if record and idx is not None:
            self.push_screen(DetailScreen(record, idx, len(self.records)))

    def action_find(self) -> None:
        def on_result(expr: Optional[str]) -> None:
            if expr:
                self._do_search(expr)
        self.push_screen(FindDialog(), on_result)

    def _do_search(self, expr: str) -> None:
        self.filter_expr = expr
        self.matches = []
        self.match_idx = 0
        fn = compile_filter(expr)
        if fn:
            for i, r in enumerate(self.records):
                try:
                    if fn(r):
                        self.matches.append(i)
                except Exception:
                    pass
        self._populate_table()
        self._update_subtitle()
        if self.matches:
            self.notify(f"Found {len(self.matches)} matches")
        else:
            self.notify("No matches found", severity="warning")

    def action_next_match(self) -> None:
        if self.matches:
            self.match_idx = (self.match_idx + 1) % len(self.matches)
            self._select_match()

    def action_prev_match(self) -> None:
        if self.matches:
            self.match_idx = (self.match_idx - 1) % len(self.matches)
            self._select_match()

    def _select_match(self) -> None:
        if not self.matches:
            return
        target = self.matches[self.match_idx]
        table = self.query_one("#table", DataTable)
        # Find row with matching key
        for i, key in enumerate(table.rows.keys()):
            if int(key.value) == target:
                table.move_cursor(row=i)
                break
        self._update_subtitle()

    def action_clear_search(self) -> None:
        if self.filter_expr:
            self.filter_expr = None
            self.matches = []
            self._populate_table()
            self._update_subtitle()

    def action_first(self) -> None:
        table = self.query_one("#table", DataTable)
        table.move_cursor(row=0)

    def action_last(self) -> None:
        table = self.query_one("#table", DataTable)
        table.move_cursor(row=table.row_count - 1)

    def action_goto(self) -> None:
        def on_result(idx: Optional[int]) -> None:
            if idx is not None and 0 <= idx < len(self.records):
                table = self.query_one("#table", DataTable)
                # Try to find row in table
                found = False
                for i, key in enumerate(table.rows.keys()):
                    if int(key.value) == idx:
                        table.move_cursor(row=i)
                        found = True
                        break
                # If not in table (beyond 10K cap), open detail directly
                if not found:
                    record = self.records[idx]
                    self.push_screen(DetailScreen(record, idx, len(self.records)))
        self.push_screen(GotoDialog(), on_result)

    def action_mark(self) -> None:
        idx = self._current_index()
        if idx is not None:
            self.bookmarks.add(idx)
            self._populate_table()
            self._update_subtitle()

    def action_unmark(self) -> None:
        idx = self._current_index()
        if idx is not None:
            self.bookmarks.discard(idx)
            self._populate_table()
            self._update_subtitle()

    def action_next_mark(self) -> None:
        if not self.bookmarks:
            self.notify("No bookmarks")
            return
        idx = self._current_index() or 0
        marks = sorted(self.bookmarks)
        for m in marks:
            if m > idx:
                self.action_goto_index(m)
                return
        self.action_goto_index(marks[0])

    def action_goto_index(self, idx: int) -> None:
        table = self.query_one("#table", DataTable)
        for i, key in enumerate(table.rows.keys()):
            if int(key.value) == idx:
                table.move_cursor(row=i)
                break

    def action_help(self) -> None:
        self.push_screen(HelpScreen())


# =============================================================================
# Entry Point
# =============================================================================

def load_records_from_stdin() -> list:
    """Load NDJSON records from stdin."""
    records = []
    for line in sys.stdin:
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                records.append({"_error": str(e), "_line": line[:100]})
    return records


def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, display in Data Lens viewer."""
    if not sys.stdin.isatty():
        # Save stdin to temp file then redirect to tty
        temp_fd, temp_path = tempfile.mkstemp(suffix='.ndjson', prefix='jn-viewer-')
        with os.fdopen(temp_fd, 'w') as f:
            for line in sys.stdin:
                f.write(line)

        try:
            tty_fd = os.open('/dev/tty', os.O_RDONLY)
            os.dup2(tty_fd, 0)
            os.close(tty_fd)
            sys.stdin = open(0, 'r')
        except (OSError, FileNotFoundError):
            pass

        # Load from temp file
        records = []
        with open(temp_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        records.append({"_error": str(e)})
        os.unlink(temp_path)
    else:
        records = []

    app = DataLensApp(records)
    app.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Data Lens")
    parser.add_argument("--mode", default="write", choices=["write"])
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--start-at", type=int, default=0)
    args = parser.parse_args()
    writes()
