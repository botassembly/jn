"""AST-based code checker for plugins and core code."""

import ast
import re
from pathlib import Path
from typing import List, Set

from .violation import Violation, Severity


# PEP 723 regex pattern
PEP723_PATTERN = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\n(?P<content>(^#(| .*)$\n)+)^# ///$"
)


class BaseChecker(ast.NodeVisitor):
    """Base class for AST-based checkers.

    Subclasses should override visit_* methods to implement specific checks.
    """

    def __init__(self, file_path: Path, source: str):
        """Initialize checker.

        Args:
            file_path: Path to file being checked
            source: Source code content
        """
        self.file_path = file_path
        self.source = source
        self.lines = source.splitlines()
        self.violations: List[Violation] = []

    def add_violation(
        self,
        rule: str,
        severity: Severity,
        message: str,
        line: int,
        column: int = 0,
        fix: str = None,
        reference: str = None
    ) -> None:
        """Add a violation to the results.

        Args:
            rule: Rule identifier
            severity: Severity level
            message: Human-readable message
            line: Line number (1-indexed)
            column: Column number (0-indexed)
            fix: Optional suggested fix
            reference: Optional reference to docs
        """
        self.violations.append(
            Violation(
                rule=rule,
                severity=severity,
                message=message,
                file_path=str(self.file_path),
                line=line,
                column=column,
                fix=fix,
                reference=reference
            )
        )

    def check(self, tree: ast.AST) -> List[Violation]:
        """Run checker on AST tree.

        Args:
            tree: AST tree to check

        Returns:
            List of violations found
        """
        self.visit(tree)
        return self.violations


def parse_pep723(source: str) -> dict:
    """Parse PEP 723 metadata from source code.

    Args:
        source: Source code content

    Returns:
        Dict with PEP 723 metadata, or empty dict if not found
    """
    import tomllib

    match = PEP723_PATTERN.search(source)
    if not match or match.group("type") != "script":
        return {}

    lines = match.group("content").splitlines()
    toml_content = "\n".join(
        line[2:] if line.startswith("# ") else line[1:] for line in lines
    )

    try:
        return tomllib.loads(toml_content)
    except tomllib.TOMLDecodeError:
        return {}


def get_function_names(tree: ast.AST) -> Set[str]:
    """Extract all function names from AST.

    Args:
        tree: AST tree

    Returns:
        Set of function names
    """
    functions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.add(node.name)
    return functions


def get_imports(tree: ast.AST) -> Set[str]:
    """Extract all imported module names from AST.

    Args:
        tree: AST tree

    Returns:
        Set of top-level module names
    """
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # Get top-level module (e.g., 'requests' from 'requests.auth')
                module = alias.name.split('.')[0]
                imports.add(module)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split('.')[0]
                imports.add(module)
    return imports


# Python standard library modules (Python 3.11+)
STDLIB_MODULES = frozenset([
    # Core
    'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
    'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'bisect', 'builtins',
    # C-Z
    'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs',
    'codeop', 'collections', 'colorsys', 'compileall', 'concurrent', 'configparser',
    'contextlib', 'contextvars', 'copy', 'copyreg', 'cProfile', 'crypt', 'csv',
    'ctypes', 'curses', 'dataclasses', 'datetime', 'dbm', 'decimal', 'difflib',
    'dis', 'distutils', 'doctest', 'email', 'encodings', 'enum', 'errno',
    'faulthandler', 'fcntl', 'filecmp', 'fileinput', 'fnmatch', 'fractions',
    'ftplib', 'functools', 'gc', 'getopt', 'getpass', 'gettext', 'glob', 'graphlib',
    'grp', 'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http', 'imaplib', 'imghdr',
    'imp', 'importlib', 'inspect', 'io', 'ipaddress', 'itertools', 'json', 'keyword',
    'lib2to3', 'linecache', 'locale', 'logging', 'lzma', 'mailbox', 'mailcap',
    'marshal', 'math', 'mimetypes', 'mmap', 'modulefinder', 'msilib', 'msvcrt',
    'multiprocessing', 'netrc', 'nis', 'nntplib', 'numbers', 'operator', 'optparse',
    'os', 'ossaudiodev', 'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes',
    'pkgutil', 'platform', 'plistlib', 'poplib', 'posix', 'posixpath', 'pprint',
    'profile', 'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc', 'queue',
    'quopri', 'random', 're', 'readline', 'reprlib', 'resource', 'rlcompleter',
    'runpy', 'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex', 'shutil',
    'signal', 'site', 'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver',
    'spwd', 'sqlite3', 'ssl', 'stat', 'statistics', 'string', 'stringprep',
    'struct', 'subprocess', 'sunau', 'symtable', 'sys', 'sysconfig', 'syslog',
    'tabnanny', 'tarfile', 'telnetlib', 'tempfile', 'termios', 'test', 'textwrap',
    'threading', 'time', 'timeit', 'tkinter', 'token', 'tokenize', 'tomllib',
    'trace', 'traceback', 'tracemalloc', 'tty', 'turtle', 'turtledemo', 'types',
    'typing', 'typing_extensions', 'unicodedata', 'unittest', 'urllib', 'uu', 'uuid',
    'venv', 'warnings', 'wave', 'weakref', 'webbrowser', 'winreg', 'winsound',
    'wsgiref', 'xdrlib', 'xml', 'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib',
    # Python 3.11 additions
    'tomli', '_thread',
])
