# RAG Architecture — Mutual Fund FAQ Assistant

> **Project:** Facts-Only Mutual Fund FAQ Assistant — Mirae Asset (Groww Context)
> **Version:** 2.0
> **Date:** April 2026
> **Embedding Model:** BAAI/bge-small-en-v1.5 (local, no API cost)
> **LLM:** Groq (llama3-8b-8192)
> **Vector Store:** ChromaDB (local persistent)
> **Deployment:** GitHub Actions (Scheduler) · Render (Backend) · Vercel (Frontend)

---

## Pre-Build Checklist (Complete Before Writing Any Code)

- [ ] `docs/problem-statement.md` is present and matches scope
- [ ] `docs/rag-architecture.md` (this file) is reviewed and locked
- [ ] `docs/chunking-embedding-architecture.md` is reviewed and locked
- [ ] All 36 Groww URLs are reachable and returning expected HTML
- [ ] `.env.example` lists all required keys (Groq API key only — embedding is local)
- [ ] ChromaDB local persistence path is defined in `config.yaml`
- [ ] GitHub Actions secrets are documented (`GROQ_API_KEY`, `RENDER_DEPLOY_HOOK`)
- [ ] Refusal keyword list is reviewed and covers all advisory patterns

---

## 1. Architecture Overview

The system follows a **Retrieval-Augmented Generation (RAG)** pattern. Every answer is grounded exclusively in scraped Groww pages for Mirae Asset mutual fund schemes. The pipeline has **two major flows**:

| # | Flow | Components | Responsibility |
|---|---|---|---|
| 1 | **Ingestion Flow** (Offline/Scheduled) | GitHub Actions → Scraping → Chunking → Embedding (bge-small) → ChromaDB | Daily automated pipeline that scrapes Groww URLs, chunks content, and stores local vectors |
| 2 | **Retrieval + Generation Flow** (Online) | Query Guard → Retriever → Re-ranker → Groq LLM → Post-processor | Real-time query handling with citation-backed, facts-only answers |

**Key design constraints:**
- No OpenAI or paid embedding API — `bge-small-en-v1.5` runs locally via `sentence-transformers`
- LLM is Groq (`llama3-8b-8192`) — free tier, fast inference
- ChromaDB runs as a **local persistent collection** — no cloud dependency
- No PII collected or stored — stateless query processing except thread session state
- Every response: ≤ 3 sentences · exactly 1 citation · "Last updated from sources: <date>" footer

---

## 2. System Architecture Diagram

