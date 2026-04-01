"""Validate a generated autoresearch project structure and content."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path


def _check_file_exists(path: Path, errors: list[str]) -> bool:
    if not path.is_file():
        errors.append(f"Missing required file: {path.name}")
        return False
    return True


def _validate_prepare(path: Path, errors: list[str], warnings: list[str]) -> None:
    source = path.read_text()

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        errors.append(f"prepare.py has a syntax error: {exc}")
        return

    # Check for TIME_BUDGET constant
    has_time_budget = False
    has_metric_name = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id == "TIME_BUDGET":
                        has_time_budget = True
                    elif target.id == "METRIC_NAME":
                        has_metric_name = True

    if not has_time_budget:
        errors.append("prepare.py must define a TIME_BUDGET constant")
    if not has_metric_name:
        errors.append("prepare.py must define a METRIC_NAME constant")

    # Check for an evaluate function
    has_eval = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("evaluate")
        for node in ast.walk(tree)
    )
    if not has_eval:
        errors.append("prepare.py must define an evaluate function (e.g. evaluate, evaluate_bpb)")

    # Check for greppable metric output pattern
    if "METRIC_NAME" not in source and not re.search(r'print\(f"[^"]*:', source):
        warnings.append(
            "prepare.py should document the metric output format: "
            'print(f"{METRIC_NAME}: {score:.6f}")'
        )


def _validate_train(path: Path, errors: list[str], warnings: list[str]) -> None:
    source = path.read_text()

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        errors.append(f"train.py has a syntax error: {exc}")
        return

    # Check it imports from prepare
    imports_prepare = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "prepare":
            imports_prepare = True
            break

    if not imports_prepare:
        warnings.append("train.py should import from prepare (e.g. from prepare import evaluate, TIME_BUDGET)")

    # Check for local module imports (not stdlib, not prepare)
    stdlib_top_level = _get_stdlib_modules()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top not in stdlib_top_level and top != "prepare":
                # It's a third-party or local import — third-party is fine
                pass
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in stdlib_top_level and top != "prepare":
                    pass


def _validate_program(path: Path, errors: list[str], warnings: list[str]) -> None:
    content = path.read_text().lower()

    required_concepts = {
        "experiment loop": ["loop", "experiment"],
        "metric definition": ["metric", "lower is better"],
        "simplicity criterion": ["simplicity", "simpl"],
        "never stop": ["never stop", "indefinitely", "do not stop"],
    }

    for concept, keywords in required_concepts.items():
        if not any(kw in content for kw in keywords):
            warnings.append(f"program.md should mention: {concept}")

    # Check for results.tsv logging format
    if "results.tsv" not in content and "results" not in content:
        warnings.append("program.md should define the results logging format (results.tsv)")

    # Check for git-based tracking
    if "git" not in content:
        errors.append("program.md must describe git-based experiment tracking (commit/reset)")


def _get_stdlib_modules() -> set[str]:
    """Return a set of top-level stdlib module names."""
    return {
        "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio",
        "asyncore", "atexit", "base64", "bdb", "binascii", "binhex",
        "bisect", "builtins", "bz2", "calendar", "cgi", "cgitb", "chunk",
        "cmath", "cmd", "code", "codecs", "codeop", "collections",
        "colorsys", "compileall", "concurrent", "configparser", "contextlib",
        "contextvars", "copy", "copyreg", "cProfile", "crypt", "csv",
        "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal",
        "difflib", "dis", "distutils", "doctest", "email", "encodings",
        "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput",
        "fnmatch", "fractions", "ftplib", "functools", "gc", "getopt",
        "getpass", "gettext", "glob", "graphlib", "grp", "gzip",
        "hashlib", "heapq", "hmac", "html", "http", "idlelib", "imaplib",
        "imghdr", "imp", "importlib", "inspect", "io", "ipaddress",
        "itertools", "json", "keyword", "lib2to3", "linecache", "locale",
        "logging", "lzma", "mailbox", "mailcap", "marshal", "math",
        "mimetypes", "mmap", "modulefinder", "multiprocessing", "netrc",
        "nis", "nntplib", "numbers", "operator", "optparse", "os",
        "ossaudiodev", "pathlib", "pdb", "pickle", "pickletools", "pipes",
        "pkgutil", "platform", "plistlib", "poplib", "posix", "posixpath",
        "pprint", "profile", "pstats", "pty", "pwd", "py_compile",
        "pyclbr", "pydoc", "queue", "quopri", "random", "re", "readline",
        "reprlib", "resource", "rlcompleter", "runpy", "sched", "secrets",
        "select", "selectors", "shelve", "shlex", "shutil", "signal",
        "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver",
        "spwd", "sqlite3", "ssl", "stat", "statistics", "string",
        "stringprep", "struct", "subprocess", "sunau", "symtable", "sys",
        "sysconfig", "syslog", "tabnanny", "tarfile", "telnetlib", "tempfile",
        "termios", "test", "textwrap", "threading", "time", "timeit",
        "tkinter", "token", "tokenize", "tomllib", "trace", "traceback",
        "tracemalloc", "tty", "turtle", "turtledemo", "types", "typing",
        "unicodedata", "unittest", "urllib", "uu", "uuid", "venv",
        "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound",
        "wsgiref", "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile",
        "zipimport", "zlib", "_thread",
    }


def validate_project(project_dir: Path) -> dict[str, object]:
    """Validate an autoresearch project. Returns structured result."""
    errors: list[str] = []
    warnings: list[str] = []

    prepare = project_dir / "prepare.py"
    train = project_dir / "train.py"
    program = project_dir / "program.md"

    has_prepare = _check_file_exists(prepare, errors)
    has_train = _check_file_exists(train, errors)
    has_program = _check_file_exists(program, errors)

    if has_prepare:
        _validate_prepare(prepare, errors, warnings)
    if has_train:
        _validate_train(train, errors, warnings)
    if has_program:
        _validate_program(program, errors, warnings)

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "files_checked": {
            "prepare.py": has_prepare,
            "train.py": has_train,
            "program.md": has_program,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an autoresearch project")
    parser.add_argument("--dir", required=True, help="Path to the autoresearch project directory")
    args = parser.parse_args()

    project_dir = Path(args.dir).resolve()
    if not project_dir.is_dir():
        print(json.dumps({"ok": False, "errors": [f"Directory not found: {project_dir}"]}, indent=2))
        sys.exit(1)

    result = validate_project(project_dir)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
