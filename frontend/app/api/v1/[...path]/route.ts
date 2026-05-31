import { NextRequest } from 'next/server';

const BACKEND_URL = process.env.API_PROXY_TARGET || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:7860';

async function proxy(req: NextRequest, path: string[], method: string): Promise<Response> {
  const pathStr = path.join('/');
  const url = `${BACKEND_URL}/api/v1/${pathStr}${req.nextUrl.search}`;

  const sessionCookie = req.cookies.get('session')?.value;
  const headers: Record<string, string> = {};
  if (sessionCookie) {
    headers['Cookie'] = `session=${sessionCookie}`;
  }

  const contentType = req.headers.get('content-type');
  if (contentType) {
    headers['Content-Type'] = contentType;
  }

  try {
    const body = method === 'GET' || method === 'DELETE' || method === 'HEAD'
      ? undefined
      : await req.text();

    const backendRes = await fetch(url, { method, headers, body });
    const resHeaders = new Headers(backendRes.headers);
    return new Response(backendRes.body, {
      status: backendRes.status,
      headers: resHeaders,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Proxy failed';
    return new Response(JSON.stringify({ error: message }), {
      status: 502,
      headers: { 'content-type': 'application/json' },
    });
  }
}

export async function GET(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path, 'GET');
}

export async function POST(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path, 'POST');
}

export async function PUT(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path, 'PUT');
}

export async function PATCH(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path, 'PATCH');
}

export async function DELETE(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxy(req, params.path, 'DELETE');
}
