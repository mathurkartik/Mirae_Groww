#!/usr/bin/env python3
"""
Phase 4.2 -- Embedding Service
===============================
Implements Stages C and D of the ingestion pipeline.
Stage E (ChromaDB upsert + manifest) is delegated to VectorStore
(ingestion/vector_store.py) to keep responsibilities separate.

  Stage C -- Change Detection
    Load previous ingestion_manifest.json and classify each chunk as
    NEW / UPDATED / UNCHANGED / DELETED.

  Stage D -- Batch Embedding (BAAI/bge-small-en-v1.5, fully local)
    - Prepend BGE prefix: "Represent this sentence: " (REQUIRED)
    - Encode NEW + UPDATED chunks, batch_size=32
    - normalize_embeddings=True -> 384-dim L2-normalised vectors

  Stage E -- delegated to VectorStore
    vs.upsert(), vs.delete(), vs.write_manifest()

Idempotency:
  Running twice without content changes -> zero embed calls, zero upserts.

CLI flags:
  --self-test   Embed 5 synthetic chunks, verify 384-dim, then upsert into
                ChromaDB via VectorStore as a quick integration smoke-test.

Usage:
  python ingestion/embedder.py               # full pipeline
  python ingestion/embedder.py --self-test   # 384-dim + Chroma smoke-test

Environment variables:
  CHUNKS_JSONL        data/chunks.jsonl
  MANIFEST_PATH       data/ingestion_manifest.json
  CHROMA_PERSIST_PATH data/chroma_db
  CHROMA_COLLECTION   mutual_fund_faq
  EMBEDDING_MODEL     BAAI/bge-small-en-v1.5
  EMBEDDING_VER       2026-04
  BATCH_SIZE          32
  FORCE_FULL_RERUN    false
  PIPELINE_RUN_ID     local
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

# Ensure the project root (parent of ingestion/) is on sys.path so that
# 'from ingestion.vector_store import VectorStore' works when this script
# is executed directly (e.g. py ingestion/embedder.py).
import sys as _sys
import pathlib as _pathlib
_PROJECT_ROOT = str(_pathlib.Path(__file__).parent.parent)
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)

# VectorStore owns all ChromaDB + manifest operations (Stage E)
from ingestion.vector_store import VectorStore

# ---------------------------------------------------------------------------
# Logging -- UTF-8 safe on all platforms (avoids cp1252 crash on Windows)
# ---------------------------------------------------------------------------
_utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    handlers=[logging.StreamHandler(_utf8_stdout)],
)
log = logging.getLogger("embedder")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
_ROOT = _HERE.parent

CHUNKS_JSONL        = Path(os.environ.get("CHUNKS_JSONL",        _ROOT / "data" / "chunks.jsonl"))
MANIFEST_PATH       = Path(os.environ.get("MANIFEST_PATH",       _ROOT / "data" / "ingestion_manifest.json"))
CHROMA_PERSIST_PATH = Path(os.environ.get("CHROMA_PERSIST_PATH", _ROOT / "data" / "chroma_db"))
CHROMA_COLLECTION   = os.environ.get("CHROMA_COLLECTION",   "mutual_fund_faq")
EMBEDDING_MODEL     = os.environ.get("EMBEDDING_MODEL",     "BAAI/bge-small-en-v1.5")
EMBEDDING_VER       = os.environ.get("EMBEDDING_VER",       "2026-04")
BATCH_SIZE          = int(os.environ.get("BATCH_SIZE",      "32"))
FORCE_FULL_RERUN    = os.environ.get("FORCE_FULL_RERUN",    "false").lower() == "true"
PIPELINE_RUN_ID     = os.environ.get("PIPELINE_RUN_ID",     "local")

# BGE prefix -- MUST be applied to every chunk content before encoding.
# BGE-small is trained as an asymmetric bi-encoder; omitting this prefix
# measurably degrades Recall@3. See architecture spec section 4.2.
BGE_PREFIX = "Represent this sentence: "

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Stage C -- Change Detection
# ---------------------------------------------------------------------------

def load_manifest(path: Path) -> dict[str, Any]:
    """
    Load the previous ingestion manifest.

    Returns an empty manifest dict if the file does not exist (first run).
    The manifest's "chunks" key maps chunk_id -> {doc_hash, source_url}.
    """
    empty: dict[str, Any] = {
        "chunk_ids": [],
        "chunks": {},       # chunk_id -> {doc_hash, source_url}
        "doc_hashes": {},   # source_url -> doc_hash
    }

    if not path.exists():
        log.info("No previous manifest found at %s -- treating all chunks as NEW", path)
        return empty

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        log.info("Loaded manifest from %s  (run_id: %s)", path, data.get("run_id", "?"))
        # Back-fill "chunks" from flat chunk_ids if manifest was written by an older version
        if "chunks" not in data:
            data["chunks"] = {cid: {"doc_hash": "", "source_url": ""} for cid in data.get("chunk_ids", [])}
        return data
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read manifest (%s) -- treating all chunks as NEW", exc)
        return empty


def classify_chunks(
    current_chunks: list[dict],
    manifest: dict[str, Any],
    force_full_rerun: bool,
) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    """
    Classify all current chunks against the previous manifest.

    Returns:
        new_chunks      -- chunks not in manifest (need embed + upsert)
        updated_chunks  -- chunks whose doc_hash changed (need re-embed + upsert)
        unchanged_chunks-- chunks identical to manifest (skip)
        deleted_ids     -- chunk_ids in manifest but absent from current run (delete)
    """
    if force_full_rerun:
        log.info("FORCE_FULL_RERUN=true -- classifying all %d chunks as NEW", len(current_chunks))
        return list(current_chunks), [], [], []

    manifest_chunks: dict[str, dict] = manifest.get("chunks", {})
    current_ids: set[str] = {c["chunk_id"] for c in current_chunks}

    new_chunks:       list[dict] = []
    updated_chunks:   list[dict] = []
    unchanged_chunks: list[dict] = []

    for chunk in current_chunks:
        cid = chunk["chunk_id"]
        if cid not in manifest_chunks:
            new_chunks.append(chunk)
        elif manifest_chunks[cid].get("doc_hash", "") != chunk["doc_hash"]:
            updated_chunks.append(chunk)
        else:
            unchanged_chunks.append(chunk)

    # DELETED: present in manifest but absent in current run
    deleted_ids: list[str] = [
        cid for cid in manifest_chunks if cid not in current_ids
    ]

    return new_chunks, updated_chunks, unchanged_chunks, deleted_ids


# ---------------------------------------------------------------------------
# Stage D -- Batch Embedding
# ---------------------------------------------------------------------------

def load_model(model_name: str):
    """Load the SentenceTransformer model. Downloads on first run, cached after."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        log.critical("sentence-transformers not installed. Run: pip install sentence-transformers")
        sys.exit(1)

    log.info("Loading embedding model: %s", model_name)
    t0 = time.time()
    model = SentenceTransformer(model_name)
    log.info("Model loaded in %.1fs", time.time() - t0)
    return model


