"""Integration tests for XLSX files downloaded from HTTP/HTTPS.

These tests verify that XLSX files can be downloaded and parsed correctly.
Currently uses curl for downloading as the http_ plugin doesn't support
binary formats yet.

See: https://github.com/botassembly/jn/issues/TBD for direct HTTP support.
"""
import json
import subprocess
import sys
import pytest
from pathlib import Path

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


def test_xlsx_from_github_raw_small():
    """Test parsing a small XLSX file from GitHub raw URL."""
    url = "https://raw.githubusercontent.com/Russel88/COEF/master/ExampleData/test.xlsx"
    plugin_path = Path(__file__).parent.parent.parent / "jn_home" / "plugins" / "formats" / "xlsx_.py"

    # Download with curl and pipe to XLSX plugin
    curl = subprocess.Popen(
        ["curl", "-sL", url],
        stdout=subprocess.PIPE
    )

    result = subprocess.run(
        [sys.executable, str(plugin_path), "--mode", "read"],
        stdin=curl.stdout,
        capture_output=True,
        timeout=30
    )

    curl.stdout.close()
    curl.wait()

    assert result.returncode == 0, f"Plugin failed: {result.stderr.decode()}"
    assert curl.returncode == 0, "curl download failed"

    # Parse and verify output
    output = result.stdout.decode()
    lines = [l for l in output.strip().split("\n") if l]
    assert len(lines) > 0, "No output from XLSX parser"

    # Verify first line contains expected data
    first_record = json.loads(lines[0])
    assert "Column_1" in first_record or "Software Version" in str(first_record.values())


def test_xlsx_from_hubmap_consortium():
    """Test parsing HuBMAP consortium sample spreadsheet."""
    url = "https://raw.githubusercontent.com/hubmapconsortium/dataset-metadata-spreadsheet/main/sample-section/latest/sample-section.xlsx"
    plugin_path = Path(__file__).parent.parent.parent / "jn_home" / "plugins" / "formats" / "xlsx_.py"

    curl = subprocess.Popen(
        ["curl", "-sL", url],
        stdout=subprocess.PIPE
    )

    result = subprocess.run(
        [sys.executable, str(plugin_path), "--mode", "read"],
        stdin=curl.stdout,
        capture_output=True,
        timeout=30
    )

    curl.stdout.close()
    curl.wait()

    assert result.returncode == 0, f"Plugin failed: {result.stderr.decode()}"
    assert curl.returncode == 0, "curl download failed"

    output = result.stdout.decode()
    lines = [l for l in output.strip().split("\n") if l]
    assert len(lines) > 0

    # Verify structure includes expected metadata fields
    first_record = json.loads(lines[0])
    assert "metadata_schema_id" in first_record or "sample_id" in first_record


@pytest.mark.slow
def test_xlsx_from_s3_statistics_iceland():
    """Test parsing XLSX from S3 bucket (Statistics Iceland)."""
    url = "https://hagstofan.s3.amazonaws.com/media/public/2019/c464faa7-dbd0-41c7-b37c-8984d23abd8a.xlsx"
    plugin_path = Path(__file__).parent.parent.parent / "jn_home" / "plugins" / "formats" / "xlsx_.py"

    curl = subprocess.Popen(
        ["curl", "-sL", url],
        stdout=subprocess.PIPE
    )

    result = subprocess.run(
        [sys.executable, str(plugin_path), "--mode", "read"],
        stdin=curl.stdout,
        capture_output=True,
        timeout=60  # Larger file may take longer
    )

    curl.stdout.close()
    curl.wait()

    assert result.returncode == 0, f"Plugin failed: {result.stderr.decode()}"
    assert curl.returncode == 0, "curl download failed"

    output = result.stdout.decode()
    lines = [l for l in output.strip().split("\n") if l]
    assert len(lines) > 0

    # Just verify we got valid JSON
    first_record = json.loads(lines[0])
    assert isinstance(first_record, dict)


@pytest.mark.slow
def test_xlsx_from_ons_uk():
    """Test parsing XLSX from UK Office for National Statistics."""
    url = "https://www.ons.gov.uk/visualisations/dvc818/fig1/datadownload.xlsx"
    plugin_path = Path(__file__).parent.parent.parent / "jn_home" / "plugins" / "formats" / "xlsx_.py"

    curl = subprocess.Popen(
        ["curl", "-sL", url],
        stdout=subprocess.PIPE
    )

    result = subprocess.run(
        [sys.executable, str(plugin_path), "--mode", "read"],
        stdin=curl.stdout,
        capture_output=True,
        timeout=60
    )

    curl.stdout.close()
    curl.wait()

    assert result.returncode == 0, f"Plugin failed: {result.stderr.decode()}"
    assert curl.returncode == 0, "curl download failed"

    output = result.stdout.decode()
    lines = [l for l in output.strip().split("\n") if l]
    assert len(lines) > 0

    # Verify valid JSON output
    first_record = json.loads(lines[0])
    assert isinstance(first_record, dict)


def test_xlsx_pipeline_with_filter():
    """Test complete pipeline: download XLSX, filter, output."""
    url = "https://raw.githubusercontent.com/Russel88/COEF/master/ExampleData/test.xlsx"
    plugin_path = Path(__file__).parent.parent.parent / "jn_home" / "plugins" / "formats" / "xlsx_.py"

    # Download and parse
    curl = subprocess.Popen(
        ["curl", "-sL", url],
        stdout=subprocess.PIPE
    )

    xlsx_reader = subprocess.Popen(
        [sys.executable, str(plugin_path), "--mode", "read"],
        stdin=curl.stdout,
        stdout=subprocess.PIPE
    )

    curl.stdout.close()

    # Get first 5 lines
    result = subprocess.run(
        ["head", "-n", "5"],
        stdin=xlsx_reader.stdout,
        capture_output=True,
        timeout=30
    )

    xlsx_reader.stdout.close()
    xlsx_reader.wait()
    curl.wait()

    assert result.returncode == 0
    output = result.stdout.decode()
    lines = [l for l in output.strip().split("\n") if l]
    assert len(lines) == 5

    # Verify all lines are valid JSON
    for line in lines:
        record = json.loads(line)
        assert isinstance(record, dict)
