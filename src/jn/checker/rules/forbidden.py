"""Check for forbidden patterns in plugins."""

import ast

from ..ast_checker import BaseChecker, get_function_names
from ..violation import Severity


class ForbiddenPatternsChecker(BaseChecker):
    """Check for patterns that are forbidden in plugins."""

    def __init__(self, file_path, source):
        super().__init__(file_path, source)
        self.in_main_block = False
        self.plugin_functions = set()  # reads, writes, etc.

    def visit_Module(self, node: ast.Module) -> None:
        """Extract plugin function names."""
        self.plugin_functions = get_function_names(node)
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        """Track if we're in if __name__ == '__main__' block."""
        # Check if this is: if __name__ == '__main__':
        is_compare = (
            isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
            and node.test.ops
            and isinstance(node.test.ops[0], ast.Eq)
            and node.test.comparators
        )
        comp = node.test.comparators[0] if is_compare else None
        is_main_check = bool(
            comp
            and isinstance(comp, ast.Constant)
            and comp.value == "__main__"
        )

        if is_main_check:
            self.in_main_block = True
            self.generic_visit(node)
            self.in_main_block = False
        else:
            self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Check for forbidden framework imports."""
        for alias in node.names:
            # Check for jn framework imports
            if alias.name == "jn" or alias.name.startswith("jn."):
                self.add_violation(
                    rule="framework_import",
                    severity=Severity.ERROR,
                    message=f"Importing from jn framework ('{alias.name}') - plugins must be self-contained",
                    line=node.lineno,
                    fix="Remove framework import - plugins should not depend on jn internals",
                    reference="spec/design/plugin-specification.md (Forbidden Patterns)",
                )

        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check for forbidden framework imports."""
        if node.module and (
            node.module == "jn" or node.module.startswith("jn.")
        ):
            self.add_violation(
                rule="framework_import",
                severity=Severity.ERROR,
                message=f"Importing from jn framework ('{node.module}') - plugins must be self-contained",
                line=node.lineno,
                fix="Remove framework import - plugins should not depend on jn internals",
                reference="spec/design/plugin-specification.md (Forbidden Patterns)",
            )

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check for forbidden function calls."""
        # Check for sys.exit() in plugin functions (not in main block)
        if self._is_sys_exit(node) and not self.in_main_block:
            self.add_violation(
                rule="sys_exit_in_function",
                severity=Severity.ERROR,
                message="sys.exit() in plugin function (exits entire process)",
                line=node.lineno,
                fix="Remove sys.exit() - yield error records or raise exceptions instead",
                reference="spec/design/plugin-specification.md (Forbidden Patterns)",
            )

        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Check for bare except: clauses."""
        if node.type is None:  # Bare except:
            self.add_violation(
                rule="bare_except",
                severity=Severity.ERROR,
                message="Bare except: clause (catches KeyboardInterrupt, SystemExit)",
                line=node.lineno,
                fix="Use specific exception type: except ValueError:",
                reference="spec/design/plugin-specification.md",
            )

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check function-level patterns."""
        # Check for missing docstrings in reads/writes
        if node.name in ("reads", "writes"):
            has_docstring = (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            )
            if not has_docstring:
                self.add_violation(
                    rule="missing_function_docstring",
                    severity=Severity.WARNING,
                    message=f"Function '{node.name}()' missing docstring",
                    line=node.lineno,
                    fix=f"Add docstring describing {node.name}() behavior",
                )

        self.generic_visit(node)

    def _is_sys_exit(self, node: ast.Call) -> bool:
        """Check if call is sys.exit()."""
        if isinstance(node.func, ast.Attribute):
            return (
                node.func.attr == "exit"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "sys"
            )
        elif isinstance(node.func, ast.Name):
            return node.func.id == "exit"
        return False
