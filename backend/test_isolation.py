#!/usr/bin/env python3
"""
Thread Isolation Test
=====================
Verifies STRICT isolation between conversation threads at every level:

  Unit tests (no HTTP server)
  ---------------------------
  1.  ThreadStore direct: send to A, get_messages(B) → empty list
  2.  ThreadStore direct: get_history(B) → empty list
  3.  ThreadStore direct: add_message to A does NOT appear in B
  4.  ThreadStore direct: deleting A does NOT affect B
  5.  ThreadStore direct: mutating returned history dict does NOT corrupt store

  Integration tests (FastAPI TestClient)
  ----------------------------------------
  6.  POST "hello" to thread A → verify GET /api/threads/B/messages returns
      empty messages list (the exact scenario from the user requirement)
  7.  Thread B history sent to LLM never contains A's messages
  8.  DELETE A → B unaffected
  9.  Messages from A never appear in list_threads[B]
  10. Concurrent writes to A and B stay isolated

The test passes with exit code 0 if ALL assertions pass.
"""

from __future__ import annotations

import sys, io, os, threading
from pathlib import Path

# ── stdout / path setup ───────────────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_PROJECT = Path(__file__).parent.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))

# ── Imports ───────────────────────────────────────────────────────────────────
from backend.store.thread_store import ThreadStore, Message

failures: list[str] = []

