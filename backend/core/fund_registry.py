"""
backend/core/fund_registry.py — Structured Fund Data Registry
==============================================================
Parses urls.yaml and cleaned_docs.jsonl at startup to build an in-memory
catalog of all Mirae Asset mutual funds with structured metrics.

Used by the /api/funds/* endpoints to serve the explorer frontend.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import yaml

log = logging.getLogger("fund_registry")

_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent
_URLS_YAML = _ROOT / "data" / "urls.yaml"
_CLEANED_JSONL = _ROOT / "data" / "cleaned_docs.jsonl"

# ── In-memory cache ──────────────────────────────────────────────────────────
_FUND_CATALOG: list[dict[str, Any]] = []
_FUND_BY_SLUG: dict[str, dict[str, Any]] = {}
_CATEGORIES: list[dict[str, Any]] = []
_INITIALIZED = False


# ── Category metadata ────────────────────────────────────────────────────────
CATEGORY_META = {
    "Equity / Core": {
        "display_name": "Equity",
        "slug": "equity",
        "icon": "trending-up",
        "description": "High growth potential investments primarily in the stock market for long-term wealth.",
        "color": "#00b386",
    },
    "Sectoral": {
        "display_name": "Sectoral",
        "slug": "sectoral",
        "icon": "layers",
        "description": "Focused investments in specific sectors like banking, healthcare, and consumer goods.",
        "color": "#6366f1",
    },
    "Index / Passive": {
        "display_name": "Index & Passive",
        "slug": "index-passive",
        "icon": "bar-chart",
        "description": "Low-cost funds tracking market indices for passive, diversified investing.",
        "color": "#f59e0b",
    },
    "Debt": {
        "display_name": "Debt",
        "slug": "debt",
        "icon": "shield",
        "description": "Stable returns and lower risk, investing in government and corporate bonds.",
        "color": "#3b82f6",
    },
    "Target Maturity": {
        "display_name": "Target Maturity",
        "slug": "target-maturity",
        "icon": "calendar",
        "description": "Fixed-duration debt funds aligned to specific maturity dates for predictable returns.",
        "color": "#8b5cf6",
    },
}


def _slug_from_url(url: str) -> str:
    """Extract slug from Groww URL."""
    return urlparse(url).path.rstrip("/").split("/")[-1]


def _extract_metric(text: str, pattern: str) -> Optional[str]:
    """Extract a metric value from cleaned text using regex."""
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _parse_nav(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract NAV value and date from cleaned text."""
    # Pattern: NAV: 16 Apr '26\n₹124.18
    nav_date_match = re.search(r"NAV:\s*(.+?)[\n\r]", text)
    nav_val_match = re.search(r"NAV:.*?[\n\r]\s*₹([\d,.]+)", text)
    nav_date = nav_date_match.group(1).strip() if nav_date_match else None
    nav_val = nav_val_match.group(1).strip().replace(",", "") if nav_val_match else None
    return nav_val, nav_date


def _parse_returns(text: str) -> dict[str, Optional[str]]:
    """Extract annualized returns from the returns table."""
    returns = {}
    # Look for "Fund returns | +12.8% | +12.2% | +14.3% | +15.3%"
    fund_returns = re.search(
        r"Fund returns\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^\n]*)",
        text,
    )
    if fund_returns:
        vals = [v.strip() for v in fund_returns.groups()]
        # The header row tells us which periods
        header = re.search(
            r"Name\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^\n]*)",
            text,
        )
        if header:
            periods = [h.strip() for h in header.groups()]
            for period, val in zip(periods, vals):
                if period and val and val != "--":
                    returns[period] = val
    return returns


def _parse_holdings_count(text: str) -> Optional[int]:
    """Extract number of holdings."""
    match = re.search(r"Holdings?\s*\((\d+)\)", text)
    return int(match.group(1)) if match else None


