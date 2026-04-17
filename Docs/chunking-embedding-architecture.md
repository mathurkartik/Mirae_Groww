# Chunking & Embedding Architecture

> **Project:** Mutual Fund FAQ Assistant — Mirae Asset
> **Version:** 2.0
> **Embedding Model:** `BAAI/bge-small-en-v1.5` (local via sentence-transformers)
> **Vector Dimension:** 384
> **Related doc:** `rag-architecture.md` (high-level system) — this file covers chunking + embedding only

---

## 1. Scope and Boundaries

| In scope | Out of scope (see other docs) |
|---|---|
| Document normalization after scraping | Scraping, scheduling, raw HTML (Phase 4.0) |
| Chunking strategy, parameters, metadata schema | Retrieval fusion, re-ranking, LLM generation |
| bge-small-en-v1.5 embedding — model loading, batching, caching | Frontend, chat API |
| ChromaDB upsert/delete semantics | Security and compliance details |
| Change detection (diff against ingestion manifest) | Deployment architecture |

**Upstream contract:** Scrape pipeline produces `cleaned_docs.jsonl` — one row per URL with fields: `source_url`, `scheme_name`, `scrape_date`, `content_hash` (SHA-256 of cleaned text), `cleaned_text`.

**Downstream contract:** ChromaDB collection `mutual_fund_faq` is queryable by 384-dim cosine vectors with metadata for filtering and citation.

---

## 2. End-to-End Pipeline

