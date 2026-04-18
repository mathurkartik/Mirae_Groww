# Walkthrough: Emerald Ledger — Frontend Redesign

> **Date:** April 19, 2026
> **Version:** 3.0 (formerly "MiraeExplorer")
> **Brand:** Emerald Ledger / Sovereign Analyst
> **AI Assistant:** Atelier Advisor (Active Insight)

---

## Overview

The entire frontend has been redesigned from "MiraeExplorer" (Groww-green light theme) to **Emerald Ledger** — a professional, institutional-grade mutual fund analytics platform with a "Sovereign Analyst" design language.

---

## 🏛️ Design System Changes

| Before (MiraeExplorer) | After (Emerald Ledger) |
|---|---|
| Accent: `#00b386` (Groww green) | Accent: `#00a884` / Dark: `#047857` (Deep Emerald) |
| Sidebar width: `220px` | Sidebar width: `240px` |
| Single layout for all pages | **Dual-layout** (Global vs Fund Detail) |
| Brand: "MiraeExplorer" | Brand: "Emerald Ledger / SOVEREIGN ANALYST" |
| Chat: "MiraeExplorer AI" | Chat: "Atelier Advisor / ACTIVE INSIGHT" |
| Text colors: `#1a1a2e`, `#94a3b8` | Text colors: `#0f172a`, `#334155`, `#64748b` (higher contrast) |

### New CSS Tokens Added
- `--bg-dark-green: #064e3b` — used for dark accent cards, AI recommendation blocks
- `--accent-light: #d1fae5` — used for badges and highlight surfaces

---

## 📐 Layout Architecture Changes

### Global Layout (Home / Category pages)
- **Left Sidebar**: Emerald Ledger brand + "SOVEREIGN ANALYST" label, nav links (Explore, Investments, SIP Dashboard, Watchlist, Reports), AI Assistant button, Settings/Support links, user profile card ("Alex Mercer / PRO TIER")
- **Top Nav (inside content pane)**: Search bar, category pills (DIRECT FUNDS / ETFS / GOLD / FIXED INCOME), notification/profile icons, "Invest Now" CTA

### Fund Detail Layout
- **Full-width Top Nav**: Emerald Ledger logo, Markets/Funds/Insights/Institutional links, Support + "Invest Now" CTA
- **Left Sidebar (under top nav)**: "Mirae Asset / DEEP DIVE ANALYST" brand, section nav (Overview/Performance/Holdings/Risk Metrics/Calculators), AI Recommendation card, Reports/Settings links

---

## 📄 Page-by-Page Changes

### Home Page (`/`)
- "Discover Mutual Funds" heading in dark green
- Filter pills: ALL CATEGORIES / HIGH RETURN / TOP RATED / SIP WITH ₹500
- Category cards with icon backgrounds, fund counts, and "VIEW ALL" links
- **New**: Dark green "Can't decide where to invest?" AI Advisor CTA card
- **New**: "Top 10 Active Funds" table with ratings and 3Y returns
- **New**: Right column with NFO (New Fund Offers) and Watchlist modules
- **New**: Footer with INVESTMENTS / INSIGHTS / COMPANY / LEGAL columns + disclaimer

### Category Page (`/category/[slug]`)
- Breadcrumb navigation: `INVESTMENTS / EQUITY MUTUAL FUNDS`
- **New**: "Market Sentiment: Bullish" status banner with NIFTY 50 and SENSEX data
- Category filter pills: MIRAE ASSET PICKS / LARGE CAP / MID CAP / SMALL CAP / TAX SAVER
- Sort dropdown: Best 3Y Returns / Largest AUM / Alphabetical
- "LOAD MORE PICKS" button

### Fund Detail Page (`/fund/[slug]`)
- Breadcrumb: `MUTUAL FUNDS / MIRAE ASSET / [CATEGORY]`
- **Header**: Fund name (32px bold), equity badge, star rating, NAV with daily change arrow
- **Top Section (2 columns)**:
  - Left: Investment Objective + metrics grid (Min Investment, Expense Ratio, AUM, Exit Load)
  - Right: "GROWTH OF ₹10,000" chart with period selector pills (1M/6M/1Y/3Y/ALL)
- **Returns Calculator**: Full-width section with slider UI + historical returns table
- **Bottom Stats (3 columns)**: Risk Profile (bar visualization), Asset Allocation (progress bars), Fund Managers
- **Holdings & Peers**: Existing `HoldingsTable` and `PeerComparison` components preserved

### Key Fund Metrics Preserved
All original data points are rendered in the new layout:
- ✅ Expense Ratio
- ✅ AUM (Fund Size)
- ✅ Exit Load (with regex parsing for % and duration)
- ✅ Minimum SIP/Investment
- ✅ Investment Objective
- ✅ Benchmark
- ✅ Top Holdings
- ✅ Peer Comparison
- ✅ NAV with 1-day change
- ✅ Historical Returns by period

---

## ✨ AI Assistant Changes (Atelier Advisor)

### ChatWidget
- **FAB**: Dark green (`#064e3b`) with ✨ sparkle icon instead of 💬
- **Panel**: 420px width, rounded corners, dark emerald header
- **Header**: "Atelier Advisor" with "ACTIVE INSIGHT" badge
- **Footer disclaimer**: "Facts-only. No investment advice."

### MessageBubble
- **User messages**: Dark emerald background (`var(--bg-dark-green)`) with white text
- **Assistant messages**: White cards with subtle border, "Atelier Assistant" avatar label below
- **Refusal badge**: "ADVISORY QUERY — FACTS ONLY" in emerald

### WelcomeScreen
- ✨ icon in dark green square logo
- "Sovereign-grade analysis on fund details, fees, and regulatory facts."
- 3 example questions in bordered cards
- "INSTITUTIONAL DATA SOURCE • MIRAE ASSET" footer

---

## 🔧 Technical Fixes Applied

| Fix | Details |
|---|---|
| Dead imports removed | `ReturnCalculator` and `SipCalculator` imports cleaned from fund detail page |
| Exit Load metric restored | Was lost during redesign — re-added with regex parsing |
| Duplicate type deduplicated | `FundSummary` interface moved to single canonical source (`@/lib/api`) |
| CSS property typos fixed | `marginbottom` → `marginBottom`, `justifycontent` → `justifyContent` |
| Branding updated | CSS file header, sidebar labels, chat widget all updated |

---

## ✅ Build & Deployment

- **TypeScript**: `npm run build` passes with zero type errors
- **Static generation**: All 4 routes (`/`, `/_not-found`, `/category/[slug]`, `/fund/[slug]`) generate successfully
- **Deployment**: Auto-deployed to Vercel via `main` branch push
- **CI/CD**: GitHub Actions scheduler + Render deploy hook pipeline remains unchanged

---

> **Disclaimer:** Facts-only. No investment advice.
