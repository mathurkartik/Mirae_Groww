# M2 Project Improvement Plan

**Project:** Mirae Asset Mutual Fund FAQ Assistant  
**Current Version:** Final submission (M2.zip)  
**Target:** Production-grade compliance fixes + fund-specific SIP calculator

---

## 🚨 CRITICAL FIXES (Priority 1 — Week 1)

### 1. Remove Math Projection Capability from LLM Generator

**Issue:** COMPLIANCE RISK — Lines 134, 138 in `backend/core/generator.py` allow LLM to perform mathematical projections, violating facts-only mandate.

**Current problematic lines:**
```python
# Line 134
2. Maximum 3 sentences per answer unless you are demonstrating a mathematical calculation.

# Line 138  
6. If the user asks for a SIP, Step-Up SIP, or lumpsum mathematical prediction/calculation based on historical returns or assumed rates, you MUST calculate and provide the estimated future value using standard mathematical formulas. Clearly state that this is an estimate.
```

**Fix:**
```python
# backend/core/generator.py — REPLACE SYSTEM_PROMPT (lines 130-142)

SYSTEM_PROMPT = """You are a facts-only mutual fund FAQ assistant for Mirae Asset funds.

STRICT RULES:
1. Answer ONLY factual, verifiable questions about mutual fund schemes.
2. Maximum 3 sentences per answer.
3. Include EXACTLY ONE citation URL from the provided context if you are answering about a specific fund. Use 'https://groww.in/mutual-funds' as citation if answering a general question.
4. End every answer with: "Last updated from sources: <last_crawled_date>"
5. NEVER provide investment advice, recommendations, comparisons, or return predictions.
6. NEVER perform mathematical calculations for SIP projections, lumpsum future values, or returns. For calculation requests, redirect users to the interactive calculator.
7. If context is insufficient for a fund-specific question, respond: "I don't have this information in my current sources. Please check https://groww.in/mutual-funds for the latest details."
8. NEVER fabricate fund data. If unsure about a fund's specific metric, say you don't have it.

Facts-only. No investment advice."""
```

**Validation:**
- Grep for `mathematical calculation` → should return 0 results
- Grep for `SIP.*projection` → should return 0 results  
- Test query: "Calculate SIP returns for 5000/month at 12% for 5 years" → should NOT generate calculation

---

### 2. Add MATH_QUERY Intent to Query Guard

**Issue:** SIP calculator questions are currently classified as FACTUAL or ADVISORY, leading to wrong responses. Need explicit MATH_QUERY intent with redirect.

**File:** `backend/core/query_guard.py`

**Changes:**

#### Step 2a: Add new intent constant (after line 87)
```python
INTENT_MATH_QUERY   = "MATH_QUERY"
```

#### Step 2b: Add math redirect message (after line 106)
```python
REFUSAL_MATH_REDIRECT = (
    "I can help you with that using our interactive calculator. "
    "The calculator lets you simulate SIP or one-time investments with custom return rates and periods. "
    "Please use the SIP Calculator tab to project your investment growth.\n\n"
    "Facts-only. No investment advice."
)
```

#### Step 2c: Add math query pattern list (after line 196)
```python
# Math query patterns: triggers calculator redirect
_MATH_PHRASES: list[str] = [
    "calculate sip",
    "sip calculation",
    "calculate returns",
    "future value",
    "corpus after",
    "how much will",
    "what will be the",
    "sip calculator",
    "lumpsum calculator",
    "investment calculator",
    "calculate investment",
    "sip of ",           # catches "SIP of 5000"
    "monthly sip of",
    "invest 5000",
    "invest 10000",
    "maturity value",
    "final amount",
    "step up sip",
    "step-up sip",
]
```