```
┌──────────────────────────────────────────────────────────────────────────────┐
│               CHUNKING + EMBEDDING EXECUTION PIPELINE                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Input: cleaned_docs.jsonl  (from scrape job)                               │
│                                                                              │
│  Stage A — Document Normalization                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  • Strip boilerplate (nav menus, cookie banners, footer links)         │  │
│  │  • Normalize whitespace (collapse multiple newlines/spaces)            │  │
│  │  • Preserve markdown-style headings (## H2, ### H3) and tables        │  │
│  │  • Compute doc_hash = SHA256(normalized_text)                          │  │
│  │  • Output: normalized_docs.jsonl                                       │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                            │                                                 │
│                            ▼                                                 │
│  Stage B — Deterministic Chunking                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Step 1: Section-aware split on H1 / H2 / H3 boundaries               │  │
│  │  Step 2: Tables kept atomic (single chunk if ≤ 500 tokens)            │  │
│  │         If table > 500 tokens → split on rows, duplicate header row   │  │
│  │  Step 3: Recursive token fallback on oversized sections                │  │
│  │         chunk_size = 500 tokens · overlap = 50 tokens                 │  │
│  │  Step 4: Assign chunk_index (0,1,2,…) per source_url                  │  │
│  │  Step 5: Compute chunk_id = SHA256(doc_hash + section_heading         │  │
│  │          + str(chunk_index))                                           │  │
│  │  Output: chunks.jsonl                                                  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                            │                                                 │
│                            ▼                                                 │
│  Stage C — Change Detection                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  • Load previous ingestion_manifest.json (if exists)                   │  │
│  │  • Compare current chunk_id set vs manifest chunk_id set              │  │
│  │  • Classify each chunk:                                                │  │
│  │      NEW      → not in manifest · proceed to embed                    │  │
│  │      UPDATED  → chunk_id exists but doc_hash changed · re-embed       │  │
│  │      UNCHANGED → chunk_id + doc_hash match · SKIP (no API call)       │  │
│  │      DELETED  → in manifest but not in current chunks · delete vector │  │
│  │  • Output: chunk_diff.json {new: [], updated: [], deleted: []}        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                            │                                                 │
│                            ▼                                                 │
│  Stage D — Batch Embedding (bge-small-en-v1.5)                               │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  • Load model: SentenceTransformer("BAAI/bge-small-en-v1.5")          │  │
│  │    First run: downloads from HuggingFace (~33MB)                       │  │
│  │    Subsequent runs: loads from local cache (~/.cache/huggingface)      │  │
│  │                                                                        │  │
│  │  • BGE prefix: prepend "Represent this sentence: " to each chunk text │  │
│  │    (required for bge-small to achieve best retrieval quality)          │  │
│  │                                                                        │  │
│  │  • Batch NEW + UPDATED chunks: batch_size = 32                        │  │
│  │  • model.encode(batch, normalize_embeddings=True, show_progress=True) │  │
│  │  • Output: 384-dim float32 vectors (L2-normalized)                    │  │
│  │                                                                        │  │
│  │  • Record per run: embedding_model, embedding_version                 │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                            │                                                 │
│                            ▼                                                 │
│  Stage E — Vector Upsert + Cleanup                                           │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  • Connect: chromadb.PersistentClient(path="data/chroma_db")          │  │
│  │  • Collection: "mutual_fund_faq" (create if not exists)               │  │
│  │  • Upsert NEW + UPDATED chunks by chunk_id (idempotent)               │  │
│  │  • Delete vectors for DELETED chunks                                   │  │
│  │  • Write ingestion_manifest.json for next run diff                    │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Output: ChromaDB collection synchronized with latest corpus state          │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Chunking Architecture — Detail

### 3.1 Splitting Strategy

| Priority | Splitter | Condition |
|---|---|---|
| 1st | Section-aware (H1/H2/H3) | Use when headings are present in cleaned text |
| 2nd | Table atomicity | Detected table blocks → keep whole; split on rows only if > 500 tokens |
| 3rd | Recursive character splitter | Fallback for any section still > 500 tokens |

**Separator hierarchy for recursive fallback:**
```
["\n## ", "\n### ", "\n\n", "\n", ". ", " "]
```

### 3.2 Parameters

| Parameter | Value | Rationale |
|---|---|---|
| `chunk_size` | 500 tokens | Financial facts are dense; 500 tokens gives enough context without diluting precision |
| `chunk_overlap` | 50 tokens | Prevents boundary cuts mid-sentence; acceptable memory cost |
| `min_chunk_size` | 50 tokens | Discard chunks too small to contain useful facts |
| `table_max_tokens` | 500 tokens | Keep table as one chunk up to this limit |

### 3.3 Chunk Metadata Schema

Every row in `chunks.jsonl`:

```json
{
  "chunk_id": "sha256(doc_hash + ':' + section_heading + ':' + str(chunk_index))",
  "doc_hash": "sha256(normalized_document_text)",
  "source_url": "https://groww.in/mutual-funds/mirae-asset-large-cap-fund-direct-growth",
  "scheme_name": "Mirae Asset Large Cap Fund",
  "section_heading": "Expense Ratio",
  "chunk_index": 3,
  "content": "The expense ratio of Mirae Asset Large Cap Fund Direct Plan is 0.53%...",
  "token_count": 412,
  "last_crawled_date": "2026-04-17",
  "doc_type": "groww_page",
  "embedding_model": "BAAI/bge-small-en-v1.5",
  "embedding_version": "2026-04",
  "pipeline_run_id": "gh_run_123456789"
}
```

### 3.4 Financial Domain — Special Handling

| Content Type | Chunking Rule |
|---|---|
| NAV table | Atomic single chunk |
| Expense ratio table | Atomic single chunk |
| Exit load table | Atomic single chunk |
| SIP/lump sum minimums | Keep in same chunk as surrounding paragraph |
| ELSS lock-in info | Must not be split across chunks |
| Benchmark index | Keep within scheme overview chunk |
| Riskometer classification | Keep within scheme overview chunk |

---

## 4. Embedding Architecture — bge-small-en-v1.5

### 4.1 Model Details

| Property | Value |
|---|---|
| Model ID | `BAAI/bge-small-en-v1.5` |
| Library | `sentence-transformers` |
| Vector dimension | **384** |
| Max input tokens | 512 |
| Model size | ~33 MB |
| Requires GPU | No — CPU inference is fast enough for 36 URLs × ~10 chunks |
| Cost | Free — fully local, no API |
| Distance metric | Cosine (use `normalize_embeddings=True` for dot product = cosine) |

### 4.2 BGE Input Prefix — Critical

BGE models require a task prefix for **retrieval** quality. Apply this prefix to all chunk texts during embedding:

```python
# During ingestion (document embedding):
texts_to_embed = [f"Represent this sentence: {chunk['content']}" for chunk in batch]

