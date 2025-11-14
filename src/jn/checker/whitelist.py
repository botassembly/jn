"""Whitelist support for checker violations.

Supports two whitelisting mechanisms:
1. .jncheck.toml configuration file (project-level exemptions)
2. Inline comments (per-line exemptions)
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for older Python


@dataclass
class WhitelistEntry:
    """A single whitelist entry."""

    file_pattern: str  # Glob pattern or specific file
    rule: str  # Rule name or '*' for all
    lines: Optional[List[int]] = None  # Specific lines, None = all lines
    reason: Optional[str] = None  # Justification


class Whitelist:
    """Manages checker violation exemptions."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize whitelist from config file.

        Args:
            config_path: Path to .jncheck.toml (default: search from cwd)
        """
        self.entries: List[WhitelistEntry] = []
        self.inline_ignores: Dict[str, Dict[int, Set[str]]] = (
            {}
        )  # file -> line -> rules

        # Load config file
        if config_path is None:
            config_path = self._find_config()
        if config_path and config_path.exists():
            self._load_config(config_path)

    def _find_config(self) -> Optional[Path]:
        """Search for .jncheck.toml in current directory and parents."""
        current = Path.cwd()
        while True:
            config = current / ".jncheck.toml"
            if config.exists():
                return config
            if current.parent == current:
                break
            current = current.parent
        return None

    def _load_config(self, config_path: Path):
        """Load whitelist entries from TOML config.

        Example .jncheck.toml:
        ```toml
        [[whitelist]]
        file = "jn_home/plugins/formats/xlsx_.py"
        rule = "stdin_buffer_read"
        lines = [38]
        reason = "ZIP archives require complete file access (EOF metadata)"

        [[whitelist]]
        file = "src/jn/cli/commands/*.py"
        rule = "sys_exit_in_function"
        reason = "CLI commands legitimately use sys.exit() for error codes"
        ```
        """
        try:
            data = tomllib.loads(config_path.read_text())
            for entry in data.get("whitelist", []):
                self.entries.append(
                    WhitelistEntry(
                        file_pattern=entry["file"],
                        rule=entry.get("rule", "*"),
                        lines=entry.get("lines"),
                        reason=entry.get("reason"),
                    )
                )
        except Exception as e:
            # Don't fail checker if config is invalid
            print(f"Warning: Failed to load .jncheck.toml: {e}")

    def add_inline_ignore(self, file_path: str, line: int, rules: Set[str]):
        """Add inline ignore from code comment.

        Args:
            file_path: File path
            line: Line number
            rules: Set of rule names to ignore
        """
        if file_path not in self.inline_ignores:
            self.inline_ignores[file_path] = {}
        self.inline_ignores[file_path][line] = rules

    def parse_inline_ignores(self, file_path: str, source: str):
        """Parse inline ignore comments from source code.

        Supported formats:
        - # jn:ignore - Ignore all rules on this line
        - # jn:ignore[rule_name] - Ignore specific rule
        - # jn:ignore[rule1,rule2] - Ignore multiple rules
        - # jn:ignore: reason - Ignore with reason (optional)

        Args:
            file_path: File path being checked
            source: Source code
        """
        for line_num, line in enumerate(source.splitlines(), start=1):
            # Look for jn:ignore comments
            match = re.search(
                r"#\s*jn:ignore(?:\[([^\]]+)\])?(?::\s*(.+))?", line
            )
            if match:
                rules_str = match.group(1)
                # reason = match.group(2)  # Could be used for reporting

                if rules_str:
                    # Specific rules
                    rules = {r.strip() for r in rules_str.split(",")}
                else:
                    # All rules
                    rules = {"*"}

                self.add_inline_ignore(file_path, line_num, rules)

    def is_whitelisted(self, file_path: str, rule: str, line: int) -> bool:
        """Check if a violation should be ignored.

        Args:
            file_path: File path
            rule: Rule name
            line: Line number

        Returns:
            True if violation is whitelisted
        """
        # Check inline ignores first (highest priority)
        if (
            file_path in self.inline_ignores
            and line in self.inline_ignores[file_path]
        ):
            ignored_rules = self.inline_ignores[file_path][line]
            if "*" in ignored_rules or rule in ignored_rules:
                return True

        # Check config file entries
        for entry in self.entries:
            # Match file pattern
            if not self._matches_pattern(file_path, entry.file_pattern):
                continue

            # Match rule
            if entry.rule != "*" and entry.rule != rule:
                continue

            # Match line (if specified)
            if entry.lines is not None and line not in entry.lines:
                continue

            # All criteria matched
            return True

        return False

    def _matches_pattern(self, file_path: str, pattern: str) -> bool:
        """Check if file path matches glob pattern.

        Handles both absolute and relative paths by trying multiple matching strategies.

        Args:
            file_path: File path to check (may be absolute or relative)
            pattern: Glob pattern (e.g., "*.py", "src/**/*.py")

        Returns:
            True if path matches pattern
        """
        from fnmatch import fnmatch

        # Normalize paths
        file_path_obj = Path(file_path)
        pattern_obj = Path(pattern)

        # Convert to strings for matching
        file_path_str = str(file_path_obj)
        pattern_str = str(pattern_obj)

        # Try direct match
        if fnmatch(file_path_str, pattern_str):
            return True

        # If file_path is absolute, try matching against suffix
        # e.g., /home/user/jn/src/jn/cli/commands/cat.py should match src/jn/cli/commands/*.py
        if file_path_obj.is_absolute():
            # Try to extract relative path by finding pattern prefix in file path
            # Look for pattern prefix anywhere in the file path
            file_parts = file_path_obj.parts

            # Try to find where pattern starts in file path
            for i in range(len(file_parts)):
                # Try to match pattern from this position
                remaining_file_parts = file_parts[i:]

                # Build relative path from this position
                if remaining_file_parts:
                    relative_path = str(Path(*remaining_file_parts))

                    # Try direct fnmatch
                    if fnmatch(relative_path, pattern_str):
                        return True

                    # Try with ** glob expansion
                    if "**" in pattern_str:
                        regex_pattern = pattern_str.replace("**/", ".*?/")
                        regex_pattern = regex_pattern.replace("**", ".*?")
                        regex_pattern = regex_pattern.replace("*", "[^/]*")
                        regex_pattern = regex_pattern.replace("?", ".")
                        regex_pattern = f"^{regex_pattern}$"
                        if re.match(regex_pattern, relative_path):
                            return True

        # Try with ** glob (recursive) on original path
        if "**" in pattern_str:
            # Convert ** to regex
            regex_pattern = pattern_str.replace("**/", ".*?/")
            regex_pattern = regex_pattern.replace("**", ".*?")
            regex_pattern = regex_pattern.replace("*", "[^/]*")
            regex_pattern = regex_pattern.replace("?", ".")
            if re.search(regex_pattern, file_path_str):
                return True

        # Try basename match
        return fnmatch(file_path_obj.name, pattern_str) or fnmatch(
            file_path_obj.name, pattern_obj.name
        )

    def get_reason(
        self, file_path: str, rule: str, line: int
    ) -> Optional[str]:
        """Get whitelist reason for a violation.

        Args:
            file_path: File path
            rule: Rule name
            line: Line number

        Returns:
            Reason string if whitelisted, None otherwise
        """
        for entry in self.entries:
            if not self._matches_pattern(file_path, entry.file_pattern):
                continue
            if entry.rule != "*" and entry.rule != rule:
                continue
            if entry.lines is not None and line not in entry.lines:
                continue
            return entry.reason

        return None