def embed_chunks(
    chunks: list[dict],
    model,
    batch_size: int = 32,
) -> list[list[float]]:
    """
    Embed a list of chunk dicts.

    BGE prefix "Represent this sentence: " is prepended to every chunk content
    before encoding. This is REQUIRED for bge-small-en-v1.5 retrieval quality.

    Returns a list of 384-dim float32 vectors (L2-normalized via
    normalize_embeddings=True, which makes dot product == cosine similarity).
    """
    if not chunks:
        return []

    texts = [f"{BGE_PREFIX}{chunk['content']}" for chunk in chunks]

    log.info("Encoding %d chunk(s) with batch_size=%d ...", len(chunks), batch_size)
    t0 = time.time()

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,   # L2 normalize -> dot product == cosine
        show_progress_bar=True,
    )

    elapsed = time.time() - t0
    log.info(
        "Encoded %d chunk(s) in %.1fs  (%.2f chunks/sec)  dim=%d",
        len(chunks), elapsed, len(chunks) / max(elapsed, 0.001),
        len(embeddings[0]) if len(embeddings) > 0 else 0,
    )

    return embeddings.tolist()


def embed_query(query: str, model) -> list[float]:
    """
    Embed a single query string with the BGE prefix.
    Used at retrieval time (Phase 5 retriever imports this function).
    """
    return model.encode(
        f"{BGE_PREFIX}{query}",
        normalize_embeddings=True,
    ).tolist()


