<script lang="ts">
  import ChevronDown from '@lucide/svelte/icons/chevron-down';
  import ChevronUp from '@lucide/svelte/icons/chevron-up';
  import Info from '@lucide/svelte/icons/info';
  import { onMount } from 'svelte';

  import {
    DEFAULT_EDITOR_METRICS,
    editorMarkers,
    gutterLines,
    highlightPayload,
    type EditorMetrics,
  } from '../lib/editor';
  import {
    canRun,
    canSave,
    payload,
    payloadState,
    runPayload,
    savePayload,
    validatePayloadDraft,
    validating,
    validation,
  } from '../stores/editor';
  import { activeAccordion, showNotice, validationModalOpen } from '../stores/ui';

  let textarea = $state<HTMLTextAreaElement | null>(null);
  let metrics = $state<EditorMetrics>(DEFAULT_EDITOR_METRICS);
  let scrollLeft = $state(0);
  let scrollTop = $state(0);
  let validationTimer = 0;

  const badgeClass = (tone?: string) =>
    `inline-flex items-center whitespace-nowrap rounded-md border px-2 py-0.5 text-[11px] font-medium ${
      tone === 'success'
        ? 'border-(--success-border) bg-(--success-bg) text-(--success)'
        : tone === 'error'
          ? 'border-(--danger-border) bg-(--danger-bg) text-(--danger)'
          : tone === 'warning' || tone === 'warn'
            ? 'border-(--warning-border) bg-(--warning-bg) text-(--warning)'
            : 'border-(--border) bg-(--surface) text-(--text-3)'
    }`;

  const buttonClass =
    'inline-flex h-9 cursor-pointer items-center justify-center whitespace-nowrap rounded-lg border px-4 text-[13px] font-medium leading-none disabled:cursor-not-allowed disabled:opacity-40';
  const ghostButton = `${buttonClass} border-picobit-border-strong bg-picobit-surface text-picobit-text hover:bg-picobit-surface-2`;
  const primaryButton = `${buttonClass} border-picobit-text bg-picobit-text text-white hover:bg-[#2d2d2f] dark:text-black dark:hover:bg-[#f2f2f2]`;

  function measure() {
    if (!textarea) return;
    const style = window.getComputedStyle(textarea);
    const sample = document.createElement('span');
    sample.textContent = 'MMMMMMMMMM';
    sample.style.font = style.font;
    sample.style.position = 'absolute';
    sample.style.visibility = 'hidden';
    document.body.appendChild(sample);
    metrics = {
      charWidth: sample.getBoundingClientRect().width / 10 || DEFAULT_EDITOR_METRICS.charWidth,
      lineHeight: Number.parseFloat(style.lineHeight) || DEFAULT_EDITOR_METRICS.lineHeight,
      padLeft: Number.parseFloat(style.paddingLeft) || DEFAULT_EDITOR_METRICS.padLeft,
      padTop: Number.parseFloat(style.paddingTop) || DEFAULT_EDITOR_METRICS.padTop,
    };
    sample.remove();
  }

  function syncScroll() {
    if (!textarea) return;
    scrollLeft = textarea.scrollLeft;
    scrollTop = textarea.scrollTop;
  }

  function queueValidation() {
    window.clearTimeout(validationTimer);
    validationTimer = window.setTimeout(() => {
      validatePayloadDraft().catch((error) => showNotice(error.message, 'error'));
    }, 260);
  }

  function handleInput() {
    payloadState.set('Unsaved draft');
    queueValidation();
  }

  onMount(() => {
    measure();
    window.addEventListener('resize', measure);
    return () => {
      window.clearTimeout(validationTimer);
      window.removeEventListener('resize', measure);
    };
  });
</script>

