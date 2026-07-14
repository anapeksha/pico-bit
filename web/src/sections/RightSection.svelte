<script lang="ts">
  import type { ActivityCode } from '../stores/activity';
  import { activity } from '../stores/activity';
  import { changeKeyboardTarget, keyboard } from '../stores/keyboard';
  import { runHistory } from '../stores/run';

  const panelClass = 'rounded-xl border border-(--border) bg-(--surface) px-4 py-4';
  const titleClass = 'm-0 mb-2.5 text-[13px] font-semibold tracking-[-0.005em] text-(--text)';
  const labelClass = 'text-[11px] font-medium text-(--text-3)';
  const selectClass =
    'w-full appearance-none rounded-lg border border-(--border-strong) bg-(--surface) px-3 py-2 text-[13px] leading-none text-(--text) outline-none focus:border-(--text)';

  const activityLabels: Record<ActivityCode, string> = {
    armory_delete_complete: 'Binary deleted',
    armory_delete_failed: 'Delete failed',
    armory_upload_complete: 'Binary uploaded',
    armory_upload_failed: 'Upload failed',
    keyboard_target_changed: 'Keyboard target changed',
    keyboard_target_failed: 'Keyboard change failed',
    payload_run_failed: 'Payload run failed',
    payload_run_requested: 'Payload run requested',
    payload_save_failed: 'Payload save failed',
    payload_saved: 'Payload saved',
  };
</script>

<div class="lg:order-2 xl:order-0">
  <aside class="flex flex-col gap-3.5 xl:w-68" aria-label="Layout and recent runs">
    <div class={panelClass}>
      <p class={titleClass}>Layout</p>
      <p class="m-0 mb-3 text-xs leading-relaxed text-(--text-3)">
        Tell how the host interprets typed text.
      </p>
      <div class="flex flex-col gap-2">
        <div class="grid gap-1">
          <label class={labelClass} for="keyboard-os">Operating system</label>
          <select
            id="keyboard-os"
            class={selectClass}
            value={$keyboard.os}
            onchange={(event) =>
              changeKeyboardTarget({
                os: (event.currentTarget as HTMLSelectElement).value,
              })}
          >
            {#each $keyboard.oses as os (os.code)}
              <option value={os.code}>{os.label}</option>
            {/each}
          </select>
        </div>
        <div class="grid gap-1">
          <label class={labelClass} for="keyboard-layout">Keyboard layout</label>
          <select
            id="keyboard-layout"
            class={selectClass}
            value={$keyboard.layout}
            onchange={(event) =>
              changeKeyboardTarget({
                layout: (event.currentTarget as HTMLSelectElement).value,
                os: $keyboard.os,
              })}
          >
            {#each $keyboard.layouts as layout (layout.code)}
              <option value={layout.code}>{layout.label}</option>
            {/each}
          </select>
        </div>
      </div>
      <p class="m-0 mt-3 text-[11px] leading-relaxed text-(--text-4)">
        {$keyboard.hint}
      </p>
    </div>

    <div class={panelClass}>
      <p class={titleClass}>Activity</p>
      <div class="flex max-h-48 flex-col gap-1 overflow-y-auto" aria-live="polite">
        {#if $activity.length}
          {#each $activity as item (item.sequence)}
            <div
              class="flex min-w-0 items-center gap-2 rounded-lg border border-(--border) bg-(--surface-2) px-2 py-1.5"
            >
              <span class="shrink-0 font-mono text-[11px] font-semibold text-(--text-4)">
                #{item.sequence}
              </span>
              <span class="min-w-0 flex-1 truncate text-xs text-(--text-2)">
                {activityLabels[item.code]}
              </span>
              <span
                class={`size-1.5 shrink-0 rounded-full ${item.ok ? 'bg-(--success)' : 'bg-(--danger)'}`}
                aria-label={item.ok ? 'Succeeded' : 'Failed'}
              ></span>
            </div>
          {/each}
        {:else}
          <p class="m-0 text-xs leading-relaxed text-(--text-3)">No actions this session.</p>
        {/if}
      </div>
    </div>

    <div class={panelClass}>
      <p class={titleClass}>Recent runs</p>
      <div class="flex max-h-56 flex-col gap-1 overflow-y-auto" aria-live="polite">
        {#if $runHistory.length}
          {#each $runHistory as item (item.sequence)}
            <div
              class="flex min-w-0 items-center gap-2 rounded-lg border border-(--border) bg-(--surface-2) px-2 py-1.5"
            >
              <span class="shrink-0 font-mono text-[11px] font-semibold text-(--text-4)">
                #{item.sequence}
              </span>
              <span class="min-w-0 flex-1 truncate text-xs text-(--text-2)">
                {item.source ? `${item.source} · ` : ''}{item.preview || 'payload.dd'}
              </span>
              <span
                class={`shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold tracking-[0.04em] uppercase ${
                  item.ok !== false
                    ? 'border-(--success-border) bg-(--success-bg) text-(--success)'
                    : 'border-(--danger-border) bg-(--danger-bg) text-(--danger)'
                }`}
              >
                {item.ok !== false ? 'OK' : 'ERR'}
              </span>
            </div>
          {/each}
        {:else}
          <p class="m-0 text-xs leading-relaxed text-(--text-3)">No payloads have run yet.</p>
        {/if}
      </div>
    </div>
  </aside>
</div>
