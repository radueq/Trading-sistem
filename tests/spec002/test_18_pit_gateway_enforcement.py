"""TEST 18 -- PIT gateway enforcement (Spec #002 SS38/SS7).

No module under src/discovery/ may import data_foundation.model.repository
or data_foundation.storage.db directly -- only data_foundation.pit.access.
Structural, mirrors Spec #001's TEST 10 (tests/test_10_direct_access.py).
"""
import ast
import inspect
from pathlib import Path

DISCOVERY_ROOT = Path(__file__).resolve().parents[2] / "src" / "discovery"
FORBIDDEN_MODULES = ("data_foundation.model.repository", "data_foundation.storage.db")


def _forbidden_imports(py_file: Path) -> list[str]:
    tree = ast.parse(py_file.read_text())
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            hits.extend(f for f in FORBIDDEN_MODULES if f in node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                hits.extend(f for f in FORBIDDEN_MODULES if f in alias.name)
    return hits


def test_discovery_modules_only_use_pit_access():
    violations = {}
    for py_file in DISCOVERY_ROOT.rglob("*.py"):
        hits = _forbidden_imports(py_file)
        if hits:
            violations[str(py_file)] = hits
    assert violations == {}, f"modules under src/discovery/ bypass the PIT gateway: {violations}"


def test_discovery_engine_uses_pit_access():
    from discovery import engine
    source = inspect.getsource(engine)
    assert "data_foundation.pit import access" in source
