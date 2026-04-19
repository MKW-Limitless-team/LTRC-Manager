import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const appBasePath = env.VITE_APP_BASE_PATH || "/";

  return {
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
  };
});
