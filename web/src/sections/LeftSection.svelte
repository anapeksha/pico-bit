<script lang="ts">
  import { keyboard } from '../stores/keyboard';
  import { seededThisBoot } from '../stores/run';

  const panelClass = 'rounded-xl border border-(--border) bg-(--surface) px-4 py-4';
  const titleClass = 'm-0 mb-2.5 text-[13px] font-semibold tracking-[-0.005em] text-(--text)';
</script>

<div
  class="lg:order-3 lg:col-span-full lg:grid lg:grid-cols-2 lg:gap-4 xl:order-0 xl:col-span-1 xl:block"
>
  <aside class="flex flex-col gap-3.5 xl:w-60">
    <div class={panelClass}>
      <p class={titleClass}>About</p>
      <p class="m-0 mb-2.5 text-xs leading-relaxed text-(--text-3)">
        Two-stage drop-shell workflow for authorized security assessment.
      </p>
      <ul class="m-0 list-disc pl-4 text-xs leading-7 text-(--text-3)">
        <li>
          <strong>Stage&nbsp;1&nbsp;&middot;&nbsp;Recon</strong> - write DuckyScript to type commands
          or exfiltrate data from the target
        </li>
        <li>
          <strong>Stage&nbsp;2&nbsp;&middot;&nbsp;Inject</strong> - upload an agent binary, then HID-inject
          the USB execution stager; the agent writes loot back to the Pico drive
        </li>
        <li>Loot panel live-updates as data arrives</li>
      </ul>
    </div>

    <div class={panelClass}>
      <p class={titleClass}>Status</p>
      <dl class="m-0 grid">
        <div class="flex items-center justify-between gap-2 border-b border-(--border) pb-2">
          <span class="text-xs text-(--text-3)">Seeded this boot</span>
          <span class="text-right text-xs font-medium text-(--text)">
            {$seededThisBoot ? 'Yes' : 'No'}
          </span>
        </div>
        <div class="flex items-center justify-between gap-2 py-2">
          <span class="text-xs text-(--text-3)">Typing target</span>
          <span class="text-right text-xs font-medium text-(--text)">
            {$keyboard.targetLabel}
          </span>
        </div>
      </dl>
      <div class="my-3.5 h-px bg-(--border)"></div>
      <form action="/logout" method="post">
        <button
          class="inline-flex h-9 w-full cursor-pointer items-center justify-center rounded-lg border border-(--border-strong) bg-(--surface) px-4 text-[13px] font-medium leading-none text-(--danger) hover:border-(--danger-border) hover:bg-(--danger-bg)"
          type="submit"
        >
          Sign out
        </button>
      </form>
    </div>
  </aside>
</div>
