'use client';

import { useState, useEffect, useRef, useCallback, memo } from 'react';
import {
  SendHorizontal, AlertCircle, ChevronDown, ChevronUp, FileText,
  Search, MessageSquare,
} from 'lucide-react';
import { queryStream, retrieveQuery } from '@/lib/api';
import { updateSessionMessages } from '@/lib/storage';
import { addToQueryHistory } from '@/lib/storage';
import type { ChatMessage, Source, NodeEvaluation, RagasScores } from '@/types';

interface ChatPanelProps {
  sessionId: string;
  messages: ChatMessage[];
  onMessagesChange: (messages: ChatMessage[]) => void;
  onNewEvaluation?: (evaluations: NodeEvaluation[] | null, passed: boolean, latency: number, error: string | null) => void;
}

type QueryMode = 'ask' | 'retrieve';

function renderMarkdown(text: string): React.ReactNode {
  let content = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  const segments = content.split(/\n{2,}/).map(s => s.trim()).filter(Boolean);
  if (segments.length === 1) {
    const lines = content.split('\n').map(l => l.trim()).filter(Boolean);
    const numbered = lines.filter(l => /^\d+[.)]\s/.test(l));
    if (numbered.length >= 2) {
      return (
        <ol className="list-decimal pl-5 space-y-2">
          {numbered.map((line, i) => (
            <li key={i} dangerouslySetInnerHTML={{ __html: line.replace(/^\d+[.)]\s+/, '') }} />
          ))}
        </ol>
      );
    }
    const bullets = lines.filter(l => /^[-*+]\s/.test(l));
    if (bullets.length >= 2) {
      return (
        <ul className="list-disc pl-5 space-y-2">
          {bullets.map((line, i) => (
            <li key={i} dangerouslySetInnerHTML={{ __html: line.replace(/^[-*+]\s+/, '') }} />
          ))}
        </ul>
      );
    }
  }
  return (
    <div className="space-y-3">
      {segments.map((seg, i) => {
        const lines = seg.split('\n').map(l => l.trim()).filter(Boolean);
        const numbered = lines.filter(l => /^\d+[.)]\s/.test(l));
        if (numbered.length >= 2) {
          return (
            <ol key={i} className="list-decimal pl-5 space-y-2">
              {numbered.map((line, j) => (
                <li key={j} dangerouslySetInnerHTML={{ __html: line.replace(/^\d+[.)]\s+/, '') }} />
              ))}
            </ol>
          );
        }
        const bullets = lines.filter(l => /^[-*+]\s/.test(l));
        if (bullets.length >= 2) {
          return (
            <ul key={i} className="list-disc pl-5 space-y-2">
              {bullets.map((line, j) => (
                <li key={j} dangerouslySetInnerHTML={{ __html: line.replace(/^[-*+]\s+/, '') }} />
              ))}
            </ul>
          );
        }
        const bolded = lines.join('<br/>');
        return <p key={i} className="whitespace-pre-wrap" dangerouslySetInnerHTML={{ __html: bolded }} />;
      })}
    </div>
  );
}

