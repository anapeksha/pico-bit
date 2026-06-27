import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';
import viteCompression from 'vite-plugin-compression';
import { viteSingleFile } from 'vite-plugin-singlefile';

const proxyTarget = process.env.PICOBIT_PROXY;
const terserOptions = {
  module: true,
  compress: {
    drop_console: true,
    passes: 5,
    pure_getters: true,
    toplevel: true,
  },
  format: {
    comments: false,
  },
  mangle: {
    module: true,
    toplevel: true,
  },
};

export default defineConfig({
  base: '/',
  define: {
    __PICOBIT_PROXY__: JSON.stringify(Boolean(proxyTarget)),
  },
  plugins: [
    svelte(),
    tailwindcss(),
    viteSingleFile({ removeViteModuleLoader: true }),
    viteCompression({
      algorithm: 'gzip',
      deleteOriginFile: true,
      ext: '',
      filter: /index\.html$/i,
      threshold: 0,
    }),
  ],
  server: {
    proxy: proxyTarget
      ? {
          '/api': proxyTarget,
        }
      : undefined,
  },
  build: {
    outDir: '../dist',
    emptyOutDir: true,
    cssCodeSplit: false,
    minify: 'terser',
    cssMinify: true,
    chunkSizeWarningLimit: 2000,
    terserOptions,
    rolldownOptions: {
      input: {
        index: 'index.html',
      },
      output: {
        minify: true,
        entryFileNames: 'assets/index.js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: (assetInfo) => {
          if (assetInfo.names?.some((name) => name.endsWith('.css'))) {
            return 'assets/index.css';
          }
          return 'assets/[name][extname]';
        },
      },
    },
  },
});
