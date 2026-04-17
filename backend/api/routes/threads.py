"""
Thread CRUD endpoints
---------------------
  POST   /api/threads               → create thread
  GET    /api/threads               → list all threads
  GET    /api/threads/{thread_id}   → get thread metadata
  DELETE /api/threads/{thread_id}   → delete thread + all messages
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.store.thread_store import ThreadStore, get_store

router = APIRouter(prefix="/threads", tags=["threads"])


# ── POST /api/threads ————————————————————————————————────————————————————————

@router.post("", status_code=201, summary="Create a new conversation thread")
def create_thread(store: ThreadStore = Depends(get_store)) -> dict:
    """
    Creates a new isolated conversation thread.

    Returns the thread_id which must be used in subsequent message calls.
    Each thread has its own independent message history — zero shared state.
    """
    thread = store.create_thread()
    return {
        "thread_id":     thread.thread_id,
        "created_at":    thread.created_at,
        "message_count": 0,
    }


# ── GET /api/threads ————————————————————————————————————————————————————————

@router.get("", summary="List all active conversation threads")
def list_threads(store: ThreadStore = Depends(get_store)) -> dict:
    """Returns a list of all active threads with metadata (no message content)."""
    threads = store.list_threads()
    return {
        "count":   len(threads),
        "threads": threads,
    }


# ── GET /api/threads/{thread_id} ————————————————————————————————————————────

@router.get("/{thread_id}", summary="Get thread metadata")
def get_thread(
    thread_id: str,
    store: ThreadStore = Depends(get_store),
) -> dict:
    """Returns thread metadata including message count. Does not return message content."""
    thread = store.get_thread(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id!r} not found")
    return thread.to_dict(include_messages=False)


# ── DELETE /api/threads/{thread_id} ————————————————————————————————————————

@router.delete("/{thread_id}", status_code=200, summary="Delete a thread and all its messages")
def delete_thread(
    thread_id: str,
    store: ThreadStore = Depends(get_store),
) -> dict:
    """
    Permanently deletes a thread and all its message history.
    The thread_id cannot be reused after deletion.
    """
    deleted = store.delete_thread(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id!r} not found")
    return {
        "deleted":   True,
        "thread_id": thread_id,
    }
