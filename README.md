# Emerald Ledger: Mirae Asset Fund Explorer & AI Assistant

Emerald Ledger is a modern, full-stack web platform designed to explore Mirae Asset mutual funds with institutional-grade design and intelligent, context-aware insights. 

It spans a complete architecture including a React-based frontend, a highly concurrent Python backend, an automated data scraping pipeline, and an AI-driven RAG (Retrieval-Augmented Generation) engine.

## ✨ Key Features

- **Context-Aware Return Calculator**: Calculate projected SIP and lump-sum returns automatically. Instead of manual guesswork, the calculator dynamically uses the actual historical performance (1Y, 3Y, 5Y rates) of the specific fund being viewed.
- **Interactive NAV Charts**: Beautiful, responsive SVGs powered by `recharts` to visualize portfolio holdings, sector allocation, and NAV growth over time.
- **Floating AI Assistant (RAG)**: A persistent, facts-only chatbot widget that answers mutual fund FAQs. It's powered by an advanced RAG pipeline leveraging BM25 lexical search and ChromaDB vector search.
- **Premium UI/UX**: Designed with a sleek, institutional aesthetic featuring curated color palettes, dynamic micro-animations, and a highly responsive Next.js App Router layout.
- **Automated Daily Ingestion**: A robust scraping pipeline (`ingestion/`) that pulls fresh fund data and FAQs from Groww, automated via GitHub Actions.

## 🏗️ Tech Stack

### Frontend (User Interface)
- **Framework**: Next.js 15 (React)
- **Styling**: Vanilla CSS (`globals.css`) with a bespoke modern design system
- **Data Visualization**: Recharts
- **Hosting**: Vercel

### Backend (API & AI)
- **Framework**: FastAPI (Python)
- **LLM Engine**: Groq API
- **Vector Database**: ChromaDB
- **Retrieval**: Hybrid Search (BM25 + Vector embeddings)
- **Hosting**: Render / Docker

### Data Pipeline
- **Orchestration**: GitHub Actions (CI/CD)
- **Scraping**: BeautifulSoup4, Requests
- **Processing**: Chunking and sanitization scripts for LLM optimization

## 🚀 Getting Started

### 1. Backend Setup
Navigate to the `backend/` directory:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```
Create a `.env` file referencing `.env.example` and add your keys (like `GROQ_API_KEY`).
Start the API:
```bash
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup
Navigate to the `frontend/` directory:
```bash
cd frontend
npm install
```
Start the Next.js development server:
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

## 🤝 Project Structure
- `/frontend`: Next.js web application.
- `/backend`: FastAPI service handling standard REST endpoints and the conversational RAG logic.
- `/ingestion`: Scripts used to scrape and format mutual fund data into `.jsonl`.
- `/.github`: CI/CD pipelines including the daily data ingestion chron job.

---

> **Disclaimer:** Mutual fund investments are subject to market risks. This project is intended as a display of software engineering and design capabilities. It does not provide financial or investment advice.
