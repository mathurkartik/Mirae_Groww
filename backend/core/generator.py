#!/usr/bin/env python3
"""
Phase 6 — Generator (Groq LLM Integration)
===========================================
Orchestrates the full query → answer flow for a single user turn:

  1. Query Guard  (query_guard.classify)
       ADVISORY / OUT_OF_SCOPE → return refusal immediately, no LLM call.
       FACTUAL → proceed to retrieval + generation.

  2. Retrieval  (retriever.retrieve)
       Hybrid dense+sparse+RRF+rerank → top-3 RetrievedChunk objects.
       If retrieval returns empty, LLM is told context is insufficient.

  3. Prompt Assembly
       System prompt (facts-only rules) + last-3-turn thread history +
       retrieved chunks + user query → single messages list.

  4. Groq LLM call  (llama3-8b-8192)
       API key loaded ONLY from .env / environment — never hardcoded.
       Retry with exponential backoff (max 3 attempts) on transient errors.

  5. Response parsing
       Extract: answer text, citation URL (first Groww URL in response),
       last_updated_date (from "Last updated from sources: YYYY-MM-DD").

Output
------
  GeneratorResult(
      answer:           str       # ≤ 3 sentences
      citation_url:     str       # Groww URL from top retrieved chunk
      last_updated_date: str      # ISO date from chunk metadata
      is_refusal:       bool      # True if advisory/OOS refusal
      retrieval_count:  int       # number of chunks retrieved
      intent:           str       # FACTUAL | ADVISORY | OUT_OF_SCOPE
  )

System Prompt (verbatim from RAG_Architecture.md section "Phase 6")
-------------------------------------------------------------------
  You are a facts-only mutual fund FAQ assistant for Mirae Asset funds.

  STRICT RULES:
  1. Answer ONLY factual, verifiable questions about mutual fund schemes.
  2. Maximum 3 sentences per answer. Never exceed this.
  3. Include EXACTLY ONE citation URL from the provided context.
  4. End every answer with: "Last updated from sources: <last_crawled_date>"
  5. NEVER provide investment advice, recommendations, comparisons, or return predictions.
  6. If context is insufficient, respond: "I don't have this information in my current
     sources. Please check https://groww.in/mutual-funds for the latest details."
  7. NEVER fabricate data. If unsure, say you don't have it.

  Facts-only. No investment advice.

CLI
---
  python backend/core/generator.py --query "expense ratio Mirae Asset Large Cap"
  python backend/core/generator.py --self-test   (requires GROQ_API_KEY in .env)
  python backend/core/generator.py --guard-test  (no GROQ_API_KEY needed)

Environment variables
---------------------
  GROQ_API_KEY         (from .env) — REQUIRED for LLM generation
  GROQ_MODEL           default: llama3-8b-8192
  GROQ_MAX_TOKENS      default: 256   (≤3 sentences fits well within this)
  GROQ_TEMPERATURE     default: 0.1   (low temperature for factual consistency)
  GROQ_TIMEOUT         default: 30    (seconds)
  GROQ_MAX_RETRIES     default: 3
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# sys.path patch
# ---------------------------------------------------------------------------
_HERE    = Path(__file__).parent          # backend/core/
_BACKEND = _HERE.parent                   # backend/
_PROJECT = _BACKEND.parent                # project root
for _p in [str(_PROJECT), str(_BACKEND)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    handlers=[logging.StreamHandler(_utf8_stdout)],
)
log = logging.getLogger("generator")

# ---------------------------------------------------------------------------
# Load .env — API key must NEVER be hardcoded
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_PROJECT / ".env", override=False)
except ImportError:
    pass   # python-dotenv optional; key may already be in environment

GROQ_API_KEY     = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL       = os.environ.get("GROQ_MODEL",       "llama3-8b-8192")
GROQ_MAX_TOKENS  = int(os.environ.get("GROQ_MAX_TOKENS",  "256"))
GROQ_TEMPERATURE = float(os.environ.get("GROQ_TEMPERATURE", "0.1"))
GROQ_TIMEOUT     = int(os.environ.get("GROQ_TIMEOUT",     "30"))
GROQ_MAX_RETRIES = int(os.environ.get("GROQ_MAX_RETRIES", "3"))

# Groww URL pattern — used to extract citation from LLM response
_GROWW_URL_RE = re.compile(
    r"https://groww\.in/mutual-funds/[\w\-]+"
)
# "Last updated from sources: YYYY-MM-DD" pattern
_LAST_UPDATED_RE = re.compile(
    r"Last updated from sources:\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# System prompt (verbatim from RAG_Architecture.md Phase 6)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a facts-only mutual fund FAQ assistant for Mirae Asset funds.

STRICT RULES:
1. Answer ONLY factual, verifiable questions about mutual fund schemes.
2. Maximum 3 sentences per answer. Never exceed this.
3. Include EXACTLY ONE citation URL from the provided context.
4. End every answer with: "Last updated from sources: <last_crawled_date>"
5. NEVER provide investment advice, recommendations, comparisons, or return predictions.
6. If context is insufficient, respond: "I don't have this information in my current sources. Please check https://groww.in/mutual-funds for the latest details."
7. NEVER fabricate data. If unsure, say you don't have it.

Facts-only. No investment advice."""

