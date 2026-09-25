"""TEST 35 -- no HypothesisScore/AlphaScore-style combined field exists
anywhere in src/hypothesis/ (Spec #004 SS60, mirrors Spec #003's own SS49
prohibition) -- an AST identifier scan, not just a naming convention."""
import ast
from pathlib import Path

_HYPOTHESIS_SRC = Path(__file__).resolve().parents[2] / "src" / "hypothesis"
_FORBIDDEN_SUBSTRINGS = ("hypothesisscore", "alphascore", "combinedscore", "compositescore")


def test_no_forbidden_score_identifier_anywhere_in_hypothesis_package():
    offenders = []
    for path in _HYPOTHESIS_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.Attribute):
                name = node.attr
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                name = node.name
            if name and any(tok in name.lower() for tok in _FORBIDDEN_SUBSTRINGS):
                offenders.append(f"{path}:{node.lineno}:{name}")
    assert not offenders, f"forbidden score-style identifiers found: {offenders}"
