"""GET /api/health — liveness + readiness probe."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["health"])

_PROJECT = Path(__file__).parent.parent.parent.parent   # project root


@router.get("/health", summary="Health & readiness check")
def health() -> dict:
    """
    Returns 200 with system status.

    Checks:
    - ChromaDB collection reachability and vector count
    - chunks.jsonl presence (BM25 corpus)
    - GROQ_API_KEY presence (masked)
    """
    status: dict = {
        "status":    "ok",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks":    {},
    }

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    try:
        import chromadb
        chroma_path = os.environ.get("CHROMA_PERSIST_PATH",
                                     str(_PROJECT / "data" / "chroma_db"))
        collection_name = os.environ.get("CHROMA_COLLECTION", "mutual_fund_faq")
        client = chromadb.PersistentClient(path=chroma_path)
        col    = client.get_or_create_collection(collection_name)
        count  = col.count()
        status["checks"]["chroma"] = {"status": "ok", "vector_count": count}
    except Exception as exc:
        status["checks"]["chroma"] = {"status": "error", "detail": str(exc)}
        status["status"] = "degraded"

    # ── BM25 corpus ──────────────────────────────────────────────────────────
    chunks_path = Path(os.environ.get("CHUNKS_JSONL",
                                      str(_PROJECT / "data" / "chunks.jsonl")))
    if chunks_path.exists():
        status["checks"]["chunks_jsonl"] = {
            "status": "ok",
            "path":   str(chunks_path),
        }
    else:
        status["checks"]["chunks_jsonl"] = {
            "status": "missing",
            "path":   str(chunks_path),
        }
        status["status"] = "degraded"

    # ── Groq API key ─────────────────────────────────────────────────────────
    key = os.environ.get("GROQ_API_KEY", "")
    status["checks"]["groq_api_key"] = {
        "status": "set" if key else "missing",
        "value":  f"{key[:8]}..." if key else None,
    }
    if not key:
        status["status"] = "degraded"

    return status
