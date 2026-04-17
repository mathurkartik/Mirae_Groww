/**
 * MessageBubble.tsx
 * Renders a single chat message — user or assistant.
 * Assistant messages include:
 *   - Answer text
 *   - Citation link (opens in new tab)
 *   - "Last updated from sources: <date>" footer
 *   - Refusal badge when is_refusal is true
 */
import type { Message } from "@/lib/api";

interface Props {
  message: Message;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="msg-row msg-row--user">
        <div className="bubble bubble--user">
          <p className="bubble-text">{message.content}</p>
        </div>
      </div>
    );
  }

  const isError = message.content.startsWith("⚠️");

  return (
    <div className="msg-row msg-row--assistant">
      {/* Avatar */}
      <div className="assistant-avatar" aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z" />
        </svg>
      </div>

      <div className={`bubble bubble--assistant ${isError ? "bubble--error" : ""}`}>
        {/* Refusal badge */}
        {message.is_refusal && !isError && (
          <span className="refusal-badge">Advisory query — facts only</span>
        )}

        {/* Answer text */}
        <p className="bubble-text">{message.content}</p>

        {/* Citation link */}
        {message.citation && (
          <a
            href={message.citation}
            target="_blank"
            rel="noopener noreferrer"
            className="citation-link"
            aria-label={`Source: ${message.citation}`}
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
              <polyline points="15 3 21 3 21 9" />
              <line x1="10" y1="14" x2="21" y2="3" />
            </svg>
            <span className="citation-text">View source</span>
          </a>
        )}

        {/* Last updated footer */}
        {message.last_updated && (
          <p className="last-updated">
            Last updated from sources:{" "}
            <time dateTime={message.last_updated}>{message.last_updated}</time>
          </p>
        )}
      </div>
    </div>
  );
}
