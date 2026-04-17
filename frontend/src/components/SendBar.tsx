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
    <div className="chat-send-bar">
      <div className="chat-send-inner" style={{ flex: 1, position: 'relative' }}>
        <textarea
          ref={textareaRef}
          id="chat-input"
          className="chat-input-field"
          placeholder="Ask a factual question..."
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          maxLength={MAX_CHARS}
          style={{ width: '100%', resize: 'none', paddingRight: '46px' }}
        />

        <button
          id="send-button"
          className="chat-send-btn-inset"
          onClick={handleSend}
          disabled={!canSend}
          aria-label="Send message"
          type="button"
        >
          {disabled ? (
            <div className="loading-dots mini"><span></span><span></span><span></span></div>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" width="18" height="18">
              <line x1="12" y1="19" x2="12" y2="5" />
              <polyline points="5 12 12 5 19 12" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
