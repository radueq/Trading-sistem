"""Spec #005 Batch 3 -- STOP_MANAGED_INVALIDATION exit engine.

Implements docs/spec005_exit_amendment_v1.0.md (ACCEPTED) as a
self-contained, per-position simulation: protective-stop/target formulas
(section 3), the session event-order extension (section 5, Pas 0/3'),
split reconciliation (section 6), the new execution-semantics profile
(section 7), cost formulas (section 9), the three-facet taxonomy
(section 10), the selection metric (section 11), and per-tranche MAE/MFE
(section 12).

Scope note (read before wiring this into a full backtest run): Batch 1/2
of Spec #005 (`backtest.models.entities`/`backtest.data.*`) are
CONTRACTS AND PIT ACCESS ONLY -- no multi-security session/universe loop,
entry-signal matching, or TIME_EXIT/SIGNAL_INVALIDATION execution engine
exists anywhere in this codebase yet for ANY exit family. This package
does not add one either: it implements exactly what the accepted
amendment itself fully specifies -- the STOP_MANAGED_INVALIDATION
position's own mechanics, taking an already-determined entry fill and
already-fetched PIT data as input. Steps 1/2/4/6 of the base session
order (scheduled exits, entry matching, TIME_EXIT/CAP, new entries) are
explicitly "unchanged" per the amendment and belong to that not-yet-built
base engine; wiring this package's Pas 0/3' functions into a real
multi-security session loop is future work outside this amendment's own
scope.
"""
