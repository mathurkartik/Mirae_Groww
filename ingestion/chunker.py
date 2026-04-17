#!/usr/bin/env python3
"""
Phase 4.1 -- Chunking Service
==============================
Reads data/cleaned_docs.jsonl (produced by scraper.py) and outputs
data/chunks.jsonl -- one JSON record per chunk.

Chunking strategy (priority order):
  1. Section-aware split on H1/H2/H3/H4 heading boundaries.
  2. Table atomicity: pipe-delimited blocks kept as a single chunk if
     <= table_max_tokens (500). If larger, split on row boundaries with
     the header row duplicated into every sub-chunk.
  3. Recursive character splitter fallback for any text block still
     exceeding chunk_size (500 tokens).

Separator hierarchy for recursive fallback:
  ["\\n## ", "\\n### ", "\\n\\n", "\\n", ". ", " "]

Parameters:
  chunk_size      = 500 tokens
  chunk_overlap   = 50  tokens
  min_chunk_size  = 50  tokens  (chunks below this are discarded)
  table_max_tokens= 500 tokens

Financial domain special handling (section 3.4 of architecture):
  - NAV / expense ratio / exit load tables  -> table atomicity rule
  - ELSS lock-in, riskometer, benchmark     -> kept within their section chunk
  - SIP/lump-sum minimums                   -> kept with surrounding paragraph

Chunk ID:
  SHA-256(doc_hash + ':' + section_heading + ':' + str(chunk_index))
  chunk_index is a global counter per source_url (0-based), not per section.

Output schema (chunks.jsonl):
  chunk_id, doc_hash, source_url, scheme_name, category,
  section_heading, chunk_index, content, token_count,
  last_crawled_date, doc_type, embedding_model, embedding_version,
  pipeline_run_id

Usage:
  python ingestion/chunker.py

Environment variables (optional overrides):
  INPUT_JSONL     path to cleaned_docs.jsonl   (default: data/cleaned_docs.jsonl)
  OUTPUT_JSONL    path to chunks.jsonl          (default: data/chunks.jsonl)
  CHUNK_SIZE      max tokens per chunk          (default: 500)
  CHUNK_OVERLAP   overlap tokens                (default: 50)
  MIN_CHUNK       min tokens before discard     (default: 50)
  TABLE_MAX_TOKENS max tokens to keep table atomic (default: 500)
  EMBEDDING_MODEL embedding model name          (default: BAAI/bge-small-en-v1.5)
  EMBEDDING_VER   embedding version tag         (default: 2026-04)
  PIPELINE_RUN_ID pipeline run identifier       (default: local)
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Generator

import tiktoken

# ---------------------------------------------------------------------------
# Logging -- UTF-8 safe on all platforms
# ---------------------------------------------------------------------------
_utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    handlers=[logging.StreamHandler(_utf8_stdout)],
)
log = logging.getLogger("chunker")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
_ROOT = _HERE.parent

INPUT_JSONL      = Path(os.environ.get("INPUT_JSONL",    _ROOT / "data" / "cleaned_docs.jsonl"))
OUTPUT_JSONL     = Path(os.environ.get("OUTPUT_JSONL",   _ROOT / "data" / "chunks.jsonl"))
CHUNK_SIZE       = int(os.environ.get("CHUNK_SIZE",      "500"))
CHUNK_OVERLAP    = int(os.environ.get("CHUNK_OVERLAP",   "50"))
MIN_CHUNK        = int(os.environ.get("MIN_CHUNK",       "50"))
TABLE_MAX_TOKENS = int(os.environ.get("TABLE_MAX_TOKENS","500"))
EMBEDDING_MODEL  = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_VER    = os.environ.get("EMBEDDING_VER",   "2026-04")
PIPELINE_RUN_ID  = os.environ.get("PIPELINE_RUN_ID", "local")

# Separator hierarchy for recursive fallback (architecture spec section 3.1)
RECURSIVE_SEPARATORS = ["\n## ", "\n### ", "\n\n", "\n", ". ", " "]

# Heading regex: matches markdown headings produced by the scraper
# Captures (hashes, heading_text), anchored to start of line
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)

# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------
# cl100k_base is the encoding used by text-embedding-3 and gpt-4 family;
# it's a good proxy for token counting with bge-small-en-v1.5.
try:
    _TOKENIZER = tiktoken.get_encoding("cl100k_base")
except Exception:
    _TOKENIZER = None
    log.warning("tiktoken unavailable -- using whitespace split as token proxy")


def count_tokens(text: str) -> int:
    """Return approximate token count for text."""
    if _TOKENIZER is not None:
        return len(_TOKENIZER.encode(text, disallowed_special=()))
    # Fallback: whitespace split (rough approximation)
    return len(text.split())


# ---------------------------------------------------------------------------
# SHA-256 helpers
# ---------------------------------------------------------------------------

def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_chunk_id(doc_hash: str, source_url: str, section_heading: str, chunk_index: int) -> str:
    """Deterministic chunk ID — unique per (url, heading, index) triple.

    We include source_url in the hash so that two documents with identical
    content (e.g. a 404 error page returned for multiple URLs) still produce
    distinct chunk IDs.
    """
    raw = f"{doc_hash}:{source_url}:{section_heading}:{chunk_index}"
    return sha256(raw)


# ---------------------------------------------------------------------------
# Table detection helpers
# ---------------------------------------------------------------------------

def _is_table_line(line: str) -> bool:
    """True if the line looks like a pipe-delimited table row from the scraper."""
    stripped = line.strip()
    # Must contain at least one pipe and have non-trivial content
    return "|" in stripped and len(stripped) > 3


def _split_into_blocks(text: str) -> list[tuple[str, str]]:
    """
    Split text into alternating 'text' and 'table' blocks.

    Returns a list of (block_type, block_content) tuples where
    block_type is 'text' or 'table'.
    """
    lines = text.split("\n")
    blocks: list[tuple[str, str]] = []
    current_type: str = "text"
    current_lines: list[str] = []

    for line in lines:
        line_type = "table" if _is_table_line(line) else "text"

        if line_type == current_type:
            current_lines.append(line)
        else:
            # Save current block (strip trailing blank lines from text blocks)
            content = "\n".join(current_lines)
            if current_type == "text":
                content = content.rstrip()
            if content:
                blocks.append((current_type, content))
            # Start new block
            current_type = line_type
            current_lines = [line]

    # Flush final block
    if current_lines:
        content = "\n".join(current_lines)
        if current_type == "text":
            content = content.rstrip()
        if content:
            blocks.append((current_type, content))

    return blocks


# ---------------------------------------------------------------------------
# Table chunking
# ---------------------------------------------------------------------------

def _chunk_table(
    table_text: str,
    heading: str,
) -> list[str]:
    """
    Chunk a pipe-delimited table block.

    Rule (architecture spec 3.1 / 3.4):
      - If token_count <= TABLE_MAX_TOKENS: return as a single atomic chunk.
      - If token_count > TABLE_MAX_TOKENS: split on rows. The first row is the
        header; duplicate it into every sub-chunk so each chunk is self-contained.

    Returns a list of chunk content strings.
    """
    tokens = count_tokens(table_text)
    if tokens <= TABLE_MAX_TOKENS:
        return [table_text.strip()]

    # Split oversized table on rows, duplicating header
    rows = [r for r in table_text.strip().split("\n") if r.strip()]
    if len(rows) <= 1:
        # Single row -- can't split further; return as-is
        return [table_text.strip()]

    header = rows[0]
    data_rows = rows[1:]

    sub_chunks: list[str] = []
    current_rows = [header]
    current_tokens = count_tokens(header)

    for row in data_rows:
        row_tokens = count_tokens(row)
        # +1 for the newline separator
        if current_tokens + row_tokens + 1 > TABLE_MAX_TOKENS and len(current_rows) > 1:
            sub_chunks.append("\n".join(current_rows))
            # Start new sub-chunk with duplicated header
            current_rows = [header, row]
            current_tokens = count_tokens(header) + row_tokens + 1
        else:
            current_rows.append(row)
            current_tokens += row_tokens + 1

    if current_rows:
        sub_chunks.append("\n".join(current_rows))

    return sub_chunks


# ---------------------------------------------------------------------------
# Recursive text splitter
# ---------------------------------------------------------------------------

def _merge_splits(
    splits: list[str],
    separator: str,
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """
    Merge a list of string splits back into chunks respecting chunk_size and overlap.
    This is the standard LangChain-style merge step.
    """
    chunks: list[str] = []
    current_parts: list[str] = []
    current_tokens = 0

    for part in splits:
        part_tokens = count_tokens(part)

        if current_tokens + part_tokens + (count_tokens(separator) if current_parts else 0) > chunk_size:
            if current_parts:
                # Emit current chunk
                chunks.append(separator.join(current_parts).strip())

                # Build overlap: keep tail of current_parts that fits in overlap budget
                overlap_parts: list[str] = []
                overlap_tokens = 0
                for p in reversed(current_parts):
                    p_tok = count_tokens(p)
                    if overlap_tokens + p_tok <= overlap:
                        overlap_parts.insert(0, p)
                        overlap_tokens += p_tok
                    else:
                        break
                current_parts = overlap_parts
                current_tokens = overlap_tokens

        current_parts.append(part)
        current_tokens += part_tokens + (count_tokens(separator) if len(current_parts) > 1 else 0)

    if current_parts:
        chunks.append(separator.join(current_parts).strip())

    return [c for c in chunks if c]


def _recursive_split(
    text: str,
    separators: list[str],
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """
    Recursively split text using the separator hierarchy until all splits
    are <= chunk_size tokens.

    Implements the separator hierarchy from architecture spec section 3.1:
      ["\\n## ", "\\n### ", "\\n\\n", "\\n", ". ", " "]
    """
    if count_tokens(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    if not separators:
        # Hard character fallback -- last resort
        # Estimate chars per token (~4 chars) for the boundary
        char_limit = chunk_size * 4
        overlap_chars = overlap * 4
        result = []
        start = 0
        while start < len(text):
            end = start + char_limit
            result.append(text[start:end].strip())
            start = end - overlap_chars
        return [c for c in result if c]

    sep = separators[0]
    rest = separators[1:]

    if sep not in text:
        return _recursive_split(text, rest, chunk_size, overlap)

    parts = text.split(sep)
    # Restore separator prefix (except on first part)
    restored: list[str] = []
    for i, part in enumerate(parts):
        if i == 0:
            restored.append(part)
        else:
            restored.append(sep.lstrip("\n") + part)

    # Merge parts into chunks, then recursively split any that are still too large
    merged = _merge_splits(restored, "\n", chunk_size, overlap)
    result: list[str] = []
    for chunk in merged:
        if count_tokens(chunk) > chunk_size:
            result.extend(_recursive_split(chunk, rest, chunk_size, overlap))
        else:
            if chunk.strip():
                result.append(chunk.strip())

    return result


# ---------------------------------------------------------------------------
# Per-section chunker
# ---------------------------------------------------------------------------

def _chunk_section(
    section_text: str,
    heading: str,
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """
    Chunk a single document section.

    Strategy:
      1. Split into table and text blocks.
      2. Table blocks: chunk_table() (atomic or row-split).
      3. Text blocks: recursive split if > chunk_size, else keep whole.
      4. Return all chunks in order.
    """
    if not section_text.strip():
        return []

    blocks = _split_into_blocks(section_text)
    chunks: list[str] = []

    for block_type, block_content in blocks:
        block_content = block_content.strip()
        if not block_content:
            continue

        if block_type == "table":
            chunks.extend(_chunk_table(block_content, heading))
        else:
            # Text block
            tokens = count_tokens(block_content)
            if tokens <= chunk_size:
                chunks.append(block_content)
            else:
                chunks.extend(
                    _recursive_split(block_content, RECURSIVE_SEPARATORS, chunk_size, overlap)
                )

    return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# Document-level heading splitter
# ---------------------------------------------------------------------------

def _split_on_headings(text: str) -> list[tuple[str, str]]:
    """
    Split document text on H1/H2/H3/H4 heading boundaries.

    Returns a list of (heading_text, section_body) tuples.
    The first element is always ("__preamble__", <text before first heading>)
    if there is text before the first heading.

    The heading_text for each section includes the heading line itself so that
    it stays part of the chunk content.
    """
    sections: list[tuple[str, str]] = []

    # Find all heading positions
    matches = list(_HEADING_RE.finditer(text))

    if not matches:
        # No headings -- treat entire text as one unnamed section
        return [("__preamble__", text)]

    # Preamble: everything before the first heading
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(("__preamble__", preamble))

    # Each heading to next heading (or end of text)
    for i, match in enumerate(matches):
        heading_text = match.group(2).strip()  # heading without the # marks
        section_start = match.end()
        section_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[section_start:section_end].strip()
        sections.append((heading_text, body))

    return sections


# ---------------------------------------------------------------------------
# Single document chunker
# ---------------------------------------------------------------------------

def chunk_document(doc: dict) -> list[dict]:
    """
    Chunk a single document record from cleaned_docs.jsonl.

    Returns a list of chunk dicts ready for chunks.jsonl.
    chunk_index is a global counter across all sections of the document.
    """
    source_url      = doc.get("source_url", "")
    scheme_name     = doc.get("scheme_name", "")
    category        = doc.get("category", "")
    scrape_date     = doc.get("scrape_date", "")
    doc_hash        = doc.get("content_hash", "")
    cleaned_text    = doc.get("cleaned_text") or ""

    if not cleaned_text.strip():
        log.warning("Empty cleaned_text for %s -- skipping", source_url)
        return []

    sections = _split_on_headings(cleaned_text)

    chunks: list[dict] = []
    chunk_index = 0  # global counter per document

    for heading, body in sections:
        section_chunks = _chunk_section(body, heading, CHUNK_SIZE, CHUNK_OVERLAP)

        for content in section_chunks:
            content = content.strip()
            tokens = count_tokens(content)

            # Discard below min threshold
            if tokens < MIN_CHUNK:
                log.debug("Discarding micro-chunk (%d tokens) under section '%s'", tokens, heading)
                continue

            chunk_id = make_chunk_id(doc_hash, source_url, heading, chunk_index)

            chunk = {
                "chunk_id":          chunk_id,
                "doc_hash":          doc_hash,
                "source_url":        source_url,
                "scheme_name":       scheme_name,
                "category":          category,
                "section_heading":   heading,
                "chunk_index":       chunk_index,
                "content":           content,
                "token_count":       tokens,
                "last_crawled_date": scrape_date,
                "doc_type":          "groww_page",
                "embedding_model":   EMBEDDING_MODEL,
                "embedding_version": EMBEDDING_VER,
                "pipeline_run_id":   PIPELINE_RUN_ID,
            }
            chunks.append(chunk)
            chunk_index += 1

    return chunks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=" * 72)
    log.info("Phase 4.1 - Chunking Service")
    log.info("Input   : %s", INPUT_JSONL)
    log.info("Output  : %s", OUTPUT_JSONL)
    log.info("Params  : chunk_size=%d  overlap=%d  min=%d  table_max=%d",
             CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK, TABLE_MAX_TOKENS)
    log.info("Model   : %s  ver=%s  run=%s", EMBEDDING_MODEL, EMBEDDING_VER, PIPELINE_RUN_ID)
    log.info("=" * 72)

    if not INPUT_JSONL.exists():
        log.critical("Input file not found: %s", INPUT_JSONL)
        sys.exit(1)

    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)

    # ---- Load documents -----------------------------------------------------
    docs: list[dict] = []
    with INPUT_JSONL.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                docs.append(json.loads(line))

    total_docs = len(docs)
    ok_docs = sum(1 for d in docs if d.get("status") == "ok")
    skip_docs = total_docs - ok_docs
    log.info("Loaded %d docs (%d OK, %d skipped with status != ok)", total_docs, ok_docs, skip_docs)

    # ---- Chunk each document ------------------------------------------------
    all_chunks: list[dict] = []
    total_over_limit = 0
    max_tokens_seen = 0

    for idx, doc in enumerate(docs, start=1):
        if doc.get("status") != "ok":
            log.info("[%2d/%d] SKIP (%s status) -- %s",
                     idx, total_docs, doc.get("status"), doc.get("scheme_name", "?"))
            continue

        scheme = doc.get("scheme_name", doc.get("source_url", "?"))
        chunks = chunk_document(doc)

        # Verify no chunk exceeds hard limit (600 tokens per exit criteria)
        for c in chunks:
            if c["token_count"] > max_tokens_seen:
                max_tokens_seen = c["token_count"]
            if c["token_count"] > 600:
                total_over_limit += 1
                log.warning(
                    "OVERSIZED chunk (%d tokens) in '%s' section='%s' idx=%d",
                    c["token_count"], scheme, c["section_heading"], c["chunk_index"],
                )

        all_chunks.extend(chunks)
        log.info("[%2d/%d] %-55s -> %d chunks", idx, total_docs, scheme, len(chunks))

    # ---- Write output -------------------------------------------------------
    with OUTPUT_JSONL.open("w", encoding="utf-8") as out:
        for chunk in all_chunks:
            out.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    # ---- Summary ------------------------------------------------------------
    log.info("=" * 72)
    log.info("Chunking complete")
    log.info("  Documents processed : %d / %d", ok_docs, total_docs)
    log.info("  Total chunks        : %d", len(all_chunks))
    log.info("  Max token count     : %d", max_tokens_seen)
    log.info("  Chunks > 600 tokens : %d", total_over_limit)
    log.info("  Output              : %s", OUTPUT_JSONL)
    log.info("=" * 72)

    if total_over_limit > 0:
        log.error("Exit criteria FAILED: %d chunk(s) exceed 600 tokens", total_over_limit)
        sys.exit(1)

    log.info("Exit criteria PASSED: no chunk exceeds 600 tokens")


if __name__ == "__main__":
    main()
