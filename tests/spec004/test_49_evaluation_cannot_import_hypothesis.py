"""TEST 49 -- src/evaluation/ never imports src/hypothesis/ (Radu's
SS110-F guard: strict one-directional dependency Data Foundation ->
Discovery -> Evaluation -> Hypothesis, never reversed) -- mirrors Spec
#003 TEST 26 (discovery cannot import evaluation), one level further up
the chain."""
import ast
from pathlib import Path

_EVALUATION_SRC = Path(__file__).resolve().parents[2] / "src" / "evaluation"
_DISCOVERY_SRC = Path(__file__).resolve().parents[2] / "src" / "discovery"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_evaluation_never_imports_hypothesis():
    offenders = [
        str(path) for path in _EVALUATION_SRC.rglob("*.py")
        if any(m == "hypothesis" or m.startswith("hypothesis.") for m in _imports(path))
    ]
    assert not offenders, offenders


def test_discovery_never_imports_hypothesis():
    offenders = [
        str(path) for path in _DISCOVERY_SRC.rglob("*.py")
        if any(m == "hypothesis" or m.startswith("hypothesis.") for m in _imports(path))
    ]
    assert not offenders, offenders
