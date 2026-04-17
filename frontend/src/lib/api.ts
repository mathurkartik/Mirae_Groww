/**
 * src/lib/api.ts
 * Typed API client for the Mutual Fund FAQ Assistant backend.
 * Requests go through the Next.js rewrite proxy (/api/*) which forwards to
 * NEXT_PUBLIC_API_URL (FastAPI on Render/localhost:8000).
 * This avoids CORS preflight in both dev and production (Vercel).
 */

// Always use relative /api path — Next.js rewrite handles backend URL
const BASE = "";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Thread {
  thread_id: string;
  created_at: string;
  message_count?: number;
}

export interface Message {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  citation?: string | null;
  last_updated?: string | null;
  timestamp: string;
  is_refusal?: boolean;
  intent?: string | null;
}

export interface SendMessageResponse extends Message {
  thread_id: string;
  retrieval_count?: number;
}

export interface FundSummary {
  slug: string;
  scheme_name: string;
  category: string;
  category_slug: string;
  source_url: string;
  mfapi_code: number | null;
  nav: number | null;
  nav_date: string | null;
  nav_change_1d: string | null;
  aum: string | null;
  expense_ratio: string | null;
  rating: number | null;
  min_sip: string | null;
  risk_level: string | null;
  returns_3y_annualized: string | null;
  returns: Record<string, string>;
}

export interface Category {
  name: string;
  slug: string;
  display_name: string;
  icon: string;
  description: string;
  color: string;
  fund_count: number;
}

export interface FundDetail extends FundSummary {
  objective: string | null;
  benchmark: string | null;
  exit_load: string | null;
  holdings_count: number | null;
  top_holdings: Array<{
    name: string;
    sector: string;
    instrument: string;
    allocation: string;
  }>;
  peers: Array<{
    name: string;
    return_1y: string | null;
    return_3y: string | null;
    fund_size: string | null;
  }>;
}

export interface NavPoint {
  date: string;
  nav: number;
}

export interface ApiError {
  detail: string;
  retry_after_seconds?: number;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = (await res.json()) as ApiError;
      detail = err.detail ?? detail;
      if (err.retry_after_seconds) {
        detail += ` — retry after ${err.retry_after_seconds}s`;
      }
    } catch {
      // non-JSON error body
    }
    throw new Error(detail);
  }

  return res.json() as Promise<T>;
}

// ─── Thread endpoints ────────────────────────────────────────────────────────

export async function createThread(): Promise<Thread> {
  return request<Thread>("/api/threads", { method: "POST", body: "{}" });
}

export async function listThreads(): Promise<{ threads: Thread[] }> {
  return request<{ threads: Thread[] }>("/api/threads");
}

export async function deleteThread(threadId: string): Promise<void> {
  await request<unknown>(`/api/threads/${threadId}`, { method: "DELETE" });
}

// ─── Message endpoints ────────────────────────────────────────────────────────

export async function sendMessage(
  threadId: string,
  content: string
): Promise<SendMessageResponse> {
  return request<SendMessageResponse>(`/api/threads/${threadId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export async function getMessages(
  threadId: string
): Promise<{ thread_id: string; message_count: number; messages: Message[] }> {
  return request(`/api/threads/${threadId}/messages`);
}

// ─── Health ──────────────────────────────────────────────────────────────────

export async function getHealth(): Promise<Record<string, unknown>> {
  return request("/api/health");
}

// ─── Fund endpoints ──────────────────────────────────────────────────────────

export async function getFunds(category?: string): Promise<{ funds: FundSummary[] }> {
  const query = category ? `?category=${category}` : "";
  return request(`/api/funds${query}`);
}

export async function getCategories(): Promise<{ categories: Category[] }> {
  return request("/api/funds/categories");
}

export async function getFundsByCategory(slug: string): Promise<{ category: Category; funds: FundSummary[] }> {
  return request(`/api/funds/category/${slug}`);
}

export async function getFundDetail(slug: string): Promise<{ fund: FundDetail }> {
  return request(`/api/funds/${slug}`);
}

export async function getNavHistory(slug: string, period: string = "1Y"): Promise<{ data: NavPoint[] }> {
  return request(`/api/funds/${slug}/nav-history?period=${period}`);
}
