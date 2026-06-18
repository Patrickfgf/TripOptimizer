/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") } },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./vitest.setup.ts",
    css: true,
    coverage: {
      provider: "v8",
      reportsDirectory: "./coverage",
      exclude: ["src/components/ui/**", "src/main.tsx", "**/*.config.*", "src/test/**", "src/vite-env.d.ts", "src/world-atlas.d.ts"],
      thresholds: { lines: 80, functions: 80 },
    },
  },
});
