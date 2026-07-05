import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// Proxy /api → the FastAPI backend so the app is same-origin.
// ANALYST_API overrides the target (used by the e2e harness, which runs the
// API on an ephemeral port); `vite preview` inherits server.proxy.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'ANALYST_');
  const api = env.ANALYST_API ?? 'http://127.0.0.1:8000';
  return {
    plugins: [react()],
    server: { port: 5173, proxy: { '/api': api } },
    preview: { proxy: { '/api': api } },
  };
});