### Flow 1 — Ingestion Pipeline (Offline / Scheduled Daily @ 9:15 AM IST)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    INGESTION FLOW  (Runs Daily @ 9:15 AM IST)                │
│                                                                              │
│  ┌──────────────┐                                                            │
│  │  SCHEDULER   │  GitHub cron: "45 3 * * *" (UTC = 9:15 AM IST)          │
│  │  (GitHub     │  Triggers: automatic schedule + workflow_dispatch          │
│  │   Actions)   │                                                            │
│  └──────┬───────┘                                                            │
│         │ triggers                                                           │
│         ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐            │
│  │                    SCRAPING SERVICE                           │            │
│  │                                                              │            │
│  │  urls.yaml (36 Groww URLs) ──▶ requests + BeautifulSoup     │            │
│  │                                     │                        │            │
│  │                              [JS pages: Playwright]          │            │
│  │                                     │                        │            │
│  │                              Raw HTML → Cleaned Text         │            │
│  │                              + SHA-256 content hash          │            │
│  │                              + metadata {source_url,         │            │
│  │                                scheme_name, scrape_date}     │            │
│  │                              saved to data/raw/              │            │
│  └──────────────────────────────┬───────────────────────────────┘            │
│                                 │ cleaned_docs.jsonl                         │
│                                 ▼                                            │
│  ┌──────────────────────────────────────────────────────────────┐            │
│  │                  INGESTION COMPONENT                          │            │
│  │                                                              │            │
│  │  Stage A: Normalize text + compute doc_hash                  │            │
│  │       │                                                      │            │
│  │       ▼                                                      │            │
│  │  Stage B: Chunking (section-aware + recursive fallback)      │            │
│  │       │  chunk_size ≈ 500 tokens · overlap ≈ 50 tokens       │            │
│  │       ▼                                                      │            │
│  │  Stage C: Change detection (diff vs ingestion_manifest.json) │            │
│  │       │  NEW / UPDATED → embed · UNCHANGED → skip           │            │
│  │       ▼                                                      │            │
│  │  Stage D: Batch embed with bge-small-en-v1.5 (local)        │            │
│  │       │  batch_size = 32 · 384-dim vectors                   │            │
│  │       ▼                                                      │            │
│  │  Stage E: Upsert into ChromaDB (local persistent)            │            │
│  │       │  collection: mutual_fund_faq                         │            │
│  │       ▼                                                      │            │
│  │  Write ingestion_manifest.json (run_id, counts, timestamps)  │            │
│  └──────────────────────────────┬───────────────────────────────┘            │
│                                 │                                            │
│                                 ▼                                            │
│                      ┌─────────────────────┐                                 │
│                      │   ChromaDB          │                                 │
│                      │   (local persist)   │                                 │
│                      │   384-dim vectors   │                                 │
│                      │   cosine similarity │                                 │
│                      └─────────────────────┘                                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Flow 2 — Retrieval + Generation (Online / Real-time)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                  RETRIEVAL + GENERATION FLOW (Real-time)                     │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         NEXT.JS FRONTEND                                │ │
│  │  Welcome message · 3 example questions · "Facts-only. No advice." banner│ │
│  │  Thread sidebar (multiple independent sessions) · Dark theme             │ │
│  └────────────────────────────────┬────────────────────────────────────────┘ │
│                                   │ User Query                               │
│                                   ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    FASTAPI BACKEND (Render)                            │  │
│  │                                                                        │  │
│  │  ┌──────────────┐   ADVISORY/OOScope ──▶ Refusal + AMFI/SEBI link     │  │
│  │  │  Query Guard │                                                      │  │
│  │  │  (Intent     │   FACTUAL ──▶                                        │  │
│  │  │  Classifier) │          │                                           │  │
│  │  └──────────────┘          ▼                                           │  │
│  │                   ┌──────────────────┐                                 │  │
│  │                   │  Query Preprocess │                                 │  │
│  │                   │  expand acronyms  │                                 │  │
│  │                   │  (SIP/ELSS/NAV)   │                                 │  │
│  │                   └────────┬─────────┘                                 │  │
│  │                            │                                           │  │
│  │                            ▼                                           │  │
│  │                   ┌──────────────────┐                                 │  │
│  │                   │  bge-small-en    │  embed query → 384-dim vector   │  │
│  │                   │  (local model)   │                                 │  │
│  │                   └────────┬─────────┘                                 │  │
│  │                            │                                           │  │
│  │               ┌────────────┴──────────────┐                           │  │
│  │               ▼                           ▼                           │  │
│  │  ┌────────────────────┐   ┌────────────────────┐                      │  │
│  │  │  Dense Retrieval   │   │  Sparse Retrieval  │                      │  │
│  │  │  ChromaDB cosine   │   │  BM25 (rank_bm25)  │                      │  │
│  │  │  Top-K = 10        │   │  Top-K = 10        │                      │  │
│  │  └──────────┬─────────┘   └──────────┬─────────┘                      │  │
│  │             └──────────┬─────────────┘                                 │  │
│  │                        ▼                                               │  │
│  │             ┌─────────────────────┐                                    │  │
│  │             │  RRF Hybrid Fusion  │  Top-5                             │  │
│  │             └──────────┬──────────┘                                    │  │
│  │                        │                                               │  │
│  │                        ▼                                               │  │
│  │             ┌─────────────────────┐                                    │  │
│  │             │  Cross-Encoder      │  Top-3 final chunks                │  │
│  │             │  Re-Ranker          │  (ms-marco-MiniLM-L-6-v2)          │  │
│  │             └──────────┬──────────┘                                    │  │
│  │                        │                                               │  │
│  │                        ▼                                               │  │
│  │             ┌─────────────────────┐                                    │  │
│  │             │  Groq LLM           │  llama3-8b-8192                    │  │
│  │             │  (llama3-8b-8192)   │  System prompt + chunks + query    │  │
│  │             └──────────┬──────────┘                                    │  │
│  │                        │                                               │  │
│  │                        ▼                                               │  │
│  │             ┌─────────────────────┐                                    │  │
│  │             │  Post-Processor     │  ≤3 sentences · 1 citation ·       │  │
│  │             │                     │  footer · PII scan · advisory scan │  │
│  │             └──────────┬──────────┘                                    │  │
│  │                        │                                               │  │
│  │                        ▼                                               │  │
│  │             ┌─────────────────────┐                                    │  │
│  │             │  Session Store      │  In-memory dict (dev)              │  │
│  │             │  (Thread State)     │  Thread isolation — no cross-share  │  │
│  │             └──────────┬──────────┘                                    │  │
│  └────────────────────────┼──────────────────────────────────────────────┘  │
│                           │ Response                                         │
│                           ▼                                                  │
│                  Next.js Frontend renders:                                   │
│                  Answer · Source link · "Last updated: <date>" footer        │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Corpus Definition

**AMC:** Mirae Asset · **Source:** Groww pages only · **PDFs:** Not in scope (v1.0)

### 3.1 URL List (36 Groww URLs)

