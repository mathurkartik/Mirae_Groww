"""
Feature Flags Module
====================
Loads feature flags from YAML config with environment variable overrides.

Config: backend/config/feature_flags.yaml
Env override: FF_<FLAG_NAME_UPPER>=true/false
Example: FF_HYBRID_SEARCH=false

Usage:
    from backend.core.feature_flags import get_flag
    if get_flag("hybrid_search"):
        # do vector search
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger("feature_flags")

_HERE = Path(__file__).parent
_BACKEND = _HERE.parent
_CONFIG_PATH = _BACKEND / "config" / "feature_flags.yaml"

_flags: dict[str, bool] = {}
_loaded: bool = False


def _load_flags() -> None:
    global _flags, _loaded
    if _loaded:
        return

    defaults: dict[str, bool] = {}

    if _CONFIG_PATH.exists():
        try:
            import yaml
            with _CONFIG_PATH.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            defaults = {k: bool(v) for k, v in data.get("flags", {}).items()}
        except Exception as exc:
            log.warning("Failed to load feature flags YAML: %s", exc)

    for name, default_val in defaults.items():
        env_key = f"FF_{name.upper()}"
        env_val = os.environ.get(env_key)
        if env_val is not None:
            resolved = env_val.lower() in ("true", "1", "yes")
            _flags[name] = resolved
            log.info("Feature flag %s = %s (env override via %s)", name, resolved, env_key)
        else:
            _flags[name] = default_val

    _loaded = True
    log.info("Feature flags loaded: %s", {k: v for k, v in _flags.items()})


def get_flag(name: str, default: bool = False) -> bool:
    _load_flags()
    return _flags.get(name, default)


def get_all_flags() -> dict[str, bool]:
    _load_flags()
    return dict(_flags)


def set_flag(name: str, value: bool) -> None:
    """Runtime override (e.g., from A/B testing). Does not persist to YAML."""
    _load_flags()
    _flags[name] = value


def reload_flags() -> None:
    """Force reload from YAML + env. Useful after config changes."""
    global _loaded
    _loaded = False
    _flags.clear()
    _load_flags()


def log_startup_state() -> None:
    """Log all flag values at startup."""
    _load_flags()
    log.info("=" * 60)
    log.info("Feature Flags State:")
    for name, value in sorted(_flags.items()):
        log.info("  %-30s = %s", name, value)
    log.info("=" * 60)
