/**
 * ChatWindow.tsx
 * Main message area. Shows WelcomeScreen when empty.
 * Auto-scrolls to bottom on new messages.
 * Accepts AbortController ref for request cancellation on thread switch.
 */
"use client";

import { useEffect, useRef } from "react";
import type { Message } from "@/lib/api";
import { MessageBubble } from "./MessageBubble";
import { WelcomeScreen } from "./WelcomeScreen";
import { LoadingDots } from "./LoadingDots";
import { SendBar } from "./SendBar";

interface Props {
  messages: Message[];
  isLoading: boolean;
  hasActiveThread: boolean;
  onSend: (content: string) => void;
  onExampleClick: (q: string) => void;
}

export function ChatWindow({
  messages,
  isLoading,
  hasActiveThread,
  onSend,
  onExampleClick,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom whenever messages change or loading starts
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (!hasActiveThread) {
    return (
      <div className="chat-window chat-window--empty">
        <div className="no-thread-placeholder">
          <p>Select a thread or create a new one to get started.</p>
        </div>
      </div>
    );
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="chat-window">
      {/* Message list / Welcome screen */}
      <div className="chat-scroll" role="log" aria-live="polite" aria-label="Conversation">
        {isEmpty ? (
          <WelcomeScreen onQuestion={onExampleClick} />
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.message_id} message={msg} />
            ))}

            {/* Loading indicator */}
            {isLoading && (
              <div className="msg-row msg-row--assistant" aria-label="Assistant is responding">
                <div className="assistant-avatar" aria-hidden="true">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z" />
                  </svg>
                </div>
                <div className="bubble bubble--assistant bubble--loading">
                  <LoadingDots />
                </div>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} aria-hidden="true" />
      </div>

      {/* Send bar — always visible at bottom */}
      <SendBar onSend={onSend} disabled={isLoading} />
    </div>
  );
}
