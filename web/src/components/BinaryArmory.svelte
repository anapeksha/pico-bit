<script lang="ts">
  import { fileDrop } from '../actions/fileDrop';
  import { formatBytes, stagerPreview, validateArmoryFile } from '../lib/binary';
  import type { TargetOs } from '../lib/types';
  import {
    activeAccordion,
    armoryNotice,
    binaryTargetOs,
    hasBinary,
    injectingBinary,
    injectBinary,
    stagedBinaryName,
    uploadBinary,
    uploadingBinary,
    uploadProgress,
  } from '../stores/portal';

  let selectedFile = $state<File | null>(null);
  let fileInput = $state<HTMLInputElement | null>(null);
  let fileError = $state('');

  const buttonClass =
    'inline-flex cursor-pointer items-center justify-center whitespace-nowrap rounded-lg border px-4 py-2 text-[13px] font-medium leading-tight disabled:cursor-not-allowed disabled:opacity-40';
  const ghostButton = `${buttonClass} border-picobit-border-strong bg-picobit-surface text-picobit-text hover:bg-picobit-surface-2`;
  const primaryButton = `${buttonClass} border-picobit-text bg-picobit-text text-white hover:bg-[#2d2d2f]`;

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

<section class:flex-1={$activeAccordion === 'armory'} class="flex min-h-0 shrink-0 flex-col">
  <button
    class="flex w-full cursor-pointer items-center gap-2 border-0 border-b border-picobit-border bg-picobit-surface-2 px-3.5 py-2.5 text-left text-xs font-medium text-picobit-text hover:bg-picobit-surface-3"
    type="button"
    aria-expanded={$activeAccordion === 'armory'}
    onclick={() => activeAccordion.set('armory')}
  >
    <span class="flex-1 font-mono text-xs text-picobit-text-3">Binary Armory</span>
    {#if $stagedBinaryName}
      <span class="inline-flex items-center rounded-md border border-picobit-text bg-picobit-text px-2 py-0.5 text-[11px] font-medium text-white">
        {$stagedBinaryName}
      </span>
    {/if}
    <svg
      class={`size-3.5 shrink-0 text-picobit-text-4 transition-transform ${
        $activeAccordion === 'armory' ? 'rotate-180' : ''
      }`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <polyline points="6 9 12 15 18 9"></polyline>
    </svg>
  </button>

  {#if $activeAccordion === 'armory'}
    <div class="grid gap-3 overflow-y-auto px-3.5 py-4">
      <div
        class="relative flex min-h-28 cursor-pointer flex-col items-center justify-center rounded-[10px] border border-dashed border-picobit-border-strong bg-picobit-surface-2 px-4 py-6 transition hover:bg-picobit-surface-3"
        role="button"
        tabindex="0"
        aria-label="Upload binary file"
        use:fileDrop={{ onFile: selectFile }}
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
            <svg
              class="size-6 shrink-0 text-picobit-text-3"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
              <polyline points="13 2 13 9 20 9"></polyline>
            </svg>
            <span class="font-mono text-xs font-medium text-picobit-text">
              {selectedFile.name}
            </span>
            <span class="text-[11px] text-picobit-text-3">{formatBytes(selectedFile.size)}</span>
          </div>
        {:else}
          <div class="pointer-events-none flex flex-col items-center gap-1.5">
            <svg
              class="size-7 text-picobit-text-3"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <polyline points="16 16 12 12 8 16"></polyline>
              <line x1="12" y1="12" x2="12" y2="21"></line>
              <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"></path>
            </svg>
            <p class="m-0 text-xs font-medium text-picobit-text-2">
              Drag &amp; drop or click to upload
            </p>
            <p class="m-0 text-[11px] text-picobit-text-4">
              EXE, ELF, or Mach-O binaries only. Unix binaries may be extensionless.
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

      <div class="flex flex-wrap items-end gap-3">
        <div class="grid min-w-32 flex-1 gap-1">
          <label class="text-[11px] font-medium text-picobit-text-3" for="inject-os">
            Target OS
          </label>
          <select
            id="inject-os"
            class="w-full appearance-none rounded-lg border border-picobit-border-strong bg-picobit-surface px-3 py-2 text-[13px] leading-none text-picobit-text outline-none focus:border-picobit-text"
            bind:value={$binaryTargetOs}
          >
            <option value="windows">Windows</option>
            <option value="linux">Linux</option>
            <option value="macos">macOS</option>
          </select>
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

      <div class="rounded-lg border border-picobit-border bg-picobit-surface-2 px-3.5 py-3">
        <p class="m-0 mb-1.5 text-[11px] text-picobit-text-3">
          USB command that will be typed:
        </p>
        <pre class="m-0 whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed text-picobit-text-2">{stagerPreview($binaryTargetOs as TargetOs)}</pre>
      </div>
    </div>
  {/if}
</section>
