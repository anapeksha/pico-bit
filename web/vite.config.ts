import { gzipAsync } from '@gfx/zopfli';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { minify } from 'html-minifier-terser';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { defineConfig, type PluginOption } from 'vite';

const proxyTarget = process.env.PICOBIT_PROXY;

/**
 * Minify index.html
 */
function minifyHtml(): PluginOption {
  return {
    name: 'picobit-minify-html',
    async transformIndexHtml(html: string) {
      return minify(html, {
        collapseBooleanAttributes: true,
        collapseWhitespace: true,
        minifyCSS: true,
        minifyJS: true,
        removeComments: true,
        removeRedundantAttributes: true,
      });
    },
  };
}

/**
 * Gzip the final emitted assets in-place.
 *
 * The generated files keep their normal names, but their contents are gzip
 * encoded. The MicroPython server must serve them with `Content-Encoding: gzip`.
 */
function gzipBuildAssets(): PluginOption {
  let outDir = 'dist';

  return {
    name: 'picobit-gzip-only-assets',
    apply: 'build',

    configResolved(config) {
      outDir = config.build.outDir;
    },

    async closeBundle() {
      const root = process.cwd();
      const outputRoot = join(root, outDir);
      const files = ['assets/index.css', 'assets/index.js'];

      for (const fileName of files) {
        const filePath = join(outputRoot, fileName);
        const source = readFileSync(filePath);
        const gzipped = await gzipAsync(source, {
          blocksplitting: true,
          blocksplittingmax: 15,
          numiterations: 100,
        });

        writeFileSync(filePath, Buffer.from(gzipped));
        console.info(
          `[picobit] ${fileName}: ${source.length} -> ${gzipped.length} bytes`,
        );
      }
    },
  };
}

export default defineConfig({
  base: '/',
  define: {
    __PICOBIT_PROXY__: JSON.stringify(Boolean(proxyTarget)),
  },
  plugins: [svelte(), tailwindcss(), minifyHtml(), gzipBuildAssets()],
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
    },
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
