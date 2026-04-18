"""
backend/main.py — FastAPI application entry point
==================================================
Mutual Fund FAQ Assistant — Phase 8 (Backend API)

Endpoints
---------
  POST   /api/threads                          → create thread
  GET    /api/threads                          → list threads
  GET    /api/threads/{id}                     → thread metadata
  DELETE /api/threads/{id}                     → delete thread
  POST   /api/threads/{id}/messages            → query → answer (full pipeline)
  GET    /api/threads/{id}/messages            → message history
  POST   /api/ingest                           → admin: trigger embedding pipeline
  GET    /api/ingest/{job_id}                  → admin: poll job status
  GET    /api/health                           → liveness + readiness probe

Middleware stack (in order)
---------------------------
  CORSMiddleware         → allow frontend origin (Vercel / localhost:3000)
  ThreadRateLimiter      → 30 req/min per thread (POST .../messages only)

Startup events
--------------
  load_dotenv()          → load GROQ_API_KEY and other env vars from .env
  BM25 index warm-up     → build BM25 index from chunks.jsonl at startup

Run (development)
-----------------
  uvicorn backend.main:app --reload --port 8000

Run (production / Render)
------------------------
  uvicorn backend.main:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

import logging
import os
import sys
import io
from pathlib import Path

# ── sys.path: ensure project root importable ─────────────────────────────────
_HERE    = Path(__file__).parent          # backend/
_PROJECT = _HERE.parent                   # project root
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))

# ── Load .env before anything else ───────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_PROJECT / ".env", override=False)
except ImportError:
    pass

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("main")

# ── FastAPI ───────────────────────────────────────────────────────────────────
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import health, threads, messages, ingest, funds
from backend.middleware.rate_limiter import ThreadRateLimiter

# ── App definition ────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "Mutual Fund FAQ Assistant API",
    description = (
        "Facts-only FAQ assistant for Mirae Asset mutual fund schemes. "
        "All answers are grounded in scraped Groww content. "
        "No investment advice."
    ),
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    os.environ.get("NEXT_PUBLIC_FRONTEND_URL", "https://your-app.vercel.app"),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins     = _ALLOWED_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Rate limiter ──────────────────────────────────────────────────────────────
app.add_middleware(ThreadRateLimiter, max_requests=30, window_seconds=60)

# ── Routers ───────────────────────────────────────────────────────────────────
_PREFIX = "/api"
app.include_router(health.router,   prefix=_PREFIX)
app.include_router(threads.router,  prefix=_PREFIX)
app.include_router(messages.router, prefix=_PREFIX)
app.include_router(ingest.router,   prefix=_PREFIX)
app.include_router(funds.router,    prefix=_PREFIX)


# ── Startup event: warm up BM25 index ────────────────────────────────────────
@app.on_event("startup")
async def _startup() -> None:
    log.info("Starting Mutual Fund FAQ Assistant API v1.0")

    # Warm up BM25 index (reads chunks.jsonl once, ~50ms for 419 chunks)
    try:
        from backend.core.retriever import _load_bm25_index
        _load_bm25_index()
        log.info("BM25 index warmed up at startup")
    except Exception as exc:
        log.warning("BM25 warm-up skipped: %s", exc)

    # Warm up fund registry (parses urls.yaml + cleaned_docs.jsonl)
    try:
        from backend.core.fund_registry import initialize as init_fund_registry
        init_fund_registry()
        log.info("Fund registry loaded at startup")
    except Exception as exc:
        log.warning("Fund registry warm-up skipped: %s", exc)

    # Log key configuration
    log.info(
        "Config: CHROMA=%s  COLLECTION=%s  GROQ_KEY=%s",
        os.environ.get("CHROMA_PERSIST_PATH", "data/chroma_db"),
        os.environ.get("CHROMA_COLLECTION",   "mutual_fund_faq"),
        "SET" if os.environ.get("GROQ_API_KEY") else "MISSING",
    )


# ── Root redirect ─────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def root():
    return {
        "service": "Mutual Fund FAQ Assistant",
        "docs":    "/docs",
        "health":  "/api/health",
    }
