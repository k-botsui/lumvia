import { NextRequest, NextResponse } from 'next/server';
export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString('base64');
  const development = process.env.NODE_ENV === 'development';
  const storageOrigin = process.env.STORAGE_ORIGIN || '';
  const policy = `default-src 'self'; script-src 'self' 'nonce-${nonce}' 'strict-dynamic' ${development ? "'unsafe-eval'" : ''}; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data: https://i.ytimg.com ${storageOrigin}; media-src 'self' blob: ${storageOrigin}; connect-src 'self' ${development ? 'ws: wss:' : ''} ${storageOrigin}; frame-src https://www.youtube-nocookie.com https://platform.twitter.com https://www.instagram.com https://www.tiktok.com; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`;
  const headers = new Headers(request.headers);
  headers.set('x-nonce', nonce);
  headers.set('Content-Security-Policy', policy);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set('Content-Security-Policy', policy);
  response.headers.set('X-Content-Type-Options', 'nosniff');
  response.headers.set('Referrer-Policy', 'same-origin');
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  return response;
}
export const config = { matcher: ['/((?!api|_next/static|_next/image|favicon.svg|sample.mp4).*)'] };
