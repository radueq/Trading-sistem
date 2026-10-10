"""TEST 26 -- Discovery cannot import Evaluation (Spec #003 SS10-11/SS66).

Dependency is one-directional: Discovery -> observations -> Evaluation,
never the reverse. Structural, not conventional -- AST import scan.

Corrected in two rounds (joint remediation design section 8/9, #003 G1
/ Top Finding 18 -- GPT's review, relayed by Radu, Stage 5):

Round 1 fixed the collector itself: the previous version called
`ast.walk()` and only ever recorded `ast.ImportFrom.module` -- for
`from X import Y`, that is `X`, never `Y`. A scratch file containing
exactly `from src import evaluation as ev` therefore produced
`{"src"}`, and `"evaluation"` itself was never inspected. Candidates
are built from both the base alone and base+alias per import
statement, so a `src.`-prefixed absolute import and a bare `from src
import evaluation` both resolve to the same namespace as a direct
`import evaluation`.

Round 2 (GPT's CHANGES REQUIRED on round 1, independently verified via
`importlib.util.resolve_name()`) fixed two further defects:

1. The main production test discarded the scanner's own
   `unresolvable` diagnostics entirely -- a relative import that
   climbed beyond its own package root produced the diagnostic
   internally, but nothing on the real test path ever surfaced it, so
   "never silently passed" was not actually true end to end. Fixed by
   routing the directory scan through `_scan_directory()`, which emits
   each diagnostic via `warnings.warn()` -- non-blocking, as designed,
   but no longer discarded.
2. The "climbs to the project's own src/ root" and "exceeds its
   package root" cases are NOT the same case -- they depend on which
   of the two contexts this guard recognizes for the analyzed file's
   own package: the bare one (e.g. `discovery.candidate`) and the
   `src`-prefixed one (`src.discovery.candidate`) -- the same duality
   already used for absolute imports (a leading `src` is a recognized
   defensive form, never assumed unused). Verified by direct execution
   before this round's fix: `resolve_name("...evaluation",
   "discovery.candidate")` raises ImportError (bare context exhausted),
   but `resolve_name("...evaluation", "src.discovery.candidate")`
   resolves to `"src.evaluation"` (the src-prefixed context still has
   one level of headroom) -- a GENUINE, resolvable hit that round 1's
   single-context implementation missed entirely, wrongly classifying
   it as "unresolvable, not flagged." Fixed by resolving a relative
   import's base under BOTH contexts and treating a hit from EITHER as
   forbidden; the `unresolvable` diagnostic now fires only when BOTH
   contexts are beyond their own root. The `src` prefix is still
   stripped only at classification, after resolution, never during the
   climb itself.
"""
import ast
import warnings
from pathlib import Path

import pytest

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


def _relative_base(package_tuple: tuple[str, ...], drop: int, module_parts: list[str]) -> list[str] | None:
    """The base of a relative import's candidate, under ONE package-tuple
    context. None means this context is exhausted (the climb reaches at
    or beyond its own root) -- not a hit, not yet a verdict either way."""
    if drop >= len(package_tuple):
        return None
    return list(package_tuple[: len(package_tuple) - drop]) + module_parts


def _scan_tree(tree: ast.AST, package_tuple: tuple[str, ...], forbidden: str) -> tuple[list[str], list[str]]:
    """Returns (hits, unresolvable).

    `hits` are human-readable descriptions of imports whose resolved
    namespace is the forbidden one. For a relative import, the base is
    resolved under BOTH contexts this guard recognizes for the analyzed
    file's own package: the bare one (`package_tuple`) and the
    `src`-prefixed one (`("src",) + package_tuple`) -- a climb that is
    beyond-root under the bare context can still validly resolve under
    the src-prefixed one, landing on a genuine hit (verified against
    real Python: `resolve_name("...evaluation", "discovery.candidate")`
    raises, but `resolve_name("...evaluation", "src.discovery.
    candidate")` resolves to `"src.evaluation"`). A hit from EITHER
    context counts. `unresolvable` is populated only when BOTH contexts
    are beyond their own root -- an informational diagnostic, never
    silently flagged and never silently passed (surfaced by the caller,
    see `_scan_directory()`, not swallowed here).
    """
    hits: list[str] = []
    unresolvable: list[str] = []
    src_prefixed = ("src", *package_tuple)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden_candidate(alias.name.split("."), forbidden):
                    hits.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module_parts = node.module.split(".") if node.module else []
            if node.level == 0:
                bases = [module_parts]
            else:
                drop = node.level - 1
                bases = [
                    b for b in (
                        _relative_base(package_tuple, drop, module_parts),
                        _relative_base(src_prefixed, drop, module_parts),
                    )
                    if b is not None
                ]
                if not bases:
                    unresolvable.append(
                        "relative import climbs above its package root under "
                        "both recognized contexts, cannot verify architectural "
                        f"direction: level={node.level} module={node.module!r} "
                        f"package={'.'.join(package_tuple) or '<root>'} "
                        f"(also tried src-prefixed {'.'.join(src_prefixed)})"
                    )
                    continue
            candidates = list(bases) + [base + [alias.name] for base in bases for alias in node.names]
            if any(_is_forbidden_candidate(c, forbidden) for c in candidates):
                names = ", ".join(alias.name for alias in node.names)
                hits.append(f"from {'.' * node.level}{node.module or ''} import {names}")
    return hits, unresolvable


