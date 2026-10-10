"""TEST 49 -- src/evaluation/ (and src/discovery/) never import
src/hypothesis/ (Radu's SS110-F guard: strict one-directional dependency
Data Foundation -> Discovery -> Evaluation -> Hypothesis, never
reversed) -- mirrors Spec #003 TEST 26 (discovery cannot import
evaluation), one level further up the chain.

Corrected in Stage 7 (joint remediation design section 8; decision
registry F1; authorized by Radu 2026-10-10). The previous collector had
the SAME defect TEST 26 had before Stage 5: it recorded only
`ast.ImportFrom.module` and ignored `node.level` entirely. Reproduced by
execution on `28987a8` over the section-8 matrix, 5 of 9 cases wrong:
`from src.hypothesis import X` and `from src import hypothesis as h`
NOT flagged (false negatives -- the second collected only `{"src"}`);
`from .hypothesis import X`, `from ..hypothesis import X` (internal
`evaluation` siblings) and `from ....hypothesis import X` (beyond both
roots) all FLAGGED (false positives -- the relative level was never
applied, so every relative `...hypothesis` looked like a top-level
`hypothesis`).

The algorithm is NOT re-implemented here: this module reuses TEST 26's
own scanner (`_scan_tree()`/`_scan_file()`/`_scan_directory()`), the
exact code GPT ACCEPTED at Stage 5 round 2 -- base+alias candidate
construction, the leading-`src` strip at classification only, relative
imports resolved under BOTH recognized contexts (bare and `src`-
prefixed) with a hit from EITHER counting, and the `unresolvable`
diagnostic (both contexts beyond root) surfaced via `warnings.warn()`
on the real scan path, never gating, never silently dropped. One
implementation for both guards, so the two cannot drift; only the
forbidden namespace and the scanned trees differ.

F1 (decision registry F1): the bare top-level name `hypothesis` is
RESERVED, by declared project convention, for this project's own
package, for this guard. The third-party property-based testing library
of the same name on PyPI is not installed and not a declared
dependency (checked again this round: `pip show hypothesis` -> not
found; absent from requirements.txt). If it is ever added, a bare
`import hypothesis` meaning the library is AST-identical to this
project's own unqualified import style -- the convention must then be
re-examined. The note sits at the dependency-management surface
(requirements.txt); `test_f1_reserved_name_trigger_condition_has_not_
fired` below fails if the library ever becomes a declared dependency,
so the re-examination cannot be skipped silently.
"""
import ast
import re
import tomllib
from pathlib import Path

import pytest

from spec003.test_26_discovery_cannot_import_evaluation import _scan_directory, _scan_file, _scan_tree

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"
_EVALUATION_SRC = _SRC_ROOT / "evaluation"
_DISCOVERY_SRC = _SRC_ROOT / "discovery"
_FORBIDDEN = "hypothesis"


def test_evaluation_never_imports_hypothesis():
    all_hits = _scan_directory(_EVALUATION_SRC, _SRC_ROOT, _FORBIDDEN)
    assert not all_hits, "Evaluation must never depend on Hypothesis:\n" + "\n".join(all_hits)


def test_discovery_never_imports_hypothesis():
    all_hits = _scan_directory(_DISCOVERY_SRC, _SRC_ROOT, _FORBIDDEN)
    assert not all_hits, "Discovery must never depend on Hypothesis:\n" + "\n".join(all_hits)


def test_unresolvable_relative_import_is_warned_not_silently_passed(tmp_path):
    """Through `_scan_directory()` -- the SAME entry point the production
    tests above call -- not only the helper's return value."""
    offender = tmp_path / "sub" / "deep" / "probe.py"
    offender.parent.mkdir(parents=True)
    offender.write_text("from ....hypothesis import X\n")  # drop=3 >= 2 (bare) and >= 3 (src-prefixed)
    with pytest.warns(UserWarning, match="package root"):
        hits = _scan_directory(tmp_path, tmp_path, _FORBIDDEN)
    assert not hits


# -- Regression matrix (joint remediation design section 8, consolidated
# TEST 26/TEST 49 matrix, `hypothesis` namespace). Relative cases are
# analyzed from the real, existing 2-deep package evaluation.baseline --
# the design's own worked-example package.
_PKG = ("evaluation", "baseline")


def _hits_for(source: str, package_tuple: tuple[str, ...] = _PKG) -> list[str]:
    hits, _unresolvable = _scan_tree(ast.parse(source), package_tuple, _FORBIDDEN)
    return hits


