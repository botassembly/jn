#!/usr/bin/env -S uv run --script
"""Single-record JSON viewer with tree navigation."""
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
import sys
from typing import Any, Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Static, Tree
from textual.widgets.tree import TreeNode


class RecordNavigator:
    """Manages record list and current position."""

    def __init__(self):
        self.records: list[dict] = []
        self.current_index: int = 0
        self.total_known: bool = False
        self.loading: bool = False

    def next(self) -> bool:
        """Move to next record. Returns True if moved."""
        if self.current_index < len(self.records) - 1:
            self.current_index += 1
            return True
        return False

    def previous(self) -> bool:
        """Move to previous record. Returns True if moved."""
        if self.current_index > 0:
            self.current_index -= 1
            return True
        return False

    def jump_to(self, index: int) -> bool:
        """Jump to specific record by index. Returns True if valid."""
        if 0 <= index < len(self.records):
            self.current_index = index
            return True
        return False

    def jump_forward(self, count: int = 10) -> bool:
        """Jump forward by count records."""
        new_index = min(self.current_index + count, len(self.records) - 1)
        if new_index != self.current_index:
            self.current_index = new_index
            return True
        return False

    def jump_back(self, count: int = 10) -> bool:
        """Jump back by count records."""
        new_index = max(self.current_index - count, 0)
        if new_index != self.current_index:
            self.current_index = new_index
            return True
        return False

    def first(self) -> bool:
        """Jump to first record. Returns True if moved."""
        if self.current_index != 0 and self.records:
            self.current_index = 0
            return True
        return False

    def last(self) -> bool:
        """Jump to last record. Returns True if moved."""
        if self.records and self.current_index != len(self.records) - 1:
            self.current_index = len(self.records) - 1
            return True
        return False

    def current_record(self) -> Optional[dict]:
        """Get currently displayed record."""
        if self.records and 0 <= self.current_index < len(self.records):
            return self.records[self.current_index]
        return None

    def add_record(self, record: dict) -> None:
        """Add a record to the list."""
        self.records.append(record)

    def position_info(self) -> str:
        """Get position info string for display."""
        if not self.records:
            return "No records"

        pos = self.current_index + 1  # 1-based for display
        if self.total_known:
            total = len(self.records)
            return f"Record {pos} of {total}"
        else:
            return f"Record {pos} (streaming...)"


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
        # Truncate long strings
        if len(value) > 100:
            display_value = value[:97] + "..."
        else:
            display_value = value
        return Text(f'"{display_value}"', style="green")
    else:
        return Text(str(value), style="white")


def add_json_node(
    parent: TreeNode, label: str, data: Any, current_depth: int, max_depth: int
) -> None:
    """Recursively add JSON data to tree."""
    if isinstance(data, dict):
        # Object node
        if data:
            node_label = f"{label} (object, {len(data)} keys)" if label != "Record" else label
            node = parent.add(node_label, expand=current_depth < max_depth)

            for key, value in data.items():
                add_json_node(node, str(key), value, current_depth + 1, max_depth)
        else:
            parent.add_leaf(f"{label}: {{}}")

    elif isinstance(data, list):
        # Array node
        if data:
            node_label = f"{label} (array, {len(data)} items)"
            node = parent.add(node_label, expand=current_depth < max_depth)

            for i, item in enumerate(data):
                add_json_node(node, f"[{i}]", item, current_depth + 1, max_depth)
        else:
            parent.add_leaf(f"{label}: []")

    else:
        # Leaf node (primitive)
        styled_value = style_value(data)
        parent.add_leaf(f"{label}: {styled_value}")


def build_tree_for_record(tree: Tree, record: dict, depth: int = 2) -> None:
    """Build a tree widget for a single record.

    Args:
        tree: Textual Tree widget
        record: The JSON record to display
        depth: Initial expansion depth (default: 2)
    """
    tree.clear()
    root = tree.root
    root.expand()

    # Build tree from record
    add_json_node(root, "Record", record, current_depth=0, max_depth=depth)


