import type { Metadata, Viewport } from 'next';
import './globals.css';
export const metadata: Metadata = {
  title: 'Lumvia — 動画とリンクのライブラリ',
  description: '動画・リンクの管理、区間保存、Shelfの共有。',
  icons: { icon: '/favicon.svg', apple: '/brand/app-icon-192.png' },
  appleWebApp: { capable: true, title: 'Lumvia', statusBarStyle: 'default' },
};
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  themeColor: '#f5f5f7',
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
