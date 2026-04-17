/**
 * ThreadSidebar.tsx
 * Left panel — thread list, create, switch, delete.
 * Thread title is derived from the first user message (set in useThreads).
 */
"use client";

import type { ThreadMeta } from "@/hooks/useThreads";

interface Props {
  threads: ThreadMeta[];
  activeThreadId: string | null;
  onNew: () => void;
  onSwitch: (threadId: string) => void;
  onDelete: (threadId: string) => void;
  isCreating?: boolean;
}

export function ThreadSidebar({
  threads,
  activeThreadId,
  onNew,
  onSwitch,
  onDelete,
  isCreating = false,
}: Props) {
  return (
    <aside className="sidebar" aria-label="Conversation threads">
      {/* Header */}
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <span className="sidebar-brand-dot" aria-hidden="true" />
          <span className="sidebar-brand-name">MiraeAI</span>
        </div>
        <button
          id="new-thread-btn"
          className="new-thread-btn"
          onClick={onNew}
          disabled={isCreating}
          aria-label="Create new thread"
          type="button"
        >
          {isCreating ? (
            <span className="new-thread-btn-spinner" aria-hidden="true" />
          ) : (
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          )}
          New thread
        </button>
      </div>

      {/* Thread list */}
      <nav className="thread-list" aria-label="Your threads">
        {threads.length === 0 && (
          <p className="thread-list-empty">No threads yet. Create one above.</p>
        )}

        {threads.map((t) => {
          const isActive = t.thread_id === activeThreadId;
          const label = t.title ?? "New thread";
          return (
            <div
              key={t.thread_id}
              className={`thread-item ${isActive ? "thread-item--active" : ""}`}
              role="listitem"
            >
              <button
                id={`thread-${t.thread_id}`}
                className="thread-item-btn"
                onClick={() => onSwitch(t.thread_id)}
                aria-current={isActive ? "page" : undefined}
                aria-label={`Switch to thread: ${label}`}
                type="button"
              >
                <span className="thread-item-icon" aria-hidden="true">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" opacity="0.6">
                    <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" />
                  </svg>
                </span>
                <span className="thread-item-title">{label}</span>
              </button>

              <button
                className="thread-delete-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(t.thread_id);
                }}
                aria-label={`Delete thread: ${label}`}
                type="button"
              >
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  aria-hidden="true"
                >
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <p className="sidebar-footer-text">Mirae Asset · Groww data only</p>
      </div>
    </aside>
  );
}
