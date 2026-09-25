"""TEST 38 -- no backtesting-engine IMPORT or callable/class in
src/hypothesis/ (Spec #004 SS2/SS99 -- #004 forms hypotheses, it does not
backtest them, and Spec #005 does not exist as a module yet). Docstring
prose that explains this exact boundary (e.g. "#005 will backtest these
variants") is expected and allowed -- only actual imports and
function/class definitions are scanned, via AST, not a raw text grep."""
import ast
from pathlib import Path

_HYPOTHESIS_SRC = Path(__file__).resolve().parents[2] / "src" / "hypothesis"
_FORBIDDEN_TOKENS = ("backtest", "walk_forward", "walkforward")


def test_no_backtesting_related_import_or_definition():
    offenders = []
    for path in _HYPOTHESIS_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                names = [node.name]
            for name in names:
                if any(tok in name.lower() for tok in _FORBIDDEN_TOKENS):
                    offenders.append(f"{path}:{node.lineno}: {name!r}")
    assert not offenders, offenders


def test_no_backtesting_package_exists_yet():
    repo_src = _HYPOTHESIS_SRC.parent
    assert not (repo_src / "backtesting").exists()
    assert not (repo_src / "backtest").exists()
