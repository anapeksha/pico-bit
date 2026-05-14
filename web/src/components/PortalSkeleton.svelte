<div class="animate-pulse grid gap-4">
  <!-- TopSection: 4 stat cards matching TopSection.svelte layout -->
  <div class="flex flex-wrap justify-around gap-2">
    <div
      class="min-w-0 basis-full rounded-[10px] border border-picobit-border bg-picobit-surface px-3.5 py-3 sm:basis-[calc(50%-0.25rem)] xl:basis-[calc(25%-0.375rem)]"
    >
      <div class="mb-2 h-2.5 w-16 rounded bg-picobit-border-strong opacity-60"></div>
      <div class="h-4 w-28 rounded bg-picobit-border-strong opacity-60"></div>
    </div>
    <div
      class="min-w-0 basis-full rounded-[10px] border border-picobit-border bg-picobit-surface px-3.5 py-3 sm:basis-[calc(50%-0.25rem)] xl:basis-[calc(25%-0.375rem)]"
    >
      <div class="mb-2 h-2.5 w-20 rounded bg-picobit-border-strong opacity-60"></div>
      <div class="h-4 w-24 rounded bg-picobit-border-strong opacity-60"></div>
    </div>
    <div
      class="min-w-0 basis-full rounded-[10px] border border-picobit-border bg-picobit-surface px-3.5 py-3 sm:basis-[calc(50%-0.25rem)] xl:basis-[calc(25%-0.375rem)]"
    >
      <div class="mb-2 h-2.5 w-14 rounded bg-picobit-border-strong opacity-60"></div>
      <div class="h-4 w-20 rounded bg-picobit-border-strong opacity-60"></div>
    </div>
    <div
      class="min-w-0 basis-full rounded-[10px] border border-picobit-border bg-picobit-surface px-3.5 py-3 sm:basis-[calc(50%-0.25rem)] xl:basis-[calc(25%-0.375rem)]"
    >
      <div class="mb-2 h-2.5 w-16 rounded bg-picobit-border-strong opacity-60"></div>
      <div class="h-4 w-32 rounded bg-picobit-border-strong opacity-60"></div>
    </div>
  </div>

  <!-- Three-column grid matching App.svelte layout -->
  <div
    class="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_17rem] xl:grid-cols-[15rem_minmax(0,1fr)_17rem]"
  >
    <!-- Left: About + Status panels -->
    <div
      class="lg:order-3 lg:col-span-full lg:grid lg:grid-cols-2 lg:gap-4 xl:order-0 xl:col-span-1 xl:block"
    >
      <div class="flex flex-col gap-3.5 xl:w-60">
        <!-- About panel -->
        <div class="rounded-xl border border-picobit-border bg-picobit-surface px-4 py-4">
          <div class="mb-3 h-3 w-10 rounded bg-picobit-border-strong opacity-60"></div>
          <div class="flex flex-col gap-2">
            <div class="h-2.5 w-full rounded bg-picobit-border opacity-60"></div>
            <div class="h-2.5 w-full rounded bg-picobit-border opacity-60"></div>
            <div class="h-2.5 w-3/4 rounded bg-picobit-border opacity-60"></div>
            <div class="mt-1 h-2.5 w-full rounded bg-picobit-border opacity-60"></div>
            <div class="h-2.5 w-5/6 rounded bg-picobit-border opacity-60"></div>
          </div>
        </div>

        <!-- Status panel -->
        <div class="rounded-xl border border-picobit-border bg-picobit-surface px-4 py-4">
          <div class="mb-3 h-3 w-10 rounded bg-picobit-border-strong opacity-60"></div>
          <div class="flex items-center justify-between border-b border-picobit-border pb-2">
            <div class="h-2.5 w-24 rounded bg-picobit-border opacity-60"></div>
            <div class="h-2.5 w-8 rounded bg-picobit-border opacity-60"></div>
          </div>
          <div class="flex items-center justify-between py-2">
            <div class="h-2.5 w-24 rounded bg-picobit-border opacity-60"></div>
            <div class="h-2.5 w-16 rounded bg-picobit-border opacity-60"></div>
          </div>
          <div class="my-3.5 h-px bg-picobit-border"></div>
          <div class="h-9 rounded-lg bg-picobit-border opacity-60"></div>
        </div>
      </div>
    </div>

    <!-- Middle: DuckyEditor + BinaryArmory -->
    <div
      class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-picobit-border bg-picobit-surface lg:order-1 xl:order-0"
    >
      <!-- DuckyEditor skeleton: toolbar + code lines -->
      <div class="flex items-center justify-between border-b border-picobit-border px-3.5 py-2.5">
        <div class="h-2.5 w-24 rounded bg-picobit-border opacity-60"></div>
        <div class="flex gap-2">
          <div class="h-7 w-16 rounded-lg bg-picobit-border opacity-60"></div>
          <div class="h-7 w-12 rounded-lg bg-picobit-border opacity-60"></div>
          <div class="h-7 w-14 rounded-lg bg-picobit-border opacity-60"></div>
        </div>
      </div>
      <div class="flex-1 px-3.5 py-4" style="min-height: 12rem">
        <div class="flex flex-col gap-2.5">
          <div class="h-2.5 w-32 rounded bg-picobit-border opacity-60"></div>
          <div class="h-2.5 w-48 rounded bg-picobit-border opacity-60"></div>
          <div class="h-2.5 w-20 rounded bg-picobit-border opacity-60"></div>
          <div class="h-2.5 w-44 rounded bg-picobit-border opacity-60"></div>
          <div class="h-2.5 w-28 rounded bg-picobit-border opacity-60"></div>
          <div class="h-2.5 w-36 rounded bg-picobit-border opacity-60"></div>
          <div class="h-2.5 w-16 rounded bg-picobit-border opacity-60"></div>
        </div>
      </div>

      <!-- BinaryArmory skeleton: header bar -->
      <div class="flex items-center border-t border-picobit-border bg-picobit-surface-2 px-3.5 py-2.5">
        <div class="h-2.5 w-24 rounded bg-picobit-border opacity-60"></div>
      </div>
    </div>

    <!-- Right: Layout + Recent Runs panels -->
    <div class="lg:order-2 xl:order-0">
      <div class="flex flex-col gap-3.5 xl:w-[17rem]">
        <!-- Layout panel -->
        <div class="rounded-xl border border-picobit-border bg-picobit-surface px-4 py-4">
          <div class="mb-3 h-3 w-12 rounded bg-picobit-border-strong opacity-60"></div>
          <div class="mb-3 flex flex-col gap-1.5">
            <div class="h-2.5 w-full rounded bg-picobit-border opacity-60"></div>
            <div class="h-2.5 w-4/5 rounded bg-picobit-border opacity-60"></div>
          </div>
          <div class="flex flex-col gap-2">
            <div class="h-9 w-full rounded-lg bg-picobit-border opacity-60"></div>
            <div class="h-9 w-full rounded-lg bg-picobit-border opacity-60"></div>
          </div>
        </div>

        <!-- Recent Runs panel -->
        <div class="rounded-xl border border-picobit-border bg-picobit-surface px-4 py-4">
          <div class="mb-3 h-3 w-20 rounded bg-picobit-border-strong opacity-60"></div>
          <div class="flex flex-col gap-2">
            <div class="h-8 w-full rounded-lg bg-picobit-border opacity-60"></div>
            <div class="h-8 w-full rounded-lg bg-picobit-border opacity-60"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