def _scan_file(path: Path, src_root: Path, forbidden: str) -> tuple[list[str], list[str]]:
    tree = ast.parse(path.read_text(), filename=str(path))
    return _scan_tree(tree, _package_tuple_for(path, src_root), forbidden)


def _scan_directory(root: Path, src_root: Path, forbidden: str) -> list[str]:
    """Scans every .py file under `root`. Returns the hits (what the
    caller must fail on). Every `unresolvable` diagnostic is surfaced
    via `warnings.warn()` -- never gating, per the design's own
    non-blocking contract, but never silently dropped either."""
    all_hits: list[str] = []
    for path in sorted(root.rglob("*.py")):
        hits, unresolvable = _scan_file(path, src_root, forbidden)
        all_hits.extend(f"{path.relative_to(src_root)}: {hit}" for hit in hits)
        for diagnostic in unresolvable:
            warnings.warn(f"{path.relative_to(src_root)}: {diagnostic}", stacklevel=2)
    return all_hits


def test_no_discovery_module_imports_evaluation():
    all_hits = _scan_directory(_DISCOVERY_SRC, _SRC_ROOT, _FORBIDDEN)
    assert not all_hits, "Discovery must never depend on Evaluation:\n" + "\n".join(all_hits)


def test_unresolvable_relative_import_is_warned_not_silently_passed(tmp_path):
    """Exercises the SAME entry point the main test above calls --
    `_scan_directory()` -- not just the helper's own return value, per
    GPT's own explicit requirement: checking the returned list alone
    does not prove the real test path surfaces the diagnostic."""
    offender = tmp_path / "sub" / "deep" / "probe.py"
    offender.parent.mkdir(parents=True)
    # package tuple ("sub", "deep"), length 2 -- beyond-root under BOTH
    # contexts requires drop = level-1 >= 2+1 = 3, i.e. level >= 4.
    offender.write_text("from ....evaluation import X\n")
    with pytest.warns(UserWarning, match="package root"):
        hits = _scan_directory(tmp_path, tmp_path, _FORBIDDEN)
    assert not hits


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
    # (Both recognized contexts agree here -- drop=0 is below either
    # context's root, so the src-prefixed context strips back down to
    # the exact same candidate; see _scan_tree's own docstring.)
    assert not _hits_for("from .evaluation import X\n")


def test_not_flagged_relative_two_levels_internal_sibling():
    # level=2 resolves to discovery.evaluation -- still first component
    # "discovery", one level further up. Same both-contexts-agree
    # reasoning as the one-level case above.
    assert not _hits_for("from ..evaluation import X\n")


def test_flagged_relative_import_resolves_via_src_prefixed_context():
    # level=3 from discovery.candidate (bare length 2): drop=2 exhausts
    # the BARE context (2 >= 2), but the src-prefixed context
    # (discovery.candidate.-> src.discovery.candidate, length 3) still
    # has exactly one level of headroom left (2 < 3), landing on
    # "src.evaluation" -- stripped to "evaluation" at classification.
    # Verified against real Python before writing this test:
    # importlib.util.resolve_name("...evaluation", "discovery.candidate")
    # raises, but resolve_name("...evaluation", "src.discovery.candidate")
    # resolves to "src.evaluation". This is the genuine "climbs all the
    # way to the project's own src/ root and then into evaluation" case
    # from the design doc's own matrix -- round 1 wrongly folded it into
    # the unresolvable/beyond-root case by only ever checking the bare
    # context.
    assert _hits_for("from ...evaluation import X\n")


def test_relative_import_beyond_package_root_in_both_contexts_is_unresolvable_not_silently_passed():
    # level=4 from discovery.candidate: drop=3 exhausts BOTH the bare
    # context (3 >= 2) AND the src-prefixed one (3 >= 3) -- genuinely
    # beyond either recognized root. Surfaced as its own diagnostic,
    # never silently assumed forbidden, never silently passed as safe
    # (see test_unresolvable_relative_import_is_warned_not_silently_passed
    # above for proof that the real scan path surfaces this, not just
    # this helper's own return value).
    source = "from ....evaluation import X\n"
    assert not _hits_for(source)
    unresolvable = _unresolvable_for(source)
    assert unresolvable
    assert "package root" in unresolvable[0]
