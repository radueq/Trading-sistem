"""TEST 10 -- dependency direction and zero LLM/broker calls (Spec #005
v1.0 SS22, Batch 1). Mirrors the AST-scan discipline already
established in tests/spec003 (TEST 26) and tests/spec004 (TEST 39/49):
"No discovery/evaluation/hypothesis import of backtest. No LLM SDK,
broker SDK or network fetch in the deterministic core.\""""
import ast
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
_BACKTEST_SRC = _SRC_ROOT / "backtest"
_UPSTREAM_PACKAGES = ("discovery", "evaluation", "hypothesis", "data_foundation")
_FORBIDDEN_LLM_MODULES = ("anthropic", "openai", "google.generativeai", "cohere", "langchain")
# Real broker/exchange SDK package names -- an AST import scan (not a raw
# text/substring scan) so a docstring merely QUOTING the spec's own "no
# broker orders" language is never a false positive.
_FORBIDDEN_BROKER_MODULES = ("alpaca_trade_api", "ib_insync", "ccxt", "MetaTrader5", "oandapyV20", "robin_stocks")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_no_upstream_package_imports_backtest():
    offenders = []
    for pkg in _UPSTREAM_PACKAGES:
        pkg_dir = _SRC_ROOT / pkg
        if not pkg_dir.exists():
            continue
        for path in pkg_dir.rglob("*.py"):
            if any(m == "backtest" or m.startswith("backtest.") for m in _imports(path)):
                offenders.append(str(path))
    assert not offenders, offenders


def test_no_llm_sdk_import_anywhere_in_backtest_package():
    offenders = []
    for path in _BACKTEST_SRC.rglob("*.py"):
        for name in _imports(path):
            if any(name == m or name.startswith(m + ".") for m in _FORBIDDEN_LLM_MODULES):
                offenders.append(f"{path}: imports {name!r}")
    assert not offenders, offenders


def test_no_broker_sdk_import_anywhere_in_backtest_package():
    offenders = []
    for path in _BACKTEST_SRC.rglob("*.py"):
        for name in _imports(path):
            if any(name == m or name.startswith(m + ".") for m in _FORBIDDEN_BROKER_MODULES):
                offenders.append(f"{path}: imports {name!r}")
    assert not offenders, offenders


def test_no_agents_or_broker_adapter_package_exists_yet():
    assert not (_BACKTEST_SRC / "agents").exists()
    assert not (_BACKTEST_SRC / "broker").exists()
