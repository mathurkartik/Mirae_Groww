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
  const isFundPage = typeof window !== "undefined" && window.location.pathname.includes("/fund/");

  if (isUser) {
    return (
      <div className="chat-msg-row chat-msg-row--user">
        <div className="chat-bubble chat-bubble--user">
          <p>{message.content}</p>
        </div>
      </div>
    );
  }

  const isError = message.content.startsWith("⚠️");

  return (
    <div className="chat-msg-row chat-msg-row--assistant">
      <div className="chat-msg-avatar" aria-hidden="true">AI</div>

      <div className={`chat-bubble chat-bubble--assistant ${isError ? "chat-bubble--error" : ""}`}>
        {message.is_refusal && !isError && (
          <span className="refusal-badge" style={{ display: 'block', fontSize: '10px', opacity: 0.7, marginBottom: '4px' }}>
            Advisory query — facts only
          </span>
        )}
        <p>{message.content}</p>

        {message.is_math_redirect && (
          <a
            href={isFundPage ? "#sip-calculator" : "/"}
            className="mt-2 inline-flex items-center gap-2 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 
                       border border-zinc-700 rounded-lg text-sm text-zinc-300 
                       hover:text-white transition-colors cursor-pointer"
          >
            {isFundPage ? "Scroll to Calculator ↓" : "Explore funds to calculate →"}
          </a>
        )}

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
