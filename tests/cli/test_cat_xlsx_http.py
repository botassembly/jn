"""Test XLSX files via HTTP using jn cat command."""

import pytest


def test_jn_cat_xlsx_from_github_url(invoke):
    """Test reading XLSX directly from GitHub raw URL."""
    url = "https://raw.githubusercontent.com/Russel88/COEF/master/ExampleData/test.xlsx"

    result = invoke(["cat", url])
    assert result.exit_code == 0, f"Failed: {result.output}"

    lines = result.output.strip().split("\n")
    assert len(lines) > 5
    assert "Software Version" in lines[0]


def test_jn_cat_xlsx_from_s3_url(invoke):
    """Test reading XLSX from S3 bucket."""
    url = "https://hagstofan.s3.amazonaws.com/media/public/2019/c464faa7-dbd0-41c7-b37c-8984d23abd8a.xlsx"

    result = invoke(["cat", url])
    assert result.exit_code == 0

    lines = result.output.strip().split("\n")
    assert len(lines) > 0


def test_jn_run_xlsx_url_to_json(invoke, tmp_path):
    """Test converting XLSX URL directly to JSON file."""
    url = "https://raw.githubusercontent.com/hubmapconsortium/dataset-metadata-spreadsheet/main/sample-section/latest/sample-section.xlsx"
    output = tmp_path / "output.json"

    result = invoke(["run", url, str(output)])
    assert result.exit_code == 0

    # Verify output file exists and is valid JSON
    assert output.exists()
    content = output.read_text()
    assert len(content) > 0
    assert "metadata_schema_id" in content or "sample_id" in content
