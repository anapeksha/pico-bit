<script lang="ts">
  import ChevronDown from '@lucide/svelte/icons/chevron-down';
  import ChevronUp from '@lucide/svelte/icons/chevron-up';
  import CloudUpload from '@lucide/svelte/icons/cloud-upload';
  import Download from '@lucide/svelte/icons/download';
  import FileTerminal from '@lucide/svelte/icons/file-terminal';
  import Import from '@lucide/svelte/icons/import';

  import { fileDrop } from '../attachments/fileDrop';
  import { formatBytes, validateArmoryFile } from '../lib/binary';
  import {
    armoryNotice,
    binaryTargetOs,
    hasBinary,
    injectBinary,
    injectingBinary,
    stagedBinaryName,
    uploadBinary,
    uploadingBinary,
    uploadProgress,
  } from '../stores/binary';
  import { importingLoot, importUsbLoot, loot } from '../stores/loot';
  import { activeAccordion } from '../stores/ui';
  import ExecutionTimeline from './ExecutionTimeline.svelte';
  import LootViewer from './LootViewer.svelte';

  const TRACKING_KEYS = new Set([
    'execution_failure_reason',
    'execution_state',
    'execution_step',
    'source',
    'target_os',
    'timestamp',
  ]);

  function hasAgentData(record: Record<string, unknown> | null): boolean {
    if (!record) return false;
    return Object.keys(record).some((k) => !TRACKING_KEYS.has(k));
  }

  let selectedFile = $state<File | null>(null);
  let fileInput = $state<HTMLInputElement | null>(null);
  let fileError = $state('');
  let importPromise = $state<Promise<void>>(Promise.resolve());

  const buttonClass =
    'inline-flex h-9 cursor-pointer items-center justify-center whitespace-nowrap rounded-lg border px-4 text-[13px] font-medium leading-none disabled:cursor-not-allowed disabled:opacity-40';
  const lootButtonClass =
    'inline-flex h-9 cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap rounded-lg border px-3 text-[13px] font-medium leading-none disabled:cursor-not-allowed disabled:opacity-40';
  const ghostButton = `${buttonClass} border-picobit-border-strong bg-picobit-surface text-picobit-text hover:bg-picobit-surface-2`;
  const lootGhostButton = `${lootButtonClass} border-picobit-border-strong bg-picobit-surface text-picobit-text hover:bg-picobit-surface-2`;
  const primaryButton = `${buttonClass} border-picobit-text bg-picobit-text text-white hover:bg-[#2d2d2f] dark:text-black dark:hover:bg-[#f2f2f2]`;

  async function selectFile(file: File) {
    const error = await validateArmoryFile(file);
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
    const error = await validateArmoryFile(selectedFile);
    if (error) {
      fileError = error;
      return;
    }
    fileError = '';
    await uploadBinary(selectedFile);
  }
</script>

<section
  class:flex-1={$activeAccordion === 'armory'}
  class="flex min-h-0 shrink-0 flex-col"
