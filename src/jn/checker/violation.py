"""Violation data structure for checker results."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Severity(Enum):
    """Violation severity levels."""

    ERROR = "error"  # Phase 1: Block PRs
    WARNING = "warning"  # Phase 2: Should fix
    INFO = "info"  # Phase 3: Nice to have


@dataclass
class Violation:
    """Represents a single checker violation."""

    rule: str  # Rule identifier (e.g., "missing_flush")
    severity: Severity  # Error/Warning/Info
    message: str  # Human-readable message
    file_path: str  # Absolute path to file
    line: int  # Line number (1-indexed)
    column: int = 0  # Column number (0-indexed)
    fix: Optional[str] = None  # Suggested fix
    reference: Optional[str] = (
        None  # Reference to docs (e.g., "spec/arch/backpressure.md:18")
    )

    def __str__(self) -> str:
        """Format violation for display."""
        loc = f"{self.file_path}:{self.line}"
        if self.column:
            loc += f":{self.column}"
        return f"{loc}: [{self.severity.value.upper()}] {self.message}"


@dataclass
class CheckResult:
    """Results from checking a single file."""

    file_path: str
    violations: list[Violation]
    checked_rules: list[str]

    @property
    def passed(self) -> bool:
        """Check if file has no ERROR violations."""
        return not any(v.severity == Severity.ERROR for v in self.violations)

    @property
    def error_count(self) -> int:
        """Count ERROR violations."""
        return sum(1 for v in self.violations if v.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count WARNING violations."""
        return sum(
            1 for v in self.violations if v.severity == Severity.WARNING
        )

    @property
    def info_count(self) -> int:
        """Count INFO violations."""
        return sum(1 for v in self.violations if v.severity == Severity.INFO)