# Sentinel used when no retrieved context is available
_NO_CONTEXT_RESPONSE = (
    "I don't have this information in my current sources. "
    "Please check https://groww.in/mutual-funds for the latest details."
)

# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class GeneratorResult:
    """Structured output returned to the FastAPI endpoint."""
    answer:            str            # Final answer text (≤ 3 sentences)
    citation_url:      str            # Groww URL from retrieved context
    last_updated_date: str            # ISO date from chunk metadata
    is_refusal:        bool           # True if query was ADVISORY/OOS
    retrieval_count:   int            # How many chunks were retrieved
    intent:            str            # FACTUAL | ADVISORY | OUT_OF_SCOPE
    chunks_used:       list[dict] = field(default_factory=list)  # debug only

    def to_dict(self) -> dict:
        return {
            "answer":            self.answer,
            "citation_url":      self.citation_url,
            "last_updated_date": self.last_updated_date,
            "is_refusal":        self.is_refusal,
            "retrieval_count":   self.retrieval_count,
            "intent":            self.intent,
        }


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def _build_context_block(chunks: list) -> str:
    """
    Format retrieved chunks into a numbered context block for the LLM prompt.

    Each entry contains: source URL, scheme name, section heading, content.
    The LLM is instructed to cite EXACTLY ONE URL from this block.
    """
    if not chunks:
        return "No relevant context found."

    lines: list[str] = ["[RETRIEVED CONTEXT]"]
    for i, chunk in enumerate(chunks, 1):
        # Handle both RetrievedChunk dataclass and plain dict
        if hasattr(chunk, "source_url"):
            url     = chunk.source_url
            scheme  = chunk.scheme_name
            heading = chunk.section_heading
            content = chunk.content
            updated = chunk.last_crawled_date
        else:
            url     = chunk.get("source_url", "")
            scheme  = chunk.get("scheme_name", "")
            heading = chunk.get("section_heading", "")
            content = chunk.get("content", "")
            updated = chunk.get("last_crawled_date", "")

        lines.append(
            f"\nSource {i}:\n"
            f"  URL: {url}\n"
            f"  Scheme: {scheme}\n"
            f"  Section: {heading}\n"
            f"  Last updated: {updated}\n"
            f"  Content: {content}"
        )

    return "\n".join(lines)


def _build_history_block(thread_history: list[dict], max_turns: int = 3) -> str:
    """
    Format the last N conversation turns for the LLM prompt.

    thread_history is a list of {"role": "user"|"assistant", "content": "..."}
    Only the last max_turns complete turns (user + assistant pairs) are used.
    Empty history returns an empty string (no block injected).
    """
    if not thread_history:
        return ""

    # Take the last 2*max_turns messages (each turn = user + assistant)
    recent = thread_history[-(max_turns * 2):]

    lines = ["[CONVERSATION HISTORY]"]
    for msg in recent:
        role    = msg.get("role", "user").capitalize()
        content = msg.get("content", "").strip()
        lines.append(f"{role}: {content}")

    return "\n".join(lines)