#### Step 2d: Modify `_keyword_classify` function (replace lines 228-305)
```python
def _keyword_classify(query: str) -> GuardResult | None:
    """
    Stage-1 classification via keyword matching.
    
    Returns
    -------
    GuardResult | None
        If a definitive classification can be made, return GuardResult.
        If ambiguous, return None → defer to LLM stage.
    """
    q_lower = query.lower()
    
    # Priority 1: Check factual overrides FIRST (prevents false positives)
    for phrase in _FACTUAL_OVERRIDES:
        if phrase in q_lower:
            log.debug("Query FACTUAL (override): %r matched %r", query[:60], phrase)
            return GuardResult(
                intent=INTENT_FACTUAL,
                refusal_message=None,
                matched_phrase=phrase,
                stage="keyword",
            )
    
    # Priority 2: Check MATH patterns
    for phrase in _MATH_PHRASES:
        if phrase in q_lower:
            log.info("Query MATH_QUERY: %r matched %r", query[:60], phrase)
            return GuardResult(
                intent=INTENT_MATH_QUERY,
                refusal_message=REFUSAL_MATH_REDIRECT,
                matched_phrase=phrase,
                stage="keyword",
            )
    
    # Priority 3: Check ADVISORY patterns
    for phrase in _ADVISORY_PHRASES:
        if phrase in q_lower:
            log.info("Query ADVISORY: %r matched %r", query[:60], phrase)
            return GuardResult(
                intent=INTENT_ADVISORY,
                refusal_message=REFUSAL_ADVISORY,
                matched_phrase=phrase,
                stage="keyword",
            )
    
    # Priority 4: Check OUT_OF_SCOPE patterns
    for phrase in _OOS_PHRASES:
        if phrase in q_lower:
            log.info("Query OUT_OF_SCOPE: %r matched %r", query[:60], phrase)
            return GuardResult(
                intent=INTENT_OUT_OF_SCOPE,
                refusal_message=REFUSAL_OUT_OF_SCOPE,
                matched_phrase=phrase,
                stage="keyword",
            )
    
    # No match → return None (defer to LLM classifier)
    log.debug("No keyword match for query: %r", query[:60])
    return None
```

#### Step 2e: Update GuardResult property (add after line 224)
```python
@property
def is_math_redirect(self) -> bool:
    return self.intent == INTENT_MATH_QUERY
```

---

### 3. Wire MATH_QUERY Through Backend API

**File:** `backend/api/routes/messages.py`

**Change at line 148-163:**

Replace the current refusal block with:
```python
if guard.is_refusal or guard.is_math_redirect:
    # Build refusal/redirect assistant message directly — no LLM call
    assistant_msg = Message(
        message_id   = str(uuid.uuid4()),
        role         = "assistant",
        content      = guard.refusal_message or REFUSAL_ADVISORY,
        timestamp    = _utcnow(),
        citation     = "https://www.amfiindia.com/investor-corner/knowledge-center" if guard.is_refusal else None,
        last_updated = None,
        is_refusal   = guard.is_refusal,
        is_math_redirect = guard.is_math_redirect,
        intent       = guard.intent,
    )
    store.add_message(thread_id, assistant_msg)
    return _build_response(thread_id, assistant_msg, retrieval_count=0)
```

**File:** `backend/store/thread_store.py`

Add `is_math_redirect` field to Message dataclass:
```python
@dataclass
class Message:
    message_id:   str
    role:         str
    content:      str
    timestamp:    str
    citation:     str | None        = None
    last_updated: str | None        = None
    is_refusal:   bool               = False
    is_math_redirect: bool           = False  # NEW
    intent:       str | None        = None
```

**File:** `backend/api/routes/messages.py` (MessageResponse schema at line 48)

Add field:
```python
class MessageResponse(BaseModel):
    thread_id:    str
    message_id:   str
    role:         str
    content:      str
    citation:     Optional[str]
    last_updated: Optional[str]
    timestamp:    str
    is_refusal:   bool
    is_math_redirect: bool = False  # NEW
    intent:       Optional[str]   = None
    retrieval_count: Optional[int] = None
```

---

### 4. Wire MATH_QUERY Through Frontend

**File:** `frontend/src/lib/api.ts`

Add field to Message interface:
```typescript
export interface Message {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  citation?: string;
  last_updated?: string;
  is_refusal?: boolean;
  is_math_redirect?: boolean;  // NEW
  intent?: string;
}
```

**Frontend display is ALREADY implemented** in `MessageBubble.tsx` (lines 63-82) — no changes needed there.

---

### 5. Fix Groww Boilerplate in Chunks (Data Quality Issue)

**Issue:** `chunk_index: 0` for all 36 funds contains React SPA nav boilerplate instead of fund content.

**File:** `ingestion/scraper.py`

**Add after line 50 (after `_strip_script_tags` function):**

