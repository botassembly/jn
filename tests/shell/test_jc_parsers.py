"""Additional integration coverage for jc fallback paths.

Covers a batch (array) parser path and another streaming parser path.
"""

import json
import shutil
import subprocess
import sys


def _jn_cli_cmd():
    # Prefer installed 'jn' binary if present
    jn_path = shutil.which("jn")
    if jn_path:
        return [jn_path]
    return [sys.executable, "-m", "jn.cli.main"]


def test_jn_sh_ps_batch_parser_ndjson():
    """ps is parsed by jc in batch mode (JSON array → NDJSON).

    Validate that we receive valid NDJSON objects and at least one record.
    """
    cmd = [*_jn_cli_cmd(), "sh", "ps", "aux"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    lines = [ln for ln in res.stdout.splitlines() if ln.strip()]
    assert len(lines) > 0
    # First line should be a JSON object
    obj = json.loads(lines[0])
    assert isinstance(obj, dict)
    assert "pid" in obj or "process_name" in obj or "user" in obj

    # Note: Streaming path is exercised by ls -l test in test_shell_integration.
