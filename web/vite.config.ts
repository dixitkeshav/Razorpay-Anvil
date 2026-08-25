import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const apiProxy = {
  "/api": {
    target: process.env.ANVIL_API_URL || "http://localhost:8000",
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: apiProxy,
  },
  // `vite preview` (what the Docker image runs) reads this section, not
  // `server` -- without it, the built image would 404 every /api call.
  preview: {
    host: true,
    port: 5173,
    proxy: apiProxy,
  },
});
