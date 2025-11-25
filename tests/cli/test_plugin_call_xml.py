"""Tests for XML plugin read/write functionality."""

import json
from pathlib import Path


def test_xml_read_flatten_mode(invoke, test_data):
    """Test XML plugin in flatten mode (default)."""
    xml_file = test_data / "books.xml"
    with open(xml_file) as f:
        xml_content = f.read()

    res = invoke(
        ["plugin", "call", "xml_", "--mode", "read"], input_data=xml_content
    )
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) > 0

    # Check first record (should be the catalog root)
    first = json.loads(lines[0])
    assert "tag" in first
    assert first["tag"] == "catalog"


def test_xml_read_books_structure(invoke, test_data):
    """Test that books.xml is parsed with correct structure."""
    xml_file = test_data / "books.xml"
    with open(xml_file) as f:
        xml_content = f.read()

    res = invoke(
        [
            "plugin",
            "call",
            "xml_",
            "--mode",
            "read",
            "--parse-mode",
            "flatten",
        ],
        input_data=xml_content,
    )
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Find book records
    books = [r for r in records if r.get("tag") == "book"]
    assert len(books) == 3

    # Check book attributes
    book_ids = [r.get("id") for r in books]
    assert "1" in book_ids
    assert "2" in book_ids
    assert "3" in book_ids


def test_xml_read_tree_mode(invoke, test_data):
    """Test XML plugin in tree mode (returns single nested record)."""
    xml_file = test_data / "books.xml"
    with open(xml_file) as f:
        xml_content = f.read()

    res = invoke(
        ["plugin", "call", "xml_", "--mode", "read", "--parse-mode", "tree"],
        input_data=xml_content,
    )
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 1  # Tree mode returns single record

    tree = json.loads(lines[0])
    assert tree["_tag"] == "catalog"
    assert "_children" in tree
    assert "book" in tree["_children"]


def test_xml_read_users_with_attributes(invoke, test_data):
    """Test XML parsing with element attributes."""
    xml_file = test_data / "users.xml"
    with open(xml_file) as f:
        xml_content = f.read()

    res = invoke(
        [
            "plugin",
            "call",
            "xml_",
            "--mode",
            "read",
            "--parse-mode",
            "flatten",
        ],
        input_data=xml_content,
    )
    assert res.exit_code == 0

    lines = [line for line in res.output.strip().split("\n") if line]
    records = [json.loads(line) for line in lines]

    # Find user records
    users = [r for r in records if r.get("tag") == "user"]
    assert len(users) == 3

    # Check that attributes are present
    alice = next(u for u in users if u.get("id") == "1")
    assert alice["email"] == "alice@example.com"
    assert alice["active"] == "true"


def test_xml_write_basic(invoke):
    """Test XML plugin write mode with basic NDJSON."""
    ndjson = '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'

    res = invoke(
        ["plugin", "call", "xml_", "--mode", "write"],
        input_data=ndjson,
    )
    assert res.exit_code == 0
    assert '<?xml version="1.0"' in res.output
    assert "<root>" in res.output
    assert "<item>" in res.output
    assert "Alice" in res.output
    assert "Bob" in res.output


def test_xml_write_custom_tags(invoke):
    """Test XML write with custom root and item tags."""
    ndjson = '{"title":"Book1"}\n{"title":"Book2"}\n'

    res = invoke(
        [
            "plugin",
            "call",
            "xml_",
            "--mode",
            "write",
            "--root-tag",
            "library",
            "--item-tag",
            "book",
        ],
        input_data=ndjson,
    )
    assert res.exit_code == 0
    assert "<library>" in res.output
    assert "<book>" in res.output
    assert "Book1" in res.output
    assert "Book2" in res.output
