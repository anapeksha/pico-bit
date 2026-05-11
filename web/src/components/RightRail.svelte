<script lang="ts">
  import { lootSections } from '../lib/loot';
  import {
    changeKeyboardTarget,
    importUsbLoot,
    importingLoot,
    keyboard,
    loot,
    runHistory,
  } from '../stores/portal';

  const panelClass = 'rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-4';
  const titleClass = 'm-0 mb-2.5 text-[13px] font-semibold tracking-[-0.005em] text-[var(--text)]';
  const labelClass = 'text-[11px] font-medium text-[var(--text-3)]';
  const selectClass =
    'w-full appearance-none rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 text-[13px] leading-none text-[var(--text)] outline-none focus:border-[var(--text)]';
  const rowClass = 'flex items-center justify-between gap-2 border-t border-[var(--border)] py-2';
</script>

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
            changeKeyboardTarget({ os: (event.currentTarget as HTMLSelectElement).value })}
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
    <p class={titleClass}>Loot</p>
    {#if $loot}
      {#each lootSections($loot) as section}
        <p class="m-0 mt-3 mb-1 text-[0.7rem] font-semibold tracking-[0.06em] text-[var(--text-4)] uppercase">
          {section.title}
        </p>
        <dl class="m-0 grid">
          {#each section.rows as row}
            <div class={rowClass}>
              <span class="text-xs text-[var(--text-3)]">{row.label}</span>
              {#if row.value}
                <span
                  class={`text-right text-xs font-medium text-[var(--text)] ${
                    row.mono ? 'break-all font-mono' : ''
                  }`}
                >
                  {row.value}
                </span>
              {/if}
            </div>
          {/each}
        </dl>
      {/each}
    {:else}
      <p class="m-0 text-xs leading-relaxed text-[var(--text-3)]">No loot collected yet.</p>
    {/if}

    <div class="mt-3 grid grid-cols-[minmax(0,1fr)_auto] gap-2">
      <button
        class="inline-flex cursor-pointer items-center justify-center rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-4 py-2 text-[13px] font-medium text-[var(--text)] hover:bg-[var(--surface-2)] disabled:cursor-not-allowed disabled:opacity-40"
        type="button"
        disabled={$importingLoot}
        onclick={() => importUsbLoot()}
      >
        Import USB loot
      </button>
      <button
        class="inline-flex size-[2.35rem] cursor-pointer items-center justify-center rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--text)] hover:bg-[var(--surface-2)] disabled:cursor-not-allowed disabled:opacity-40"
        type="button"
        aria-label="Download loot.json"
        title="Download loot.json"
        disabled={!$loot}
        onclick={() => {
          window.location.href = '/api/loot/download';
        }}
      >
        <svg
          class="size-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="7 10 12 15 17 10"></polyline>
          <line x1="12" y1="15" x2="12" y2="3"></line>
        </svg>
      </button>
    </div>
  </div>

  <div class={panelClass}>
    <p class={titleClass}>Recent runs</p>
    <div class="flex max-h-56 flex-col gap-1 overflow-y-auto" aria-live="polite">
      {#if $runHistory.length}
        {#each $runHistory as item}
          <div class="flex min-w-0 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1.5">
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
