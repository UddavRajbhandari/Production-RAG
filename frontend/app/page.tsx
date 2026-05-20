'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { MessageSquare, Upload, FileText, Settings, Loader2, AlertCircle, CheckCircle2, RefreshCw, Database, Brain, Search, ChevronRight } from 'lucide-react';
import Navbar from '@/components/Navbar';
import { checkHealth, getDocumentStats } from '@/lib/api';
import { getQueryHistory } from '@/lib/storage';
import type { HealthStatus } from '@/types';

interface DocStats {
  total_chunks: number;
  by_department: Record<string, number>;
  by_year: Record<string, number>;
  by_domain: Record<string, number>;
}

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [stats, setStats] = useState<DocStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [history] = useState(() => getQueryHistory());

  const loadHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, s] = await Promise.all([checkHealth(), getDocumentStats()]);
      setHealth(h);
      setStats(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHealth();
    const interval = setInterval(loadHealth, 120000);
    const handleVisibility = () => { if (!document.hidden) loadHealth(); };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => { clearInterval(interval); document.removeEventListener('visibilitychange', handleVisibility); };
  }, []);

  const llmMode = health?.components?.llm_mode || 'none';
  const userHasKey = typeof window !== 'undefined' && Boolean(localStorage.getItem('openrouter_api_key'));
  const effectiveLlm = llmMode !== 'none' ? llmMode : userHasKey ? 'openrouter (user)' : 'none';
  const llmActive = llmMode !== 'none' || userHasKey;

  return (
    <div className="min-h-screen bg-background-primary">
      <Navbar />
      <main className="mx-auto max-w-5xl px-4 pt-20 pb-12 sm:px-6">
        <div className="mb-8">
          <h1 className="font-display text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">Overview</h1>
          <p className="mt-1 text-sm text-text-secondary">System status and quick actions</p>
        </div>

        {loading && !health ? (
          <div className="flex h-40 items-center justify-center gap-2 text-text-muted">
            <Loader2 size={20} className="animate-spin" />
            <span className="text-sm">Loading...</span>
          </div>
        ) : error && !health ? (
          <div className="flex h-32 items-center gap-2 text-status-error">
            <AlertCircle size={16} />
            <span className="text-sm">{error}</span>
          </div>
        ) : (
          <>
            <div className="mb-6 grid gap-4 sm:grid-cols-3">
              <StatusCard
                label="System Status"
                icon={<div className={`h-2 w-2 rounded-full ${health?.status === 'healthy' ? 'bg-status-success animate-pulse-glow' : health?.status === 'degraded' ? 'bg-status-warning' : 'bg-status-error'}`} />}
                value={health?.status ? health.status.charAt(0).toUpperCase() + health.status.slice(1) : 'Unknown'}
                loading={loading}
                onRefresh={loadHealth}
              />
              <StatusCard
                label="Documents"
                icon={<Database size={14} className="text-accent-primary" />}
                value={`${stats?.total_chunks ?? 0} chunks`}
                sub={Object.keys(stats?.by_department ?? {}).length > 0 ? `${Object.keys(stats?.by_department ?? {}).length} departments` : 'No data'}
                loading={loading}
                onRefresh={loadHealth}
              />
              <StatusCard
                label="LLM Engine"
                icon={<Brain size={14} className="text-accent-primary" />}
                value={llmActive ? 'Active' : 'Unavailable'}
                sub={effectiveLlm}
                loading={loading}
                onRefresh={loadHealth}
              />
            </div>

            {(!llmActive || !stats?.total_chunks) && (
              <div className="mb-6 rounded-card border border-status-warning/30 bg-status-warning/5 p-4">
                <div className="flex items-start gap-3">
                  <AlertCircle size={16} className="mt-0.5 shrink-0 text-status-warning" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-status-warning">Setup incomplete</p>
                    <ul className="mt-1.5 space-y-1 text-xs text-text-muted">
                      {!stats?.total_chunks && <li>No documents ingested — <Link href="/documents" className="text-accent-secondary hover:text-accent-primary">upload files</Link> to get started</li>}
                      {!llmActive && <li>No LLM configured — <Link href="/settings" className="text-accent-secondary hover:text-accent-primary">add your OpenRouter key</Link> to enable queries</li>}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            <div className="mb-6 grid gap-3 sm:grid-cols-2">
              <QuickAction
                icon={<Search size={18} />}
                title="Query Documents"
                description={stats?.total_chunks ? `Ask questions over ${stats.total_chunks} indexed chunks` : 'Ingest documents first'}
                href="/query"
                disabled={!stats?.total_chunks}
              />
              <QuickAction
                icon={<Upload size={18} />}
                title="Upload Documents"
                description="Add PDF, DOCX, XLSX, or PPT files to the knowledge base"
                href="/documents"
              />
            </div>

            {stats?.total_chunks ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-card border border-border bg-background-surface p-4">
                  <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">By Department</h3>
                  <div className="space-y-2">
                    {Object.entries(stats.by_department).length === 0 ? (
                      <p className="text-xs text-text-muted">No department data</p>
                    ) : (
                      Object.entries(stats.by_department).map(([dept, count]) => (
                        <div key={dept} className="flex items-center justify-between">
                          <span className="text-sm text-text-secondary">{dept}</span>
                          <span className="text-xs font-mono text-accent-primary">{count}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
                <div className="rounded-card border border-border bg-background-surface p-4">
                  <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">By Year</h3>
                  <div className="space-y-2">
                    {Object.keys(stats.by_year).length === 0 ? (
                      <p className="text-xs text-text-muted">No year data</p>
                    ) : (
                      Object.entries(stats.by_year).sort((a, b) => b[0].localeCompare(a[0])).map(([year, count]) => (
                        <div key={year} className="flex items-center justify-between">
                          <span className="text-sm text-text-secondary">{year}</span>
                          <span className="text-xs font-mono text-accent-primary">{count}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            ) : null}

            <div className="mt-6 rounded-card border border-border bg-background-surface p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">Recent Queries</h3>
                {history.length > 0 && (
                  <span className="text-xs text-text-muted">{history.length} total</span>
                )}
              </div>
              {history.length === 0 ? (
                <div className="py-6 text-center">
                  <MessageSquare size={20} className="mx-auto mb-2 text-text-muted" />
                  <p className="text-xs text-text-muted">No queries yet</p>
                </div>
              ) : (
                <ul className="space-y-2">
                  {history.slice(0, 5).map((item) => (
                    <li key={item.id}>
                      <Link href={`/query?q=${encodeURIComponent(item.query)}`} className="group flex items-center justify-between rounded-input border border-border-subtle bg-background-muted p-3 transition-all hover:border-accent-primary/40">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-text-primary group-hover:text-accent-primary">{item.query}</p>
                          <p className="truncate text-xs text-text-muted">{item.answerPreview}</p>
                        </div>
                        <ChevronRight size={14} className="ml-2 shrink-0 text-text-muted" />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function StatusCard({ label, icon, value, sub, loading, onRefresh }: {
  label: string; icon: React.ReactNode; value: string; sub?: string; loading: boolean; onRefresh: () => void;
}) {
  return (
    <div className="rounded-card border border-border bg-background-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-text-muted">{icon}</span>
          <span className="text-xs font-semibold uppercase tracking-widest text-text-muted">{label}</span>
        </div>
        <button onClick={onRefresh} className="rounded p-1 text-text-muted transition-colors hover:bg-background-muted hover:text-text-secondary" disabled={loading}>
          <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>
      <p className="font-display text-xl font-bold text-text-primary">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-text-muted">{sub}</p>}
    </div>
  );
}

function QuickAction({ icon, title, description, href, disabled }: { icon: React.ReactNode; title: string; description: string; href: string; disabled?: boolean }) {
  return (
    <Link href={href} className={`group flex items-center gap-4 rounded-card border p-4 transition-all ${disabled ? 'pointer-events-none cursor-not-allowed opacity-50' : 'border-border bg-background-surface hover:border-accent-primary/40'}`}>
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-input border border-accent-primary/30 bg-accent-primary/10 text-accent-primary">
        {icon}
      </div>
      <div>
        <p className="text-sm font-medium text-text-primary group-hover:text-accent-primary">{title}</p>
        <p className="mt-0.5 text-xs text-text-muted">{description}</p>
      </div>
    </Link>
  );
}
