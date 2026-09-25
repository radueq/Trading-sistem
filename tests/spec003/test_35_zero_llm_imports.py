"""TEST 35 -- Zero LLM runtime imports (Spec #003 SS61/SS66).

AST import scan -- no anthropic/openai/google.generativeai/cohere/
langchain import anywhere under src/evaluation/. Mirrors Spec #002's
TEST 21.
"""
import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "evaluation"
_FORBIDDEN = {"anthropic", "openai", "google.generativeai", "cohere", "langchain"}


def test_no_llm_imports_in_evaluation_source():
    for path in _SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in {m.split(".")[0] for m in _FORBIDDEN}, f"{path}: forbidden import {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in {m.split(".")[0] for m in _FORBIDDEN}, f"{path}: forbidden import {node.module}"
