/**
 * useFundData.ts — Data fetching hooks for Mutual Fund Explorer
 * Uses standard fetch with React state for simplicity.
 */
"use client";

import { useState, useEffect, useCallback } from "react";
import * as api from "@/lib/api";
import type { FundSummary, Category, FundDetail, NavPoint } from "@/lib/api";

export function useFunds(categorySlug?: string) {
  const [funds, setFunds] = useState<FundSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchFunds = useCallback(async () => {
    setIsLoading(true);
    try {
      const resp = await api.getFunds(categorySlug);
      setFunds(resp.funds);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load funds");
    } finally {
      setIsLoading(false);
    }
  }, [categorySlug]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchFunds();
  }, [fetchFunds]);

  return { funds, isLoading, error, refresh: fetchFunds };
}

export function useCategories() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCats = async () => {
      try {
        const resp = await api.getCategories();
        setCategories(resp.categories);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load categories");
      } finally {
        setIsLoading(false);
      }
    };
    fetchCats();
  }, []);

  return { categories, isLoading, error };
}

export function useCategoryDetail(slug: string) {
  const [data, setData] = useState<{ category: Category; funds: FundSummary[] } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const resp = await api.getFundsByCategory(slug);
        setData(resp);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load category data");
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [slug]);

  return { data, isLoading, error };
}

export function useFundDetail(slug: string) {
  const [fund, setFund] = useState<FundDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const resp = await api.getFundDetail(slug);
        setFund(resp.fund);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load fund details");
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [slug]);

  return { fund, isLoading, error };
}

export function useNavHistory(slug: string, period: string = "1Y") {
  const [history, setHistory] = useState<NavPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const resp = await api.getNavHistory(slug, period);
        setHistory(resp.data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load NAV history");
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [slug, period]);

  return { history, isLoading, error };
}
