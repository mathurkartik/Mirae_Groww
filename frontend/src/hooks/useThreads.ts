/**
 * src/hooks/useThreads.ts
 * Central client-side state: threads + per-thread messages.
 * No localStorage — pure React state as per spec.
 */

"use client";

import { useCallback, useReducer, useRef } from "react";
import * as api from "@/lib/api";
import type { Thread, Message, SendMessageResponse } from "@/lib/api";

// ─── State Shape ─────────────────────────────────────────────────────────────

export interface ThreadMeta extends Thread {
  /** Title derived from the first user message, or null for brand new threads */
  title: string | null;
}

interface State {
  threads: ThreadMeta[];
  activeThreadId: string | null;
  /** Per-thread message arrays keyed by thread_id */
  messages: Record<string, Message[]>;
  /** Which thread_id is currently awaiting a response */
  loadingThreadId: string | null;
  /** Per-thread error strings */
  errors: Record<string, string>;
}

// ─── Actions ──────────────────────────────────────────────────────────────────

type Action =
  | { type: "ADD_THREAD"; thread: ThreadMeta }
  | { type: "REMOVE_THREAD"; threadId: string }
  | { type: "SET_ACTIVE"; threadId: string }
  | { type: "ADD_MESSAGE"; threadId: string; message: Message }
  | { type: "SET_LOADING"; threadId: string | null }
  | { type: "SET_ERROR"; threadId: string; error: string }
  | { type: "CLEAR_ERROR"; threadId: string }
  | { type: "SET_THREAD_TITLE"; threadId: string; title: string };

// ─── Reducer ─────────────────────────────────────────────────────────────────

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "ADD_THREAD":
      return {
        ...state,
        threads: [action.thread, ...state.threads],
        messages: { ...state.messages, [action.thread.thread_id]: [] },
      };

    case "REMOVE_THREAD": {
      const threads = state.threads.filter(
        (t) => t.thread_id !== action.threadId
      );
      const messages = { ...state.messages };
      delete messages[action.threadId];
      const errors = { ...state.errors };
      delete errors[action.threadId];
      const activeThreadId =
        state.activeThreadId === action.threadId
          ? threads[0]?.thread_id ?? null
          : state.activeThreadId;
      return { ...state, threads, messages, errors, activeThreadId };
    }

    case "SET_ACTIVE":
      return { ...state, activeThreadId: action.threadId };

    case "ADD_MESSAGE": {
      const existing = state.messages[action.threadId] ?? [];
      return {
        ...state,
        messages: {
          ...state.messages,
          [action.threadId]: [...existing, action.message],
        },
      };
    }

    case "SET_LOADING":
      return { ...state, loadingThreadId: action.threadId };

    case "SET_ERROR":
      return {
        ...state,
        errors: { ...state.errors, [action.threadId]: action.error },
      };

    case "CLEAR_ERROR": {
      const errors = { ...state.errors };
      delete errors[action.threadId];
      return { ...state, errors };
    }

    case "SET_THREAD_TITLE":
      return {
        ...state,
        threads: state.threads.map((t) =>
          t.thread_id === action.threadId ? { ...t, title: action.title } : t
        ),
      };

    default:
      return state;
  }
}