| Category | # | Fund Name | URL |
|---|---|---|---|
| **Equity / Core** | 1 | Mirae Asset Large Cap Fund | https://groww.in/mutual-funds/mirae-asset-large-cap-fund-direct-growth |
| | 2 | Mirae Asset Large & Midcap Fund | https://groww.in/mutual-funds/mirae-asset-large-midcap-fund-direct-growth |
| | 3 | Mirae Asset Midcap Fund | https://groww.in/mutual-funds/mirae-asset-midcap-fund-direct-growth |
| | 4 | Mirae Asset Small Cap Fund | https://groww.in/mutual-funds/mirae-asset-small-cap-fund-direct-growth |
| | 5 | Mirae Asset Multicap Fund | https://groww.in/mutual-funds/mirae-asset-multicap-fund-direct-growth |
| | 6 | Mirae Asset Flexi Cap Fund | https://groww.in/mutual-funds/mirae-asset-flexi-cap-fund-direct-growth |
| | 7 | Mirae Asset ELSS Tax Saver Fund | https://groww.in/mutual-funds/mirae-asset-elss-tax-saver-fund-direct-growth |
| | 8 | Mirae Asset Aggressive Hybrid Fund | https://groww.in/mutual-funds/mirae-asset-aggressive-hybrid-fund-direct-growth |
| | 9 | Mirae Asset Equity Savings Fund | https://groww.in/mutual-funds/mirae-asset-equity-savings-fund-direct-growth |
| | 10 | Mirae Asset Balanced Advantage Fund | https://groww.in/mutual-funds/mirae-asset-balanced-advantage-fund-direct-growth |
| **Sectoral** | 11 | Mirae Asset Great Consumer Fund | https://groww.in/mutual-funds/mirae-asset-great-consumer-fund-direct-growth |
| | 12 | Mirae Asset Healthcare Fund | https://groww.in/mutual-funds/mirae-asset-healthcare-fund-direct-growth |
| | 13 | Mirae Asset Banking & Financial Services Fund | https://groww.in/mutual-funds/mirae-asset-banking-and-financial-services-fund-direct-growth |
| | 14 | Mirae Asset Infrastructure Fund | https://groww.in/mutual-funds/mirae-asset-infrastructure-fund-direct-growth |
| **Index / Passive** | 15 | Mirae Asset Nifty 50 Index Fund | https://groww.in/mutual-funds/mirae-asset-nifty-50-index-fund-direct-growth |
| | 16 | Mirae Asset Nifty LargeMidcap 250 | https://groww.in/mutual-funds/mirae-asset-nifty-largemidcap-250-index-fund-direct-growth |
| | 17 | Mirae Asset Nifty Total Market | https://groww.in/mutual-funds/mirae-asset-nifty-total-market-index-fund-direct-growth |
| | 18 | Mirae Asset Nifty MidSmallcap400 ETF FoF | https://groww.in/mutual-funds/mirae-asset-nifty-midsmallcap400-momentum-quality-100-etf-fof-direct-growth |
| | 19 | Mirae Asset Nifty India New Age ETF FoF | https://groww.in/mutual-funds/mirae-asset-nifty-india-new-age-consumption-etf-fof-direct-growth |
| | 20 | Mirae Asset NYSE FANG+ ETF FoF | https://groww.in/mutual-funds/mirae-asset-nyse-fang-plus-etf-fof-direct-growth |
| | 21 | Mirae Asset Hang Seng TECH ETF FoF | https://groww.in/mutual-funds/mirae-asset-hang-seng-tech-etf-fof-direct-growth |
| | 22 | Mirae Asset S&P 500 Top 50 ETF FoF | https://groww.in/mutual-funds/mirae-asset-s-and-p-500-top-50-etf-fof-direct-growth |
| | 23 | Mirae Asset Global X AI & Tech ETF FoF | https://groww.in/mutual-funds/mirae-asset-global-x-artificial-intelligence-technology-etf-fof-direct-growth |
| **Debt** | 24 | Mirae Asset Liquid Fund | https://groww.in/mutual-funds/mirae-asset-liquid-fund-direct-growth |
| | 25 | Mirae Asset Money Market Fund | https://groww.in/mutual-funds/mirae-asset-money-market-fund-direct-growth |
| | 26 | Mirae Asset Short Duration Fund | https://groww.in/mutual-funds/mirae-asset-short-duration-fund-direct-growth |
| | 27 | Mirae Asset Low Duration Fund | https://groww.in/mutual-funds/mirae-asset-low-duration-fund-direct-growth |
| | 28 | Mirae Asset Ultra Short Duration Fund | https://groww.in/mutual-funds/mirae-asset-ultra-short-duration-fund-direct-growth |
| | 29 | Mirae Asset Dynamic Bond Fund | https://groww.in/mutual-funds/mirae-asset-dynamic-bond-fund-direct-growth |
| | 30 | Mirae Asset Corporate Bond Fund | https://groww.in/mutual-funds/mirae-asset-corporate-bond-fund-direct-growth |
| | 31 | Mirae Asset Banking & PSU Fund | https://groww.in/mutual-funds/mirae-asset-banking-and-psu-fund-direct-growth |
| **Target Maturity** | 32 | Mirae Asset CRISIL IBX FinServ 9-12M | https://groww.in/mutual-funds/mirae-asset-crisil-ibx-financial-services-9-12-months-debt-index-fund-direct-growth |
| | 33 | Mirae Asset CRISIL IBX Gilt Apr 2033 | https://groww.in/mutual-funds/mirae-asset-crisil-ibx-gilt-index-april-2033-index-fund-direct-growth |
| | 34 | Mirae Asset Nifty SDL Jun 2027 | https://groww.in/mutual-funds/mirae-asset-nifty-sdl-jun-2027-index-fund-direct-growth |
| | 35 | Mirae Asset Nifty SDL Jun 2028 | https://groww.in/mutual-funds/mirae-asset-nifty-sdl-june-2028-index-fund-direct-growth |
| | 36 | Mirae Asset Nifty AAA PSU+SDL Apr 2026 | https://groww.in/mutual-funds/mirae-asset-nifty-aaa-psu-bond-plus-sdl-apr-2026-50-50-index-fund-direct-growth |

