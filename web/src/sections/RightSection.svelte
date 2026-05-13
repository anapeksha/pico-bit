<script lang="ts">
  import { changeKeyboardTarget, keyboard } from '../stores/keyboard';
  import { runHistory } from '../stores/run';

  const panelClass =
    'rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-4';
  const titleClass =
    'm-0 mb-2.5 text-[13px] font-semibold tracking-[-0.005em] text-[var(--text)]';
  const labelClass = 'text-[11px] font-medium text-[var(--text-3)]';
  const selectClass =
    'w-full appearance-none rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 text-[13px] leading-none text-[var(--text)] outline-none focus:border-[var(--text)]';
  const rowClass =
    'flex items-center justify-between gap-2 border-t border-[var(--border)] py-2';
</script>

<div class="lg:order-2 xl:order-0">
  <aside class="flex flex-col gap-3.5 xl:w-[17rem]">
    <div class={panelClass}>
      <p class={titleClass}>Layout</p>
      <p class="m-0 mb-3 text-xs leading-relaxed text-[var(--text-3)]">
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
            {#each $keyboard.oses as os}
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
            {#each $keyboard.layouts as layout}
              <option value={layout.code}>{layout.label}</option>
            {/each}
          </select>
        </div>
      </div>
      <p class="m-0 mt-3 text-[11px] leading-relaxed text-[var(--text-4)]">
        {$keyboard.hint}
      </p>
    </div>

    <div class={panelClass}>
      <p class={titleClass}>Recent runs</p>
      <div class="flex max-h-56 flex-col gap-1 overflow-y-auto" aria-live="polite">
        {#if $runHistory.length}
          {#each $runHistory as item}
            <div
              class="flex min-w-0 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1.5"
            >
              <span class="shrink-0 font-mono text-[11px] font-semibold text-[var(--text-4)]">
                #{item.sequence}
              </span>
              <span class="min-w-0 flex-1 truncate text-xs text-[var(--text-2)]">
                {item.source ? `${item.source} · ` : ''}{item.preview || item.message}
              </span>
              <span
                class={`shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold tracking-[0.04em] uppercase ${
                  item.notice === 'success'
                    ? 'border-[var(--success-border)] bg-[var(--success-bg)] text-[var(--success)]'
                    : 'border-[var(--danger-border)] bg-[var(--danger-bg)] text-[var(--danger)]'
                }`}
              >
                {item.notice === 'success' ? 'OK' : 'ERR'}
              </span>
            </div>
          {/each}
        {:else}
          <p class="m-0 text-xs leading-relaxed text-[var(--text-3)]">
            No payloads have run yet.
          </p>
        {/if}
      </div>
    </div>
  </aside>
</div>
