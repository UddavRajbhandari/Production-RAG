'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import Navbar from '@/components/Navbar';
import UploadPanel from '@/components/UploadPanel';
import ChatPanel from '@/components/ChatPanel';
import PastQueries from '@/components/PastQueries';
import StartupSkeleton from '@/components/StartupSkeleton';
import { getActiveSession, getSession, createSession, setActiveSession, updateSessionMessages, updateSessionFiles, getStoredTenantId, setStoredTenantId } from '@/lib/storage';
import type { ChatMessage } from '@/types';

export default function HomePage() {
  const [backendReady, setBackendReady] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionFiles, setSessionFiles] = useState<{ name: string; timestamp: number }[]>([]);
  const [showLeft, setShowLeft] = useState(true);
  const healthAttempts = useRef(0);

  // Poll health endpoint until backend is ready
  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const base = process.env.NEXT_PUBLIC_API_URL || '';
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        const res = await fetch(`${base}/api/v1/health/live`, {
          method: 'GET',
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        if (cancelled) return;
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'alive') {
            setBackendReady(true);
            return;
          }
        }
      } catch {
        // Backend not ready yet
      }
      if (cancelled) return;
      healthAttempts.current += 1;
      if (healthAttempts.current < 90) {
        setTimeout(check, 2000);
      }
    };

    check();
    return () => { cancelled = true; };
  }, []);

  // Initialize session on mount (only after backend is ready)
  useEffect(() => {
    if (!backendReady) return;
    let session = getActiveSession();
    if (!session) {
      session = createSession();
    }
    setCurrentSessionId(session.id);
    setMessages(session.messages);
    setSessionFiles(session.files);
  }, [backendReady]);

  // Auto-init app session — always call /session/init, passing stored tenant_id
  // so the backend re-issues a cookie for the same tenant (data is preserved)
  // across server restarts or cookie expiry.
  useEffect(() => {
    if (!backendReady) return;

    const init = async () => {
      try {
        const storedTenantId = getStoredTenantId();
        const base = process.env.NEXT_PUBLIC_API_URL || '';
        const res = await fetch(`${base}/api/v1/session/init`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(
            storedTenantId ? { tenant_id: storedTenantId } : {}
          ),
        });
        if (!res.ok) return;
        const data = await res.json() as { tenant_id: string };
        setStoredTenantId(data.tenant_id);
      } catch {
        // will retry on next page load
      }
    };
    init();
  }, [backendReady]);

  const handleSelectSession = useCallback((id: string) => {
    const session = getSession(id);
    if (!session) return;
    setCurrentSessionId(id);
    setMessages(session.messages);
    setSessionFiles(session.files);
    setActiveSession(id);
  }, []);

  const handleNewChat = useCallback(() => {
    const session = createSession();
    setCurrentSessionId(session.id);
    setMessages([]);
    setSessionFiles([]);
  }, []);

  const handleMessagesChange = useCallback((newMessages: ChatMessage[]) => {
    setMessages(newMessages);
  }, []);

  const handleFilesChange = useCallback((files: { name: string; timestamp: number }[]) => {
    setSessionFiles(files);
  }, []);

  // Persist messages on change
  useEffect(() => {
    if (currentSessionId && messages.length > 0) {
      updateSessionMessages(currentSessionId, messages);
    }
  }, [messages, currentSessionId]);

  // Persist session files on change
  useEffect(() => {
    if (currentSessionId) {
      updateSessionFiles(currentSessionId, sessionFiles);
    }
  }, [sessionFiles, currentSessionId]);

  if (!backendReady) {
    return <StartupSkeleton />;
  }

  return (
    <div key="app-content" className="min-h-screen animate-fade-in bg-background-primary">
      <Navbar />
      <div className="mx-auto flex max-w-[1600px] pt-13">
        {/* Left Sidebar */}
        <aside
          className={`flex w-64 shrink-0 flex-col border-r border-border bg-background-surface transition-transform duration-200 ${
            showLeft ? 'translate-x-0' : '-translate-x-64'
          } hidden md:flex`}
          style={{ height: 'calc(100vh - 3.25rem)' }}
        >
          <div className="flex flex-1 flex-col overflow-y-auto">
            <UploadPanel
              sessionId={currentSessionId || ''}
              sessionFiles={sessionFiles}
              onFilesChange={handleFilesChange}
            />
            <PastQueries
              currentSessionId={currentSessionId}
              onSelectSession={handleSelectSession}
              onNewChat={handleNewChat}
            />
          </div>
        </aside>

        {/* Mobile Left Sidebar overlay */}
        <aside
          className={`fixed inset-0 z-30 transition-opacity duration-200 md:hidden ${
            showLeft ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
          }`}
        >
          <div className="absolute inset-0 bg-black/50" onClick={() => setShowLeft(false)} />
          <div
            className={`relative h-full w-72 max-w-[85vw] bg-background-surface border-r border-border transition-transform duration-200 ${
              showLeft ? 'translate-x-0' : '-translate-x-full'
            }`}
          >
            <div className="flex h-full flex-col overflow-y-auto pt-4">
              <UploadPanel
                sessionId={currentSessionId || ''}
                sessionFiles={sessionFiles}
                onFilesChange={handleFilesChange}
              />
              <PastQueries
                currentSessionId={currentSessionId}
                onSelectSession={handleSelectSession}
                onNewChat={handleNewChat}
              />
            </div>
          </div>
        </aside>

        {/* Center — Chat full width */}
        <main
          className="flex min-w-0 flex-1 flex-col"
          style={{ height: 'calc(100vh - 3.25rem)' }}
        >
          <ChatPanel
            key={currentSessionId}
            sessionId={currentSessionId || ''}
            messages={messages}
            onMessagesChange={handleMessagesChange}
          />
        </main>

        {/* Sidebar toggle button */}
        <button
          onClick={() => setShowLeft(p => !p)}
          className="fixed left-2 top-16 z-20 hidden rounded-input border border-border bg-background-surface p-1 text-text-muted hover:text-text-secondary md:flex"
          aria-label={showLeft ? 'Hide sidebar' : 'Show sidebar'}
        >
          {showLeft ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 18l-6-6 6-6"/></svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18l6-6-6-6"/></svg>
          )}
        </button>
      </div>
    </div>
  );
}
