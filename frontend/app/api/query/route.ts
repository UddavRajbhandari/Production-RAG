import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.API_PROXY_TARGET || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:7860';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as { query: string; stream?: boolean; include_sources?: boolean; llm_api_key?: string | null; source_files?: string[] };
    const isStreaming = body.stream === true;

    const sessionCookie = req.cookies.get('session')?.value;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (sessionCookie) {
      headers['Cookie'] = `session=${sessionCookie}`;
    }

    if (isStreaming) {
      const backendRes = await fetch(`${BACKEND_URL}/api/v1/query/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      });

      return new Response(backendRes.body, {
        headers: {
          'Content-Type': 'text/event-stream',
          'X-Accel-Buffering': 'no',
          'Cache-Control': 'no-store',
        },
      });
    }

    const backendRes = await fetch(`${BACKEND_URL}/api/v1/query`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });
    const result = await backendRes.json();
    if (!backendRes.ok) {
      const detail = result?.detail as Record<string, unknown> | undefined;
      const msg = (detail?.message as string) || (detail?.error as string) || (result?.message as string) || (result?.error as string) || `HTTP ${backendRes.status}`;
      return NextResponse.json({ error: msg }, { status: backendRes.status });
    }
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Internal server error';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
