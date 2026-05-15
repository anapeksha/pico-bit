<script lang="ts">
  import Copy from '@lucide/svelte/icons/copy';

  import { agentData } from '../lib/loot';
  import { loot } from '../stores/loot';

  function esc(s: string): string {
    return s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function colorize(val: unknown, depth = 0): string {
    const pad = '  '.repeat(depth);
    const inner = '  '.repeat(depth + 1);

    if (val === null) return '<span class="j-null">null</span>';
    if (typeof val === 'boolean') return `<span class="j-bool">${val}</span>`;
    if (typeof val === 'number') return `<span class="j-num">${val}</span>`;
    if (typeof val === 'string') return `<span class="j-str">&quot;${esc(val)}&quot;</span>`;

    if (Array.isArray(val)) {
      if (!val.length) return '[]';
      const items = val.map((v) => `${inner}${colorize(v, depth + 1)}`).join(',\n');
      return `[\n${items}\n${pad}]`;
    }

    const entries = Object.entries(val as Record<string, unknown>);
    if (!entries.length) return '{}';
    const items = entries
      .map(
        ([k, v]) =>
          `${inner}<span class="j-key">&quot;${esc(k)}&quot;</span>: ${colorize(v, depth + 1)}`,
      )
      .join(',\n');
    return `{\n${items}\n${pad}}`;
  }

  let copied = $state(false);

  function copyJson() {
    if (!$loot) return;
    navigator.clipboard
      .writeText(JSON.stringify($loot, null, 2))
      .then(() => {
        copied = true;
        setTimeout(() => (copied = false), 1500);
      })
      .catch(() => {});
  }

  const buttonClass =
    'inline-flex h-9 cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap rounded-lg border px-3 text-[13px] font-medium leading-none disabled:cursor-not-allowed disabled:opacity-40';
  const ghostButton = `${buttonClass} border-picobit-border-strong bg-picobit-surface text-picobit-text hover:bg-picobit-surface-2`;
</script>

{#if $loot}
  {@const data = agentData($loot)}
  {#if Object.keys(data).length}
    <div class="flex min-h-0 flex-col gap-2">
      <div class="flex items-center justify-between gap-2">
        <p class="m-0 text-[11px] font-medium text-picobit-text-3">loot.json</p>
        <button
          class={ghostButton}
          type="button"
          onclick={copyJson}
          title="Copy JSON"
          aria-label="Copy loot JSON"
        >
          <Copy size={14} />
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>

      <div
        class="loot-viewer min-h-0 overflow-auto rounded-lg border border-picobit-border bg-picobit-surface-2 p-3"
      >
        <pre
          class="m-0 font-mono text-[11px] leading-relaxed text-picobit-text-2 whitespace-pre"
          aria-label="Loot JSON output">{@html colorize(data)}</pre>
      </div>
    </div>
  {/if}
{/if}

<style>
  .loot-viewer :global(.j-key) {
    color: var(--text);
  }
  .loot-viewer :global(.j-str) {
    color: var(--success);
  }
  .loot-viewer :global(.j-num) {
    color: #60a5fa;
  }
  .loot-viewer :global(.j-bool) {
    color: #a78bfa;
  }
  .loot-viewer :global(.j-null) {
    color: var(--text-4);
  }
</style>
