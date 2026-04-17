# Deployment Plan — Mutual Fund Explorer & FAQ Assistant

> **Version:** 1.0  
> **Date:** April 2026  
> **Architecture:** GitHub Actions (Scheduler) → Render (Backend) → Vercel (Frontend)

---

## 1. Deployment Architecture Overview

```
                         ┌──────────────────────────────────────────────────┐
                         │          GITHUB ACTIONS (Scheduler)              │
                         │                                                  │
                         │  Cron: 45 3 * * * UTC  (9:15 AM IST daily)     │
                         │  Also: workflow_dispatch (manual trigger)        │
                         │                                                  │
                         │  3-Job Pipeline:                                 │
                         │    1. scrape_documents → cleaned_docs.jsonl     │
                         │    2. chunk_documents  → chunks.jsonl           │
                         │    3. embed_and_upsert → chroma_db/ + manifest │
                         │                                                  │
                         │  After Job 3:                                    │
                         │    ✦ git commit + push data/ to repo            │
                         │    ✦ POST to RENDER_DEPLOY_HOOK webhook         │
                         └───────────────┬─────────────────┬───────────────┘
                                         │ push            │ webhook POST
                                         ▼                 ▼
 ┌───────────────────────────────────────────────────────────────┐
 │                      RENDER (Backend)                         │
 │                                                               │
 │  Service: Web Service (Python 3.11)                          │
 │  Repo:    auto-deploy on push to main                        │
 │  Build:   pip install -r ingestion/requirements.txt          │
 │  Start:   uvicorn backend.main:app --host 0.0.0.0           │
 │           --port $PORT                                       │
 │                                                               │
 │  Reads:   data/chroma_db/  (committed to repo)              │
 │           data/chunks.jsonl (for BM25 index at startup)      │
 │  API:     GET  /api/funds                                   │
 │           GET  /api/funds/categories                        │
 │           GET  /api/funds/{slug}                            │
 │           GET  /api/funds/{slug}/nav-history                │
 │           POST /api/threads                                 │
 │           POST /api/threads/{id}/messages                   │
 │           ...                                               │
 └───────────────────────────┬──────────────────────────────────┘
                              │ API calls via rewrite proxy
                              │
 ┌────────────────────────────┴────────────────────────────────┐
 │                     VERCEL (Frontend)                        │
 │                                                              │
 │  Framework:  Next.js 16 (App Router)                        │
 │  Root Dir:   frontend/                                      │
 │  Build Cmd:  npm install && npm run build                   │
 │  Dependencies: recharts, lucide-react                       │
 │  Output Dir: .next                                          │
 │                                                              │
 │  Rewrite proxy in next.config.ts:                           │
 │    /api/* → $NEXT_PUBLIC_API_URL/api/*                      │
 │                                                              │
 │  Result: browser calls Vercel /api/* → Render /api/*        │
 │          (no CORS preflight, zero client-side URL exposure)  │
 └──────────────────────────────────────────────────────────────┘
```

---

## 2. Environment Variables — Per Platform

### 2.1 GitHub Actions Secrets

Set in **Settings → Secrets and variables → Actions → Repository secrets.**

| Secret Name | Value | Required By |
|---|---|---|
| `GROQ_API_KEY` | `gsk_...` (Groq console key) | Ingestion pipeline (embed_and_upsert — if future steps need LLM validation) |
| `RENDER_DEPLOY_HOOK` | `https://api.render.com/deploy/srv-...?key=...` | Post-ingestion step that triggers Render redeploy |
| `GH_PAT` | Personal Access Token with `repo` scope | Committing and pushing `data/` artifacts back to the repo from the workflow |

> [!WARNING]  
> **`GH_PAT`** is needed because `GITHUB_TOKEN` (the default) cannot trigger subsequent workflows on push. If you don't have other workflows to trigger, the default `GITHUB_TOKEN` suffices.

### 2.2 Render Environment Variables

Set in **Render Dashboard → Your Service → Environment.**

| Variable | Value | Notes |
|---|---|---|
| `GROQ_API_KEY` | `gsk_...` | **Required.** LLM API key. Never hardcoded. |
| `CHROMA_PERSIST_PATH` | `data/chroma_db` | Path to the ChromaDB directory (relative to repo root) |
| `CHROMA_COLLECTION` | `mutual_fund_faq` | ChromaDB collection name |
| `CHUNKS_JSONL` | `data/chunks.jsonl` | BM25 corpus file path |
| `NEXT_PUBLIC_FRONTEND_URL` | `https://your-app.vercel.app` | Allowed CORS origin (backend reads this to allow the Vercel domain) |
| `PYTHON_VERSION` | `3.11.9` | Pin Python version on Render |

