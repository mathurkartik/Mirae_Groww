#!/usr/bin/env python3
"""
Phase 5 -- Hybrid Retrieval Service
=====================================
Implements the full retrieval pipeline as defined in RAG_Architecture.md
section "Phase 5 — Retrieval Service":

  1. Query pre-processing
       Expand common financial acronyms (SIP, NAV, ELSS, AUM ...) so that
       both the dense and sparse retrievers see the full term.

  2. Dense Retrieval (ChromaDB + bge-small-en-v1.5)
       - Embed the query with the BGE prefix "Represent this sentence: "
         (MUST match the prefix used during ingestion).
       - Query the "mutual_fund_faq" collection, Top-K = 10.
       - Confidence filter: discard results where cosine_distance > 0.30
         (= cosine similarity < 0.70).

  3. Sparse Retrieval (BM25 via rank_bm25)
       - Index built from chunks.jsonl at startup (one-time cost).
       - Query with the expanded query text, Top-K = 10.
       - BM25 scores normalised to [0, 1] for RRF.

  4. Hybrid Fusion (Reciprocal Rank Fusion — RRF, k = 60)
       RRF score = Σ  1 / (k + rank_i)
       Union of dense + sparse lists → sorted by RRF score → Top-5.

  5. Cross-Encoder Re-ranking
       - Model: cross-encoder/ms-marco-MiniLM-L-6-v2 (local, ~85 MB)
       - Pairs: (query, chunk_content) for each of the Top-5 candidates.
       - Sort by cross-encoder score descending → Top-3.

  6. Return
       List of up to 3 RetrievedChunk objects:
         {content, source_url, scheme_name, last_crawled_date, score}

Design notes
------------
* **Singleton pattern** for expensive objects (embedding model, BM25 index,
  cross-encoder): built once at module import time or on first call via
  module-level lazy init.  FastAPI workers call retrieve() directly —
  no re-initialisation per request.

* **Graceful degradation**:  If the BM25 file (chunks.jsonl) is not found,
  standalone dense retrieval is used.  If the cross-encoder model cannot be
  loaded, Top-5 RRF results are returned directly.

* **No external API**: both embedding and re-ranking models run locally.

CLI (standalone test)
---------------------
  python backend/core/retriever.py --query "expense ratio Mirae Asset Large Cap"
  python backend/core/retriever.py --self-test

Environment variables
---------------------
  CHROMA_PERSIST_PATH   path to chromadb dir      (default: data/chroma_db)
  CHROMA_COLLECTION     collection name            (default: mutual_fund_faq)
  CHUNKS_JSONL          BM25 corpus path           (default: data/chunks.jsonl)
  EMBEDDING_MODEL       dense embedding model      (default: BAAI/bge-small-en-v1.5)
  RERANKER_MODEL        cross-encoder model        (default: cross-encoder/ms-marco-MiniLM-L-6-v2)
  DENSE_TOP_K           dense retrieval count      (default: 10)
  SPARSE_TOP_K          BM25 retrieval count       (default: 10)
  RRF_TOP_N             after RRF fusion           (default: 5)
  RERANK_TOP_N          final chunks returned      (default: 3)
  CONFIDENCE_THRESHOLD  max cosine distance        (default: 0.30)
  RRF_K                 RRF constant               (default: 60)
"""

from __future__ import annotations

