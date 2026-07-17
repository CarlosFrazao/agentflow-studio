import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        // Habilita tunelamento de WebSocket (ex.: /api/v1/share/{id}/ws do
        // recurso de compartilhamento em tempo real). Sem `ws: true` o Vite
        // não faz o upgrade e o backend responde 200 em vez de 101, quebrando
        // a conexão WS no dev server.
        ws: true,
        secure: false,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    exclude: ["e2e/**", "node_modules/**"],
  },
});
