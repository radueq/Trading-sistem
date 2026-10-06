"""B4 -- calendar relocation is a pure move (joint remediation design
003+004 section 2; decision registry B4, revision 5-6; authorized
2026-10-06, Stage 2).

`backtest.models.entities`/`backtest.data.calendar` must re-export the
SAME objects `data_foundation.calendar` defines -- not copies -- so the
relocation is provably identity-preserving, not merely
behavior-alike. The architecture guard mirrors TEST 26's own existing
(not-yet-corrected) algorithm -- the base+alias/relative-import fix is
separate, not-yet-authorized work (joint design section 8, Stage 5/7 of
the implementation plan); this guard catches the simple, direct-import
case, consistent with what TEST 26 itself currently catches.
"""
import ast
from pathlib import Path

import backtest.data.calendar as backtest_calendar_module
import backtest.models.entities as backtest_entities_module
import data_foundation.calendar.contract as contract_module
import data_foundation.calendar.entities as entities_module

_EVALUATION_SRC = Path(__file__).resolve().parents[2] / "src" / "evaluation"


def test_backtest_models_entities_reexports_the_same_calendar_entities_objects():
    assert backtest_entities_module.TradingCalendar is entities_module.TradingCalendar
    assert backtest_entities_module.CalendarSource is entities_module.CalendarSource
    assert backtest_entities_module.calendar_fingerprint is entities_module.calendar_fingerprint
    assert backtest_entities_module.build_calendar_id is entities_module.build_calendar_id
    assert backtest_entities_module.verify_calendar_content_address is entities_module.verify_calendar_content_address
    assert backtest_entities_module.verify_calendar_structure is entities_module.verify_calendar_structure
    assert backtest_entities_module.CalendarNotVerifiedError is entities_module.CalendarNotVerifiedError
    assert backtest_entities_module.CalendarCoverageIncompleteError is entities_module.CalendarCoverageIncompleteError


def test_backtest_data_calendar_reexports_the_same_contract_functions():
    assert backtest_calendar_module.build_trading_calendar is contract_module.build_trading_calendar
    assert backtest_calendar_module.require_verified_calendar_for_formal_run is contract_module.require_verified_calendar_for_formal_run
    assert backtest_calendar_module.require_calendar_covers_window is contract_module.require_calendar_covers_window
    assert backtest_calendar_module.is_session is contract_module.is_session


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_evaluation_never_imports_backtest():
    for path in _EVALUATION_SRC.rglob("*.py"):
        for module in _imported_modules(path):
            assert not module.startswith("backtest"), (
                f"{path} imports {module!r} -- evaluation must never depend on backtest "
                f"(joint remediation design section 2's own relocation goal)"
            )