---

## 4. Phase-by-Phase Breakdown

### Phase 4.0 — Scheduler & Scraping Service

**Objective:** Automate daily data refresh. Trigger a 3-job ingestion pipeline at 9:15 AM IST every day via GitHub Actions. Also supports `workflow_dispatch` for manual on-demand runs.

**Schedule:** `45 3 * * *` (UTC) = 9:15 AM IST

**Pipeline jobs (defined in `.github/workflows/ingestion-scheduler.yml`):**

| Job | Depends On | Inputs | Outputs |
|---|---|---|---|
| `scrape_documents` | — | `data/urls.yaml` | `cleaned_docs.jsonl` (artifact) |
| `chunk_documents` | `scrape_documents` | `cleaned_docs.jsonl` (artifact) | `chunks.jsonl` (artifact) |
| `embed_and_upsert` | `chunk_documents` | `chunks.jsonl` + `ingestion_manifest.json` (artifact) | updated `chroma_db/` + `ingestion_manifest.json` (artifact) |

**Components:**
- `.github/workflows/ingestion-scheduler.yml` — pipeline definition
- `ingestion/scraper.py` — `requests` + `BeautifulSoup` for static pages; `Playwright` for JS-rendered pages
- `ingestion/chunker.py` — section-aware chunker
- `ingestion/embedder.py` — bge-small-en-v1.5 batch embedder + ChromaDB upsert
- `data/urls.yaml` — source of truth for all 36 Groww URLs
- `data/raw/` — timestamped raw HTML files

**Exit criteria:**
- [ ] GitHub Actions cron triggers successfully at 9:15 AM IST (`45 3 * * *`)
- [ ] `workflow_dispatch` manual trigger works from the Actions UI
- [ ] All 36 URLs scraped without error; raw HTML saved to `data/raw/`
- [ ] Cleaned text + metadata written to `cleaned_docs.jsonl`
- [ ] SHA-256 content hash computed per document
- [ ] `cleaned_docs.jsonl` uploaded as GitHub Actions artifact and downloaded by `chunk_documents`
- [ ] `chunks.jsonl` uploaded as artifact and downloaded by `embed_and_upsert`
- [ ] `ingestion_manifest.json` from previous run downloaded at start of `embed_and_upsert` for diff
- [ ] `ingestion_manifest.json` written and uploaded at end of `embed_and_upsert` for next run
- [ ] Scrape run logged with URL, status, hash, timestamp
- [ ] Test: trigger scheduler manually via `workflow_dispatch` and verify all 3 jobs turn green

---

### Phase 4.1 — Chunking

**Objective:** Split cleaned documents into retrieval-optimal chunks with rich metadata.

**Components:**
- `ingestion/chunker.py`
- Strategy: section-aware split on H1/H2/H3 → tables kept atomic → recursive token fallback
- Parameters: `chunk_size=500`, `overlap=50`
- Output: `data/chunks.jsonl`

**Exit criteria:**
- [ ] Chunks written to `chunks.jsonl`
- [ ] Each chunk has `chunk_id`, `source_url`, `scheme_name`, `section_heading`, `chunk_index`, `content`, `last_crawled_date`
- [ ] No chunk exceeds 600 tokens
- [ ] Tables are kept as single chunks where possible
- [ ] Test: run `python ingestion/chunker.py` and verify chunk count and metadata completeness

---

### Phase 4.2 — Embedding with bge-small-en-v1.5

**Objective:** Generate 384-dim embeddings locally using `bge-small-en-v1.5`. No API key required.

**Model:** `BAAI/bge-small-en-v1.5` via `sentence-transformers`
**Dimension:** 384
**Batch size:** 32

**Components:**
- `ingestion/embedder.py`
- Model loaded via `SentenceTransformer("BAAI/bge-small-en-v1.5")`
- Change detection: diff `chunk_id` list vs `ingestion_manifest.json` — only NEW/UPDATED chunks re-embedded

**Exit criteria:**
- [ ] `bge-small-en-v1.5` loads from HuggingFace (first run) or local cache
- [ ] Embeddings generated in batches of 32 without OOM errors
- [ ] Change detection skips UNCHANGED chunks
- [ ] `embedding_model: "BAAI/bge-small-en-v1.5"` recorded in manifest
- [ ] Test: embed 5 test chunks and verify vector dimensions are 384

---

### Phase 4.3 — ChromaDB Vector Upsert

**Objective:** Store embeddings in a local persistent ChromaDB collection.

**Collection:** `mutual_fund_faq`
**Distance metric:** cosine
**Persistence:** `data/chroma_db/` (local filesystem)

**Components:**
- `ingestion/vector_store.py`
- ChromaDB client: `chromadb.PersistentClient(path="data/chroma_db")`
- Upsert by `chunk_id` (idempotent)
- Delete stale vectors for DELETED chunks

**Exit criteria:**
- [ ] Collection `mutual_fund_faq` created and persistent across restarts
- [ ] Upsert is idempotent — re-running does not duplicate vectors
- [ ] DELETED chunks removed from collection
- [ ] `ingestion_manifest.json` written with: `run_id`, `new_count`, `updated_count`, `deleted_count`, `unchanged_count`, `timestamp`
- [ ] Test: upsert 10 chunks, restart Python, verify collection still has 10 vectors

