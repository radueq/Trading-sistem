"""Config loader for Spec #003 -- Evaluation Engine.

Mirrors discovery.config.loader's discipline (Spec #002 SS33/SS45): every
tunable parameter lives in config/evaluation.yaml, never hardcoded in
calculation logic; config_version is a hash of the file's raw content, so
any edit to a threshold/window automatically changes the version -- a
silent parameter change is structurally impossible to hide.

`raw_texts` (Stage 3, authorized 2026-10-07, corrected round 2): see
discovery.config.loader's own docstring -- same discipline, single file.
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
    raw_texts: tuple[str, ...]


def reparse_raw_texts(raw_texts: tuple[str, ...]) -> EvaluationConfig:
    """Pure (no disk I/O) -- see discovery.config.loader.reparse_raw_texts."""
    if len(raw_texts) != 1:
        raise ValueError(f"expected exactly 1 raw text (for {_FILE!r}), got {len(raw_texts)}")
    text = raw_texts[0]
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    return EvaluationConfig(data=yaml.safe_load(text), config_version=f"cfg_{digest}", raw_texts=tuple(raw_texts))


def load_config_with_raw_texts(config_dir: Path | None = None) -> tuple[EvaluationConfig, tuple[str, ...]]:
    config_dir = config_dir or _CONFIG_DIR
    raw_texts = ((config_dir / _FILE).read_text(),)
    config = reparse_raw_texts(raw_texts)
    return config, raw_texts


def load_config(config_dir: Path | None = None) -> EvaluationConfig:
    config, _raw_texts = load_config_with_raw_texts(config_dir)
    return config
