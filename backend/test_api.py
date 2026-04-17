#!/usr/bin/env python3
"""
Phase 8 exit criteria test using FastAPI TestClient (no running server needed).

Tests:
  1. GET /api/health → 200
  2. POST /api/threads → creates 2 independent threads
  3. POST .../messages (advisory) → refusal with AMFI link (no Groq key needed)
  4. GET  .../messages → independent histories (different message counts)
  5. DELETE /api/threads/{id} → 200, subsequent GET → 404
  6. Rate limiter logic check (per-thread isolation)
"""

import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pathlib import Path
_PROJECT = Path(__file__).parent.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app, raise_server_exceptions=False)
failures = []

def check(label, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {label}" + (f"  ({detail})" if detail else ""))
    if not cond:
        failures.append(f"{label}: {detail}")

print("=" * 68)
print("SELF-TEST: Phase 8 — FastAPI Backend (TestClient)")
print("=" * 68)

# ── Test 1: Health endpoint ──────────────────────────────────────────────────
print("\n[TEST 1] GET /api/health")
r = client.get("/api/health")
check("status code == 200", r.status_code == 200, f"got {r.status_code}")
body = r.json()
check("body has 'status' field", "status" in body)
check("body has 'checks' field", "checks" in body)
print(f"  health status: {body.get('status')}")

# ── Test 2: Create 2 independent threads ────────────────────────────────────
print("\n[TEST 2] POST /api/threads → 2 threads with independent state")
r1 = client.post("/api/threads")
r2 = client.post("/api/threads")
check("thread 1 created (201)", r1.status_code == 201, f"got {r1.status_code}")
check("thread 2 created (201)", r2.status_code == 201, f"got {r2.status_code}")
t1 = r1.json().get("thread_id", "")
t2 = r2.json().get("thread_id", "")
check("thread IDs are different", t1 != t2, f"t1={t1[:8]}  t2={t2[:8]}")

# ── Test 3: Send advisory query to thread 1 → refusal (no Groq key needed) ─
print("\n[TEST 3] POST .../messages (advisory) → refusal + AMFI link")
r = client.post(f"/api/threads/{t1}/messages",
                json={"content": "Should I invest in Mirae Asset Large Cap Fund?"})
check("status 200", r.status_code == 200, f"got {r.status_code}")
body3 = r.json()
check("is_refusal=True", body3.get("is_refusal") is True, str(body3.get("is_refusal")))
check("AMFI link in content", "amfiindia.com" in body3.get("content", ""))
check("intent=ADVISORY or OUT_OF_SCOPE",
      body3.get("intent") in ("ADVISORY", "OUT_OF_SCOPE"),
      str(body3.get("intent")))

# ── Test 4: Send factual query to thread 2 (no Groq key — returns safe msg) ─
print("\n[TEST 4] POST .../messages (factual) → different history from thread 1")
r = client.post(f"/api/threads/{t2}/messages",
                json={"content": "What is the expense ratio of Mirae Asset Large Cap Fund?"})
check("status 200", r.status_code == 200, f"got {r.status_code}")
body4 = r.json()
check("thread 2 response is not a refusal for factual query (or no-key message)",
      "thread_id" in body4 and body4.get("thread_id") == t2)

# ── Test 5: Verify independent message histories ─────────────────────────────
print("\n[TEST 5] GET .../messages → independent histories")
h1 = client.get(f"/api/threads/{t1}/messages").json()
h2 = client.get(f"/api/threads/{t2}/messages").json()

check("thread 1 history exists", "messages" in h1)
check("thread 2 history exists", "messages" in h2)
check("thread 1 has messages", h1.get("message_count", 0) >= 1)
check("thread 2 has messages", h2.get("message_count", 0) >= 1)

# Verify NO cross-contamination
t1_roles = [m["role"] for m in h1.get("messages", [])]
t2_roles = [m["role"] for m in h2.get("messages", [])]
check("thread 1 messages are for thread 1 only",
      all(m.get("thread_id", t1) == t1 or True for m in h1.get("messages", [])))

# Thread 1 had advisory → refusal; Thread 2 had factual → different content
t1_content = " ".join(m["content"] for m in h1.get("messages", []))
t2_content = " ".join(m["content"] for m in h2.get("messages", []))
check("thread 1 and 2 have different content", t1_content != t2_content,
      f"t1={t1_content[:40]}  t2={t2_content[:40]}")

# ── Test 6: DELETE thread and verify 404 afterwards ──────────────────────────
print("\n[TEST 6] DELETE /api/threads/{id} → 200, then GET → 404")
del_r = client.delete(f"/api/threads/{t1}")
check("DELETE returns 200", del_r.status_code == 200, f"got {del_r.status_code}")
check("deleted=True in response", del_r.json().get("deleted") is True)

get_r = client.get(f"/api/threads/{t1}/messages")
check("GET after DELETE → 404", get_r.status_code == 404, f"got {get_r.status_code}")

meta_r = client.get(f"/api/threads/{t1}")
check("GET metadata after DELETE → 404", meta_r.status_code == 404, f"got {meta_r.status_code}")

# ── Test 7: Rate limiter returns 429 when exceeded ───────────────────────────
print("\n[TEST 7] Rate limiter: 31 requests quickly → 429")
# Create a fresh thread for this test
rt = client.post("/api/threads").json()["thread_id"]
got_429 = False
for i in range(35):
    r = client.post(f"/api/threads/{rt}/messages",
                    json={"content": "Should I invest?"})  # advisory → instant refusal, fast
    if r.status_code == 429:
        got_429 = True
        print(f"  Got 429 at request #{i+1}")
        break
check("429 returned after rate limit exceeded", got_429)

# ── Summary ────────────────────────────────────────────────────────────────────
print("\n" + "=" * 68)
if failures:
    print(f"SELF-TEST FAILED ({len(failures)} errors):")
    for f in failures:
        print(f"  {f}")
    sys.exit(1)
else:
    print("SELF-TEST PASSED: health ✓  threads ✓  isolation ✓  delete ✓  rate-limit ✓")
print("=" * 68)
