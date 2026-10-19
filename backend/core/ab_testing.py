"""
A/B Testing Framework
=====================
Hash-based bucketing by conversation/session ID for consistent experiment assignment.

Config: backend/config/ab_tests.yaml
Log output: backend/data/ab_test_log.jsonl

Usage:
    from backend.core.ab_testing import ABTestManager
    manager = ABTestManager()
    flags = manager.get_flags_for_session("conv_abc")
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("ab_testing")

_HERE = Path(__file__).parent
_BACKEND = _HERE.parent
_CONFIG_PATH = _BACKEND / "config" / "ab_tests.yaml"
_LOG_PATH = _BACKEND / "data" / "ab_test_log.jsonl"


class ABTestManager:
    def __init__(self, config_path: Path | None = None, log_path: Path | None = None):
        self._config_path = config_path or _CONFIG_PATH
        self._log_path = log_path or _LOG_PATH
        self._experiments: dict[str, dict] = {}
        self._load_config()

    def _load_config(self) -> None:
        if not self._config_path.exists():
            log.warning("A/B test config not found: %s", self._config_path)
            return
        try:
            import yaml
            with self._config_path.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            self._experiments = data.get("experiments", {})
            log.info("A/B test config loaded: %d experiments", len(self._experiments))
        except Exception as exc:
            log.warning("Failed to load A/B test config: %s", exc)

    def _bucket(self, session_id: str, experiment_name: str, variants: dict[str, dict]) -> str:
        """Hash-based deterministic bucketing. Returns the chosen variant name."""
        hash_input = f"{experiment_name}:{session_id}"
        hash_val = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
        bucket = hash_val % 100

        cumulative = 0
        for variant_name, variant_cfg in variants.items():
            cumulative += variant_cfg.get("weight", 0)
            if bucket < cumulative:
                return variant_name

        return list(variants.keys())[-1]

    def get_assignment(self, session_id: str) -> dict[str, str]:
        """Return {experiment_name: variant_name} for all enabled experiments."""
        assignments: dict[str, str] = {}
        for exp_name, exp_cfg in self._experiments.items():
            if not exp_cfg.get("enabled", False):
                continue
            variants = exp_cfg.get("variants", {})
            if not variants:
                continue
            chosen = self._bucket(session_id, exp_name, variants)
            assignments[exp_name] = chosen
        return assignments

    def get_flags_for_session(self, session_id: str) -> dict[str, bool]:
        """Return merged feature flag overrides for a session based on all active experiments."""
        flags: dict[str, bool] = {}
        assignments = self.get_assignment(session_id)
        for exp_name, variant_name in assignments.items():
            variant_cfg = self._experiments[exp_name]["variants"][variant_name]
            variant_flags = variant_cfg.get("flags", {})
            flags.update(variant_flags)
        return flags

    def log_assignment(
        self,
        session_id: str,
        assignments: dict[str, str],
        query: str = "",
    ) -> None:
        """Append assignment to JSONL log file."""
        entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "session_id": session_id,
            "assignments": assignments,
            "query": query[:200],
        }
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except Exception as exc:
            log.warning("Failed to write A/B test log: %s", exc)

    def get_results(self) -> dict[str, Any]:
        """Read JSONL log and compute per-experiment, per-variant counts."""
        results: dict[str, dict[str, int]] = {}
        total_entries = 0

        if not self._log_path.exists():
            return {"total_entries": 0, "experiments": {}}

        try:
            with self._log_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    total_entries += 1
                    for exp_name, variant_name in entry.get("assignments", {}).items():
                        if exp_name not in results:
                            results[exp_name] = {}
                        results[exp_name][variant_name] = results[exp_name].get(variant_name, 0) + 1
        except Exception as exc:
            log.warning("Failed to read A/B test log: %s", exc)

        return {
            "total_entries": total_entries,
            "experiments": results,
        }

    def get_experiments(self) -> dict[str, dict]:
        """Return current experiment configuration."""
        return dict(self._experiments)


# Module-level singleton
_manager: ABTestManager | None = None


def get_ab_manager() -> ABTestManager:
    global _manager
    if _manager is None:
        _manager = ABTestManager()
    return _manager
