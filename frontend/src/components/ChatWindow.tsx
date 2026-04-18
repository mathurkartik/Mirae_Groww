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
    <>
      {/* Message list / Welcome screen */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3" role="log" aria-live="polite" aria-label="Conversation">
        {isEmpty ? (
          <WelcomeScreen onQuestion={onExampleClick} />
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.message_id} message={msg} />
            ))}

            {/* Loading indicator */}
            {isLoading && (
              <div className="chat-msg-row chat-msg-row--assistant" aria-label="Assistant is responding">
                <div className="chat-msg-avatar" aria-hidden="true">AI</div>
                <div className="chat-bubble chat-bubble--assistant">
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
    </>
  );
}
