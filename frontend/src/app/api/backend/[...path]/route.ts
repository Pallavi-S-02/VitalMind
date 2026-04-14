import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@/auth';

const RENDER_BACKEND = 'https://vitalmind-backend.onrender.com';
const SKIP_HEADERS = new Set(['host', 'connection', 'transfer-encoding', 'content-length', 'cookie']);

async function handler(req: NextRequest, { params }: { params: { path: string[] } }) {
  // ✅ Get the JWT token server-side from the NextAuth session
  // This is reliable because the browser always sends cookies (same-origin),
  // so auth() correctly identifies who is making the request.
  const session = await auth();

  const path = (params.path || []).join('/');
  const targetUrl = `${RENDER_BACKEND}/${path}${req.nextUrl.search}`;

  // Build outgoing headers, skipping ones that would break the proxy
  const forwardHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  req.headers.forEach((value, key) => {
    if (!SKIP_HEADERS.has(key.toLowerCase())) {
      forwardHeaders[key] = value;
    }
  });

  // Always inject the backend JWT from the server session
  const accessToken = (session as any)?.accessToken;
  if (accessToken) {
    forwardHeaders['Authorization'] = `Bearer ${accessToken}`;
  }

  const body = ['GET', 'HEAD'].includes(req.method) ? undefined : await req.text();

  try {
    const response = await fetch(targetUrl, {
      method: req.method,
      headers: forwardHeaders,
      body,
    });

    const responseData = await response.text();

    return new NextResponse(responseData, {
      status: response.status,
      headers: {
        'Content-Type': response.headers.get('Content-Type') || 'application/json',
      },
    });
  } catch (err) {
    console.error('[proxy] Error forwarding to backend:', err);
    return NextResponse.json({ message: 'Proxy error: could not reach backend' }, { status: 502 });
  }
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
export const OPTIONS = handler;
