<script lang="ts">
  import X from '@lucide/svelte/icons/x';
  import { validation, validationModalOpen } from '../stores/portal';

  function close() {
    validationModalOpen.set(false);
  }
</script>

{#if $validationModalOpen}
  <div
    class="fixed inset-0 z-[1000] flex items-end justify-center p-0 sm:items-center sm:p-6"
    role="presentation"
    onkeydown={(event) => {
      if (event.key === 'Escape') close();
    }}
  >
    <button
      class="absolute inset-0 cursor-default border-0 bg-black/30 backdrop-blur-sm dark:bg-black/60"
      aria-label="Close validation modal"
      type="button"
      onclick={close}
    ></button>
    <div
      class="relative flex max-h-[70vh] w-full max-w-full flex-col overflow-hidden rounded-t-[14px] rounded-b-none border border-[var(--border)] bg-[var(--surface)] shadow-2xl sm:max-h-[80vh] sm:max-w-md sm:rounded-[14px] md:max-h-[32rem]"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      aria-describedby="modal-subtitle"
    >
      <div
        class="flex shrink-0 items-start justify-between gap-4 border-b border-[var(--border)] px-5 pt-4 pb-3"
      >
        <div class="grid min-w-0 gap-0.5">
          <h3
            class="m-0 text-sm font-semibold tracking-[-0.01em] text-[var(--text)]"
            id="modal-title"
          >
            Validation issues
          </h3>
          <p
            class="m-0 text-xs leading-snug text-[var(--text-3)]"
            id="modal-subtitle"
          >
            {$validation?.blocking
              ? 'Errors found in the payload'
              : 'Payload warnings'}
          </p>
        </div>
        <button
          class="inline-flex shrink-0 cursor-pointer items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-1.5 text-[var(--text-3)] hover:text-[var(--text)]"
          type="button"
          aria-label="Close"
          onclick={close}
        >
          <X size={16} />
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
              <p
                class="m-0 text-[13px] font-medium leading-snug text-[var(--text)]"
              >
                {item.message}
              </p>
              {#if item.hint}
                <p class="m-0 text-xs leading-relaxed text-[var(--text-3)]">
                  {item.hint}
                </p>
              {/if}
            </div>
          {/each}
        {:else}
          <p
            class="m-0 py-6 text-center text-xs leading-relaxed text-[var(--text-3)]"
          >
            No issues detected.
          </p>
        {/if}
      </div>
    </div>
  </div>
{/if}
