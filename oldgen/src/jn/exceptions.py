"""JN exceptions."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class JnError(Exception):
    """JN pipeline execution error."""

    step: str
    name: str
    exit_code: int
    stderr: Optional[str] = None