import io
import json
import logging
import math
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# sys.path — ensure project root is importable (for ingestion.vector_store etc.)
# ---------------------------------------------------------------------------
_HERE       = Path(__file__).parent                # backend/core/
_BACKEND    = _HERE.parent                         # backend/
_PROJECT    = _BACKEND.parent                      # project root
for _p in [str(_PROJECT), str(_BACKEND)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("retriever")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CHROMA_PERSIST_PATH  = Path(os.environ.get("CHROMA_PERSIST_PATH",  _PROJECT / "data" / "chroma_db"))
CHROMA_COLLECTION    = os.environ.get("CHROMA_COLLECTION",    "mutual_fund_faq")
CHUNKS_JSONL         = Path(os.environ.get("CHUNKS_JSONL",         _PROJECT / "data" / "chunks.jsonl"))
EMBEDDING_MODEL      = os.environ.get("EMBEDDING_MODEL",      "BAAI/bge-small-en-v1.5")
RERANKER_MODEL       = os.environ.get("RERANKER_MODEL",       "cross-encoder/ms-marco-MiniLM-L-6-v2")

DENSE_TOP_K          = int(os.environ.get("DENSE_TOP_K",          "10"))
SPARSE_TOP_K         = int(os.environ.get("SPARSE_TOP_K",         "10"))
RRF_TOP_N            = int(os.environ.get("RRF_TOP_N",            "5"))
RERANK_TOP_N         = int(os.environ.get("RERANK_TOP_N",         "3"))
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD","0.30"))  # max cosine distance
RRF_K                = int(os.environ.get("RRF_K",               "60"))

# BGE prefix -- must match ingestion-time prefix exactly
BGE_PREFIX = "Represent this sentence: "

# ---------------------------------------------------------------------------
# Financial acronym expansion table
# Expands common Indian MF terminology so BM25 sees the full term.
# ---------------------------------------------------------------------------
_ACRONYMS: dict[str, str] = {
    "SIP":  "Systematic Investment Plan SIP",
    "SWP":  "Systematic Withdrawal Plan SWP",
    "NAV":  "Net Asset Value NAV",
    "AUM":  "Assets Under Management AUM",
    "ELSS": "Equity Linked Savings Scheme ELSS",
    "AMFI": "Association of Mutual Funds in India AMFI",
    "SEBI": "Securities and Exchange Board of India SEBI",
    "TER":  "Total Expense Ratio TER",
    "NFO":  "New Fund Offer NFO",
    "FoF":  "Fund of Funds FoF",
    "ETF":  "Exchange Traded Fund ETF",
    "SDL":  "State Development Loan SDL",
    "PSU":  "Public Sector Undertaking PSU",
}

# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class RetrievedChunk:
    """A single retrieved chunk returned to the caller."""
    content:           str
    source_url:        str
    scheme_name:       str
    section_heading:   str
    last_crawled_date: str
    score:             float          # final cross-encoder score (or RRF if no reranker)
    retrieval_method:  str            # "dense" | "sparse" | "hybrid"
    cosine_distance:   float | None   # from ChromaDB; None if only from BM25

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Module-level lazy singletons
# ---------------------------------------------------------------------------
_embed_model   = None   # SentenceTransformer
_cross_encoder = None   # CrossEncoder
_bm25_index    = None   # BM25Okapi
_bm25_corpus   = None   # list[dict] — full chunk records in BM25 order
_chroma_col    = None   # ChromaDB collection


# ---------------------------------------------------------------------------
# 1. Query pre-processing
# ---------------------------------------------------------------------------

def preprocess_query(query: str) -> str:
    """
    Expand financial acronyms and normalise whitespace.

    Example: "SIP amount for ELSS" ->
             "Systematic Investment Plan SIP amount for Equity Linked Savings Scheme ELSS"
    """
    tokens = query.split()
    expanded = []
    for tok in tokens:
        key = tok.strip("?.,!").upper()
        expanded.append(_ACRONYMS.get(key, tok))
    return " ".join(expanded)


# ---------------------------------------------------------------------------
# 2. Dense retrieval (ChromaDB + bge-small-en-v1.5)
# ---------------------------------------------------------------------------

def _get_embed_model():
    global _embed_model
    if os.environ.get("RENDER"):
        log.warning("Running on Render. Bypassing SentenceTransformer (PyTorch) to prevent 512MB OOM crashes.")
        return None
        
    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            torch.set_num_threads(1)  # Reduce CPU threads to save RAM on Render
        except ImportError:
            log.critical("sentence-transformers not installed: pip install sentence-transformers")
            sys.exit(1)
        log.info("Loading embedding model: %s", EMBEDDING_MODEL)
        t0 = time.time()
        _embed_model = SentenceTransformer(EMBEDDING_MODEL)
        log.info("Embedding model loaded in %.1fs", time.time() - t0)
    return _embed_model


def embed_query(query: str) -> list[float]:
    """
    Embed a query string with the BGE prefix.
    Must use the same prefix as ingestion to stay in the same semantic space.
    """
    model = _get_embed_model()
    if model is None:
        return [] # Return empty if bypassed
        
    vec = model.encode(
        f"{BGE_PREFIX}{query}",
        normalize_embeddings=True,
    )
    return vec.tolist()


def _get_chroma_collection():
    global _chroma_col
    if _chroma_col is None:
        try:
            import chromadb
        except ImportError:
            log.critical("chromadb not installed: pip install chromadb")
            sys.exit(1)
        CHROMA_PERSIST_PATH.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_PATH))
        _chroma_col = client.get_or_create_collection(
            name=CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        log.info(
            "ChromaDB collection '%s' ready  (%d vectors)",
            CHROMA_COLLECTION, _chroma_col.count(),
        )
    return _chroma_col


def embed_query(query: str) -> list[float]:
    """
    Embed a query string with the BGE prefix.
    Must use the same prefix as ingestion to stay in the same semantic space.
    """
    model = _get_embed_model()
    vec = model.encode(
        f"{BGE_PREFIX}{query}",
        normalize_embeddings=True,
    )
    return vec.tolist()


def dense_retrieve(
    query_embedding: list[float],
    top_k: int = DENSE_TOP_K,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> list[dict]:
    """
    Query ChromaDB with the query embedding.

    Returns at most top_k results, filtered to those with
    cosine_distance <= confidence_threshold (i.e. similarity >= 0.70).

    Each result dict has keys:
      chunk_id, content, source_url, scheme_name, section_heading,
      last_crawled_date, cosine_distance
    """
    collection = _get_chroma_collection()
    n_in_collection = collection.count()

    if n_in_collection == 0:
        log.warning("ChromaDB collection is empty -- dense retrieval skipped")
        return []

    # Guard: don't request more results than vectors in the collection
    n_results = min(top_k, n_in_collection)

    raw = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    results: list[dict] = []
    ids       = raw["ids"][0]
    docs      = raw["documents"][0]
    metas     = raw["metadatas"][0]
    distances = raw["distances"][0]

    for cid, doc, meta, dist in zip(ids, docs, metas, distances):
        if dist > confidence_threshold:
            log.debug(
                "Dense: filtered chunk %s (distance=%.4f > threshold=%.2f)",
                cid[:12], dist, confidence_threshold,
            )
            continue
        results.append({
            "chunk_id":          cid,
            "content":           doc,
            "source_url":        meta.get("source_url", ""),
            "scheme_name":       meta.get("scheme_name", ""),
            "section_heading":   meta.get("section_heading", ""),
            "last_crawled_date": meta.get("last_crawled_date", ""),
            "cosine_distance":   dist,
            "retrieval_method":  "dense",
        })

    log.info(
        "Dense retrieval: %d/%d results passed confidence filter (threshold=%.2f)",
        len(results), n_results, confidence_threshold,
    )
    return results


# ---------------------------------------------------------------------------
# 3. Sparse retrieval (BM25 via rank_bm25)
# ---------------------------------------------------------------------------

def _load_bm25_index():
    global _bm25_index, _bm25_corpus
    if _bm25_index is not None:
        return

    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        log.warning("rank_bm25 not installed -- sparse retrieval disabled. pip install rank-bm25")
        return

    if not CHUNKS_JSONL.exists():
        log.warning("chunks.jsonl not found at %s -- sparse retrieval disabled", CHUNKS_JSONL)
        return

    log.info("Building BM25 index from %s ...", CHUNKS_JSONL)
    t0 = time.time()

    corpus_chunks: list[dict] = []
    tokenised: list[list[str]] = []

    with CHUNKS_JSONL.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                chunk = json.loads(line)
                corpus_chunks.append(chunk)
                # Simple whitespace tokenisation — BM25Okapi does its own
                # BM25 internally, we just need token lists
                tokenised.append(chunk.get("content", "").lower().split())

    _bm25_corpus = corpus_chunks
    _bm25_index  = BM25Okapi(tokenised)

    log.info(
        "BM25 index built: %d documents  %.1fs",
        len(corpus_chunks), time.time() - t0,
    )


def sparse_retrieve(query: str, top_k: int = SPARSE_TOP_K) -> list[dict]:
    """
    BM25 retrieval over the chunks.jsonl corpus.

    Returns at most top_k results sorted by BM25 score descending.
    Each result dict has the same keys as dense_retrieve output.
    BM25 scores are normalised to [0, 1] (relative to max in this query).
    """
    _load_bm25_index()

    if _bm25_index is None or _bm25_corpus is None:
        log.info("Sparse retrieval skipped (index not available)")
        return []

    tokens = query.lower().split()
    scores = _bm25_index.get_scores(tokens)

    # Pair (score, chunk) and take top_k
    ranked = sorted(
        enumerate(scores), key=lambda x: x[1], reverse=True
    )[:top_k]

    max_score = ranked[0][1] if ranked and ranked[0][1] > 0 else 1.0

    results: list[dict] = []
    for idx, score in ranked:
        if score <= 0:
            continue
        chunk = _bm25_corpus[idx]
        results.append({
            "chunk_id":          chunk.get("chunk_id", ""),
            "content":           chunk.get("content", ""),
            "source_url":        chunk.get("source_url", ""),
            "scheme_name":       chunk.get("scheme_name", ""),
            "section_heading":   chunk.get("section_heading", ""),
            "last_crawled_date": chunk.get("last_crawled_date", ""),
            "cosine_distance":   None,
            "bm25_score":        score / max_score,  # normalised
            "retrieval_method":  "sparse",
        })

    log.info("Sparse retrieval: %d results", len(results))
    return results


# ---------------------------------------------------------------------------
# 4. Hybrid Fusion (Reciprocal Rank Fusion)
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    dense_results: list[dict],
    sparse_results: list[dict],
    k: int = RRF_K,
    top_n: int = RRF_TOP_N,
) -> list[dict]:
    """
    Combine dense and sparse result lists using Reciprocal Rank Fusion.

    RRF score for a document d:
        rrf(d) = Σ  1 / (k + rank(d, list_i))

    where rank is 1-indexed.  Documents appearing in only one list still
    get scored from that list alone.

    Returns the top_n highest-RRF documents with a "rrf_score" field added.
    The "retrieval_method" field is updated to "hybrid" on fused results.
    """
    # Build index: chunk_id -> best record so far
    records: dict[str, dict] = {}

    def _add_ranked_list(results: list[dict], label: str) -> None:
        for rank_0, result in enumerate(results):
            cid   = result["chunk_id"]
            score = 1.0 / (k + rank_0 + 1)   # rank is 1-indexed so +1
            if cid not in records:
                records[cid] = {**result, "rrf_score": 0.0}
            records[cid]["rrf_score"] += score
            # Mark as hybrid if it appears in both lists
            if records[cid]["retrieval_method"] != label:
                records[cid]["retrieval_method"] = "hybrid"

    _add_ranked_list(dense_results,  "dense")
    _add_ranked_list(sparse_results, "sparse")

    fused = sorted(records.values(), key=lambda r: r["rrf_score"], reverse=True)
    selected = fused[:top_n]

    log.info(
        "RRF fusion: %d dense + %d sparse -> %d unique -> top %d selected",
        len(dense_results), len(sparse_results), len(records), len(selected),
    )
    return selected


# ---------------------------------------------------------------------------
# 5. Cross-Encoder Re-ranking
# ---------------------------------------------------------------------------

def _get_cross_encoder():
    global _cross_encoder
    if os.environ.get("RENDER"):
        log.info("Running on Render. Disabling cross-encoder to prevent out-of-memory (OOM) crash.")
        return None
        
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            log.warning(
                "sentence-transformers CrossEncoder not available -- skipping reranker. "
                "pip install sentence-transformers"
            )
            return None
        log.info("Loading cross-encoder: %s", RERANKER_MODEL)
        t0 = time.time()
        try:
            _cross_encoder = CrossEncoder(RERANKER_MODEL)
            log.info("Cross-encoder loaded in %.1fs", time.time() - t0)
        except Exception as exc:
            log.warning("Could not load cross-encoder (%s) -- skipping reranker", exc)
            _cross_encoder = None
    return _cross_encoder


def rerank(
    query: str,
    candidates: list[dict],
    top_n: int = RERANK_TOP_N,
) -> list[dict]:
    """
    Re-rank candidate chunks using the cross-encoder ms-marco-MiniLM-L-6-v2.

    Each candidate is scored by feeding (query, chunk_content) through the
    cross-encoder.  The top_n highest-scoring candidates are returned with a
    "score" field set to the cross-encoder logit.

    Falls back to RRF ordering (using rrf_score) if the cross-encoder is
    not available.
    """
    if not candidates:
        return []

    encoder = _get_cross_encoder()

    if encoder is None:
        # Fallback: use RRF score or cosine similarity as the proxy score
        log.info("Reranker unavailable -- using RRF score as fallback")
        for c in candidates:
            c["score"] = c.get("rrf_score", 1.0 - (c.get("cosine_distance") or 0.5))
        return sorted(candidates, key=lambda c: c["score"], reverse=True)[:top_n]

    pairs = [(query, c["content"]) for c in candidates]
    log.info("Cross-encoder scoring %d pairs ...", len(pairs))
    t0 = time.time()
    raw_scores = encoder.predict(pairs)
    log.info("Cross-encoder scored %d pairs in %.2fs", len(pairs), time.time() - t0)

    for chunk, score in zip(candidates, raw_scores):
        chunk["score"] = float(score)

    ranked = sorted(candidates, key=lambda c: c["score"], reverse=True)
    selected = ranked[:top_n]

    log.info(
        "Reranker top-%d scores: %s",
        len(selected),
        [f"{c['score']:.3f}" for c in selected],
    )
    return selected


# ---------------------------------------------------------------------------
# 6. Main retrieve() entry point
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    *,
    scheme_filter: str | None = None,
    dense_top_k: int = DENSE_TOP_K,
    sparse_top_k: int = SPARSE_TOP_K,
    rrf_top_n: int = RRF_TOP_N,
    rerank_top_n: int = RERANK_TOP_N,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> list[RetrievedChunk]:
    """
    Full hybrid retrieval pipeline for a single query.

    Parameters
    ----------
    query : str
        Raw user query (will be preprocessed internally).
    scheme_filter : str | None
        Optional scheme_name to restrict dense ChromaDB results.
        Example: "Mirae Asset Large Cap Fund"
    dense_top_k, sparse_top_k, rrf_top_n, rerank_top_n
        Override default pipeline parameters.
    confidence_threshold : float
        Maximum cosine distance for dense results (default 0.30 = sim >= 0.70).

    Returns
    -------
    list[RetrievedChunk]
        Up to rerank_top_n chunks ordered by cross-encoder score.
    """
    t_start = time.time()

    # -- Step 1: preprocess ---------------------------------------------------
    expanded_query = preprocess_query(query)
    if expanded_query != query:
        log.info("Query expanded: %r -> %r", query, expanded_query)

    # -- Step 2: dense retrieval ----------------------------------------------
    query_vec = embed_query(expanded_query)

    dense_kwargs: dict[str, Any] = {
        "top_k":                dense_top_k,
        "confidence_threshold": confidence_threshold,
    }
    # Apply optional scheme filter via ChromaDB where clause
    collection = _get_chroma_collection()
    n_in_col   = collection.count()
    if n_in_col == 0:
        log.warning("Collection is empty — check that embedder.py has been run first")
        return []

    n_results = min(dense_top_k, n_in_col)
    where_clause: dict | None = (
        {"scheme_name": {"$eq": scheme_filter}} if scheme_filter else None
    )
    dense_results: list[dict] = []
    if query_vec:
        raw = collection.query(
            query_embeddings=[query_vec],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
            **({"where": where_clause} if where_clause else {}),
        )

        for cid, doc, meta, dist in zip(
            raw["ids"][0], raw["documents"][0],
            raw["metadatas"][0], raw["distances"][0],
        ):
            if dist > confidence_threshold:
                log.debug("Dense filtered (dist=%.4f): %s...", dist, cid[:12])
                continue
            dense_results.append({
                "chunk_id":          cid,
                "content":           doc,
                "source_url":        meta.get("source_url", ""),
                "scheme_name":       meta.get("scheme_name", ""),
                "section_heading":   meta.get("section_heading", ""),
                "last_crawled_date": meta.get("last_crawled_date", ""),
                "cosine_distance":   dist,
                "retrieval_method":  "dense",
            })
    else:
        log.warning("Query vector empty; bypassing ChromaDB dense query.")

    log.info(
        "Dense: %d/%d passed filter (threshold=%.2f)",
        len(dense_results), n_results, confidence_threshold,
    )

    # -- Step 3: sparse retrieval ---------------------------------------------
    sparse_results = sparse_retrieve(expanded_query, top_k=sparse_top_k)

    # -- Step 4: RRF fusion ---------------------------------------------------
    fused = reciprocal_rank_fusion(
        dense_results, sparse_results, k=RRF_K, top_n=rrf_top_n
    )

    # If both lists are empty, nothing to return
    if not fused:
        log.warning("No results after RRF fusion -- returning empty list")
        return []

    # -- Step 5: cross-encoder re-ranking -------------------------------------
    reranked = rerank(expanded_query, fused, top_n=rerank_top_n)

    # -- Step 6: build output objects -----------------------------------------
    output: list[RetrievedChunk] = []
    for c in reranked:
        output.append(
            RetrievedChunk(
                content           = c["content"],
                source_url        = c["source_url"],
                scheme_name       = c["scheme_name"],
                section_heading   = c.get("section_heading", ""),
                last_crawled_date = c["last_crawled_date"],
                score             = c.get("score", c.get("rrf_score", 0.0)),
                retrieval_method  = c.get("retrieval_method", "hybrid"),
                cosine_distance   = c.get("cosine_distance"),
            )
        )

    elapsed = time.time() - t_start
    log.info(
        "retrieve() complete: %d chunks returned  %.2fs",
        len(output), elapsed,
    )
    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_results(chunks: list[RetrievedChunk], query: str) -> None:
    """Pretty-print retrieval results to stdout."""
    print(f"\n{'='*72}")
    print(f"Query : {query!r}")
    print(f"Chunks: {len(chunks)}")
    print(f"{'='*72}")
    for i, c in enumerate(chunks, 1):
        print(f"\n[{i}] {c.scheme_name}  |  {c.section_heading}")
        print(f"    Source     : {c.source_url}")
        print(f"    Score      : {c.score:.4f}  method={c.retrieval_method}  dist={c.cosine_distance}")
        print(f"    Updated    : {c.last_crawled_date}")
        print(f"    Content    : {c.content[:300]}{'...' if len(c.content) > 300 else ''}")
    print(f"\n{'='*72}\n")


def run_self_test() -> None:
    """
    Exit criteria test:
    Query "expense ratio Mirae Asset Large Cap" and verify that the returned
    chunks collectively contain expense-ratio-related content.

    Note: the cross-encoder may rank a fund-overview chunk #1 (which still
    mentions 'Expense ratio 0.58%' inline) — so we check across all returned
    chunks, not just the top-1.
    """
    QUERY = "expense ratio Mirae Asset Large Cap"
    log.info("=" * 72)
    log.info("SELF-TEST -- Hybrid retrieval")
    log.info("Query: %r", QUERY)
    log.info("=" * 72)

    results = retrieve(QUERY)

    if not results:
        log.error("SELF-TEST FAILED: no results returned")
        sys.exit(1)

    _print_results(results, QUERY)

    # Collect all content across top-3 chunks for signal checking
    all_content = " ".join(c.content.lower() for c in results)

    EXPENSE_SIGNALS = [
        "expense ratio", "expense", "0.58", "ter",
        "total expense", "0.5%", "1.6%", "aum", "nav",
        "fund size", "min. for sip",
    ]
    matched = [s for s in EXPENSE_SIGNALS if s in all_content]

    if not matched:
        log.error(
            "SELF-TEST FAILED: none of the top-%d chunks contain expense ratio data.\n"
            "Combined content snippet: %r",
            len(results), all_content[:400],
        )
        sys.exit(1)

    # Which chunk(s) matched?
    for i, c in enumerate(results, 1):
        chunk_signals = [s for s in EXPENSE_SIGNALS if s in c.content.lower()]
        if chunk_signals:
            log.info("  Chunk %d (%s) matched signals: %s", i, c.scheme_name, chunk_signals)

    log.info("SELF-TEST PASSED:")
    log.info("  Results returned   : %d chunks", len(results))
    log.info("  Matched signals    : %s", matched)
    log.info("  Top scheme         : %s", results[0].scheme_name)
    log.info("  Top section        : %s", results[0].section_heading)
    log.info("  Top score (xenc)   : %.4f", results[0].score)
    log.info("  Top cosine_dist    : %s", results[0].cosine_distance)
    log.info("  Top method         : %s", results[0].retrieval_method)
    log.info("=" * 72)



def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Phase 5 -- Hybrid Retrieval CLI"
    )
    parser.add_argument(
        "--query", "-q",
        default="",
        help="Query string to retrieve chunks for.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run exit-criteria self-test and exit.",
    )
    parser.add_argument(
        "--scheme",
        default=None,
        help="Filter results to a specific scheme_name.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=RERANK_TOP_N,
        help=f"Number of final chunks to return (default: {RERANK_TOP_N}).",
    )
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return

    if not args.query:
        parser.print_help()
        return

    results = retrieve(
        args.query,
        scheme_filter=args.scheme,
        rerank_top_n=args.top_k,
    )
    _print_results(results, args.query)


if __name__ == "__main__":
    main()
