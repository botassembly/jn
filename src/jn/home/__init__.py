"""Home layer: path resolution and file I/O (no Pydantic dependencies)."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def resolve_config_path(cli_path: Optional[Path] = None) -> Path:
    """
    Resolve jn.json config file path with precedence:
    1. CLI --jn path
    2. JN_PATH env var
    3. CWD: .jn.json or jn.json (prefer .jn.json)
    4. User home: ~/.jn.json
    """
    if cli_path:
        return cli_path

    env = os.getenv("JN_PATH")
    if env:
        return Path(env).expanduser()

    cwd = Path.cwd()
    for name in (".jn.json", "jn.json"):
        p = cwd / name
        if p.exists():
            return p

    return Path.home() / ".jn.json"


def load_json(path: Path) -> Dict[str, Any]:
    """Load and parse JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Dict[str, Any]) -> None:
    """Save data to JSON file with pretty formatting."""
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
