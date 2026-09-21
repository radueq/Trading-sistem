"""TEST 19 -- Total-return prohibition (Spec #002 SS38/SS31).

Experimental total-return series rejected as research input by
default: Feature Engine uses split-adjusted close, never
total_return_adjusted_close, for its price series. Checked via actual
attribute-access usage (AST), not raw source text, since this codebase's
own comments legitimately discuss total_return_adjusted_close by name to
document why it's avoided.
"""
import ast
import inspect

from discovery import engine


def _accessed_attributes(func) -> set[str]:
    tree = ast.parse(inspect.getsource(func))
    return {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}


def test_engine_does_not_use_total_return_adjusted_close():
    attrs = _accessed_attributes(engine._price_series_to_df)
    assert "total_return_adjusted_close" not in attrs
    assert "split_adjusted_close" in attrs
