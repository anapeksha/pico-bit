import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/vite-plugin-svelte').Options} */
const config = {
  preprocess: vitePreprocess(),
  compilerOptions: {
    preserveComments: false,
  },
  onwarn(warning, defaultHandler) {
    defaultHandler(warning);
    throw new Error(`Svelte compiler warning: ${warning.code}`);
  },
};

export default config;
