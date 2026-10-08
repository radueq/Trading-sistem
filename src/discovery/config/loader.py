"""Config loader for Spec #002 -- Feature Engine + Discovery Engine.

All tunable parameters live in the YAML files in this directory, never
hardcoded in calculation logic (Spec #002 SS33). config_version is a
hash of the loaded files' raw content, so any edit to a threshold or
window automatically changes the version -- a silent formula/parameter
change is structurally impossible to hide (Spec #002 SS45).

`raw_texts` (Stage 3 -- config identity infrastructure, decision
registry, Stage 3; authorized 2026-10-07, corrected round 2): the
EXACT text read from disk for each of `_FILES`, in order, retained on
the returned `DiscoveryConfig` itself. `reparse_raw_texts()` is the
SAME parse+hash logic `load_config()` uses, extracted into a pure
function (no disk I/O) so `config_identity` -- and tests building a
legitimate alternative config -- can independently re-derive
`config_version`/content FROM a given `raw_texts` tuple, never by
trusting a caller's separately-claimed label/content pair.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_CONFIG_DIR = Path(__file__).parent
_FILES = ["features.yaml", "states.yaml", "discovery.yaml", "eligibility.yaml"]


@dataclass(frozen=True)
class DiscoveryConfig:
    features: dict[str, Any]
    states: dict[str, Any]
    discovery: dict[str, Any]
    eligibility: dict[str, Any]
    config_version: str
    raw_texts: tuple[str, ...]


def reparse_raw_texts(raw_texts: tuple[str, ...]) -> DiscoveryConfig:
    """Pure (no disk I/O): parses an already-read `raw_texts` tuple
    (one entry per `_FILES`, same order) into a `DiscoveryConfig`,
    using the UNCHANGED multi-source combination rule
    (`sha256("".join(raw_texts))[:12]`). Identical computation to what
    `load_config()` performs after its own disk read -- kept as one
    function so the two can never silently drift apart."""
    if len(raw_texts) != len(_FILES):
        raise ValueError(f"expected {len(_FILES)} raw texts (one per {_FILES!r}), got {len(raw_texts)}")
    parsed: dict[str, Any] = {fname: yaml.safe_load(text) for fname, text in zip(_FILES, raw_texts, strict=True)}
    digest = hashlib.sha256("".join(raw_texts).encode()).hexdigest()[:12]
    return DiscoveryConfig(
        features=parsed["features.yaml"],
        states=parsed["states.yaml"],
        discovery=parsed["discovery.yaml"],
        eligibility=parsed["eligibility.yaml"],
        config_version=f"cfg_{digest}",
        raw_texts=tuple(raw_texts),
    )


def load_config_with_raw_texts(config_dir: Path | None = None) -> tuple[DiscoveryConfig, tuple[str, ...]]:
    config_dir = config_dir or _CONFIG_DIR
    raw_texts = tuple((config_dir / fname).read_text() for fname in _FILES)
    config = reparse_raw_texts(raw_texts)
    return config, raw_texts


def load_config(config_dir: Path | None = None) -> DiscoveryConfig:
    config, _raw_texts = load_config_with_raw_texts(config_dir)
    return config