---

### Phase 5 — Retrieval Service

**Objective:** Hybrid retrieval combining dense (ChromaDB cosine) and sparse (BM25) search.

**Components:**
- `backend/core/retriever.py`
- Dense: ChromaDB query with `bge-small-en-v1.5` query embedding, Top-K=10
- Sparse: `rank_bm25` BM25 index built from chunk contents, Top-K=10
- Fusion: Reciprocal Rank Fusion (RRF) → Top-5
- Re-ranker: `cross-encoder/ms-marco-MiniLM-L-6-v2` → Top-3

**Exit criteria:**
- [ ] Dense retrieval returns Top-10 results with metadata
- [ ] BM25 index built from `chunks.jsonl` at backend startup
- [ ] RRF fusion combines both lists correctly
- [ ] Cross-encoder re-ranks to Top-3 chunks
- [ ] Similarity threshold: chunks below 0.70 cosine score filtered out
- [ ] Test: query "expense ratio Mirae Asset Large Cap" → verify returned chunks contain expense ratio data

---

### Phase 6 — Groq LLM Integration & Prompt Layer

**Objective:** Generate ≤3 sentence, citation-backed factual answers using Groq.

**Model:** `llama3-8b-8192` via Groq API
**API Key:** `GROQ_API_KEY` in `.env`

**System Prompt:**
```
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
```

**Components:**
- `backend/core/generator.py`
- `backend/core/query_guard.py` — intent classification (FACTUAL / ADVISORY / OUT_OF_SCOPE)
- Prompt template: system prompt + user query + 3 retrieved chunks with metadata

**Exit criteria:**
- [ ] Groq API key loaded from `.env` (never hardcoded)
- [ ] Query guard correctly classifies: factual queries proceed, advisory queries return refusal
- [ ] LLM responses are consistently ≤ 3 sentences
- [ ] Refusal response includes AMFI or SEBI educational link
- [ ] Test: run 5 factual + 3 advisory queries, verify correct classification and response format

---

### Phase 7 — Post-Processor & Guardrails

**Objective:** Validate every LLM response before it reaches the user.

**Components:**
- `backend/core/post_processor.py`

**Validation pipeline:**
1. **Sentence count** — truncate if > 3 sentences
2. **Citation validator** — verify URL exists in `urls.yaml` whitelist; inject from metadata if absent
3. **Footer injector** — append "Last updated from sources: <date>"
4. **PII scanner** — block response if PAN / Aadhaar / phone / email / account number detected
5. **Advisory content filter** — scan for "recommend", "should invest", "better than", "returns will" → replace with refusal

**Exit criteria:**
- [ ] All 5 validation steps run on every response
- [ ] PII scanner blocks responses with synthetic test PAN (e.g. ABCDE1234F)
- [ ] Advisory language filter catches at least: "recommend", "should invest", "which is better"
- [ ] Citation URL is always from the `urls.yaml` whitelist
- [ ] Test: inject an advisory phrase into mock LLM output → verify it is caught and replaced

---

### Phase 8 — FastAPI Backend & Thread Management

**Objective:** REST API with multi-thread conversation support. No memory sharing between threads.

**Framework:** FastAPI
**Session store:** In-memory dict (dev) — thread isolation enforced

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/threads` | Create a new conversation thread |
| `GET` | `/api/threads` | List all active threads |
| `DELETE` | `/api/threads/{thread_id}` | Delete a thread and its history |
| `POST` | `/api/threads/{thread_id}/messages` | Send query, get response |
| `GET` | `/api/threads/{thread_id}/messages` | Get full message history for thread |
| `POST` | `/api/ingest` | Manually trigger ingestion (admin) |
| `GET` | `/api/health` | Health check |

**Thread isolation:** Each thread has its own `{thread_id, messages[], created_at}`. The LLM prompt uses last 3 turns of that thread's history only. Zero cross-thread state.

**Request / Response schema:**
```json
// POST /api/threads/{thread_id}/messages — Request
{ "content": "What is the expense ratio of Mirae Asset Large Cap Fund?" }