>
  <button
    class="flex w-full cursor-pointer items-center gap-2 border-0 border-b border-picobit-border bg-picobit-surface-2 px-3.5 py-2.5 text-left text-xs font-medium text-picobit-text hover:bg-picobit-surface-3"
    type="button"
    aria-expanded={$activeAccordion === 'armory'}
    onclick={() => activeAccordion.set('armory')}
  >
    <span class="flex-1 font-mono text-xs text-picobit-text-3"
      >Binary Armory</span
    >
    {#if $stagedBinaryName}
      <span
        class="inline-flex items-center rounded-md border border-picobit-text bg-picobit-text px-2 py-0.5 text-[11px] font-medium text-white dark:text-black"
      >
        {$stagedBinaryName}
      </span>
    {/if}
    {#if $activeAccordion === 'armory'}
      <ChevronUp size={16} className="text-picobit-text-4" />
    {:else}
      <ChevronDown size={16} className="text-picobit-text-4" />
    {/if}
  </button>

  {#if $activeAccordion === 'armory'}
    <div class="grid gap-3 overflow-y-auto px-3.5 py-4">
      <div
        class="relative flex min-h-28 cursor-pointer flex-col items-center justify-center rounded-[10px] border border-dashed border-picobit-border-strong bg-picobit-surface-2 px-4 py-6 transition hover:bg-picobit-surface-3"
        role="button"
        tabindex="0"
        aria-label="Upload binary file"
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
            <FileTerminal />
            <span class="font-mono text-xs font-medium text-picobit-text"
              >{selectedFile.name}</span
            >
            <span class="text-[11px] text-picobit-text-3"
              >{formatBytes(selectedFile.size)}</span
            >
          </div>
        {:else}
          <div class="pointer-events-none flex flex-col items-center gap-1.5">
            <CloudUpload size={32} />
            <p class="m-0 text-xs font-medium text-picobit-text-2">
              Drag &amp; drop or click to upload
            </p>
            <p class="m-0 text-[11px] text-picobit-text-4">
              EXE, ELF, or Mach-O binaries only. Unix binaries may be
              extensionless.
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
          class={`rounded-lg border px-3.5 py-2.5 text-xs ${
            fileError
              ? 'border-picobit-danger-border bg-picobit-danger-bg text-picobit-danger'
              : $armoryNotice.tone === 'success'
                ? 'border-picobit-success-border bg-picobit-success-bg text-picobit-success'
                : $armoryNotice.tone === 'error'
                  ? 'border-picobit-danger-border bg-picobit-danger-bg text-picobit-danger'
                  : 'border-picobit-border-strong bg-picobit-surface text-picobit-text-3'
          }`}
          role="status"
          aria-live="polite"
        >
          {fileError || $armoryNotice.message}
        </div>
      {/if}

      <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div class="min-w-0 flex-1">
          <ExecutionTimeline />
        </div>
        <div class="flex shrink-0 gap-2">
          <button
            class={ghostButton}
            type="button"
            disabled={!selectedFile || $uploadingBinary}
            onclick={uploadSelected}
          >
            Upload
          </button>
          <button
            class={primaryButton}
            type="button"
            disabled={!$hasBinary || $injectingBinary}
            onclick={() => injectBinary()}
          >
            Inject
          </button>
        </div>
      </div>

      {#await importPromise}
        <div class="h-24 animate-pulse rounded-lg bg-picobit-border"></div>
      {:then}
        <div class="relative">
          {#if $effect.pending()}
            <div
              class="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-picobit-surface/70 backdrop-blur-[2px]"
            >
              <span class="text-xs text-picobit-text-3">Importing…</span>
            </div>
          {/if}
          {#if hasAgentData($loot)}
            <LootViewer />
          {:else}
            <div
              class="rounded-lg border border-picobit-border bg-picobit-surface-2 px-3.5 py-3"
            >
              <p class="m-0 mb-1.5 text-[11px] text-picobit-text-3">
                USB stager:
              </p>
              <pre
                class="m-0 whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed text-picobit-text-2">Backend-generated at injection time for {$binaryTargetOs}. It opens the host shell, writes a temporary runner script, executes payload.{$binaryTargetOs ===
                'windows'
                  ? 'exe'
                  : 'bin'}, stores loot-usb.json on the Pico drive, then cleans up.</pre>
            </div>
          {/if}
        </div>
      {/await}

      <div class="flex justify-end gap-1.5">
        <button
          class={lootGhostButton}
          type="button"
          disabled={$importingLoot}
          onclick={() => {
            importPromise = importUsbLoot();
          }}
          title="Import loot from USB drive"
        >
          <Import size={14} />
          <span>Import USB</span>
        </button>
        {#if hasAgentData($loot)}
          <a
            class={lootGhostButton}
            href="/api/loot/download"
            download="loot.json"
            title="Download loot.json"
          >
            <Download size={14} />
          </a>
        {:else}
          <button
            class={lootGhostButton}
            type="button"
            disabled
            title="No loot to download"
          >
            <Download size={14} />
          </button>
        {/if}
      </div>
    </div>
  {/if}
</section>
