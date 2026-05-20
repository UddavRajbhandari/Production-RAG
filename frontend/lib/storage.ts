const STORAGE_KEY = 'openrouter_api_key';
const HISTORY_KEY = 'query_history';
const MAX_HISTORY = 20;

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
