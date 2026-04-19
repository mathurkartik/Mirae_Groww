#!/usr/bin/env python3
"""
Phase 6 — Query Guard (Intent Classifier)
==========================================
Classifies every incoming query as one of three intents *before* calling the
LLM.  The classification drives two outcomes:

  FACTUAL      → proceed to retriever → generator
  ADVISORY     → return refusal + AMFI link (no LLM call, no cost)
  OUT_OF_SCOPE → return refusal + AMFI link (no LLM call, no cost)

Two-stage classification
------------------------
  Stage 1 — keyword matching (zero-latency, zero API cost)
    A curated list of advisory/OOS phrases is checked against the
    lower-cased query.  Clear-cut cases are resolved here without any
    network call.

  Stage 2 — LLM classification via Groq (optional, ambiguous queries only)
    When keyword matching returns no match, a short Groq prompt is used to
    classify the query.  This stage is SKIPPED if GROQ_API_KEY is absent
    (falls back to FACTUAL).

Refusal message (verbatim from architecture spec section 7)
-----------------------------------------------------------
  "I'm a facts-only assistant and cannot provide investment advice,
   recommendations, or opinions. For guidance on mutual fund investing,
   please visit the AMFI Investor Education portal at
   https://www.amfiindia.com/investor-corner/knowledge-center.

   Facts-only. No investment advice."

Usage (standalone test)
-----------------------
  python backend/core/query_guard.py --self-test
  python backend/core/query_guard.py --query "What is the SIP amount?"

Environment variables
---------------------
  GROQ_API_KEY   (from .env)  – required only for Stage-2 LLM classification
  GROQ_MODEL     (optional)   – Groq model to use (default: llama3-8b-8192)
"""

from __future__ import annotations

import io
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path — ensure project root importable
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
_PROJECT = _HERE.parent.parent
if str(_PROJECT) not in sys.path:
    sys.path.insert(0, str(_PROJECT))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("query_guard")

# ---------------------------------------------------------------------------
# Load .env  (GROQ_API_KEY must never be hardcoded)
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_PROJECT / ".env", override=False)
except ImportError:
    pass   # python-dotenv optional at import time; key may already be in env

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

# ---------------------------------------------------------------------------
# Intent constants
# ---------------------------------------------------------------------------
INTENT_FACTUAL      = "FACTUAL"
INTENT_ADVISORY     = "ADVISORY"
INTENT_OUT_OF_SCOPE = "OUT_OF_SCOPE"
INTENT_MATH_QUERY   = "MATH_QUERY"

# ---------------------------------------------------------------------------
# Refusal & redirect messages  (verbatim per architecture spec section 7)
# ---------------------------------------------------------------------------
AMFI_LINK = "https://www.amfiindia.com/investor-corner/knowledge-center"

REFUSAL_ADVISORY = (
    "I'm a facts-only assistant and cannot provide investment advice, "
    "recommendations, or opinions. For guidance on mutual fund investing, "
    f"please visit the AMFI Investor Education portal at {AMFI_LINK}.\n\n"
    "Facts-only. No investment advice."
)

REFUSAL_OUT_OF_SCOPE = (
    "I can only answer factual questions about Mirae Asset mutual fund schemes "
    "available on Groww. Your question appears to be outside my scope. "
    "For general mutual fund education, please visit the AMFI Investor Education "
    f"portal at {AMFI_LINK}.\n\nFacts-only. No investment advice."
)

REFUSAL_MATH_REDIRECT = (
    "I can help you with that using our interactive calculator. "
    "The calculator lets you simulate SIP or one-time investments with custom return rates and periods. "
    "Please use the SIP Calculator tab to project your investment growth.\n\n"
    "Facts-only. No investment advice."
)

# ---------------------------------------------------------------------------
# Stage-1 keyword lists
# ---------------------------------------------------------------------------