# During query (retrieval embedding):
query_text = f"Represent this sentence: {user_query}"
```

> **Why:** BGE-small is a bi-encoder trained with this prefix for asymmetric retrieval. Skipping the prefix degrades Recall@3 noticeably.

### 4.3 Implementation

```python
from sentence_transformers import SentenceTransformer

# Load model (downloads on first run, cached after)
model = SentenceTransformer("BAAI/bge-small-en-v1.5")

def embed_chunks(chunks: list[dict], batch_size: int = 32) -> list[list[float]]:
    texts = [f"Represent this sentence: {c['content']}" for c in chunks]
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,   # L2 normalize → cosine via dot product
        show_progress_bar=True
    )
    return embeddings.tolist()

def embed_query(query: str) -> list[float]:
    return model.encode(
        f"Represent this sentence: {query}",
        normalize_embeddings=True
    ).tolist()
```

### 4.4 Batching & Performance

| Scenario | Expected time (CPU) |
|---|---|
| Full ingestion (36 URLs × ~10 chunks = ~360 chunks) | ~60–90 seconds |
| Incremental (only changed chunks, avg ~30/day) | ~5–10 seconds |
| Single query embedding (retrieval) | < 50ms |

**Batch size:** 32 — safe for CPU RAM. Do not increase without testing.

### 4.5 Model Version Pinning

Record `embedding_model` and `embedding_version` in every chunk payload and `ingestion_manifest.json`. If the model is ever changed or updated, **all vectors must be re-embedded** — partial updates will cause dimension/distribution mismatch in retrieval.

---

## 5. ChromaDB Schema

### 5.1 Collection Configuration

```python
import chromadb

client = chromadb.PersistentClient(path="data/chroma_db")

collection = client.get_or_create_collection(
    name="mutual_fund_faq",
    metadata={"hnsw:space": "cosine"}   # cosine distance
)
```

### 5.2 Upsert Schema

```python
collection.upsert(
    ids=[chunk["chunk_id"]],
    embeddings=[embedding_vector],        # list[float], len=384
    documents=[chunk["content"]],
    metadatas=[{
        "source_url":        chunk["source_url"],
        "scheme_name":       chunk["scheme_name"],
        "section_heading":   chunk["section_heading"],
        "doc_type":          chunk["doc_type"],
        "last_crawled_date": chunk["last_crawled_date"],
        "chunk_index":       chunk["chunk_index"],
        "embedding_model":   chunk["embedding_model"],
    }]
)
```

### 5.3 Query Schema

```python
results = collection.query(
    query_embeddings=[embed_query(user_query)],
    n_results=10,
    where={"scheme_name": "Mirae Asset Large Cap Fund"},  # optional metadata filter
    include=["documents", "metadatas", "distances"]
)
```

### 5.4 Delete Stale Vectors

```python
# Called for DELETED chunks from change detection
collection.delete(ids=deleted_chunk_ids)
```

---

## 6. Change Detection Logic

```
For each URL in urls.yaml:
  1. Scrape + normalize → get new doc_hash
  2. Load ingestion_manifest.json (previous run)
  3. For each chunk in new chunks.jsonl:
       IF chunk_id NOT IN manifest.chunk_ids:
           → NEW → embed + upsert
       ELIF manifest[chunk_id].doc_hash != current doc_hash:
           → UPDATED → re-embed + upsert
       ELSE:
           → UNCHANGED → skip (no embed call)
  4. For each chunk_id IN manifest but NOT in new chunks:
       → DELETED → collection.delete(id)
  5. Write new ingestion_manifest.json