class GotoDialog(ModalScreen[Optional[int]]):
    """Modal dialog for jumping to a specific record."""

    CSS = """
    GotoDialog {
        align: center middle;
    }

    #goto-container {
        width: 50;
        height: 7;
        border: thick $background 80%;
        background: $surface;
    }

    #goto-title {
        dock: top;
        width: 100%;
        content-align: center middle;
        text-style: bold;
    }

    #goto-input {
        margin: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="goto-container"):
            yield Static("Go to Record Number", id="goto-title")
            yield Input(placeholder="Enter record number (1-based)", id="goto-input")

    def on_mount(self) -> None:
        """Focus input when dialog opens."""
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        try:
            # User enters 1-based, convert to 0-based
            record_num = int(event.value)
            if record_num > 0:
                self.dismiss(record_num - 1)
            else:
                self.dismiss(None)
        except ValueError:
            self.dismiss(None)

    def key_escape(self) -> None:
        """Handle Escape key."""
        self.dismiss(None)


class SearchDialog(ModalScreen[Optional[str]]):
    """Modal dialog for searching records with jq expression."""

    CSS = """
    SearchDialog {
        align: center middle;
    }

    #search-container {
        width: 70;
        height: 9;
        border: thick $background 80%;
        background: $surface;
    }

    #search-title {
        dock: top;
        width: 100%;
        content-align: center middle;
        text-style: bold;
    }

    #search-input {
        margin: 1 2;
    }

    #search-help {
        margin: 0 2;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="search-container"):
            yield Static("Search Records", id="search-title")
            yield Input(
                placeholder="Enter jq expression (e.g., .age > 30, .name == \"Alice\")",
                id="search-input",
            )
            yield Static(
                "Tip: Use . prefix for fields. Press Enter to search, Esc to cancel.",
                id="search-help",
            )

    def on_mount(self) -> None:
        """Focus input when dialog opens."""
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        query = event.value.strip()
        if query:
            self.dismiss(query)
        else:
            self.dismiss(None)

    def key_escape(self) -> None:
        """Handle Escape key."""
        self.dismiss(None)


class HelpScreen(ModalScreen):
    """Modal screen showing keyboard shortcuts."""

    CSS = """
    HelpScreen {
        align: center middle;
    }

    #help-container {
        width: 80;
        height: 30;
        border: thick $background 80%;
        background: $surface;
    }

    #help-title {
        dock: top;
        width: 100%;
        content-align: center middle;
        text-style: bold;
        background: $primary;
    }

    #help-content {
        padding: 1 2;
        height: 100%;
    }
    """

    HELP_TEXT = """
[bold cyan]Record Navigation[/]
  n              Next record
  p              Previous record
  g / Home       First record
  G / End        Last record
  Ctrl+D         Jump forward 10 records
  Ctrl+U         Jump back 10 records
  :              Go to specific record

[bold cyan]Search[/]
  /              Search with jq expression
  n              Next match (when searching)
  N              Previous match (when searching)
  Esc            Clear search

[bold cyan]Tree Navigation[/]
  ↑ / k          Move cursor up
  ↓ / j          Move cursor down
  Space          Toggle expand/collapse
  → / l          Expand node
  ← / h          Collapse node
  e              Expand all nodes
  c              Collapse all nodes

[bold cyan]Other[/]
  q              Quit viewer
  ?              Show this help
  r              Refresh display

[dim]Press Escape or ? to close this help[/]
"""

    def compose(self) -> ComposeResult:
        with Container(id="help-container"):
            yield Static("Keyboard Shortcuts", id="help-title")
            with VerticalScroll(id="help-content"):
                yield Static(self.HELP_TEXT)

    def key_escape(self) -> None:
        """Handle Escape key."""
        self.app.pop_screen()

    def key_question_mark(self) -> None:
        """Handle ? key."""
        self.app.pop_screen()


