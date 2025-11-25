#!/usr/bin/env -S uv run --script
"""Data Lens - Table-first data exploration tool.

A professional data exploration TUI that displays data in table mode by default,
with tree view available for drilling down into individual records.
"""
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
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List, Optional, Set

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.coordinate import Coordinate
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Static, Tree
from textual.widgets.tree import TreeNode


# =============================================================================
# Models
# =============================================================================

@dataclass
class RecordStore:
    """Manages record list with disk-backed streaming support."""

    records: List[dict] = field(default_factory=list)
    loading: bool = False
    total_known: bool = False
    temp_file_path: Optional[str] = None
    _columns: Optional[List[str]] = None

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict:
        if 0 <= index < len(self.records):
            return self.records[index]
        raise IndexError(f"Record index {index} out of range")

    @property
    def columns(self) -> List[str]:
        """Get column names from first records."""
        if self._columns is None:
            if self.records:
                all_keys: Set[str] = set()
                for record in self.records[:100]:
                    if isinstance(record, dict):
                        all_keys.update(record.keys())
                self._columns = sorted(all_keys)
            else:
                self._columns = []
        return self._columns

    def invalidate_columns(self) -> None:
        self._columns = None

    def add_record(self, record: dict) -> int:
        self.records.append(record)
        return len(self.records) - 1

    def get_record(self, index: int) -> Optional[dict]:
        if 0 <= index < len(self.records):
            return self.records[index]
        return None

    def load_from_temp_file(self):
        """Generator that loads records from temp file."""
        if not self.temp_file_path:
            return

        self.loading = True
        self.total_known = False

        try:
            with open(self.temp_file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            idx = self.add_record(record)
                            if idx < 100:
                                self.invalidate_columns()
                            yield record
                        except json.JSONDecodeError as e:
                            error_record = {
                                "_error": True,
                                "type": "json_decode_error",
                                "message": str(e),
                            }
                            self.add_record(error_record)
                            yield error_record
        finally:
            self.loading = False
            self.total_known = True
            self.invalidate_columns()
            if self.temp_file_path:
                try:
                    os.unlink(self.temp_file_path)
                except OSError:
                    pass
                self.temp_file_path = None

    @classmethod
    def from_records(cls, records: List[dict]) -> "RecordStore":
        store = cls(records=list(records))
        store.total_known = True
        store.loading = False
        return store

    @classmethod
    def from_temp_file(cls, temp_file_path: str) -> "RecordStore":
        return cls(temp_file_path=temp_file_path)


@dataclass
class RecordNavigator:
    """Manages current position and bookmarks."""

    current_index: int = 0
    record_count: int = 0
    bookmarks: Set[int] = field(default_factory=set)

    def update_count(self, count: int) -> None:
        self.record_count = count
        if self.current_index >= count and count > 0:
            self.current_index = count - 1

    def next(self) -> bool:
        if self.current_index < self.record_count - 1:
            self.current_index += 1
            return True
        return False

    def previous(self) -> bool:
        if self.current_index > 0:
            self.current_index -= 1
            return True
        return False

    def jump_to(self, index: int) -> bool:
        if 0 <= index < self.record_count and index != self.current_index:
            self.current_index = index
            return True
        return False

    def jump_forward(self, count: int = 10) -> bool:
        new_index = min(self.current_index + count, self.record_count - 1)
        if new_index != self.current_index and new_index >= 0:
            self.current_index = new_index
            return True
        return False

    def jump_back(self, count: int = 10) -> bool:
        new_index = max(self.current_index - count, 0)
        if new_index != self.current_index:
            self.current_index = new_index
            return True
        return False

    def first(self) -> bool:
        if self.current_index != 0 and self.record_count > 0:
            self.current_index = 0
            return True
        return False

    def last(self) -> bool:
        if self.record_count > 0 and self.current_index != self.record_count - 1:
            self.current_index = self.record_count - 1
            return True
        return False

    def mark(self) -> None:
        if 0 <= self.current_index < self.record_count:
            self.bookmarks.add(self.current_index)

    def unmark(self) -> None:
        self.bookmarks.discard(self.current_index)

    def is_marked(self) -> bool:
        return self.current_index in self.bookmarks

    def next_bookmark(self) -> Optional[int]:
        if not self.bookmarks:
            return None
        sorted_marks = sorted(self.bookmarks)
        for mark in sorted_marks:
            if mark > self.current_index:
                return mark
        return sorted_marks[0]


# =============================================================================
# Search Controller
# =============================================================================

class SearchController:
    """Handles search and filtering operations in-memory."""

    def __init__(self):
        self.current_expr: Optional[str] = None
        self.matches: List[int] = []
        self.match_index: int = 0

    def search(self, records: List[dict], expr: str) -> List[int]:
        self.current_expr = expr
        self.matches = []
        self.match_index = 0

        python_filter = self._compile_python_filter(expr)
        if python_filter:
            for idx, record in enumerate(records):
                try:
                    if python_filter(record):
                        self.matches.append(idx)
                except Exception:
                    continue
        else:
            self.matches = self._search_with_jq(records, expr)

        return self.matches

    def clear(self) -> None:
        self.current_expr = None
        self.matches = []
        self.match_index = 0

    def next_match(self) -> Optional[int]:
        if not self.matches:
            return None
        self.match_index = (self.match_index + 1) % len(self.matches)
        return self.matches[self.match_index]

    def prev_match(self) -> Optional[int]:
        if not self.matches:
            return None
        self.match_index = (self.match_index - 1) % len(self.matches)
        return self.matches[self.match_index]

    def current_match(self) -> Optional[int]:
        if not self.matches:
            return None
        return self.matches[self.match_index]

    @property
    def match_count(self) -> int:
        return len(self.matches)

    @property
    def is_active(self) -> bool:
        return self.current_expr is not None

    def _compile_python_filter(self, expr: str) -> Optional[Callable[[dict], bool]]:
        import re

        expr = expr.strip()
        select_match = re.match(r'^select\s*\(\s*(.*)\s*\)\s*$', expr)
        if select_match:
            expr = select_match.group(1)

        # .field == "value"
        match = re.match(r'^\.(\w+)\s*==\s*"([^"]*)"$', expr)
        if match:
            field, value = match.groups()
            return lambda r, f=field, v=value: r.get(f) == v

        # .field == number
        match = re.match(r'^\.(\w+)\s*==\s*(-?\d+(?:\.\d+)?)$', expr)
        if match:
            field, value = match.groups()
            num_value = float(value) if '.' in value else int(value)
            return lambda r, f=field, v=num_value: r.get(f) == v

        # .field != "value"
        match = re.match(r'^\.(\w+)\s*!=\s*"([^"]*)"$', expr)
        if match:
            field, value = match.groups()
            return lambda r, f=field, v=value: r.get(f) != v

        # .field > number
        match = re.match(r'^\.(\w+)\s*>\s*(-?\d+(?:\.\d+)?)$', expr)
        if match:
            field, value = match.groups()
            num_value = float(value) if '.' in value else int(value)
            return lambda r, f=field, v=num_value: (r.get(f) is not None and r.get(f) > v)

        # .field < number
        match = re.match(r'^\.(\w+)\s*<\s*(-?\d+(?:\.\d+)?)$', expr)
        if match:
            field, value = match.groups()
            num_value = float(value) if '.' in value else int(value)
            return lambda r, f=field, v=num_value: (r.get(f) is not None and r.get(f) < v)

        # .field (truthy)
        match = re.match(r'^\.(\w+)$', expr)
        if match:
            field = match.group(1)
            return lambda r, f=field: bool(r.get(f))

        return None

    def _search_with_jq(self, records: List[dict], expr: str) -> List[int]:
        import subprocess
        matches = []
        try:
            jq_expr = f'select({expr})'
            proc = subprocess.Popen(
                ['jq', '-c', jq_expr],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                for idx, record in enumerate(records):
                    record_with_idx = {"__jn_idx__": idx, **record}
                    proc.stdin.write(json.dumps(record_with_idx) + "\n")
                proc.stdin.close()
            except BrokenPipeError:
                proc.wait()
                return matches

            for line in proc.stdout:
                line = line.strip()
                if line:
                    try:
                        match = json.loads(line)
                        if "__jn_idx__" in match:
                            matches.append(match["__jn_idx__"])
                    except json.JSONDecodeError:
                        continue
            proc.wait()
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            pass
        return matches


# =============================================================================
# Formatters
# =============================================================================

def style_value(value: Any) -> Text:
    """Apply syntax highlighting to primitive values."""
    if value is None:
        return Text("null", style="dim italic")
    elif isinstance(value, bool):
        return Text(str(value).lower(), style="bold yellow")
    elif isinstance(value, int):
        return Text(str(value), style="cyan")
    elif isinstance(value, float):
        return Text(f"{value}", style="cyan")
    elif isinstance(value, str):
        if len(value) > 100:
            display_value = value[:97] + "..."
        else:
            display_value = value
        return Text(f'"{display_value}"', style="green")
    else:
        return Text(str(value), style="white")


def format_cell_value(value: Any, max_width: int = 50) -> str:
    """Format a value for table cell display."""
    if value is None:
        return ""
    elif isinstance(value, bool):
        return str(value).lower()
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, str):
        clean = value.replace("\n", " ").replace("\r", "")
        if len(clean) > max_width:
            return clean[:max_width - 3] + "..."
        return clean
    elif isinstance(value, dict):
        return f"{{...}} ({len(value)} keys)"
    elif isinstance(value, list):
        return f"[...] ({len(value)} items)"
    else:
        result = str(value)
        if len(result) > max_width:
            return result[:max_width - 3] + "..."
        return result


# =============================================================================
# Views
# =============================================================================

class TableView(DataTable):
    """Table view for displaying multiple records at once."""

    DEFAULT_CSS = """
    TableView {
        height: 100%;
    }
    """

    def __init__(self, *, id: Optional[str] = None, classes: Optional[str] = None):
        super().__init__(id=id, classes=classes, cursor_type="row", zebra_stripes=True)
        self._records: List[dict] = []
        self._columns: List[str] = []
        self._visible_indices: List[int] = []
        self._bookmarks: Set[int] = set()
        self._search_matches: Set[int] = set()

    def set_data(
        self,
        records: List[dict],
        columns: Optional[List[str]] = None,
        visible_indices: Optional[List[int]] = None,
    ) -> None:
        self._records = records
        self._visible_indices = visible_indices if visible_indices is not None else list(range(len(records)))

        if columns is None:
            all_keys: Set[str] = set()
            for record in records[:100]:
                if isinstance(record, dict):
                    all_keys.update(record.keys())
            self._columns = sorted(all_keys)
        else:
            self._columns = list(columns)

        self._rebuild_table()

    def _rebuild_table(self) -> None:
        self.clear(columns=True)
        self.add_column("#", key="__row_num__")
        for col in self._columns:
            self.add_column(col, key=col)

        # Limit to first 10000 visible rows for performance
        MAX_VISIBLE_ROWS = 10000
        for display_idx, record_idx in enumerate(self._visible_indices[:MAX_VISIBLE_ROWS]):
            if 0 <= record_idx < len(self._records):
                record = self._records[record_idx]
                row = self._format_row(record, record_idx)
                self.add_row(*row, key=str(record_idx))

    def _format_row(self, record: dict, record_idx: int) -> List[str]:
        row = []
        prefix = ""
        if record_idx in self._bookmarks:
            prefix = "* "
        elif record_idx in self._search_matches:
            prefix = "> "
        row.append(f"{prefix}{record_idx + 1}")

        for col in self._columns:
            value = record.get(col) if isinstance(record, dict) else None
            row.append(format_cell_value(value))
        return row

    def set_bookmarks(self, bookmarks: Set[int]) -> None:
        self._bookmarks = bookmarks

    def set_search_matches(self, matches: Set[int]) -> None:
        self._search_matches = matches

    def filter_to_indices(self, indices: List[int]) -> None:
        self._visible_indices = indices
        self._rebuild_table()

    def get_selected_record_index(self) -> Optional[int]:
        if self.cursor_row is not None and 0 <= self.cursor_row < len(self._visible_indices):
            return self._visible_indices[self.cursor_row]
        return None

    def select_record_index(self, record_idx: int) -> bool:
        try:
            display_idx = self._visible_indices.index(record_idx)
            self.move_cursor(row=display_idx)
            return True
        except ValueError:
            return False

    @property
    def column_names(self) -> List[str]:
        return self._columns

    @property
    def visible_count(self) -> int:
        return len(self._visible_indices)


class TreeView(Tree):
    """Tree view for displaying a single record's structure."""

    DEFAULT_CSS = """
    TreeView {
        height: 100%;
        scrollbar-gutter: stable;
    }
    """

    def __init__(self, label: str = "Root", *, id: Optional[str] = None, classes: Optional[str] = None):
        super().__init__(label, id=id, classes=classes)
        self._current_record: Optional[dict] = None
        self._initial_depth: int = 2

    def set_record(self, record: dict, depth: int = 2) -> None:
        self._current_record = record
        self._initial_depth = depth
        self._build_tree(record, depth)

    def _build_tree(self, record: dict, depth: int) -> None:
        self.clear()
        self.root.expand()
        self._add_json_node(self.root, "Record", record, 0, depth)

    def _add_json_node(self, parent: TreeNode, label: str, data: Any, current_depth: int, max_depth: int) -> None:
        if isinstance(data, dict):
            if data:
                node_label = f"{label} (object, {len(data)} keys)" if label != "Record" else label
                node = parent.add(node_label, expand=current_depth < max_depth)
                for key, value in data.items():
                    self._add_json_node(node, str(key), value, current_depth + 1, max_depth)
            else:
                parent.add_leaf(f"{label}: {{}}")
        elif isinstance(data, list):
            if data:
                node_label = f"{label} (array, {len(data)} items)"
                node = parent.add(node_label, expand=current_depth < max_depth)
                for i, item in enumerate(data):
                    self._add_json_node(node, f"[{i}]", item, current_depth + 1, max_depth)
            else:
                parent.add_leaf(f"{label}: []")
        else:
            styled_value = style_value(data)
            parent.add_leaf(f"{label}: {styled_value}")

    def toggle_current_node(self) -> None:
        if self.cursor_node:
            self.cursor_node.toggle()

    def expand_all_nodes(self) -> None:
        self.root.expand_all()

    def collapse_all_nodes(self) -> None:
        for child in self.root.children:
            child.collapse_all()

    @property
    def current_record(self) -> Optional[dict]:
        return self._current_record


# =============================================================================
# Screens/Dialogs
# =============================================================================

class GotoDialog(ModalScreen[Optional[int]]):
    """Modal dialog for jumping to a specific record."""

    CSS = """
    GotoDialog { align: center middle; }
    #goto-container { width: 50; height: 7; border: thick $background 80%; background: $surface; }
    #goto-title { dock: top; width: 100%; content-align: center middle; text-style: bold; }
    #goto-input { margin: 1 2; }
    """

    def compose(self) -> ComposeResult:
        with Container(id="goto-container"):
            yield Static("Go to Record Number", id="goto-title")
            yield Input(placeholder="Enter record number (1-based)", id="goto-input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            record_num = int(event.value)
            if record_num > 0:
                self.dismiss(record_num - 1)
            else:
                self.dismiss(None)
        except ValueError:
            self.dismiss(None)

    def key_escape(self) -> None:
        self.dismiss(None)


class SearchDialog(ModalScreen[Optional[str]]):
    """Modal dialog for searching records."""

    CSS = """
    SearchDialog { align: center middle; }
    #search-container { width: 70; height: 9; border: thick $background 80%; background: $surface; }
    #search-title { dock: top; width: 100%; content-align: center middle; text-style: bold; }
    #search-input { margin: 1 2; }
    #search-help { margin: 0 2; color: $text-muted; }
    """

    def compose(self) -> ComposeResult:
        with Container(id="search-container"):
            yield Static("Search Records", id="search-title")
            yield Input(placeholder='Enter jq expression (e.g., .age > 30, .name == "Alice")', id="search-input")
            yield Static("Tip: Use . prefix for fields. Press Enter to search, Esc to cancel.", id="search-help")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        self.dismiss(query if query else None)

    def key_escape(self) -> None:
        self.dismiss(None)


class FindByFieldDialog(ModalScreen[Optional[str]]):
    """Modal dialog for finding by field."""

    CSS = """
    FindByFieldDialog { align: center middle; }
    #find-container { width: 70; height: 11; border: thick $background 80%; background: $surface; }
    #find-title { dock: top; width: 100%; content-align: center middle; text-style: bold; }
    #find-input { margin: 1 2; }
    #find-help { margin: 0 2; color: $text-muted; }
    #find-examples { margin: 0 2; color: $text-muted; }
    """

    def compose(self) -> ComposeResult:
        with Container(id="find-container"):
            yield Static("Find by Field", id="find-title")
            yield Input(placeholder='field = value  (e.g., age > 30, name = "Alice")', id="find-input")
            yield Static("Operators: = (equals), != (not equals), > < >= <= (comparison)", id="find-help")
            yield Static('Examples: city = "NYC", age > 30, Symbol = "BRAF"', id="find-examples")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if query:
            self.dismiss(self._convert_to_jq(query))
        else:
            self.dismiss(None)

    def _convert_to_jq(self, query: str) -> str:
        if " " not in query and "=" not in query and ">" not in query and "<" not in query:
            return f".{query}"

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
                    if value.startswith('"') and value.endswith('"'):
                        pass
                    elif value.lower() not in ("true", "false", "null") and not value.replace(".", "").replace("-", "").isdigit():
                        value = f'"{value}"'
                    return f"{field} {op} {value}"
        return query

    def key_escape(self) -> None:
        self.dismiss(None)


class DetailScreen(ModalScreen[None]):
    """Modal screen showing a single record in detail."""

    CSS = """
    DetailScreen { align: center middle; }
    #detail-container { width: 90%; height: 90%; border: thick $background 80%; background: $surface; }
    #detail-header { dock: top; width: 100%; height: 3; content-align: center middle; text-style: bold; background: $primary-background; padding: 1; }
    #detail-tree { height: 100%; }
    #detail-footer { dock: bottom; width: 100%; height: 1; background: $primary-background; }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
        Binding("y", "copy_record", "Copy"),
        Binding("space", "toggle_node", "Toggle"),
        Binding("e", "expand_all", "Expand"),
        Binding("c", "collapse_all", "Collapse"),
    ]

    def __init__(self, record: dict, record_index: int, total_records: int, *, id: Optional[str] = None):
        super().__init__(id=id)
        self._record = record
        self._record_index = record_index
        self._total_records = total_records

    def compose(self) -> ComposeResult:
        with Container(id="detail-container"):
            yield Static(f"Record {self._record_index + 1} of {self._total_records}", id="detail-header")
            yield TreeView("Root", id="detail-tree")
            yield Static("Esc:Close  y:Copy  Space:Toggle  e:Expand  c:Collapse", id="detail-footer")

    def on_mount(self) -> None:
        tree = self.query_one("#detail-tree", TreeView)
        tree.set_record(self._record, depth=3)
        tree.focus()

    def action_close(self) -> None:
        self.dismiss(None)

    def action_copy_record(self) -> None:
        try:
            import pyperclip
            pyperclip.copy(json.dumps(self._record, indent=2))
            self.notify("Record copied!")
        except ImportError:
            self.notify("pyperclip not installed", severity="error")
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def action_toggle_node(self) -> None:
        self.query_one("#detail-tree", TreeView).toggle_current_node()

    def action_expand_all(self) -> None:
        self.query_one("#detail-tree", TreeView).expand_all_nodes()

    def action_collapse_all(self) -> None:
        self.query_one("#detail-tree", TreeView).collapse_all_nodes()


class HelpScreen(ModalScreen):
    """Help screen showing keyboard shortcuts."""

    CSS = """
    HelpScreen { align: center middle; }
    #help-container { width: 80; height: 35; border: thick $background 80%; background: $surface; }
    #help-title { dock: top; width: 100%; content-align: center middle; text-style: bold; background: $primary; padding: 1; }
    #help-content { padding: 1 2; height: 100%; }
    """

    HELP_TEXT = """
[bold cyan]View Modes[/]
  t              Toggle Table/Tree view
  Enter          Drill down (from Table)
  Esc            Close modal / Clear search

[bold cyan]Navigation (Table)[/]
  j/k or ↓/↑     Move down/up
  g / G          First / Last record
  Ctrl+D/U       Page down / Page up
  #              Go to record number

[bold cyan]Navigation (Tree)[/]
  n / p          Next / Previous record
  Space          Toggle expand/collapse
  e / c          Expand / Collapse all

[bold cyan]Search[/]
  /              Search (jq expression)
  f              Find by field
  x              Clear search

[bold cyan]Bookmarks[/]
  m              Mark current record
  u              Unmark current record
  '              Jump to next bookmark

[bold cyan]Actions[/]
  y              Copy record as JSON
  w              Write record to file
  s              Toggle stats panel

[bold cyan]Other[/]
  q              Quit
  ?              This help

[dim]Press Escape or ? to close[/]
"""

    def compose(self) -> ComposeResult:
        with Container(id="help-container"):
            yield Static("Keyboard Shortcuts", id="help-title")
            with VerticalScroll(id="help-content"):
                yield Static(self.HELP_TEXT)

    def key_escape(self) -> None:
        self.app.pop_screen()

    def key_question_mark(self) -> None:
        self.app.pop_screen()


# =============================================================================
# Main Application
# =============================================================================

class ViewMode(Enum):
    TABLE = "table"
    TREE = "tree"


class DataLensApp(App):
    """Data Lens - Table-first data exploration tool."""

    CSS = """
    Screen { background: $surface; }
    #main-container { height: 100%; }
    #view-container { height: 100%; }
    #table-view { height: 100%; }
    #tree-view { height: 100%; }
    .hidden { display: none; }
    """

    BINDINGS = [
        Binding("t", "toggle_view_mode", "Toggle View", show=True),
        Binding("enter", "drill_down", "Drill Down", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "first_record", "First", show=False),
        Binding("home", "first_record", "First", show=False),
        Binding("G", "last_record", "Last", show=False),
        Binding("end", "last_record", "Last", show=False),
        Binding("ctrl+d", "page_down", "+10", show=True),
        Binding("ctrl+u", "page_up", "-10", show=True),
        Binding("number_sign", "goto_record", "Go to", show=True, key_display="#"),
        Binding("n", "next_record", "Next", show=True),
        Binding("p", "prev_record", "Prev", show=True),
        Binding("space", "toggle_node", "Toggle", show=False),
        Binding("e", "expand_all", "Expand", show=False),
        Binding("c", "collapse_all", "Collapse", show=False),
        Binding("slash", "search", "Search", show=True),
        Binding("f", "find_by_field", "Find", show=True),
        Binding("N", "prev_match", "Prev Match", show=False),
        Binding("x", "clear_search", "Clear", show=False),
        Binding("escape", "escape_action", "Escape", show=False),
        Binding("m", "mark_record", "Mark", show=False),
        Binding("u", "unmark_record", "Unmark", show=False),
        Binding("apostrophe", "jump_to_mark", "Marks", show=False),
        Binding("y", "copy_record", "Copy", show=False),
        Binding("w", "write_record", "Write", show=False),
        Binding("q", "quit", "Quit", show=True),
        Binding("question_mark", "help", "Help", show=True),
        Binding("r", "refresh", "Refresh", show=False),
    ]

    view_mode: reactive[ViewMode] = reactive(ViewMode.TABLE)

    def __init__(self, store: Optional[RecordStore] = None, config: Optional[dict] = None):
        super().__init__()
        # Use explicit None check - RecordStore with empty records is falsy due to __len__
        self.store = store if store is not None else RecordStore()
        self.config = config if config is not None else {}
        self.navigator = RecordNavigator()
        self.search = SearchController()
        self._loading_complete = False
        self._initial_depth = self.config.get("depth", 2)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            with Container(id="view-container"):
                yield TableView(id="table-view")
                yield TreeView("Root", id="tree-view", classes="hidden")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Data Lens"
        if self.store.temp_file_path:
            self.sub_title = "Loading..."
            self.run_worker(self._load_records_streaming, thread=True, exclusive=True)
        else:
            self._loading_complete = True
            self.navigator.update_count(len(self.store))
            self._refresh_view()

    def _load_records_streaming(self) -> None:
        first_displayed = False
        for record in self.store.load_from_temp_file():
            self.navigator.update_count(len(self.store))
            if not first_displayed and len(self.store) > 0:
                first_displayed = True
                self.call_from_thread(self._refresh_view)
            elif len(self.store) % 1000 == 0:
                self.call_from_thread(self._update_subtitle)

        self._loading_complete = True
        self.call_from_thread(self._on_loading_complete)

    def _on_loading_complete(self) -> None:
        self.navigator.update_count(len(self.store))
        self._refresh_view()

    def _refresh_view(self) -> None:
        self._update_subtitle()
        if self.view_mode == ViewMode.TABLE:
            self._refresh_table()
        else:
            self._refresh_tree()

    def _refresh_table(self) -> None:
        table = self.query_one("#table-view", TableView)
        if self.search.is_active:
            table.set_data(self.store.records, columns=self.store.columns, visible_indices=self.search.matches)
        else:
            table.set_data(self.store.records, columns=self.store.columns)
        table.set_bookmarks(self.navigator.bookmarks)
        table.set_search_matches(set(self.search.matches))
        if self.navigator.record_count > 0:
            table.select_record_index(self.navigator.current_index)

    def _refresh_tree(self) -> None:
        tree = self.query_one("#tree-view", TreeView)
        record = self.store.get_record(self.navigator.current_index)
        if record:
            tree.set_record(record, depth=self._initial_depth)

    def _update_subtitle(self) -> None:
        parts = []
        if self._loading_complete:
            pos = self.navigator.current_index + 1
            total = self.navigator.record_count
            parts.append(f"Record {pos} of {total}")
        else:
            parts.append(f"Loading... ({len(self.store):,} records)")

        if self.view_mode == ViewMode.TABLE and self.search.is_active:
            parts.append(f"Showing {self.search.match_count} matches")

        if self.navigator.is_marked():
            parts.append("[marked]")

        if self.search.is_active:
            if self.search.match_count > 0:
                parts.append(f"Match {self.search.match_index + 1}/{self.search.match_count}")
            else:
                parts.append("No matches")

        if self.navigator.bookmarks:
            parts.append(f"{len(self.navigator.bookmarks)} bookmark(s)")

        self.sub_title = " | ".join(parts)

    def watch_view_mode(self, mode: ViewMode) -> None:
        table = self.query_one("#table-view", TableView)
        tree = self.query_one("#tree-view", TreeView)
        if mode == ViewMode.TABLE:
            table.remove_class("hidden")
            tree.add_class("hidden")
            table.focus()
            self._refresh_table()
        else:
            table.add_class("hidden")
            tree.remove_class("hidden")
            tree.focus()
            self._refresh_tree()
        self._update_subtitle()

    def action_toggle_view_mode(self) -> None:
        if self.view_mode == ViewMode.TABLE:
            table = self.query_one("#table-view", TableView)
            idx = table.get_selected_record_index()
            if idx is not None:
                self.navigator.current_index = idx
            self.view_mode = ViewMode.TREE
        else:
            self.view_mode = ViewMode.TABLE

    def action_drill_down(self) -> None:
        if self.view_mode != ViewMode.TABLE:
            return
        table = self.query_one("#table-view", TableView)
        idx = table.get_selected_record_index()
        if idx is not None:
            record = self.store.get_record(idx)
            if record:
                self.push_screen(DetailScreen(record, idx, self.navigator.record_count))

    def action_cursor_down(self) -> None:
        if self.view_mode == ViewMode.TABLE:
            table = self.query_one("#table-view", TableView)
            table.action_cursor_down()
            idx = table.get_selected_record_index()
            if idx is not None:
                self.navigator.current_index = idx
                self._update_subtitle()

    def action_cursor_up(self) -> None:
        if self.view_mode == ViewMode.TABLE:
            table = self.query_one("#table-view", TableView)
            table.action_cursor_up()
            idx = table.get_selected_record_index()
            if idx is not None:
                self.navigator.current_index = idx
                self._update_subtitle()

    def action_next_record(self) -> None:
        if self.search.is_active and self.search.match_count > 1:
            idx = self.search.next_match()
            if idx is not None:
                self.navigator.jump_to(idx)
        else:
            self.navigator.next()
        self._refresh_view()

    def action_prev_record(self) -> None:
        if self.search.is_active and self.search.match_count > 1:
            idx = self.search.prev_match()
            if idx is not None:
                self.navigator.jump_to(idx)
        else:
            self.navigator.previous()
        self._refresh_view()

    def action_first_record(self) -> None:
        self.navigator.first()
        self._refresh_view()

    def action_last_record(self) -> None:
        self.navigator.last()
        self._refresh_view()

    def action_page_down(self) -> None:
        if self.view_mode == ViewMode.TABLE:
            table = self.query_one("#table-view", TableView)
            table.action_page_down()
            idx = table.get_selected_record_index()
            if idx is not None:
                self.navigator.current_index = idx
                self._update_subtitle()
        else:
            self.navigator.jump_forward(10)
            self._refresh_view()

    def action_page_up(self) -> None:
        if self.view_mode == ViewMode.TABLE:
            table = self.query_one("#table-view", TableView)
            table.action_page_up()
            idx = table.get_selected_record_index()
            if idx is not None:
                self.navigator.current_index = idx
                self._update_subtitle()
        else:
            self.navigator.jump_back(10)
            self._refresh_view()

    def action_goto_record(self) -> None:
        def handle_goto(record_index: Optional[int]) -> None:
            if record_index is not None and self.navigator.jump_to(record_index):
                self._refresh_view()
        self.push_screen(GotoDialog(), handle_goto)

    def action_toggle_node(self) -> None:
        if self.view_mode == ViewMode.TREE:
            self.query_one("#tree-view", TreeView).toggle_current_node()

    def action_expand_all(self) -> None:
        if self.view_mode == ViewMode.TREE:
            self.query_one("#tree-view", TreeView).expand_all_nodes()

    def action_collapse_all(self) -> None:
        if self.view_mode == ViewMode.TREE:
            self.query_one("#tree-view", TreeView).collapse_all_nodes()

    def action_search(self) -> None:
        def handle_search(expr: Optional[str]) -> None:
            if expr:
                self.search.search(self.store.records, expr)
                if self.search.match_count > 0:
                    idx = self.search.current_match()
                    if idx is not None:
                        self.navigator.jump_to(idx)
                self._refresh_view()
        self.push_screen(SearchDialog(), handle_search)

    def action_find_by_field(self) -> None:
        def handle_find(expr: Optional[str]) -> None:
            if expr:
                self.search.search(self.store.records, expr)
                if self.search.match_count > 0:
                    idx = self.search.current_match()
                    if idx is not None:
                        self.navigator.jump_to(idx)
                self._refresh_view()
        self.push_screen(FindByFieldDialog(), handle_find)

    def action_prev_match(self) -> None:
        if self.search.is_active:
            idx = self.search.prev_match()
            if idx is not None:
                self.navigator.jump_to(idx)
                self._refresh_view()

    def action_clear_search(self) -> None:
        self.search.clear()
        self._refresh_view()

    def action_escape_action(self) -> None:
        if self.search.is_active:
            self.search.clear()
            self._refresh_view()

    def action_mark_record(self) -> None:
        self.navigator.mark()
        self._update_subtitle()
        if self.view_mode == ViewMode.TABLE:
            self.query_one("#table-view", TableView).set_bookmarks(self.navigator.bookmarks)
            self._refresh_table()

    def action_unmark_record(self) -> None:
        self.navigator.unmark()
        self._update_subtitle()
        if self.view_mode == ViewMode.TABLE:
            self.query_one("#table-view", TableView).set_bookmarks(self.navigator.bookmarks)
            self._refresh_table()

    def action_jump_to_mark(self) -> None:
        next_mark = self.navigator.next_bookmark()
        if next_mark is not None:
            self.navigator.jump_to(next_mark)
            self._refresh_view()
        elif not self.navigator.bookmarks:
            self.notify("No bookmarks. Press 'm' to mark.")

    def action_copy_record(self) -> None:
        record = self.store.get_record(self.navigator.current_index)
        if record:
            try:
                import pyperclip
                pyperclip.copy(json.dumps(record, indent=2))
                self.notify("Record copied!")
            except ImportError:
                self.notify("pyperclip not installed", severity="error")
            except Exception as e:
                self.notify(f"Error: {e}", severity="error")

    def action_write_record(self) -> None:
        record = self.store.get_record(self.navigator.current_index)
        if record:
            try:
                filename = f"record_{self.navigator.current_index + 1}.json"
                with open(filename, "w") as f:
                    json.dump(record, f, indent=2)
                self.notify(f"Saved to {filename}")
            except Exception as e:
                self.notify(f"Error: {e}", severity="error")

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_refresh(self) -> None:
        self._refresh_view()

    def on_data_table_row_selected(self, event) -> None:
        table = self.query_one("#table-view", TableView)
        idx = table.get_selected_record_index()
        if idx is not None:
            self.navigator.current_index = idx
            self._update_subtitle()


# =============================================================================
# Entry Point
# =============================================================================

def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, display in Data Lens viewer."""
    config = config or {}

    stdin_is_tty = sys.stdin.isatty()

    if not stdin_is_tty:
        temp_fd, temp_path = tempfile.mkstemp(suffix='.ndjson', prefix='jn-viewer-')
        with os.fdopen(temp_fd, 'w') as temp_file:
            for line in sys.stdin:
                temp_file.write(line)

        try:
            tty_fd = os.open('/dev/tty', os.O_RDONLY)
            os.dup2(tty_fd, 0)
            os.close(tty_fd)
            sys.stdin = open(0, 'r')
        except (OSError, FileNotFoundError):
            pass

        store = RecordStore.from_temp_file(temp_path)
        app = DataLensApp(store=store, config=config)
        app.run()
    else:
        import signal
        import time

        records = []
        timeout = 5.0
        start_time = time.time()

        def timeout_handler(signum, frame):
            raise TimeoutError()

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout))

        try:
            for line in sys.stdin:
                signal.alarm(int(timeout))
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
                if not records and time.time() - start_time > timeout:
                    break
        except TimeoutError:
            pass
        finally:
            signal.alarm(0)

        store = RecordStore.from_records(records)
        app = DataLensApp(store=store, config=config)
        app.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Data Lens - Table-first data exploration tool")
    parser.add_argument("--mode", default="write", choices=["write"])
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--start-at", type=int, default=0)
    args = parser.parse_args()
    config = {"depth": args.depth, "start_at": args.start_at}
    writes(config)
