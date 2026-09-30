import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// https://vite.dev/config/ · https://vitest.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    // Proxies API/auth/health calls to the FastAPI backend in local dev
    // (task 4.1), so the SPA and the API are same-origin during `npm run dev`
    // the same way FastAPI serves both in production.
    proxy: {
      "/api": "http://localhost:8000",
      "/auth": "http://localhost:8000",
      "/healthz": "http://localhost:8000",
    },
    fs: {
      // Allows serving tests/front/ (repo root), which lives outside this
      // package's own directory (D2: tests mirror krtr/front/src/ 1:1, at
      // the repo root, not alongside the source).
      allow: [path.resolve(import.meta.dirname, "../..")],
    },
  },
  test: {
    // Tests live under tests/front/ at the repo root, mirroring krtr/front/src/
    // (D2), not next to the source files.
    environment: "jsdom",
    // https, so __Host- prefixed cookies (session, CSRF) can actually be
    // set in tests — jsdom enforces the same __Host- rules real browsers do.
    environmentOptions: { jsdom: { url: "https://localhost" } },
    globals: true,
    setupFiles: ["../../tests/front/setup.ts"],
    include: ["../../tests/front/**/*.test.{ts,tsx}"],
  },
});
