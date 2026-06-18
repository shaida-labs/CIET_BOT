import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
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