def _build_messages(
    query: str,
    chunks: list,
    thread_history: list[dict],
) -> list[dict]:
    """
    Assemble the full messages list for the Groq chat completion API.

    Structure:
      [system]   SYSTEM_PROMPT
      [user]     CONTEXT BLOCK + HISTORY BLOCK + CURRENT QUERY
    """
    context_block  = _build_context_block(chunks)
    history_block  = _build_history_block(thread_history)

    user_parts: list[str] = [context_block]
    if history_block:
        user_parts.append(history_block)
    user_parts.append(f"[CURRENT QUESTION]\nUser: {query}")

    user_content = "\n\n".join(user_parts)

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _extract_citation(text: str, chunks: list) -> str:
    """
    Extract a citation URL from the LLM response.

    Priority:
      1. First Groww URL found in the LLM's response text.
      2. Source URL from the top retrieved chunk (the LLM was instructed
         to cite from context — use top chunk as authoritative fallback).
      3. Fallback: https://groww.in/mutual-funds
    """
    # Priority 1: URL in LLM response
    m = _GROWW_URL_RE.search(text)
    if m:
        return m.group(0)

    # Priority 2: Top chunk URL
    if chunks:
        chunk = chunks[0]
        url = chunk.source_url if hasattr(chunk, "source_url") else chunk.get("source_url", "")
        if url:
            return url

    # Priority 3: Generic fallback
    return "https://groww.in/mutual-funds"


def _extract_last_updated(text: str, chunks: list) -> str:
    """
    Extract the last_updated_date from:
      1. "Last updated from sources: YYYY-MM-DD" in LLM response.
      2. last_crawled_date from the top retrieved chunk.
      3. Today's date as fallback.
    """
    m = _LAST_UPDATED_RE.search(text)
    if m:
        return m.group(1)

    if chunks:
        chunk = chunks[0]
        date = (
            chunk.last_crawled_date
            if hasattr(chunk, "last_crawled_date")
            else chunk.get("last_crawled_date", "")
        )
        if date:
            return date

    from datetime import date
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Groq API call with retry
# ---------------------------------------------------------------------------

def _call_groq(messages: list[dict]) -> str:
    """
    Call the Groq chat completions API with retry + exponential backoff.

    Returns the assistant's response text.
    Raises RuntimeError after GROQ_MAX_RETRIES failed attempts.
    """
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is not set. Add it to .env file:\n"
            "  GROQ_API_KEY=gsk_...\n"
            "Never hardcode the key in source files."
        )

    try:
        from groq import Groq, APIError, RateLimitError
    except ImportError:
        raise ImportError(
            "groq package not installed. Run:\n"
            "  pip install groq"
        )

    client = Groq(api_key=GROQ_API_KEY)

    for attempt in range(1, GROQ_MAX_RETRIES + 1):
        try:
            log.info(
                "Groq call attempt %d/%d  model=%s  max_tokens=%d",
                attempt, GROQ_MAX_RETRIES, GROQ_MODEL, GROQ_MAX_TOKENS,
            )
            t0 = time.time()

            response = client.chat.completions.create(
                model       = GROQ_MODEL,
                messages    = messages,
                max_tokens  = GROQ_MAX_TOKENS,
                temperature = GROQ_TEMPERATURE,
                timeout     = GROQ_TIMEOUT,
            )

            text = response.choices[0].message.content.strip()
            elapsed = time.time() - t0
            log.info(
                "Groq response received in %.2fs  chars=%d",
                elapsed, len(text),
            )
            return text

        except Exception as exc:
            # Exponential backoff for transient errors
            wait = 2 ** attempt
            log.warning(
                "Groq attempt %d/%d failed: %s — retrying in %ds",
                attempt, GROQ_MAX_RETRIES, exc, wait,
            )
            if attempt < GROQ_MAX_RETRIES:
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"Groq API failed after {GROQ_MAX_RETRIES} attempts: {exc}"
                ) from exc

    raise RuntimeError("Groq call exhausted retries")  # mypy unreachable


# ---------------------------------------------------------------------------
# Public API: generate()
# ---------------------------------------------------------------------------

