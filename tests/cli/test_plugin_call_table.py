import json


def test_plugin_call_table_write_grid(invoke):
    """Test writing NDJSON to grid table format."""
    ndjson = '{"name":"Alice","age":30,"score":95.5}\n{"name":"Bob","age":25,"score":87.2}\n'
    res = invoke(
        ["plugin", "call", "table_", "--mode", "write", "--tablefmt", "grid"],
        input_data=ndjson,
    )
    assert res.exit_code == 0
    output = res.output
    # Grid format has borders
    assert "+" in output or "─" in output
    assert "Alice" in output
    assert "Bob" in output


def test_plugin_call_table_write_pipe(invoke):
    """Test writing NDJSON to pipe (markdown) table format."""
    ndjson = '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'
    res = invoke(
        ["plugin", "call", "table_", "--mode", "write", "--tablefmt", "pipe"],
        input_data=ndjson,
    )
    assert res.exit_code == 0
    output = res.output
    # Pipe format uses |
    assert "|" in output
    assert "Alice" in output
    assert "Bob" in output


def test_plugin_call_table_write_html(invoke):
    """Test writing NDJSON to HTML table format."""
    ndjson = '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'
    res = invoke(
        ["plugin", "call", "table_", "--mode", "write", "--tablefmt", "html"],
        input_data=ndjson,
    )
    assert res.exit_code == 0
    output = res.output
    # HTML format has tags
    assert "<table>" in output
    assert "<tr>" in output
    assert "<td>" in output or "<th>" in output
    assert "Alice" in output


def test_plugin_call_table_read_pipe(invoke):
    """Test reading pipe (markdown) table to NDJSON."""
    table = """| name  | age |
|-------|-----|
| Alice | 30  |
| Bob   | 25  |
"""
    res = invoke(
        ["plugin", "call", "table_", "--mode", "read", "--format", "pipe"],
        input_data=table,
    )
    assert res.exit_code == 0
    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 2

    record1 = json.loads(lines[0])
    assert record1["name"] == "Alice"
    assert record1["age"] == 30  # Should be parsed as int


def test_plugin_call_table_read_grid(invoke):
    """Test reading grid table to NDJSON."""
    table = """+-------+-----+
| name  | age |
+-------+-----+
| Alice | 30  |
| Bob   | 25  |
+-------+-----+
"""
    res = invoke(
        ["plugin", "call", "table_", "--mode", "read", "--format", "grid"],
        input_data=table,
    )
    assert res.exit_code == 0
    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 2

    record1 = json.loads(lines[0])
    assert record1["name"] == "Alice"
    assert record1["age"] == 30


def test_plugin_call_table_read_html(invoke):
    """Test reading HTML table to NDJSON."""
    table = """<table>
<tr><th>name</th><th>age</th></tr>
<tr><td>Alice</td><td>30</td></tr>
<tr><td>Bob</td><td>25</td></tr>
</table>
"""
    res = invoke(
        ["plugin", "call", "table_", "--mode", "read", "--format", "html"],
        input_data=table,
    )
    assert res.exit_code == 0
    lines = [line for line in res.output.strip().split("\n") if line]
    assert len(lines) == 2

    record1 = json.loads(lines[0])
    assert record1["name"] == "Alice"
    assert record1["age"] == 30


def test_plugin_call_table_roundtrip_grid(invoke):
    """Test round-trip: JSON → grid table → JSON."""
    original_ndjson = '{"name":"Alice","age":30,"score":95.5}\n{"name":"Bob","age":25,"score":87.2}\n'

    # Write to grid table
    res1 = invoke(
        ["plugin", "call", "table_", "--mode", "write", "--tablefmt", "grid"],
        input_data=original_ndjson,
    )
    assert res1.exit_code == 0
    table_output = res1.output

    # Read back from grid table
    res2 = invoke(
        ["plugin", "call", "table_", "--mode", "read", "--format", "grid"],
        input_data=table_output,
    )
    assert res2.exit_code == 0

    # Parse both original and round-trip results
    original_records = [
        json.loads(line) for line in original_ndjson.strip().split("\n")
    ]
    roundtrip_records = [
        json.loads(line) for line in res2.output.strip().split("\n") if line
    ]

    # Verify same number of records
    assert len(roundtrip_records) == len(original_records)

    # Verify data matches
    for orig, roundtrip in zip(
        original_records, roundtrip_records, strict=True
    ):
        assert orig["name"] == roundtrip["name"]
        assert orig["age"] == roundtrip["age"]
        assert orig["score"] == roundtrip["score"]


