/**
 * ChatWidget.tsx — Atelier Advisor Redesign
 * Professional AI advisor interface for Emerald Ledger.
 */
"use client";

import { useRef, useEffect, useState } from "react";
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

  // Auto-initialize a thread if none exists
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
      {/* Floating Action Button - Dark Green Logo Style */}
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

      {/* Side Panel - Atelier Advisor Look */}
      {isOpen && (
        <aside className="chat-panel" style={{ width: '420px', borderRadius: '16px 0 0 16px', border: '1px solid var(--border)' }}>
          <header className="chat-panel-header" style={{ background: 'var(--bg-dark-green)', padding: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '20px' }}>✨</div>
              <div>
                <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 800, color: 'white', letterSpacing: '-0.01em' }}>Atelier Advisor</h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                  <span style={{ fontSize: '9px', fontWeight: 800, color: 'var(--accent-light)', letterSpacing: '0.05em' }}>ACTIVE INSIGHT</span>
                </div>
              </div>
            </div>
            <button className="chat-panel-close" onClick={onToggle} style={{ opacity: 0.7 }}>✕</button>
          </header>

          <div className="flex-1 flex flex-col overflow-hidden" style={{ background: '#f8fafc' }}>
            <div className="flex flex-col h-full">
              <div className="px-6 pt-6">
                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '20px' }}>
                   <span style={{ fontSize: '9px', fontWeight: 800, color: 'var(--text-muted)', border: '1px solid var(--border)', padding: '4px 12px', borderRadius: '20px', background: 'white', letterSpacing: '0.05em' }}>
                      ONLINE AI INTEL
                   </span>
                </div>
              </div>
              
              <ChatWindow 
                messages={activeMessages}
                isLoading={isLoading}
                hasActiveThread={activeThreadId !== null}
                onSend={handleSend}
                onExampleClick={handleExample}
              />

              <div style={{ padding: '12px 24px', textAlign: 'center' }}>
                 <p style={{ margin: 0, fontSize: '10px', color: 'var(--text-muted)', fontWeight: 600 }}>
                    &quot;Facts-only. No investment advice.&quot;
                 </p>
              </div>
            </div>
          </div>
        </aside>
      )}
    </>
  );
}
