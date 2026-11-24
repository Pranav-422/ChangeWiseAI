import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": new URL(".", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1").replace(/\/$/, "") } },
  test: { environment: "jsdom", include: ["tests/unit/**/*.test.{ts,tsx}"], setupFiles: ["tests/unit/setup.ts"] },
});
