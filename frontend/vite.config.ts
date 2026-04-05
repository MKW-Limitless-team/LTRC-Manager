import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const appBasePath = process.env.VITE_APP_BASE_PATH ?? "/";

export default defineConfig({
  base: appBasePath,
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/auth": "http://localhost:8000",
      "/ltrc": "http://localhost:8000",
      "/health": "http://localhost:8000"
    }
  }
});