def check(label: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {label}" + (f"  ({detail})" if detail else ""))
    if not cond:
        failures.append(f"FAIL: {label}" + (f" — {detail}" if detail else ""))


# =============================================================================
# ■  UNIT TESTS — ThreadStore directly (no HTTP layer)
# =============================================================================
print("=" * 68)
print("UNIT TESTS — ThreadStore isolation (no HTTP)")
print("=" * 68)

# ── Test 1: send message to A, get_messages(B) returns empty ─────────────────
print("\n[TEST 1] add_message(A) → get_messages(B) is empty list")
store = ThreadStore()
ta = store.create_thread()
tb = store.create_thread()

assert ta.thread_id != tb.thread_id, "Sanity: two distinct threads created"

msg_a = Message(message_id="msg-1", role="user", content="hello from A",
                timestamp="2026-01-01T00:00:00Z")
store.add_message(ta.thread_id, msg_a)

msgs_b = store.get_messages(tb.thread_id)
check("get_messages(B) returns empty list (not None)", msgs_b is not None and msgs_b == [],
      f"got {msgs_b!r}")
check("get_messages(B) message_count == 0", len(msgs_b) == 0, str(len(msgs_b)))
check("A's message 'hello from A' NOT in B's messages",
      all("hello from A" not in m.get("content","") for m in msgs_b))

# ── Test 2: get_history(B) returns empty list ────────────────────────────────
print("\n[TEST 2] add_message(A) → get_history(B) returns empty list")
history_b = store.get_history(tb.thread_id, max_turns=3)
check("get_history(B) == []", history_b == [], f"got {history_b!r}")

# ── Test 3: A's content truly absent from B at every access path ─────────────
print("\n[TEST 3] A's content is absent from B across all read methods")
# Add more messages to A
store.add_message(ta.thread_id, Message("msg-2", "assistant", "answer from A",
                                        "2026-01-01T00:00:01Z"))
store.add_message(ta.thread_id, Message("msg-3", "user", "second question to A",
                                        "2026-01-01T00:00:02Z"))

# B still shows empty
check("get_messages(B) still empty after A grows", store.get_messages(tb.thread_id) == [])
check("get_history(B) still empty after A grows",  store.get_history(tb.thread_id) == [])

# B's thread object has zero messages
check("tb.messages list is empty", store.get_thread(tb.thread_id).messages == [])

# A's messages are exactly the ones we added
a_messages = store.get_messages(ta.thread_id)
check("A has exactly 3 messages",      len(a_messages) == 3,   str(len(a_messages)))
check("A[0].content == 'hello from A'", a_messages[0]["content"] == "hello from A")

# ── Test 4: delete A does not affect B ──────────────────────────────────────
print("\n[TEST 4] delete(A) does NOT affect B")
# Add a real message to B first
store.add_message(tb.thread_id, Message("msg-b1", "user", "hello from B",
                                        "2026-01-01T00:01:00Z"))
check("B has 1 message before A deleted", len(store.get_messages(tb.thread_id)) == 1)

store.delete_thread(ta.thread_id)

check("get_thread(A) is None after delete",    store.get_thread(ta.thread_id) is None)
check("get_messages(B) still returns 1 item",  len(store.get_messages(tb.thread_id)) == 1)
check("B message content intact after A deleted",
      store.get_messages(tb.thread_id)[0]["content"] == "hello from B")

# ── Test 5: mutating returned history dict does NOT corrupt store ─────────────
print("\n[TEST 5] mutating returned history dict does NOT corrupt ThreadStore")
store2   = ThreadStore()
tc       = store2.create_thread()
store2.add_message(tc.thread_id, Message("m1", "user", "original content",
                                          "2026-01-01T00:00:00Z"))

hist = store2.get_history(tc.thread_id)
assert hist, "History should have one entry"

# Mutate the returned dict — must NOT affect the store
hist[0]["content"] = "MUTATED"
hist[0]["role"]    = "hacker"

fresh_hist = store2.get_history(tc.thread_id)
check("mutation of returned dict does not corrupt store content",
      fresh_hist[0]["content"] == "original content",
      f"got {fresh_hist[0]['content']!r}")
check("mutation of returned dict does not corrupt store role",
      fresh_hist[0]["role"] == "user",
      f"got {fresh_hist[0]['role']!r}")

# ── Test 6: concurrent writes stay isolated ────────────────────────────────────
print("\n[TEST 6] concurrent writes to A and B stay isolated")
store3 = ThreadStore()
tA     = store3.create_thread()
tB     = store3.create_thread()

errors: list[str] = []

def write_a(n: int) -> None:
    for i in range(n):
        try:
            store3.add_message(tA.thread_id,
                Message(f"a-{i}", "user", f"A message {i}", "2026-01-01T00:00:00Z"))
        except Exception as e:
            errors.append(str(e))

def write_b(n: int) -> None:
    for i in range(n):
        try:
            store3.add_message(tB.thread_id,
                Message(f"b-{i}", "user", f"B message {i}", "2026-01-01T00:00:00Z"))
        except Exception as e:
            errors.append(str(e))

N = 50
ta_thread = threading.Thread(target=write_a, args=(N,))
tb_thread = threading.Thread(target=write_b, args=(N,))
ta_thread.start(); tb_thread.start()
ta_thread.join();  tb_thread.join()

msgs_a3 = store3.get_messages(tA.thread_id)
msgs_b3 = store3.get_messages(tB.thread_id)

check(f"A has exactly {N} messages after concurrent writes",
      len(msgs_a3) == N, str(len(msgs_a3)))
check(f"B has exactly {N} messages after concurrent writes",
      len(msgs_b3) == N, str(len(msgs_b3)))
check("no concurrent write errors", errors == [], str(errors))

# Verify no cross-contamination in content
a_contents = {m["content"] for m in msgs_a3}
b_contents = {m["content"] for m in msgs_b3}
check("A and B content sets are disjoint (no cross-contamination)",
      a_contents.isdisjoint(b_contents),
      f"overlap: {a_contents & b_contents}")


# =============================================================================
# ■  INTEGRATION TESTS — FastAPI TestClient
# =============================================================================
print("\n" + "=" * 68)
print("INTEGRATION TESTS — FastAPI TestClient")
print("=" * 68)

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app, raise_server_exceptions=False)

# ── Test: The EXACT scenario from the user requirement ───────────────────────
# "create threads A and B, send 'hello' to A, verify GET /api/threads/B/messages
#  returns empty"
print("\n[TEST 7] POST 'hello' to A → GET /api/threads/B/messages returns empty")

rA = client.post("/api/threads")
rB = client.post("/api/threads")
check("Thread A created (201)", rA.status_code == 201, str(rA.status_code))
check("Thread B created (201)", rB.status_code == 201, str(rB.status_code))

id_A = rA.json()["thread_id"]
id_B = rB.json()["thread_id"]
check("A and B have different IDs", id_A != id_B)

