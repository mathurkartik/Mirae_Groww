#!/usr/bin/env python3
"""
Phase 4.0 — Scraping Service
==============================
Scrapes all 36 Mirae Asset Groww URLs defined in data/urls.yaml.

Strategy:
  1. Attempt requests + BeautifulSoup (fast, no browser overhead).
     Groww pages are React SPAs; the static response typically contains
     SEO-prerendered content inside <script id="__NEXT_DATA__"> or within
     the initial <body>. If the extracted text is too short (< MIN_CONTENT_CHARS),
     we fall back to Playwright.
  2. Playwright (headless Chromium) executes JavaScript, waits for the page to
     fully hydrate, then returns the live DOM.

Outputs:
  data/raw/<scheme_slug>_<YYYY-MM-DD>.html   — raw HTML per URL
  data/cleaned_docs.jsonl                    — one JSON record per URL

Record schema (cleaned_docs.jsonl):
  {
    "source_url":     str,
    "scheme_name":    str,
    "category":       str,
    "scrape_date":    str  (YYYY-MM-DD),
    "scrape_ts":      str  (ISO-8601 UTC),
    "content_hash":   str  (SHA-256 of cleaned_text),
    "cleaned_text":   str,
    "scrape_method":  str  ("requests" | "playwright"),
    "status":         str  ("ok" | "failed"),
    "error":          str | null
  }

Usage:
  python ingestion/scraper.py

Environment variables (optional overrides):
  URLS_YAML            path to urls.yaml   (default: data/urls.yaml)
  RAW_DIR              path to raw HTML dir (default: data/raw)
  OUTPUT_JSONL         path to output file  (default: data/cleaned_docs.jsonl)
  MIN_CONTENT_CHARS    minimum chars before Playwright fallback (default: 500)
  PLAYWRIGHT_TIMEOUT   page load timeout ms (default: 30000)
  REQUEST_TIMEOUT      requests timeout sec (default: 15)
  MAX_RETRIES          retries per URL      (default: 3)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml
from bs4 import BeautifulSoup, Comment

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("scraper")

# ── Configuration ─────────────────────────────────────────────────────────────

# Resolve paths relative to the project root (parent of ingestion/)
_HERE = Path(__file__).parent
_ROOT = _HERE.parent

URLS_YAML         = Path(os.environ.get("URLS_YAML",        _ROOT / "data" / "urls.yaml"))
RAW_DIR           = Path(os.environ.get("RAW_DIR",          _ROOT / "data" / "raw"))
OUTPUT_JSONL      = Path(os.environ.get("OUTPUT_JSONL",     _ROOT / "data" / "cleaned_docs.jsonl"))
MIN_CONTENT_CHARS = int(os.environ.get("MIN_CONTENT_CHARS", "500"))
PLAYWRIGHT_TIMEOUT= int(os.environ.get("PLAYWRIGHT_TIMEOUT","30000"))
REQUEST_TIMEOUT   = int(os.environ.get("REQUEST_TIMEOUT",   "15"))
MAX_RETRIES       = int(os.environ.get("MAX_RETRIES",       "3"))

# HTTP headers to mimic a real browser (reduces bot-detection blocks)
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Tags whose text content is always discarded during cleaning
_NOISE_TAGS = {
    "script", "style", "noscript", "header", "footer", "nav",
    "aside", "form", "button", "svg", "iframe", "meta", "link",
}

# CSS class fragments that indicate boilerplate / nav / cookie banners
_NOISE_CLASS_FRAGMENTS = [
    "navbar", "nav-", "footer", "cookie", "banner", "popup",
    "modal", "overlay", "toast", "breadcrumb", "sidebar",
    "advertisement", "ad-", "promo",
]


# ── Utility helpers ───────────────────────────────────────────────────────────

def slug_from_url(url: str) -> str:
    """Extract the last path segment of the URL and sanitize for filesystem safety.

    Example:
        https://groww.in/mutual-funds/mirae-asset-large-cap-fund-direct-growth
        → mirae-asset-large-cap-fund-direct-growth

    Sanitization replaces characters not allowed in GitHub Actions artifacts
    (", :, <, >, |, *, ?, \r, \n) with hyphens to ensure cross-platform compatibility.
    """
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    # Replace artifact-invalid characters with hyphens
    invalid_chars = ['"', ':', '<', '>', '|', '*', '?', '\r', '\n']
    for char in invalid_chars:
        slug = slug.replace(char, '-')
    return slug


def sha256(text: str) -> str:
    """Return the SHA-256 hex digest of a UTF-8 encoded string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    """Return today's date as YYYY-MM-DD (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def is_noise_element(tag) -> bool:
    """Return True if a BeautifulSoup tag should be discarded during cleaning.

    Guards against NavigableString nodes (which have no .name or .attrs).
    """
    if not hasattr(tag, "name") or tag.name is None:
        return False
    if tag.name in _NOISE_TAGS:
        return True
    attrs = getattr(tag, "attrs", None) or {}
    cls = " ".join(attrs.get("class", []))
    return any(frag in cls.lower() for frag in _NOISE_CLASS_FRAGMENTS)


# ── Text extraction / cleaning ────────────────────────────────────────────────

def clean_html(raw_html: str, source_url: str) -> str:
    """
    Parse raw HTML and return cleaned plain text suitable for chunking.

    Steps:
      1. Parse with html.parser (lxml optional).
      2. Remove HTML comments.
      3. Decompose noise tags (nav, footer, scripts, …).
      4. Convert tables to pipe-delimited markdown-style text.
      5. Convert headings to markdown (## / ### / ####).
      6. Extract remaining text, normalize whitespace.
    """
    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove HTML comments
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Remove noise elements
    for tag in soup.find_all(True):
        if is_noise_element(tag):
            tag.decompose()

    # Convert <table> elements to markdown-style text before extracting
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(" | ".join(cells))
        table.replace_with("\n" + "\n".join(rows) + "\n")

    # Convert headings to markdown
    for lvl, md in [("h1", "# "), ("h2", "## "), ("h3", "### "), ("h4", "#### ")]:
        for h in soup.find_all(lvl):
            text = h.get_text(strip=True)
            if text:
                h.replace_with(f"\n{md}{text}\n")

    # Extract text
    raw_text = soup.get_text(separator="\n")

    # Normalize whitespace — collapse multiple blank lines, strip trailing spaces
    lines = [line.rstrip() for line in raw_text.splitlines()]
    cleaned_lines: list[str] = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            if blank_run <= 1:
                cleaned_lines.append("")
        else:
            blank_run = 0
            cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines).strip()
    return cleaned


# ── requests + BeautifulSoup scrape ──────────────────────────────────────────

def scrape_with_requests(url: str) -> tuple[str | None, str | None]:
    """
    Fetch URL with requests.
    Returns (raw_html, error_message). error_message is None on success.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                headers=REQUEST_HEADERS,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            response.raise_for_status()
            return response.text, None
        except requests.exceptions.RequestException as exc:
            log.warning("requests attempt %d/%d failed for %s: %s", attempt, MAX_RETRIES, url, exc)
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)  # exponential back-off

    return None, f"requests failed after {MAX_RETRIES} attempts"


# ── Playwright scrape ─────────────────────────────────────────────────────────

def scrape_with_playwright(url: str) -> tuple[str | None, str | None]:
    """
    Fetch URL using Playwright (headless Chromium).
    Waits for networkidle so that React/Next.js components finish rendering.
    Returns (raw_html, error_message). error_message is None on success.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        return None, "playwright not installed — run: pip install playwright && playwright install chromium"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=REQUEST_HEADERS["User-Agent"],
                    locale="en-IN",
                    extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"},
                )
                page = context.new_page()
                page.goto(url, wait_until="networkidle", timeout=PLAYWRIGHT_TIMEOUT)
                # Extra wait for dynamic content panels (NAV table, etc.)
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()
            return html, None
        except PWTimeout:
            log.warning("Playwright timeout attempt %d/%d for %s", attempt, MAX_RETRIES, url)
            if attempt < MAX_RETRIES:
                time.sleep(3)
        except Exception as exc:  # noqa: BLE001
            return None, f"Playwright error: {exc}"

    return None, f"Playwright timed out after {MAX_RETRIES} attempts"


# ── Per-URL orchestrator ──────────────────────────────────────────────────────

def scrape_url(entry: dict[str, str], scrape_date: str) -> dict[str, Any]:
    """
    Scrape a single URL entry from urls.yaml.
    Returns a cleaned_docs.jsonl record dict.
    """
    url         = entry["url"]
    scheme_name = entry["scheme_name"]
    category    = entry["category"]
    slug        = slug_from_url(url)
    raw_path    = RAW_DIR / f"{slug}_{scrape_date}.html"

    record: dict[str, Any] = {
        "source_url":   url,
        "scheme_name":  scheme_name,
        "category":     category,
        "scrape_date":  scrape_date,
        "scrape_ts":    utc_now(),
        "content_hash": None,
        "cleaned_text": None,
        "scrape_method": None,
        "status":       "failed",
        "error":        None,
    }

    # -- Step 1: Try requests -------------------------------------------------
    log.info("[%-6s] Trying requests -> %s", "REQ", url)
    raw_html, err = scrape_with_requests(url)

    if raw_html:
        cleaned = clean_html(raw_html, url)
        if len(cleaned) >= MIN_CONTENT_CHARS:
            record["scrape_method"] = "requests"
            log.info("[%-6s] requests OK, %d chars extracted", "REQ", len(cleaned))
        else:
            log.info(
                "[%-6s] Content too short (%d < %d chars), escalating to Playwright",
                "REQ", len(cleaned), MIN_CONTENT_CHARS,
            )
            raw_html = None  # trigger Playwright below

    # -- Step 2: Playwright fallback (or if requests returned nothing) --------
    if raw_html is None:
        log.info("[%-6s] Using Playwright -> %s", "PW", url)
        raw_html, err = scrape_with_playwright(url)
        if raw_html:
            record["scrape_method"] = "playwright"
            log.info("[%-6s] Playwright OK", "PW")

    # ── Step 3: Process results ───────────────────────────────────────────────
    if raw_html is None:
        record["error"] = err or "all scrape methods failed"
        log.error("[FAIL] %s — %s", url, record["error"])
        return record

    # Save raw HTML to disk
    try:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw_html, encoding="utf-8")
        log.info("[RAW ] Saved -> %s", raw_path.name)
    except OSError as exc:
        log.warning("[RAW ] Could not save raw HTML: %s", exc)

    # Clean and hash
    cleaned = clean_html(raw_html, url)
    record["cleaned_text"] = cleaned
    record["content_hash"] = sha256(cleaned)
    record["status"]       = "ok"
    record["error"]        = None

    log.info(
        "[ OK ] %s | method=%-10s | chars=%-6d | hash=%s...",
        scheme_name,
        record["scrape_method"],
        len(cleaned),
        record["content_hash"][:12],
    )
    return record


# -- Main ---------------------------------------------------------------------

def main() -> None:
    run_start = time.time()
    scrape_date = today()

    log.info("=" * 72)
    log.info("Phase 4.0 - Scraping Service")
    log.info("Date        : %s", scrape_date)
    log.info("URLs file   : %s", URLS_YAML)
    log.info("Output      : %s", OUTPUT_JSONL)
    log.info("Raw HTML dir: %s", RAW_DIR)
    log.info("=" * 72)

    # ── Load URL list ─────────────────────────────────────────────────────────
    if not URLS_YAML.exists():
        log.critical("urls.yaml not found at %s — aborting", URLS_YAML)
        sys.exit(1)

    with URLS_YAML.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    entries: list[dict] = config.get("urls", [])
    total = len(entries)
    log.info("Loaded %d URL entries from %s", total, URLS_YAML.name)

    if total != 36:
        log.warning("Expected 36 URLs, found %d — check urls.yaml", total)

    # ── Ensure output directories exist ──────────────────────────────────────
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)

    # ── Scrape loop ───────────────────────────────────────────────────────────
    records: list[dict] = []
    ok_count   = 0
    fail_count = 0

    for idx, entry in enumerate(entries, start=1):
        log.info("-" * 60)
        log.info("[%2d/%d] %s", idx, total, entry.get("scheme_name", entry["url"]))
        record = scrape_url(entry, scrape_date)
        records.append(record)

        if record["status"] == "ok":
            ok_count += 1
        else:
            fail_count += 1

        # Polite delay between requests to avoid rate-limiting
        if idx < total:
            time.sleep(1.5)

    # ── Write cleaned_docs.jsonl ──────────────────────────────────────────────
    with OUTPUT_JSONL.open("w", encoding="utf-8") as out:
        for rec in records:
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    elapsed = time.time() - run_start

    log.info("=" * 72)
    log.info("Scrape complete in %.1fs", elapsed)
    log.info("  Total   : %d", total)
    log.info("  OK      : %d", ok_count)
    log.info("  Failed  : %d", fail_count)
    log.info("  Output  : %s", OUTPUT_JSONL)
    log.info("=" * 72)

    if fail_count > 0:
        log.warning("%d URL(s) failed — check logs above for details", fail_count)
        # Non-zero exit so GitHub Actions marks the job as failed when any URL is broken
        sys.exit(1)


if __name__ == "__main__":
    main()
