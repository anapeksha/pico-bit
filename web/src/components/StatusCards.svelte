<script lang="ts">
  import Eye from '@lucide/svelte/icons/eye';
  import EyeClosed from '@lucide/svelte/icons/eye-closed';
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
  const valueClass =
    'break-all text-[13px] font-medium leading-snug text-picobit-text';
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
            <Eye size={16} />
          {:else}
            <EyeClosed size={16} />
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
