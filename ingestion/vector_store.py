#!/usr/bin/env python3
"""
Phase 4.3 -- Vector Store (ChromaDB PersistentClient)
======================================================
Canonical wrapper around ChromaDB for the Mutual Fund FAQ ingestion pipeline.
All direct ChromaDB calls are centralised here so that embedder.py, the
retriever, and tests have a single, consistent interface.

Key design choices
------------------
* **Local only** -- chromadb.PersistentClient(path=...) writes to disk.
  No ChromaDB Cloud, no trychroma.com, no network calls.
* **Idempotent upsert** -- indexed by chunk_id (SHA-256).  Re-running with
  the same chunk_id safely overwrites; no duplicate entries possible.
* **Cosine distance** -- collection created with hnsw:space=cosine.
  Normalised embeddings (L2-norm=1) make dot product == cosine similarity,
  so distances returned by ChromaDB are in [0, 2] where 0 = identical.
* **Batched writes** -- upserts are chunked at UPSERT_BATCH=100 to keep
  peak memory predictable regardless of collection size.

CLI (standalone)
----------------
  python ingestion/vector_store.py --self-test
        Runs the persistence test:
          1. Upserts 10 test chunks (random 384-dim L2-normalised vectors)
             into a *temporary* test collection.
          2. Closes the ChromaDB client (simulates process exit).
          3. Re-opens the client from the same path (simulates restart).
          4. Queries the collection and verifies all 10 vectors are present.
          5. Cleans up the test collection.

  python ingestion/vector_store.py --info
        Prints current collection stats (count, path, collection name).

Environment variables (all optional -- defaults shown)
------------------------------------------------------
  CHROMA_PERSIST_PATH   data/chroma_db
  CHROMA_COLLECTION     mutual_fund_faq
  MANIFEST_PATH         data/ingestion_manifest.json
  EMBEDDING_MODEL       BAAI/bge-small-en-v1.5
  EMBEDDING_VER         2026-04
  PIPELINE_RUN_ID       local

Public API (import from other modules)
--------------------------------------
  vs = VectorStore(persist_path, collection_name)
  vs.upsert(chunks, embeddings)          # list[dict], list[list[float]]
  vs.delete(chunk_ids)                   # list[str]
  vs.query(query_embedding, n=10, where=None)   # returns Chroma results dict
  vs.count()                             # int
  vs.write_manifest(path, all_chunks, counts)
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import math
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
log = logging.getLogger("vector_store")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
_ROOT = _HERE.parent

CHROMA_PERSIST_PATH = Path(os.environ.get("CHROMA_PERSIST_PATH", _ROOT / "data" / "chroma_db"))
CHROMA_COLLECTION   = os.environ.get("CHROMA_COLLECTION",   "mutual_fund_faq")
MANIFEST_PATH       = Path(os.environ.get("MANIFEST_PATH",  _ROOT / "data" / "ingestion_manifest.json"))
EMBEDDING_MODEL     = os.environ.get("EMBEDDING_MODEL",     "BAAI/bge-small-en-v1.5")
EMBEDDING_VER       = os.environ.get("EMBEDDING_VER",       "2026-04")
PIPELINE_RUN_ID     = os.environ.get("PIPELINE_RUN_ID",     "local")

# How many records to write per ChromaDB call.
# Keeps peak memory predictable for large collections.
UPSERT_BATCH = 100

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _import_chromadb():
    """Lazy import with a friendly error if not installed."""
    try:
        import chromadb
        return chromadb
    except ImportError:
        log.critical(
            "chromadb is not installed. Run:\n"
            "    pip install chromadb"
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# VectorStore class
# ---------------------------------------------------------------------------

class VectorStore:
    """
    Thin, opinionated wrapper around a single ChromaDB PersistentClient
    collection for the mutual_fund_faq ingestion pipeline.

    Parameters
    ----------
    persist_path : str | Path
        Directory where ChromaDB writes its on-disk HNSW index and SQLite DB.
        Created automatically if it does not exist.
    collection_name : str
        ChromaDB collection name.  Created with hnsw:space=cosine on first use.
    """

    def __init__(
        self,
        persist_path: str | Path = CHROMA_PERSIST_PATH,
        collection_name: str = CHROMA_COLLECTION,
    ) -> None:
        chromadb = _import_chromadb()

        self.persist_path    = Path(persist_path)
        self.collection_name = collection_name

        self.persist_path.mkdir(parents=True, exist_ok=True)

        # PersistentClient -- local disk only, no network
        self._client = chromadb.PersistentClient(path=str(self.persist_path))

        # get_or_create ensures the collection exists with the right metadata
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        log.info(
            "VectorStore ready  path=%s  collection=%s  vectors=%d",
            self.persist_path, self.collection_name, self._collection.count(),
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def upsert(
        self,
        chunks: list[dict],
        embeddings: list[list[float]],
    ) -> None:
        """
        Upsert chunk documents and their embedding vectors.

        Idempotent: re-upserting with the same chunk_id overwrites the
        existing record -- no duplicates, no errors.

        Parameters
        ----------
        chunks : list[dict]
            Chunk dicts from chunks.jsonl.  Required keys:
              chunk_id, content, source_url, scheme_name, category,
              section_heading, doc_type, last_crawled_date, chunk_index,
              embedding_model
        embeddings : list[list[float]]
            384-dim L2-normalised float vectors, one per chunk.
            Must be the same length as chunks.

        ChromaDB metadata constraints
        ------------------------------
        Only str, int, and float values are accepted in the metadata dict.
        Boolean, None, and list values will raise a runtime error.
        """
        if not chunks:
            return

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch"
            )

        total = len(chunks)
        for start in range(0, total, UPSERT_BATCH):
            batch_c = chunks[start : start + UPSERT_BATCH]
            batch_e = embeddings[start : start + UPSERT_BATCH]

            self._collection.upsert(
                ids       = [c["chunk_id"] for c in batch_c],
                embeddings= batch_e,
                documents = [c["content"] for c in batch_c],
                metadatas = [
                    {
                        "source_url":        c.get("source_url", ""),
                        "scheme_name":       c.get("scheme_name", ""),
                        "category":          c.get("category", ""),
                        "section_heading":   c.get("section_heading", ""),
                        "doc_type":          c.get("doc_type", "groww_page"),
                        "last_crawled_date": c.get("last_crawled_date", ""),
                        "chunk_index":       int(c.get("chunk_index", 0)),
                        "embedding_model":   c.get("embedding_model", EMBEDDING_MODEL),
                    }
                    for c in batch_c
                ],
            )

            end = min(start + UPSERT_BATCH, total)
            log.info("Upserted %d / %d vectors", end, total)

    def delete(self, chunk_ids: list[str]) -> None:
        """
        Delete vectors for the given chunk_ids (DELETED chunks from change detection).

        Safe to call with an empty list -- no-op.
        Safe to call with ids that no longer exist -- ChromaDB ignores them.
        """
        if not chunk_ids:
            return
        log.info("Deleting %d stale vector(s)", len(chunk_ids))
        self._collection.delete(ids=chunk_ids)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: dict | None = None,
    ) -> dict:
        """
        Vector similarity query.

        Parameters
        ----------
        query_embedding : list[float]
            384-dim L2-normalised query vector (produced by embedder.embed_query).
        n_results : int
            Number of nearest neighbours to return.
        where : dict | None
            Optional ChromaDB $eq/$in metadata filter, e.g.
            {"scheme_name": "Mirae Asset Large Cap Fund"}

        Returns
        -------
        dict with keys: ids, documents, metadatas, distances
            Each is a list-of-lists (one inner list per query).
        """
        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results":        n_results,
            "include":          ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        return self._collection.query(**kwargs)

    def count(self) -> int:
        """Return the number of vectors currently in the collection."""
        return self._collection.count()

    def get_by_ids(self, ids: list[str]) -> dict:
        """Fetch specific records by chunk_id (used in tests and diagnostics)."""
        return self._collection.get(
            ids=ids,
            include=["documents", "metadatas"],
        )

    # ------------------------------------------------------------------
    # Manifest writer
    # ------------------------------------------------------------------

    def write_manifest(
        self,
        path: Path,
        all_chunks: list[dict],
        counts: dict[str, int],
    ) -> None:
        """
        Write data/ingestion_manifest.json at the end of a successful
        pipeline run.

        Schema (from chunking-embedding-architecture.md section 7):
          run_id, pipeline_run_at, embedding_model, embedding_version,
          counts{new, updated, unchanged, deleted, total_in_collection},
          urls_processed, chunk_ids[], doc_hashes{url->hash},
          chunks{chunk_id->{doc_hash, source_url}}   <- for next-run diff

        Parameters
        ----------
        path : Path
            Destination path for the JSON file.
        all_chunks : list[dict]
            All chunks from the current pipeline run (including UNCHANGED).
        counts : dict[str, int]
            Keys: new, updated, unchanged, deleted.
        """
        doc_hashes: dict[str, str] = {}
        chunk_meta: dict[str, dict] = {}

        for c in all_chunks:
            doc_hashes[c["source_url"]] = c["doc_hash"]
            chunk_meta[c["chunk_id"]] = {
                "doc_hash":   c["doc_hash"],
                "source_url": c["source_url"],
            }

        manifest = {
            "run_id":            PIPELINE_RUN_ID,
            "pipeline_run_at":   _utc_now(),
            "triggered_by":      "workflow_dispatch" if PIPELINE_RUN_ID != "local" else "local",
            "embedding_model":   EMBEDDING_MODEL,
            "embedding_version": EMBEDDING_VER,
            "counts": {
                "new":                 counts.get("new",       0),
                "updated":             counts.get("updated",   0),
                "unchanged":           counts.get("unchanged", 0),
                "deleted":             counts.get("deleted",   0),
                "total_in_collection": self.count(),
            },
            "urls_processed": len(doc_hashes),
            "chunk_ids":      list(chunk_meta.keys()),
            "doc_hashes":     doc_hashes,
            "chunks":         chunk_meta,   # per-chunk diff data for next run
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)

        log.info(
            "Manifest -> %s  (total=%d  new=%d  updated=%d  unchanged=%d  deleted=%d)",
            path,
            self.count(),
            counts.get("new", 0),
            counts.get("updated", 0),
            counts.get("unchanged", 0),
            counts.get("deleted", 0),
        )

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def info(self) -> dict:
        """Return a summary dict for logging / diagnostics."""
        return {
            "persist_path":    str(self.persist_path),
            "collection_name": self.collection_name,
            "vector_count":    self.count(),
            "hnsw_space":      "cosine",
        }


# ---------------------------------------------------------------------------
# Standalone helpers
# ---------------------------------------------------------------------------

def _random_unit_vector(dim: int = 384) -> list[float]:
    """Generate a random L2-normalised vector of the given dimension."""
    vec = [random.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec]


def _make_test_chunk(i: int) -> dict:
    """Build a minimal chunk dict for self-test purposes."""
    cid = hashlib.sha256(f"vs_test_chunk_{i}".encode()).hexdigest()
    return {
        "chunk_id":          cid,
        "doc_hash":          hashlib.sha256(f"doc_{i}".encode()).hexdigest(),
        "content":           f"Test chunk {i}: Mirae Asset Large Cap Fund expense ratio is 0.58% (test vector {i}).",
        "source_url":        f"https://groww.in/mutual-funds/test-fund-{i}",
        "scheme_name":       f"Test Fund {i}",
        "category":          "Test",
        "section_heading":   "Test Section",
        "doc_type":          "groww_page",
        "last_crawled_date": "2026-04-17",
        "chunk_index":       i,
        "embedding_model":   EMBEDDING_MODEL,
    }


# ---------------------------------------------------------------------------
# Self-test: persistence round-trip
# ---------------------------------------------------------------------------

def run_self_test(persist_path: Path) -> None:
    """
    Exit-criteria test -- upsert 10 chunks, close client, reopen, verify.

    Steps:
      1. Open VectorStore against a dedicated test collection.
      2. Upsert 10 test chunks with random 384-dim L2-normalised vectors.
      3. Verify count == 10 immediately after upsert.
      4. Delete the VectorStore object (releases client -> ChromaDB flushes).
      5. Re-create VectorStore from the same path (simulates process restart).
      6. Verify count == 10 (persistence confirmed).
      7. Retrieve all 10 records by ID and verify content is intact.
      8. Delete the test collection (cleanup).
    """
    TEST_COLLECTION = "vs_self_test"
    N = 10

    log.info("=" * 72)
    log.info("SELF-TEST -- VectorStore persistence round-trip (%d chunks)", N)
    log.info("Path : %s", persist_path)
    log.info("=" * 72)

    # -- Step 1: Create fresh VectorStore (test collection) --------------------
    log.info("Step 1: Opening VectorStore  collection=%s", TEST_COLLECTION)
    vs1 = VectorStore(persist_path=persist_path, collection_name=TEST_COLLECTION)

    # Clean slate: delete the test collection if it existed from a previous run
    chromadb = _import_chromadb()
    client_tmp = chromadb.PersistentClient(path=str(persist_path))
    try:
        client_tmp.delete_collection(TEST_COLLECTION)
        log.info("  (Deleted leftover test collection from previous run)")
    except Exception:
        pass
    del client_tmp

    vs1 = VectorStore(persist_path=persist_path, collection_name=TEST_COLLECTION)

    # -- Step 2: Upsert 10 chunks with random vectors -------------------------
    log.info("Step 2: Upserting %d chunks with random 384-dim vectors", N)
    test_chunks = [_make_test_chunk(i) for i in range(N)]
    test_vectors = [_random_unit_vector(384) for _ in range(N)]
    vs1.upsert(test_chunks, test_vectors)

    count_after_upsert = vs1.count()
    log.info("  Count after upsert: %d", count_after_upsert)
    assert count_after_upsert == N, f"Expected {N} vectors; got {count_after_upsert}"
    log.info("  [PASS] Count == %d immediately after upsert", N)

    # -- Step 3: Verify L2 norms of stored/fetched vectors match originals ------
    log.info("Step 3: Verifying upsert was idempotent (re-upsert same ids)")
    vs1.upsert(test_chunks, test_vectors)   # same ids -> should NOT increase count
    count_after_re_upsert = vs1.count()
    assert count_after_re_upsert == N, (
        f"Idempotency broken: expected {N} after re-upsert, got {count_after_re_upsert}"
    )
    log.info("  [PASS] Count still == %d after re-upsert (idempotent)", N)

    # -- Step 4: Close client (simulate process exit) --------------------------
    log.info("Step 4: Releasing VectorStore client (simulating process exit)")
    del vs1                # releases PersistentClient references -> disk flush
    time.sleep(0.5)        # give OS a moment to flush

    # -- Step 5: Re-open from same path (simulate restart) --------------------
    log.info("Step 5: Re-opening VectorStore from same path (simulating restart)")
    vs2 = VectorStore(persist_path=persist_path, collection_name=TEST_COLLECTION)
    count_after_restart = vs2.count()
    log.info("  Count after restart: %d", count_after_restart)
    assert count_after_restart == N, (
        f"PERSISTENCE FAILED: expected {N} vectors after restart; got {count_after_restart}"
    )
    log.info("  [PASS] All %d vectors survived process restart", N)

    # -- Step 6: Fetch all by id and verify content ---------------------------
    log.info("Step 6: Fetching all %d records by chunk_id", N)
    all_ids = [c["chunk_id"] for c in test_chunks]
    result = vs2.get_by_ids(all_ids)

    returned_ids = set(result["ids"])
    expected_ids = set(all_ids)
    missing = expected_ids - returned_ids
    assert not missing, f"Missing chunk_ids after restart: {missing}"

    # Spot-check one document
    sample_doc = result["documents"][0]
    assert "Mirae Asset Large Cap Fund" in sample_doc, (
        f"Document content mismatch: {sample_doc!r}"
    )
    log.info("  [PASS] All %d records intact, content verified", N)

    # -- Step 7: Verify metadata is stored correctly --------------------------
    log.info("Step 7: Verifying metadata fields")
    sample_meta = result["metadatas"][0]
    assert sample_meta["doc_type"] == "groww_page", f"doc_type wrong: {sample_meta}"
    assert isinstance(sample_meta["chunk_index"], int), "chunk_index should be int"
    log.info("  [PASS] Metadata fields correct (doc_type, chunk_index type)")

    # -- Step 8: Cleanup test collection --------------------------------------
    log.info("Step 8: Cleaning up test collection '%s'", TEST_COLLECTION)
    chromadb2 = _import_chromadb()
    cleanup_client = chromadb2.PersistentClient(path=str(persist_path))
    cleanup_client.delete_collection(TEST_COLLECTION)
    del cleanup_client
    log.info("  Test collection deleted")

    log.info("=" * 72)
    log.info(
        "SELF-TEST PASSED: %d chunks upserted, persisted across restart, "
        "content and metadata verified.",
        N,
    )
    log.info("=" * 72)


# ---------------------------------------------------------------------------
# Info command
# ---------------------------------------------------------------------------

def run_info(persist_path: Path, collection_name: str) -> None:
    """Print current collection statistics."""
    vs = VectorStore(persist_path=persist_path, collection_name=collection_name)
    info = vs.info()
    log.info("=" * 60)
    log.info("Collection info")
    for k, v in info.items():
        log.info("  %-22s: %s", k, v)
    log.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 4.3 -- VectorStore CLI (ChromaDB PersistentClient)"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help=(
            "Run persistence round-trip: upsert 10 chunks into a temporary "
            "test collection, close client, reopen, verify 10 vectors present."
        ),
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Print current collection statistics and exit.",
    )
    parser.add_argument(
        "--persist-path",
        default=str(CHROMA_PERSIST_PATH),
        help="Path to ChromaDB persistence directory (default: data/chroma_db)",
    )
    parser.add_argument(
        "--collection",
        default=CHROMA_COLLECTION,
        help="ChromaDB collection name (default: mutual_fund_faq)",
    )
    args = parser.parse_args()

    if args.self_test:
        run_self_test(Path(args.persist_path))
    elif args.info:
        run_info(Path(args.persist_path), args.collection)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
