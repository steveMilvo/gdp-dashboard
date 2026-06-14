import { defineConfig } from "vite";

// Relative base so the build can be hosted from any sub-path (e.g. GitHub Pages).
export default defineConfig({
  base: "./",
  server: { port: 5173, open: true },
  build: { target: "es2020", outDir: "dist" },
});
