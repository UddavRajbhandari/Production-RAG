import type { QueryRequest, QueryResponse, RetrieveResponse, HealthStatus, DocumentInfo, Source, NodeEvaluation, RagasScores } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

function getHeaders(): HeadersInit {
  return {
    'Content-Type': 'application/json',
    'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || '',
  };
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('application/json')) {
      const errorData = (await response.json()) as Record<string, unknown>;
      const detail = errorData.detail as Record<string, unknown> | undefined;
      throw new Error(
        (detail?.message as string) ||
        (detail?.error as string) ||
        (errorData.message as string) ||
        (errorData.error as string) ||
        `HTTP ${response.status}`
      );
    }
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export async function query(request: QueryRequest): Promise<QueryResponse> {
  const response = await fetch(`${API_BASE}/api/v1/query`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(request),
  });
  return handleResponse<QueryResponse>(response);
}

export async function queryStream(
  request: QueryRequest,
  onChunk: (text: string) => void,
  onMetadata: (meta: {
    sources: Source[] | null;
    node_evaluations: NodeEvaluation[] | null;
    validation_passed: boolean;
    latency_ms: number;
    error_message: string | null;
    ragas_scores: RagasScores | null;
  }) => void,
  onDone: () => void,
  onError: (error: string) => void
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/query/stream`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ ...request, stream: true }),
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as Record<string, unknown>;
    const detail = errorData.detail as Record<string, unknown> | undefined;
    onError(
      (detail?.message as string) ||
      (detail?.error as string) ||
      (errorData.message as string) ||
      (errorData.error as string) ||
      `HTTP ${response.status}`
    );
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    onError('No response body');
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6);
        if (!data.trim() || data.trim() === '[DONE]') {
          onDone();
          return;
        }

        if (data.startsWith('{')) {
          try {
            const parsed = JSON.parse(data) as Record<string, unknown>;
            if (parsed.error) {
              onError((parsed.message as string) || (parsed.error as string));
              return;
            }
            if ('sources' in parsed || 'node_evaluations' in parsed) {
              onMetadata(parsed as {
                sources: Source[] | null;
                node_evaluations: NodeEvaluation[] | null;
                validation_passed: boolean;
                latency_ms: number;
                error_message: string | null;
                ragas_scores: RagasScores | null;
              });
              continue;
            }
          } catch {
            // Not JSON, treat as text chunk
          }
        }

        onChunk(data);
      }
    }
    onDone();
  } catch (err) {
    onError(err instanceof Error ? err.message : 'Stream interrupted');
  }
}

export async function retrieveQuery(request: QueryRequest): Promise<RetrieveResponse> {
  const response = await fetch(`${API_BASE}/api/v1/query/retrieve`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ query: request.query }),
  });
  return handleResponse<RetrieveResponse>(response);
}

export async function checkHealth(): Promise<HealthStatus> {
  const response = await fetch(`${API_BASE}/api/v1/health`, {
    method: 'GET',
  });
  return handleResponse<HealthStatus>(response);
}

export interface IngestResponse {
  status: string;
  chunks_created: number;
  document_id: string;
}

export interface DocumentStats {
  total_chunks: number;
  by_department: Record<string, number>;
  by_year: Record<string, number>;
  by_domain: Record<string, number>;
}

export async function ingestDocument(
  textContent: string,
  metadata?: Record<string, string>
): Promise<IngestResponse> {
  const response = await fetch(`${API_BASE}/api/v1/ingest`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ text_content: textContent, metadata }),
  });
  return handleResponse<IngestResponse>(response);
}

export async function getDocumentStats(): Promise<DocumentStats> {
  const response = await fetch(`${API_BASE}/api/v1/metadata/stats`, {
    method: 'GET',
    headers: getHeaders(),
  });
  return handleResponse<DocumentStats>(response);
}

export async function getDepartments(): Promise<string[]> {
  const response = await fetch(`${API_BASE}/api/v1/metadata/departments`, {
    method: 'GET',
    headers: getHeaders(),
  });
  return handleResponse<string[]>(response);
}

export async function getDocuments(): Promise<DocumentInfo[]> {
  const response = await fetch(`${API_BASE}/api/v1/metadata/documents`, {
    method: 'GET',
    headers: getHeaders(),
  });
  return handleResponse<DocumentInfo[]>(response);
}
