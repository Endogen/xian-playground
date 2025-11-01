"""Utility helpers to lint contracts using the custom Xian linter."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LINTER_ROOT = PROJECT_ROOT.parent / "xian-linter"
_LINTER_AVAILABLE = LINTER_ROOT.exists()
if _LINTER_AVAILABLE:
    linter_path = str(LINTER_ROOT)
    if linter_path not in sys.path:
        sys.path.append(linter_path)
    from xian_linter.custom import Linter  # type: ignore  # noqa: E402
else:
    Linter = None  # type: ignore


def lint_contract(code: str) -> List[str]:
    """Run the AST-based linter defined in xian-linter."""

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        line = exc.lineno or 0
        column = exc.offset or 0
        return [f"Line {line}: Syntax error at column {column}: {exc.msg}"]

    if Linter is None:
        return ["Linter dependency not available on this system."]

    linter = Linter()
    violations = linter.check(tree) or []
    return [violation.strip() for violation in violations]
