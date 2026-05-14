<script lang="ts">
  type Props = { class?: string };
  let { class: className = '' }: Props = $props();
</script>

<div class={`rounded bg-picobit-border ${className}`}></div>
