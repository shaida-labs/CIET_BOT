import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Mirror apps/widget/vite.config.ts: keep admin development same-origin
    // and forward /api to the Docker backend instead of baking in a host.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
