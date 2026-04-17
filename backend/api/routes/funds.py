"""
backend/api/routes/funds.py — Fund Explorer REST API
=====================================================
Endpoints for the mutual fund explorer frontend.

  GET  /api/funds                        → list all funds with summary metrics
  GET  /api/funds/categories             → list categories with fund counts
  GET  /api/funds/category/{slug}        → funds in a specific category
  GET  /api/funds/{slug}                 → full fund detail
  GET  /api/funds/{slug}/nav-history     → historical NAV (proxied from MFAPI.in)
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException, Query

from backend.core.fund_registry import (
    get_all_funds,
    get_categories,
    get_fund_by_slug,
    get_funds_by_category,
)

log = logging.getLogger("funds")
router = APIRouter(prefix="/funds", tags=["funds"])

# ── NAV history cache (in-memory, 1hr TTL) ───────────────────────────────────
_NAV_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 3600  # 1 hour


# ── GET /api/funds ───────────────────────────────────────────────────────────

@router.get("", summary="List all funds with summary metrics")
def list_funds(
    category: Optional[str] = Query(None, description="Filter by category slug"),
    sort_by: Optional[str] = Query(None, description="Sort by: returns_3y, aum, expense_ratio, name"),
    limit: Optional[int] = Query(None, description="Limit number of results"),
) -> dict:
    """
    Returns all funds with summary-level data suitable for fund cards.
    Supports filtering by category and sorting.
    """
    if category:
        funds = get_funds_by_category(category)
    else:
        funds = get_all_funds()

    # Create summary dicts (exclude heavy fields like top_holdings, peers)
    summaries = []
    for f in funds:
        summaries.append({
            "slug": f["slug"],
            "scheme_name": f["scheme_name"],
            "category": f["category"],
            "category_slug": f["category_slug"],
            "source_url": f["source_url"],
            "mfapi_code": f.get("mfapi_code"),
            "nav": f.get("nav"),
            "nav_date": f.get("nav_date"),
            "nav_change_1d": f.get("nav_change_1d"),
            "aum": f.get("aum"),
            "expense_ratio": f.get("expense_ratio"),
            "rating": f.get("rating"),
            "min_sip": f.get("min_sip"),
            "risk_level": f.get("risk_level"),
            "returns_3y_annualized": f.get("returns_3y_annualized"),
            "returns": f.get("returns", {}),
        })

    # Sort
    if sort_by == "returns_3y":
        summaries.sort(
            key=lambda x: float((x.get("returns_3y_annualized") or "0").replace("%", "").replace("+", "")),
            reverse=True,
        )
    elif sort_by == "aum":
        def _parse_aum(val):
            if not val:
                return 0
            return float(val.replace(",", "").replace(" Cr", "").strip())
        summaries.sort(key=lambda x: _parse_aum(x.get("aum")), reverse=True)
    elif sort_by == "expense_ratio":
        summaries.sort(
            key=lambda x: float((x.get("expense_ratio") or "999").replace("%", "")),
        )
    elif sort_by == "name":
        summaries.sort(key=lambda x: x.get("scheme_name", ""))

    if limit:
        summaries = summaries[:limit]

    return {"funds": summaries, "total": len(summaries)}


# ── GET /api/funds/categories ────────────────────────────────────────────────

@router.get("/categories", summary="List categories with fund counts")
def list_categories() -> dict:
    """Returns all fund categories with display metadata and fund counts."""
    return {"categories": get_categories()}


# ── GET /api/funds/category/{slug} ───────────────────────────────────────────

@router.get("/category/{category_slug}", summary="Funds in a specific category")
def funds_by_category(category_slug: str) -> dict:
    """Returns all funds in a specific category by its slug."""
    funds = get_funds_by_category(category_slug)
    if not funds:
        raise HTTPException(status_code=404, detail=f"Category '{category_slug}' not found or has no funds")

    # Get category metadata
    categories = get_categories()
    cat_meta = next((c for c in categories if c["slug"] == category_slug), None)

    summaries = []
    for f in funds:
        summaries.append({
            "slug": f["slug"],
            "scheme_name": f["scheme_name"],
            "category": f["category"],
            "category_slug": f["category_slug"],
            "source_url": f["source_url"],
            "mfapi_code": f.get("mfapi_code"),
            "nav": f.get("nav"),
            "nav_date": f.get("nav_date"),
            "nav_change_1d": f.get("nav_change_1d"),
            "aum": f.get("aum"),
            "expense_ratio": f.get("expense_ratio"),
            "rating": f.get("rating"),
            "min_sip": f.get("min_sip"),
            "risk_level": f.get("risk_level"),
            "returns_3y_annualized": f.get("returns_3y_annualized"),
            "returns": f.get("returns", {}),
        })

    return {
        "category": cat_meta,
        "funds": summaries,
        "total": len(summaries),
    }


# ── GET /api/funds/{slug} ───────────────────────────────────────────────────

@router.get("/{slug}", summary="Get full fund detail")
def fund_detail(slug: str) -> dict:
    """Returns complete fund detail including holdings, peers, and all metrics."""
    fund = get_fund_by_slug(slug)
    if not fund:
        raise HTTPException(status_code=404, detail=f"Fund '{slug}' not found")
    return {"fund": fund}


# ── GET /api/funds/{slug}/nav-history ────────────────────────────────────────

@router.get("/{slug}/nav-history", summary="Historical NAV data")
def nav_history(
    slug: str,
    period: str = Query("1Y", description="Period: 1M, 6M, 1Y, 3Y, 5Y, ALL"),
) -> dict:
    """
    Returns historical NAV data by proxying MFAPI.in.
    Results are cached for 1 hour to be respectful to the free API.
    """
    fund = get_fund_by_slug(slug)
    if not fund:
        raise HTTPException(status_code=404, detail=f"Fund '{slug}' not found")

    mfapi_code = fund.get("mfapi_code")
    if not mfapi_code:
        raise HTTPException(
            status_code=404,
            detail=f"No MFAPI scheme code configured for '{fund['scheme_name']}'",
        )

    # Check cache
    cache_key = f"{mfapi_code}:{period}"
    if cache_key in _NAV_CACHE:
        cached_ts, cached_data = _NAV_CACHE[cache_key]
        if time.time() - cached_ts < _CACHE_TTL:
            return cached_data

    # Fetch from MFAPI.in
    try:
        url = f"https://api.mfapi.in/mf/{mfapi_code}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as exc:
        log.warning("MFAPI.in request failed for %s: %s", mfapi_code, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch NAV data from MFAPI.in: {exc}",
        )

    if raw.get("status") != "SUCCESS":
        raise HTTPException(status_code=502, detail="MFAPI.in returned non-success status")

    # Parse and filter by period
    all_data = []
    for entry in raw.get("data", []):
        try:
            from datetime import datetime
            dt = datetime.strptime(entry["date"], "%d-%m-%Y")
            all_data.append({
                "date": dt.strftime("%Y-%m-%d"),
                "nav": float(entry["nav"]),
                "_dt": dt,
            })
        except (ValueError, KeyError):
            continue

    # Sort chronologically
    all_data.sort(key=lambda x: x["_dt"])

    # Filter by period
    if all_data and period != "ALL":
        from datetime import timedelta
        latest_dt = all_data[-1]["_dt"]
        period_map = {
            "1M": timedelta(days=30),
            "3M": timedelta(days=90),
            "6M": timedelta(days=180),
            "1Y": timedelta(days=365),
            "3Y": timedelta(days=365 * 3),
            "5Y": timedelta(days=365 * 5),
        }
        delta = period_map.get(period, timedelta(days=365))
        cutoff = latest_dt - delta
        all_data = [d for d in all_data if d["_dt"] >= cutoff]

    # Remove internal _dt field
    result_data = [{"date": d["date"], "nav": d["nav"]} for d in all_data]

    result = {
        "scheme_name": fund["scheme_name"],
        "mfapi_code": mfapi_code,
        "period": period,
        "data_points": len(result_data),
        "data": result_data,
    }

    # Cache the result
    _NAV_CACHE[cache_key] = (time.time(), result)

    return result
