"""Structural checks for plugin files (shebang, PEP 723, docstrings)."""

import ast

from ..ast_checker import (
    STDLIB_MODULES,
    BaseChecker,
    get_imports,
    parse_pep723,
)
from ..violation import Severity


class StructureChecker(BaseChecker):
    """Check plugin structure requirements."""

    def __init__(self, file_path, source, is_plugin: bool = True):
        """Initialize structure checker.

        Args:
            file_path: Path to file
            source: Source code
            is_plugin: Whether this is a plugin file (vs framework code)
        """
        super().__init__(file_path, source)
        self.is_plugin = is_plugin

    def check_file(self) -> None:
        """Check file-level structure (shebang, PEP 723, docstring)."""
        lines = self.source.splitlines()

        # Skip plugin-specific checks for framework code
        if not self.is_plugin:
            return

        # Check 1: UV shebang (line 1) - PLUGINS ONLY
        if not lines:
            self.add_violation(
                rule="missing_shebang",
                severity=Severity.ERROR,
                message="File is empty",
                line=1,
            )
            return

        expected_shebang = "#!/usr/bin/env -S uv run --script"
        if lines[0] != expected_shebang:
            self.add_violation(
                rule="missing_uv_shebang",
                severity=Severity.ERROR,
                message=f"First line must be: {expected_shebang}",
                line=1,
                fix=f"Change line 1 to: {expected_shebang}",
                reference="spec/design/plugin-specification.md (Required Components)",
            )

        # Check 2: PEP 723 block - PLUGINS ONLY
        pep723 = parse_pep723(self.source)
        if not pep723:
            self.add_violation(
                rule="missing_pep723",
                severity=Severity.ERROR,
                message="Missing PEP 723 script block",
                line=3,
                fix="Add PEP 723 block with requires-python, dependencies, and [tool.jn]",
                reference="spec/design/plugin-specification.md (Required Components)",
            )
            return

        # Check 3: PEP 723 required fields - PLUGINS ONLY
        if "requires-python" not in pep723:
            self.add_violation(
                rule="missing_requires_python",
                severity=Severity.ERROR,
                message="PEP 723 block missing 'requires-python' field",
                line=4,
            )

        if "dependencies" not in pep723:
            self.add_violation(
                rule="missing_dependencies",
                severity=Severity.ERROR,
                message="PEP 723 block missing 'dependencies' field",
                line=4,
                fix="Add: dependencies = []",
            )

        # Check 4: [tool.jn] section - PLUGINS ONLY
        tool_jn = pep723.get("tool", {}).get("jn", {})
        if not tool_jn:
            self.add_violation(
                rule="missing_tool_jn",
                severity=Severity.WARNING,
                message="PEP 723 block missing [tool.jn] section",
                line=4,
                fix="Add: [tool.jn] section with matches = []",
            )
        elif "matches" not in tool_jn:
            self.add_violation(
                rule="missing_matches",
                severity=Severity.WARNING,
                message="[tool.jn] section missing 'matches' field",
                line=4,
                fix="Add: matches = [] (empty list for filters)",
            )

    def check_dependencies(self, tree: ast.AST) -> None:
        """Check that all imports are declared in PEP 723 dependencies."""
        # Skip dependency checking for framework code (no PEP 723 required)
        if not self.is_plugin:
            return

        pep723 = parse_pep723(self.source)
        if not pep723:
            return  # Already flagged by check_file

        # Known package-to-module mappings (package name -> module name)
        PACKAGE_MODULE_MAP = {
            "pyyaml": "yaml",
            "ruamel.yaml": "ruamel",
            "pillow": "PIL",
            "beautifulsoup4": "bs4",
            "python-dateutil": "dateutil",
            "attrs": "attr",
            "protobuf": "google.protobuf",
        }

        # Get declared dependencies
        declared_deps = set()
        for dep in pep723.get("dependencies", []):
            # Parse dependency (e.g., "requests>=2.31.0" -> "requests")
            pkg_name = dep.split(">=")[0].split("==")[0].split("[")[0].strip()

            # Add the package name itself
            declared_deps.add(pkg_name)

            # Add known module mapping
            if pkg_name.lower() in PACKAGE_MODULE_MAP:
                declared_deps.add(PACKAGE_MODULE_MAP[pkg_name.lower()])

            # Normalize package name (e.g., "python-frontmatter" -> "frontmatter")
            if "-" in pkg_name:
                # Common pattern: python-foo -> import foo
                parts = pkg_name.split("-")
                if parts[0] == "python":
                    declared_deps.add(parts[1])
                # Also add the full name with underscores
                declared_deps.add(pkg_name.replace("-", "_"))

        # Get imports from code
        imports = get_imports(tree)

        # Check for undeclared imports
        missing = imports - declared_deps - STDLIB_MODULES
        if missing:
            # Find first import location for each missing module
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split(".")[0]
                        if module in missing:
                            self.add_violation(
                                rule="missing_dependency",
                                severity=Severity.ERROR,
                                message=f"Import '{module}' not declared in PEP 723 dependencies",
                                line=node.lineno,
                                fix=f"Add '{module}' to dependencies list",
                                reference="spec/design/plugin-specification.md",
                            )
                            missing.remove(module)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module = node.module.split(".")[0]
                        if module in missing:
                            self.add_violation(
                                rule="missing_dependency",
                                severity=Severity.ERROR,
                                message=f"Import '{module}' not declared in PEP 723 dependencies",
                                line=node.lineno,
                                fix=f"Add '{module}' to dependencies list",
                                reference="spec/design/plugin-specification.md",
                            )
                            missing.remove(module)

    def visit_Module(self, node: ast.Module) -> None:
        """Check module-level docstring."""
        # Check if first statement is a docstring
        has_docstring = (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        )

        if not has_docstring:
            self.add_violation(
                rule="missing_module_docstring",
                severity=Severity.WARNING,
                message="Missing module docstring",
                line=2,
                fix='Add docstring on line 2: """Description of plugin."""',
            )

        self.generic_visit(node)

    def check(self, tree: ast.AST) -> list:
        """Run all structure checks."""
        # File-level checks (before AST traversal)
        self.check_file()

        # AST checks
        self.visit(tree)
        self.check_dependencies(tree)

        return self.violations
