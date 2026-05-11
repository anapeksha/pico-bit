import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { minify } from 'html-minifier-terser';
import { defineConfig } from 'vite';

const proxyTarget = process.env.PICOBIT_PROXY;

function minifyHtml() {
  return {
    name: 'picobit-minify-html',
    async transformIndexHtml(html: string) {
      return minify(html, {
        collapseBooleanAttributes: true,
        collapseWhitespace: true,
        minifyCSS: false,
        minifyJS: false,
        removeComments: true,
        removeRedundantAttributes: true,
      });
    },
  };
}

export default defineConfig({
  base: '/',
  define: {
    __PICOBIT_PROXY__: JSON.stringify(Boolean(proxyTarget)),
  },
  plugins: [svelte(), tailwindcss(), minifyHtml()],
  server: {
    proxy: proxyTarget
      ? {
          '/api': proxyTarget,
          '/login': proxyTarget,
          '/logout': proxyTarget,
        }
      : undefined,
  },
  build: {
    outDir: '../dist/web',
    emptyOutDir: true,
    minify: 'terser',
    terserOptions: {
      compress: {
        passes: 2,
      },
      format: {
        comments: false,
      },
      mangle: true,
    },
    rollupOptions: {
      input: {
        index: 'index.html',
      },
      output: {
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
