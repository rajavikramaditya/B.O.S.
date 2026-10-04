import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development the dashboard proxies API calls to the backend on :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/v1": "http://localhost:8000",
      "/mcp": "http://localhost:8000",
    },
  },
});