<section class:flex-1={$activeAccordion === 'ducky'} class="flex min-h-0 shrink-0 flex-col">
  <button
    class="flex w-full cursor-pointer items-center gap-2 border-0 border-b border-(--border) bg-(--surface-2) px-3.5 py-2.5 text-left text-xs font-medium text-(--text) hover:bg-(--surface-3)"
    type="button"
    aria-expanded={$activeAccordion === 'ducky'}
    onclick={() => activeAccordion.set('ducky')}
  >
    <span class="flex-1 font-mono text-xs text-(--text-3)">Ducky Editor</span>
    <span class={badgeClass($validation?.badge_tone)}
      >{$validation?.badge_label || $payloadState}</span
    >
    {#if $activeAccordion === 'ducky'}
      <ChevronUp size={16} className="text-picobit-text-4" />
    {:else}
      <ChevronDown size={16} className="text-picobit-text-4" />
    {/if}
  </button>

  {#if $activeAccordion === 'ducky'}
    <div class="flex min-h-0 flex-1 flex-col">
      <div
        class="flex items-center gap-2.5 border-b border-(--border) bg-(--surface-3) px-3.5 py-2.5"
      >
        <div class="flex-1 font-mono text-xs text-(--text-3)">payload.dd</div>
      </div>

      <div class="grid min-h-[28rem] grid-cols-[3rem_minmax(0,1fr)]">
        <div
          class="relative overflow-hidden border-r border-(--border) bg-(--surface-2) select-none"
        >
          <div
            class="relative py-[0.85rem] font-mono text-[13px] leading-[1.7]"
            style={`transform: translateY(${-scrollTop}px);`}
          >
            {#each gutterLines($payload, $validation) as item (item.line)}
              <div
                class={`flex h-[22.1px] items-center justify-end gap-1.5 px-2 text-[11px] ${
                  item.severity === 'error'
                    ? 'font-semibold text-(--danger)'
                    : item.severity === 'warning'
                      ? 'font-semibold text-(--warning)'
                      : 'text-(--text-4)'
                }`}
                title={item.title || ''}
              >
                {#if item.severity}
                  <span class="size-1.5 shrink-0 rounded-full bg-current"></span>
                {/if}
                {item.line}
              </div>
            {/each}
          </div>
        </div>

        <div class="relative overflow-hidden bg-(--surface)">
          <div class="pointer-events-none absolute inset-0">
            {#each editorMarkers($validation, metrics, scrollLeft, scrollTop) as marker (`${marker.line}-${marker.severity}`)}
              <div
                class={`absolute h-0.5 rounded-full opacity-90 ${
                  marker.severity === 'error' ? 'bg-(--danger)' : 'bg-(--warning)'
                }`}
                style={marker.style}
                title={marker.title}
              ></div>
            {/each}
          </div>
          <div
            class="editor-highlight pointer-events-none absolute inset-0 whitespace-pre p-[0.85rem_1rem] font-mono text-[13px] leading-[1.7] text-(--text)"
            aria-hidden="true"
            style={`transform: translate(${-scrollLeft}px, ${-scrollTop}px);`}
          >
            <!-- eslint-disable-next-line svelte/no-at-html-tags -->
            {@html highlightPayload($payload)}
          </div>
          <label for="payload" class="sr-only">Payload script</label>
          <textarea
            bind:this={textarea}
            bind:value={$payload}
            id="payload"
            class="relative z-10 block h-full min-h-[28rem] w-full resize-none overflow-auto whitespace-pre border-0 bg-transparent p-[0.85rem_1rem] font-mono text-[13px] leading-[1.7] text-transparent caret-(--text) outline-none [tab-size:4]"
            spellcheck="false"
            autocapitalize="off"
            autocomplete="off"
            placeholder="REM Write your payload here"
            wrap="off"
            aria-describedby="editor-status"
            oninput={handleInput}
            onscroll={syncScroll}
          ></textarea>
        </div>
      </div>

      <div
        class="flex flex-col items-stretch justify-between gap-4 border-t border-(--border) bg-(--surface-3) px-4 py-3 sm:flex-row sm:flex-wrap sm:items-center"
      >
        <div class="flex min-w-0 flex-1 items-center gap-2.5" id="editor-status">
          <span class={badgeClass($validating ? 'quiet' : $validation?.badge_tone)}>
            {$validating ? 'Checking...' : $validation?.badge_label || 'Ready'}
          </span>
          <span class="min-w-0 flex-1 truncate text-xs text-(--text-3)">
            {$validation?.summary || 'Dry run runs before save and execution.'}
          </span>
          {#if $validation?.diagnostics?.length}
            <button
              class="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-md border border-(--danger-border) bg-(--danger-bg) px-2 py-1 text-[11px] font-medium text-(--danger) hover:border-(--danger)"
              type="button"
              aria-label="Show validation errors"
              onclick={() => validationModalOpen.set(true)}
            >
              <Info size={16} />
              <span>{$validation.diagnostics.length}</span>
            </button>
          {/if}
        </div>
        <div class="flex w-full items-center gap-1.5 sm:w-auto">
          <button
            class={`${ghostButton} flex-1 sm:flex-none`}
            type="button"
            onclick={() => location.reload()}
          >
            Reload
          </button>
          <button
            class={`${ghostButton} flex-1 sm:flex-none`}
            type="button"
            disabled={!$canSave}
            onclick={() => savePayload()}
          >
            Save
          </button>
          <button
            class={`${primaryButton} flex-1 sm:flex-none`}
            type="button"
            disabled={!$canRun}
            onclick={() => runPayload()}
          >
            Save &amp; run
          </button>
        </div>
      </div>
    </div>
  {/if}
</section>