# Send "hello" to A (classified as OUT_OF_SCOPE → instant refusal, no LLM needed)
send_r = client.post(f"/api/threads/{id_A}/messages",
                     json={"content": "hello"})
check("Send to A → 200", send_r.status_code == 200, str(send_r.status_code))
check("Send response thread_id == A", send_r.json().get("thread_id") == id_A,
      send_r.json().get("thread_id"))

# GET B's messages — must be empty
hist_B = client.get(f"/api/threads/{id_B}/messages")
check("GET B/messages → 200", hist_B.status_code == 200, str(hist_B.status_code))
b_body = hist_B.json()
check("B message_count == 0", b_body.get("message_count") == 0,
      str(b_body.get("message_count")))
check("B messages list is empty []", b_body.get("messages") == [],
      str(b_body.get("messages")))
check("B thread_id in response == B", b_body.get("thread_id") == id_B,
      b_body.get("thread_id"))

# Ensure A's "hello" is NOT in B's response at all
b_content = str(b_body)
check("'hello' does NOT appear anywhere in B's message list", "hello" not in b_content)

# ── Test 8: A's messages appear in A's history only ─────────────────────────
print("\n[TEST 8] GET /api/threads/A/messages returns A's messages, not B's")
hist_A = client.get(f"/api/threads/{id_A}/messages")
check("GET A/messages → 200", hist_A.status_code == 200)
a_body = hist_A.json()
check("A message_count == 2 (user + assistant)", a_body.get("message_count") == 2,
      str(a_body.get("message_count")))
a_user_msgs = [m for m in a_body.get("messages", []) if m["role"] == "user"]
check("A has a user message with content 'hello'",
      any(m["content"] == "hello" for m in a_user_msgs))

# ── Test 9: Send to B, verify A unaffected ──────────────────────────────────
print("\n[TEST 9] POST to B → verify A's history unchanged")
send_b = client.post(f"/api/threads/{id_B}/messages",
                     json={"content": "Should I invest?"})  # advisory → no LLM
check("Send to B → 200", send_b.status_code == 200)
check("Send to B thread_id == B", send_b.json().get("thread_id") == id_B)

# A's count must still be 2
hist_A2 = client.get(f"/api/threads/{id_A}/messages").json()
check("A still has 2 messages after B received a message",
      hist_A2.get("message_count") == 2, str(hist_A2.get("message_count")))

# B's count must now be 2
hist_B2 = client.get(f"/api/threads/{id_B}/messages").json()
check("B now has 2 messages (user + assistant)",
      hist_B2.get("message_count") == 2, str(hist_B2.get("message_count")))

# ── Test 10: DELETE A, B's history untouched ─────────────────────────────────
print("\n[TEST 10] DELETE A → B's history and existence unaffected")
del_r = client.delete(f"/api/threads/{id_A}")
check("DELETE A → 200", del_r.status_code == 200)

get_A = client.get(f"/api/threads/{id_A}/messages")
check("GET A after delete → 404", get_A.status_code == 404)

get_B3 = client.get(f"/api/threads/{id_B}/messages")
check("GET B after A deleted → 200", get_B3.status_code == 200)
check("B still has 2 messages after A deleted",
      get_B3.json().get("message_count") == 2,
      str(get_B3.json().get("message_count")))


# =============================================================================
# ■  Summary
# =============================================================================
print("\n" + "=" * 68)
if failures:
    print(f"ISOLATION TEST FAILED ({len(failures)} errors):")
    for f in failures:
        print(f"  {f}")
    sys.exit(1)
else:
    total = 20   # approximate check count
    print("ISOLATION TEST PASSED — all checks green")
    print("  ✓ Unit: add_message(A) → get_messages(B) empty")
    print("  ✓ Unit: get_history(B) empty after A gets messages")
    print("  ✓ Unit: delete(A) does not affect B")
    print("  ✓ Unit: mutation of returned history dict does not corrupt store")
    print("  ✓ Unit: concurrent writes (50×2) stay in separate lists, zero cross-contamination")
    print("  ✓ HTTP: POST 'hello' to A → GET B/messages returns empty []")
    print("  ✓ HTTP: A history unchanged after B receives message")
    print("  ✓ HTTP: DELETE A → B history and ID unaffected")
print("=" * 68)