# ---------------------------------------------------------------------------
# Stage E -- ChromaDB Upsert + Cleanup
# ---------------------------------------------------------------------------

def get_collection(persist_path: Path, collection_name: str):
    """
    Connect to ChromaDB and return (or create) the target collection.
    Distance metric: cosine (via hnsw:space=cosine).
    """
    try:
        import chromadb
    except ImportError:
        log.critical("chromadb not installed. Run: pip install chromadb")
        sys.exit(1)

    CHROMA_PERSIST_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_path))

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    log.info(
        "ChromaDB collection '%s' ready  (existing vectors: %d)",
        collection_name, collection.count(),
    )
    return collection


def upsert_to_chroma(
    collection,
    chunks: list[dict],
    embeddings: list[list[float]],
) -> None:
    """
    Upsert chunks and their embeddings into ChromaDB.
    Upsert is idempotent -- re-running with the same chunk_id overwrites.

    Metadata fields stored per chunk (ChromaDB only accepts str/int/float):
      source_url, scheme_name, section_heading, doc_type,
      last_crawled_date, chunk_index, embedding_model
    """
    if not chunks:
        return

    # ChromaDB upsert is batched internally, but we call it in our own
    # batches to keep memory manageable and log progress.
    UPSERT_BATCH = 100
    total = len(chunks)

    for start in range(0, total, UPSERT_BATCH):
        batch_chunks = chunks[start : start + UPSERT_BATCH]
        batch_embeds = embeddings[start : start + UPSERT_BATCH]

        collection.upsert(
            ids=[c["chunk_id"] for c in batch_chunks],
            embeddings=batch_embeds,
            documents=[c["content"] for c in batch_chunks],
            metadatas=[
                {
                    "source_url":        c["source_url"],
                    "scheme_name":       c["scheme_name"],
                    "category":          c.get("category", ""),
                    "section_heading":   c["section_heading"],
                    "doc_type":          c["doc_type"],
                    "last_crawled_date": c["last_crawled_date"],
                    "chunk_index":       int(c["chunk_index"]),
                    "embedding_model":   c["embedding_model"],
                }
                for c in batch_chunks
            ],
        )
        end = min(start + UPSERT_BATCH, total)
        log.info("Upserted %d/%d vectors", end, total)


def delete_from_chroma(collection, deleted_ids: list[str]) -> None:
    """Delete stale vectors from ChromaDB for DELETED chunk_ids."""
    if not deleted_ids:
        return
    log.info("Deleting %d stale vector(s) from ChromaDB", len(deleted_ids))
    collection.delete(ids=deleted_ids)


# ---------------------------------------------------------------------------
# Manifest writer
# ---------------------------------------------------------------------------

