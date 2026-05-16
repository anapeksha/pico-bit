<script lang="ts">
  import Eye from '@lucide/svelte/icons/eye';
  import EyeClosed from '@lucide/svelte/icons/eye-closed';
  import { apPassword, apSsid } from '../stores/ap';
  import { hidState } from '../stores/keyboard';
  import { hostUsb, usbStateLabel } from '../stores/usb';

  let revealPassword = $state(false);

  const statClass =
    'min-w-0 basis-full rounded-[10px] border border-picobit-border bg-picobit-surface px-3.5 py-3 sm:basis-[calc(50%-0.25rem)] xl:basis-[calc(25%-0.375rem)]';
  const labelClass = 'mb-1 text-[11px] font-medium text-picobit-text-3';
  const valueClass = 'break-all text-[13px] font-medium leading-snug text-picobit-text';
</script>

<div class="flex flex-wrap justify-around gap-2">
  <dl class={`${statClass} m-0`}>
    <dt class={labelClass}>Access point</dt>
    <dd class={`${valueClass} m-0`}>{$apSsid}</dd>
  </dl>

  <dl class={`${statClass} m-0`}>
    <dt class={labelClass}>AP password</dt>
    <dd class="m-0 flex min-w-0 items-center gap-1.5">
      <span class={`${valueClass} min-w-0 flex-1 truncate font-mono text-xs`}>
        {$apPassword === 'Open network' || revealPassword
          ? $apPassword
          : '•'.repeat($apPassword.length)}
      </span>
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
    </dd>
  </dl>

  <dl class={`${statClass} m-0`}>
    <dt class={labelClass}>Host HID</dt>
    <dd class={`${valueClass} m-0`} aria-live="polite">{$hidState}</dd>
  </dl>

  <dl
    class={`${statClass} m-0 ${
      $hostUsb.state === 'active' || $hostUsb.mounted
        ? 'border-picobit-success-border bg-picobit-success-bg'
        : $hostUsb.state === 'error' || !$hostUsb.available
          ? 'border-picobit-danger-border bg-picobit-danger-bg'
          : ''
    }`}
  >
    <dt class={labelClass}>Host USB</dt>
    <dd
      class={`${valueClass} m-0 ${
        $hostUsb.state === 'active' || $hostUsb.mounted
          ? 'text-picobit-success'
          : $hostUsb.state === 'error' || !$hostUsb.available
            ? 'text-picobit-danger'
            : ''
      }`}
      aria-live="polite"
    >
      {$usbStateLabel}
    </dd>
  </dl>
</div>
