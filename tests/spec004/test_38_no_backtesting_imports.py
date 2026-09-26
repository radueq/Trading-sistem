"""TEST 38 -- no backtesting-engine IMPORT or callable/class in
src/hypothesis/ (Spec #004 SS2/SS99 -- #004 forms hypotheses, it does not
backtest them). Docstring prose that explains this exact boundary (e.g.
"#005 will backtest these variants") is expected and allowed -- only
actual imports and function/class definitions are scanned, via AST, not
a raw text grep.

Spec #005 v1.0 Batch 1 (2026-09-26, approved by Radu) now exists as
`src/backtest/` -- the SECOND function below no longer asserts the
package's total absence (that was only ever a proxy for "no premature
#005 imports," true at #004's own acceptance time, now obsolete by
design). The invariant that actually matters -- #004 never imports
#005 -- is unchanged and is exactly what
`test_no_backtesting_related_import_or_definition()` above already
checks; `tests/spec005/test_10_dependency_and_llm_broker_guards.py`
checks the same dependency direction from the other side."""
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


def test_no_alternate_named_backtesting_package_exists():
    """`backtesting` (with the "-ing") was never the name Spec #005
    actually used -- confirms no stray duplicate/alternate package was
    ever created under that name. `src/backtest/` itself is the real,
    approved Spec #005 package and is expected to exist from here on."""
    repo_src = _HYPOTHESIS_SRC.parent
    assert not (repo_src / "backtesting").exists()