```python
def _strip_groww_nav(html_text: str) -> str:
    """
    Remove Groww-specific navigation boilerplate that appears at the start
    of every fund page. This content is identical across all funds and adds
    no fund-specific value.
    
    Boilerplate patterns to remove:
    - "Stocks Mutual Funds Fixed Deposits Gold US Stocks..."
    - "Login/Register GROWW"
    - Generic nav menus
    """
    # Pattern 1: Top nav links (Stocks, Mutual Funds, Fixed Deposits...)
    html_text = re.sub(
        r'Stocks\s+Mutual Funds\s+Fixed Deposits\s+Gold\s+US Stocks.*?(?=<)',
        '',
        html_text,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Pattern 2: Login/Register + GROWW branding
    html_text = re.sub(
        r'Login/Register\s+GROWW.*?(?=<)',
        '',
        html_text,
        flags=re.DOTALL
    )
    
    # Pattern 3: Generic header menus (matches divs with navigation classes)
    html_text = re.sub(
        r'<div[^>]*class="[^"]*nav[^"]*"[^>]*>.*?</div>',
        '',
        html_text,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    return html_text
```

**Then modify the `scrape_url` function (around line 120):**

```python
# After line 135 (_strip_script_tags call)
cleaned_html = _strip_script_tags(html_text)
cleaned_html = _strip_groww_nav(cleaned_html)  # NEW — Add this line
```

**Validation after re-ingestion:**
```bash
# Re-run ingestion
cd ingestion && python scraper.py

# Check chunk_index 0 for any fund — should NOT contain boilerplate
grep -A5 '"chunk_index": 0' data/chunks.jsonl | head -20
```

---

## 🎯 ENHANCEMENT: Fund-Specific SIP Calculator (Priority 2 — Week 1)

### Problem Statement

Current SIP calculator is **generic** — user manually enters return rate. Goal: **Auto-populate expected return rate based on current fund's historical performance** when calculator is opened from a fund detail page.

---

### Architecture

#### Data Flow
```
Fund Detail Page (/fund/[slug])
  └─> Fetch fund metadata (useFundData hook)
      ├─> Fund name (e.g., "Mirae Asset Low Duration Fund")
      ├─> MFAPI code (118840)
      └─> Pass to SipCalculator as props

SipCalculator Component
  ├─> Receive: fundName, mfapiCode
  ├─> On mount: Fetch 1Y/3Y/5Y CAGR from MFAPI
  ├─> Auto-select best matching period
  └─> Pre-fill return rate slider with fund's historical CAGR
```

---

### Implementation Steps

#### Step 1: Create MFAPI historical returns fetcher

**New file:** `frontend/src/lib/mfapi.ts`

