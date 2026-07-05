import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  preprocess: vitePreprocess(),
  onwarn(warning, defaultHandler) {
    defaultHandler(warning);
    throw new Error(`Svelte compiler warning: ${warning.code}`);
  },
};
