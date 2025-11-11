"""Plugin checker - AST-based static analysis for JN plugins and core code."""

import ast
from pathlib import Path
from typing import List

from .violation import CheckResult, Violation, Severity
from .rules.structure import StructureChecker
from .rules.subprocess_rules import SubprocessChecker
from .rules.forbidden import ForbiddenPatternsChecker


def check_file(file_path: Path, rules: List[str] = None) -> CheckResult:
    """Check a single file with all enabled rules.

    Args:
        file_path: Path to file to check
        rules: List of rule categories to run (default: all)
            Options: 'structure', 'subprocess', 'forbidden'

    Returns:
        CheckResult with violations found
    """
    if rules is None:
        rules = ["structure", "subprocess", "forbidden"]

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
                    line=1
                )
            ],
            checked_rules=[]
        )

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
                    line=e.lineno or 1
                )
            ],
            checked_rules=[]
        )

    # Run checkers
    all_violations = []

    if "structure" in rules:
        checker = StructureChecker(file_path, source)
        all_violations.extend(checker.check(tree))

    if "subprocess" in rules:
        checker = SubprocessChecker(file_path, source)
        all_violations.extend(checker.check(tree))

    if "forbidden" in rules:
        checker = ForbiddenPatternsChecker(file_path, source)
        all_violations.extend(checker.check(tree))

    return CheckResult(
        file_path=str(file_path),
        violations=all_violations,
        checked_rules=rules
    )


def check_files(file_paths: List[Path], rules: List[str] = None) -> List[CheckResult]:
    """Check multiple files.

    Args:
        file_paths: List of file paths to check
        rules: List of rule categories to run (default: all)

    Returns:
        List of CheckResult objects
    """
    results = []
    for file_path in file_paths:
        result = check_file(file_path, rules=rules)
        results.append(result)
    return results
