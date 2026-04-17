"use client";

import { useState, useEffect } from "react";
import type { FundSummary } from "@/lib/api";

const WATCHLIST_KEY = "mirae_explorer_watchlist";

export function useWatchlist() {
  const [watchlist, setWatchlist] = useState<FundSummary[]>([]);

  // Load on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(WATCHLIST_KEY);
      if (stored) {
        setWatchlist(JSON.parse(stored));
      }
    } catch (e) {
      console.error("Failed to load watchlist", e);
    }
  }, []);

  const addToWatchlist = (fund: FundSummary) => {
    setWatchlist((prev) => {
      // Prevent duplicates
      if (prev.some((f) => f.slug === fund.slug)) return prev;
      const next = [...prev, fund];
      localStorage.setItem(WATCHLIST_KEY, JSON.stringify(next));
      return next;
    });
  };

  const removeFromWatchlist = (slug: string) => {
    setWatchlist((prev) => {
      const next = prev.filter((f) => f.slug !== slug);
      localStorage.setItem(WATCHLIST_KEY, JSON.stringify(next));
      return next;
    });
  };

  const isInWatchlist = (slug: string) => {
    return watchlist.some((f) => f.slug === slug);
  };

  return {
    watchlist,
    addToWatchlist,
    removeFromWatchlist,
    isInWatchlist,
  };
}