def generate(
    query: str,
    thread_history: list[dict] | None = None,
    *,
    scheme_filter: str | None = None,
    skip_guard: bool = False,
) -> GeneratorResult:
    """
    Full pipeline: guard → retrieve → generate.

    Parameters
    ----------
    query : str
        Raw user query.
    thread_history : list[dict] | None
        Last N conversation turns as [{role, content}, ...].
        Up to 3 turns are included in the prompt.
    scheme_filter : str | None
        Optional scheme_name to restrict dense retrieval.
    skip_guard : bool
        If True, skip query guard (useful for FastAPI admin endpoints).

    Returns
    -------
    GeneratorResult
    """
    from backend.core.query_guard import classify, INTENT_FACTUAL, REFUSAL_ADVISORY

    thread_history = thread_history or []

    # ---- Step 1: Query Guard ------------------------------------------------
    if not skip_guard:
        guard = classify(query)
        log.info(
            "QueryGuard: intent=%s stage=%s phrase=%s",
            guard.intent, guard.stage, guard.matched_phrase,
        )
        if guard.is_refusal:
            return GeneratorResult(
                answer            = guard.refusal_message or REFUSAL_ADVISORY,
                citation_url      = "https://www.amfiindia.com/investor-corner/knowledge-center",
                last_updated_date = "",
                is_refusal        = True,
                retrieval_count   = 0,
                intent            = guard.intent,
            )
        intent = guard.intent
    else:
        intent = INTENT_FACTUAL

    # ---- Step 2: Retrieve ---------------------------------------------------
    from backend.core.retriever import retrieve

    chunks = retrieve(query, scheme_filter=scheme_filter)
    log.info("Retrieved %d chunk(s) for query: %r", len(chunks), query[:60])

    # ---- Step 3: Build prompt -----------------------------------------------
    messages = _build_messages(query, chunks, thread_history)

    # ---- Step 4: Call Groq --------------------------------------------------
    raw_answer = _call_groq(messages)

    # ---- Step 5: Parse response ---------------------------------------------
    citation_url      = _extract_citation(raw_answer, chunks)
    last_updated_date = _extract_last_updated(raw_answer, chunks)

    chunks_debug = [
        {
            "scheme_name": c.scheme_name if hasattr(c, "scheme_name") else c.get("scheme_name", ""),
            "source_url":  c.source_url  if hasattr(c, "source_url")  else c.get("source_url", ""),
            "score":       c.score       if hasattr(c, "score")       else c.get("score", 0),
        }
        for c in chunks
    ]

    return GeneratorResult(
        answer            = raw_answer,
        citation_url      = citation_url,
        last_updated_date = last_updated_date,
        is_refusal        = False,
        retrieval_count   = len(chunks),
        intent            = intent,
        chunks_used       = chunks_debug,
    )


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def run_guard_test() -> None:
    """
    Guard-only test (no GROQ_API_KEY needed):
    5 factual queries → FACTUAL, 3 advisory queries → ADVISORY/OOS + AMFI link
    """
    from backend.core.query_guard import (
        classify, INTENT_FACTUAL, INTENT_ADVISORY,
        INTENT_OUT_OF_SCOPE, AMFI_LINK,
    )

    FACTUAL_QUERIES = [
        "What is the expense ratio of Mirae Asset Large Cap Fund?",
        "What is the exit load for Mirae Asset ELSS Tax Saver Fund?",
        "What is the minimum SIP amount for Mirae Asset Flexi Cap Fund?",
        "Who is the fund manager of Mirae Asset Midcap Fund?",
        "What is the AUM of Mirae Asset Nifty 50 Index Fund?",
    ]
    ADVISORY_QUERIES = [
        "Should I invest in Mirae Asset Large Cap Fund?",
        "Which Mirae Asset fund is better for long term?",
        "Will the returns of Mirae Asset ELSS fund be good this year?",
    ]

    log.info("=" * 72)
    log.info("GUARD-TEST: 5 FACTUAL + 3 ADVISORY (no Groq key required)")
    log.info("=" * 72)

    failures: list[str] = []

    log.info("\n--- FACTUAL queries ---")
    for q in FACTUAL_QUERIES:
        r = classify(q, use_llm=False)
        ok = r.intent == INTENT_FACTUAL
        log.info("  [%s] %s | intent=%s", "PASS" if ok else "FAIL", q[:55], r.intent)
        if not ok:
            failures.append(f"Expected FACTUAL, got {r.intent}: {q!r}")

    log.info("\n--- ADVISORY queries ---")
    for q in ADVISORY_QUERIES:
        r = classify(q, use_llm=False)
        has_amfi = bool(r.refusal_message and AMFI_LINK in r.refusal_message)
        ok = r.intent in (INTENT_ADVISORY, INTENT_OUT_OF_SCOPE) and has_amfi
        log.info(
            "  [%s] %s | intent=%s amfi=%s",
            "PASS" if ok else "FAIL", q[:55], r.intent, has_amfi,
        )
        if not ok:
            failures.append(
                f"Expected ADVISORY+AMFI, got intent={r.intent} amfi={has_amfi}: {q!r}"
            )

    log.info("\n" + "=" * 72)
    if failures:
        log.error("GUARD-TEST FAILED (%d errors):", len(failures))
        for f in failures:
            log.error("  %s", f)
        sys.exit(1)
    else:
        log.info("GUARD-TEST PASSED: 5 FACTUAL + 3 ADVISORY all classified correctly")
    log.info("=" * 72)


