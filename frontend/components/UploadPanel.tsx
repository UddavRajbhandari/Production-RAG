'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Upload, FileText, Loader2, CheckCircle, AlertCircle, ChevronDown, ChevronRight, FolderOpen } from 'lucide-react';
import { getDocuments } from '@/lib/api';
import type { DocumentInfo } from '@/types';

interface UploadedFile {
  name: string;
  status: 'pending' | 'success' | 'error';
  apiStatus?: string;
  message?: string;
  chunks?: number;
}

interface UploadPanelProps {
  sessionId: string;
  sessionFiles: { name: string; timestamp: number }[];
  onFilesChange: (files: { name: string; timestamp: number }[]) => void;
}

export default function UploadPanel({ sessionId, sessionFiles, onFilesChange }: UploadPanelProps) {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [rawDocsCollapsed, setRawDocsCollapsed] = useState(false);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [docsError, setDocsError] = useState<string | null>(null);

  // Reset local uploads when session changes
  useEffect(() => {
    setUploadedFiles([]);
  }, [sessionId]);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocuments = useCallback(async () => {
    setDocsLoading(true);
    setDocsError(null);
    try {
      const docs = await getDocuments();
      setDocuments(docs);
    } catch (err) {
      setDocsError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setDocsLoading(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setDocsLoading(true);
      try {
        const docs = await getDocuments();
        if (mounted) setDocuments(docs);
      } catch (err) {
        if (mounted) setDocsError(err instanceof Error ? err.message : 'Failed to load documents');
      } finally {
        if (mounted) setDocsLoading(false);
      }
    };
    load();
    return () => { mounted = false; };
  }, []);

  const processFiles = useCallback(async (files: FileList) => {
    setUploading(true);
    const newFiles: UploadedFile[] = Array.from(files).map(f => ({
      name: f.name,
      status: 'pending' as const,
    }));
    setUploadedFiles(prev => [...prev, ...newFiles]);

    let hasNewFile = false;

    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);

      try {
        const response = await fetch(
          '/api/ingest/file',
          {
            method: 'POST',
            body: formData,
          }
        );

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || 'Upload failed');
        }

        const result = await response.json();
        setUploadedFiles(prev => prev.map(f =>
          f.name === file.name
            ? { ...f, status: 'success', apiStatus: result.status, chunks: result.chunks_created }
            : f
        ));
        if (result.status !== 'skipped') {
          hasNewFile = true;
          onFilesChange([...sessionFiles, { name: file.name, timestamp: Date.now() }]);
        }
      } catch (err) {
        setUploadedFiles(prev => prev.map(f =>
          f.name === file.name
            ? { ...f, status: 'error', message: err instanceof Error ? err.message : 'Upload failed' }
            : f
        ));
      }
    }

    setUploading(false);

    // Refresh document list after upload — storage runs in a background
    // task on the backend, so poll a few times until it completes
    if (hasNewFile) {
      for (let attempt = 0; attempt < 3; attempt++) {
        await new Promise(r => setTimeout(r, 2000));
        try {
          const docs = await getDocuments();
          setDocuments(docs);
          setDocsError(null);
          break;
        } catch {
          // backend storage still processing, keep polling
        }
      }
    }
  }, [sessionFiles, onFilesChange]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    processFiles(files);
    e.target.value = '';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) processFiles(files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => setIsDragOver(false);

  const clearFiles = () => setUploadedFiles([]);

  return (
    <div className="flex h-full flex-col">
      <button
        onClick={() => setCollapsed(p => !p)}
        className="flex w-full items-center justify-between px-4 py-3 text-xs font-semibold uppercase tracking-wider text-text-muted hover:text-text-secondary transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <Upload size={12} />
          Upload Documents
        </span>
        {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
      </button>

      {!collapsed && (
        <div className="flex-1 overflow-y-auto px-4 pb-4">
          {/* Raw Documents — collapsible */}
          <div className="mb-3">
            <button
              onClick={() => setRawDocsCollapsed(p => !p)}
              className="mb-2 flex w-full items-center justify-between text-xs font-semibold uppercase tracking-wider text-text-muted hover:text-text-secondary transition-colors"
            >
              <span className="flex items-center gap-1.5">
                <FolderOpen size={12} />
                Raw Documents
                {!docsLoading && <span className="font-normal normal-case text-text-muted/60">({documents.length})</span>}
              </span>
              {rawDocsCollapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
            </button>
            {!rawDocsCollapsed && (
              <>
                {docsLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 size={14} className="animate-spin text-text-muted" />
                  </div>
                ) : docsError ? (
                  <div className="rounded-card border border-status-error/30 bg-status-error/5 p-3 text-center">
                    <p className="text-[10px] text-status-error">{docsError}</p>
                    <button
                      onClick={loadDocuments}
                      className="mt-2 rounded-input border border-border bg-background-surface px-3 py-1 text-[10px] text-text-secondary hover:text-accent-primary transition-colors"
                    >
                      Retry
                    </button>
                  </div>
                ) : documents.length > 0 ? (
                  <div className="space-y-1 max-h-[40vh] overflow-y-auto rounded-card border border-border bg-background-surface p-2">
                    {documents.map((doc) => (
                      <div
                        key={doc.source_file}
                        className="flex items-center gap-2 rounded-input bg-background-muted/50 px-2.5 py-2 hover:bg-background-muted transition-colors"
                      >
                        <FileText size={12} className="shrink-0 text-accent-primary" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[11px] font-medium text-text-primary">{doc.source_file}</p>
                          <div className="flex items-center gap-2 text-[9px] text-text-muted">
                            <span className="capitalize">{doc.department}</span>
                            <span>{doc.year}</span>
                            {doc.chunk_count > 0 && <span>{doc.chunk_count} chunks</span>}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-card border border-border bg-background-surface p-3 text-center">
                    <p className="text-[10px] text-text-muted">No documents in database</p>
                    <p className="text-[9px] text-text-muted/60 mt-0.5">Upload files below to populate</p>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Upload drop zone */}
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
            className={`mb-3 cursor-pointer rounded-card border-2 border-dashed p-4 text-center transition-all ${
              isDragOver
                ? 'border-accent-primary bg-accent-primary/5'
                : 'border-border bg-background-muted hover:border-accent-primary/50 hover:bg-background-surface'
            }`}
          >
            <Upload size={20} className="mx-auto mb-2 text-text-muted" />
            <p className="text-xs font-medium text-text-secondary">
              {isDragOver ? 'Drop files here' : 'Drop files or click'}
            </p>
            <p className="mt-1 text-[10px] text-text-muted">PDF, DOCX, XLSX</p>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.doc,.xlsx,.xls"
            onChange={handleFileSelect}
            className="hidden"
          />

          {/* Session files */}
          {sessionFiles.length > 0 && (
            <div className="mb-3">
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                Session Files
              </p>
              <div className="space-y-1">
                {sessionFiles.map((f, idx) => (
                  <div key={`sf-${idx}`} className="flex items-center gap-1.5 rounded-input bg-accent-primary/5 px-2.5 py-1.5">
                    <FileText size={10} className="text-accent-primary" />
                    <span className="truncate text-[10px] text-text-primary">{f.name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Upload progress */}
          {uploadedFiles.length > 0 && (
            <div className="mb-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  Uploads ({uploadedFiles.length})
                </span>
                <button
                  onClick={clearFiles}
                  className="text-[10px] text-text-muted hover:text-status-error"
                  disabled={uploading}
                >
                  Clear
                </button>
              </div>
              {uploadedFiles.map((file, idx) => (
                <div
                  key={`${file.name}-${idx}`}
                  className="flex items-center gap-2 rounded-input border border-border-subtle bg-background-muted px-2.5 py-2"
                >
                  {file.status === 'pending' ? (
                    <Loader2 size={12} className="animate-spin text-text-muted" />
                  ) : file.status === 'success' ? (
                    <CheckCircle size={12} className="text-status-success" />
                  ) : (
                    <AlertCircle size={12} className="text-status-error" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs text-text-primary">{file.name}</p>
                  </div>
                  {file.status === 'success' && file.apiStatus === 'skipped' && (
                    <span className="shrink-0 text-[10px] text-text-muted">Duplicate</span>
                  )}
                  {file.status === 'success' && file.apiStatus !== 'skipped' && (
                    <span className="shrink-0 text-[10px] text-accent-primary">{file.chunks}c</span>
                  )}
                  {file.status === 'error' && (
                    <span className="shrink-0 text-[10px] text-status-error">Error</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
