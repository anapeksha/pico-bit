<script lang="ts">
  import Circle from '@lucide/svelte/icons/circle';
  import CircleCheck from '@lucide/svelte/icons/circle-check';
  import CircleX from '@lucide/svelte/icons/circle-x';
  import Loader from '@lucide/svelte/icons/loader-circle';

  import { executionMap, type ExecutionState } from '../stores/execution';

  const steps = ['Detect', 'Copy', 'Execute', 'Collect', 'Cleanup'];

  function iconClass(state: ExecutionState): string {
    if (state === 'success') return 'h-5 w-5 text-picobit-success';
    if (state === 'error') return 'h-5 w-5 text-picobit-danger';
    if (state === 'loading') return 'h-5 w-5 animate-spin text-picobit-text';
    return 'h-5 w-5 text-picobit-text-3';
  }

  function stateLabel(state: ExecutionState): string {
    if (state === 'loading') return 'running';
    if (state === 'success') return 'done';
    if (state === 'error') return 'failed';
    return 'planned';
  }
</script>

{#snippet StepIcon(state: ExecutionState)}
  {#if state === 'loading'}
    <Loader class={iconClass(state)} aria-hidden="true" />
  {:else if state === 'success'}
    <CircleCheck class={iconClass(state)} aria-hidden="true" />
  {:else if state === 'error'}
    <CircleX class={iconClass(state)} aria-hidden="true" />
  {:else}
    <Circle class={iconClass(state)} aria-hidden="true" />
  {/if}
{/snippet}

<ol class="flex w-full" aria-label="Binary injection execution timeline">
  {#each steps as step, index}
    {@const state = ($executionMap.get(step) ?? 'idle') as ExecutionState}
    {@const isLast = index === steps.length - 1}

    <li
      class="relative w-full"
      aria-label={`${index + 1}. ${step}, ${stateLabel(state)}`}
    >
      <div class="flex items-center">
        <div
          class="z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-picobit-surface"
        >
          {@render StepIcon(state)}
        </div>

        {#if !isLast}
          <div class="h-px w-full bg-picobit-border-strong sm:block"></div>
        {/if}
      </div>

      <div class="mt-2 sm:pe-8">
        <p class="m-0 truncate text-[11px] font-medium text-picobit-text-3">
          {step}
        </p>
        <p class="m-0 mt-0.5 text-[10px] capitalize text-picobit-text-4">
          {stateLabel(state)}
        </p>
      </div>
    </li>
  {/each}
</ol>
