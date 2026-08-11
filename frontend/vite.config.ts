import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * In development the SPA runs on :5173 and proxies API + Django-rendered auth
 * pages to the backend on :8000, so cookies and CSRF behave as if everything
 * were served from one origin (which is exactly what nginx does in Docker).
 */
const backend = process.env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': { target: backend, changeOrigin: true },
      '/accounts': { target: backend, changeOrigin: true },
      '/admin': { target: backend, changeOrigin: true },
      '/static': { target: backend, changeOrigin: true },
      '/media': { target: backend, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
});
