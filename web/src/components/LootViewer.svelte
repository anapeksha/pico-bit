<script lang="ts">
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

</script>

{#if $loot}
  {@const data = agentData($loot)}
  {#if Object.keys(data).length}
    <div
      class="loot-viewer max-h-80 overflow-auto rounded-lg border border-picobit-border bg-picobit-surface-2 p-3"
    >
      <pre
        class="m-0 font-mono text-[11px] leading-relaxed text-picobit-text-2 whitespace-pre"
        aria-label="Loot JSON output">{@html colorize(data)}</pre>
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
