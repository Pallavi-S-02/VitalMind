import { NextRequest, NextResponse } from 'next/server';

const RENDER_BACKEND = 'https://vitalmind-backend.onrender.com';

// Headers to skip when forwarding (host must be set to backend's host, not Vercel's)
const SKIP_HEADERS = new Set(['host', 'connection', 'transfer-encoding', 'content-length']);

async function handler(req: NextRequest, { params }: { params: { path: string[] } }) {
  const path = (params.path || []).join('/');
  const targetUrl = `${RENDER_BACKEND}/${path}${req.nextUrl.search}`;

  // Forward ALL headers except ones that would break the proxy
  const forwardHeaders: Record<string, string> = {};
  req.headers.forEach((value, key) => {
    if (!SKIP_HEADERS.has(key.toLowerCase())) {
      forwardHeaders[key] = value;
    }
  });

  // Ensure Authorization is explicitly set (belt and suspenders)
  const authHeader = req.headers.get('authorization') || req.headers.get('Authorization');
  if (authHeader) {
    forwardHeaders['Authorization'] = authHeader;
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
        'Access-Control-Allow-Origin': '*',
      },
    });
  } catch (err) {
    console.error('[proxy] Error forwarding request to backend:', err);
    return NextResponse.json({ message: 'Proxy error: could not reach backend' }, { status: 502 });
  }
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
export const OPTIONS = handler;
