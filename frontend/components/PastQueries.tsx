'use client';

import { useState, useEffect } from 'react';
import { MessageSquare, Plus, Trash2, FileText, Clock, ChevronDown, ChevronRight } from 'lucide-react';
import { getRecentSessions, deleteSession, createSession } from '@/lib/storage';
import type { ChatSession } from '@/types';

interface PastQueriesProps {
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
}

export default function PastQueries({ currentSessionId, onSelectSession, onNewChat }: PastQueriesProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [collapsed, setCollapsed] = useState(false);

  const loadSessions = () => setSessions(getRecentSessions());

  useEffect(() => {
    loadSessions();
    const interval = setInterval(loadSessions, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    deleteSession(id);
    loadSessions();
  };

  const formatDate = (ts: number) => {
    const d = new Date(ts);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return d.toLocaleDateString();
  };

  return (
    <div className="border-t border-border">
      <div className="px-4 pt-3 pb-2">
        <button
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-1.5 rounded-input border border-accent-primary/50 bg-accent-primary/5 px-3 py-2 text-xs font-medium text-accent-primary transition-all hover:bg-accent-primary/10"
        >
          <Plus size={12} />
          New Chat
        </button>
      </div>

      <button
        onClick={() => setCollapsed(p => !p)}
        className="flex w-full items-center justify-between px-4 py-2 text-xs font-semibold uppercase tracking-wider text-text-muted hover:text-text-secondary transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <Clock size={12} />
          History
          {sessions.length > 0 && (
            <span className="ml-1 rounded-full bg-background-muted px-1.5 py-0.5 text-[10px] font-normal">
              {sessions.length}
            </span>
          )}
        </span>
        {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
      </button>

      {!collapsed && (
        <div className="px-4 pb-4">
          {sessions.length === 0 ? (
            <div className="flex flex-col items-center py-4 text-center">
              <MessageSquare size={16} className="mb-1.5 text-text-muted" />
              <p className="text-[10px] text-text-muted">No sessions yet</p>
              <p className="text-[10px] text-text-muted/60">Start a new chat to begin</p>
            </div>
          ) : (
            <div className="space-y-1">
              {sessions.map((session) => {
                const isActive = session.id === currentSessionId;
                const msgCount = session.messages.length;

                return (
                  <button
                    key={session.id}
                    onClick={() => onSelectSession(session.id)}
                    className={`group flex w-full items-start gap-2 rounded-input border p-2 text-left transition-all ${
                      isActive
                        ? 'border-accent-primary/40 bg-accent-primary/5'
                        : 'border-transparent bg-background-muted/50 hover:border-border hover:bg-background-muted'
                    }`}
                  >
                    <MessageSquare size={10} className={`mt-0.5 shrink-0 ${
                      isActive ? 'text-accent-primary' : 'text-text-muted'
                    }`} />
                    <div className="min-w-0 flex-1">
                      <p className={`truncate text-[11px] font-medium ${
                        isActive ? 'text-accent-primary' : 'text-text-primary'
                      }`}>
                        {session.name}
                      </p>
                      <div className="mt-0.5 flex items-center gap-2 text-[9px] text-text-muted">
                        {msgCount > 0 && <span>{msgCount} msgs</span>}
                        {session.files.length > 0 && (
                          <span className="flex items-center gap-0.5">
                            <FileText size={8} />
                            {session.files.length}
                          </span>
                        )}
                        <span>{formatDate(session.updated_at)}</span>
                      </div>
                    </div>
                    <button
                      onClick={(e) => handleDelete(e, session.id)}
                      className="shrink-0 rounded p-0.5 text-text-muted opacity-0 group-hover:opacity-100 hover:text-status-error transition-all"
                      aria-label="Delete session"
                    >
                      <Trash2 size={10} />
                    </button>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