def _parse_top_holdings(text: str, limit: int = 10) -> list[dict]:
    """Extract top holdings from the holdings table."""
    holdings = []
    # Pattern: "HDFC Bank Ltd. | Financial | Equity | 9.23%"
    section = re.search(r"Holdings?\s*\(\d+\)(.*?)(?:See All|Minimum investments)", text, re.DOTALL)
    if not section:
        return holdings

    lines = section.group(1).strip().split("\n")
    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4 and "%" in parts[-1]:
            try:
                alloc = float(parts[-1].replace("%", "").strip())
                if alloc > 0:
                    holdings.append({
                        "name": parts[0],
                        "sector": parts[1],
                        "instrument": parts[2],
                        "allocation": parts[-1],
                    })
            except ValueError:
                continue
        if len(holdings) >= limit:
            break
    return holdings


def _parse_fund_detail(record: dict, url_entry: dict) -> dict[str, Any]:
    """Parse a cleaned_docs.jsonl record into structured fund data."""
    text = record.get("cleaned_text", "")
    slug = _slug_from_url(record["source_url"])

    nav_val, nav_date = _parse_nav(text)

    # Extract key metrics
    aum_match = re.search(r"Fund size \(AUM\)\s*[\n\r]\s*₹?([\d,.]+\s*Cr)", text)
    expense_match = re.search(r"Expense ratio\s*[\n\r]\s*([\d.]+%)", text)
    rating_match = re.search(r"Rating\s*[\n\r]\s*(\d+|--)", text)
    min_sip_match = re.search(r"Min\.\s*for SIP\s*[\n\r]\s*₹?([\d,]+)", text)
    risk_match = re.search(r"rated\s+([\w\s]+)\s+risk", text, re.IGNORECASE)

    # Extract 3Y annualized return from top of page
    ret_3y_match = re.search(r"([+-][\d.]+)\s*%\s*[\n\r]\s*3Y annualised", text)

    # Extract 1D change
    ret_1d_match = re.search(r"([+-][\d.]+)\s*%\s*[\n\r]\s*1D", text)

    # Exit load
    exit_load_match = re.search(r"Exit load\s*[\n\r]+\s*(.+?)(?:\n|$)", text, re.IGNORECASE)

    # Fund benchmark
    benchmark_match = re.search(r"Fund benchmark\s*[\n\r]+\s*(.+?)(?:\n|$)", text)

    # Investment objective
    objective_match = re.search(
        r"Investment Objective\s*[\n\r]+\s*(.+?)(?:\n(?:Fund benchmark|;)|$)",
        text,
        re.DOTALL,
    )

    # Fund manager
    manager_match = re.search(r"Fund management.*?([A-Z]{2})([A-Za-z\s]+?)(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", text, re.DOTALL)

    returns = _parse_returns(text)
    holdings_count = _parse_holdings_count(text)
    top_holdings = _parse_top_holdings(text)

    # Parse peer comparison
    peers = []
    peer_section = re.search(r"Compare similar funds(.*?)Compare", text, re.DOTALL)
    if peer_section:
        for line in peer_section.group(1).strip().split("\n"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4 and "%" in parts[1]:
                peers.append({
                    "name": parts[0].strip(" |"),
                    "return_1y": parts[1] if len(parts) > 1 else None,
                    "return_3y": parts[2] if len(parts) > 2 else None,
                    "fund_size": parts[3] if len(parts) > 3 else None,
                })

    return {
        "slug": slug,
        "scheme_name": url_entry["scheme_name"],
        "category": url_entry["category"],
        "category_slug": CATEGORY_META.get(url_entry["category"], {}).get("slug", "other"),
        "source_url": record["source_url"],
        "mfapi_code": url_entry.get("mfapi_code"),
        "nav": float(nav_val) if nav_val else None,
        "nav_date": nav_date,
        "nav_change_1d": ret_1d_match.group(1) + "%" if ret_1d_match else None,
        "aum": aum_match.group(1) if aum_match else None,
        "expense_ratio": expense_match.group(1) if expense_match else None,
        "rating": int(rating_match.group(1)) if rating_match and rating_match.group(1) != "--" else None,
        "min_sip": "₹" + min_sip_match.group(1) if min_sip_match else None,
        "risk_level": risk_match.group(1).strip().title() if risk_match else None,
        "returns_3y_annualized": ret_3y_match.group(1) + "%" if ret_3y_match else None,
        "returns": returns,
        "exit_load": exit_load_match.group(1).strip() if exit_load_match else None,
        "benchmark": benchmark_match.group(1).strip() if benchmark_match else None,
        "objective": objective_match.group(1).strip().rstrip(";").strip() if objective_match else None,
        "holdings_count": holdings_count,
        "top_holdings": top_holdings,
        "peers": peers,
        "scrape_date": record.get("scrape_date"),
    }


def initialize() -> None:
    """Load and parse fund data from urls.yaml + cleaned_docs.jsonl."""
    global _FUND_CATALOG, _FUND_BY_SLUG, _CATEGORIES, _INITIALIZED

    if _INITIALIZED:
        return

    # Load URL entries
    if not _URLS_YAML.exists():
        log.warning("urls.yaml not found at %s", _URLS_YAML)
        _INITIALIZED = True
        return

    with _URLS_YAML.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    url_entries = config.get("urls", [])

    # Build URL→entry lookup
    url_to_entry = {e["url"]: e for e in url_entries}

    # Load cleaned docs
    if not _CLEANED_JSONL.exists():
        log.warning("cleaned_docs.jsonl not found at %s", _CLEANED_JSONL)
        # Fall back to basic data from urls.yaml only
        for entry in url_entries:
            slug = _slug_from_url(entry["url"])
            fund = {
                "slug": slug,
                "scheme_name": entry["scheme_name"],
                "category": entry["category"],
                "category_slug": CATEGORY_META.get(entry["category"], {}).get("slug", "other"),
                "source_url": entry["url"],
                "mfapi_code": entry.get("mfapi_code"),
                "nav": None, "nav_date": None, "nav_change_1d": None,
                "aum": None, "expense_ratio": None, "rating": None,
                "min_sip": None, "risk_level": None,
                "returns_3y_annualized": None, "returns": {},
                "exit_load": None, "benchmark": None, "objective": None,
                "holdings_count": None, "top_holdings": [], "peers": [],
                "scrape_date": None,
            }
            _FUND_CATALOG.append(fund)
            _FUND_BY_SLUG[slug] = fund
    else:
        with _CLEANED_JSONL.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("status") != "ok":
                    continue
                url = record["source_url"]
                entry = url_to_entry.get(url)
                if not entry:
                    continue

                fund = _parse_fund_detail(record, entry)
                _FUND_CATALOG.append(fund)
                _FUND_BY_SLUG[fund["slug"]] = fund

    # Build category summaries
    cat_counts: dict[str, int] = {}
    for fund in _FUND_CATALOG:
        cat = fund["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    _CATEGORIES = []
    for cat_name, meta in CATEGORY_META.items():
        _CATEGORIES.append({
            "name": cat_name,
            "slug": meta["slug"],
            "display_name": meta["display_name"],
            "icon": meta["icon"],
            "description": meta["description"],
            "color": meta["color"],
            "fund_count": cat_counts.get(cat_name, 0),
        })

    _INITIALIZED = True
    log.info(
        "Fund registry loaded: %d funds, %d categories",
        len(_FUND_CATALOG),
        len(_CATEGORIES),
    )


# ── Public API ────────────────────────────────────────────────────────────────

def get_all_funds() -> list[dict[str, Any]]:
    """Return summary data for all funds."""
    initialize()
    return _FUND_CATALOG


def get_fund_by_slug(slug: str) -> Optional[dict[str, Any]]:
    """Return full detail for a single fund by its URL slug."""
    initialize()
    return _FUND_BY_SLUG.get(slug)


def get_categories() -> list[dict[str, Any]]:
    """Return category list with fund counts."""
    initialize()
    return _CATEGORIES


def get_funds_by_category(category_slug: str) -> list[dict[str, Any]]:
    """Return all funds in a given category."""
    initialize()
    return [f for f in _FUND_CATALOG if f.get("category_slug") == category_slug]
