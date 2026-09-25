"""TEST 39 -- zero LLM imports anywhere in src/hypothesis/ (Spec #004
SS88-89/SS93/SS110-G -- the deterministic core never calls an LLM API;
AI orchestration, if it ever exists, lives strictly outside this
package) -- an AST import scan, mirroring Spec #003 TEST 35."""
import ast
from pathlib import Path

_HYPOTHESIS_SRC = Path(__file__).resolve().parents[2] / "src" / "hypothesis"
_FORBIDDEN_MODULES = ("anthropic", "openai", "google.generativeai", "cohere", "langchain")


def test_no_llm_sdk_import_anywhere_in_hypothesis_package():
    offenders = []
    for path in _HYPOTHESIS_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if any(name == m or name.startswith(m + ".") for m in _FORBIDDEN_MODULES):
                    offenders.append(f"{path}: imports {name!r}")
    assert not offenders, offenders


def test_no_agents_adapter_package_exists_yet():
    assert not (_HYPOTHESIS_SRC / "agents").exists(), "Spec #004 SS93-94: no GPT/Claude API adapter is built yet"
