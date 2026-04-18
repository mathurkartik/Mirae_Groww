#!/usr/bin/env python3
"""
Phase 7 — Post-Processor & Guardrails
======================================
Validates and sanitises every LLM response before it reaches the user.
All 5 steps run in sequence on every factual (non-refusal) response.

Pipeline (in order)
-------------------
  Step 1  Sentence Count Validator
          Truncate to ≤ 3 sentences using NLTK-style boundary detection.
          The footer sentence ("Last updated from sources: ...") is
          excluded from the count so it never gets truncated.

  Step 2  Citation Validator
          Locate the first Groww URL in the response and verify it exists
          in the data/urls.yaml whitelist.
          • URL found and valid  → keep as-is.
          • URL found but NOT in whitelist → replace with top chunk URL.
          • No URL found at all  → inject top chunk URL into response text.

  Step 3  Footer Injector
          Append "Last updated from sources: <date>" if not already present.
          Date is sourced from: LLM response → top chunk → today's date.

  Step 4  PII Scanner
          Regex scan of the OUTPUT text for:
            - PAN number       [A-Z]{5}[0-9]{4}[A-Z]
            - Aadhaar number   \\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}
            - Indian phone     (\\+?91[\\s-]?)?[6-9]\\d{9}
            - Email address    standard RFC-5322 pattern
            - Bank account     \\d{9,18} (9–18 digit sequence)
          If ANY PII is detected → block the response with a safe fallback.
          PII blocking takes priority over all other steps.

  Step 5  Advisory Content Filter
          Scan the OUTPUT for phrases that indicate advisory content that
          the LLM may have generated despite the system prompt:
            "recommend", "should invest", "better than", "returns will",
            "outperform", "i suggest", "you should", "it is advisable"
          If found → replace the entire answer with the standard refusal.

Behaviour on refusal responses
--------------------------------
  Refusal answers (is_refusal=True) skip steps 1, 2, 3 (no truncation,
  citation, or footer on pre-canned refusals). Steps 4 and 5 still run
  to catch any unexpected content.

Output
------
  PostProcessorResult(
      answer              : str      # final safe answer
      citation_url        : str      # validated/injected URL
      last_updated_date   : str      # ISO date
      is_blocked          : bool     # True if PII blocked the response
      is_replaced         : bool     # True if advisory filter triggered
      was_truncated       : bool     # True if sentence count was reduced
      citation_injected   : bool     # True if URL was injected/replaced
      footer_appended     : bool     # True if footer was added
      pii_types_found     : list[str]
      advisory_triggers   : list[str]
      validation_log      : list[str]# human-readable audit trail per step
  )

Usage (standalone)
------------------
  python backend/core/post_processor.py --self-test
  python backend/core/post_processor.py --demo

Environment variables
---------------------
  URLS_YAML   path to urls yaml   (default: data/urls.yaml)
"""

from __future__ import annotations

import io
import logging
import os
import re
import sys
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

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("post_processor")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
URLS_YAML = Path(os.environ.get("URLS_YAML", _PROJECT / "data" / "urls.yaml"))

