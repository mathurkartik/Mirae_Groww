/**
 * SendBar.tsx
 * Auto-resizing textarea input with send button.
 * - Enter → send, Shift+Enter → newline
 * - Disabled while loading
 * - Character counter near 1000-char limit
 */
"use client";

import { useRef, useState, useCallback, KeyboardEvent, ChangeEvent } from "react";

interface Props {
  onSend: (content: string) => void;
  disabled?: boolean;
}

const MAX_CHARS = 1000;
const WARN_AT = 850;

export function SendBar({ onSend, disabled = false }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 180) + "px";
  }, []);

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    if (e.target.value.length > MAX_CHARS) return;
    setValue(e.target.value);
    resize();
  };

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    }, 0);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const charCount = value.length;
  const nearLimit = charCount >= WARN_AT;
  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div className="send-bar">
      <div className="send-bar-inner">
        <textarea
          ref={textareaRef}
          id="chat-input"
          className="send-input"
          placeholder="Ask a factual question about Mirae Asset funds…"
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          aria-label="Message input"
          aria-describedby="char-counter"
          maxLength={MAX_CHARS}
        />

        <div className="send-bar-actions">
          {nearLimit && (
            <span
              id="char-counter"
              className={`char-counter ${charCount >= MAX_CHARS ? "char-counter--limit" : ""}`}
              aria-live="polite"
            >
              {charCount}/{MAX_CHARS}
            </span>
          )}

          <button
            id="send-button"
            className="send-btn"
            onClick={handleSend}
            disabled={!canSend}
            aria-label="Send message"
            type="button"
          >
            {disabled ? (
              /* Spinner when loading */
              <svg
                className="send-btn-spinner"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
              </svg>
            ) : (
              /* Arrow-up icon */
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <line x1="12" y1="19" x2="12" y2="5" />
                <polyline points="5 12 12 5 19 12" />
              </svg>
            )}
          </button>
        </div>
      </div>

      <p className="send-hint">
        Press <kbd>Enter</kbd> to send &middot; <kbd>Shift+Enter</kbd> for new line
      </p>
    </div>
  );
}
