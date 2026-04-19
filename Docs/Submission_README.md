# Mutual Fund FAQ Assistant (RAG Pipeline)
**Milestone 1 Submission**

## Project Scope
- **Target Product Modeled**: Groww
- **AMC**: Mirae Asset
- **Corpus Limit**: Exactly 36 verified public fund tracking pages scraped directly from Groww (Equity, Sectoral, Index, Target Maturity, Debt).

## Limitations and Constraints Check
1. **Public Sources Only**: We do not use third-party unverified blogs. All context is built upon facts fetched continuously from official data endpoints and web UI rendering (Playwright/BeautifulSoup pipeline).
2. **Zero PII**: This chatbot intercepts and automatically redacts Aadhaar, PAN, SSNs, phone numbers, and emails using a RegEx post-processor before feeding content into or out of the DB.
3. **Strictly "No Advice"**: 
   - An advanced dual-stage explicit Intent Classifier (`query_guard.py`) analyzes inputs.
   - If terms like "Should I buy", "Recommend", or "Which is better" are used, the chatbot returns a predefined static refusal response pointing to the AMFI Investor Education Portal.
4. **No Financial Returns Projections by LLM**: All Mathematical/Projection requests automatically redirect users to an interactive Math Calculator in the UI (Historical performance injected directly into frontend without relying on LLM hallucinative responses).
5. **Citations & Maximum Lengths**: All factual answers are brutally limited to 3 sentences, appending a unified footnote: `Last updated from sources: <date>`. Followed immediately by the original `<Citation_URL>`.

## File Setup & Running Instructions
*Note: Ensure you have your `.env` configured inside `./` (containing your Groq key) prior to running.*

**1. Data Ingestion & RAG Embalming**
```bash
# In Root
pip install -r requirements.txt
playwright install chromium
python ingestion/scraper.py
python ingestion/chunker.py
python ingestion/embedder.py
python ingestion/vector_store.py
```

**2. Backend (FastAPI)**
```bash
# Run the API server
cd backend
uvicorn main:app --reload --port 8000
```

**3. Frontend (Next.js)**
```bash
# Run the Next server
cd frontend
npm install
npm run dev
```

Visit the `http://localhost:3000` dashboard. A fully context-aware 36-Mutual Fund Chat Widget awaits!
