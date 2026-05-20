'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { SendHorizontal, Square, AlertCircle, ChevronDown, ChevronUp, FileText, ChevronDown as ChevronDownIcon, ChevronUp as ChevronUpIcon } from 'lucide-react';
import { getDocumentStats, getDepartments } from '@/lib/api';
import Navbar from '@/components/Navbar';
import { queryStream } from '@/lib/api';
import { getStoredApiKey, addToQueryHistory } from '@/lib/storage';
import type { ChatMessage, Source } from '@/types';

export default function QueryPageClient() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [departments, setDepartments] = useState<string[]>([]);
  const [stats, setStats] = useState<{ total_chunks: number; by_department: Record<string, number> } | null>(null);
  const [showContext, setShowContext] = useState(false);
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());

  useEffect(() => {
    getDepartments().then(setDepartments).catch(() => {});
    getDocumentStats().then(setStats).catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedInput = input.trim();
    if (!trimmedInput || isStreaming) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmedInput,
      timestamp: Date.now(),
    };

    const assistantMsgId = crypto.randomUUID();
    const assistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput('');
    setIsStreaming(true);
    setError(null);

    const llmApiKey = getStoredApiKey();
    let streamedAnswer = '';

    await queryStream(
      {
        query: trimmedInput,
        stream: true,
        include_sources: true,
        llm_api_key: llmApiKey || null,
      },
      (chunk) => {
        streamedAnswer += chunk;
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantMsgId ? { ...m, content: streamedAnswer } : m))
        );
      },
      () => {},
      () => setIsStreaming(false),
      (err) => {
        setError(err);
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantMsgId ? { ...m, error: err } : m))
        );
        setIsStreaming(false);
      }
    );

    if (streamedAnswer) {
      addToQueryHistory(trimmedInput, streamedAnswer);
      try {
        const sourcesResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/query/retrieve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || '' },
          body: JSON.stringify({ query: trimmedInput, include_sources: true }),
        });
        if (sourcesResponse.ok) {
          const data = await sourcesResponse.json();
          const sources: Source[] = (data.results || []).map((r: { text: string; score: number; source: string; metadata?: Record<string, unknown> }) => ({
            text: r.text,
            score: r.score,
            source: r.source,
            metadata: r.metadata,
          }));
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantMsgId ? { ...m, sources } : m))
          );
        }
      } catch (err) {
        console.error('Failed to fetch sources:', err);
      }
    }
    setIsStreaming(false);
  }, [input, isStreaming]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-background-primary">
      <Navbar />

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 pt-16 sm:px-6">
        <div className="flex flex-1 gap-6 py-6">
          {messages.length === 0 && (
            <aside className="hidden w-64 shrink-0 lg:block">
              <button
                onClick={() => setShowContext((p) => !p)}
                className="mb-3 flex w-full items-center justify-between rounded-input border border-border bg-background-surface px-3 py-2 text-xs text-text-muted hover:border-accent-primary/50"
              >
                <span>Document Context</span>
                {showContext ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
              {showContext && (
                <div className="space-y-3 rounded-card border border-border bg-background-surface p-4">
                  <div className="text-xs text-text-muted">
                    <p className="mb-1 font-medium text-text-secondary">Available Departments</p>
                    {departments.length === 0 ? (
                      <p className="text-text-muted">No documents ingested yet.</p>
                    ) : (
                      <ul className="space-y-1">
                        {departments.map((d) => (
                          <li key={d} className="flex items-center gap-1.5">
                            <span className="h-1 w-1 rounded-full bg-accent-primary" />
                            <span className="text-text-secondary">{d}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  {stats && (
                    <div className="border-t border-border pt-3 text-xs">
                      <p className="mb-1 font-medium text-text-secondary">Total Chunks</p>
                      <p className="font-mono text-accent-primary">{stats.total_chunks}</p>
                    </div>
                  )}
                  <div className="border-t border-border pt-3">
                    <p className="mb-2 text-xs font-medium text-text-secondary">Source Files</p>
                    <Link
                      href="/documents"
                      className="block text-center text-xs text-accent-primary hover:underline"
                    >
                      Upload documents
                    </Link>
                  </div>
                </div>
              )}
            </aside>
          )}

          <div className={`flex-1 ${messages.length === 0 ? 'lg:max-w-2xl' : ''}`}>
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <svg width="48" height="48" viewBox="0 0 32 32" fill="none" className="mb-4 opacity-30">
                <circle cx="16" cy="16" r="14" fill="none" stroke="#6ee7b7" strokeWidth="1.5" />
                <circle cx="16" cy="16" r="6" fill="none" stroke="#6ee7b7" strokeWidth="1.5" />
                <circle cx="16" cy="16" r="2" fill="#6ee7b7" />
              </svg>
              <h2 className="mb-1 font-display text-lg font-semibold text-text-secondary">
                Ask a question
              </h2>
              <p className="max-w-xs text-xs text-text-muted">
                Query your documents using natural language.
              </p>
            </div>
          ) : (
            <div className="space-y-5">
              {messages.map((msg) => (
                <div key={msg.id}>
                  <div
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-card px-4 py-3 text-sm leading-relaxed ${
                        msg.role === 'user'
                          ? 'border border-accent-primary/30 bg-accent-primary/10 text-text-primary'
                          : msg.error
                          ? 'border border-status-error/40 bg-status-error/5 text-status-error'
                          : 'border-l-2 border-accent-primary/60 bg-background-surface text-text-primary'
                      }`}
                    >
                      {msg.error ? (
                        <div className="flex items-start gap-2">
                          <AlertCircle size={14} className="mt-0.5 shrink-0" />
                          <span>{msg.error}</span>
                        </div>
                      ) : (
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                      )}
                    </div>
                  </div>
                  {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                    <div className="ml-4 mt-2">
                      <button
                        onClick={() => {
                          setExpandedSources((prev) => {
                            const next = new Set(prev);
                            if (next.has(msg.id)) {
                              next.delete(msg.id);
                            } else {
                              next.add(msg.id);
                            }
                            return next;
                          });
                        }}
                        className="flex items-center gap-1.5 text-xs text-text-muted hover:text-accent-primary"
                      >
                        {expandedSources.has(msg.id) ? (
                          <ChevronUpIcon size={12} />
                        ) : (
                          <ChevronDownIcon size={12} />
                        )}
                        <FileText size={12} />
                        <span>{msg.sources.length} source{msg.sources.length > 1 ? 's' : ''}</span>
                      </button>
                      {expandedSources.has(msg.id) && (
                        <div className="mt-2 space-y-2">
                          {msg.sources.map((source, idx) => (
                            <div
                              key={`${msg.id}-${idx}`}
                              className="rounded border border-border-subtle bg-background-muted p-3 text-xs"
                            >
                              <div className="mb-1 flex items-center justify-between">
                                <span className="font-medium text-accent-primary truncate">{source.source || 'Unknown source'}</span>
                                <span className="text-text-muted">{(source.score * 100).toFixed(1)}%</span>
                              </div>
                              <p className="line-clamp-3 text-text-secondary">{source.text}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
          </div>
        </div>

        {error && !isStreaming && (
          <div className="mb-3 rounded-input border border-status-error/40 bg-status-error/5 px-3 py-2.5">
            <div className="flex items-start gap-2">
              <AlertCircle size={13} className="mt-0.5 shrink-0 text-status-error" />
              <div>
                <p className="text-xs font-medium text-status-error">Error</p>
                <p className="mt-0.5 text-xs text-text-muted">{error}</p>
              </div>
            </div>
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="sticky bottom-0 border-t border-border bg-background-primary/95 py-4 backdrop-blur-sm"
        >
          <div className="flex gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your documents..."
              rows={1}
              disabled={isStreaming}
              className="flex-1 resize-none rounded-input border border-border bg-background-muted px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted disabled:opacity-50"
              style={{ minHeight: '44px', maxHeight: '120px' }}
            />
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-input border border-accent-primary bg-accent-primary text-background-primary transition-all hover:bg-accent-primary/90 disabled:opacity-40 disabled:hover:bg-accent-primary"
              aria-label="Send message"
            >
              {isStreaming ? (
                <Square size={14} className="fill-current" />
              ) : (
                <SendHorizontal size={14} />
              )}
            </button>
          </div>
          <p className="mt-1.5 text-center text-xs text-text-muted">
            Press Enter to send, Shift+Enter for new line
          </p>
        </form>
      </main>
    </div>
  );
}
