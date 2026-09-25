"""TEST 25 -- No Evaluation/Alpha Score (Spec #003 SS49/SS66).

No field anywhere aggregates into a single combined score. AST identifier
scan across all of src/evaluation/ -- mirrors Spec #002's TEST 13/17.
"""
import ast
from pathlib import Path

_FORBIDDEN_SUBSTRINGS = ("alpha_score", "evaluation_score", "combined_score", "edge_score", "overall_score")

_SRC = Path(__file__).resolve().parents[2] / "src" / "evaluation"


def _identifiers_in_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute)):
            names.add(getattr(node, "id", None) or getattr(node, "attr", None) or "")
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
    return names


def test_no_forbidden_score_identifiers_in_evaluation_source():
    for path in _SRC.rglob("*.py"):
        for name in _identifiers_in_file(path):
            lowered = name.lower()
            for forbidden in _FORBIDDEN_SUBSTRINGS:
                assert forbidden not in lowered, f"{path}: forbidden identifier containing {forbidden!r}: {name!r}"