MAX_SENTENCES    = 3
FOOTER_PREFIX    = "Last updated from sources:"
FALLBACK_URL     = "https://groww.in/mutual-funds"
GROWW_URL_RE     = re.compile(r"https://groww\.in/mutual-funds/[\w\-]+")
LAST_UPDATED_RE  = re.compile(
    r"Last updated from sources:\s*\d{4}-\d{2}-\d{2}", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Compliance strings (reuse from query_guard rather than duplicating)
# ---------------------------------------------------------------------------
AMFI_LINK = "https://www.amfiindia.com/investor-corner/knowledge-center"

_BLOCKED_RESPONSE = (
    "I'm unable to provide this response due to a data quality issue. "
    "Please check https://groww.in/mutual-funds for accurate information.\n\n"
    "Facts-only. No investment advice."
)

_ADVISORY_REFUSAL = (
    "I'm a facts-only assistant and cannot provide investment advice, "
    "recommendations, or opinions. For guidance on mutual fund investing, "
    f"please visit the AMFI Investor Education portal at {AMFI_LINK}.\n\n"
    "Facts-only. No investment advice."
)

# ---------------------------------------------------------------------------
# Step 4 — PII patterns
# ---------------------------------------------------------------------------
_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    # PAN: 5 uppercase letters, 4 digits, 1 uppercase letter (e.g. ABCDE1234F)
    ("PAN", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),

    # Aadhaar: 12 digits, optionally grouped with spaces or hyphens (82XX XXXX XXXX)
    ("Aadhaar", re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")),

    # Indian phone: optionally prefixed with +91 or 91, then 10 digits starting with 6-9
    ("phone", re.compile(r"(?<!\d)(\+?91[\s\-]?)?[6-9]\d{9}(?!\d)")),

    # Email address
    ("email", re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    )),

    # Bank account number: 9–18 consecutive digits (not part of a longer number)
    ("bank_account", re.compile(r"(?<!\d)\d{9,18}(?!\d)")),
]

# ---------------------------------------------------------------------------
# Step 5 — Advisory content patterns (post-generation check)
# ---------------------------------------------------------------------------
_ADVISORY_OUTPUT_PHRASES: list[str] = [
    "i recommend",
    "recommend this",
    "recommend investing",
    "should invest",
    "you should invest",
    "better than",
    "returns will",
    "outperform",
    "i suggest",
    "you should",
    "it is advisable",
    "advisable to invest",
    "best option",
    "good time to invest",
    "ideal for investors",
]

# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class PostProcessorResult:
    """Final validated answer returned to the API endpoint."""
    answer:             str
    citation_url:       str
    last_updated_date:  str
    is_blocked:         bool            # PII detected in output
    is_replaced:        bool            # Advisory content detected and replaced
    was_truncated:      bool            # Sentence count was reduced
    citation_injected:  bool            # Citation URL was injected or replaced
    footer_appended:    bool            # Footer line was added
    pii_types_found:    list[str]       = field(default_factory=list)
    advisory_triggers:  list[str]       = field(default_factory=list)
    validation_log:     list[str]       = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "answer":            self.answer,
            "citation_url":      self.citation_url,
            "last_updated_date": self.last_updated_date,
            "is_blocked":        self.is_blocked,
            "is_replaced":       self.is_replaced,
            "was_truncated":     self.was_truncated,
            "citation_injected": self.citation_injected,
            "footer_appended":   self.footer_appended,
        }


# ---------------------------------------------------------------------------
# URL whitelist
# ---------------------------------------------------------------------------
_url_whitelist: set[str] | None = None


def _load_url_whitelist() -> set[str]:
    """Load and cache the set of valid Groww URLs from data/urls.yaml."""
    global _url_whitelist
    if _url_whitelist is not None:
        return _url_whitelist

    if not URLS_YAML.exists():
        log.warning("urls.yaml not found at %s — citation whitelist is empty", URLS_YAML)
        _url_whitelist = set()
        return _url_whitelist

    try:
        import yaml
    except ImportError:
        log.warning("pyyaml not installed — citation whitelist disabled. pip install pyyaml")
        _url_whitelist = set()
        return _url_whitelist

    with URLS_YAML.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    urls: set[str] = set()
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                url = entry.get("url", "")
                if url:
                    urls.add(url.rstrip("/"))
            elif isinstance(entry, str):
                urls.add(entry.rstrip("/"))

    _url_whitelist = urls
    log.info("URL whitelist loaded: %d entries from %s", len(urls), URLS_YAML)
    return _url_whitelist


