import io
import json
import subprocess
import sys
from pathlib import Path


def test_plugin_xlsx_read_direct():
    """Test reading XLSX file to NDJSON by calling plugin directly."""
    # Create a simple XLSX file in memory
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "TestSheet"

    # Write header
    sheet.cell(row=1, column=1, value="name")
    sheet.cell(row=1, column=2, value="age")

    # Write data rows
    sheet.cell(row=2, column=1, value="Alice")
    sheet.cell(row=2, column=2, value=30)
    sheet.cell(row=3, column=1, value="Bob")
    sheet.cell(row=3, column=2, value=25)

    # Save to bytes
    output = io.BytesIO()
    workbook.save(output)
    xlsx_bytes = output.getvalue()

    # Call plugin directly
    plugin_path = Path(__file__).parent.parent.parent / "jn_home" / "plugins" / "formats" / "xlsx_.py"
    result = subprocess.run(
        [sys.executable, str(plugin_path), "--mode", "read"],
        input=xlsx_bytes,
        capture_output=True,
    )

    assert result.returncode == 0, f"Plugin failed: {result.stderr.decode()}"

    lines = [l for l in result.stdout.decode().strip().split("\n") if l]
    assert len(lines) == 2

    record1 = json.loads(lines[0])
    assert record1["name"] == "Alice"
    assert record1["age"] == 30

    record2 = json.loads(lines[1])
    assert record2["name"] == "Bob"
    assert record2["age"] == 25


def test_plugin_xlsx_write_direct():
    """Test writing NDJSON to XLSX file by calling plugin directly."""
    ndjson = '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'

    # Call plugin directly
    plugin_path = Path(__file__).parent.parent.parent / "jn_home" / "plugins" / "formats" / "xlsx_.py"
    result = subprocess.run(
        [sys.executable, str(plugin_path), "--mode", "write"],
        input=ndjson.encode(),
        capture_output=True,
    )

    assert result.returncode == 0, f"Plugin failed: {result.stderr.decode()}"

    # Verify the output is valid XLSX by parsing it
    import openpyxl

    xlsx_bytes = result.stdout
    workbook = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    sheet = workbook.active

    # Check header
    assert sheet.cell(row=1, column=1).value == "name"
    assert sheet.cell(row=1, column=2).value == "age"

    # Check data
    assert sheet.cell(row=2, column=1).value == "Alice"
    assert sheet.cell(row=2, column=2).value == 30
    assert sheet.cell(row=3, column=1).value == "Bob"
    assert sheet.cell(row=3, column=2).value == 25


def test_plugin_xlsx_read_with_sheet_selection_direct():
    """Test reading specific sheet from XLSX file by calling plugin directly."""
    import openpyxl

    workbook = openpyxl.Workbook()

    # Create first sheet
    sheet1 = workbook.active
    sheet1.title = "Sheet1"
    sheet1.cell(row=1, column=1, value="name")
    sheet1.cell(row=2, column=1, value="Alice")

    # Create second sheet
    sheet2 = workbook.create_sheet("Sheet2")
    sheet2.cell(row=1, column=1, value="city")
    sheet2.cell(row=2, column=1, value="NYC")

    # Save to bytes
    output = io.BytesIO()
    workbook.save(output)
    xlsx_bytes = output.getvalue()

    # Test reading second sheet by index
    plugin_path = Path(__file__).parent.parent.parent / "jn_home" / "plugins" / "formats" / "xlsx_.py"
    result = subprocess.run(
        [sys.executable, str(plugin_path), "--mode", "read", "--sheet", "1"],
        input=xlsx_bytes,
        capture_output=True,
    )

    assert result.returncode == 0, f"Plugin failed: {result.stderr.decode()}"

    lines = [l for l in result.stdout.decode().strip().split("\n") if l]
    record = json.loads(lines[0])
    assert record["city"] == "NYC"

    # Test reading second sheet by name
    result = subprocess.run(
        [sys.executable, str(plugin_path), "--mode", "read", "--sheet", "Sheet2"],
        input=xlsx_bytes,
        capture_output=True,
    )

    assert result.returncode == 0, f"Plugin failed: {result.stderr.decode()}"

    lines = [l for l in result.stdout.decode().strip().split("\n") if l]
    record = json.loads(lines[0])
    assert record["city"] == "NYC"


def test_plugin_xlsx_read_empty_rows_direct():
    """Test that empty rows are skipped by calling plugin directly."""
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active

    # Write header
    sheet.cell(row=1, column=1, value="name")
    sheet.cell(row=1, column=2, value="age")

    # Write data with empty row in between
    sheet.cell(row=2, column=1, value="Alice")
    sheet.cell(row=2, column=2, value=30)
    # Row 3 is empty
    sheet.cell(row=4, column=1, value="Bob")
    sheet.cell(row=4, column=2, value=25)

    # Save to bytes
    output = io.BytesIO()
    workbook.save(output)
    xlsx_bytes = output.getvalue()

    # Call plugin directly
    plugin_path = Path(__file__).parent.parent.parent / "jn_home" / "plugins" / "formats" / "xlsx_.py"
    result = subprocess.run(
        [sys.executable, str(plugin_path), "--mode", "read"],
        input=xlsx_bytes,
        capture_output=True,
    )

    assert result.returncode == 0, f"Plugin failed: {result.stderr.decode()}"

    lines = [l for l in result.stdout.decode().strip().split("\n") if l]
    assert len(lines) == 2  # Empty row should be skipped


def test_plugin_xlsx_write_via_jn_plugin_call(invoke):
    """Test binary XLSX output via 'jn plugin call' command."""
    ndjson = '{"name":"Alice","age":30}\n{"name":"Bob","age":25}\n'

    # Call via jn plugin call command (tests binary output handling in service.py)
    result = invoke(["plugin", "call", "xlsx_", "--mode", "write"], input_data=ndjson)

    assert result.exit_code == 0, f"Failed: {result.output}"

    # Verify output is valid XLSX
    import openpyxl

    # Get binary output from result
    xlsx_bytes = result.stdout_bytes if hasattr(result, 'stdout_bytes') else result.output.encode('latin-1')
    workbook = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    sheet = workbook.active

    # Check header
    assert sheet.cell(row=1, column=1).value == "name"
    assert sheet.cell(row=1, column=2).value == "age"

    # Check data
    assert sheet.cell(row=2, column=1).value == "Alice"
    assert sheet.cell(row=2, column=2).value == 30
    assert sheet.cell(row=3, column=1).value == "Bob"
    assert sheet.cell(row=3, column=2).value == 25