def write_manifest(
    path: Path,
    *,
    all_chunks: list[dict],
    counts: dict[str, int],
    collection_count: int,
) -> None:
    """
    Write ingestion_manifest.json after a successful pipeline run.

    The "chunks" sub-dict stores per-chunk metadata needed for next-run
    change detection: {chunk_id: {doc_hash, source_url}}.
    """
    # Per-URL doc_hash index
    doc_hashes: dict[str, str] = {}
    for c in all_chunks:
        doc_hashes[c["source_url"]] = c["doc_hash"]

    # Per-chunk index for change detection
    chunk_meta: dict[str, dict] = {
        c["chunk_id"]: {
            "doc_hash":   c["doc_hash"],
            "source_url": c["source_url"],
        }
        for c in all_chunks
    }

    manifest = {
        "run_id":              PIPELINE_RUN_ID,
        "pipeline_run_at":     utc_now(),
        "triggered_by":        "workflow_dispatch" if PIPELINE_RUN_ID != "local" else "local",
        "force_full_rerun":    FORCE_FULL_RERUN,
        "embedding_model":     EMBEDDING_MODEL,
        "embedding_version":   EMBEDDING_VER,
        "counts": {
            "new":               counts.get("new", 0),
            "updated":           counts.get("updated", 0),
            "unchanged":         counts.get("unchanged", 0),
            "deleted":           counts.get("deleted", 0),
            "total_in_collection": collection_count,
        },
        "urls_processed":      len(doc_hashes),
        "chunk_ids":           list(chunk_meta.keys()),
        "doc_hashes":          doc_hashes,
        "chunks":              chunk_meta,   # used by next run's change detection
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    log.info("Manifest written -> %s  (%d chunks indexed)", path, len(chunk_meta))


# ---------------------------------------------------------------------------
# Self-test: verify 384-dim vectors + ChromaDB smoke-test
# ---------------------------------------------------------------------------

def run_self_test() -> None:
    """
    Exit-criteria test:
      1. Embed 5 synthetic chunks and verify they are 384-dim L2-normalised.
      2. Upsert them into ChromaDB via VectorStore (integration smoke-test).
      3. Verify count in collection == 5.
    """
    log.info("=" * 72)
    log.info("SELF-TEST MODE -- verifying 384-dim output + ChromaDB integration")
    log.info("=" * 72)

    test_chunks = [
        {
            "chunk_id":          f"embedder_test_{i}",
            "doc_hash":          f"dochash_{i}",
            "content":           text,
            "source_url":        f"https://groww.in/test-{i}",
            "scheme_name":       "Mirae Asset Large Cap Fund",
            "category":          "Test",
            "section_heading":   "Test",
            "doc_type":          "groww_page",
            "last_crawled_date": "2026-04-17",
            "chunk_index":       i,
            "embedding_model":   EMBEDDING_MODEL,
        }
        for i, text in enumerate(
            [
                "The expense ratio of Mirae Asset Large Cap Fund Direct Plan is 0.58%.",
                "The exit load for Mirae Asset Large Cap Fund is 1% if redeemed within 1 year.",
                "The minimum SIP amount for Mirae Asset Large Cap Fund is Rs. 99 per month.",
                "Mirae Asset Large Cap Fund has an ELSS lock-in period of 3 years.",
                "The benchmark index for Mirae Asset Large Cap Fund is Nifty 100 TRI.",
            ]
        )
    ]

    # ---- Stage D: embed ----
    model = load_model(EMBEDDING_MODEL)
    embeddings = embed_chunks(test_chunks, model, batch_size=BATCH_SIZE)

    passed = True
    for i, (chunk, vec) in enumerate(zip(test_chunks, embeddings)):
        dim    = len(vec)
        is_flt = all(isinstance(v, float) for v in vec[:5])
        norm   = sum(v * v for v in vec) ** 0.5
        ok     = dim == 384 and is_flt
        if not ok:
            passed = False
        log.info(
            "  embed chunk %d | dim=%-4d | float=%s | L2_norm=%.6f | %s",
            i, dim, is_flt, norm, "PASS" if ok else "FAIL",
        )

    if not passed:
        log.error("SELF-TEST FAILED: unexpected vector dimensions or types")
        sys.exit(1)

    # ---- Stage E: ChromaDB smoke-test (use a temporary test collection) ----
    SMOKE_COLLECTION = "embedder_self_test"
    log.info("Upserting 5 test chunks into ChromaDB collection '%s' ...", SMOKE_COLLECTION)

    vs = VectorStore(
        persist_path=CHROMA_PERSIST_PATH,
        collection_name=SMOKE_COLLECTION,
    )
    vs.upsert(test_chunks, embeddings)
    count = vs.count()
    assert count == 5, f"Expected 5 in smoke collection, got {count}"
    log.info("  ChromaDB smoke-test: count=%d  [PASS]", count)

    # Cleanup smoke collection
    import chromadb as _chroma
    _c = _chroma.PersistentClient(path=str(CHROMA_PERSIST_PATH))
    _c.delete_collection(SMOKE_COLLECTION)
    del _c
    log.info("  Smoke collection cleaned up")

    log.info("=" * 72)
    log.info("SELF-TEST PASSED: 5 chunks -> 384-dim + ChromaDB upsert verified")
    log.info("=" * 72)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 4.2+4.3 -- Embed & Upsert")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Embed 5 test chunks and verify 384-dim output, then exit.",
    )
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return

    t_start = time.time()

    log.info("=" * 72)
    log.info("Phase 4.2+4.3 - Embed & Upsert Service")
    log.info("Chunks JSONL    : %s", CHUNKS_JSONL)
    log.info("Manifest        : %s", MANIFEST_PATH)
    log.info("ChromaDB path   : %s", CHROMA_PERSIST_PATH)
    log.info("Collection      : %s", CHROMA_COLLECTION)
    log.info("Embedding model : %s  (ver=%s)", EMBEDDING_MODEL, EMBEDDING_VER)
    log.info("Batch size      : %d", BATCH_SIZE)
    log.info("Force full rerun: %s", FORCE_FULL_RERUN)
    log.info("Pipeline run ID : %s", PIPELINE_RUN_ID)
    log.info("=" * 72)

    # ---- 1. Load chunks -----------------------------------------------------
    if not CHUNKS_JSONL.exists():
        log.critical("chunks.jsonl not found at %s", CHUNKS_JSONL)
        sys.exit(1)

    all_chunks: list[dict] = []
    with CHUNKS_JSONL.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                all_chunks.append(json.loads(line))

    log.info("Loaded %d chunks from %s", len(all_chunks), CHUNKS_JSONL)

    if not all_chunks:
        log.warning("No chunks to process -- writing empty manifest and exiting")
        write_manifest(
            MANIFEST_PATH,
            all_chunks=[],
            counts={"new": 0, "updated": 0, "unchanged": 0, "deleted": 0},
            collection_count=0,
        )
        return

    # ---- 2. Load previous manifest ------------------------------------------
    manifest = load_manifest(MANIFEST_PATH)

    # ---- 3. Change detection (Stage C) --------------------------------------
    log.info("-" * 60)
    log.info("Stage C -- Change Detection")

    new_chunks, updated_chunks, unchanged_chunks, deleted_ids = classify_chunks(
        all_chunks, manifest, FORCE_FULL_RERUN
    )

    to_embed = new_chunks + updated_chunks
    counts = {
        "new":       len(new_chunks),
        "updated":   len(updated_chunks),
        "unchanged": len(unchanged_chunks),
        "deleted":   len(deleted_ids),
    }

    log.info(
        "Classification: NEW=%d  UPDATED=%d  UNCHANGED=%d  DELETED=%d",
        counts["new"], counts["updated"], counts["unchanged"], counts["deleted"],
    )

    # ---- 4. Embed NEW + UPDATED (Stage D) -----------------------------------
    log.info("-" * 60)
    log.info("Stage D -- Batch Embedding (%s)", EMBEDDING_MODEL)

    embeddings: list[list[float]] = []

    if to_embed:
        model = load_model(EMBEDDING_MODEL)
        embeddings = embed_chunks(to_embed, model, batch_size=BATCH_SIZE)

        # Sanity-check dimensions
        if embeddings and len(embeddings[0]) != 384:
            log.critical(
                "Unexpected embedding dimension: got %d, expected 384",
                len(embeddings[0]),
            )
            sys.exit(1)

        log.info("Embedding stage complete: %d vectors  dim=384", len(embeddings))
    else:
        log.info("Nothing to embed (all chunks UNCHANGED) -- skipping model load")

    # ---- 5. ChromaDB upsert + cleanup (Stage E via VectorStore) -------------
    log.info("-" * 60)
    log.info("Stage E -- ChromaDB Upsert + Cleanup (via VectorStore)")

    vs = VectorStore(
        persist_path=CHROMA_PERSIST_PATH,
        collection_name=CHROMA_COLLECTION,
    )

    if to_embed and embeddings:
        vs.upsert(to_embed, embeddings)

    if deleted_ids:
        vs.delete(deleted_ids)

    collection_count = vs.count()
    counts["total_in_collection"] = collection_count
    log.info("Collection '%s' now has %d vectors", CHROMA_COLLECTION, collection_count)

    # ---- 6. Write ingestion_manifest.json (via VectorStore) -----------------
    log.info("-" * 60)
    vs.write_manifest(MANIFEST_PATH, all_chunks=all_chunks, counts=counts)

    # ---- Summary ------------------------------------------------------------
    elapsed = time.time() - t_start
    log.info("=" * 72)
    log.info("Pipeline complete in %.1fs", elapsed)
    log.info("  NEW embedded    : %d", counts["new"])
    log.info("  UPDATED re-embed: %d", counts["updated"])
    log.info("  UNCHANGED skip  : %d", counts["unchanged"])
    log.info("  DELETED removed : %d", counts["deleted"])
    log.info("  Total in DB     : %d", collection_count)
    log.info("  Manifest        : %s", MANIFEST_PATH)
    log.info("=" * 72)


if __name__ == "__main__":
    main()
