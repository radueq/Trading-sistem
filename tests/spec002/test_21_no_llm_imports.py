"""TEST 21 -- No LLM runtime imports (Spec #002 SS41).

Not numbered in SS38's required-test list, but stated as a hard rule:
"If LLM-related imports appear in #002 runtime code: FAIL." Structural
AST scan, same style as TEST 17/18.
"""
import ast
from pathlib import Path

DISCOVERY_ROOT = Path(__file__).resolve().parents[2] / "src" / "discovery"
FORBIDDEN_IMPORT_PREFIXES = ("anthropic", "openai", "google.generativeai", "cohere", "langchain")


def test_no_llm_imports_in_discovery_source():
    violations = {}
    for py_file in DISCOVERY_ROOT.rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        hits = []
        for node in ast.walk(tree):
            module_names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                module_names.append(node.module)
            elif isinstance(node, ast.Import):
                module_names.extend(alias.name for alias in node.names)
            for name in module_names:
                if any(name.startswith(prefix) for prefix in FORBIDDEN_IMPORT_PREFIXES):
                    hits.append(name)
        if hits:
            violations[str(py_file)] = hits
    assert violations == {}, f"LLM-related imports found in discovery runtime code: {violations}"
