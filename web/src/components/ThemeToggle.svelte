<script lang="ts">
  import Moon from '@lucide/svelte/icons/moon';
  import Sun from '@lucide/svelte/icons/sun';
  import { theme, toggleTheme } from '../stores/theme';
</script>

<button
  class="inline-flex cursor-pointer items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-[11px] font-medium text-[var(--text-3)] transition hover:text-[var(--text)] dark:border-white/15 dark:bg-white/10 dark:hover:bg-white/15"
  type="button"
  aria-label={$theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
  aria-pressed={$theme === 'dark'}
  onclick={toggleTheme}
>
  <span class="font-mono" aria-hidden="true">
    {#if $theme === 'dark'}
      <Moon size={16} />
    {:else}
      <Sun size={16} />
    {/if}
  </span>
  <span
    class="relative h-4 w-8 rounded-full bg-[var(--border-strong)] transition dark:bg-white/25"
    aria-hidden="true"
  >
    <span
      class="absolute top-0.5 left-0.5 size-3 rounded-full bg-[var(--surface)] shadow-xl transition-transform dark:translate-x-4 dark:bg-white"
    ></span>
  </span>
</button>