const initialState: State = {
  threads: [],
  activeThreadId: null,
  messages: {},
  loadingThreadId: null,
  errors: {},
};

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useThreads() {
  const [state, dispatch] = useReducer(reducer, initialState);
  // Track in-flight fetch controllers per thread for cancellation
  const controllersRef = useRef<Record<string, AbortController>>({});

  // ── createLocalThread ────────────────────────────────────────────────────
  /**
   * Creates a client-side-only thread without a backend call.
   * Used as a fallback when the backend is unreachable on first load.
   * Any message sent on this thread will fail gracefully with an error bubble.
   */
  const createLocalThread = useCallback(() => {
    const localId = `local-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const meta: ThreadMeta = {
      thread_id: localId,
      created_at: new Date().toISOString(),
      title: null,
    };
    dispatch({ type: "ADD_THREAD", thread: meta });
    dispatch({ type: "SET_ACTIVE", threadId: localId });
    return localId;
  }, []);

  // ── createThread ─────────────────────────────────────────────────────────
  const createThread = useCallback(async () => {
    try {
      const thread = await api.createThread();
      const meta: ThreadMeta = { ...thread, title: null };
      dispatch({ type: "ADD_THREAD", thread: meta });
      dispatch({ type: "SET_ACTIVE", threadId: thread.thread_id });
      return thread.thread_id;
    } catch (err) {
      console.error("createThread:", err);
      return null;
    }
  }, []);

  // ── deleteThread ─────────────────────────────────────────────────────────
  const deleteThread = useCallback(async (threadId: string) => {
    try {
      await api.deleteThread(threadId);
    } catch {
      // ignore 404 — thread may have already been removed
    }
    dispatch({ type: "REMOVE_THREAD", threadId });
  }, []);

  // ── switchThread ─────────────────────────────────────────────────────────
  const switchThread = useCallback(
    (threadId: string) => {
      // Cancel any in-flight request for a different thread
      const prev = state.activeThreadId;
      if (prev && prev !== threadId && controllersRef.current[prev]) {
        controllersRef.current[prev].abort();
        delete controllersRef.current[prev];
      }
      dispatch({ type: "SET_ACTIVE", threadId });
    },
    [state.activeThreadId]
  );

  // ── sendMessage ──────────────────────────────────────────────────────────
  const sendMessage = useCallback(
    async (threadId: string, content: string) => {
      if (!content.trim()) return;

      dispatch({ type: "CLEAR_ERROR", threadId });

      // Optimistic user message
      const userMsg: Message = {
        message_id: `local-${Date.now()}`,
        role: "user",
        content: content.trim(),
        timestamp: new Date().toISOString(),
      };
      dispatch({ type: "ADD_MESSAGE", threadId, message: userMsg });

      // Set title from first user message
      const msgs = state.messages[threadId] ?? [];
      if (msgs.length === 0) {
        const title =
          content.trim().length > 50
            ? content.trim().slice(0, 47) + "…"
            : content.trim();
        dispatch({ type: "SET_THREAD_TITLE", threadId, title });
      }

      dispatch({ type: "SET_LOADING", threadId });

      try {
        const response: SendMessageResponse = await api.sendMessage(
          threadId,
          content.trim()
        );

        const assistantMsg: Message = {
          message_id: response.message_id,
          role: "assistant",
          content: response.content,
          citation: response.citation,
          last_updated: response.last_updated,
          timestamp: response.timestamp,
          is_refusal: response.is_refusal,
          is_math_redirect: response.is_math_redirect,
          intent: response.intent,
        };
        dispatch({ type: "ADD_MESSAGE", threadId, message: assistantMsg });
      } catch (err) {
        const errorMsg =
          err instanceof Error ? err.message : "Something went wrong.";
        dispatch({ type: "SET_ERROR", threadId, error: errorMsg });

        // Add error as a synthetic assistant message so it appears in chat
        const errBubble: Message = {
          message_id: `err-${Date.now()}`,
          role: "assistant",
          content: `⚠️ ${errorMsg}`,
          timestamp: new Date().toISOString(),
          is_refusal: false,
        };
        dispatch({ type: "ADD_MESSAGE", threadId, message: errBubble });
      } finally {
        dispatch({ type: "SET_LOADING", threadId: null });
      }
    },
    [state.messages]
  );

  // ── Derived helpers ───────────────────────────────────────────────────────
  const activeMessages =
    state.activeThreadId != null
      ? (state.messages[state.activeThreadId] ?? [])
      : [];

  const isLoading =
    state.loadingThreadId !== null &&
    state.loadingThreadId === state.activeThreadId;

  return {
    threads: state.threads,
    activeThreadId: state.activeThreadId,
    activeMessages,
    isLoading,
    errors: state.errors,
    createThread,
    createLocalThread,
    deleteThread,
    switchThread,
    sendMessage,
  };
}
