<script lang="ts">
  import {
    apPassword,
    apSsid,
    authLabel,
    hidState,
    hostUsb,
    usbStateLabel,
  } from '../stores/portal';

  let revealPassword = $state(false);

  const statClass =
    'min-w-0 basis-full rounded-[10px] border border-picobit-border bg-picobit-surface px-3.5 py-3 md:basis-[calc(50%-0.25rem)] lg:basis-[calc(33.333%-0.333rem)] xl:basis-[calc(20%-0.4rem)]';
  const labelClass = 'mb-1 text-[11px] font-medium text-picobit-text-3';
  const valueClass = 'break-all text-[13px] font-medium leading-snug text-picobit-text';
</script>

<div class="flex flex-wrap justify-around gap-2">
  <div class={statClass}>
    <div class={labelClass}>Access point</div>
    <div class={valueClass}>{$apSsid}</div>
  </div>

  <div class={statClass}>
    <div class={labelClass}>AP password</div>
    <div class="flex min-w-0 items-center gap-1.5">
      <div class={`${valueClass} min-w-0 flex-1 truncate font-mono text-xs`}>
        {$apPassword === 'Open network' || revealPassword
          ? $apPassword
          : '•'.repeat($apPassword.length)}
      </div>
      {#if $apPassword !== 'Open network'}
        <button
          class="flex shrink-0 items-center border-0 bg-transparent p-0 text-picobit-text-3 hover:text-picobit-text"
          type="button"
          aria-label={revealPassword ? 'Hide AP password' : 'Show AP password'}
          aria-pressed={revealPassword}
          onclick={() => (revealPassword = !revealPassword)}
        >
          {#if revealPassword}
            <svg class="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path
                d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"
                stroke-width="2"
              />
              <line x1="1" y1="1" x2="23" y2="23" stroke-width="2" />
            </svg>
          {:else}
            <svg class="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke-width="2" />
              <circle cx="12" cy="12" r="3" stroke-width="2" />
            </svg>
          {/if}
        </button>
      {/if}
    </div>
  </div>

  <div class={statClass}>
    <div class={labelClass}>Portal auth</div>
    <div class={valueClass}>{$authLabel}</div>
  </div>

  <div class={statClass}>
    <div class={labelClass}>Host HID</div>
    <div class={valueClass} aria-live="polite">{$hidState}</div>
  </div>

  <div
    class={`${statClass} ${
      $hostUsb.state === 'active' || $hostUsb.mounted
        ? 'border-picobit-success-border bg-picobit-success-bg'
        : $hostUsb.state === 'error' || !$hostUsb.available
          ? 'border-picobit-danger-border bg-picobit-danger-bg'
          : ''
    }`}
  >
    <div class={labelClass}>Host USB</div>
    <div
      class={`${valueClass} ${
        $hostUsb.state === 'active' || $hostUsb.mounted
          ? 'text-picobit-success'
          : $hostUsb.state === 'error' || !$hostUsb.available
            ? 'text-picobit-danger'
            : ''
      }`}
      aria-live="polite"
    >
      {$usbStateLabel}
    </div>
  </div>
</div>
