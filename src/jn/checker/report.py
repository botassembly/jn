"""Report formatting for checker results."""

import json
from pathlib import Path
from typing import List

from .violation import CheckResult, Severity


def format_text(results: List[CheckResult], verbose: bool = False) -> str:
    """Format results as human-readable text.

    Args:
        results: List of check results
        verbose: Show all details including passed checks

    Returns:
        Formatted text report
    """
    lines = []
    total_errors = 0
    total_warnings = 0
    total_infos = 0
    passed_count = 0
    failed_count = 0

    for result in results:
        file_name = Path(result.file_path).name
        plugin_name = Path(result.file_path).stem

        lines.append("")
        lines.append("━" * 70)
        lines.append(f"📋 Checking: {plugin_name} ({result.file_path})")
        lines.append("━" * 70)
        lines.append("")

        if not result.violations:
            lines.append("✅ All checks passed! 🎉")
            passed_count += 1
        else:
            # Group violations by severity
            errors = [
                v for v in result.violations if v.severity == Severity.ERROR
            ]
            warnings = [
                v for v in result.violations if v.severity == Severity.WARNING
            ]
            infos = [
                v for v in result.violations if v.severity == Severity.INFO
            ]

            total_errors += len(errors)
            total_warnings += len(warnings)
            total_infos += len(infos)

            if errors:
                failed_count += 1

            # Show errors
            for violation in errors:
                lines.append(f"❌ ERROR: {violation.rule}")
                lines.append(f"   {file_name}:{violation.line}")
                if violation.column:
                    lines.append(f"   Column {violation.column}")
                lines.append(f"   {violation.message}")
                if violation.fix:
                    lines.append(f"   💡 Fix: {violation.fix}")
                if violation.reference:
                    lines.append(f"   📖 Reference: {violation.reference}")
                lines.append("")

            # Show warnings
            for violation in warnings:
                lines.append(f"⚠️  WARNING: {violation.rule}")
                lines.append(f"   {file_name}:{violation.line}")
                lines.append(f"   {violation.message}")
                if violation.fix:
                    lines.append(f"   💡 Fix: {violation.fix}")
                lines.append("")

            # Show infos (only in verbose mode)
            if verbose and infos:
                for violation in infos:
                    lines.append(f"INFO: {violation.rule}")
                    lines.append(f"   {file_name}:{violation.line}")
                    lines.append(f"   {violation.message}")
                    lines.append("")

    # Summary
    lines.append("")
    lines.append("━" * 70)
    lines.append("Summary")
    lines.append("━" * 70)
    lines.append("")
    lines.append(f"Checked: {len(results)} files")
    lines.append(f"  ✅ {passed_count} passed")
    if failed_count:
        lines.append(f"  ❌ {failed_count} failed")
    lines.append("")
    lines.append(
        f"Issues found: {total_errors} errors, {total_warnings} warnings"
    )
    if verbose and total_infos:
        lines.append(f"             {total_infos} info")
    lines.append("")

    if total_errors > 0:
        lines.append("Exit code: 1 (errors present)")
    else:
        lines.append("Exit code: 0 (no errors)")

    return "\n".join(lines)


def format_json(results: List[CheckResult]) -> str:
    """Format results as JSON for CI/CD.

    Args:
        results: List of check results

    Returns:
        JSON string
    """
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)
    total_infos = sum(r.info_count for r in results)
    passed_count = sum(1 for r in results if r.passed)
    failed_count = sum(1 for r in results if not r.passed)

    output = {
        "summary": {
            "checked": len(results),
            "passed": passed_count,
            "failed": failed_count,
            "errors": total_errors,
            "warnings": total_warnings,
            "infos": total_infos,
        },
        "results": [],
    }

    for result in results:
        file_result = {
            "file": result.file_path,
            "passed": result.passed,
            "violations": [
                {
                    "rule": v.rule,
                    "severity": v.severity.value,
                    "message": v.message,
                    "line": v.line,
                    "column": v.column,
                    "fix": v.fix,
                    "reference": v.reference,
                }
                for v in result.violations
            ],
        }
        output["results"].append(file_result)

    return json.dumps(output, indent=2)


def format_summary(results: List[CheckResult]) -> str:
    """Format concise one-line summary.

    Args:
        results: List of check results

    Returns:
        Summary string
    """
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)
    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count

    parts = [f"{len(results)} files"]

    if passed_count > 0:
        parts.append(f"✅ {passed_count} passed")
    if failed_count > 0:
        parts.append(f"❌ {failed_count} failed")
    if total_errors > 0:
        parts.append(f"{total_errors} errors")
    if total_warnings > 0:
        parts.append(f"{total_warnings} warnings")

    return " | ".join(parts)
