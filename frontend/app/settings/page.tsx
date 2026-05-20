'use client';

import { useState, useEffect } from 'react';
import { Eye, EyeOff, Trash2, CheckCircle2, AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import Navbar from '@/components/Navbar';
import { checkHealth } from '@/lib/api';
import { getStoredApiKey, setStoredApiKey, clearStoredApiKey } from '@/lib/storage';
import type { HealthStatus } from '@/types';

export default function SettingsPage() {
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);
  const [cleared, setCleared] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  useEffect(() => {
    setApiKey(getStoredApiKey());
  }, []);

  const handleSave = () => {
    const trimmed = apiKey.trim();
    if (trimmed.length < 10 && trimmed.length > 0) {
      return;
    }
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

  const llmMode = health?.components?.llm_mode || 'none';
  const isLlmActive = llmMode !== 'none';
  const userHasKey = typeof window !== 'undefined' && Boolean(localStorage.getItem('openrouter_api_key'));
  const effectiveLlmMode = isLlmActive ? llmMode : userHasKey ? 'user-provided' : 'none';
  const isEffectiveLlmActive = isLlmActive || userHasKey;

  return (
    <div className="min-h-screen bg-background-primary">
      <Navbar />

      <main className="mx-auto max-w-2xl px-4 pt-20 pb-12 sm:px-6">
        <div className="mb-8">
          <h1 className="font-display text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">
            Settings
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            Configure your LLM provider and system preferences
          </p>
        </div>

        <div className="mb-6 space-y-5">
          <div className="rounded-card border border-border bg-background-surface p-5">
            <div className="mb-5">
              <h2 className="mb-1 font-display text-base font-semibold text-text-primary">
                OpenRouter API Key
              </h2>
              <p className="text-xs text-text-muted">
                Your key is stored only in your browser and sent directly to OpenRouter.
              </p>
            </div>

            <div className="space-y-3">
              <div className="relative">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-or-v1-..."
                  className="w-full rounded-input border border-border bg-background-muted px-3.5 py-2.5 pr-12 font-mono text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary/50 focus:outline-none"
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
                  className="flex items-center gap-1.5 rounded-input bg-accent-primary px-4 py-2 text-xs font-semibold text-background-primary transition-all hover:bg-accent-primary/90 disabled:opacity-50"
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
                  className="flex items-center gap-1.5 rounded-input border border-status-error/40 px-4 py-2 text-xs font-medium text-status-error transition-all hover:border-status-error hover:bg-status-error/5 disabled:opacity-50"
                >
                  <Trash2 size={13} />
                  Clear
                </button>
              </div>

              {cleared && (
                <p className="text-xs text-status-success">
                  <CheckCircle2 size={11} className="mr-1 inline" />
                  API key cleared from browser storage
                </p>
              )}
            </div>
          </div>

          <div className="rounded-card border border-border bg-background-surface p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-display text-base font-semibold text-text-primary">
                LLM Mode
              </h2>
              <button
                onClick={handleRefreshHealth}
                disabled={healthLoading}
                className="rounded p-1 text-text-muted transition-colors hover:bg-background-muted hover:text-text-secondary disabled:opacity-50"
                aria-label="Refresh status"
              >
                <RefreshCw size={12} className={healthLoading ? 'animate-spin' : ''} />
              </button>
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    isEffectiveLlmActive
                      ? 'bg-accent-primary animate-pulse-glow'
                      : health?.components?.llm_mode
                      ? 'bg-status-error'
                      : 'bg-text-muted'
                  }`}
                />
                <div>
                  <p className="text-sm font-medium text-text-primary">{effectiveLlmMode}</p>
                  <p className="text-xs text-text-muted">
                    {isEffectiveLlmActive
                      ? 'LLM is available for queries'
                      : 'No LLM available — add your OpenRouter key above'}
                  </p>
                </div>
              </div>

              <div className="space-y-1.5 rounded-input bg-background-muted p-3">
                <p className="text-xs font-semibold uppercase tracking-widest text-text-muted">Provider Details</p>
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-text-muted">Vector DB</span>
                    <span className="text-xs text-text-secondary">{health?.components?.qdrant || 'Unknown'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-text-muted">Metadata DB</span>
                    <span className="text-xs text-text-secondary">{health?.components?.postgres || 'Unknown'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-text-muted">BM25 Index</span>
                    <span className="text-xs text-text-secondary">{health?.components?.bm25 || 'Unknown'}</span>
                  </div>
                </div>
              </div>

              {!isLlmActive && (
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
          </div>

          <div className="rounded-card border border-border bg-background-surface p-5">
            <h2 className="mb-3 font-display text-base font-semibold text-text-primary">
              About
            </h2>
            <div className="space-y-2">
              <InfoRow label="Application" value="Production RAG" />
              <InfoRow label="Version" value="1.0.0" />
              <InfoRow label="Framework" value="Next.js + FastAPI" />
              <InfoRow label="Storage" value={health?.components?.qdrant?.includes('healthy') ? 'Cloud (Qdrant + Neon)' : 'Local'} />
            </div>
          </div>
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
