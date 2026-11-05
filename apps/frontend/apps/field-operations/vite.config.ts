import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const appRoot = fileURLToPath(new URL(".", import.meta.url));
const gatewayTarget = process.env.KOKONUT_GATEWAY_DEV_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  root: appRoot,
  base: "/field/",
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    proxy: {
      "/operator": { target: gatewayTarget, changeOrigin: false },
      "/api/mobile": { target: gatewayTarget, changeOrigin: false },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
