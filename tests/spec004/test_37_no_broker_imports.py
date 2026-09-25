"""TEST 37 -- no broker/live-trading import anywhere in src/hypothesis/
(Spec #004 SS99 -- out of scope)."""
import ast
from pathlib import Path

_HYPOTHESIS_SRC = Path(__file__).resolve().parents[2] / "src" / "hypothesis"
_FORBIDDEN_TOKENS = ("broker", "alpaca", "interactive_brokers", "ibkr", "tradier", "ccxt", "live_trading")


def test_no_broker_related_import_or_identifier():
    offenders = []
    for path in _HYPOTHESIS_SRC.rglob("*.py"):
        text = path.read_text().lower()
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                offenders.append(f"{path}: contains {token!r}")
    assert not offenders, offenders
