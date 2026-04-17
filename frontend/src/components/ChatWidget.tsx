/**
 * ChatWidget.tsx — Floating Chatbot Widget
 * Collapsible side panel for the RAG FAQ assistant.
 */
"use client";

import { useRef, useEffect } from "react";
import { ChatWindow } from "./ChatWindow";
import { SendBar } from "./SendBar";
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
      {/* Floating Action Button */}
      {!isOpen && (
        <button className="chat-fab" onClick={onToggle} aria-label="Open AI Assistant">
          💬
        </button>
      )}

      {/* Side Panel */}
      {isOpen && (
        <aside className="chat-panel">
          <header className="chat-panel-header">
            <div className="chat-panel-header-info">
              <div className="chat-panel-header-dot"></div>
              <div>
                <h3>MiraeExplorer AI</h3>
                <p>Online & Ready</p>
              </div>
            </div>
            <button className="chat-panel-close" onClick={onToggle} aria-label="Close">
              ✕
            </button>
          </header>

          <div className="chat-panel-messages">
             <div className="chat-panel-disclaimer">
                💡 <strong>Facts-only AI:</strong> I can help with fund details, 
                tax rules, and SIP calculations. No investment advice.
             </div>
             
             <ChatWindow 
                messages={activeMessages}
                isLoading={isLoading}
                hasActiveThread={activeThreadId !== null}
                onSend={handleSend}
                onExampleClick={handleExample}
             />
          </div>
         </aside>
      )}
    </>
  );
}