const MessageBubble = memo(function MessageBubble({ msg, expandedSources, onToggleSources }: {
  msg: ChatMessage;
  expandedSources: Set<string>;
  onToggleSources: (id: string) => void;
}) {
  const [showEval, setShowEval] = useState(false);
  return (
    <div className="animate-fade-in">
      <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
        <div className={`max-w-[85%] rounded-card px-4 py-3 text-sm leading-relaxed ${
          msg.role === 'user'
            ? 'border border-accent-primary/30 bg-accent-primary/10 text-text-primary'
            : msg.error
            ? 'border border-status-error/40 bg-status-error/5 text-status-error'
            : 'border-l-2 border-accent-primary/60 bg-background-surface text-text-primary shadow-sm'
        }`}>
          {msg.error ? (
            <div className="flex items-start gap-2">
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <span>{msg.error}</span>
            </div>
          ) : (
            renderMarkdown(msg.content)
          )}
        </div>
      </div>

      {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
        <div className="ml-4 mt-2">
          <button
            onClick={() => onToggleSources(msg.id)}
            className="flex items-center gap-1.5 text-xs text-text-muted hover:text-accent-primary transition-colors"
          >
            {expandedSources.has(msg.id) ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            <FileText size={12} />
            <span>{msg.sources.length} source{msg.sources.length > 1 ? 's' : ''}</span>
          </button>
          {expandedSources.has(msg.id) && (
            <div className="mt-2 space-y-2">
              {msg.sources.map((source, idx) => (
                <div key={`${msg.id}-${idx}`} className="rounded border border-border-subtle bg-background-muted p-3 text-xs animate-slide-up">
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

      {msg.role === 'assistant' && msg.validation_passed !== undefined && (
        <div className="ml-4 mt-2 space-y-1.5">
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-medium ${
              msg.validation_passed ? 'text-status-success' : 'text-status-error'
            }`}>
              {msg.validation_passed ? 'Validation passed' : 'Validation failed'}
            </span>
            {msg.latency_ms !== undefined && (
              <span className="text-[10px] text-text-muted">
                {(msg.latency_ms / 1000).toFixed(2)}s
              </span>
            )}
          </div>

          {!msg.validation_passed && msg.error_message && (
            <div className="rounded border border-status-error/30 bg-status-error/5 px-3 py-2">
              <p className="text-[11px] font-medium text-status-error mb-1">Auditor rejection:</p>
              <p className="text-[11px] text-text-secondary leading-relaxed">{msg.error_message}</p>
            </div>
          )}

          {msg.node_evaluations && msg.node_evaluations.length > 0 && (
            <>
              <button
                onClick={() => setShowEval(p => !p)}
                className="flex items-center gap-1 text-[10px] text-text-muted hover:text-accent-primary transition-colors"
              >
                {showEval ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                <span>Node evaluations ({msg.node_evaluations.length})</span>
              </button>
              {showEval && (
                <div className="space-y-1">
                  {msg.node_evaluations.map((ne, idx) => (
                    <div key={idx} className="flex items-center gap-2 rounded border border-border-subtle bg-background-muted px-2.5 py-1.5 text-[10px]">
                      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                        ne.evaluation === 'passed' ? 'bg-status-success' :
                        ne.evaluation === 'failed' ? 'bg-status-error' : 'bg-text-muted'
                      }`} />
                      <span className="font-medium text-text-secondary capitalize">{ne.node.replace(/_/g, ' ')}</span>
                      <span className="text-text-muted ml-auto">{ne.latency_ms.toFixed(0)}ms</span>
                      <span className={`text-[9px] uppercase ${
                        ne.evaluation === 'passed' ? 'text-status-success' :
                        ne.evaluation === 'failed' ? 'text-status-error' : 'text-text-muted'
                      }`}>{ne.evaluation}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* RAGAS scores */}
          {msg.ragas_scores && (
            <div className="rounded border border-border-subtle bg-background-muted px-2.5 py-1.5">
              <p className="text-[10px] font-medium text-text-secondary mb-1">RAGAS scores</p>
              <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                {[
                  { field: 'context_precision' as const, label: 'Context Precision' },
                  { field: 'answer_relevancy' as const, label: 'Answer Relevancy' },
                  { field: 'faithfulness' as const, label: 'Faithfulness' },
                  { field: 'answer_completeness' as const, label: 'Completeness' },
                ].map(m => (
                  <span key={m.field} className="text-[9px]">
                    <span className="text-accent-primary">{m.label}</span>{' '}
                    <span className="font-semibold text-text-primary">{(msg.ragas_scores![m.field] * 100).toFixed(0)}%</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
});

export default function ChatPanel({ sessionId, messages, onMessagesChange, onNewEvaluation }: ChatPanelProps) {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());
  const [mode, setMode] = useState<QueryMode>('ask');

  // Streaming state
  const [streamingMsgId, setStreamingMsgId] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState('');
  const [streamingMetadata, setStreamingMetadata] = useState<{
    sources: Source[] | null;
    node_evaluations: NodeEvaluation[] | null;
    validation_passed: boolean;
    latency_ms: number;
    error_message: string | null;
    ragas_scores: RagasScores | null;
  } | null>(null);

  // Refs to avoid stale closures in streaming callbacks
  const streamingContentRef = useRef('');
  const streamingMetaRef = useRef<typeof streamingMetadata>(null);
  const streamMsgIdRef = useRef<string | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  const toggleSource = useCallback((id: string) => {
    setExpandedSources((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const stripSourceCitations = (text: string): string => {
    return text
      .replace(/\s*\([Ss]ource:\s*[^)]+\)\s*/g, '')
      .replace(/\s*\[[Ss]ource:\s*[^\]]+\]\s*/g, '')
      .trim();
  };

  const finalizeStream = useCallback((userMessages: ChatMessage[], assistantId: string, content: string, meta: typeof streamingMetadata, err?: string) => {
    const finalMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: err ? '' : stripSourceCitations(content),
      sources: meta?.sources || [],
      error: err,
      timestamp: Date.now(),
      node_evaluations: meta?.node_evaluations || null,
      validation_passed: meta?.validation_passed ?? true,
      latency_ms: meta?.latency_ms ?? 0,
      error_message: meta?.error_message || null,
      ragas_scores: meta?.ragas_scores || null,
    };
    const allMessages = [...userMessages, finalMsg];
    onMessagesChange(allMessages);
    updateSessionMessages(sessionId, allMessages);
    if (!err && content) {
      addToQueryHistory(userMessages[userMessages.length - 1]?.content || '', content);
    }
    if (onNewEvaluation && meta) {
      onNewEvaluation(meta.node_evaluations, meta.validation_passed, meta.latency_ms, meta.error_message);
    }
    setIsLoading(false);
    setStreamingMsgId(null);
    streamMsgIdRef.current = null;
  }, [onMessagesChange, sessionId, onNewEvaluation]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedInput = input.trim();
    if (!trimmedInput || isLoading) return;

    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: trimmedInput, timestamp: Date.now() };
    const assistantId = crypto.randomUUID();
    const userMessages = [...messages, userMsg];

    onMessagesChange(userMessages);
    setInput('');
    setIsLoading(true);
    setError(null);

    // Init streaming state
    streamingContentRef.current = '';
    streamingMetaRef.current = null;
    streamMsgIdRef.current = assistantId;
    setStreamingMsgId(assistantId);
    setStreamingContent('');
    setStreamingMetadata(null);

    const llmApiKey = typeof window !== 'undefined' ? localStorage.getItem('openrouter_api_key') : null;

    try {
      if (mode === 'retrieve') {
        const result = await retrieveQuery({ query: trimmedInput });
        const sources = result.results || [];
        const summary = sources.length > 0
          ? `Found ${sources.length} relevant document${sources.length > 1 ? 's' : ''}`
          : 'No relevant documents found';
        streamingContentRef.current = summary;
        streamingMetaRef.current = { sources, node_evaluations: null, validation_passed: true, latency_ms: 0, error_message: null, ragas_scores: null };
        setStreamingContent(summary);
        setStreamingMetadata(streamingMetaRef.current);
        finalizeStream(userMessages, assistantId, summary, streamingMetaRef.current);
      } else {
        await queryStream(
          { query: trimmedInput, include_sources: true, llm_api_key: llmApiKey || null },
          (chunk) => {
            streamingContentRef.current += chunk;
            setStreamingContent(streamingContentRef.current);
          },
          (meta) => {
            streamingMetaRef.current = meta;
            setStreamingMetadata(meta);
          },
          () => {
            finalizeStream(userMessages, assistantId, streamingContentRef.current, streamingMetaRef.current);
          },
          (err) => {
            setError(err);
            finalizeStream(userMessages, assistantId, streamingContentRef.current, streamingMetaRef.current, err);
          },
        );
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Query failed';
      setError(msg);
      finalizeStream(userMessages, assistantId, '', null, msg);
    }
  }, [input, isLoading, messages, sessionId, onMessagesChange, mode, finalizeStream, onNewEvaluation]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const streamingMsg: ChatMessage | null = streamingMsgId && (streamingContent || streamingMetadata)
    ? {
        id: streamingMsgId,
        role: 'assistant',
        content: streamingContent,
        sources: streamingMetadata?.sources || [],
        node_evaluations: streamingMetadata?.node_evaluations || null,
        validation_passed: streamingMetadata?.validation_passed ?? undefined,
        latency_ms: streamingMetadata?.latency_ms || undefined,
        error_message: streamingMetadata?.error_message || null,
        ragas_scores: streamingMetadata?.ragas_scores || null,
        timestamp: Date.now(),
      }
    : null;

  return (
    <div className="flex h-full flex-col">
      {messages.length === 0 && !streamingMsgId ? (
        <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
          <svg width="48" height="48" viewBox="0 0 32 32" fill="none" className="mb-4 opacity-30">
            <circle cx="16" cy="16" r="14" fill="none" stroke="var(--accent-primary)" strokeWidth="1.5" />
            <circle cx="16" cy="16" r="6" fill="none" stroke="var(--accent-primary)" strokeWidth="1.5" />
            <circle cx="16" cy="16" r="2" fill="var(--accent-primary)" />
          </svg>
          <h2 className="mb-1 font-display text-lg font-semibold text-text-secondary">
            Ask a question
          </h2>
          <p className="max-w-xs text-xs text-text-muted">
            Query your documents using natural language.
          </p>
        </div>
      ) : (
        <div className="flex-1 space-y-5 overflow-y-auto px-6 py-4">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} expandedSources={expandedSources} onToggleSources={toggleSource} />
          ))}
          {streamingMsg && (
            <MessageBubble key={streamingMsg.id} msg={streamingMsg} expandedSources={expandedSources} onToggleSources={toggleSource} />
          )}
          {streamingMsgId && !streamingMsg && (
            <div className="flex justify-start">
              <div className="rounded-card border-l-2 border-accent-primary/60 bg-background-surface px-4 py-3 shadow-sm">
                <span className="typing-dots text-sm text-text-secondary">Thinking</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}

      {error && !isLoading && (
        <div className="mx-6 mb-3 rounded-input border border-status-error/40 bg-status-error/5 px-3 py-2.5">
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
        className="border-t border-border bg-background-primary/95 px-6 py-4 backdrop-blur-sm"
      >
        {/* Mode toggle */}
        <div className="mb-2 flex items-center gap-1">
          <button
            type="button"
            onClick={() => setMode('ask')}
            className={`flex items-center gap-1.5 rounded-tab px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === 'ask'
                ? 'bg-accent-primary/15 text-accent-primary'
                : 'text-text-muted hover:text-text-secondary'
            }`}
            disabled={isLoading}
          >
            <MessageSquare size={12} />
            <span>Ask</span>
          </button>
          <button
            type="button"
            onClick={() => setMode('retrieve')}
            className={`flex items-center gap-1.5 rounded-tab px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === 'retrieve'
                ? 'bg-accent-primary/15 text-accent-primary'
                : 'text-text-muted hover:text-text-secondary'
            }`}
            disabled={isLoading}
          >
            <Search size={12} />
            <span>Retrieve</span>
          </button>
        </div>

        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={mode === 'ask' ? 'Ask about your documents...' : 'Search for documents...'}
            rows={1}
            disabled={isLoading}
            className="flex-1 resize-none rounded-input border border-border bg-background-muted px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted disabled:opacity-50 transition-colors focus:border-accent-primary/50"
            style={{ minHeight: '44px', maxHeight: '120px' }}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-input bg-accent-primary text-background-primary transition-all hover:opacity-90 disabled:opacity-40 disabled:hover:opacity-40"
            aria-label={mode === 'ask' ? 'Send message' : 'Search'}
          >
            {isLoading ? (
              <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-background-primary border-t-transparent" />
            ) : (
              <SendHorizontal size={14} />
            )}
          </button>
        </div>
        <p className="mt-1.5 text-center text-xs text-text-muted">
          Press Enter to send, Shift+Enter for new line
        </p>
      </form>
    </div>
  );
}
