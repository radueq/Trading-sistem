"""TEST 30 -- Total-return prohibition (Spec #003 SS16/SS66).

`total_return_adjusted_close` (EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH,
Spec #001) is never accessed anywhere under src/evaluation/ -- AST
attribute-access scan, mirrors Spec #002's TEST 19.
"""
import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "evaluation"


def test_evaluation_never_accesses_total_return_adjusted_close():
    for path in _SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "total_return_adjusted_close":
                raise AssertionError(f"{path}: total_return_adjusted_close accessed -- forbidden (EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH)")
