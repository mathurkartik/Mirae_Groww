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
      <div 
        role="log" 
        aria-live="polite" 
        aria-label="Conversation"
        style={{
           flex: 1,
           overflowY: 'auto',
           padding: '24px',
           display: 'flex',
           flexDirection: 'column',
           gap: '16px'
        }}
      >
        {isEmpty ? (
          <WelcomeScreen onQuestion={onExampleClick} />
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.message_id} message={msg} />
            ))}

            {/* Loading indicator */}
            {isLoading && (
              <div aria-label="Assistant is responding" style={{ marginBottom: '24px', position: 'relative' }}>
                <div style={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
                  <div style={{ background: 'white', border: '1px solid var(--border)', padding: '16px 20px', borderRadius: '24px 24px 24px 4px', maxWidth: '90%', boxShadow: '0 4px 16px rgba(0,0,0,0.03)', display: 'inline-block', width: 'fit-content' }}>
                     <LoadingDots />
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px', paddingLeft: '4px' }}>
                    <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px' }}>✨</div>
                    <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-muted)' }}>Atelier Assistant</span>
                  </div>
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
