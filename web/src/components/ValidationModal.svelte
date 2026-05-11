<script lang="ts">
  import { validation, validationModalOpen } from '../stores/portal';

  function close() {
    validationModalOpen.set(false);
  }
</script>

{#if $validationModalOpen}
  <div
    class="fixed inset-0 z-[1000] flex items-center justify-center p-6 max-sm:items-end max-sm:p-0"
    role="presentation"
    onkeydown={(event) => {
      if (event.key === 'Escape') close();
    }}
  >
    <button
      class="absolute inset-0 cursor-default border-0 bg-black/30 backdrop-blur-[2px]"
      aria-label="Close validation modal"
      type="button"
      onclick={close}
    ></button>
    <div
      class="relative flex max-h-[min(32rem,80vh)] w-full max-w-md flex-col overflow-hidden rounded-[14px] border border-[var(--border)] bg-[var(--surface)] shadow-2xl max-sm:max-h-[70vh] max-sm:max-w-full max-sm:rounded-b-none"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      aria-describedby="modal-subtitle"
    >
      <div class="flex shrink-0 items-start justify-between gap-4 border-b border-[var(--border)] px-5 pt-4 pb-3">
        <div class="grid min-w-0 gap-0.5">
          <h3 class="m-0 text-sm font-semibold tracking-[-0.01em] text-[var(--text)]" id="modal-title">
            Validation issues
          </h3>
          <p class="m-0 text-xs leading-snug text-[var(--text-3)]" id="modal-subtitle">
            {$validation?.blocking ? 'Errors found in the payload' : 'Payload warnings'}
          </p>
        </div>
        <button
          class="inline-flex shrink-0 cursor-pointer items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-1.5 text-[var(--text-3)] hover:text-[var(--text)]"
          type="button"
          aria-label="Close"
          onclick={close}
        >
          <svg
            viewBox="0 0 24 24"
            width="16"
            height="16"
            fill="none"
            stroke="currentcolor"
            stroke-width="2.2"
            stroke-linecap="round"
          >
            <line x1="6" y1="6" x2="18" y2="18"></line>
            <line x1="18" y1="6" x2="6" y2="18"></line>
          </svg>
        </button>
      </div>
      <div class="grid gap-2 overflow-y-auto px-5 py-4">
        {#if $validation?.diagnostics?.length}
          {#each $validation.diagnostics as item}
            <div
              class={`grid gap-1 rounded-lg border px-3.5 py-3 ${
                item.severity === 'error'
                  ? 'border-[var(--danger-border)] bg-[var(--danger-bg)]'
                  : 'border-[var(--warning-border)] bg-[var(--warning-bg)]'
              }`}
            >
              <p
                class={`m-0 font-mono text-[11px] font-medium tracking-[0.04em] uppercase ${
                  item.severity === 'error'
                    ? 'text-[var(--danger)]'
                    : 'text-[var(--warning)]'
                }`}
              >
                Line {item.line}, column {item.column}
              </p>
              <p class="m-0 text-[13px] font-medium leading-snug text-[var(--text)]">
                {item.message}
              </p>
              {#if item.hint}
                <p class="m-0 text-xs leading-relaxed text-[var(--text-3)]">{item.hint}</p>
              {/if}
            </div>
          {/each}
        {:else}
          <p class="m-0 py-6 text-center text-xs leading-relaxed text-[var(--text-3)]">
            No issues detected.
          </p>
        {/if}
      </div>
    </div>
  </div>
{/if}