def test_plugin_call_table_roundtrip_pipe(invoke):
    """Test round-trip: JSON → pipe table → JSON."""
    original_ndjson = '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'

    # Write to pipe table
    res1 = invoke(
        ["plugin", "call", "table_", "--mode", "write", "--tablefmt", "pipe"],
        input_data=original_ndjson,
    )
    assert res1.exit_code == 0
    table_output = res1.output

    # Read back from pipe table
    res2 = invoke(
        ["plugin", "call", "table_", "--mode", "read", "--format", "pipe"],
        input_data=table_output,
    )
    assert res2.exit_code == 0

    # Parse both original and round-trip results
    original_records = [
        json.loads(line) for line in original_ndjson.strip().split("\n")
    ]
    roundtrip_records = [
        json.loads(line) for line in res2.output.strip().split("\n") if line
    ]

    # Verify same number of records
    assert len(roundtrip_records) == len(original_records)

    # Verify data matches
    for orig, roundtrip in zip(
        original_records, roundtrip_records, strict=True
    ):
        assert orig["name"] == roundtrip["name"]
        assert orig["age"] == roundtrip["age"]


def test_plugin_call_table_roundtrip_html(invoke):
    """Test round-trip: JSON → HTML table → JSON."""
    original_ndjson = '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'

    # Write to HTML table
    res1 = invoke(
        ["plugin", "call", "table_", "--mode", "write", "--tablefmt", "html"],
        input_data=original_ndjson,
    )
    assert res1.exit_code == 0
    table_output = res1.output

    # Read back from HTML table
    res2 = invoke(
        ["plugin", "call", "table_", "--mode", "read", "--format", "html"],
        input_data=table_output,
    )
    assert res2.exit_code == 0

    # Parse both original and round-trip results
    original_records = [
        json.loads(line) for line in original_ndjson.strip().split("\n")
    ]
    roundtrip_records = [
        json.loads(line) for line in res2.output.strip().split("\n") if line
    ]

    # Verify same number of records
    assert len(roundtrip_records) == len(original_records)

    # Verify data matches
    for orig, roundtrip in zip(
        original_records, roundtrip_records, strict=True
    ):
        assert orig["name"] == roundtrip["name"]
        assert orig["age"] == roundtrip["age"]


def test_plugin_call_table_data_types(invoke):
    """Test that data types are preserved in round-trip."""
    # Test various data types
    original_ndjson = (
        '{"str":"hello","int":42,"float":3.14,"bool":true,"null":null}\n'
    )

    # Write to grid table
    res1 = invoke(
        ["plugin", "call", "table_", "--mode", "write", "--tablefmt", "grid"],
        input_data=original_ndjson,
    )
    assert res1.exit_code == 0

    # Read back
    res2 = invoke(
        ["plugin", "call", "table_", "--mode", "read", "--format", "grid"],
        input_data=res1.output,
    )
    assert res2.exit_code == 0

    # Parse result
    record = json.loads(res2.output.strip())

    # Verify types are preserved
    assert record["str"] == "hello"
    assert record["int"] == 42
    assert record["float"] == 3.14
    assert record["bool"] is True
    assert record["null"] is None


def test_plugin_call_table_auto_detect_pipe(invoke):
    """Test auto-detection of pipe/markdown tables."""
    table = """| name  | age |
|-------|-----|
| Alice | 30  |
"""
    res = invoke(
        ["plugin", "call", "table_", "--mode", "read"], input_data=table
    )
    assert res.exit_code == 0
    record = json.loads(res.output.strip())
    assert record["name"] == "Alice"
    assert record["age"] == 30


def test_plugin_call_table_auto_detect_grid(invoke):
    """Test auto-detection of grid tables."""
    table = """+-------+-----+
| name  | age |
+-------+-----+
| Alice | 30  |
+-------+-----+
"""
    res = invoke(
        ["plugin", "call", "table_", "--mode", "read"], input_data=table
    )
    assert res.exit_code == 0
    record = json.loads(res.output.strip())
    assert record["name"] == "Alice"


def test_plugin_call_table_auto_detect_html(invoke):
    """Test auto-detection of HTML tables."""
    table = """<table>
<tr><th>name</th><th>age</th></tr>
<tr><td>Alice</td><td>30</td></tr>
</table>
"""
    res = invoke(
        ["plugin", "call", "table_", "--mode", "read"], input_data=table
    )
    assert res.exit_code == 0
    record = json.loads(res.output.strip())
    assert record["name"] == "Alice"


def test_plugin_call_table_fancy_grid(invoke):
    """Test fancy grid format with box-drawing characters."""
    ndjson = '{"name":"Alice","age":30}\n'
    res = invoke(
        [
            "plugin",
            "call",
            "table_",
            "--mode",
            "write",
            "--tablefmt",
            "fancy_grid",
        ],
        input_data=ndjson,
    )
    assert res.exit_code == 0
    output = res.output
    # Fancy grid uses box-drawing characters
    assert "╒" in output or "│" in output or "═" in output
    assert "Alice" in output


def test_plugin_call_table_github_format(invoke):
    """Test GitHub-flavored markdown table format."""
    ndjson = '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'
    res = invoke(
        [
            "plugin",
            "call",
            "table_",
            "--mode",
            "write",
            "--tablefmt",
            "github",
        ],
        input_data=ndjson,
    )
    assert res.exit_code == 0
    output = res.output
    # GitHub format is pipe-based
    assert "|" in output
    assert "Alice" in output
    assert "Bob" in output
