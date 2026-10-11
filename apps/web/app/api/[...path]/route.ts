import { NextRequest } from 'next/server';
export const dynamic = 'force-dynamic';
const API = process.env.API_INTERNAL_URL ?? 'http://127.0.0.1:8000';
async function proxy(request: NextRequest) {
  const url = new URL(request.url);
  const headers = new Headers(request.headers);
  for (const key of [
    'host',
    'connection',
    'transfer-encoding',
    'content-length',
    'x-forwarded-for',
    'x-forwarded-host',
  ])
    headers.delete(key);
  try {
    const response = await fetch(`${API}${url.pathname}${url.search}`, {
      method: request.method,
      headers,
      redirect: 'manual',
      cache: 'no-store',
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
      // Node fetch streams uploads instead of buffering full videos in the web process.
      ...({ duplex: 'half' } as Record<string, string>),
      signal: request.signal,
    });
    const outgoing = new Headers(response.headers);
    for (const key of ['connection', 'transfer-encoding', 'content-encoding', 'content-length'])
      outgoing.delete(key);
    return new Response(response.body, { status: response.status, headers: outgoing });
  } catch {
    return Response.json(
      {
        error: { code: 'API_UNAVAILABLE', message: 'サーバーに接続できません。起動状況を確認してください。' },
      },
      { status: 503 },
    );
  }
}
export { proxy as GET, proxy as POST, proxy as PATCH, proxy as PUT, proxy as DELETE, proxy as HEAD };