// Response
{
  "thread_id": "uuid",
  "message_id": "uuid",
  "role": "assistant",
  "content": "The expense ratio of Mirae Asset Large Cap Fund Direct Plan is 0.53%. The Regular Plan expense ratio is 1.60%.",
  "citation": "https://groww.in/mutual-funds/mirae-asset-large-cap-fund-direct-growth",
  "last_updated": "2026-04-15",
  "timestamp": "2026-04-17T09:00:00Z",
  "is_refusal": false
}
```

**Exit criteria:**
- [ ] All 7 endpoints operational
- [ ] Two threads can run simultaneously with no shared state
- [ ] Thread deletion removes message history
- [ ] `/api/health` returns 200
- [ ] Test: create 2 threads, send different queries to each, verify histories are independent

---

### Phase 9 — Next.js Frontend

**Objective:** Dark-theme chat UI with multi-thread sidebar and disclaimer.

**Tech:** Next.js (App Router) · Tailwind CSS · deployed on Vercel

**Required UI components:**
- `ThreadSidebar` — list threads, create new, switch, delete
- `ChatWindow` — message list with user/assistant bubbles
- `MessageBubble` — renders answer + citation link + "Last updated" footer
- `DisclaimerBanner` — always visible: "Facts-only. No investment advice."
- Welcome screen with 3 example questions:
  1. "What is the expense ratio of Mirae Asset Large Cap Direct?"
  2. "What is the exit load for Mirae Asset ELSS Tax Saver Fund?"
  3. "What is the minimum SIP amount for Mirae Asset Flexi Cap Fund?"

**Exit criteria:**
- [ ] New thread created on page load or sidebar button
- [ ] Messages sent to `/api/threads/{id}/messages` and response rendered
- [ ] Citation link opens in new tab
- [ ] "Last updated from sources" footer visible on every assistant message
- [ ] Disclaimer banner visible at all times
- [ ] Thread switch preserves individual histories
- [ ] Test: open two browser tabs, create threads in each, verify independent histories

---

## 5. Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Scheduler | GitHub Actions | `45 3 * * *` cron · `workflow_dispatch` manual trigger |
| Scraping | `requests` + `BeautifulSoup` · `Playwright` | Static + JS-rendered pages |
| Chunking | Custom Python + `tiktoken` | Section-aware + recursive fallback |
| Embedding | `sentence-transformers` + `BAAI/bge-small-en-v1.5` | Local, no API cost, 384-dim |
| Vector Store | `chromadb` (PersistentClient) | Local, `data/chroma_db/` |
| Sparse Retrieval | `rank_bm25` | BM25 index at startup |
| Re-ranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Local cross-encoder |
| LLM | Groq `llama3-8b-8192` | Free tier · fast inference |
| Backend | FastAPI (Python 3.11+) | Deployed on Render |
| Frontend | Next.js + Tailwind CSS | Deployed on Vercel |
| Session Store | In-memory dict | Thread isolation, dev scope |

---

## 6. Dependency Graph

```
Phase 4.0 (Scrape) → Phase 4.1 (Chunk) → Phase 4.2 (Embed) → Phase 4.3 (ChromaDB)
                                                                        ↓
                                                          Phase 5 (Retrieval) can prototype
                                                          independently with dummy vectors
                                                                        ↓
                                                          Phase 6 (Groq LLM) — needs Phase 5 output
                                                                        ↓
                                                          Phase 7 (Post-Processor) — wraps Phase 6
                                                                        ↓
                                                          Phase 8 (FastAPI) — wraps Phases 5-7
                                                                        ↓
                                                          Phase 9 (Frontend) — consumes Phase 8 API
```

> **Note:** Phases 4.0–4.3 can be tested entirely offline. Phase 5 onwards requires the ChromaDB collection to be populated.

---

## 7. Refusal Handling

**Trigger keywords / patterns (LLM-classified + keyword fallback):**
- "should I invest", "is it good to invest", "recommend", "which is better", "safe to invest"
- "will returns be", "will it grow", "compare funds", "outperforms"
- "should I switch", "is this fund good"

**Refusal response template:**
```
I'm a facts-only assistant and cannot provide investment advice, recommendations,
or opinions. For guidance on mutual fund investing, please visit the AMFI Investor
Education portal at https://www.amfiindia.com/investor-corner/knowledge-center.

Facts-only. No investment advice.
```

---

## 8. Security & Compliance

| Check | Implementation |
|---|---|
| No PII collected | No user auth, no account numbers, no PAN/Aadhaar stored |
| PII scanner | Regex patterns on both INPUT and OUTPUT for PAN, Aadhaar, phone, email |
| API key security | `GROQ_API_KEY` in `.env` only · never in prompts · never committed to Git |
| Source whitelist | Citation URLs validated against `urls.yaml` |
| No hallucination | Post-processor fallback if retrieval confidence < 0.70 |
| Rate limiting | 30 queries/min per thread (FastAPI middleware) |
| Input sanitization | Strip HTML tags, SQL patterns, prompt injection attempts |

---

## 9. Deployment Architecture

```
GitHub Actions (Scheduler)
        │ daily @ 9:15 AM IST
        │ triggers ingestion pipeline
        ▼
