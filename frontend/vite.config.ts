import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies API + WebSocket calls to the FastAPI backend so the
// frontend can use same-origin relative URLs (no CORS gymnastics in the browser).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
});
