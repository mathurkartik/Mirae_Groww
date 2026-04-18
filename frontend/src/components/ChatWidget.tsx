/**
 * ChatWidget.tsx — Atelier Advisor Redesign
 * Professional AI advisor interface for Emerald Ledger.
 */
"use client";

import { useRef, useEffect } from "react";
import { ChatWindow } from "./ChatWindow";
import { useThreads } from "@/hooks/useThreads";

interface ChatWidgetProps {
  isOpen: boolean;
  onToggle: () => void;
}

export function ChatWidget({ isOpen, onToggle }: ChatWidgetProps) {
  const {
    activeThreadId,
    activeMessages,
    isLoading,
    createThread,
    sendMessage,
    createLocalThread,
  } = useThreads();

  const didInit = useRef(false);

  useEffect(() => {
    if (!isOpen || didInit.current) return;
    didInit.current = true;
    const init = async () => {
       const id = await createThread();
       if (!id) createLocalThread();
    };
    init();
  }, [isOpen, createThread, createLocalThread]);

  const handleSend = (content: string) => {
    if (activeThreadId) sendMessage(activeThreadId, content);
  };

  const handleExample = (question: string) => {
    if (activeThreadId) sendMessage(activeThreadId, question);
  };

  return (
    <>
      {/* Floating Action Button */}
      {!isOpen && (
        <button 
          className="chat-fab" 
          onClick={onToggle} 
          aria-label="Atelier Advisor"
          style={{ 
             background: 'var(--bg-dark-green)', 
             boxShadow: '0 8px 32px rgba(6, 78, 59, 0.3)',
             fontSize: '20px'
          }}
        >
          ✨
        </button>
      )}

      {/* Side Panel */}
      {isOpen && (
        <aside className="chat-panel" style={{ width: '380px', borderRadius: '16px 0 0 16px', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column' }}>
          {/* Header */}
          <header className="chat-panel-header" style={{ background: 'var(--bg-dark-green)', padding: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px' }}>✨</div>
              <div>
                <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 800, color: 'white' }}>Atelier Advisor</h3>
                <span style={{ fontSize: '9px', fontWeight: 800, color: 'var(--accent-light)', letterSpacing: '0.05em' }}>ACTIVE INSIGHT</span>
              </div>
            </div>
            <button className="chat-panel-close" onClick={onToggle} style={{ opacity: 0.7 }}>✕</button>
          </header>

          {/* Body */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#f8fafc' }}>
            <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0 0' }}>
               <span style={{ fontSize: '9px', fontWeight: 800, color: 'var(--text-muted)', border: '1px solid var(--border)', padding: '3px 10px', borderRadius: '20px', background: 'white', letterSpacing: '0.05em' }}>
                  ONLINE AI INTEL
               </span>
            </div>
            
            <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <ChatWindow 
                messages={activeMessages}
                isLoading={isLoading}
                hasActiveThread={activeThreadId !== null}
                onSend={handleSend}
                onExampleClick={handleExample}
              />
            </div>
          </div>

          {/* Footer */}
          <div style={{ padding: '8px 20px 12px', textAlign: 'center', flexShrink: 0, borderTop: '1px solid var(--border-light)' }}>
             <p style={{ margin: 0, fontSize: '10px', color: 'var(--text-muted)', fontWeight: 600 }}>
                &quot;Facts-only. No investment advice.&quot;
             </p>
          </div>
        </aside>
      )}
    </>
  );
}
