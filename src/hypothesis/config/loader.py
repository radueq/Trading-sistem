"""Config loader for Spec #004 -- Hypothesis Generation & Strategy Definition.

Mirrors discovery.config.loader / evaluation.config.loader discipline: every
tunable guardrail lives in config/hypothesis.yaml, never hardcoded in
validator/budget logic; config_version is a hash of the file's raw content.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_CONFIG_DIR = Path(__file__).parent
_FILE = "hypothesis.yaml"


@dataclass(frozen=True)
class HypothesisConfig:
    data: dict[str, Any]
    config_version: str


def load_config(config_dir: Path | None = None) -> HypothesisConfig:
    config_dir = config_dir or _CONFIG_DIR
    text = (config_dir / _FILE).read_text()
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    return HypothesisConfig(data=yaml.safe_load(text), config_version=f"cfg_{digest}")