### 2.3 Vercel Environment Variables

Set in **Vercel Dashboard → Your Project → Settings → Environment Variables.**

| Variable | Value | Scope | Notes |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://your-service.onrender.com` | Production + Preview | Used by `next.config.ts` to rewrite `/api/*` → Render backend |

> [!NOTE]  
> `NEXT_PUBLIC_API_URL` is consumed **server-side** by the Next.js rewrite — it is NOT exposed to the browser. The actual API calls from the browser go to `/api/*` on the Vercel domain.

---

## 3. How ChromaDB Data Gets to Render

ChromaDB is a **local persistent** vector store — there is no cloud database. The data pipeline is:

```
GitHub Actions (embed_and_upsert)
        │
        │ Generates:
        │   data/chroma_db/          (~2–10 MB, SQLite + parquet files)
        │   data/chunks.jsonl        (~600 KB)
        │   data/ingestion_manifest.json
        │
        ├──▶ Upload as GitHub Actions artifacts (for next-run manifest diff)
        │
        └──▶ git add + commit + push to main branch
                    │
                    ▼
             GitHub repo (main)
                    │ Render detects push (auto-deploy)
                    │  — OR —
                    │ GitHub Actions POSTs to RENDER_DEPLOY_HOOK
                    ▼
             Render pulls latest main → pip install → uvicorn starts
             Backend reads data/chroma_db/ and data/chunks.jsonl from disk
```

### 3.1 Workflow Addition — Commit Data + Trigger Render

Add these steps **at the end of the `embed_and_upsert` job** in `.github/workflows/ingestion-scheduler.yml`:

```yaml
      # ── Commit updated data back to repo ─────────────────────────────
      - name: Commit ingestion data to repo
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

          # Force-add data files that are normally gitignored
          git add -f data/chroma_db/
          git add -f data/chunks.jsonl
          git add -f data/ingestion_manifest.json

          # Only commit if there are actual changes
          if git diff --cached --quiet; then
            echo "No data changes — skipping commit"
          else
            git commit -m "chore: update ingestion data [skip ci]

            Run ID: ${{ github.run_id }}
            Triggered by: ${{ github.event_name }}"
            git push
          fi
        env:
          GITHUB_TOKEN: ${{ secrets.GH_PAT }}

      # ── Trigger Render redeploy ──────────────────────────────────────
      - name: Trigger Render redeploy
        if: success()
        run: |
          echo "Triggering Render deploy hook..."
          curl -s -o /dev/null -w "HTTP %{http_code}" \
            -X POST "${{ secrets.RENDER_DEPLOY_HOOK }}"
          echo ""
          echo "Deploy hook triggered successfully"
```

> [!IMPORTANT]  
> The commit message includes `[skip ci]` to prevent the push from re-triggering the ingestion workflow in an infinite loop.

### 3.2 Why Commit to Repo (vs. Other Options)

| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| **Commit to repo** | Simple; Render auto-deploys on push; data versioned in Git | Repo size grows over time (~10 MB/run) | ✅ Yes (v1.0) |
| GitHub Releases | Clean separation of code and data | Complex download at Render build time | ❌ |
| S3/GCS bucket | Scalable; decoupled | Extra infra cost; Render needs download logic | ❌ (future) |
| Render Persistent Disk | No Git storage needed | Render free tier has no persistent disk | ❌ |

> [!TIP]  
> When the repo size grows past ~100 MB, migrate to a cloud storage bucket (S3/GCS). The embedder writes there; the Render start script downloads on boot.

---

## 4. Render Backend — Setup Guide

### 4.1 Create Render Web Service