def run_self_test() -> None:
    """
    Full pipeline self-test (requires GROQ_API_KEY in .env).
    Runs 2 factual queries through the full guard → retrieve → generate pipeline.
    """
    if not GROQ_API_KEY:
        log.error(
            "GROQ_API_KEY not found in .env. "
            "Create .env with:\n  GROQ_API_KEY=gsk_...\n"
            "Run --guard-test instead (no key required)."
        )
        sys.exit(1)

    TEST_QUERIES = [
        "What is the expense ratio of Mirae Asset Large Cap Fund?",
        "What is the exit load for Mirae Asset ELSS Tax Saver Fund?",
    ]

    log.info("=" * 72)
    log.info("SELF-TEST: Full pipeline (guard + retrieve + Groq)")
    log.info("Model: %s", GROQ_MODEL)
    log.info("=" * 72)

    failures: list[str] = []

    for q in TEST_QUERIES:
        log.info("\nQuery: %r", q)
        try:
            result = generate(q)
            log.info("  Intent         : %s", result.intent)
            log.info("  Is refusal     : %s", result.is_refusal)
            log.info("  Retrieval count: %d", result.retrieval_count)
            log.info("  Citation URL   : %s", result.citation_url)
            log.info("  Last updated   : %s", result.last_updated_date)
            log.info("  Answer         : %s", result.answer[:200])

            # Validate
            if result.is_refusal:
                failures.append(f"Factual query incorrectly refused: {q!r}")
            if "groww.in" not in result.citation_url:
                failures.append(f"No Groww citation URL: {result.citation_url!r}")

        except Exception as exc:
            failures.append(f"Exception for query {q!r}: {exc}")
            log.error("  ERROR: %s", exc)

    log.info("\n" + "=" * 72)
    if failures:
        log.error("SELF-TEST FAILED:")
        for f in failures:
            log.error("  %s", f)
        sys.exit(1)
    else:
        log.info("SELF-TEST PASSED: all factual queries answered with Groww citations")
    log.info("=" * 72)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Phase 6 — Generator CLI (guard + retrieve + Groq)"
    )
    parser.add_argument("--query",      "-q", default="", help="Query to generate answer for")
    parser.add_argument("--self-test",  action="store_true", help="Run full pipeline self-test (needs GROQ_API_KEY)")
    parser.add_argument("--guard-test", action="store_true", help="Run guard-only test (no GROQ_API_KEY needed)")
    parser.add_argument("--scheme",     default=None, help="Filter results to a specific scheme_name")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return

    if args.guard_test:
        run_guard_test()
        return

    if not args.query:
        parser.print_help()
        return

    if not GROQ_API_KEY:
        log.error("GROQ_API_KEY not set. Add GROQ_API_KEY=... to .env file")
        sys.exit(1)

    result = generate(args.query, scheme_filter=args.scheme)
    print(f"\n{'='*72}")
    print(f"Query  : {args.query}")
    print(f"Intent : {result.intent}")
    print(f"Refusal: {result.is_refusal}")
    print(f"\nAnswer :\n{result.answer}")
    print(f"\nCitation   : {result.citation_url}")
    print(f"Last updated: {result.last_updated_date}")
    print(f"Chunks used : {result.retrieval_count}")
    print(f"{'='*72}\n")


if __name__ == "__main__":
    main()
