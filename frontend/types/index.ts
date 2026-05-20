export interface QueryRequest {
  query: string;
  stream?: boolean;
  include_sources?: boolean;
  llm_api_key?: string | null;
}

export interface Source {
  text: string;
  score: number;
  source: string;
  metadata?: Record<string, unknown>;
}

export interface QueryResponse {
  answer: string;
  sources: Source[] | null;
  latency_ms: number;
  validation_passed: boolean;
}

export interface SSEChunk {
  data: string;
  done?: boolean;
  error?: string;
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'offline';
  components: {
    api: string;
    qdrant: string;
    bm25: string;
    postgres: string;
    llm: string;
    llm_mode: string;
    storage_mode: {
      qdrant_mode: string;
      postgres_mode: string;
      bm25_mode: string;
    };
  };
}

export interface ErrorDetail {
  error?: string;
  message?: string;
  solution?: string;
  detail?: {
    error?: string;
    message?: string;
    solution?: string;
  };
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  error?: string;
  timestamp: number;
}

export interface QueryHistoryItem {
  id: string;
  query: string;
  timestamp: number;
  answerPreview: string;
}
