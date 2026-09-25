"""TEST 36 -- src/hypothesis/ never imports PIT/Data Foundation/raw-price
access, anywhere (Spec #004 SS5/SS39, Radu's SS110-F confirmation) -- an
AST import scan, mirroring Spec #002 TEST 26 / Spec #003 TEST 26."""
import ast
from pathlib import Path

_HYPOTHESIS_SRC = Path(__file__).resolve().parents[2] / "src" / "hypothesis"
_FORBIDDEN_MODULE_PREFIXES = ("data_foundation",)
_FORBIDDEN_EVALUATION_SUBMODULES = ("evaluation.engine", "evaluation.outcomes", "evaluation.baseline", "evaluation.statistics", "evaluation.registry", "evaluation.observations")
_FORBIDDEN_DISCOVERY_SUBMODULES = ("discovery.engine", "discovery.features", "discovery.eligibility", "discovery.normalization", "discovery.states", "discovery.candidate")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_no_pit_or_engine_level_import_anywhere_in_hypothesis_package():
    offenders = []
    for path in _HYPOTHESIS_SRC.rglob("*.py"):
        for mod in _imported_modules(path):
            if mod.startswith(_FORBIDDEN_MODULE_PREFIXES):
                offenders.append(f"{path}: imports {mod!r} (Data Foundation/PIT)")
            if any(mod == m or mod.startswith(m + ".") for m in _FORBIDDEN_EVALUATION_SUBMODULES):
                offenders.append(f"{path}: imports {mod!r} (Evaluation engine internals, not just models.entities)")
            if any(mod == m or mod.startswith(m + ".") for m in _FORBIDDEN_DISCOVERY_SUBMODULES):
                if "discovery.candidate.reason_codes" not in mod and "discovery.config" not in mod:
                    offenders.append(f"{path}: imports {mod!r} (Discovery engine internals)")
    assert not offenders, offenders


def test_only_evaluation_models_entities_is_imported_not_evaluation_engine():
    for path in _HYPOTHESIS_SRC.rglob("*.py"):
        for mod in _imported_modules(path):
            if mod.startswith("evaluation"):
                assert mod == "evaluation.models.entities", f"{path}: imports {mod!r}, only evaluation.models.entities is allowed"