# ---------------------------------------------------------------------------
# Step 1 — Sentence count validator
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentences using a regex boundary detector.

    Handles:
    - Standard sentence endings: '. ', '! ', '? '
    - End-of-string termination
    - Skips common abbreviations (Mr., Dr., Rs., etc.)
    - Treats the "Last updated from sources:" footer as a single sentence
    """
    # Remove the footer before splitting so it's never counted or truncated
    footer_match = LAST_UPDATED_RE.search(text)
    footer = footer_match.group(0) if footer_match else ""
    body   = text[:footer_match.start()].strip() if footer_match else text.strip()

    # Regex: split on sentence-ending punctuation followed by space+capital or end-of-string
    # Avoids splitting on "Rs.", "Mr.", "Dr.", "e.g.", "i.e.", "vs.", "etc."
    _ABBREV = re.compile(r"\b(?:Mr|Ms|Mrs|Dr|Rs|Prof|vs|etc|e\.g|i\.e|No|Jr|Sr)\.")
    _SENT_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

    # Temporarily mask common abbreviations
    masked = _ABBREV.sub(lambda m: m.group(0).replace(".", "\x00"), body)
    parts  = _SENT_END.split(masked)
    sentences = [p.replace("\x00", ".").strip() for p in parts if p.strip()]

    return sentences, footer


def step1_sentence_limit(
    text: str, max_sentences: int = MAX_SENTENCES
) -> tuple[str, bool]:
    """
    Return (truncated_text, was_truncated).

    If the response has > max_sentences sentences, keep only the first
    max_sentences and re-append the footer if present.
    """
    sentences, footer = _split_sentences(text)

    if len(sentences) <= max_sentences:
        return text, False

    kept   = sentences[:max_sentences]
    suffix = " " + footer if footer else ""
    result = " ".join(kept) + suffix

    log.info(
        "Step 1 TRUNCATE: %d sentences -> %d. Removed: %r",
        len(sentences), max_sentences,
        " ".join(sentences[max_sentences:])[:100],
    )
    return result, True


# ---------------------------------------------------------------------------
# Step 2 — Citation validator
# ---------------------------------------------------------------------------

def step2_citation(
    text: str,
    citation_url: str,
    top_chunk: dict | None,
) -> tuple[str, str, bool]:
    """
    Validate the citation URL in the response text against the whitelist.

    Returns (updated_text, validated_url, was_injected_or_replaced).

    Logic:
      1. Find first Groww URL in LLM response text.
      2a. If found AND in whitelist → keep.
      2b. If found BUT not in whitelist → log warning, replace URL in text
          with top-chunk URL.
      3.  If not found at all → inject top-chunk URL as a new sentence.
    """
    whitelist = _load_url_whitelist()

    # Determine the authoritative chunk URL (fallback chain)
    chunk_url = ""
    if top_chunk:
        if hasattr(top_chunk, "source_url"):
            chunk_url = top_chunk.source_url
        elif isinstance(top_chunk, dict):
            chunk_url = top_chunk.get("source_url", "")
    if not chunk_url:
        chunk_url = citation_url or FALLBACK_URL

    chunk_url = chunk_url.rstrip("/")

    # Search for Groww URL in text
    m = GROWW_URL_RE.search(text)

    if m:
        found_url = m.group(0).rstrip("/")

        # URL found and whitelisted — perfect
        if not whitelist or found_url in whitelist:
            log.info("Step 2 CITATION: valid URL in response: %s", found_url)
            return text, found_url, False

        # URL found but not whitelisted — replace
        log.warning(
            "Step 2 CITATION: URL not in whitelist: %s → replacing with %s",
            found_url, chunk_url,
        )
        updated_text = text.replace(found_url, chunk_url)
        return updated_text, chunk_url, True

    # No URL in response — inject the chunk URL
    log.info("Step 2 CITATION: no URL found in response → injecting %s", chunk_url)

    # Find a natural injection point: just before the footer, or at end
    footer_match = LAST_UPDATED_RE.search(text)
    if footer_match:
        injection = f" Source: {chunk_url}."
        insert_pos = footer_match.start()
        updated_text = text[:insert_pos].rstrip() + injection + " " + text[insert_pos:]
    else:
        updated_text = text.rstrip() + f" Source: {chunk_url}."

    return updated_text, chunk_url, True


# ---------------------------------------------------------------------------
# Step 3 — Footer injector
# ---------------------------------------------------------------------------

def step3_footer(
    text: str,
    last_updated_date: str,
    top_chunk: dict | None,
) -> tuple[str, str, bool]:
    """
    Ensure the response ends with "Last updated from sources: YYYY-MM-DD".

    Returns (updated_text, date_used, was_appended).
    """
    # Already has footer → nothing to do
    if LAST_UPDATED_RE.search(text):
        # Extract the existing date for consistency
        m = re.search(r"\d{4}-\d{2}-\d{2}", text[text.lower().rfind("last updated"):])
        date = m.group(0) if m else last_updated_date
        log.info("Step 3 FOOTER: already present (date=%s)", date)
        return text, date, False

    # Determine date (priority: caller-supplied → top chunk → today)
    date = last_updated_date
    if not date and top_chunk:
        if hasattr(top_chunk, "last_crawled_date"):
            date = top_chunk.last_crawled_date
        elif isinstance(top_chunk, dict):
            date = top_chunk.get("last_crawled_date", "")
    if not date:
        from datetime import date as _date
        date = _date.today().isoformat()

    footer = f"\n\n{FOOTER_PREFIX} {date}"
    log.info("Step 3 FOOTER: appending (date=%s)", date)
    return text.rstrip() + footer, date, True


# ---------------------------------------------------------------------------
# Step 4 — PII scanner
# ---------------------------------------------------------------------------

def step4_pii_scan(text: str) -> tuple[bool, list[str]]:
    """
    Scan text for PII patterns.

    Returns (pii_detected: bool, pii_types: list[str]).
    A non-empty pii_types list means the response must be blocked.

    Special case: URLs like https://...12345... or "Last updated: 2026-04-17"
    contain digit sequences. We exclude date strings and URLs before
    applying the bank account regex to reduce false positives.
    """
    # Sanitise: remove URLs and date strings before scanning for bank accounts
    _cleaned = re.sub(r"https?://\S+", "", text)
    _cleaned = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", _cleaned)

    found_types: list[str] = []

    for pii_type, pattern in _PII_PATTERNS:
        # Bank account scan uses cleaned text; others use raw text
        scan_target = _cleaned if pii_type == "bank_account" else text
        matches = pattern.findall(scan_target)

        if matches:
            # PAN guard: the regex [A-Z]{5}[0-9]{4}[A-Z] is already precise.
            # Just ensure it's a string of exactly 10 chars to avoid tuple matches
            # from groups in other patterns.
            if pii_type == "PAN":
                real_pans = [
                    m for m in matches
                    if isinstance(m, str) and len(m) == 10
                ]
                if not real_pans:
                    continue
                found_types.append(pii_type)
                log.warning("Step 4 PII: %s detected: %s", pii_type, real_pans)
            else:
                found_types.append(pii_type)
                log.warning("Step 4 PII: %s detected in response", pii_type)

    return bool(found_types), found_types


# ---------------------------------------------------------------------------
# Step 5 — Advisory content filter
# ---------------------------------------------------------------------------

def step5_advisory_filter(text: str) -> tuple[bool, list[str]]:
    """
    Scan output text for advisory language that bypassed the query guard.

    Returns (advisory_found: bool, trigger_phrases: list[str]).
    If advisory_found is True, the caller must replace the answer with
    the standard refusal.
    """
    lower = text.lower()
    triggers: list[str] = [
        phrase for phrase in _ADVISORY_OUTPUT_PHRASES
        if phrase in lower
    ]
    if triggers:
        log.warning("Step 5 ADVISORY: found phrases in output: %s", triggers)
    return bool(triggers), triggers


# ---------------------------------------------------------------------------
# Main process() entry point
# ---------------------------------------------------------------------------

def process(
    answer: str,
    citation_url: str = "",
    last_updated_date: str = "",
    *,
    is_refusal: bool = False,
    top_chunk: dict | None = None,
) -> PostProcessorResult:
    """
    Run all 5 post-processing steps on a single LLM response.

    Parameters
    ----------
    answer : str
        Raw LLM response text.
    citation_url : str
        Citation URL extracted by the generator (may be empty or unvalidated).
    last_updated_date : str
        Date string from the generator (may be empty).
    is_refusal : bool
        If True, skip steps 1–3 (no truncation, citation, or footer for
        pre-canned refusal messages). Steps 4–5 still run.
    top_chunk : dict | None
        The top retrieved chunk (RetrievedChunk or plain dict). Used for
        citation injection and date fallback.

    Returns
    -------
    PostProcessorResult
    """
    vlog: list[str] = []
    was_truncated     = False
    citation_injected = False
    footer_appended   = False
    validated_url     = citation_url
    validated_date    = last_updated_date
    current_text      = answer

    if is_refusal:
        vlog.append("Refusal response — skipping steps 1, 2, 3")
        log.info("Post-processor: refusal mode — skipping steps 1–3")
    else:
        # ── Step 1: Sentence limit ────────────────────────────────────────────
        current_text, was_truncated = step1_sentence_limit(current_text)
        vlog.append(
            f"Step 1: {'TRUNCATED to 3 sentences' if was_truncated else 'OK (≤3 sentences)'}"
        )

        # ── Step 2: Citation validator ────────────────────────────────────────
        current_text, validated_url, citation_injected = step2_citation(
            current_text, citation_url, top_chunk
        )
        vlog.append(
            f"Step 2: citation={'INJECTED/REPLACED' if citation_injected else 'OK'} url={validated_url}"
        )

        # ── Step 3: Footer injector ───────────────────────────────────────────
        current_text, validated_date, footer_appended = step3_footer(
            current_text, last_updated_date, top_chunk
        )
        vlog.append(
            f"Step 3: footer={'APPENDED' if footer_appended else 'ALREADY PRESENT'} date={validated_date}"
        )

    # ── Step 4: PII scanner ───────────────────────────────────────────────────
    pii_detected, pii_types = step4_pii_scan(current_text)
    vlog.append(
        f"Step 4: PII={'BLOCKED (' + ','.join(pii_types) + ')' if pii_detected else 'OK'}"
    )

    if pii_detected:
        log.warning("Post-processor: BLOCKING response due to PII: %s", pii_types)
        return PostProcessorResult(
            answer            = _BLOCKED_RESPONSE,
            citation_url      = FALLBACK_URL,
            last_updated_date = validated_date,
            is_blocked        = True,
            is_replaced       = False,
            was_truncated     = was_truncated,
            citation_injected = citation_injected,
            footer_appended   = footer_appended,
            pii_types_found   = pii_types,
            advisory_triggers = [],
            validation_log    = vlog,
        )

    # ── Step 5: Advisory content filter ──────────────────────────────────────
    advisory_found, triggers = step5_advisory_filter(current_text)
    vlog.append(
        f"Step 5: advisory={'REPLACED (' + ','.join(triggers) + ')' if advisory_found else 'OK'}"
    )

    if advisory_found:
        log.warning(
            "Post-processor: REPLACING response — advisory content found: %s", triggers
        )
        return PostProcessorResult(
            answer            = _ADVISORY_REFUSAL,
            citation_url      = AMFI_LINK,
            last_updated_date = "",
            is_blocked        = False,
            is_replaced       = True,
            was_truncated     = was_truncated,
            citation_injected = citation_injected,
            footer_appended   = False,
            pii_types_found   = [],
            advisory_triggers = triggers,
            validation_log    = vlog,
        )

    log.info("Post-processor: all 5 steps passed")
    return PostProcessorResult(
        answer            = current_text,
        citation_url      = validated_url,
        last_updated_date = validated_date,
        is_blocked        = False,
        is_replaced       = False,
        was_truncated     = was_truncated,
        citation_injected = citation_injected,
        footer_appended   = footer_appended,
        pii_types_found   = [],
        advisory_triggers = [],
        validation_log    = vlog,
    )


# ---------------------------------------------------------------------------
# Self-test (exit criteria)
# ---------------------------------------------------------------------------

def run_self_test() -> None:
    """
    Exit criteria test — runs all 4 required checks:
      1. >3 sentences → truncated to ≤3
      2. Missing citation → URL injected from metadata
      3. Response with "ABCDE1234F" (test PAN) → blocked
      4. "I recommend this fund" → replaced with refusal
    """
    log.info("=" * 72)
    log.info("SELF-TEST: Post-Processor (all 5 steps)")
    log.info("=" * 72)

    DUMMY_CHUNK = {
        "source_url":        "https://groww.in/mutual-funds/mirae-asset-large-cap-fund-direct-growth",
        "scheme_name":       "Mirae Asset Large Cap Fund",
        "last_crawled_date": "2026-04-17",
    }

    failures: list[str] = []

    # ── Test 1: Sentence count truncation ─────────────────────────────────────
    log.info("\n[TEST 1] Sentence truncation (5 sentences → ≤3)")
    long_answer = (
        "The expense ratio of Mirae Asset Large Cap Fund is 0.58%. "
        "The fund was launched in 2007. "
        "The fund manager is Gaurav Misra. "
        "The AUM is approximately Rs. 35,342 crore. "
        "The benchmark is Nifty 100 TRI. "
        "Last updated from sources: 2026-04-17"
    )
    result = process(
        long_answer,
        citation_url      = "https://groww.in/mutual-funds/mirae-asset-large-cap-fund-direct-growth",
        last_updated_date = "2026-04-17",
        top_chunk         = DUMMY_CHUNK,
    )
    # Count sentences in the body BEFORE citation injection added an extra sentence.
    # The reliable signal is was_truncated=True and the original input had 5 sentences.
    # We check that the truncated body (everything before 'Last updated' and before
    # any injected 'Source:' line) has ≤ MAX_SENTENCES.
    body = result.answer.split("Last updated")[0]
    body = re.sub(r"\s*Source:.*$", "", body, flags=re.DOTALL).strip()
    body_sentences, _ = _split_sentences(body)
    sentence_count = len(body_sentences)
    ok = result.was_truncated and sentence_count <= MAX_SENTENCES
    log.info("  was_truncated=%s  body_sentences=%d  PASS=%s", result.was_truncated, sentence_count, ok)
    for line in result.validation_log:
        log.info("    %s", line)
    if not ok:
        failures.append(f"Test 1 FAIL: was_truncated={result.was_truncated}, body_sentences={sentence_count}")

    # ── Test 2: Citation injection ─────────────────────────────────────────────
    log.info("\n[TEST 2] Citation injection (no URL in response)")
    no_cite_answer = (
        "The expense ratio of Mirae Asset Large Cap Fund Direct Plan is 0.58%. "
        "The minimum SIP amount is Rs. 99 per month."
    )
    result2 = process(
        no_cite_answer,
        citation_url      = "",
        last_updated_date = "2026-04-17",
        top_chunk         = DUMMY_CHUNK,
    )
    ok2 = (
        result2.citation_injected
        and "groww.in" in result2.citation_url
        and "groww.in" in result2.answer
    )
    log.info(
        "  citation_injected=%s  url=%s  url_in_text=%s  PASS=%s",
        result2.citation_injected, result2.citation_url,
        "groww.in" in result2.answer, ok2,
    )
    for line in result2.validation_log:
        log.info("    %s", line)
    if not ok2:
        failures.append(
            f"Test 2 FAIL: citation_injected={result2.citation_injected} "
            f"url={result2.citation_url!r}"
        )

    # ── Test 3: PII blocking — PAN number ─────────────────────────────────────
    log.info("\n[TEST 3] PII blocking — PAN ABCDE1234F")
    pii_answer = (
        "The investment has been registered under PAN ABCDE1234F. "
        "Source: https://groww.in/mutual-funds/mirae-asset-large-cap-fund-direct-growth."
    )
    result3 = process(
        pii_answer,
        citation_url      = "https://groww.in/mutual-funds/mirae-asset-large-cap-fund-direct-growth",
        last_updated_date = "2026-04-17",
        top_chunk         = DUMMY_CHUNK,
    )
    ok3 = result3.is_blocked and "PAN" in result3.pii_types_found
    log.info(
        "  is_blocked=%s  pii_types=%s  PASS=%s",
        result3.is_blocked, result3.pii_types_found, ok3,
    )
    for line in result3.validation_log:
        log.info("    %s", line)
    if not ok3:
        failures.append(
            f"Test 3 FAIL: is_blocked={result3.is_blocked} pii={result3.pii_types_found}"
        )

    # ── Test 4: Advisory content filter ───────────────────────────────────────
    log.info("\n[TEST 4] Advisory content filter — 'I recommend this fund'")
    advisory_answer = (
        "The Mirae Asset Large Cap Fund is excellent. "
        "I recommend this fund for long-term wealth creation. "
        "Source: https://groww.in/mutual-funds/mirae-asset-large-cap-fund-direct-growth."
    )
    result4 = process(
        advisory_answer,
        citation_url      = "https://groww.in/mutual-funds/mirae-asset-large-cap-fund-direct-growth",
        last_updated_date = "2026-04-17",
        top_chunk         = DUMMY_CHUNK,
    )
    ok4 = result4.is_replaced and AMFI_LINK in result4.answer
    log.info(
        "  is_replaced=%s  amfi_link_in_answer=%s  PASS=%s",
        result4.is_replaced, AMFI_LINK in result4.answer, ok4,
    )
    for line in result4.validation_log:
        log.info("    %s", line)
    if not ok4:
        failures.append(
            f"Test 4 FAIL: is_replaced={result4.is_replaced} triggers={result4.advisory_triggers}"
        )

    # ── Summary ────────────────────────────────────────────────────────────────
    log.info("\n" + "=" * 72)
    if failures:
        log.error("SELF-TEST FAILED (%d errors):", len(failures))
        for f in failures:
            log.error("  %s", f)
        sys.exit(1)
    else:
        log.info(
            "SELF-TEST PASSED: sentence truncation ✓  citation injection ✓  "
            "PII blocking ✓  advisory filter ✓"
        )
    log.info("=" * 72)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Phase 7 — Post-Processor CLI"
    )
    parser.add_argument(
        "--self-test", action="store_true",
        help="Run all 4 exit-criteria tests",
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Run a demo of all 5 steps on a sample response",
    )
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return

    if args.demo:
        demo_answer = (
            "The expense ratio of Mirae Asset Large Cap Fund Direct Plan is 0.58%. "
            "The fund was launched in November 2007. "
            "The benchmark is Nifty 100 TRI. "
            "The AUM is Rs. 35,342 crore as of April 2026. "
        )
        demo_chunk = {
            "source_url":        "https://groww.in/mutual-funds/mirae-asset-large-cap-fund-direct-growth",
            "scheme_name":       "Mirae Asset Large Cap Fund",
            "last_crawled_date": "2026-04-17",
        }
        result = process(
            demo_answer,
            citation_url      = "",
            last_updated_date = "",
            top_chunk         = demo_chunk,
        )
        print(f"\n{'='*72}")
        print(f"FINAL ANSWER:\n{result.answer}")
        print(f"\ncitation_url      : {result.citation_url}")
        print(f"last_updated_date : {result.last_updated_date}")
        print(f"was_truncated     : {result.was_truncated}")
        print(f"citation_injected : {result.citation_injected}")
        print(f"footer_appended   : {result.footer_appended}")
        print(f"\nValidation log:")
        for line in result.validation_log:
            print(f"  {line}")
        print(f"{'='*72}\n")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
