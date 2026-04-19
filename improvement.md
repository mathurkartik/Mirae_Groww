# Calculator Improvement Plan: Context-Aware Fund Returns

The current Mutual Fund detail page uses a generic calculator with a hardcoded return rate (default 12%). This improvement will replace the generic calculator with a context-aware `ReturnCalculator` that automatically utilizes the historical returns of the specific fund being viewed.

## Proposed Changes

### 1. Frontend: Fund Detail Page
**File**: `frontend/src/app/fund/[slug]/page.tsx`
- Remove the manual ROI slider and manual math helpers (`calcSIP`, `fmtINR`).
- Import and use the `ReturnCalculator` component.
- Pass the fund's actual historical returns (`fund.returns`) to the component.

### 2. Frontend: Return Calculator Component
**File**: `frontend/src/components/ReturnCalculator.tsx`
- Ensure the component handles various return periods (6M, 1Y, 3Y, 5Y) gracefully.
- Add a fallback if a specific period is missing from the fund data.

## Implementation Details
The `ReturnCalculator` will be integrated into the existing "Returns Calculator" section on the fund detail page. This will provide users with realistic projections based on the actual performance of the fund, such as "Mirae Asset Low Duration Fund", rather than a generic estimated rate.

## Verification
- Visit the detail page for "Mirae Asset Low Duration Fund".
- Verify that the calculator loads returns specific to that fund (e.g., if the fund has 8.5% 1Y return, the calculator should default to or show that).
- Ensure the SIP and Lump-sum toggles work correctly with these rates.