def _unresolvable_for(source: str, package_tuple: tuple[str, ...] = _PKG) -> list[str]:
    _hits, unresolvable = _scan_tree(ast.parse(source), package_tuple, _FORBIDDEN)
    return unresolvable


def test_flagged_bare_import():
    assert _hits_for("import hypothesis\n")


def test_flagged_from_submodule_import():
    assert _hits_for("from hypothesis.registry import hypotheses\n")


def test_flagged_absolute_src_prefixed():
    assert _hits_for("from src.hypothesis import X\n")


def test_flagged_from_src_import_hypothesis_as_alias_scratch_file(tmp_path):
    """The base+alias case on a real file: the pre-Stage-7 collector
    recorded only `{"src"}` for this exact import."""
    probe = tmp_path / "scratch_probe.py"
    probe.write_text("from src import hypothesis as h\n")
    hits, _unresolvable = _scan_file(probe, tmp_path, _FORBIDDEN)
    assert hits, "from src import hypothesis as h must be caught"


def test_flagged_not_yet_written_submodule():
    """Section 8's own motivating case: filesystem existence is never a
    gate -- a violation targeting a module not written yet is still a
    violation."""
    assert not (_SRC_ROOT / "hypothesis" / "not_yet_written_module.py").exists()
    assert _hits_for("from hypothesis.not_yet_written_module import X\n")


def test_not_flagged_unrelated_vendor_namespace():
    assert not _hits_for("from vendor import hypothesis\n")
    assert not _hits_for("import vendor.hypothesis\n")


def test_not_flagged_relative_one_level_internal_sibling():
    # evaluation.baseline.hypothesis -- an evaluation-internal module.
    assert not _hits_for("from .hypothesis import X\n")


def test_not_flagged_relative_two_levels_internal_sibling():
    # evaluation.hypothesis -- still evaluation-internal.
    assert not _hits_for("from ..hypothesis import X\n")


def test_flagged_relative_import_resolves_via_src_prefixed_context():
    # level=3 from evaluation.baseline: the bare context is exhausted
    # (drop 2 >= 2), the src-prefixed one is not (2 < 3). Verified
    # against real Python before writing this test:
    # importlib.util.resolve_name("...hypothesis", "evaluation.baseline")
    # raises ImportError, resolve_name("...hypothesis",
    # "src.evaluation.baseline") == "src.hypothesis". This is the
    # matrix's "climbs to the src/ root and then into hypothesis" case.
    # NOTE: section 8's prose classifies level=3 from this package as
    # beyond-root -- that predates the dual-context correction accepted
    # at Stage 5 round 2 (decision registry K1), which this guard uses.
    assert _hits_for("from ...hypothesis import X\n")


def test_relative_import_beyond_package_root_in_both_contexts_is_unresolvable_not_silently_passed():
    source = "from ....hypothesis import X\n"
    assert not _hits_for(source)
    unresolvable = _unresolvable_for(source)
    assert unresolvable and "package root" in unresolvable[0]


# -- F1: the reserved-name trigger condition --------------------------------

def _declared_dependency_names() -> set[str]:
    names: set[str] = set()
    for line in (_REPO_ROOT / "requirements.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            names.add(re.split(r"[\s<>=!~\[;@]", line, maxsplit=1)[0].lower())
    pyproject = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())
    project = pyproject.get("project", {})
    declared = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        declared.extend(extra)
    for spec in declared:
        names.add(re.split(r"[\s<>=!~\[;@]", spec.strip(), maxsplit=1)[0].lower())
    return names


def test_f1_reserved_name_trigger_condition_has_not_fired():
    """Decision registry F1: the convention holds only while the PyPI
    `hypothesis` library is not a dependency. If this fails, do not just
    edit the test -- re-examine F1 first (see requirements.txt's note)."""
    declared = _declared_dependency_names()
    assert "pytest" in declared  # the parser actually reads the real file
    assert "hypothesis" not in declared, (
        "the third-party `hypothesis` library is now a declared dependency -- decision registry F1's "
        "reserved-name convention for TEST 49 must be re-examined before this guard can be trusted"
    )


_F1_NOTE_HEADER = (
    "# F1 (decision registry F1, Stage 7) -- RESERVED NAME: do NOT add the PyPI\n"
    "# property-based-testing library `hypothesis` without re-examining F1 first.\n"
)


def test_f1_note_is_present_at_the_dependency_management_surface():
    assert _F1_NOTE_HEADER in (_REPO_ROOT / "requirements.txt").read_text()
