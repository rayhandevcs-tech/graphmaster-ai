import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

/**
 * The tests cover the foundation's risky parts: the fetch wrapper's refresh
 * retry, the token store, the route guard, and the palette rules that are easy
 * to break by hand. Pages are covered from sprint 11, when there is behaviour
 * in them worth asserting on.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
  },
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname) },
  },
});
