"""TEST 26 -- Discovery cannot import Evaluation (Spec #003 SS10-11/SS66).

Dependency is one-directional: Discovery -> observations -> Evaluation,
never the reverse. Structural, not conventional -- AST import scan.
"""
import ast
from pathlib import Path

_DISCOVERY_SRC = Path(__file__).resolve().parents[2] / "src" / "discovery"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_no_discovery_module_imports_evaluation():
    for path in _DISCOVERY_SRC.rglob("*.py"):
        for module in _imported_modules(path):
            assert not module.startswith("evaluation"), f"{path} imports {module!r} -- Discovery must never depend on Evaluation"