# Advisory patterns: any match → ADVISORY (checked as lower-cased substrings)
_ADVISORY_PHRASES: list[str] = [
    # User intent keywords
    "should i invest",
    "should i switch",
    "should i redeem",
    "should i sell",
    "should i buy",
    "is it good to invest",
    "is it safe to invest",
    "safe to invest",
    "good to invest",
    "worth investing",
    "is this fund good",
    # Explicit advice requests
    "recommend",
    "which fund should",
    "which is better",
    "which is the best",
    "is better",          # catches "which fund is better"
    "better fund",
    "best fund",
    "tell me which fund",
    "good fund",
    "better for",         # catches "better for long term"
    "good for long term",
    "good for investment",
    # Prediction / return speculation
    "will returns",
    "will it grow",
    "what will the return",
    "expected return",
    "future return",
    "will double",
    "will the nav",
    "will be good",       # catches "will the returns be good"
    "returns be",         # catches "will returns be ..."
    "returns will",
    "be good this",
    # Comparison
    "compare funds",
    "compare mirae",
    "outperforms",
    "beats the market",
    "better than",
    "vs ",  # "fund A vs fund B"
    "versus",
    # Other advisory signals
    "should i continue",
    "is it right to",
    "long term investment",
    "short term investment",
]

# Out-of-scope patterns: topics clearly outside the corpus
_OOS_PHRASES: list[str] = [
    "stock price",
    "share price",
    "equity price",
    "crypto",
    "bitcoin",
    "ethereum",
    "real estate",
    "property price",
    "gold price",
    "silver price",
    "fixed deposit",
    " fd ",
    "ppf",
    "nps ",
    "national pension",
    "insurance premium",
    "term insurance",
    "health insurance",
    "weather",
    "cricket",
    "movie",
    "politics",
    "election",
    "ipo ",
    "unlisted share",
    "loan interest",
    "home loan",
    "personal loan",
]

# Math query patterns: triggers calculator redirect
_MATH_PHRASES: list[str] = [
    "calculate sip",
    "sip calculation",
    "calculate returns",
    "future value",
    "corpus after",
    "how much will",
    "what will be the",
    "sip calculator",
    "lumpsum calculator",
    "investment calculator",
    "calculate investment",
    "sip of ",
    "monthly sip of",
    "invest 5000",
    "invest 10000",
    "maturity value",
    "final amount",
    "step up sip",
    "step-up sip",
]

# Phrases that are commonly mis-flagged: whitelist overrides advisory check
_FACTUAL_OVERRIDES: list[str] = [
    "exit load",            # "exit load" contains "load" but is clearly factual
    "expense ratio",        # factual metric
    "nav as of",            # factual NAV query
    "minimum sip",          # factual minimum
    "what is the",          # "what is the best ..." may be advisory, but simple "what is the NAV" is factual
]

# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class GuardResult:
    intent:          str            # FACTUAL | ADVISORY | OUT_OF_SCOPE
    refusal_message: str | None     # set only for ADVISORY / OUT_OF_SCOPE
    matched_phrase:  str | None     # which keyword triggered the decision
    stage:           str            # "keyword" | "llm" | "default"

    @property
    def is_allowed(self) -> bool:
        return self.intent == INTENT_FACTUAL

    @property
    def is_refusal(self) -> bool:
        return not self.is_allowed

    @property
    def is_math_redirect(self) -> bool:
        return self.intent == INTENT_MATH_QUERY


# ---------------------------------------------------------------------------
# Stage-1: keyword matching
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lower-case, collapse whitespace, strip punctuation for matching."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _keyword_classify(query: str) -> GuardResult | None:
    """
    Check query against advisory, math, and OOS phrase lists.

    Returns a GuardResult if a phrase matches, or None if ambiguous.
    Factual overrides are checked first to prevent false positives.
    """
    norm = _normalise(query)

    # Check factual overrides FIRST — prevent common false positives
    for override in _FACTUAL_OVERRIDES:
        if override in norm:
            return GuardResult(
                intent=INTENT_FACTUAL,
                refusal_message=None,
                matched_phrase=f"override:{override}",
                stage="keyword",
            )

    # Priority 2: Check MATH patterns
    for phrase in _MATH_PHRASES:
        if phrase in norm:
            log.info("Query MATH_QUERY: %r matched %r", query[:60], phrase)
            return GuardResult(
                intent=INTENT_MATH_QUERY,
                refusal_message=REFUSAL_MATH_REDIRECT,
                matched_phrase=phrase,
                stage="keyword",
            )

    # Advisory check
    for phrase in _ADVISORY_PHRASES:
        if phrase.strip() in norm:
            log.info("Query ADVISORY (keyword): %r matched %r", query[:60], phrase)
            return GuardResult(
                intent=INTENT_ADVISORY,
                refusal_message=REFUSAL_ADVISORY,
                matched_phrase=phrase,
                stage="keyword",
            )

    # Out-of-scope check
    for phrase in _OOS_PHRASES:
        if phrase.strip() in norm:
            log.info("Query OUT_OF_SCOPE (keyword): %r matched %r", query[:60], phrase)
            return GuardResult(
                intent=INTENT_OUT_OF_SCOPE,
                refusal_message=REFUSAL_OUT_OF_SCOPE,
                matched_phrase=phrase,
                stage="keyword",
            )

    return None  # ambiguous — needs LLM classification