Render (Backend — FastAPI)
        │ REST API
        │ serves /api/* endpoints
        ▼
Vercel (Frontend — Next.js)
        │ static + SSR
        │ calls Render backend
        ▼
User Browser
```

**Environment variables required:**

| Variable | Where | Description |
|---|---|---|
| `GROQ_API_KEY` | Render + GitHub Actions | Groq LLM API key |
| `CHROMA_PERSIST_PATH` | Render | Path to ChromaDB local storage |
| `NEXT_PUBLIC_API_URL` | Vercel | Backend URL (Render service URL) |
| `RENDER_DEPLOY_HOOK` | GitHub Actions secrets | Trigger Render redeploy after ingestion |

---

## 10. GitHub Actions Scheduler Architecture

### 10.1 Trigger Configuration

```yaml
# .github/workflows/ingestion-scheduler.yml

on:
  schedule:
    - cron: "45 3 * * *"   # 9:15 AM IST daily (UTC 03:45)
  workflow_dispatch:       # manual trigger from GitHub Actions UI
    inputs:
      force_full_rerun:
        description: "Set true to re-embed ALL chunks (ignore manifest diff)"
        required: false
        default: "false"
```

> **IST → UTC:** India Standard Time is UTC+5:30. 9:15 AM IST = 03:45 UTC → cron `45 3 * * *`.

---

### 10.2 Job Dependency Graph

```
┌──────────────────────────────────────────────────────────────────────────────┐
│              GITHUB ACTIONS — INGESTION PIPELINE (3 Jobs)                    │
│                                                                              │
│  Trigger: cron "45 3 * * *" (9:15 AM IST) · workflow_dispatch               │
│                                                                              │
│  ┌─────────────────────────────────────────────┐                             │
│  │  Job 1: scrape_documents                    │                             │
│  │  runs-on: ubuntu-latest                     │                             │
│  │                                             │                             │
│  │  Steps:                                     │                             │
│  │   1. Checkout repo                          │                             │
│  │   2. Install: requests beautifulsoup4       │                             │
│  │              playwright                     │                             │
│  │   3. python ingestion/scraper.py            │                             │
│  │      ↳ reads: data/urls.yaml (36 URLs)      │                             │
│  │      ↳ writes: data/cleaned_docs.jsonl      │                             │
│  │   4. Upload artifact: scrape-output-{run}   │                             │
│  │      path: data/cleaned_docs.jsonl          │                             │
│  └──────────────────────┬──────────────────────┘                             │
│                         │ artifact: scrape-output-{run}                      │
│                         ▼                                                    │
│  ┌─────────────────────────────────────────────┐                             │
│  │  Job 2: chunk_documents                     │                             │
│  │  runs-on: ubuntu-latest                     │                             │
│  │  needs: [scrape_documents]                  │                             │
│  │                                             │                             │
│  │  Steps:                                     │                             │
│  │   1. Checkout repo                          │                             │
│  │   2. Download artifact: scrape-output-{run} │                             │
│  │      path: data/                            │                             │
│  │   3. Install: tiktoken                      │                             │
│  │   4. python ingestion/chunker.py            │                             │
│  │      ↳ reads: data/cleaned_docs.jsonl       │                             │
│  │      ↳ writes: data/chunks.jsonl            │                             │
│  │   5. Upload artifact: chunk-output-{run}    │                             │
│  │      path: data/chunks.jsonl                │                             │
│  └──────────────────────┬──────────────────────┘                             │
│                         │ artifact: chunk-output-{run}                       │
│                         ▼                                                    │
│  ┌─────────────────────────────────────────────┐                             │
│  │  Job 3: embed_and_upsert                    │                             │
│  │  runs-on: ubuntu-latest                     │                             │
│  │  needs: [chunk_documents]                   │                             │
│  │                                             │                             │
│  │  Steps:                                     │                             │
│  │   1. Checkout repo                          │                             │
│  │   2. Download artifact: chunk-output-{run}  │                             │
│  │      path: data/                            │                             │
│  │   3. Download artifact: manifest-latest     │  ← previous run manifest   │
│  │      path: data/                            │                             │
│  │   4. Install: sentence-transformers         │                             │
│  │              chromadb rank-bm25             │                             │
│  │   5. python ingestion/embedder.py           │                             │
│  │      ↳ reads: data/chunks.jsonl             │                             │
│  │      ↳ reads: data/ingestion_manifest.json  │  ← diff (NEW/UPDATED/SKIP) │
│  │      ↳ writes: data/chroma_db/              │                             │
│  │      ↳ writes: data/ingestion_manifest.json │  ← updated for next run    │
│  │   6. Upload artifact: chroma-output-{run}   │                             │
│  │      path: data/chroma_db/                  │                             │
│  │   7. Upload artifact: manifest-latest       │  ← overwrites previous     │
│  │      path: data/ingestion_manifest.json     │                             │
│  └─────────────────────────────────────────────┘                             │
│                                                                              │
│  Notification: Slack/email on any job failure (optional)                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### 10.3 Full YAML Definition

```yaml
# .github/workflows/ingestion-scheduler.yml

name: Daily Ingestion Pipeline

on:
  schedule:
    - cron: "45 3 * * *"   # 9:15 AM IST (UTC 03:45)
  workflow_dispatch:
    inputs:
      force_full_rerun:
        description: "Re-embed ALL chunks ignoring manifest diff"
        required: false
        default: "false"

jobs:

  # ─────────────────────────────────────────────────────────────
  # Job 1: Scrape all 36 Groww URLs
  # ─────────────────────────────────────────────────────────────
  scrape_documents:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install scraper dependencies
        run: pip install requests beautifulsoup4 playwright

      - name: Install Playwright browsers
        run: playwright install chromium

      - name: Run scraper
        run: python ingestion/scraper.py
        env:
          URLS_YAML: data/urls.yaml

      - name: Upload scrape artifact
        uses: actions/upload-artifact@v4
        with:
          name: scrape-output-${{ github.run_id }}
          path: data/cleaned_docs.jsonl
          retention-days: 1

  # ─────────────────────────────────────────────────────────────
  # Job 2: Chunk cleaned documents
  # ─────────────────────────────────────────────────────────────
  chunk_documents:
    needs: [scrape_documents]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Download scrape artifact
        uses: actions/download-artifact@v4
        with:
          name: scrape-output-${{ github.run_id }}
          path: data/

      - name: Install chunking dependencies
        run: pip install tiktoken

      - name: Run chunker
        run: python ingestion/chunker.py

      - name: Upload chunk artifact
        uses: actions/upload-artifact@v4
        with:
          name: chunk-output-${{ github.run_id }}
          path: data/chunks.jsonl
          retention-days: 1

  # ─────────────────────────────────────────────────────────────
  # Job 3: Embed chunks + upsert into ChromaDB
  # ─────────────────────────────────────────────────────────────
  embed_and_upsert:
    needs: [chunk_documents]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Download chunk artifact
        uses: actions/download-artifact@v4
        with:
          name: chunk-output-${{ github.run_id }}
          path: data/

      # Pull previous manifest for change-detection diff
      # If no previous run exists, this step is skipped gracefully
      - name: Download previous ingestion manifest
        uses: actions/download-artifact@v4
        continue-on-error: true   # first ever run has no manifest yet
        with:
          name: manifest-latest
          path: data/

      - name: Install embedding + vector store dependencies
        run: pip install sentence-transformers chromadb tiktoken rank-bm25

      - name: Run embedder and ChromaDB upsert
        run: python ingestion/embedder.py
        env:
          CHROMA_PERSIST_PATH: data/chroma_db
          FORCE_FULL_RERUN: ${{ github.event.inputs.force_full_rerun || 'false' }}

      # Persist updated ChromaDB for Render to pull
      - name: Upload ChromaDB artifact
        uses: actions/upload-artifact@v4
        with:
          name: chroma-output-${{ github.run_id }}
          path: data/chroma_db/
          retention-days: 7

      # Overwrite manifest-latest so next run can download it for diff
      - name: Upload updated ingestion manifest (latest)
        uses: actions/upload-artifact@v4
        with:
          name: manifest-latest
          path: data/ingestion_manifest.json
          overwrite: true        # replaces the previous manifest-latest artifact
          retention-days: 30
```

---

### 10.4 `ingestion_manifest.json` Pattern

The manifest is the **bridge between pipeline runs**. It is uploaded as artifact `manifest-latest` at the end of every run and downloaded at the start of the next `embed_and_upsert` job. This enables the change-detection diff (NEW / UPDATED / UNCHANGED / DELETED) without persisting any state in the repo.

```json
// data/ingestion_manifest.json — written by embed_and_upsert, read by next run
{
  "run_id": "gh_run_123456789",
  "pipeline_run_at": "2026-04-17T03:45:00Z",
  "triggered_by": "schedule",           // "schedule" | "workflow_dispatch"
  "force_full_rerun": false,
  "embedding_model": "BAAI/bge-small-en-v1.5",
  "embedding_version": "2026-04",
  "counts": {
    "urls_processed": 36,
    "urls_failed": 0,
    "chunks_new": 12,
    "chunks_updated": 3,
    "chunks_unchanged": 345,
    "chunks_deleted": 1,
    "total_in_collection": 359
  },
  "doc_hashes": {
    "https://groww.in/mutual-funds/mirae-asset-large-cap-fund-direct-growth": "abc123..."
    // ... one entry per URL
  },
  "chunk_ids": ["sha256...", "sha256...", "..."]
}
```

**Manifest lifecycle:**

```
Run N:   embed_and_upsert writes manifest → uploads as artifact "manifest-latest"
         (overwrite: true — replaces previous)
           ↓
Run N+1: embed_and_upsert downloads artifact "manifest-latest"
         → diffs current chunks.jsonl against it
         → only NEW / UPDATED chunks are re-embedded
         → writes updated manifest → uploads as "manifest-latest"
```

**First run (no prior manifest):** `download-artifact` step has `continue-on-error: true`. The embedder detects a missing/empty manifest and treats all chunks as NEW → full embed on first run only.

**`force_full_rerun` flag:** When manually dispatching with `force_full_rerun: true`, the embedder ignores the downloaded manifest and re-embeds everything. Use this after a model upgrade that requires all vectors to be regenerated.

---

## 11. Known Limitations

| Limitation | Mitigation |
|---|---|
| Groww page structure may change | Resilient CSS selectors; alert on crawl failure |
| bge-small has lower accuracy than larger models | Use re-ranker (cross-encoder) to compensate |
| Single AMC (Mirae Asset) — no cross-AMC answers | Stated clearly in disclaimer; architecture is extensible |
| ChromaDB is local — not shared across Render instances | Acceptable for v1.0; move to managed vector DB if scaling |
| No PDF support (v1.0) | Factsheet/KIM/SID data limited to what Groww shows on page |
| Groq free tier rate limits | Implemented retry with backoff; cache frequent queries in Phase 9 |

---

## 12. Evaluation Metrics

| Metric | Target |
|---|---|
| Retrieval Recall@3 | ≥ 90% on 50-query test set |
| Answer Accuracy | ≥ 95% (human eval vs source) |
| Citation Accuracy | 100% (automated URL validation) |
| Refusal Precision | ≥ 98% (advisory queries correctly refused) |
| Response length compliance | 100% ≤ 3 sentences |
| PII Leak Rate | 0% |
| Latency p95 | < 3 seconds end-to-end |

---

> **Disclaimer:** Facts-only. No investment advice.