1. Go to [Render Dashboard](https://dashboard.render.com) → **New +** → **Web Service**
2. Connect your GitHub repository
3. Configure:

| Setting | Value |
|---|---|
| **Name** | `mf-faq-backend` (or your choice) |
| **Region** | Oregon (US West) or nearest |
| **Branch** | `main` |
| **Root Directory** | *(leave blank — repo root)* |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | Free (or Starter for reliability) |
| **Auto-Deploy** | Yes (on push to `main`) |

4. Add all environment variables from [Section 2.2](#22-render-environment-variables)
5. Click **Create Web Service**

### 4.2 Get Render Deploy Hook

1. Go to your Render service → **Settings** → **Deploy Hook**
2. Click **Generate Deploy Hook** → copy the URL
3. Add it as `RENDER_DEPLOY_HOOK` in GitHub Actions secrets

### 4.3 Health Check Endpoint

Configure Render to use `/api/health` as the health check path. This verifies:
- ChromaDB collection is loaded with vectors
- `chunks.jsonl` exists (BM25 corpus)
- `GROQ_API_KEY` is set

### 4.4 Render Cold Starts

Render free tier spins down after 15 minutes of inactivity. First request after spin-down takes ~30–60s while:
1. Python boots
2. `sentence-transformers` loads `bge-small-en-v1.5` (~80 MB model)
3. `cross-encoder/ms-marco-MiniLM-L-6-v2` loads (~80 MB)
4. BM25 index builds from `chunks.jsonl`

> [!TIP]  
> Mitigate cold starts by setting up a **cron health ping** (e.g., UptimeRobot free tier hitting `/api/health` every 14 minutes).

---

## 5. Vercel Frontend — Setup Guide

### 5.1 Create Vercel Project

1. Go to [Vercel Dashboard](https://vercel.com/dashboard) → **Add New** → **Project**
2. Import the GitHub repository
3. Configure:

| Setting | Value |
|---|---|
| **Framework Preset** | Next.js |
| **Root Directory** | `frontend` |
| **Build Command** | `npm run build` *(auto-detected)* |
| **Output Directory** | `.next` *(auto-detected)* |
| **Node.js Version** | 20.x |

4. Add environment variable from [Section 2.3](#23-vercel-environment-variables)
5. Click **Deploy**

### 5.2 How the Rewrite Proxy Works

`frontend/next.config.ts` contains:

```ts
async rewrites() {
  return [
    {
      source: "/api/:path*",
      destination: `${API_URL}/api/:path*`,   // → Render backend
    },
  ];
}
```

**Effect:** Browser calls `https://your-app.vercel.app/api/threads` → Vercel rewrites server-side to `https://your-service.onrender.com/api/threads`. No CORS preflight, no API URL exposed in client JS.

### 5.3 Auto-Deploy & Build Optimization

Vercel auto-deploys on push to `main`. Since daily ingestion runs push data changes directly to the repo, we use a `frontend/vercel.json` file to prevent redundant frontend builds:

```json
{
  "ignoreCommand": "git diff --quiet HEAD~1 -- ."
}
```

This tells Vercel to only trigger a build if files inside the `frontend/` directory have changed.

---

## 6. GitHub Actions Scheduler — Configuration

### 6.1 Existing Workflow

Already defined in `.github/workflows/ingestion-scheduler.yml`:

| Property | Value |
|---|---|
| **Cron** | `45 3 * * *` (UTC) = **9:15 AM IST daily** |
| **Manual trigger** | `workflow_dispatch` with optional `force_full_rerun` flag |
| **Job 1** | `scrape_documents` — scrapes 36 Groww URLs |
| **Job 2** | `chunk_documents` — section-aware chunking (500 tokens, 50 overlap) |
| **Job 3** | `embed_and_upsert` — bge-small-en-v1.5 embed + ChromaDB upsert |
| **Data bridge** | GitHub Actions artifacts passed between jobs |
| **Manifest** | `manifest-latest` artifact carries diff state across runs |

### 6.2 Adding Render Deploy Trigger

Append the steps from [Section 3.1](#31-workflow-addition--commit-data--trigger-render) to the end of the `embed_and_upsert` job. The full flow becomes:

```
scrape_documents
      ↓ (artifact: cleaned_docs.jsonl)
chunk_documents
      ↓ (artifact: chunks.jsonl)
embed_and_upsert
      ↓ writes chroma_db/ + manifest
      ↓ git commit + push data/ to repo
      ↓ POST to RENDER_DEPLOY_HOOK
      ↓
Render auto-deploys with fresh data
```

### 6.3 Manual Trigger — Force Full Re-embed

```bash
# From GitHub CLI:
gh workflow run "Daily Ingestion Pipeline" \
  --field force_full_rerun=true

# Or: GitHub UI → Actions → Daily Ingestion Pipeline → Run workflow
# Set "force_full_rerun" to "true"
```

Use this after upgrading `bge-small-en-v1.5` or changing `CHUNK_SIZE`/`CHUNK_OVERLAP`, since all existing vectors must be regenerated.

---

## 7. Local Testing Before Deployment

### 7.1 Backend — Local Testing Checklist

```bash
# 1. Activate virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r ingestion/requirements.txt

# 3. Set up environment
cp .env.example .env
# Edit .env → set GROQ_API_KEY=gsk_...

# 4. Run ingestion locally (optional — if data/ already populated):
python ingestion/scraper.py
python ingestion/chunker.py
python ingestion/embedder.py

# 5. Start backend
uvicorn backend.main:app --reload --port 8000

# 6. Verify health check
curl http://localhost:8000/api/health
# Expected: {"status":"ok","checks":{"chroma":{"vector_count":...},...}}

# 7. Run API tests
python -m pytest backend/test_api.py -v
python -m pytest backend/test_isolation.py -v

# 8. Smoke test — create thread + send query
curl -X POST http://localhost:8000/api/threads
# Note the thread_id

curl -X POST http://localhost:8000/api/threads/<thread_id>/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "What is the expense ratio of Mirae Asset Large Cap Direct?"}'
# Expected: response with citation + last_updated footer
```

### 7.2 Frontend — Local Testing Checklist

```bash
cd frontend

# 1. Environment
cp .env.local.example .env.local
# Verify: NEXT_PUBLIC_API_URL=http://localhost:8000

# 2. Install and build
npm install
npm run build          # Must pass with 0 TypeScript errors
npm run lint           # Must pass with 0 lint errors

# 3. Start dev server (backend must be running on :8000)
npm run dev            # → http://localhost:3000

# 4. Manual exit criteria checks:
#    ✓ Disclaimer banner visible at top, stays fixed on scroll
#    ✓ 3 example question chips on welcome screen
#    ✓ Click example → message bubble appears with citation + footer
#    ✓ Create 2 threads → independent message histories
#    ✓ Delete thread → disappears from sidebar
```

### 7.3 End-to-End — Integration Test

```bash
# Start both services:
# Terminal 1:
uvicorn backend.main:app --reload --port 8000

# Terminal 2:
cd frontend && npm run dev

# Open http://localhost:3000
# Click "What is the expense ratio of Mirae Asset Large Cap Direct?"
# Verify:
#   ✓ User bubble appears (indigo, right-aligned)
#   ✓ Loading dots animate in assistant bubble
#   ✓ Assistant bubble appears with answer, "View source" link, and footer
#   ✓ Citation link opens Groww page in new tab
```

---

## 8. Rollback Instructions

### 8.1 Backend (Render) — Rollback to Previous Deploy

**Option A — Render Dashboard:**
1. Go to **Render Dashboard** → your service → **Deploys**
2. Find the previous successful deploy in the list
3. Click the **⋮** menu → **Rollback to this deploy**
4. Service restarts with the previous code + data snapshot

**Option B — Git Revert:**
```bash
# Identify the commit to revert to
git log --oneline -10

# Revert the bad commit (creates a new commit)
git revert <bad-commit-hash>
git push origin main
# Render auto-deploys the reverted state
```

**Option C — Revert Data Only (ingestion regression):**
```bash
# If only the ingestion data is bad (wrong embeddings, corrupted ChromaDB):

# 1. Find the last good data commit
git log --oneline -- data/

# 2. Restore data files from that commit
git checkout <good-commit-hash> -- data/chroma_db/ data/chunks.jsonl data/ingestion_manifest.json

# 3. Commit and push
git add data/
git commit -m "fix: rollback ingestion data to <good-commit-hash>"
git push origin main
# Render auto-deploys with restored data
```

### 8.2 Frontend (Vercel) — Rollback to Previous Deployment

1. Go to **Vercel Dashboard** → your project → **Deployments**
2. Find the previous successful production deployment
3. Click **⋮** → **Promote to Production**
4. The old build is promoted instantly (no rebuild needed)

### 8.3 Ingestion Pipeline — Rollback Manifest

If the ingestion pipeline produced bad data and you want the **next scheduled run** to treat all chunks as NEW (full re-embed):

```bash
# Option A — Manual trigger with force flag
gh workflow run "Daily Ingestion Pipeline" \
  --field force_full_rerun=true

# Option B — Delete the manifest-latest artifact from GitHub
# Go to: Actions → most recent successful run → Artifacts
# Delete "manifest-latest"
# Next scheduled run will treat all chunks as NEW (full embed)
```

---

## 9. Full Deployment Sequence (Step-by-Step)

### Initial Deployment (First Time)

```
Step 1  │ Push code to GitHub (main branch)
        │
Step 2  │ Set GitHub Actions secrets:
        │   GROQ_API_KEY, GH_PAT, RENDER_DEPLOY_HOOK (set after Step 4)
        │
Step 3  │ Run ingestion pipeline manually:
        │   GitHub → Actions → "Daily Ingestion Pipeline" → Run workflow
        │   Wait for all 3 jobs to pass (15–30 min)
        │   This commits data/chroma_db/ + data/chunks.jsonl to repo
        │
Step 4  │ Create Render Web Service:
        │   Build cmd:  pip install -r ingestion/requirements.txt
        │   Start cmd:  uvicorn backend.main:app --host 0.0.0.0 --port $PORT
        │   Set env vars: GROQ_API_KEY, CHROMA_PERSIST_PATH, CHROMA_COLLECTION,
        │                 CHUNKS_JSONL, NEXT_PUBLIC_FRONTEND_URL
        │   Verify: https://your-service.onrender.com/api/health → {"status":"ok"}
        │
Step 4b │ Copy the Render Deploy Hook URL → add as RENDER_DEPLOY_HOOK secret
        │   in GitHub Actions
        │
Step 5  │ Create Vercel Project:
        │   Root dir: frontend/
        │   Set env var: NEXT_PUBLIC_API_URL = https://your-service.onrender.com
        │   Deploy → verify: https://your-app.vercel.app loads the chat UI
        │
Step 6  │ Update NEXT_PUBLIC_FRONTEND_URL on Render to the actual Vercel URL
        │   (for CORS: backend must allow the Vercel origin)
        │
Step 7  │ End-to-end test:
        │   Open Vercel URL → click example question → verify response
        │   Create 2 threads → verify independent histories
        │   Disclaimer banner always visible
```

### Daily Operation (Automatic)

```
09:15 AM IST  │ GitHub Actions cron triggers ingestion pipeline
              │   Job 1: scrape 36 Groww URLs
              │   Job 2: chunk documents
              │   Job 3: embed + upsert to ChromaDB
              │   Job 3+: commit data/ to repo + POST Render deploy hook
              │
~09:45 AM IST │ Render auto-deploys with fresh data
              │ Backend restarts → loads new ChromaDB + BM25 index
              │
All day       │ Users query via Vercel frontend → Render backend → Groq LLM
              │ Answers grounded in today's scraped data
```

---

## 10. Monitoring & Alerts

| What | How |
|---|---|
| **Pipeline failures** | GitHub Actions sends email on job failure (default). Add Slack webhook for team notifications. |
| **Backend health** | UptimeRobot (free) pinging `GET /api/health` every 14 min (also prevents cold starts). |
| **Render deploy status** | Render Dashboard → Deploys → check for failed deploys. |
| **Vercel deploy status** | Vercel Dashboard → Deployments → check for build errors. |
| **Data freshness** | Every assistant response includes "Last updated from sources: \<date\>" — if the date is > 2 days old, investigate ingestion. |
| **Vector count regression** | `/api/health` returns `chroma.vector_count`. Alert if it drops significantly between deploys. |

---

## 11. Cost Summary

| Service | Tier | Monthly Cost | Limits |
|---|---|---|---|
| **GitHub Actions** | Free (public repo) / Free 2000 min (private) | $0 | ~25 min/run × 30 runs = 750 min/month |
| **Render** | Free | $0 | 750 hours/month; spins down after 15 min idle |
| **Render** | Starter (recommended) | $7/month | Always on; 512 MB RAM; no cold starts |
| **Vercel** | Hobby (free) | $0 | 100 GB bandwidth; serverless functions |
| **Groq** | Free tier | $0 | Rate-limited; sufficient for demo traffic |
| **Total (free tier)** | | **$0** | Suitable for development and demo |
| **Total (recommended)** | | **$7/month** | Render Starter eliminates cold starts |

---

## 12. Local Development (Docker)

To run the entire stack locally without relying on Render or Vercel, use the provided Docker orchestration.

### 12.1 Prerequisites
- Docker and Docker Compose installed
- A `.env` file with `GROQ_API_KEY` set

### 12.2 Quick Start
```bash
# 1. Build and start services
docker-compose up --build

# 2. Access points
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

### 12.3 Features
- **Persistence:** The `data/` directory is mounted to the backend container, so ChromaDB state survives restarts.
- **Hot-Reloading:** Both `backend/` and `frontend/` are mounted as volumes, allowing real-time code updates.
- **Isolation:** Each service runs in its own containerized environment with proper networking.

---

> **Disclaimer:** Facts-only. No investment advice.
