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

export interface NodeEvaluation {
  node: string;
  latency_ms: number;
  evaluation: string;
}

export interface RagasScores {
  context_precision: number;
  answer_relevancy: number;
  answer_completeness: number;
  faithfulness: number;
}

export interface QueryResponse {
  answer: string;
  sources: Source[] | null;
  latency_ms: number;
  validation_passed: boolean;
  error_message?: string | null;
  node_evaluations?: NodeEvaluation[] | null;
  ragas_scores?: RagasScores | null;
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
  node_evaluations?: NodeEvaluation[] | null;
  validation_passed?: boolean;
  latency_ms?: number;
  error_message?: string | null;
  ragas_scores?: RagasScores | null;
}

export interface DocumentInfo {
  source_file: string;
  chunk_count: number;
  year: string;
  department: string;
}

export interface RetrieveResponse {
  query: string;
  results: Source[];
  count: number;
}

export interface ChatSession {
  id: string;
  name: string;
  files: { name: string; timestamp: number }[];
  messages: ChatMessage[];
  created_at: number;
  updated_at: number;
}
