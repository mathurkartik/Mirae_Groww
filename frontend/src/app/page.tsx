/**
 * page.tsx — Main chat interface
 * "use client" because all state lives in useThreads (React state, no localStorage).
 * Renders: ThreadSidebar | ChatWindow
 * On mount, creates the first thread automatically.
 * Falls back to a local-only thread if the backend is unreachable.
 */
"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useThreads } from "@/hooks/useThreads";
import { ThreadSidebar } from "@/components/ThreadSidebar";
import { ChatWindow } from "@/components/ChatWindow";

export default function Home() {
  const {
    threads,
    activeThreadId,
    activeMessages,
    isLoading,
    createThread,
    deleteThread,
    switchThread,
    sendMessage,
    createLocalThread,
  } = useThreads();

  const [isCreating, setIsCreating] = useState(false);
  const didInit = useRef(false);

  // Create an initial thread on first mount.
  // If the backend is unreachable, fall back to a local-only thread
  // so the WelcomeScreen (with example questions) is always visible.
  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;
    handleNewThread();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleNewThread = useCallback(async () => {
    setIsCreating(true);
    try {
      const id = await createThread();
      // If backend call failed, create a local placeholder thread
      if (!id) createLocalThread();
    } finally {
      setIsCreating(false);
    }
  }, [createThread, createLocalThread]);

  const handleSend = useCallback(
    (content: string) => {
      if (!activeThreadId) return;
      sendMessage(activeThreadId, content);
    },
    [activeThreadId, sendMessage]
  );

  const handleExample = useCallback(
    (question: string) => {
      if (!activeThreadId) return;
      sendMessage(activeThreadId, question);
    },
    [activeThreadId, sendMessage]
  );

  return (
    <main className="app-shell">
      {/* Left sidebar */}
      <ThreadSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onNew={handleNewThread}
        onSwitch={switchThread}
        onDelete={deleteThread}
        isCreating={isCreating}
      />

      {/* Main chat area */}
      <ChatWindow
        messages={activeMessages}
        isLoading={isLoading}
        hasActiveThread={activeThreadId !== null}
        onSend={handleSend}
        onExampleClick={handleExample}
      />
    </main>
  );
}
