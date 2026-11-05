import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const appRoot = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  root: appRoot,
  base: "/ops/",
  plugins: [react()],
  server: { host: "127.0.0.1" },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
