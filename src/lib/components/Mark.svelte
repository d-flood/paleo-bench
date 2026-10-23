<script lang="ts">
  let { value, href, label }: { value: number | null; href?: string; label?: string } = $props();

  const v = $derived(value == null ? null : Math.round(value));
</script>

{#if href && v != null}
  <a class="mk" class:lo={v < 50} {href} aria-label={label}>{v}</a>
{:else}
  <span class="mk" class:lo={v != null && v < 50} class:na={v == null} aria-label={label}>
    {v ?? '–'}
  </span>
{/if}
