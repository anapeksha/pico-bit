<script lang="ts">
  import { keyboard } from '../stores/keyboard';
  import { seededThisBoot } from '../stores/run';

  const panelClass = 'rounded-xl border border-(--border) bg-(--surface) px-4 py-4';
  const titleClass = 'm-0 mb-2.5 text-[13px] font-semibold tracking-[-0.005em] text-(--text)';
</script>

<div
  class="lg:order-3 lg:col-span-full lg:grid lg:grid-cols-2 lg:gap-4 xl:order-0 xl:col-span-1 xl:block"
>
  <aside class="flex flex-col gap-3.5 xl:w-60" aria-label="About and status">
    <div class={panelClass}>
      <p class={titleClass}>About</p>
      <p class="m-0 mb-2.5 text-xs leading-relaxed text-(--text-3)">
        Pico Bit manages the device payload file and staged Armory assets from the browser.
      </p>
      <ul class="m-0 list-disc pl-4 text-xs leading-7 text-(--text-3)">
        <li>
          <strong>DuckyScript</strong> - edit <span class="font-mono">payload.dd</span>, then save
          or run with firmware validation
        </li>
        <li>
          <strong>Binary Armory</strong> - upload, download, copy links, or delete files stored in littlefs2
        </li>
        <li>NCM link exposes staged files to the host while Host HID handles typed payload runs</li>
      </ul>
    </div>

    <div class={panelClass}>
      <p class={titleClass}>Status</p>
      <dl class="m-0 grid">
        <div class="flex items-center justify-between gap-2 border-b border-(--border) pb-2">
          <dt class="text-xs text-(--text-3)">Seeded this boot</dt>
          <dd class="m-0 text-right text-xs font-medium text-(--text)">
            {$seededThisBoot ? 'Yes' : 'No'}
          </dd>
        </div>
        <div class="flex items-center justify-between gap-2 py-2">
          <dt class="text-xs text-(--text-3)">Typing target</dt>
          <dd class="m-0 text-right text-xs font-medium text-(--text)">
            {$keyboard.targetLabel}
          </dd>
        </div>
      </dl>
    </div>
  </aside>
</div>
