import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// All API calls are relative (/api/v1/...) and proxied to Django, so the
// browser sees one origin and CORS never enters the picture. In Docker,
// nginx plays the same role.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
