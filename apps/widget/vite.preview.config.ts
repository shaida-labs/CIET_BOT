import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  base: "/widget/",
  plugins: [react()],
  build: {
    emptyOutDir: false,
    outDir: "dist",
  },
});
