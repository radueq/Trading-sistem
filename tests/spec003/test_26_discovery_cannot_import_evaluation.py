"""TEST 26 -- Discovery cannot import Evaluation (Spec #003 SS10-11/SS66).

Dependency is one-directional: Discovery -> observations -> Evaluation,
never the reverse. Structural, not conventional -- AST import scan.

Corrected this round (joint remediation design section 8/9, #003 G1 /
Top Finding 18 -- GPT's review, relayed by Radu, Stage 5): the previous
collector called `ast.walk()` and only ever recorded `ast.ImportFrom.
module` -- for `from X import Y`, that is `X`, never `Y`. A scratch file
containing exactly `from src import evaluation as ev` therefore produced
`{"src"}`, and `"evaluation"` itself was never inspected. Candidates are
now built from both the base alone and base+alias per import statement,
relative imports are resolved against the analyzed file's own package
tuple (filesystem existence is never a gate, only an optional diagnostic
enrichment), and a leading `src` component is stripped before the
first-component check -- so a `src.`-prefixed absolute import and a bare
`from src import evaluation` both resolve to the same namespace as a
direct `import evaluation`.
"""
import ast
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
_DISCOVERY_SRC = _SRC_ROOT / "discovery"
_FORBIDDEN = "evaluation"


def _package_tuple_for(path: Path, src_root: Path) -> tuple[str, ...]:
    """E.g. src/evaluation/baseline/universe.py -> ("evaluation", "baseline")."""
    return path.resolve().relative_to(src_root.resolve()).parent.parts


def _is_forbidden_candidate(candidate: list[str], forbidden: str) -> bool:
    if candidate and candidate[0] == "src":
        candidate = candidate[1:]
    return bool(candidate) and candidate[0] == forbidden


def _scan_tree(tree: ast.AST, package_tuple: tuple[str, ...], forbidden: str) -> tuple[list[str], list[str]]:
    """Returns (hits, unresolvable).

    `hits` are human-readable descriptions of imports whose resolved
    namespace is the forbidden one. `unresolvable` are relative imports
    that climb at or beyond their own package root -- an informational
    diagnostic only, never silently flagged and never silently passed.
    """
    hits: list[str] = []
    unresolvable: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden_candidate(alias.name.split("."), forbidden):
                    hits.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module.split(".") if node.module else []
            else:
                drop = node.level - 1
                if drop >= len(package_tuple):
                    unresolvable.append(
                        "relative import climbs above its package root, cannot verify "
                        f"architectural direction: level={node.level} module={node.module!r} "
                        f"package={'.'.join(package_tuple) or '<root>'}"
                    )
                    continue
                base = list(package_tuple[: len(package_tuple) - drop])
                if node.module:
                    base += node.module.split(".")
            candidates = [base] + [base + [alias.name] for alias in node.names]
            if any(_is_forbidden_candidate(c, forbidden) for c in candidates):
                names = ", ".join(alias.name for alias in node.names)
                hits.append(f"from {'.' * node.level}{node.module or ''} import {names}")
    return hits, unresolvable


def _scan_file(path: Path, src_root: Path, forbidden: str) -> tuple[list[str], list[str]]:
    tree = ast.parse(path.read_text(), filename=str(path))
    return _scan_tree(tree, _package_tuple_for(path, src_root), forbidden)


def test_no_discovery_module_imports_evaluation():
    all_hits = []
    for path in sorted(_DISCOVERY_SRC.rglob("*.py")):
        hits, _unresolvable = _scan_file(path, _SRC_ROOT, _FORBIDDEN)
        all_hits.extend(f"{path.relative_to(_SRC_ROOT)}: {hit}" for hit in hits)
    assert not all_hits, "Discovery must never depend on Evaluation:\n" + "\n".join(all_hits)


# -- Regression matrix (joint remediation design section 8/9, #003 G1) --
# A real, existing 2-deep package is used for the relative-import cases
# below, so the climb arithmetic is exercised against actual project
# structure rather than a synthetic shape.
_PKG = ("discovery", "candidate")


def _hits_for(source: str, package_tuple: tuple[str, ...] = _PKG) -> list[str]:
    hits, _unresolvable = _scan_tree(ast.parse(source), package_tuple, _FORBIDDEN)
    return hits


def _unresolvable_for(source: str, package_tuple: tuple[str, ...] = _PKG) -> list[str]:
    _hits, unresolvable = _scan_tree(ast.parse(source), package_tuple, _FORBIDDEN)
    return unresolvable


def test_flagged_bare_import():
    assert _hits_for("import evaluation\n")


def test_flagged_from_submodule_import():
    # Mirrors the design doc's own worked example one level down --
    # evaluation.registry.signatures is a real, existing module.
    assert _hits_for("from evaluation.registry import signatures\n")


def test_flagged_absolute_src_prefixed():
    assert _hits_for("from src.evaluation import X\n")


def test_flagged_from_src_import_evaluation_as_alias_scratch_file(tmp_path):
    """The exact scratch-file probe that demonstrated the original bug
    (audit_spec003_requirement_code_test.md Top Finding 18): the old
    collector only ever recorded `ast.ImportFrom.module` ("src"), never
    `.names` ("evaluation" aliased to "ev") -- so `_imported_modules()`
    returned `{"src"}` and this exact import was invisible to the guard.
    The corrected base+alias candidate construction must catch it."""
    probe = tmp_path / "scratch_probe.py"
    probe.write_text("from src import evaluation as ev\n")
    hits, _unresolvable = _scan_file(probe, tmp_path, _FORBIDDEN)
    assert hits, "from src import evaluation as ev must be caught -- this is the exact case the old collector missed"


def test_not_flagged_unrelated_vendor_namespace():
    # Shares the literal name one level down, under an unrelated
    # top-level namespace -- not the project's own evaluation package.
    assert not _hits_for("from vendor import evaluation\n")


def test_not_flagged_relative_one_level_internal_sibling():
    # From discovery.candidate, level=1 resolves to
    # discovery.candidate.evaluation -- first component "discovery": a
    # same-package sibling module, confusingly named but internal.
    assert not _hits_for("from .evaluation import X\n")


def test_not_flagged_relative_two_levels_internal_sibling():
    # level=2 resolves to discovery.evaluation -- still first component
    # "discovery", one level further up.
    assert not _hits_for("from ..evaluation import X\n")


def test_relative_import_beyond_package_root_is_unresolvable_not_silently_passed():
    # level=3 from a 2-deep package (discovery.candidate): drop=2 >=
    # len(package_tuple)=2 -- beyond the top-level package. Verified by
    # execution against real Python (importlib.util.resolve_name raises
    # "attempted relative import beyond top-level package" at exactly
    # this level for this package depth, confirmed before writing this
    # test). Surfaced as its own diagnostic -- never silently assumed
    # forbidden, never silently passed as safe.
    source = "from ...evaluation import X\n"
    assert not _hits_for(source)
    unresolvable = _unresolvable_for(source)
    assert unresolvable
    assert "package root" in unresolvable[0]
