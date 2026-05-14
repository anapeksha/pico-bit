import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  // Only the Svelte compiler plugin — no gzip, minify, or Tailwind during tests.
  plugins: [svelte()],
  // Force browser entry points so Svelte 5's client-side `mount()` is used
  // instead of the SSR server bundle.
  resolve: {
    conditions: ['browser'],
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.ts'],
    setupFiles: ['./vitest-setup.ts'],
  },
});
