import { NextRequest, NextResponse } from 'next/server';
import { queryStream } from '@/lib/api-server';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as { query: string; stream?: boolean; include_sources?: boolean; llm_api_key?: string | null; source_files?: string[] };
    const isStreaming = body.stream === true;

    if (isStreaming) {
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        async start(controller) {
          const enqueue = (chunk: string) => {
            controller.enqueue(encoder.encode(`data: ${chunk}\n\n`));
          };

          const onChunk = (text: string) => enqueue(text);
          const onError = (error: string) => {
            enqueue(JSON.stringify({ error, message: error }));
          };

          await queryStream(body, onChunk, onError);
          controller.enqueue(encoder.encode('data: [DONE]\n\n'));
          controller.close();
        },
      });

      return new Response(stream, {
        headers: {
          'Content-Type': 'text/event-stream',
          'X-Accel-Buffering': 'no',
          'Cache-Control': 'no-store',
        },
      });
    }

    const backendRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/v1/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || '',
      },
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
