# Plan: Home Page Overhaul & Data Integrity Fix

We will refine the "Discover Mutual Funds" experience to be data-driven based on your specific ranking requirements (High Return, Top Rated, etc.), fix the chatbot layout issues, and ensure all fund metrics are correctly parsed from the Groww data.

## User Review Required

> [!IMPORTANT]
> - **Watchlist Persistence**: I will implement the "Add to Watchlist" feature using your browser's Local Storage. This means your watchlist will stay even if you refresh the page, without needing a login.
> - **Ranking Logic**:
>   - **High Return**: Sorted by the highest 3-Year Annualized Return.
>   - **Top Rated**: Sorted by the "Rating" (1-5 stars).
>   - **SIP with ₹500**: Filtered for funds where `min_sip` is ₹500 or less.
> - **Navigation**: "Investments" (top) and "Explore" (side) will be removed as requested.

## Proposed Changes

### [Component] Backend API (Discovery & Data)

#### [MODIFY] [fund_registry.py](file:///c:/Users/KartikMathur/Desktop/Project\M2\backend\core\fund_registry.py)
- Refactor regex to be extremely permissive with whitespace (`\s+`) to capture NAV, AUM, and Expense Ratio regardless of the source page layout.
- [NEW] Add `get_discovery_funds()` to curate:
  - `top_returns`: Top 10 by 3Y return.
  - `top_rated`: Top 10 by rating.
  - `sip_affordable`: Funds with SIP <= 500.
  - `newest`: The 3 most recently scraped funds.

#### [MODIFY] [funds.py](file:///c:/Users/KartikMathur/Desktop/Project\M2\backend\api\routes\funds.py)
- [NEW] Add `GET /api/funds/discovery` endpoint.

### [Component] Frontend UI (Navigation & Home)

#### [MODIFY] [AppShell.tsx](file:///c:/Users/KartikMathur/Desktop/Project\M2\frontend\src\components\AppShell.tsx)
- Remove "Investments" from top navbar.
- Remove "Explore" from sidebar.

#### [MODIFY] [page.tsx](file:///c:/Users/KartikMathur/Desktop/Project\M2\frontend\src\app\page.tsx)
- Connect filter pills (High Return, etc.) to the new discovery data.
- Remove the "Invest in Better Tomorrow" banner.
- Rename "Watchlist History" to "Watchlist".
- [NEW] Add "Add to Watchlist" button logic to fund cards.

### [Component] Chatbot Fix

#### [MODIFY] [ChatWidget.tsx](file:///c:/Users/KartikMathur/Desktop/Project\M2\frontend\src\components\ChatWidget.tsx)
- Remove the duplicate `SendBar` component at the bottom of the panel.
- Fix header styling to ensure it's not overlapping.

## Verification Plan

### Automated Tests
- `pytest backend/test_api.py` to verify the discovery endpoint returns the correct counts.

### Manual Verification
- Verify that **High Return** pill shows the top 5 funds by return rate.
- Verify that clicking "Add to Watchlist" on a fund card updates the Watchlist tile in the sidebar.
- Verify that the Chatbot has only **one** input box at the bottom.
- Check a "Target Maturity" fund and verify **AUM** and **Expense Ratio** are finally populated.