```

**Idempotency guarantee:** Running the same pipeline twice without content changes results in zero embed calls and zero upsert operations.

---

## 7. Ingestion Manifest Schema

`data/ingestion_manifest.json` — written at end of every successful pipeline run:

```json
{
  "run_id": "gh_run_123456789",
  "pipeline_run_at": "2026-04-17T03:45:00Z",
  "embedding_model": "BAAI/bge-small-en-v1.5",
  "embedding_version": "2026-04",
  "counts": {
    "new": 12,
    "updated": 3,
    "unchanged": 345,
    "deleted": 1,
    "total_in_collection": 359
  },
  "urls_processed": 36,
  "urls_failed": 0,
  "chunk_ids": ["sha256...", "sha256...", "..."],
  "doc_hashes": {
    "https://groww.in/mutual-funds/mirae-asset-large-cap-fund-direct-growth": "abc123..."
  }
}
```

---

## 8. Artifacts Per Pipeline Run

| Artifact | Location | Producer | Consumer |
|---|---|---|---|
| `cleaned_docs.jsonl` | `data/` | Phase 4.0 Scraper | Phase 4.1 Chunker |
| `normalized_docs.jsonl` | `data/` | Stage A | Stage B |
| `chunks.jsonl` | `data/` | Stage B | Stage C + embed |
| `chunk_diff.json` | `data/` | Stage C | Stage D |
| `ingestion_manifest.json` | `data/` | Stage E | Next run Stage C |
| `data/chroma_db/` | `data/chroma_db/` | Stage E | Phase 5 Retriever |

---

## 9. GitHub Actions Orchestration

```yaml
# .github/workflows/ingestion-scheduler.yml (relevant jobs)

jobs:
  scrape_documents:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install scraper deps
        run: pip install requests beautifulsoup4 playwright
      - name: Run scraper
        run: python ingestion/scraper.py
        env:
          URLS_YAML: data/urls.yaml
      - name: Upload scrape artifact
        uses: actions/upload-artifact@v4
        with:
          name: scrape-output-${{ github.run_id }}
          path: data/cleaned_docs.jsonl

  chunk_and_embed:
    needs: scrape_documents
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Download scrape artifact
        uses: actions/download-artifact@v4
        with:
          name: scrape-output-${{ github.run_id }}
          path: data/
      - name: Install chunking + embedding deps
        run: pip install sentence-transformers chromadb tiktoken rank-bm25
      - name: Run chunker
        run: python ingestion/chunker.py
      - name: Run embedder + upsert
        run: python ingestion/embedder.py
        env:
          CHROMA_PERSIST_PATH: data/chroma_db
      - name: Upload updated ChromaDB + manifest
        uses: actions/upload-artifact@v4
        with:
          name: chroma-output-${{ github.run_id }}
          path: |
            data/chroma_db/
            data/ingestion_manifest.json
```

> **Note on GitHub Actions artifact access by Render backend:** The ChromaDB collection must be persisted to a location accessible by the Render backend. Options: (a) commit `data/chroma_db/` to a private Git repo after ingestion, (b) upload to S3/GCS and pull on Render startup, (c) run ingestion directly on Render via `POST /api/ingest` trigger from GitHub Actions webhook.

---

## 10. Summary

| Stage | Responsibility |
|---|---|
| **Normalize** | Clean HTML artifacts, compute doc_hash |
| **Chunk** | Section-aware splits, table atomicity, deterministic chunk_id |
| **Diff** | Skip unchanged chunks to minimize compute |
| **Embed** | Local bge-small-en-v1.5, batch_size=32, normalize=True, BGE prefix required |
| **Upsert** | Idempotent write to ChromaDB, delete stale vectors, write manifest |