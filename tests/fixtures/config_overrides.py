"""Shared test helper -- Stage 3 config identity infrastructure
(decision registry, Stage 3; authorized 2026-10-07; CORRECTED round 2)
made every Discovery/Evaluation/Hypothesis config self-consistency-
checked: a candidate's `raw_texts` must actually reparse to its own
claimed `config_version`/content. A pre-existing test needing a
DELIBERATELY different config for its own scenario (a tightened
threshold, extra horizons, a reduced percentile window, ...) must
produce one that is genuinely self-consistent -- never a hand-mutated
`.data`/`.features` object that keeps its original, now-stale
`raw_texts` (exactly the shape Stage 3 now rejects, on purpose).

These helpers do that WITHOUT any disk I/O beyond the one real initial
load: they re-serialize the overridden top-level key(s) back to real
YAML text via `yaml.safe_dump()`, splice that into the real `raw_texts`
tuple, and reparse through each domain's own `reparse_raw_texts()` --
the EXACT parse+hash code `load_config()` itself uses. The result is a
real, loader-sourced config whose `config_version` genuinely,
differently corresponds to its own (deliberately different) content --
never a hand-built object trusted on its say-so.
"""
from __future__ import annotations

from typing import Any

import yaml

from discovery.config.loader import DiscoveryConfig, load_config_with_raw_texts as _load_discovery_with_raw_texts
from discovery.config.loader import reparse_raw_texts as _reparse_discovery
from evaluation.config.loader import EvaluationConfig, load_config_with_raw_texts as _load_evaluation_with_raw_texts
from evaluation.config.loader import reparse_raw_texts as _reparse_evaluation
from hypothesis.config.loader import HypothesisConfig, load_config_with_raw_texts as _load_hypothesis_with_raw_texts
from hypothesis.config.loader import reparse_raw_texts as _reparse_hypothesis

# Discovery's own multi-source file order (discovery/config/loader.py's
# _FILES) -- each top-level DiscoveryConfig field maps 1:1 to one file.
_DISCOVERY_FIELD_TO_FILE_INDEX = {"features": 0, "states": 1, "discovery": 2, "eligibility": 3}


def discovery_config_with_overrides(**top_level_overrides: dict[str, Any]) -> DiscoveryConfig:
    """Each keyword is one of {"features", "states", "discovery",
    "eligibility"}; its value FULLY REPLACES that file's own parsed
    top-level dict (spread the base yourself first, e.g.
    `features={**base.features, "percentile_window": 15}`, exactly as
    the pre-Stage-3 fixtures already did)."""
    _, raw_texts = _load_discovery_with_raw_texts()
    raw_texts = list(raw_texts)
    for key, override in top_level_overrides.items():
        idx = _DISCOVERY_FIELD_TO_FILE_INDEX[key]
        raw_texts[idx] = yaml.safe_dump(override)
    return _reparse_discovery(tuple(raw_texts))


def evaluation_config_with_overrides(**top_level_overrides: dict[str, Any]) -> EvaluationConfig:
    """Each keyword is a top-level key of evaluation.yaml (e.g.
    `horizons=`, `support=`, `bootstrap=`); its value FULLY REPLACES
    that key in the parsed dict."""
    _, raw_texts = _load_evaluation_with_raw_texts()
    parsed = yaml.safe_load(raw_texts[0])
    parsed.update(top_level_overrides)
    return _reparse_evaluation((yaml.safe_dump(parsed),))


def hypothesis_config_with_overrides(**top_level_overrides: dict[str, Any]) -> HypothesisConfig:
    """Each keyword is a top-level key of hypothesis.yaml (e.g.
    `research_queue_eligibility=`); its value FULLY REPLACES that key
    in the parsed dict."""
    _, raw_texts = _load_hypothesis_with_raw_texts()
    parsed = yaml.safe_load(raw_texts[0])
    parsed.update(top_level_overrides)
    return _reparse_hypothesis((yaml.safe_dump(parsed),))
