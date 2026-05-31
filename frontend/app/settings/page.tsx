'use client';

import { useState, useEffect } from 'react';
import { Eye, EyeOff, Trash2, CheckCircle2, AlertCircle, Loader2, RefreshCw, Server, Cpu, Database, Brain, Wifi, HardDrive, Wrench, Copy, ClipboardPaste } from 'lucide-react';
import Navbar from '@/components/Navbar';
import { checkHealth } from '@/lib/api';
import { getStoredApiKey, setStoredApiKey, clearStoredApiKey, getStoredTenantId, setStoredTenantId } from '@/lib/storage';
import type { HealthStatus } from '@/types';

export default function SettingsPage() {
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);
  const [cleared, setCleared] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [tenantId, setTenantId] = useState('');
  const [copied, setCopied] = useState(false);
  const [restoreId, setRestoreId] = useState('');
  const [restored, setRestored] = useState(false);
  const [autoCopied, setAutoCopied] = useState(false);

  useEffect(() => {
    setApiKey(getStoredApiKey());
  }, []);

  const handleSave = () => {
    const trimmed = apiKey.trim();
    setStoredApiKey(trimmed);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleClear = () => {
    clearStoredApiKey();
    setApiKey('');
    setCleared(true);
    setTimeout(() => setCleared(false), 2000);
  };

  const handleRefreshHealth = async () => {
    setHealthLoading(true);
    try {
      const status = await checkHealth();
      setHealth(status);
    } catch {
      // ignore
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    handleRefreshHealth();
  }, []);

  useEffect(() => {
    const id = getStoredTenantId();
    setTenantId(id);
    if (id && !localStorage.getItem('tenant_id_copied')) {
      navigator.clipboard.writeText(id).then(() => {
        localStorage.setItem('tenant_id_copied', 'true');
        setAutoCopied(true);
        setTimeout(() => setAutoCopied(false), 4000);
      }).catch(() => {});
    }
  }, []);

  const handleReInitSession = async () => {
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
      setTenantId(data.tenant_id);
    } catch {
      // ignore
    }
  };

  const handleCopyTenantId = () => {
    if (!tenantId) return;
    navigator.clipboard.writeText(tenantId).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleRestoreTenant = async () => {
    const trimmed = restoreId.trim();
    if (!trimmed) return;
    try {
      const base = process.env.NEXT_PUBLIC_API_URL || '';
      const res = await fetch(`${base}/api/v1/session/init`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tenant_id: trimmed }),
      });
      if (!res.ok) return;
      const data = await res.json() as { tenant_id: string };
      setStoredTenantId(data.tenant_id);
      setTenantId(data.tenant_id);
      setRestoreId('');
      setRestored(true);
      setTimeout(() => setRestored(false), 3000);
    } catch {
      // ignore
    }
  };

  const llmMode = health?.components?.llm_mode || 'none';
  const llmProvider = health?.components?.llm_provider || 'unknown';
  const isLlmActive = llmMode !== 'none';
  const userHasKey = typeof window !== 'undefined' && Boolean(localStorage.getItem('openrouter_api_key'));
  const providerLabel = userHasKey ? 'openrouter (user key)' : (isLlmActive ? llmMode : 'none');
  const effectiveLlmMode = isLlmActive ? llmMode : userHasKey ? 'user-provided' : 'none';
  const isEffectiveLlmActive = isLlmActive || userHasKey;

  const systemComponents = [
    { label: 'API Server', value: health?.components?.api || 'Unknown', icon: Server, status: health?.components?.api === 'healthy' ? 'ok' : 'error' },
    { label: 'Vector DB (Qdrant)', value: health?.components?.qdrant || 'Unknown', icon: Database, status: health?.components?.qdrant === 'healthy' ? 'ok' : 'error' },
    { label: 'Metadata DB (Postgres)', value: health?.components?.postgres || 'Unknown', icon: HardDrive, status: health?.components?.postgres === 'healthy' ? 'ok' : 'error' },
    { label: 'BM25 Index', value: health?.components?.bm25 || 'Unknown', icon: Wrench, status: health?.components?.bm25 === 'healthy' ? 'ok' : 'error' },
  ];

  return (
    <div className="min-h-screen bg-background-primary">
      <Navbar />

      <main className="mx-auto max-w-3xl px-4 pt-20 pb-12 sm:px-6">
        <div className="mb-8">
          <h1 className="font-display text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">
            Settings
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            Configure your LLM provider and view system status
          </p>
        </div>

        <div className="space-y-6">
          {/* LLM Configuration */}
          <section className="rounded-card border border-border bg-background-surface p-5">
            <div className="mb-5 flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-input bg-accent-primary/10 text-accent-primary">
                <Brain size={16} />
              </div>
              <div>
                <h2 className="font-display text-base font-semibold text-text-primary">
                  LLM Configuration
                </h2>
                <p className="text-xs text-text-muted">OpenRouter API key for query processing</p>
              </div>
            </div>

            <div className="space-y-3">
              <div className="relative">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-or-v1-..."
                  className="w-full rounded-input border border-border bg-background-muted px-3.5 py-2.5 pr-12 font-mono text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary/50 focus:outline-none transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 text-text-muted transition-colors hover:bg-background-muted hover:text-text-secondary"
                  aria-label={showKey ? 'Hide key' : 'Show key'}
                >
                  {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={handleSave}
                  className="flex items-center gap-1.5 rounded-input bg-accent-primary px-4 py-2 text-xs font-semibold text-background-primary transition-all hover:opacity-90 disabled:opacity-50"
                >
                  {saved ? (
                    <>
                      <CheckCircle2 size={13} />
                      Saved
                    </>
                  ) : (
                    'Save Key'
                  )}
                </button>
                <button
                  onClick={handleClear}
                  className="flex items-center gap-1.5 rounded-input border border-status-error/40 px-4 py-2 text-xs font-medium text-status-error transition-all hover:border-status-error hover:bg-status-error/5"
                >
                  <Trash2 size={13} />
                  Clear
                </button>
              </div>

              {cleared && (
                <p className="text-xs text-status-success animate-fade-in">
                  <CheckCircle2 size={11} className="mr-1 inline" />
                  API key cleared from browser storage
                </p>
              )}

              <p className="text-[10px] text-text-muted">
                Your key is stored only in your browser and sent directly to the API.
                It is never saved on our servers.
              </p>
            </div>
          </section>

          {/* Session */}
          <section className="rounded-card border border-border bg-background-surface p-5">
            <div className="mb-5 flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-input bg-accent-primary/10 text-accent-primary">
                <Wifi size={16} />
              </div>
              <div>
                <h2 className="font-display text-base font-semibold text-text-primary">
                  Session
                </h2>
                <p className="text-xs text-text-muted">Your tenant ID — save this to restore your documents later</p>
              </div>
            </div>

            <div className="space-y-3">
              <div className="rounded-card border border-border bg-background-muted p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">Tenant ID</span>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={handleCopyTenantId}
                      className="rounded p-1 text-text-muted transition-colors hover:bg-background-surface hover:text-accent-primary"
                      title="Copy tenant ID"
                      aria-label="Copy tenant ID"
                    >
                      {copied ? <CheckCircle2 size={13} className="text-status-success" /> : <Copy size={13} />}
                    </button>
                  </div>
                </div>
                <div className="mt-2 break-all font-mono text-[13px] font-medium text-accent-primary">
                  {tenantId || '—'}
                </div>
                <p className="mt-2 text-[10px] text-text-muted">
                  Copy this ID. If you lose your session (clear cookies, server restart, redeploy),
                  paste it below to reclaim all your uploaded documents.
                </p>
                {autoCopied && (
                  <p className="mt-2 animate-fade-in text-xs text-status-success">
                    <CheckCircle2 size={11} className="mr-1 inline" />
                    Copied to clipboard — save this to restore your data
                  </p>
                )}
              </div>

              <div className="rounded-card border border-border bg-background-muted p-3">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  Restore Previous Tenant
                </p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={restoreId}
                    onChange={(e) => setRestoreId(e.target.value)}
                    placeholder="Paste saved tenant_id here..."
                    className="min-w-0 flex-1 rounded-input border border-border bg-background-surface px-3 py-2 font-mono text-[12px] text-text-primary placeholder:text-text-muted focus:border-accent-primary/50 focus:outline-none transition-colors"
                  />
                  <button
                    onClick={handleRestoreTenant}
                    disabled={!restoreId.trim()}
                    className="flex shrink-0 items-center gap-1.5 rounded-input bg-accent-primary px-3 py-2 text-xs font-semibold text-background-primary transition-all hover:opacity-90 disabled:opacity-40"
                  >
                    <ClipboardPaste size={12} />
                    Restore
                  </button>
                </div>
                {restored && (
                  <p className="mt-2 text-xs text-status-success animate-fade-in">
                    <CheckCircle2 size={11} className="mr-1 inline" />
                    Tenant restored — your documents should now be available
                  </p>
                )}
              </div>

              <button
                onClick={handleReInitSession}
                className="flex items-center gap-1.5 rounded-input border border-border px-4 py-2 text-xs font-medium text-text-secondary transition-all hover:bg-background-muted hover:text-text-primary"
              >
                <RefreshCw size={12} />
                Re-issue Session Cookie
              </button>

              <p className="text-[10px] text-text-muted">
                Click "Re-issue" if documents disappeared after a server restart. This refreshes
                your session cookie while keeping your existing tenant and documents.
              </p>
            </div>
          </section>

          {/* LLM State */}
          <section className="rounded-card border border-border bg-background-surface p-5">
            <div className="mb-5 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-input bg-accent-secondary/10 text-accent-secondary">
                  <Cpu size={16} />
                </div>
                <div>
                  <h2 className="font-display text-base font-semibold text-text-primary">
                    LLM State
                  </h2>
                  <p className="text-xs text-text-muted">Current LLM availability and mode</p>
                </div>
              </div>
              <button
                onClick={handleRefreshHealth}
                disabled={healthLoading}
                className="rounded p-1.5 text-text-muted transition-colors hover:bg-background-muted hover:text-text-secondary disabled:opacity-50"
                aria-label="Refresh status"
              >
                <RefreshCw size={12} className={healthLoading ? 'animate-spin' : ''} />
              </button>
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-3 rounded-input bg-background-muted p-3">
                <span
                  className={`h-2.5 w-2.5 rounded-full shrink-0 ${
                    isEffectiveLlmActive
                      ? 'bg-accent-primary animate-pulse-glow'
                      : 'bg-text-muted'
                  }`}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-text-primary">{effectiveLlmMode}</p>
                  <p className="text-xs text-text-muted">
                    {isEffectiveLlmActive
                      ? 'LLM is available for queries'
                      : 'No LLM available — add your OpenRouter key above or start Ollama'}
                  </p>
                </div>
              </div>

              <div className="space-y-1.5 rounded-input border border-border bg-background-surface p-3">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">Provider Chain</p>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">Configured</span>
                  <span className="text-xs font-medium text-accent-primary">
                    {llmProvider === 'auto' ? 'auto-detect' : llmProvider}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">Active</span>
                  <span className={`text-xs font-medium ${isEffectiveLlmActive ? 'text-accent-primary' : 'text-text-muted'}`}>
                    {providerLabel}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">Env Keys Found</span>
                  <span className={`text-xs font-medium ${isLlmActive ? 'text-accent-primary' : 'text-text-muted'}`}>
                    {llmMode}
                  </span>
                </div>
              </div>

              {!isEffectiveLlmActive && (
                <div className="rounded-input border border-accent-secondary/30 bg-accent-secondary/5 p-3">
                  <div className="mb-1.5 flex items-center gap-1.5">
                    <AlertCircle size={12} className="text-accent-secondary" />
                    <span className="text-xs font-semibold text-accent-secondary">Setup Required</span>
                  </div>
                  <ul className="space-y-1 text-xs text-text-muted">
                    <li>
                      <span className="font-medium text-text-secondary">Option 1:</span>{' '}
                      Enter your OpenRouter API key above
                    </li>
                    <li>
                      <span className="font-medium text-text-secondary">Option 2:</span>{' '}
                      Run <code className="rounded bg-background-muted px-1 font-mono text-text-secondary">ollama serve</code> locally
                    </li>
                  </ul>
                </div>
              )}
            </div>
          </section>

          {/* System State */}
          <section className="rounded-card border border-border bg-background-surface p-5">
            <div className="mb-5 flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-input bg-status-success/10 text-status-success">
                <Server size={16} />
              </div>
              <div>
                <h2 className="font-display text-base font-semibold text-text-primary">
                  System State
                </h2>
                <p className="text-xs text-text-muted">Backend component health and status</p>
              </div>
            </div>

            {healthLoading && !health ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 size={20} className="animate-spin text-accent-primary" />
              </div>
            ) : (
              <div className="space-y-2">
                <div className="mb-3 flex items-center gap-2">
                  <span
                    className={`h-2 w-2 rounded-full ${
                      health?.status === 'healthy' ? 'bg-status-success' : health?.status === 'degraded' ? 'bg-status-warning' : 'bg-status-error'
                    }`}
                  />
                  <span className="text-sm font-medium text-text-primary capitalize">
                    {health?.status || 'Offline'}
                  </span>
                  <span className="text-xs text-text-muted">— Overall Status</span>
                </div>

                {systemComponents.map((comp) => (
                  <div
                    key={comp.label}
                    className="flex items-center justify-between rounded-input border border-border-subtle bg-background-muted px-3 py-2.5"
                  >
                    <div className="flex items-center gap-2.5">
                      <comp.icon size={13} className="text-text-muted" />
                      <span className="text-xs text-text-secondary">{comp.label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-medium ${
                        comp.status === 'ok' ? 'text-status-success' : 'text-status-error'
                      }`}>
                        {comp.value}
                      </span>
                      <span className={`h-1.5 w-1.5 rounded-full ${
                        comp.status === 'ok' ? 'bg-status-success' : 'bg-status-error'
                      }`} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* About */}
          <section className="rounded-card border border-border bg-background-surface p-5">
            <h2 className="mb-3 font-display text-base font-semibold text-text-primary">
              About
            </h2>
            <div className="space-y-2">
              <InfoRow label="Application" value="Production RAG" />
              <InfoRow label="Version" value="1.0.0" />
              <InfoRow label="Framework" value="Next.js + FastAPI" />
              <InfoRow label="Frontend Design" value="3-Panel Layout · Light/Dark Mode" />
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border-subtle pb-2 last:border-0 last:pb-0">
      <span className="text-xs text-text-muted">{label}</span>
      <span className="text-xs font-medium text-text-secondary">{value}</span>
    </div>
  );
}
