"""Plugin checker - AST-based static analysis for JN plugins and core code."""

import ast
from pathlib import Path
from typing import List, Optional

from .rules.forbidden import ForbiddenPatternsChecker
from .rules.structure import StructureChecker
from .rules.subprocess_rules import SubprocessChecker
from .violation import CheckResult, Severity, Violation
from .whitelist import Whitelist


def is_plugin_file(file_path: Path) -> bool:
    """Determine if a file is a plugin based on its path.

    Args:
        file_path: Path to check

    Returns:
        True if file is a plugin, False if framework/core code
    """
    path_str = str(file_path)
    # Plugins are in jn_home/plugins/ or custom plugin directories
    # Framework code is in src/jn/
    return (
        "jn_home/plugins/" in path_str
        or ("/plugins/" in path_str
        and "src/jn/" not in path_str)
    )


def check_file(
    file_path: Path,
    rules: List[str] = None,
    is_plugin: bool = None,
    whitelist: Optional[Whitelist] = None,
) -> CheckResult:
    """Check a single file with all enabled rules.

    Args:
        file_path: Path to file to check
        rules: List of rule categories to run (default: all)
            Options: 'structure', 'subprocess', 'forbidden'
        is_plugin: Whether file is a plugin (auto-detected if None)
        whitelist: Whitelist instance (auto-loaded if None)

    Returns:
        CheckResult with violations found
    """
    if rules is None:
        rules = ["structure", "subprocess", "forbidden"]

    # Auto-detect if plugin unless explicitly specified
    if is_plugin is None:
        is_plugin = is_plugin_file(file_path)

    # Load whitelist if not provided
    if whitelist is None:
        whitelist = Whitelist()

    # Read file
    try:
        source = file_path.read_text()
    except (OSError, UnicodeDecodeError) as e:
        return CheckResult(
            file_path=str(file_path),
            violations=[
                Violation(
                    rule="read_error",
                    severity=Severity.ERROR,
                    message=f"Failed to read file: {e}",
                    file_path=str(file_path),
                    line=1,
                )
            ],
            checked_rules=[],
        )

    # Parse inline ignores
    whitelist.parse_inline_ignores(str(file_path), source)

    # Parse AST
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return CheckResult(
            file_path=str(file_path),
            violations=[
                Violation(
                    rule="syntax_error",
                    severity=Severity.ERROR,
                    message=f"Syntax error: {e.msg}",
                    file_path=str(file_path),
                    line=e.lineno or 1,
                )
            ],
            checked_rules=[],
        )

    # Run checkers
    all_violations = []

    if "structure" in rules:
        checker = StructureChecker(file_path, source, is_plugin=is_plugin)
        all_violations.extend(checker.check(tree))

    if "subprocess" in rules:
        checker = SubprocessChecker(file_path, source)
        all_violations.extend(checker.check(tree))

    if "forbidden" in rules:
        checker = ForbiddenPatternsChecker(file_path, source)
        all_violations.extend(checker.check(tree))

    # Filter out whitelisted violations
    filtered_violations = [
        v
        for v in all_violations
        if not whitelist.is_whitelisted(str(file_path), v.rule, v.line)
    ]

    return CheckResult(
        file_path=str(file_path),
        violations=filtered_violations,
        checked_rules=rules,
    )


def check_files(
    file_paths: List[Path],
    rules: List[str] = None,
    is_plugin: bool = None,
    whitelist: Optional[Whitelist] = None,
) -> List[CheckResult]:
    """Check multiple files.

    Args:
        file_paths: List of file paths to check
        rules: List of rule categories to run (default: all)
        is_plugin: Whether files are plugins (auto-detected per file if None)
        whitelist: Whitelist instance (auto-loaded if None)

    Returns:
        List of CheckResult objects
    """
    # Load whitelist once for all files
    if whitelist is None:
        whitelist = Whitelist()

    results = []
    for file_path in file_paths:
        result = check_file(
            file_path, rules=rules, is_plugin=is_plugin, whitelist=whitelist
        )
        results.append(result)
    return results
