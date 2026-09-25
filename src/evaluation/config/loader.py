"""Config loader for Spec #003 -- Evaluation Engine.

Mirrors discovery.config.loader's discipline (Spec #002 SS33/SS45): every
tunable parameter lives in config/evaluation.yaml, never hardcoded in
calculation logic; config_version is a hash of the file's raw content, so
any edit to a threshold/window automatically changes the version -- a
silent parameter change is structurally impossible to hide.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_CONFIG_DIR = Path(__file__).parent
_FILE = "evaluation.yaml"


@dataclass(frozen=True)
class EvaluationConfig:
    data: dict[str, Any]
    config_version: str


def load_config(config_dir: Path | None = None) -> EvaluationConfig:
    config_dir = config_dir or _CONFIG_DIR
    text = (config_dir / _FILE).read_text()
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    return EvaluationConfig(data=yaml.safe_load(text), config_version=f"cfg_{digest}")
