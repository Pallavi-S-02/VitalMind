import { NextRequest, NextResponse } from 'next/server';

const RENDER_BACKEND = 'https://vitalmind-backend.onrender.com';

async function handler(req: NextRequest, { params }: { params: { path: string[] } }) {
  const path = params.path.join('/');
  const targetUrl = `${RENDER_BACKEND}/${path}${req.nextUrl.search}`;

  // Forward the request to the Render backend
  const headers = new Headers();
  
  // Copy relevant headers from the original request
  const authHeader = req.headers.get('Authorization');
  if (authHeader) headers.set('Authorization', authHeader);
  
  const contentType = req.headers.get('Content-Type');
  if (contentType) headers.set('Content-Type', contentType);

  const body = ['GET', 'HEAD'].includes(req.method) ? undefined : await req.text();

  const response = await fetch(targetUrl, {
    method: req.method,
    headers,
    body,
  });

  const responseData = await response.text();

  return new NextResponse(responseData, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('Content-Type') || 'application/json',
    },
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
export const OPTIONS = handler;
