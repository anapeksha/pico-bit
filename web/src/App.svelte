<script lang="ts">
  import { onMount } from 'svelte';
  import AppSkeleton from './components/AppSkeleton.svelte';
  import ThemeToggle from './components/ThemeToggle.svelte';
  import ValidationModal from './components/ValidationModal.svelte';
  import LeftSection from './sections/LeftSection.svelte';
  import MiddleSection from './sections/MiddleSection.svelte';
  import RightSection from './sections/RightSection.svelte';
  import TopSection from './sections/TopSection.svelte';
  import { startApp } from './stores/bootstrap';
  import { initTheme } from './stores/theme';
  import { globalError, notice, showNotice } from './stores/ui';

  let bootstrapPromise = $state<Promise<void>>(new Promise(() => {}));

  onMount(() => {
    const stopTheme = initTheme();

    let stop: (() => void) | null = null;
    let cancelled = false;

    const bootstrapTask = startApp();

    bootstrapTask.then((fn) => {
      if (cancelled) fn();
      else stop = fn;
    });

    bootstrapPromise = bootstrapTask
      .then(() => {})
      .catch((error: Error) => {
        showNotice(error.message || 'Bootstrap failed.', 'error');
        throw error;
      });

    return () => {
      cancelled = true;
      stop?.();
      stopTheme();
    };
  });

  function handleBoundaryError(error: unknown) {
    // eslint-disable-next-line no-console
    console.error('App render error:', error);
    showNotice((error as Error)?.message || 'An unexpected error occurred.', 'error');
  }
</script>

{#if $globalError}
  <div
    class="fixed inset-0 z-9999 flex min-h-screen flex-col items-center justify-center bg-picobit-surface-3 p-6"
    role="alert"
    aria-live="assertive"
  >
    <div
      class="w-full max-w-lg rounded-[14px] border border-picobit-danger-border bg-picobit-surface p-8 shadow-xl"
    >
      <p
        class="mb-1 text-[11px] font-medium uppercase tracking-widest text-picobit-danger opacity-70"
      >
        Fatal Error
      </p>
      <h1 class="m-0 mb-4 text-[18px] font-semibold tracking-tight text-picobit-text">
        Something went wrong
      </h1>
      <p class="m-0 mb-6 font-mono text-[13px] leading-relaxed text-picobit-text-2">
        {$globalError.message || 'An unexpected error occurred.'}
      </p>
      {#if import.meta.env.DEV && $globalError.stack}
        <pre
          class="mb-6 overflow-auto rounded-lg bg-picobit-surface-2 p-3.5 font-mono text-[11px] leading-relaxed text-picobit-text-3 whitespace-pre-wrap"
          aria-label="Stack trace">{$globalError.stack}</pre>
      {/if}
      <button
        class="inline-flex h-9 cursor-pointer items-center rounded-lg border border-picobit-text bg-picobit-text px-4 text-[13px] font-medium text-white hover:bg-[#2d2d2f] dark:text-black dark:hover:bg-[#f2f2f2]"
        type="button"
        onclick={() => window.location.reload()}
      >
        Reload page
      </button>
    </div>
  </div>
{:else}
  {#if $notice.visible}
    <div
      class={`fixed top-16 right-5 z-1100 max-w-sm rounded-[10px] border px-3.5 py-2.5 text-xs leading-relaxed shadow-xl ${
        $notice.tone === 'success'
          ? 'border-picobit-success-border bg-picobit-success-bg text-picobit-success'
          : $notice.tone === 'error'
            ? 'border-picobit-danger-border bg-picobit-danger-bg text-picobit-danger'
            : 'border-picobit-border-strong bg-picobit-surface text-picobit-text-3'
      }`}
      role="status"
      aria-live="polite"
    >
      {$notice.message}
    </div>
  {/if}

  <div>
    <nav
      class="fixed inset-x-0 top-0 z-50 flex h-12 items-center gap-3 border-b border-black/10 bg-white/80 px-6 backdrop-blur-xl dark:border-white/10 dark:bg-black/80"
    >
      <div class="text-[13px] font-semibold tracking-[-0.01em] text-picobit-text">Pico Bit</div>
      <div class="flex-1"></div>
      <ThemeToggle />
    </nav>

    <svelte:boundary onerror={handleBoundaryError}>
      <main class="mx-auto grid max-w-360 gap-4 px-4 pt-6 pb-16 sm:px-6">
        {#await bootstrapPromise}
          <AppSkeleton />
        {:then}
          <TopSection />
          <div
            class="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_17rem] xl:grid-cols-[15rem_minmax(0,1fr)_17rem]"
          >
            <LeftSection />
            <MiddleSection />
            <RightSection />
          </div>
        {:catch error}
          <div
            class="rounded-xl border border-picobit-danger-border bg-picobit-danger-bg px-4 py-4"
            role="alert"
          >
            <p class="m-0 text-sm text-picobit-danger">
              {error?.message ?? 'Dashboard failed to load. Refresh to retry.'}
            </p>
          </div>
        {/await}
      </main>
      <ValidationModal />

      {#snippet failed(error, reset)}
        <main class="mx-auto max-w-360 px-4 pt-6 pb-16 sm:px-6">
          <div
            class="rounded-xl border border-picobit-danger-border bg-picobit-danger-bg px-4 py-6"
            role="alert"
          >
            <p class="m-0 mb-3 text-sm text-picobit-danger">
              {(error as Error)?.message ?? 'An unexpected error occurred.'}
            </p>
            <button
              class="inline-flex h-8 cursor-pointer items-center rounded-lg border border-picobit-danger-border px-3 text-[13px] text-picobit-danger hover:bg-picobit-danger-bg"
              type="button"
              onclick={reset}
            >
              Retry
            </button>
          </div>
        </main>
      {/snippet}
    </svelte:boundary>
  </div>
{/if}
