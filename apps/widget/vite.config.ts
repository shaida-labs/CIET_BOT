import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Keep local widget development same-origin. This avoids fragile browser
    // CORS state while still forwarding every API call to the Docker backend.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  build: {
    // The embed injects its stylesheet into a Shadow DOM. Inline the Indic
    // fonts so /ciet-ai.js remains a complete, portable embed artifact.
    assetsInlineLimit: 200_000,
    lib: {
      entry: "src/embed.tsx",
      name: "CIETAIWidget",
      formats: ["iife"],
      fileName: () => "ciet-ai.js",
    },
    cssCodeSplit: false,
    rollupOptions: {
      output: { assetFileNames: "ciet-ai.css" },
    },
  },
});
