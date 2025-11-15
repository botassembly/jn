"""End-to-end test: HTTP (raw) → gz (raw) → csv (read) → inspect.

Uses a small public NCBI dataset to avoid large downloads.
"""

import json
import subprocess
import sys

import pytest


@pytest.fixture
def jn_cli():
    """Return path to jn CLI (installed in venv)."""
    import shutil

    jn_path = shutil.which("jn")
    if jn_path:
        return [jn_path]
    return [sys.executable, "-m", "jn.cli.main"]


def test_inspect_ncbi_viruses_retroviridae_small(jn_cli):
    """Inspect a small gz CSV over HTTP and ensure pipeline succeeds."""
    url = (
        "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/"
        "Viruses/Retroviridae.gene_info.gz~csv?delimiter=auto"
    )

    result = subprocess.run(
        [*jn_cli, "inspect", url, "--limit", "50", "--format", "json"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Head may propagate a non-zero exit when upstream closes due to
    # SIGPIPE-style truncation; accept either but verify output.
    assert result.returncode in (0, 1), f"stderr: {result.stderr}"

    data = json.loads(result.stdout)
    # Basic sanity checks
    assert data.get("resource") == url
    assert data.get("format") == "csv"
    assert data.get("rows", 0) > 0
    assert data.get("columns", 0) > 0
    assert isinstance(data.get("schema", {}), dict)


def test_head_ncbi_homo_sapiens_escape_params(jn_cli):
    """Test that '~?params' escapes URL query into JN filters."""
    url = (
        "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/"
        "Mammalia/Homo_sapiens.gene_info.gz~?chromosome=19"
    )

    result = subprocess.run(
        [*jn_cli, "head", url, "-n", "5"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Head may return non-zero due to upstream SIGPIPE-style truncation;
    # output content is the primary contract here.
    assert result.returncode in (0, 1), f"stderr: {result.stderr}"

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines, "Expected at least one filtered record"

    for line in lines:
        record = json.loads(line)
        assert record.get("chromosome") == "19"
