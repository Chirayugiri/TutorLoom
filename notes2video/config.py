"""Load config.yaml (with ${ENV} substitution) and theme.yaml."""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


class Config(dict):
    """Dict with attribute-path access: cfg.get_path("llm.model")."""

    def get_path(self, dotted: str, default: Any = None) -> Any:
        node: Any = self
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def path(self, dotted: str) -> Path:
        p = Path(self.get_path(dotted))
        return p if p.is_absolute() else ROOT / p


@lru_cache(maxsize=4)
def load_config(config_file: str | None = None) -> Config:
    load_dotenv(ROOT / ".env")
    path = Path(config_file) if config_file else ROOT / "config.yaml"
    data = _expand(yaml.safe_load(path.read_text()))
    cfg = Config(data)
    cfg["theme"] = yaml.safe_load((ROOT / cfg["theme_file"]).read_text())
    return cfg
