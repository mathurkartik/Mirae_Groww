"""
User Feedback Module
====================
Collects and summarizes user feedback on chatbot responses.

Endpoints (registered via routes):
  POST /api/feedback         - Submit feedback
  GET  /api/feedback/summary - Aggregated metrics

Storage: backend/data/feedback_log.jsonl
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("feedback")

_HERE = Path(__file__).parent
_BACKEND = _HERE.parent
_LOG_PATH = _BACKEND / "data" / "feedback_log.jsonl"

VALID_RATINGS = {"helpful", "not_helpful", "incorrect", "refused_wrongly"}


def store_feedback(
    conversation_id: str,
    message_id: str,
    query: str,
    rating: str,
    comment: str = "",
    experiment_assignments: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Store a feedback entry. Returns the stored record."""
    if rating not in VALID_RATINGS:
        raise ValueError(f"Invalid rating {rating!r}. Must be one of: {VALID_RATINGS}")

    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "conversation_id": conversation_id,
        "message_id": message_id,
        "query": query,
        "rating": rating,
        "comment": comment,
        "experiment_assignments": experiment_assignments or {},
    }

    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")

    log.info("Feedback stored: %s rating=%s msg=%s", conversation_id, rating, message_id)
    return entry


def get_summary() -> dict[str, Any]:
    """Compute feedback summary metrics."""
    entries: list[dict] = []
    if _LOG_PATH.exists():
        with _LOG_PATH.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))

    total = len(entries)
    if total == 0:
        return {
            "total_feedback": 0,
            "ratings": {},
            "helpful_ratio": 0.0,
            "incorrect_rate": 0.0,
            "false_refusal_rate": 0.0,
            "per_variant": {},
        }

    rating_counts = Counter(e["rating"] for e in entries)

    helpful = rating_counts.get("helpful", 0)
    not_helpful = rating_counts.get("not_helpful", 0)
    incorrect = rating_counts.get("incorrect", 0)
    refused_wrongly = rating_counts.get("refused_wrongly", 0)

    helpful_ratio = helpful / total if total > 0 else 0.0
    incorrect_rate = incorrect / total if total > 0 else 0.0

    total_refusals = refused_wrongly + sum(
        1 for e in entries
        if e.get("rating") == "not_helpful"
        and "refused" in e.get("comment", "").lower()
    )
    false_refusal_rate = refused_wrongly / max(total_refusals, 1)

    # Per-experiment-variant breakdown
    per_variant: dict[str, dict[str, dict[str, int]]] = {}
    for entry in entries:
        assignments = entry.get("experiment_assignments", {})
        for exp_name, variant_name in assignments.items():
            if exp_name not in per_variant:
                per_variant[exp_name] = {}
            if variant_name not in per_variant[exp_name]:
                per_variant[exp_name][variant_name] = {}
            rating = entry["rating"]
            per_variant[exp_name][variant_name][rating] = (
                per_variant[exp_name][variant_name].get(rating, 0) + 1
            )

    return {
        "total_feedback": total,
        "ratings": dict(rating_counts),
        "helpful_ratio": round(helpful_ratio, 4),
        "incorrect_rate": round(incorrect_rate, 4),
        "false_refusal_rate": round(false_refusal_rate, 4),
        "per_variant": per_variant,
    }
