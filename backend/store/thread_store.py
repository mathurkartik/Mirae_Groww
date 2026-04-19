"""
backend/store/thread_store.py
In-memory thread store providing STRICT isolation between conversation threads.

Design
------
- Module-level singleton `_store` accessed through `get_store()` dependency.
- One threading.Lock per writer operation; reads are unguarded (Python GIL
  provides sufficient safety for dict lookups).
- Each Thread owns its own message list — no list is shared between threads.
- get_history() returns plain dicts (never live references) so the LLM
  prompt builder cannot mutate thread state.

Thread schema
-------------
  Thread
    thread_id   : str  (UUID4)
    created_at  : str  (ISO-8601 UTC)
    messages    : list[Message]

Message schema
--------------
  Message
    message_id   : str  (UUID4)
    role         : "user" | "assistant"
    content      : str
    timestamp    : str  (ISO-8601 UTC)
    citation     : str | None
    last_updated : str | None
    is_refusal   : bool
    intent       : str | None  (FACTUAL / ADVISORY / OUT_OF_SCOPE)
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
import uuid


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Message:
    message_id:   str
    role:         str           # "user" | "assistant"
    content:      str
    timestamp:    str
    citation:     Optional[str] = None
    last_updated: Optional[str] = None
    is_refusal:   bool          = False
    is_math_redirect: bool      = False
    intent:       Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Thread:
    thread_id:  str
    created_at: str
    messages:   list[Message] = field(default_factory=list)

    def to_dict(self, include_messages: bool = True) -> dict:
        base = {
            "thread_id":  self.thread_id,
            "created_at": self.created_at,
            "message_count": len(self.messages),
        }
        if include_messages:
            base["messages"] = [m.to_dict() for m in self.messages]
        return base


# ---------------------------------------------------------------------------
# Thread store
# ---------------------------------------------------------------------------

class ThreadStore:
    """
    Thread-safe in-memory store for conversation threads.

    Thread isolation guarantee
    --------------------------
    Every method that mutates state acquires `_lock` before modifying the
    internal dict or any thread's message list.  get_history() returns
    *copies* of message dicts — callers cannot accidentally share references.
    """

    def __init__(self) -> None:
        self._threads: dict[str, Thread] = {}
        self._lock = threading.Lock()

    # ── Write operations ────────────────────────────────────────────────────

    def create_thread(self) -> Thread:
        """Create a new isolated thread. Returns the Thread object."""
        thread = Thread(
            thread_id  = str(uuid.uuid4()),
            created_at = _utcnow(),
            messages   = [],          # brand-new list — zero sharing
        )
        with self._lock:
            self._threads[thread.thread_id] = thread
        return thread

    def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread and all its messages. Returns True if existed."""
        with self._lock:
            existed = thread_id in self._threads
            if existed:
                # Explicitly clear the message list before deletion
                self._threads[thread_id].messages.clear()
                del self._threads[thread_id]
        return existed

    def add_message(self, thread_id: str, message: Message) -> None:
        """Append a message to a thread. Raises KeyError if thread not found."""
        with self._lock:
            if thread_id not in self._threads:
                raise KeyError(f"Thread {thread_id!r} not found")
            self._threads[thread_id].messages.append(message)

    # ── Read operations ─────────────────────────────────────────────────────

    def get_thread(self, thread_id: str) -> Thread | None:
        return self._threads.get(thread_id)

    def list_threads(self) -> list[dict]:
        """Return summary dicts for all threads (without messages)."""
        return [t.to_dict(include_messages=False) for t in self._threads.values()]

    def get_messages(self, thread_id: str) -> list[dict] | None:
        """Return all messages for a thread as plain dicts, or None if not found."""
        thread = self._threads.get(thread_id)
        if thread is None:
            return None
        # Return copies to preserve isolation
        return [m.to_dict() for m in thread.messages]

    def get_history(self, thread_id: str, max_turns: int = 3) -> list[dict]:
        """
        Return the last `max_turns` conversation turns as plain dicts for the
        LLM prompt.  Each turn = one user message + one assistant message.

        ISOLATION GUARANTEE
        -------------------
        - Only messages belonging to `thread_id` are accessed.
        - Returns new plain-dict objects (never live Message references).
        - An empty list is returned if the thread is not found — callers
          cannot accidentally receive another thread's history.

        Returns an empty list if the thread is not found or has no messages.
        """
        thread = self._threads.get(thread_id)
        if thread is None:
            return []

        # list() wraps the slice to make the copy explicit and unmistakable.
        # thread.messages[x:] already produces a new list in CPython, but the
        # explicit list() call documents intent and future-proofs against any
        # assignment optimisations that might re-use the backing array.
        recent = list(thread.messages[-(max_turns * 2):])

        # Build plain-dict copies — callers cannot mutate Thread internal state.
        return [{"role": m.role, "content": m.content} for m in recent]

    def thread_exists(self, thread_id: str) -> bool:
        return thread_id in self._threads

    @property
    def count(self) -> int:
        return len(self._threads)


# ---------------------------------------------------------------------------
# Module-level singleton  (FastAPI dependency)
# ---------------------------------------------------------------------------

_store = ThreadStore()


def get_store() -> ThreadStore:
    """FastAPI dependency — returns the shared ThreadStore singleton."""
    return _store
