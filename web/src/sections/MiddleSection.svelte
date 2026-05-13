<script lang="ts">
  import BinaryArmory from '../components/BinaryArmory.svelte';
  import DuckyEditor from '../components/DuckyEditor.svelte';
</script>

<div
  class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-picobit-border bg-picobit-surface lg:order-1 xl:order-0"
>
  <DuckyEditor />
  <BinaryArmory />
</div>
