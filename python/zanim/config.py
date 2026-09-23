from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .theme import Theme, set_theme, theme_named


@dataclass(frozen=True, slots=True)
class ZanimConfig:
    theme: Theme


def config_from_mapping(raw: Mapping[str, Any]) -> ZanimConfig:
    theme_raw = raw.get("theme", "manim")
    if isinstance(theme_raw, str):
        theme = theme_named(theme_raw)
    elif isinstance(theme_raw, Mapping):
        base = theme_named(str(theme_raw.get("base", "manim")))
        overrides = {k: v for k, v in theme_raw.items() if k != "base"}
        theme = base.with_overrides(overrides)
    else:
        raise TypeError("config theme must be a theme name or mapping")
    return ZanimConfig(theme=theme)


def load_config(source: str | os.PathLike[str] | Mapping[str, Any]) -> ZanimConfig:
    if isinstance(source, Mapping):
        return config_from_mapping(source)
    path = Path(source).expanduser()
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf8"))
    elif path.suffix.lower() in {".toml", ".tml"}:
        raw = tomllib.loads(path.read_text(encoding="utf8"))
    else:
        raise ValueError("Zanim config must be .toml or .json")
    if not isinstance(raw, Mapping):
        raise TypeError("Zanim config root must be a mapping")
    return config_from_mapping(raw)


def apply_config(config: ZanimConfig | str | os.PathLike[str] | Mapping[str, Any]) -> ZanimConfig:
    resolved = config if isinstance(config, ZanimConfig) else load_config(config)
    set_theme(resolved.theme)
    return resolved


def load_default_config() -> ZanimConfig:
    path = os.environ.get("ZANIM_CONFIG")
    if path:
        return apply_config(path)
    return ZanimConfig(theme=theme_named("manim"))


__all__ = [
    "ZanimConfig",
    "apply_config",
    "config_from_mapping",
    "load_config",
    "load_default_config",
]
