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
