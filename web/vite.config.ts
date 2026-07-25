import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig, TerserOptions } from 'vite';
import viteCompression from 'vite-plugin-compression';
import { viteSingleFile } from 'vite-plugin-singlefile';

// proxy target
const proxyTarget = process.env.PICOBIT_PROXY;

// terser options
const terserOptions = {
  module: true,
  compress: {
    drop_console: true,
    drop_debugger: true,
    passes: 5,
    pure_getters: true,
    toplevel: true,
    unsafe: true,
  },
  format: {
    comments: false,
  },
  mangle: {
    module: true,
    toplevel: true,
  },
} satisfies TerserOptions;

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
    target: 'esnext',
    outDir: '../dist',
    emptyOutDir: true,
    cssCodeSplit: false,
    minify: 'terser',
    cssMinify: true,
    modulePreload: false,
    assetsInlineLimit: 100000,
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
