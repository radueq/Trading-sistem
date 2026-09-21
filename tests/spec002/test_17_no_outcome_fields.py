"""TEST 17 -- No outcome fields (Spec #002 SS38/SS2/SS24).

Structural, not conventional: an AST scan asserts no module under
src/discovery/ defines or references an identifier (function name,
variable, dataclass field, attribute, keyword argument) drawn from the
forbidden outcome vocabulary (Spec #002 SS2). Identifiers only -- not
prose in docstrings/comments, which legitimately documents what's
forbidden throughout this codebase.
"""
import ast
from pathlib import Path

DISCOVERY_ROOT = Path(__file__).resolve().parents[2] / "src" / "discovery"

FORBIDDEN_TERMS = [
    "forward_return", "win_rate", "winrate", "expectancy", "profit_factor",
    "sharpe", "max_excursion", "maxexcursion", "drawdown", "alpha_score",
    "alphascore", "backtest", "winner", "loser", "analyst_target",
]


def _identifiers_in(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
    return names


def test_no_forbidden_outcome_identifiers_in_discovery_source():
    violations = []
    for py_file in DISCOVERY_ROOT.rglob("*.py"):
        identifiers = {n.lower() for n in _identifiers_in(py_file)}
        for term in FORBIDDEN_TERMS:
            if any(term in ident for ident in identifiers):
                violations.append((str(py_file.relative_to(DISCOVERY_ROOT.parent.parent)), term))
    assert violations == [], f"forbidden outcome identifiers found in discovery source: {violations}"
