import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.API_PROXY_TARGET || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:7860';

export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const formData = await request.formData();
    const file = formData.get('file');
    if (!file || !(file instanceof File)) {
      return NextResponse.json({ detail: 'No file provided' }, { status: 400 });
    }
    const sessionCookie = request.cookies.get('session')?.value;

    const backendForm = new FormData();
    backendForm.append('file', file, file.name);

    const headers: Record<string, string> = {};
    if (sessionCookie) {
      headers['Cookie'] = `session=${sessionCookie}`;
    }

    const response = await fetch(`${BACKEND_URL}/api/v1/ingest/file`, {
      method: 'POST',
      headers,
      body: backendForm,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      return NextResponse.json(error, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { detail: err instanceof Error ? err.message : 'Upload proxy failed' },
      { status: 502 }
    );
  }
}
