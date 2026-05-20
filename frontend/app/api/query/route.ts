import { NextRequest, NextResponse } from 'next/server';
import { query, queryStream } from '@/lib/api-server';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as { query: string; stream?: boolean; include_sources?: boolean; llm_api_key?: string | null };
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

    const result = await query(body);
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Internal server error';
    const status = message.includes('401') ? 401 : message.includes('503') ? 503 : 500;
    return NextResponse.json({ error: message }, { status });
  }
}
