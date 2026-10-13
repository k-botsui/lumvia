import type { NextConfig } from 'next';
import path from 'node:path';
const config: NextConfig = {
  turbopack: { root: path.resolve(__dirname, '../..') },
  outputFileTracingRoot: path.resolve(__dirname, '../..'),
  output: 'standalone',
  images: { unoptimized: process.env.LUMVIA_DESKTOP_BUILD === '1' },
  poweredByHeader: false,
  devIndicators: false,
};
export default config;
