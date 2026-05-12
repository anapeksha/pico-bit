<script lang="ts">
  import LockOpen from '@lucide/svelte/icons/lock-open';
  import { onMount } from 'svelte';
  import BinaryArmory from './components/BinaryArmory.svelte';
  import DuckyEditor from './components/DuckyEditor.svelte';
  import LeftRail from './components/LeftRail.svelte';
  import RightRail from './components/RightRail.svelte';
  import StatusCards from './components/StatusCards.svelte';
  import ThemeToggle from './components/ThemeToggle.svelte';
  import ValidationModal from './components/ValidationModal.svelte';
  import { notice, showNotice, startPortal } from './stores/portal';
  import { initTheme } from './stores/theme';

  type Props = {
    authState?: 'login' | 'portal';
    message?: string;
    messageClass?: string;
    username?: string;
  };

  let {
    authState = 'portal',
    message = '',
    messageClass = 'notice--hidden',
    username = '',
  }: Props = $props();

  onMount(() => {
    const stopTheme = initTheme();
    if (authState !== 'portal') return stopTheme;
    let cleanup = () => {};
    startPortal()
      .then((stop) => {
        cleanup = stop;
      })
      .catch((error) =>
        showNotice(error.message || 'Portal bootstrap failed.', 'error'),
      );
    return () => {
      cleanup();
      stopTheme();
    };
  });
</script>

<svelte:body class:auth-login={authState === 'login'} />

{#if authState === 'login'}
  <section
    class="grid min-h-screen place-items-center bg-picobit-surface-3 p-6"
  >
    <div
      class="w-full max-w-sm rounded-[14px] border border-picobit-border bg-picobit-surface p-8"
    >
      <div class="mb-5">
        <h1
          class="m-0 mb-1.5 text-[22px] font-semibold tracking-[-0.025em] text-picobit-text"
        >
          Pico Bit
        </h1>
        <p class="m-0 text-xs leading-relaxed text-picobit-text-3">
          Sign in to unlock injector.
        </p>
      </div>

      <form action="/login" method="post" class="grid gap-3">
        {#if message}
          <div
            class={`rounded-[10px] border px-3.5 py-2.5 text-xs leading-relaxed ${
              messageClass.includes('error')
                ? 'border-picobit-danger-border bg-picobit-danger-bg text-picobit-danger'
                : 'border-picobit-border-strong bg-picobit-surface text-picobit-text-3'
            }`}
            role="alert"
          >
            {message}
          </div>
        {/if}

        <div class="grid gap-1">
          <label
            class="text-[11px] font-medium text-picobit-text-3"
            for="username"
          >
            Username
          </label>
          <input
            class="w-full rounded-lg border border-picobit-border-strong bg-picobit-surface px-3 py-2 text-[13px] leading-none text-picobit-text outline-none focus:border-picobit-text"
            id="username"
            name="username"
            autocomplete="username"
            value={username}
            required
          />
        </div>
        <div class="grid gap-1">
          <label
            class="text-[11px] font-medium text-picobit-text-3"
            for="password"
          >
            Password
          </label>
          <input
            class="w-full rounded-lg border border-picobit-border-strong bg-picobit-surface px-3 py-2 text-[13px] leading-none text-picobit-text outline-none focus:border-picobit-text"
            id="password"
            name="password"
            type="password"
            autocomplete="current-password"
            required
          />
        </div>
        <button
          class="inline-flex w-full gap-1 cursor-pointer items-center justify-center rounded-lg border border-picobit-text bg-picobit-text px-4 py-2 text-[13px] font-medium text-white hover:bg-[#2d2d2f] dark:text-black dark:hover:bg-[#f2f2f2]"
          type="submit"
        >
          <LockOpen size={16} />
          Unlock
        </button>
      </form>
    </div>
  </section>
{:else}
  {#if $notice.visible}
    <div
      class={`fixed top-16 right-5 z-[1100] max-w-sm rounded-[10px] border px-3.5 py-2.5 text-xs leading-relaxed shadow-xl ${
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
      <div
        class="text-[13px] font-semibold tracking-[-0.01em] text-picobit-text"
      >
        Pico Bit
      </div>
      <div class="flex-1"></div>
      <ThemeToggle />
    </nav>

    <main class="mx-auto grid max-w-[1440px] gap-4 px-4 pt-6 pb-16 sm:px-6">
      <StatusCards />

      <div
        class="grid items-start gap-4 xl:grid-cols-[15rem_minmax(0,1fr)_17rem] lg:grid-cols-[minmax(0,1fr)_17rem]"
      >
        <div
          class="lg:order-3 lg:col-span-full lg:grid lg:grid-cols-2 lg:gap-4 xl:order-none xl:col-span-1 xl:block"
        >
          <LeftRail />
        </div>
        <div
          class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-picobit-border bg-picobit-surface lg:order-1 xl:order-none"
        >
          <DuckyEditor />
          <BinaryArmory />
        </div>
        <div class="lg:order-2 xl:order-none">
          <RightRail />
        </div>
      </div>
    </main>

    <ValidationModal />
  </div>
{/if}
