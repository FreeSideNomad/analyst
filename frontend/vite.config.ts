import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev: proxy /api → the FastAPI backend so the app is same-origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
  },
});
