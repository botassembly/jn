"""Subprocess and backpressure violation checks."""

import ast
from ..ast_checker import BaseChecker
from ..violation import Severity


class SubprocessChecker(BaseChecker):
    """Check for subprocess anti-patterns that break streaming/backpressure."""

    def __init__(self, file_path, source):
        super().__init__(file_path, source)
        self.popen_vars = {}  # Track Popen subprocess assignments
        self.has_threading = False

    def visit_Import(self, node: ast.Import) -> None:
        """Check for forbidden threading imports."""
        for alias in node.names:
            if alias.name == "threading":
                self.has_threading = True
                self.add_violation(
                    rule="threading_import",
                    severity=Severity.ERROR,
                    message="Using 'threading' module (use subprocess.Popen for parallelism)",
                    line=node.lineno,
                    fix="Use subprocess.Popen with pipes for true parallelism",
                    reference="spec/arch/backpressure.md:395-448"
                )

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check for subprocess anti-patterns."""

        # Check 1: subprocess.run with capture_output=True
        if self._is_subprocess_run(node):
            for kw in node.keywords:
                if kw.arg == "capture_output":
                    if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        self.add_violation(
                            rule="subprocess_capture_output",
                            severity=Severity.ERROR,
                            message="subprocess.run with capture_output=True buffers entire output",
                            line=node.lineno,
                            column=node.col_offset,
                            fix="Use subprocess.Popen with stdout=PIPE for streaming",
                            reference="spec/arch/backpressure.md:18-29"
                        )

        # Check 2: process.stdout.read() without size argument (reads all)
        if self._is_stdout_read_all(node):
            self.add_violation(
                rule="stdout_read_all",
                severity=Severity.ERROR,
                message="Reading all stdout data before processing (defeats streaming)",
                line=node.lineno,
                column=node.col_offset,
                fix="Stream line-by-line: for line in process.stdout",
                reference="spec/arch/backpressure.md:357-373"
            )

        # Check 3: print without flush=True in NDJSON context
        if self._is_print_json_dumps(node):
            has_flush = any(
                kw.arg == "flush" and
                isinstance(kw.value, ast.Constant) and
                kw.value.value is True
                for kw in node.keywords
            )
            if not has_flush:
                self.add_violation(
                    rule="missing_flush",
                    severity=Severity.ERROR,
                    message="Missing flush=True in print(json.dumps(...)) - causes buffering",
                    line=node.lineno,
                    column=node.col_offset,
                    fix="Add flush=True: print(json.dumps(record), flush=True)",
                    reference="spec/design/plugin-specification.md"
                )

        # Check 4: Track Popen calls
        if self._is_subprocess_popen(node):
            # Will be tracked in visit_Assign
            pass

        # Check 5: Check for .close() calls on stdout
        if self._is_stdout_close(node):
            # Mark that we found a close() call
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Attribute):
                    # e.g., fetch.stdout.close()
                    if node.func.value.attr == "stdout":
                        if isinstance(node.func.value.value, ast.Name):
                            var_name = node.func.value.value.id
                            if var_name in self.popen_vars:
                                self.popen_vars[var_name]["closed"] = True

        # Check 6: Check for .wait() calls
        if self._is_wait_call(node):
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    var_name = node.func.value.id
                    if var_name in self.popen_vars:
                        self.popen_vars[var_name]["waited"] = True

        # Check 7: threading.Thread usage
        if self.has_threading and self._is_thread_create(node):
            self.add_violation(
                rule="thread_usage",
                severity=Severity.ERROR,
                message="Creating Thread objects (doesn't provide parallelism or backpressure)",
                line=node.lineno,
                fix="Use subprocess.Popen with pipes instead",
                reference="spec/arch/backpressure.md:395-448"
            )

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Track subprocess.Popen assignments."""
        if isinstance(node.value, ast.Call) and self._is_subprocess_popen(node.value):
            # Track this Popen variable
            for target in node.targets:
                if isinstance(target, ast.Name):
                    has_stdout_pipe = self._has_stdout_pipe(node.value)
                    self.popen_vars[target.id] = {
                        "line": node.lineno,
                        "has_stdout_pipe": has_stdout_pipe,
                        "closed": False,
                        "waited": False,
                    }

        self.generic_visit(node)

    def check_popen_lifecycle(self) -> None:
        """Check that Popen processes are properly waited and closed."""
        for var_name, info in self.popen_vars.items():
            # Check for missing wait()
            if not info["waited"]:
                self.add_violation(
                    rule="missing_wait",
                    severity=Severity.ERROR,
                    message=f"Popen process '{var_name}' created but never waited (zombie process)",
                    line=info["line"],
                    fix=f"Add {var_name}.wait() before function returns",
                    reference="spec/arch/backpressure.md:375-392"
                )

            # Check for missing stdout.close() when piping to another process
            # (This is harder to detect without control flow analysis, so we'll keep it simple)
            if info["has_stdout_pipe"] and not info["closed"]:
                self.add_violation(
                    rule="missing_stdout_close",
                    severity=Severity.WARNING,
                    message=f"Popen '{var_name}' has stdout=PIPE but .close() not found (may break SIGPIPE)",
                    line=info["line"],
                    fix=f"Add {var_name}.stdout.close() after piping to next process",
                    reference="spec/arch/backpressure.md:107-156"
                )

    def check(self, tree: ast.AST) -> list:
        """Run subprocess checks."""
        self.visit(tree)
        self.check_popen_lifecycle()
        return self.violations

    # Helper methods for pattern matching

    def _is_subprocess_run(self, node: ast.Call) -> bool:
        """Check if call is subprocess.run()."""
        return (
            isinstance(node.func, ast.Attribute) and
            node.func.attr == "run" and
            isinstance(node.func.value, ast.Name) and
            node.func.value.id == "subprocess"
        )

    def _is_subprocess_popen(self, node: ast.Call) -> bool:
        """Check if call is subprocess.Popen()."""
        return (
            isinstance(node.func, ast.Attribute) and
            node.func.attr == "Popen" and
            isinstance(node.func.value, ast.Name) and
            node.func.value.id == "subprocess"
        )

    def _has_stdout_pipe(self, node: ast.Call) -> bool:
        """Check if Popen call has stdout=PIPE."""
        for kw in node.keywords:
            if kw.arg == "stdout":
                if isinstance(kw.value, ast.Attribute):
                    if (kw.value.attr == "PIPE" and
                        isinstance(kw.value.value, ast.Name) and
                        kw.value.value.id == "subprocess"):
                        return True
        return False

    def _is_stdout_read_all(self, node: ast.Call) -> bool:
        """Check if call is process.stdout.read() without size argument."""
        if not isinstance(node.func, ast.Attribute):
            return False
        if node.func.attr != "read":
            return False
        if len(node.args) > 0:  # Has size argument, OK
            return False
        # Check if it's .stdout.read()
        if isinstance(node.func.value, ast.Attribute):
            return node.func.value.attr == "stdout"
        return False

    def _is_print_json_dumps(self, node: ast.Call) -> bool:
        """Check if call is print(json.dumps(...))."""
        if not (isinstance(node.func, ast.Name) and node.func.id == "print"):
            return False

        # Check if first argument is json.dumps()
        if not node.args:
            return False

        first_arg = node.args[0]
        if isinstance(first_arg, ast.Call):
            if isinstance(first_arg.func, ast.Attribute):
                return (
                    first_arg.func.attr == "dumps" and
                    isinstance(first_arg.func.value, ast.Name) and
                    first_arg.func.value.id == "json"
                )
        return False

    def _is_stdout_close(self, node: ast.Call) -> bool:
        """Check if call is .stdout.close()."""
        return (
            isinstance(node.func, ast.Attribute) and
            node.func.attr == "close" and
            isinstance(node.func.value, ast.Attribute) and
            node.func.value.attr == "stdout"
        )

    def _is_wait_call(self, node: ast.Call) -> bool:
        """Check if call is process.wait()."""
        return (
            isinstance(node.func, ast.Attribute) and
            node.func.attr == "wait"
        )

    def _is_thread_create(self, node: ast.Call) -> bool:
        """Check if call creates a Thread object."""
        if isinstance(node.func, ast.Attribute):
            return (
                node.func.attr == "Thread" and
                isinstance(node.func.value, ast.Name) and
                node.func.value.id == "threading"
            )
        elif isinstance(node.func, ast.Name):
            return node.func.id == "Thread"
        return False
