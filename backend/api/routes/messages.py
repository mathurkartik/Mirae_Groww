"""
Message endpoints — full pipeline per query
-------------------------------------------
  POST /api/threads/{thread_id}/messages  → send query, run pipeline, get answer
  GET  /api/threads/{thread_id}/messages  → get full message history

Full pipeline per POST
----------------------
  1. Input sanitization (strip HTML, SQL, injection attempts)
  2. Query Guard      → FACTUAL / ADVISORY / OUT_OF_SCOPE
  3. Hybrid Retriever → top-3 chunks  (skipped for refusals)
  4. Generator        → Groq LLM answer  (skipped for refusals)
  5. Post-Processor   → truncate / cite / footer / PII / advisory filter
  6. Persist user + assistant messages in ThreadStore
  7. Return response dict matching RAG_Architecture.md schema
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.store.thread_store import ThreadStore, Message, get_store

router = APIRouter(prefix="/threads", tags=["messages"])

_MAX_QUERY_LEN = 1000   # characters


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class MessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=_MAX_QUERY_LEN,
                         description="User query (1–1000 characters)")
    scheme_filter: Optional[str] = Field(
        None,
        description="Optional: restrict dense retrieval to a specific scheme_name",
    )


class MessageResponse(BaseModel):
    thread_id:    str
    message_id:   str
    role:         str
    content:      str
    citation:     Optional[str]
    last_updated: Optional[str]
    timestamp:    str
    is_refusal:   bool
    is_math_redirect: bool = False
    intent:       Optional[str]   = None
    # Debug fields (omitted from production responses via exclude_none)
    retrieval_count: Optional[int] = None


# ---------------------------------------------------------------------------
# Input sanitizer
# ---------------------------------------------------------------------------

_HTML_TAG_RE     = re.compile(r"<[^>]+>")
_SQL_PATTERN_RE  = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|UNION|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)
_INJECTION_RE    = re.compile(
    r"(ignore previous|disregard (all )?instructions?|you are now|"
    r"act as|pretend (you are|to be)|new persona|jailbreak)",
    re.IGNORECASE,
)


def _sanitize(text: str) -> str:
    """Strip HTML tags, SQL keywords, and prompt-injection patterns."""
    text = _HTML_TAG_RE.sub(" ", text)
    text = _SQL_PATTERN_RE.sub("[REDACTED]", text)
    text = _INJECTION_RE.sub("[REDACTED]", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# POST /api/threads/{thread_id}/messages
# ---------------------------------------------------------------------------

@router.post(
    "/{thread_id}/messages",
    response_model=MessageResponse,
    summary="Send a query and receive an answer",
)
def send_message(
    thread_id: str,
    body:      MessageRequest,
    store:     ThreadStore = Depends(get_store),
) -> dict:
    """
    Full pipeline: guard → retrieve → generate → post-process → persist.

    Rate limit: 30 requests/min per thread (enforced by ThreadRateLimiter middleware).
    """
    # ── 0. Verify thread exists ───────────────────────────────────────────────
    if not store.thread_exists(thread_id):
        raise HTTPException(status_code=404, detail=f"Thread {thread_id!r} not found")

    # ── 1. Sanitize input ─────────────────────────────────────────────────────
    raw_query = body.content.strip()
    query     = _sanitize(raw_query)

    if not query:
        raise HTTPException(status_code=400, detail="Query is empty after sanitization")

    # ── 2. Snapshot prior history BEFORE appending current user message ───────
    # ISOLATION GUARANTEE: get_history() is keyed exclusively to thread_id.
    # It returns plain-dict copies of that thread's messages only — no other
    # thread's state is accessible, even under concurrent requests.
    #
    # Capturing history HERE (before add_message) avoids a subtle race:
    # if two requests arrive simultaneously for the same thread, each sees
    # only the turns that were already committed prior to its own user message.
    history = store.get_history(thread_id, max_turns=3)

    # ── 3. Persist user message ───────────────────────────────────────────────
    user_msg = Message(
        message_id = str(uuid.uuid4()),
        role       = "user",
        content    = raw_query,          # store original (pre-sanitize) for display
        timestamp  = _utcnow(),
    )
    store.add_message(thread_id, user_msg)
    if history and history[-1]["role"] == "user":
        history = history[:-1]

    # ── 4. Query Guard ────────────────────────────────────────────────────────
    from backend.core.query_guard import classify, REFUSAL_ADVISORY

    guard = classify(query)

    if guard.is_refusal or guard.is_math_redirect:
        # Build refusal/redirect assistant message directly — no LLM call
        assistant_msg = Message(
            message_id       = str(uuid.uuid4()),
            role             = "assistant",
            content          = guard.refusal_message or REFUSAL_ADVISORY,
            timestamp        = _utcnow(),
            citation         = "https://www.amfiindia.com/investor-corner/knowledge-center" if guard.is_refusal else None,
            last_updated     = None,
            is_refusal       = guard.is_refusal,
            is_math_redirect = guard.is_math_redirect,
            intent           = guard.intent,
        )
        store.add_message(thread_id, assistant_msg)
        return _build_response(thread_id, assistant_msg, retrieval_count=0)

    # ── 5. Retrieve ───────────────────────────────────────────────────────────
    from backend.core.retriever import retrieve

    chunks = retrieve(query, scheme_filter=body.scheme_filter)

    # ── 6. Generate (Groq LLM) ───────────────────────────────────────────────
    import os
    if not os.environ.get("GROQ_API_KEY"):
        # Return a safe "no key" message so the API still responds cleanly
        answer       = (
            "The Groq API key is not configured on this server. "
            "Retrieval worked correctly but LLM generation is unavailable. "
            "Please set GROQ_API_KEY in the environment."
        )
        citation_url = chunks[0].source_url if chunks else ""
        last_updated = chunks[0].last_crawled_date if chunks else ""
        raw_answer   = answer
        intent       = guard.intent
        no_llm       = True
    else:
        no_llm = False
        from backend.core.generator import _call_groq, _build_messages, _extract_citation, _extract_last_updated

        messages   = _build_messages(query, chunks, history)
        raw_answer = _call_groq(messages)
        citation_url  = _extract_citation(raw_answer, chunks)
        last_updated  = _extract_last_updated(raw_answer, chunks)
        intent        = guard.intent

    # ── 7. Post-process ───────────────────────────────────────────────────────
    from backend.core.post_processor import process as post_process

    top_chunk = chunks[0] if chunks else None
    pp = post_process(
        raw_answer,
        citation_url      = citation_url if not no_llm else (chunks[0].source_url if chunks else ""),
        last_updated_date = last_updated  if not no_llm else (chunks[0].last_crawled_date if chunks else ""),
        is_refusal        = False,
        top_chunk         = top_chunk,
    )

    final_is_refusal = pp.is_blocked or pp.is_replaced

    # ── 8. Persist assistant message ──────────────────────────────────────────
    assistant_msg = Message(
        message_id   = str(uuid.uuid4()),
        role         = "assistant",
        content      = pp.answer,
        timestamp    = _utcnow(),
        citation     = pp.citation_url,
        last_updated = pp.last_updated_date,
        is_refusal   = final_is_refusal,
        intent       = intent,
    )
    store.add_message(thread_id, assistant_msg)

    return _build_response(thread_id, assistant_msg, retrieval_count=len(chunks))


def _build_response(thread_id: str, msg: Message, retrieval_count: int) -> dict:
    return {
        "thread_id":       thread_id,
        "message_id":      msg.message_id,
        "role":            msg.role,
        "content":         msg.content,
        "citation":        msg.citation,
        "last_updated":    msg.last_updated,
        "timestamp":       msg.timestamp,
        "is_refusal":      msg.is_refusal,
        "is_math_redirect": msg.is_math_redirect,
        "intent":          msg.intent,
        "retrieval_count": retrieval_count,
    }


# ---------------------------------------------------------------------------
# GET /api/threads/{thread_id}/messages
# ---------------------------------------------------------------------------

@router.get(
    "/{thread_id}/messages",
    summary="Get full message history for a thread",
)
def get_messages(
    thread_id: str,
    store:     ThreadStore = Depends(get_store),
) -> dict:
    """
    Returns the complete message history for a thread.
    Each entry has: message_id, role, content, timestamp, citation, is_refusal.

    Thread isolation guarantee: only returns messages for this specific thread.
    """
    messages = store.get_messages(thread_id)
    if messages is None:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id!r} not found")

    return {
        "thread_id":     thread_id,
        "message_count": len(messages),
        "messages":      messages,
    }
