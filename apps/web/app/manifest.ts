import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Lumvia',
    short_name: 'Lumvia',
    description: '動画・リンクの管理、区間保存、Shelfの共有。',
    start_url: '/?view=home',
    scope: '/',
    display: 'standalone',
    background_color: '#f5f5f7',
    theme_color: '#f5f5f7',
    icons: [
      { src: '/brand/app-icon-192.png', sizes: '192x192', type: 'image/png' },
      { src: '/brand/app-icon-512.png', sizes: '512x512', type: 'image/png' },
    ],
  };
}
