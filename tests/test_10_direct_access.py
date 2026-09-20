"""TEST 10 -- Direct access test (Spec #001 SS10-11).

Structural check per Radu's clarification (2026-09-20): no module that
could act as a downstream research consumer may import the repository
layer directly through the application's normal interface. Storage- and
adapter-level tests are exempt (they test storage/the adapter itself,
not a stand-in for a downstream consumer) -- that exemption applies to
tests/, never to source under src/.

This runs as an AST scan of the actual import graph rather than relying
on convention, so a future module that bypasses the gateway fails this
test immediately instead of silently leaking look-ahead information.
"""
import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "data_foundation"

# Layers allowed to import the repository layer directly: the model
# layer itself (repository's own home, plus ingestion/adjustment_engine
# which write through it), storage (schema/connection), pit (the gateway
# implementation), and qa. QA is a Data Foundation pipeline stage in its
# own right (see Spec #001 SS1's architecture diagram: adapter -> model
# -> PIT -> QA -> clean/flagged data), not a downstream research
# consumer (SS10-11 names those explicitly: Discovery Engine, Candidate
# Selector, Hypothesis Engine, Backtester, Evaluation Engine) -- it must
# see full raw history to do its job (e.g. detecting a missing bar
# requires scanning the whole observed date range, not an as_of slice).
# adapters/ doesn't import it today but isn't a downstream consumer either way.
ALLOWED_DIRS = {"model", "adapters", "storage", "pit", "qa"}


def _imports_repository(py_file: Path) -> bool:
    tree = ast.parse(py_file.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and "data_foundation.model.repository" in node.module:
                return True
            if node.module == "data_foundation.model" and any(a.name == "repository" for a in node.names):
                return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "data_foundation.model.repository":
                    return True
    return False


def test_no_module_outside_allowed_layers_imports_repository_directly():
    violations = []
    for py_file in SRC_ROOT.rglob("*.py"):
        rel = py_file.relative_to(SRC_ROOT)
        top_level_dir = rel.parts[0] if len(rel.parts) > 1 else None
        if top_level_dir in ALLOWED_DIRS:
            continue
        if _imports_repository(py_file):
            violations.append(str(rel))
    assert violations == [], (
        f"modules outside {ALLOWED_DIRS} import the repository layer directly, "
        f"bypassing the PIT gateway: {violations}"
    )


def test_pit_access_exposes_the_single_gateway_entrypoint():
    from data_foundation.pit import access
    assert hasattr(access, "get_data") and callable(access.get_data)
