import type { QueryRequest, QueryResponse, HealthStatus } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function getServerHeaders(): HeadersInit {
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
    headers: getServerHeaders(),
    body: JSON.stringify(request),
  });
  return handleResponse<QueryResponse>(response);
}

export async function queryStream(
  request: QueryRequest,
  onChunk: (text: string) => void,
  onError: (error: string) => void
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/query/stream`, {
    method: 'POST',
    headers: getServerHeaders(),
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
        if (!data.trim() || data.trim() === '[DONE]') return;

        if (data.startsWith('{')) {
          try {
            const parsed = JSON.parse(data) as { error?: string; message?: string };
            if (parsed.error) {
              onError(parsed.message || parsed.error);
              return;
            }
          } catch {
            // Not JSON, treat as text
          }
        }

        onChunk(data);
      }
    }
  } catch (err) {
    onError(err instanceof Error ? err.message : 'Stream interrupted');
  }
}

export async function checkHealth(): Promise<HealthStatus> {
  const response = await fetch(`${API_BASE}/api/v1/health`, {
    method: 'GET',
    headers: getServerHeaders(),
  });
  return handleResponse<HealthStatus>(response);
}