class JSONViewerApp(App):
    """Single-record JSON viewer application."""

    CSS = """
    Screen {
        background: $surface;
    }

    Tree {
        height: 100%;
        scrollbar-gutter: stable;
    }
    """

    BINDINGS = [
        # Record navigation
        Binding("n", "next_record", "Next", show=True),
        Binding("p", "prev_record", "Prev", show=True),
        Binding("g", "first_record", "First", show=False),
        Binding("home", "first_record", "First", show=False),
        Binding("G", "last_record", "Last", show=False),
        Binding("end", "last_record", "Last", show=False),
        Binding("ctrl+d", "jump_forward", "+10", show=True),
        Binding("ctrl+u", "jump_back", "-10", show=True),
        Binding("colon", "goto_record", "Go to", show=True),
        # Search
        Binding("slash", "search", "Search", show=True),
        Binding("N", "prev_match", "Prev Match", show=False),
        Binding("escape", "clear_search", "Clear Search", show=False),
        # Tree navigation
        Binding("space", "toggle_node", "Toggle", show=True),
        Binding("e", "expand_all", "Expand All", show=False),
        Binding("c", "collapse_all", "Collapse All", show=False),
        # Other
        Binding("q", "quit", "Quit", show=True),
        Binding("question_mark", "help", "Help", show=True),
        Binding("r", "refresh", "Refresh", show=False),
    ]

    def __init__(self, config: Optional[dict] = None, records: Optional[list] = None, streaming: bool = False):
        super().__init__()
        self.config = config or {}
        self.navigator = RecordNavigator()
        self.initial_depth = self.config.get("depth", 2)
        self.start_at = self.config.get("start_at", 0)
        self.streaming = streaming
        self.loading_complete = False

        # Search state
        self.search_expr = None  # Current jq search expression
        self.search_matches = []  # List of matching record indices
        self.search_match_index = 0  # Current position in matches

        # Pre-load records if provided
        if records:
            for record in records:
                self.navigator.add_record(record)
            if not streaming:
                self.navigator.total_known = True
                self.loading_complete = True

    def compose(self) -> ComposeResult:
        """Build UI layout."""
        yield Header()
        yield Tree("Root", id="tree-view")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize viewer when app starts."""
        self.title = "JSON Viewer"

        # If streaming mode, start background worker to load records
        if self.streaming:
            self.sub_title = "Loading..."
            self.load_worker = self.run_worker(self.load_records_streaming, thread=True, exclusive=True)
        else:
            # Jump to start_at record if configured
            if self.start_at > 0 and self.navigator.records:
                self.navigator.jump_to(self.start_at)
            elif self.navigator.records:
                self.navigator.current_index = 0

            # Display the current record or show "No records" message
            if self.navigator.records:
                self.display_current_record()
            else:
                self.sub_title = "No records to display"

    def load_records_streaming(self) -> None:
        """Load records from stdin in background thread (streaming mode)."""
        import time

        self.navigator.loading = True
        timeout = 5.0
        start_time = time.time()

        try:
            for line in sys.stdin:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        self.navigator.add_record(record)

                        # Display first record immediately
                        if len(self.navigator.records) == 1:
                            self.navigator.current_index = min(
                                self.start_at, len(self.navigator.records) - 1
                            )
                            self.call_from_thread(self.display_current_record)
                        else:
                            # Update subtitle to show record count
                            self.call_from_thread(self.update_subtitle)

                    except json.JSONDecodeError as e:
                        self.navigator.add_record(
                            {
                                "_error": True,
                                "type": "json_decode_error",
                                "message": str(e),
                                "line": line[:100],
                            }
                        )

                # Timeout check for first record
                if not self.navigator.records and time.time() - start_time > timeout:
                    break

        except Exception as e:
            self.navigator.add_record(
                {
                    "_error": True,
                    "type": "load_error",
                    "message": str(e),
                }
            )
        finally:
            self.navigator.loading = False
            self.navigator.total_known = True
            self.loading_complete = True
            self.call_from_thread(self.on_loading_complete)

    def on_loading_complete(self) -> None:
        """Called when streaming load completes."""
        if not self.navigator.records:
            self.sub_title = "No records to display"
        else:
            self.update_subtitle()
            if not self.query_one("#tree-view", Tree).root.children:
                # If tree is empty, display first record
                self.display_current_record()

    def display_current_record(self) -> None:
        """Display the current record in the tree."""
        record = self.navigator.current_record()
        if record:
            tree = self.query_one("#tree-view", Tree)
            build_tree_for_record(tree, record, depth=self.initial_depth)
            self.update_subtitle()

    def update_subtitle(self) -> None:
        """Update subtitle with current position and search status."""
        base_info = self.navigator.position_info()

        # Add search status if active
        if self.search_expr:
            if self.search_matches:
                match_num = self.search_match_index + 1
                total_matches = len(self.search_matches)
                search_info = f" | Search: {match_num}/{total_matches} matches for '{self.search_expr}'"
            else:
                search_info = f" | Search: No matches for '{self.search_expr}'"
            self.sub_title = base_info + search_info
        else:
            self.sub_title = base_info

    # Record Navigation Actions
    def action_next_record(self) -> None:
        """Handle 'n' key - next record or next search match."""
        # If searching, go to next match
        if self.search_matches:
            # Move to next match (wrap around)
            self.search_match_index = (self.search_match_index + 1) % len(self.search_matches)
            target_index = self.search_matches[self.search_match_index]

            if self.navigator.jump_to(target_index):
                self.display_current_record()
        # Otherwise, normal next record
        elif self.navigator.next():
            self.display_current_record()

    def action_prev_record(self) -> None:
        """Handle 'p' key - previous record."""
        if self.navigator.previous():
            self.display_current_record()

    def action_first_record(self) -> None:
        """Handle 'g' key - first record."""
        if self.navigator.first():
            self.display_current_record()

    def action_last_record(self) -> None:
        """Handle 'G' key - last record."""
        if self.navigator.last():
            self.display_current_record()

    def action_jump_forward(self) -> None:
        """Handle Ctrl+D - jump forward 10."""
        if self.navigator.jump_forward(10):
            self.display_current_record()

    def action_jump_back(self) -> None:
        """Handle Ctrl+U - jump back 10."""
        if self.navigator.jump_back(10):
            self.display_current_record()

    def action_goto_record(self) -> None:
        """Handle ':' key - prompt for record number."""

        def handle_goto(record_index: Optional[int]) -> None:
            if record_index is not None and self.navigator.jump_to(record_index):
                self.display_current_record()

        self.push_screen(GotoDialog(), handle_goto)

    # Search Actions
    def action_search(self) -> None:
        """Handle '/' key - open search dialog."""

        def handle_search(expr: Optional[str]) -> None:
            if expr:
                self.perform_search(expr)

        self.push_screen(SearchDialog(), handle_search)

    def perform_search(self, expr: str) -> None:
        """Perform search with jq expression."""
        import subprocess
        import tempfile

        # Store search expression
        self.search_expr = expr
        self.search_matches = []
        self.search_match_index = 0

        # Search through all records using jq
        for idx, record in enumerate(self.navigator.records):
            try:
                # Write record to temp file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(record, f)
                    temp_path = f.name

                # Test if record matches using jq
                # If expression evaluates to true/truthy, it's a match
                result = subprocess.run(
                    ['jq', '-e', expr, temp_path],
                    capture_output=True,
                    text=True,
                    timeout=1
                )

                # jq -e exits 0 if expression is truthy, 1 if false/null, 2+ on error
                if result.returncode == 0:
                    self.search_matches.append(idx)

                # Clean up temp file
                import os
                os.unlink(temp_path)

            except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
                # Skip records that cause errors
                continue

        # Update subtitle and jump to first match
        if self.search_matches:
            self.navigator.jump_to(self.search_matches[0])
            self.search_match_index = 0
            self.display_current_record()
        else:
            # No matches found
            self.update_subtitle()

    def action_prev_match(self) -> None:
        """Handle 'N' key - previous search match."""
        if not self.search_matches:
            return

        # Move to previous match (wrap around)
        self.search_match_index = (self.search_match_index - 1) % len(self.search_matches)
        target_index = self.search_matches[self.search_match_index]

        if self.navigator.jump_to(target_index):
            self.display_current_record()

    def action_clear_search(self) -> None:
        """Handle Esc key - clear search."""
        self.search_expr = None
        self.search_matches = []
        self.search_match_index = 0
        self.update_subtitle()

    # Tree Navigation Actions
    def action_toggle_node(self) -> None:
        """Handle Space - toggle current node."""
        tree = self.query_one("#tree-view", Tree)
        if tree.cursor_node:
            tree.cursor_node.toggle()

    def action_expand_all(self) -> None:
        """Handle 'e' - expand all nodes."""
        tree = self.query_one("#tree-view", Tree)
        tree.root.expand_all()

    def action_collapse_all(self) -> None:
        """Handle 'c' - collapse all nodes."""
        tree = self.query_one("#tree-view", Tree)
        # Collapse all children but keep root expanded
        for child in tree.root.children:
            child.collapse_all()

    # Other Actions
    def action_help(self) -> None:
        """Handle '?' - show help screen."""
        self.push_screen(HelpScreen())

    def action_refresh(self) -> None:
        """Handle 'r' - refresh display."""
        self.display_current_record()


def writes(config: Optional[dict] = None) -> None:
    """Read NDJSON from stdin, display in single-record viewer.

    Supports two modes:
    1. Streaming mode (stdin is piped): Loads records in background, UI appears immediately
    2. Pre-load mode (stdin is TTY): Waits for data or times out

    The streaming mode allows viewing large datasets without loading everything into memory first.
    """
    config = config or {}

    # Detect if stdin is piped (has data) vs TTY (interactive)
    # If piped: use streaming mode (load in background while UI runs)
    # If TTY: use pre-load mode (wait briefly for data, then start)
    if not sys.stdin.isatty():
        # Stdin is piped - use streaming mode
        # UI starts immediately, records load in background
        app = JSONViewerApp(config=config, records=[], streaming=True)
        app.run()
    else:
        # Stdin is TTY (interactive) - pre-load with timeout
        import signal
        import time

        records = []
        timeout = 5.0
        start_time = time.time()

        def timeout_handler(signum, frame):
            raise TimeoutError("Stdin read timeout")

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout))

        try:
            for line in sys.stdin:
                signal.alarm(int(timeout))
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        records.append(record)
                    except json.JSONDecodeError as e:
                        records.append(
                            {
                                "_error": True,
                                "type": "json_decode_error",
                                "message": str(e),
                                "line": line[:100],
                            }
                        )

                if not records and time.time() - start_time > timeout:
                    break

        except TimeoutError:
            pass
        except Exception as e:
            records.append(
                {
                    "_error": True,
                    "type": "load_error",
                    "message": str(e),
                }
            )
        finally:
            signal.alarm(0)

        app = JSONViewerApp(config=config, records=records, streaming=False)
        app.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Single-record JSON viewer with tree navigation"
    )
    parser.add_argument(
        "--mode",
        default="write",
        choices=["write"],
        help="Plugin mode (write only for display plugins)",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        help="Initial tree expansion depth (default: 2)",
    )
    parser.add_argument(
        "--start-at",
        type=int,
        default=0,
        help="Start at record N (0-based index)",
    )

    args = parser.parse_args()

    config = {
        "depth": args.depth,
        "start_at": args.start_at,
    }

    writes(config)
