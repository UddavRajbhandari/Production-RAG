'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { FileText, Upload, X, Loader2, BarChart2, File, CheckCircle, AlertCircle } from 'lucide-react';
import Navbar from '@/components/Navbar';
import { getDocumentStats, getDepartments } from '@/lib/api';

interface UploadedFile {
  name: string;
  status: 'pending' | 'success' | 'error';
  message?: string;
  chunks?: number;
  documentId?: string;
}

interface DocumentStats {
  total_chunks: number;
  by_department: Record<string, number>;
  by_year: Record<string, number>;
  by_domain: Record<string, number>;
}

export default function DocumentsPage() {
  const [stats, setStats] = useState<DocumentStats | null>(null);
  const [departments, setDepartments] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'stats' | 'upload' | 'files'>('stats');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [textContent, setTextContent] = useState('');
  const [deptFilter, setDeptFilter] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadStats = useCallback(async () => {
    setLoading(true);
    try {
      const [s, d] = await Promise.all([getDocumentStats(), getDepartments()]);
      setStats(s);
      setDepartments(d);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!textContent.trim()) return;
    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || '' },
        body: JSON.stringify({ text_content: textContent, metadata: deptFilter ? { department: deptFilter } : undefined }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Upload failed');
      }
      const result = await response.json();
      setUploadSuccess(`Ingested ${result.chunks_created} chunks (ID: ${result.document_id})`);
      setTextContent('');
      setDeptFilter('');
      loadStats();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    const newFiles: UploadedFile[] = Array.from(files).map(f => ({
      name: f.name,
      status: 'pending' as const,
    }));
    setUploadedFiles(prev => [...prev, ...newFiles]);

    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);

      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/ingest/file`, {
          method: 'POST',
          headers: { 'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || '' },
          body: formData,
        });

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || 'Upload failed');
        }

        const result = await response.json();
        setUploadedFiles(prev => prev.map(f =>
          f.name === file.name
            ? { ...f, status: 'success', chunks: result.chunks_created, documentId: result.document_id }
            : f
        ));
      } catch (err) {
        setUploadedFiles(prev => prev.map(f =>
          f.name === file.name
            ? { ...f, status: 'error', message: err instanceof Error ? err.message : 'Upload failed' }
            : f
        ));
      }
    }

    setUploading(false);
    loadStats();
  };

  const clearUploadedFiles = () => setUploadedFiles([]);

  const statCards = [
    { label: 'Total Chunks', value: stats?.total_chunks ?? 0, icon: <FileText size={18} /> },
    { label: 'Departments', value: departments.length, icon: <BarChart2 size={18} /> },
    { label: 'Years', value: Object.keys(stats?.by_year ?? {}).length, icon: <BarChart2 size={18} /> },
    { label: 'Domains', value: Object.keys(stats?.by_domain ?? {}).length, icon: <BarChart2 size={18} /> },
  ];

  return (
    <div className="flex min-h-screen flex-col bg-background-primary">
      <Navbar />
      <main className="mx-auto w-full max-w-4xl px-4 pt-20 sm:px-6">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="font-display text-2xl font-bold text-text-primary">Documents</h1>
            <p className="mt-1 text-sm text-text-muted">Ingest documents and view system statistics</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('stats')}
              className={`rounded-input px-4 py-2 text-sm transition-all ${activeTab === 'stats' ? 'border border-accent-primary bg-accent-primary/10 text-accent-primary' : 'border border-border bg-background-surface text-text-secondary hover:border-accent-primary/50'}`}
            >
              <BarChart2 size={14} className="mr-1.5 inline-block" />
              Statistics
            </button>
            <button
              onClick={() => setActiveTab('upload')}
              className={`rounded-input px-4 py-2 text-sm transition-all ${activeTab === 'upload' ? 'border border-accent-primary bg-accent-primary/10 text-accent-primary' : 'border border-border bg-background-surface text-text-secondary hover:border-accent-primary/50'}`}
            >
              <Upload size={14} className="mr-1.5 inline-block" />
              Text
            </button>
            <button
              onClick={() => setActiveTab('files')}
              className={`rounded-input px-4 py-2 text-sm transition-all ${activeTab === 'files' ? 'border border-accent-primary bg-accent-primary/10 text-accent-primary' : 'border border-border bg-background-surface text-text-secondary hover:border-accent-primary/50'}`}
            >
              <File size={14} className="mr-1.5 inline-block" />
              Files
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex h-48 items-center justify-center">
            <Loader2 size={24} className="animate-spin text-accent-primary" />
          </div>
        ) : activeTab === 'stats' ? (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {statCards.map((card) => (
                <div key={card.label} className="rounded-card border border-border bg-background-surface p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-medium uppercase tracking-wider text-text-muted">{card.label}</span>
                    <span className="text-accent-primary">{card.icon}</span>
                  </div>
                  <p className="font-display text-2xl font-bold text-text-primary">{card.value}</p>
                </div>
              ))}
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-card border border-border bg-background-surface p-4">
                <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-muted">By Department</h3>
                <div className="space-y-2">
                  {Object.entries(stats?.by_department ?? {}).length === 0 ? (
                    <p className="text-xs text-text-muted">No data</p>
                  ) : (
                    Object.entries(stats?.by_department ?? {}).map(([dept, count]) => (
                      <div key={dept} className="flex items-center justify-between">
                        <span className="text-sm text-text-secondary">{dept}</span>
                        <span className="text-xs font-mono text-accent-primary">{count}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="rounded-card border border-border bg-background-surface p-4">
                <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-muted">By Year</h3>
                <div className="space-y-2">
                  {Object.entries(stats?.by_year ?? {}).length === 0 ? (
                    <p className="text-xs text-text-muted">No data</p>
                  ) : (
                    Object.entries(stats?.by_year ?? {}).map(([year, count]) => (
                      <div key={year} className="flex items-center justify-between">
                        <span className="text-sm text-text-secondary">{year}</span>
                        <span className="text-xs font-mono text-accent-primary">{count}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="rounded-card border border-border bg-background-surface p-4">
                <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-muted">By Domain</h3>
                <div className="space-y-2">
                  {Object.entries(stats?.by_domain ?? {}).length === 0 ? (
                    <p className="text-xs text-text-muted">No data</p>
                  ) : (
                    Object.entries(stats?.by_domain ?? {}).map(([domain, count]) => (
                      <div key={domain} className="flex items-center justify-between">
                        <span className="text-sm text-text-secondary">{domain}</span>
                        <span className="text-xs font-mono text-accent-primary">{count}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : activeTab === 'upload' ? (
          <form onSubmit={handleUpload} className="space-y-4">
            <div className="rounded-card border border-border bg-background-surface p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-medium text-text-primary">Paste Document Text</h3>
                <button
                  type="button"
                  onClick={() => setTextContent('')}
                  className="flex items-center gap-1 text-xs text-text-muted hover:text-status-error"
                >
                  <X size={12} /> Clear
                </button>
              </div>
              <textarea
                ref={textareaRef}
                value={textContent}
                onChange={(e) => setTextContent(e.target.value)}
                placeholder="Paste your document content here. The system will ingest this text and make it searchable for queries..."
                className="w-full resize-none rounded-input border border-border bg-background-muted px-3.5 py-3 text-sm text-text-primary placeholder:text-text-muted"
                rows={12}
              />
            </div>

            <div className="rounded-card border border-border bg-background-surface p-4">
              <label className="mb-2 block text-sm font-medium text-text-primary">Department</label>
              <select
                value={deptFilter}
                onChange={(e) => setDeptFilter(e.target.value)}
                className="w-full rounded-input border border-border bg-background-muted px-3.5 py-2.5 text-sm text-text-primary"
              >
                <option value="">General (no filter)</option>
                {departments.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
              <p className="mt-1.5 text-xs text-text-muted">Tag this document with a department category</p>
            </div>

            {uploadError && (
              <div className="rounded-input border border-status-error/40 bg-status-error/5 px-4 py-3 text-sm text-status-error">
                {uploadError}
              </div>
            )}
            {uploadSuccess && (
              <div className="rounded-input border border-status-success/40 bg-status-success/5 px-4 py-3 text-sm text-status-success">
                {uploadSuccess}
              </div>
            )}

            <button
              type="submit"
              disabled={!textContent.trim() || uploading}
              className="flex w-full items-center justify-center gap-2 rounded-input border border-accent-primary bg-accent-primary px-4 py-3 text-sm font-medium text-background-primary transition-all hover:bg-accent-primary/90 disabled:opacity-40 disabled:hover:bg-accent-primary"
            >
              {uploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
              {uploading ? 'Ingesting...' : 'Ingest Document'}
            </button>
          </form>
        ) : activeTab === 'files' ? (
          <div className="space-y-4">
            <div className="rounded-card border border-border bg-background-surface p-6">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-text-primary">Upload Files</h3>
                  <p className="mt-1 text-xs text-text-muted">Upload PDF, DOCX, TXT files to ingest into the knowledge base</p>
                </div>
                {uploadedFiles.length > 0 && (
                  <button
                    onClick={clearUploadedFiles}
                    className="text-xs text-text-muted hover:text-status-error"
                  >
                    Clear all
                  </button>
                )}
              </div>

              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.doc,.txt,.xlsx,.xls,.pptx,.ppt"
                onChange={handleFileUpload}
                className="hidden"
              />

              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="flex w-full items-center justify-center gap-2 rounded-input border border-dashed border-border bg-background-muted px-4 py-6 text-sm text-text-secondary transition-all hover:border-accent-primary hover:bg-background-primary disabled:opacity-50"
              >
                {uploading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Upload size={16} />
                )}
                {uploading ? 'Uploading...' : 'Click to select files or drag and drop'}
              </button>

              <p className="mt-2 text-center text-xs text-text-muted">
                Supported: PDF, DOCX, TXT, XLSX, PPTX
              </p>
            </div>

            {uploadedFiles.length > 0 && (
              <div className="rounded-card border border-border bg-background-surface p-4">
                <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-text-muted">Uploaded Files</h3>
                <div className="space-y-2">
                  {uploadedFiles.map((file, idx) => (
                    <div
                      key={`${file.name}-${idx}`}
                      className="flex items-center justify-between rounded-input border border-border-subtle bg-background-muted px-3 py-2"
                    >
                      <div className="flex items-center gap-3">
                        {file.status === 'pending' ? (
                          <Loader2 size={14} className="animate-spin text-text-muted" />
                        ) : file.status === 'success' ? (
                          <CheckCircle size={14} className="text-status-success" />
                        ) : (
                          <AlertCircle size={14} className="text-status-error" />
                        )}
                        <span className="text-sm text-text-primary">{file.name}</span>
                      </div>
                      <div className="text-right">
                        {file.status === 'success' ? (
                          <span className="text-xs text-accent-primary">{file.chunks} chunks</span>
                        ) : file.status === 'error' ? (
                          <span className="text-xs text-status-error">{file.message}</span>
                        ) : (
                          <span className="text-xs text-text-muted">Processing...</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : null}
      </main>
    </div>
  );
}