# ---------------------------------------------------------------------------
# Stage-2: LLM classification (Groq)
# ---------------------------------------------------------------------------

_LLM_CLASSIFY_SYSTEM = (
    "You are an intent classifier for a mutual fund FAQ assistant.\n"
    "Classify the user query into exactly one of these three categories:\n\n"
    "  FACTUAL      — asks for a verifiable fact about a mutual fund scheme "
    "(expense ratio, exit load, NAV, SIP amount, etc.) OR asks to calculate a mathematical projection (like historical step-up SIP, compound interest, or lumpsum future value).\n"
    "  ADVISORY     — asks for investment advice, recommendations, comparisons, "
    "or qualitative opinions ('should I invest', 'which is better', 'is it good').\n"
    "  OUT_OF_SCOPE — asks about topics unrelated to Mirae Asset mutual funds "
    "(stocks, crypto, real estate, other AMCs, etc.)\n\n"
    "Respond with ONLY one word: FACTUAL, ADVISORY, or OUT_OF_SCOPE.\n"
    "Do not explain. Do not add punctuation."
)


def _llm_classify(query: str) -> GuardResult:
    """
    Use Groq llama3-8b-8192 to classify ambiguous queries.
    Falls back to FACTUAL if the API call fails or key is missing.
    """
    if not GROQ_API_KEY:
        log.debug("No GROQ_API_KEY — defaulting to FACTUAL for query: %r", query[:60])
        return GuardResult(
            intent=INTENT_FACTUAL,
            refusal_message=None,
            matched_phrase=None,
            stage="default",
        )

    try:
        from groq import Groq
    except ImportError:
        log.warning("groq not installed — defaulting to FACTUAL. pip install groq")
        return GuardResult(
            intent=INTENT_FACTUAL,
            refusal_message=None,
            matched_phrase=None,
            stage="default",
        )

    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": _LLM_CLASSIFY_SYSTEM},
                {"role": "user",   "content": query},
            ],
            max_tokens=5,        # we only need one word
            temperature=0.0,     # deterministic classification
        )
        raw = response.choices[0].message.content.strip().upper()

        # Normalise to one of the three valid intents
        if "ADVISORY" in raw:
            intent = INTENT_ADVISORY
        elif "OUT_OF_SCOPE" in raw or "OUT OF SCOPE" in raw:
            intent = INTENT_OUT_OF_SCOPE
        else:
            intent = INTENT_FACTUAL

        log.info("Query %s (LLM): %r  raw=%r", intent, query[:60], raw)

        if intent == INTENT_ADVISORY:
            return GuardResult(
                intent=INTENT_ADVISORY,
                refusal_message=REFUSAL_ADVISORY,
                matched_phrase="llm_classified",
                stage="llm",
            )
        if intent == INTENT_OUT_OF_SCOPE:
            return GuardResult(
                intent=INTENT_OUT_OF_SCOPE,
                refusal_message=REFUSAL_OUT_OF_SCOPE,
                matched_phrase="llm_classified",
                stage="llm",
            )
        return GuardResult(
            intent=INTENT_FACTUAL,
            refusal_message=None,
            matched_phrase=None,
            stage="llm",
        )

    except Exception as exc:
        log.warning("LLM classification failed (%s) — defaulting to FACTUAL", exc)
        return GuardResult(
            intent=INTENT_FACTUAL,
            refusal_message=None,
            matched_phrase=None,
            stage="default",
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(query: str, *, use_llm: bool = True) -> GuardResult:
    """
    Classify a query as FACTUAL, ADVISORY, or OUT_OF_SCOPE.

    Parameters
    ----------
    query : str
        Raw user query string.
    use_llm : bool
        Whether to fall through to LLM classification for ambiguous queries.
        Set False in unit tests or when Groq key is unavailable.

    Returns
    -------
    GuardResult
        .intent           — "FACTUAL" | "ADVISORY" | "OUT_OF_SCOPE"
        .refusal_message  — pre-built refusal string (None if FACTUAL)
        .matched_phrase   — which keyword/signal triggered the decision
        .stage            — "keyword" | "llm" | "default"
        .is_allowed       — True if query should proceed to retrieval
        .is_refusal       — True if query should receive refusal response
    """
    if not query or not query.strip():
        return GuardResult(
            intent=INTENT_OUT_OF_SCOPE,
            refusal_message=REFUSAL_OUT_OF_SCOPE,
            matched_phrase="empty_query",
            stage="keyword",
        )

    # Stage 1: keyword matching
    result = _keyword_classify(query)
    if result is not None:
        return result

    # Stage 2: LLM classification (optional)
    if use_llm:
        return _llm_classify(query)

    # Default: treat as factual if no signal found and LLM disabled
    log.debug("No keyword match + LLM disabled — defaulting to FACTUAL")
    return GuardResult(
        intent=INTENT_FACTUAL,
        refusal_message=None,
        matched_phrase=None,
        stage="default",
    )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def run_self_test() -> None:
    """
    Exit criteria test:
      - 5 factual queries → all classified FACTUAL
      - 3 advisory queries → all classified ADVISORY/OOS with AMFI link
    """
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
    log.info("SELF-TEST: Query Guard (keyword-only, LLM disabled for test)")
    log.info("=" * 72)

    failures = []

    log.info("\n--- FACTUAL queries (expect: FACTUAL) ---")
    for q in FACTUAL_QUERIES:
        result = classify(q, use_llm=False)
        status = "PASS" if result.intent == INTENT_FACTUAL else "FAIL"
        if status == "FAIL":
            failures.append(f"FACTUAL expected, got {result.intent}: {q!r}")
        log.info("  [%s] %s | intent=%s stage=%s", status, q[:55], result.intent, result.stage)

    log.info("\n--- ADVISORY queries (expect: ADVISORY or OUT_OF_SCOPE) ---")
    for q in ADVISORY_QUERIES:
        result = classify(q, use_llm=False)
        has_amfi = result.refusal_message and AMFI_LINK in result.refusal_message
        ok_intent = result.intent in (INTENT_ADVISORY, INTENT_OUT_OF_SCOPE)
        status = "PASS" if ok_intent and has_amfi else "FAIL"
        if status == "FAIL":
            failures.append(
                f"ADVISORY expected + AMFI link, got intent={result.intent} "
                f"amfi={has_amfi}: {q!r}"
            )
        log.info(
            "  [%s] %s | intent=%s amfi_link=%s stage=%s",
            status, q[:55], result.intent, has_amfi, result.stage,
        )

    log.info("\n" + "=" * 72)
    if failures:
        log.error("SELF-TEST FAILED (%d failures):", len(failures))
        for f in failures:
            log.error("  %s", f)
        sys.exit(1)
    else:
        log.info(
            "SELF-TEST PASSED: %d FACTUAL + %d ADVISORY/OOS all classified correctly",
            len(FACTUAL_QUERIES), len(ADVISORY_QUERIES),
        )
    log.info("=" * 72)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Phase 6 — Query Guard intent classifier"
    )
    parser.add_argument("--query", "-q", default="", help="Query to classify")
    parser.add_argument("--self-test", action="store_true", help="Run self-test suite")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM stage")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return

    if not args.query:
        parser.print_help()
        return

    result = classify(args.query, use_llm=not args.no_llm)
    print(f"\nQuery  : {args.query!r}")
    print(f"Intent : {result.intent}")
    print(f"Stage  : {result.stage}")
    print(f"Phrase : {result.matched_phrase}")
    if result.refusal_message:
        print(f"\nRefusal:\n{result.refusal_message}")


if __name__ == "__main__":
    main()
