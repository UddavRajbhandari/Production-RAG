import type { ChatMessage, ChatSession } from '@/types';

const STORAGE_KEY = 'openrouter_api_key';  // pragma: allowlist secret
const SESSION_API_KEY = 'app_api_key';  // pragma: allowlist secret
const TENANT_ID_KEY = 'tenant_id';  // pragma: allowlist secret
const SESSIONS_KEY = 'chat_sessions';
const ACTIVE_SESSION_KEY = 'active_session_id';
const MAX_SESSIONS = 50;

export function getStoredSessionApiKey(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem(SESSION_API_KEY) || '';
}

export function setStoredSessionApiKey(key: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(SESSION_API_KEY, key);
}

export function getStoredTenantId(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem(TENANT_ID_KEY) || '';
}

export function setStoredTenantId(id: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TENANT_ID_KEY, id);
}

export function getStoredApiKey(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem(STORAGE_KEY) || '';
}

export function setStoredApiKey(key: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY, key);
}

export function clearStoredApiKey(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(STORAGE_KEY);
}

// === Session Management ===

function getAllSessions(): ChatSession[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(SESSIONS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveAllSessions(sessions: ChatSession[]): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
}

export function createSession(files: { name: string; timestamp: number }[] = []): ChatSession {
  const now = Date.now();
  const name = files.length > 0
    ? files.map(f => f.name.split('.')[0]).join(', ').slice(0, 60)
    : 'New Chat';

  const session: ChatSession = {
    id: crypto.randomUUID(),
    name,
    files,
    messages: [],
    created_at: now,
    updated_at: now,
  };

  const sessions = getAllSessions();
  sessions.unshift(session);
  saveAllSessions(sessions.slice(0, MAX_SESSIONS));
  setActiveSession(session.id);
  return session;
}

export function getSession(id: string): ChatSession | null {
  const sessions = getAllSessions();
  return sessions.find(s => s.id === id) || null;
}

export function getActiveSession(): ChatSession | null {
  if (typeof window === 'undefined') return null;
  const activeId = localStorage.getItem(ACTIVE_SESSION_KEY);
  if (!activeId) return null;
  return getSession(activeId);
}

export function setActiveSession(id: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(ACTIVE_SESSION_KEY, id);
}

export function updateSessionMessages(sessionId: string, messages: ChatMessage[]): void {
  const sessions = getAllSessions();
  const idx = sessions.findIndex(s => s.id === sessionId);
  if (idx === -1) return;
  sessions[idx].messages = messages;
  sessions[idx].updated_at = Date.now();
  // Auto-name from first user query
  if (sessions[idx].name === 'New Chat') {
    const firstUser = messages.find(m => m.role === 'user');
    if (firstUser) {
      sessions[idx].name = firstUser.content.slice(0, 60) + (firstUser.content.length > 60 ? '...' : '');
    }
  }
  saveAllSessions(sessions);
}

export function updateSessionFiles(sessionId: string, files: { name: string; timestamp: number }[]): void {
  const sessions = getAllSessions();
  const idx = sessions.findIndex(s => s.id === sessionId);
  if (idx === -1) return;
  sessions[idx].files = files;
  sessions[idx].updated_at = Date.now();
  saveAllSessions(sessions);
}

export function deleteSession(id: string): void {
  const sessions = getAllSessions().filter(s => s.id !== id);
  saveAllSessions(sessions);
  const active = getActiveSession();
  if (active?.id === id) {
    localStorage.removeItem(ACTIVE_SESSION_KEY);
  }
}

export function getRecentSessions(limit = 20): ChatSession[] {
  return getAllSessions().slice(0, limit);
}

export function clearAllSessions(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(SESSIONS_KEY);
  localStorage.removeItem(ACTIVE_SESSION_KEY);
}

// === Legacy Query History (keep for backward compatibility) ===

const HISTORY_KEY = 'query_history';
const MAX_HISTORY = 20;

export interface HistoryEntry {
  id: string;
  query: string;
  timestamp: number;
  answerPreview: string;
}

export function getQueryHistory(): HistoryEntry[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function addToQueryHistory(query: string, answer: string): void {
  if (typeof window === 'undefined') return;
  const history = getQueryHistory();
  const entry: HistoryEntry = {
    id: crypto.randomUUID(),
    query,
    timestamp: Date.now(),
    answerPreview: answer.slice(0, 120),
  };
  const updated = [entry, ...history].slice(0, MAX_HISTORY);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
}

export function clearQueryHistory(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(HISTORY_KEY);
}
