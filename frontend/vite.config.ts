import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// This build is injected into ../static/index.html as a plain <script type="module">
// (see the two `#login-view` / `#analytics-view` mount points there), not served as
// its own page -- so output filenames are fixed rather than content-hashed. That's
// safe here specifically because ../static is served with Cache-Control: no-store
// (see NoCacheStaticFiles in main.py), so there's no stale-cache risk to guard against.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../static/react",
    emptyOutDir: true,
    rollupOptions: {
      input: "src/main.tsx",
      output: {
        entryFileNames: "main.js",
        chunkFileNames: "chunk-[name].js",
        assetFileNames: "main.[ext]",
      },
    },
  },
  server: {
    proxy: {
      "/auth": "http://localhost:8000",
      "/analytics": "http://localhost:8000",
    },
  },
});
