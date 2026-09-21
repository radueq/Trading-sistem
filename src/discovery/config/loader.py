"""Config loader for Spec #002 -- Feature Engine + Discovery Engine.

All tunable parameters live in the YAML files in this directory, never
hardcoded in calculation logic (Spec #002 SS33). config_version is a
hash of the loaded files' raw content, so any edit to a threshold or
window automatically changes the version -- a silent formula/parameter
change is structurally impossible to hide (Spec #002 SS45).
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


def load_config(config_dir: Path | None = None) -> DiscoveryConfig:
    config_dir = config_dir or _CONFIG_DIR
    raw_texts = []
    parsed: dict[str, Any] = {}
    for fname in _FILES:
        text = (config_dir / fname).read_text()
        raw_texts.append(text)
        parsed[fname] = yaml.safe_load(text)

    digest = hashlib.sha256("".join(raw_texts).encode()).hexdigest()[:12]
    return DiscoveryConfig(
        features=parsed["features.yaml"],
        states=parsed["states.yaml"],
        discovery=parsed["discovery.yaml"],
        eligibility=parsed["eligibility.yaml"],
        config_version=f"cfg_{digest}",
    )