```typescript
/**
 * mfapi.ts — Fetch historical NAV data from MFAPI.in and calculate CAGR
 * 
 * MFAPI endpoint: https://api.mfapi.in/mf/{scheme_code}
 * Returns: {data: [{date: "DD-MM-YYYY", nav: "123.45"}, ...]}
 */

export interface NAVDataPoint {
  date: string;  // "DD-MM-YYYY"
  nav: string;   // "123.45"
}

export interface MFAPIResponse {
  meta: {
    scheme_code: string;
    scheme_name: string;
  };
  data: NAVDataPoint[];
  status: string;
}

/**
 * Calculate CAGR between two NAV values over a given period.
 * Formula: CAGR = ((End Value / Start Value)^(1/years) - 1) * 100
 */
function calculateCAGR(startNav: number, endNav: number, years: number): number {
  if (startNav <= 0 || years <= 0) return 0;
  const cagr = (Math.pow(endNav / startNav, 1 / years) - 1) * 100;
  return Math.round(cagr * 100) / 100; // Round to 2 decimals
}

/**
 * Parse DD-MM-YYYY string to Date object
 */
function parseDate(dateStr: string): Date {
  const [day, month, year] = dateStr.split('-').map(Number);
  return new Date(year, month - 1, day);
}

/**
 * Get NAV data point closest to target date (within ±7 days tolerance)
 */
function getNavNearDate(data: NAVDataPoint[], targetDate: Date): NAVDataPoint | null {
  const tolerance = 7 * 24 * 60 * 60 * 1000; // 7 days in milliseconds
  
  let closest: NAVDataPoint | null = null;
  let minDiff = Infinity;
  
  for (const point of data) {
    const pointDate = parseDate(point.date);
    const diff = Math.abs(pointDate.getTime() - targetDate.getTime());
    
    if (diff < minDiff && diff <= tolerance) {
      minDiff = diff;
      closest = point;
    }
  }
  
  return closest;
}

/**
 * Fetch fund's historical returns (1Y, 3Y, 5Y CAGR) from MFAPI
 */
export async function fetchHistoricalReturns(mfapiCode: number): Promise<{
  returns_1y: number | null;
  returns_3y: number | null;
  returns_5y: number | null;
  latest_nav: number | null;
  latest_date: string | null;
}> {
  try {
    const response = await fetch(`https://api.mfapi.in/mf/${mfapiCode}`);
    
    if (!response.ok) {
      console.error(`MFAPI fetch failed: ${response.status}`);
      return { returns_1y: null, returns_3y: null, returns_5y: null, latest_nav: null, latest_date: null };
    }
    
    const json: MFAPIResponse = await response.json();
    
    if (json.status !== "SUCCESS" || !json.data || json.data.length === 0) {
      console.error("MFAPI returned no data");
      return { returns_1y: null, returns_3y: null, returns_5y: null, latest_nav: null, latest_date: null };
    }
    
    // Data is sorted newest → oldest, so [0] is latest NAV
    const latest = json.data[0];
    const latestNav = parseFloat(latest.nav);
    const latestDate = parseDate(latest.date);
    
    // Calculate target dates
    const oneYearAgo = new Date(latestDate);
    oneYearAgo.setFullYear(latestDate.getFullYear() - 1);
    
    const threeYearsAgo = new Date(latestDate);
    threeYearsAgo.setFullYear(latestDate.getFullYear() - 3);
    
    const fiveYearsAgo = new Date(latestDate);
    fiveYearsAgo.setFullYear(latestDate.getFullYear() - 5);
    
    // Find NAVs at target dates
    const nav1y = getNavNearDate(json.data, oneYearAgo);
    const nav3y = getNavNearDate(json.data, threeYearsAgo);
    const nav5y = getNavNearDate(json.data, fiveYearsAgo);
    
    // Calculate CAGR
    const returns_1y = nav1y ? calculateCAGR(parseFloat(nav1y.nav), latestNav, 1) : null;
    const returns_3y = nav3y ? calculateCAGR(parseFloat(nav3y.nav), latestNav, 3) : null;
    const returns_5y = nav5y ? calculateCAGR(parseFloat(nav5y.nav), latestNav, 5) : null;
    
    return {
      returns_1y,
      returns_3y,
      returns_5y,
      latest_nav: latestNav,
      latest_date: latest.date,
    };
    
  } catch (error) {
    console.error("MFAPI fetch error:", error);
    return { returns_1y: null, returns_3y: null, returns_5y: null, latest_nav: null, latest_date: null };
  }
}
```

---

#### Step 2: Modify SipCalculator to accept fund context

**File:** `frontend/src/components/SipCalculator.tsx`

**Changes:**

1. **Add props interface (after line 40):**
```typescript
interface SipCalculatorProps {
  fundName?: string;      // e.g., "Mirae Asset Low Duration Fund"
  mfapiCode?: number;     // e.g., 118840
}
```

2. **Update component signature (line 116):**
```typescript
export default function SipCalculator({ fundName, mfapiCode }: SipCalculatorProps = {}) {
```

3. **Add state for fund-specific returns (after line 120):**
```typescript
const [fundReturns, setFundReturns] = useState<{
  returns_1y: number | null;
  returns_3y: number | null;
  returns_5y: number | null;
} | null>(null);
const [isLoadingReturns, setIsLoadingReturns] = useState(false);
```

4. **Add useEffect to fetch fund returns (after state declarations, ~line 125):**
```typescript
useEffect(() => {
  if (!mfapiCode) return;
  
  setIsLoadingReturns(true);
  
  import("@/lib/mfapi").then(({ fetchHistoricalReturns }) => {
    fetchHistoricalReturns(mfapiCode).then((data) => {
      setFundReturns(data);
      
      // Auto-select return rate based on active period
      const periodYears = PERIODS.find(p => p.label === activePeriod)?.years || 3;
      
      let suggestedRate = 12; // Default fallback
      
      if (periodYears <= 1 && data.returns_1y) {
        suggestedRate = data.returns_1y;
      } else if (periodYears <= 3 && data.returns_3y) {
        suggestedRate = data.returns_3y;
      } else if (data.returns_5y) {
        suggestedRate = data.returns_5y;
      } else if (data.returns_3y) {
        suggestedRate = data.returns_3y;
      } else if (data.returns_1y) {
        suggestedRate = data.returns_1y;
      }
      
      setReturnRate(Math.max(1, Math.min(40, suggestedRate)));
      setIsLoadingReturns(false);
    });
  });
}, [mfapiCode]); // Run only when mfapiCode changes
```

5. **Add fund context banner (before mode toggle, ~line 355):**
```typescript
{/* Fund context banner */}
{fundName && (
  <div style={{
    marginBottom: 16,
    padding: '12px 16px',
    background: '#1a1a1c',
    border: '1px solid #2c2c2e',
    borderRadius: 12,
    fontSize: 12,
    color: '#8e8e93',
    textAlign: 'center',
  }}>
    <p style={{ margin: 0, fontWeight: 600, color: '#00b386', marginBottom: 4 }}>
      {fundName}
    </p>
    <p style={{ margin: 0, fontSize: 11 }}>
      {isLoadingReturns ? (
        "Loading historical returns..."
      ) : fundReturns ? (
        `Historical: ${fundReturns.returns_1y ? `1Y: ${fundReturns.returns_1y}%` : ''} ${fundReturns.returns_3y ? `• 3Y: ${fundReturns.returns_3y}%` : ''} ${fundReturns.returns_5y ? `• 5Y: ${fundReturns.returns_5y}%` : ''}`
      ) : (
        "Historical returns unavailable"
      )}
    </p>
  </div>
)}
```

6. **Update disclaimer to reflect fund-specific mode (line 532-536):**
```typescript
<div style={S.disclaimer}>
  {fundName ? (
    `⚠️ Returns calculated using ${fundName}'s historical CAGR. Past performance does not guarantee future returns. Mathematical estimate only. Not investment advice.`
  ) : (
    "⚠️ This uses your entered return rate — not actual fund performance. Mathematical estimate only. Past performance does not guarantee future returns. Not investment advice."
  )}
</div>
```

---

#### Step 3: Pass fund context from Fund Detail page

**File:** `frontend/src/app/fund/[slug]/page.tsx`

Find where `<SipCalculator />` is rendered (likely in a tab or section), and modify:

```tsx
{/* BEFORE */}
<SipCalculator />

{/* AFTER */}
<SipCalculator 
  fundName={fundData?.scheme_name}
  mfapiCode={fundData?.mfapi_code}
/>
```

**Ensure `fundData` includes `mfapi_code`** — check if `useFundData` hook returns it. If not, add it to the fund registry.

---

#### Step 4: Verify fund registry has MFAPI codes

**File:** Check `backend/core/fund_registry.py` or wherever fund data is loaded

Ensure each fund object includes:
```python
{
  "scheme_name": "Mirae Asset Low Duration Fund",
  "mfapi_code": 118840,
  # ... other fields
}
```

These codes are already in `data/urls.yaml` — just ensure they're exposed via the API.

---

## 📋 Testing Checklist

### Week 1 Testing (Critical Fixes)

**Test 1: Math Projection Removal**
```bash
# Grep check
cd backend/core
grep -n "mathematical calculation\|SIP.*projection" generator.py
# Expected: 0 results

# API test
curl -X POST http://localhost:8000/api/threads/{thread_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Calculate SIP of 5000/month at 12% for 5 years"}'

# Expected: is_math_redirect: true, no calculation in response
```

**Test 2: MATH_QUERY Intent Classification**
```bash
cd backend/core
python query_guard.py --query "SIP calculator for 10000 monthly"
# Expected: intent=MATH_QUERY

python query_guard.py --query "What is expense ratio?"
# Expected: intent=FACTUAL

python query_guard.py --query "Should I invest?"
# Expected: intent=ADVISORY
```

**Test 3: Frontend Math Redirect Display**
1. Open chat widget
2. Type: "Calculate SIP of 5000 for 3 years"
3. Expected: Button "Open SIP Calculator" or "Scroll to Calculator ↓"

**Test 4: Groww Boilerplate Removal**
```bash
# After re-ingestion
grep -A3 '"chunk_index": 0' data/chunks.jsonl | grep -i "stocks mutual funds fixed deposits"
# Expected: 0 results
```

---

### Week 2 Testing (Fund-Specific Calculator)

**Test 1: MFAPI Returns Fetch**
```bash
# Browser console on fund detail page
fetch('https://api.mfapi.in/mf/118840')
  .then(r => r.json())
  .then(d => console.log(d))
# Expected: {status: "SUCCESS", data: [{date, nav}, ...]}
```

**Test 2: Auto-Populated Return Rate**
1. Navigate to `/fund/mirae-asset-low-duration-fund`
2. Open SIP Calculator tab
3. Expected:
   - Fund name banner: "Mirae Asset Low Duration Fund"
   - Historical returns shown: "1Y: X% • 3Y: Y% • 5Y: Z%"
   - Return rate slider pre-filled with fund's 3Y CAGR
   - Disclaimer mentions fund name

**Test 3: Generic Calculator Still Works**
1. Open calculator from Home page (not fund detail)
2. Expected: No fund banner, manual return rate input, generic disclaimer

---

## 📁 Files Modified Summary

### Backend
```
backend/core/generator.py         — Remove math projection from SYSTEM_PROMPT
backend/core/query_guard.py       — Add MATH_QUERY intent + patterns
backend/api/routes/messages.py    — Handle is_math_redirect
backend/store/thread_store.py     — Add is_math_redirect field
ingestion/scraper.py              — Add _strip_groww_nav function
```

### Frontend
```
frontend/src/lib/api.ts           — Add is_math_redirect to Message interface
frontend/src/lib/mfapi.ts         — NEW FILE — MFAPI historical returns fetcher
frontend/src/components/SipCalculator.tsx  — Fund-specific calculator
frontend/src/app/fund/[slug]/page.tsx      — Pass fund context to calculator
```

### Documentation
```
Docs/edge-cases.md                — Document MATH_QUERY intent
Docs/deployment-plan.md           — Note MFAPI CORS requirements
```

---

## 🎯 Success Criteria

### Week 1 (Critical Fixes)
- [ ] Generator SYSTEM_PROMPT has NO math calculation instructions
- [ ] Query guard classifies SIP calculator queries as MATH_QUERY
- [ ] Frontend shows "Open SIP Calculator" button for math queries
- [ ] Chunk index 0 has NO Groww navigation boilerplate

### Week 2 (Fund-Specific Calculator)
- [ ] Calculator auto-fetches fund's 1Y/3Y/5Y CAGR from MFAPI
- [ ] Return rate slider pre-fills with fund's historical CAGR
- [ ] Fund name + historical returns displayed in calculator banner
- [ ] Disclaimer mentions fund name when in fund-specific mode
- [ ] Generic calculator still works on Home page (no fund context)

---

## ⚠️ Critical Reminders

1. **NEVER hardcode API keys** — always use `.env`
2. **Test both modes** — fund-specific AND generic calculator
3. **MFAPI has rate limits** — cache responses if hitting limits
4. **CORS**: MFAPI allows cross-origin requests, but verify in production
5. **Edge case**: NFO funds have no historical data → show "N/A" gracefully

---

## 🚀 Deployment Notes

After implementing all fixes:

1. **Re-run ingestion** to regenerate chunks without Groww boilerplate:
   ```bash
   cd ingestion
   python scraper.py
   python chunker.py
   python embedder.py
   python vector_store.py
   ```

2. **Restart backend** to load updated generator.py:
   ```bash
   cd backend
   uvicorn main:app --reload
   ```

3. **Rebuild frontend** for production:
   ```bash
   cd frontend
   npm run build
   ```

4. **Smoke test**:
   - Query: "Calculate SIP" → should redirect to calculator
   - Query: "What is expense ratio" → should answer factually
   - Open calculator on fund page → should show fund's CAGR

---

## 📞 Support

For antigravity implementation, provide:
1. This full `improvement.md` file
2. Specific file paths where changes are needed
3. Clear BEFORE/AFTER code blocks
4. Test commands for validation

All code blocks are production-ready and can be copy-pasted directly.