'use client';

import { ChevronDown, ChevronRight, Shield, BarChart3, CheckCircle2, XCircle, AlertTriangle, GitMerge, Search, FileText, Brain, Scale } from 'lucide-react';
import type { NodeEvaluation } from '@/types';

const NODE_META: Record<string, { label: string; icon: typeof Shield; description: string }> = {
  planner: { label: 'Planner', icon: GitMerge, description: 'Decomposes query into sub-tasks' },
  router: { label: 'Router', icon: Search, description: 'Routes to retrieval or calculation' },
  retrieval_agent: { label: 'Retrieval Agent', icon: FileText, description: 'Hybrid search + reranking' },
  calculation_agent: { label: 'Calculation Agent', icon: BarChart3, description: 'Arithmetic extraction' },
  summarization_agent: { label: 'Summarization Agent', icon: Brain, description: 'Synthesizes final answer' },
  gatekeeper: { label: 'Gatekeeper', icon: Shield, description: 'Validates query-answer alignment' },
  auditor: { label: 'Auditor', icon: Scale, description: 'Checks for hallucination' },
  strategist: { label: 'Strategist', icon: BarChart3, description: 'Heuristic quality checks' },
};

interface EvaluationPanelProps {
  latestEvaluations?: NodeEvaluation[] | null;
  validationPassed?: boolean;
  latencyMs?: number;
  errorMessage?: string | null;
  showEmpty?: boolean;
}

export default function EvaluationPanel({
  latestEvaluations,
  validationPassed,
  latencyMs,
  errorMessage,
  showEmpty = true,
}: EvaluationPanelProps) {
  const hasData = latestEvaluations && latestEvaluations.length > 0;

  if (!hasData && !showEmpty) {
    return null;
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-4 py-3">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-muted">
          <BarChart3 size={12} />
          Agent Evaluation
        </h3>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 pb-4">
        {!hasData ? (
          <div className="flex flex-col items-center py-8 text-center">
            <BarChart3 size={20} className="mb-2 text-text-muted/50" />
            <p className="text-[10px] text-text-muted">No evaluation data yet</p>
            <p className="text-[10px] text-text-muted/60">Submit a query to see agent results</p>
          </div>
        ) : (
          <>
            {/* Summary Card */}
            <div className={`rounded-card border p-3 ${
              validationPassed
                ? 'border-status-success/30 bg-status-success/5'
                : 'border-status-error/30 bg-status-error/5'
            }`}>
              <div className="flex items-center gap-2">
                {validationPassed
                  ? <CheckCircle2 size={14} className="text-status-success" />
                  : <XCircle size={14} className="text-status-error" />
                }
                <span className={`text-xs font-semibold ${validationPassed ? 'text-status-success' : 'text-status-error'}`}>
                  {validationPassed ? 'Validation Passed' : 'Validation Failed'}
                </span>
              </div>
              {latencyMs !== undefined && (
                <p className="mt-1.5 text-[10px] text-text-muted">
                  Total latency: {(latencyMs / 1000).toFixed(2)}s
                </p>
              )}
              {errorMessage && (
                <p className="mt-1.5 text-[10px] text-status-error">{errorMessage}</p>
              )}
            </div>

            {/* Agent Chain */}
            <div className="space-y-1">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted px-0.5">Agent Chain</p>
              <div className="relative">
                {/* Vertical connector line */}
                <div className="absolute left-[11px] top-2 bottom-2 w-px bg-border" />

                {latestEvaluations.map((ev, idx) => {
                  const meta = NODE_META[ev.node];
                  if (!meta) return null;
                  const isLast = idx === latestEvaluations.length - 1;
                  const isActiveNode = ev.latency_ms > 0;

                  return (
                    <div key={ev.node} className="relative flex items-start gap-2.5 py-1.5">
                      <div className={`relative z-10 flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${
                        !isActiveNode
                          ? 'bg-background-muted text-text-muted'
                          : ev.evaluation === 'passed' || ev.evaluation === 'completed'
                          ? 'bg-status-success/10 text-status-success'
                          : ev.evaluation === 'failed'
                          ? 'bg-status-error/10 text-status-error'
                          : 'bg-background-muted text-text-muted'
                      }`}>
                        <meta.icon size={10} />
                      </div>
                      <div className="flex-1 min-w-0 pt-0.5">
                        <div className="flex items-center justify-between">
                          <span className={`text-[11px] font-medium ${isActiveNode ? 'text-text-primary' : 'text-text-muted'}`}>
                            {meta.label}
                          </span>
                          <div className="flex items-center gap-1.5">
                            {isActiveNode && (
                              <>
                                <span className={`text-[10px] ${
                                  ev.evaluation === 'passed' || ev.evaluation === 'completed'
                                    ? 'text-status-success'
                                    : ev.evaluation === 'failed'
                                    ? 'text-status-error'
                                    : 'text-text-muted'
                                }`}>
                                  {ev.evaluation === 'completed' ? 'done' : ev.evaluation}
                                </span>
                                <span className="text-[9px] text-text-muted">
                                  {ev.latency_ms > 0 ? `${ev.latency_ms.toFixed(0)}ms` : ''}
                                </span>
                              </>
                            )}
                            {!isActiveNode && (
                              <span className="text-[9px] text-text-muted">—</span>
                            )}
                          </div>
                        </div>
                        <p className="text-[9px] text-text-muted leading-tight mt-0.5">{meta.description}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
