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

    assert result.returncode == 0, f"stderr: {result.stderr}"

    data = json.loads(result.stdout)
    # Basic sanity checks
    assert data.get("resource") == url
    assert data.get("format") == "csv"
    assert data.get("rows", 0) > 0
    assert data.get("columns", 0) > 0
    assert isinstance(data.get("schema", {}), dict)
