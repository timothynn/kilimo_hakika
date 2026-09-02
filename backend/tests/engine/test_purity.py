"""The engine's purity is a promise, so it is a test.

CLAUDE.md requires the verdict path to be deterministic and UI-agnostic. That is
easy to write and easy to erode: one `import httpx` for a "quick lookup", one
`date.today()` default, and the verdict stops being replayable. This walks the
AST of every engine module and fails the build instead.
"""

from __future__ import annotations

import ast
import pathlib

ENGINE = pathlib.Path(__file__).resolve().parents[2] / "src" / "kilimo_hakika" / "engine"

ALLOWED_TOP_LEVEL = {
    "__future__",
    "dataclasses",
    "datetime",
    "decimal",
    "enum",
    "typing",
    "collections",
    "math",
    "re",
}

# Reading a clock inside the engine would make the same inputs produce different
# verdicts on different days. The travel date is an input for exactly this reason.
FORBIDDEN_CALLS = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("datetime", "today"),
    ("date", "today"),
    ("time", "time"),
    ("random", "random"),
    ("random", "choice"),
    ("os", "getenv"),
}


def engine_modules() -> list[pathlib.Path]:
    return sorted(ENGINE.glob("*.py"))


def test_engine_has_modules():
    assert engine_modules(), "engine package not found"


def test_engine_imports_stdlib_only():
    offences: list[str] = []
    for path in engine_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in ALLOWED_TOP_LEVEL:
                        offences.append(f"{path.name}:{node.lineno} import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # relative import inside the engine
                    continue
                root = (node.module or "").split(".")[0]
                if root not in ALLOWED_TOP_LEVEL:
                    offences.append(f"{path.name}:{node.lineno} from {node.module} import ...")
    assert not offences, "engine must import stdlib only:\n  " + "\n  ".join(offences)


def test_engine_reads_no_clock_and_no_randomness():
    offences: list[str] = []
    for path in engine_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                target = node.func
                owner = (
                    getattr(target.value, "id", None)
                    or getattr(getattr(target.value, "attr", None), "__str__", lambda: None)()
                )
                if (owner, target.attr) in FORBIDDEN_CALLS:
                    offences.append(f"{path.name}:{node.lineno} {owner}.{target.attr}()")
    assert not offences, "engine must not read a clock or randomness:\n  " + "\n  ".join(offences)


def test_engine_module_graph_is_closed():
    """No engine module may import from the api, persistence or assistant layers."""
    forbidden = ("kilimo_hakika.api", "kilimo_hakika.persistence", "kilimo_hakika.assistant")
    for path in engine_modules():
        source = path.read_text(encoding="utf-8")
        for name in forbidden:
            assert name not in source, f"{path.name} references {name}"


def test_engine_is_importable_without_optional_dependencies():
    """The engine must load with no database driver, web framework or SDK present."""
    for module in ("fastapi", "psycopg", "anthropic", "httpx", "pydantic"):
        assert not any(module in str(path.read_text(encoding="utf-8")) for path in engine_modules()), (
            f"engine mentions {module}"
        )
