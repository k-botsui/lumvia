import type { Metadata, Viewport } from 'next';
import localFont from 'next/font/local';
import './globals.css';
import './atelier.css';
import './studio.css';

const rounded = localFont({
  src: '../public/fonts/quicksand-variable.ttf',
  variable: '--font-rounded',
  weight: '300 700',
  display: 'swap',
});
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
  themeColor: '#fafbfe',
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ja" className={rounded.variable}>
      <body>
        {process.env.LUMVIA_DESIGN_PREVIEW === '1' && (
          <div className="design-preview-badge">DESIGN PREVIEW · サンプルデータ / 変更は一時保存</div>
        )}
        {children}
      </body>
    </html>
  );
}
