<script lang="ts">
  import 'triiiceratops/style.css';
  import { TriiiceratopsViewer } from 'triiiceratops/svelte';
  import type { Sample } from '#lib/bench.js';
  import { folioView } from '#lib/iiif.js';
  import { theme } from '#lib/theme.svelte.js';

  let { sample, label }: { sample: Sample; label: string } = $props();

  const config = {
    showCanvasNav: false,
    toolbarOpen: false,
    gallery: { open: false },
    showToggle: false
  };

  const themeConfig = $derived.by(() => {
    const scheme = theme.current;
    const css = getComputedStyle(document.documentElement);
    const token = (name: string) => css.getPropertyValue(name).trim();
    const ink = token('--ink');
    const paper = token('--paper');
    return {
      colorScheme: scheme,
      primary: token('--pen'),
      primaryContent: paper,
      neutral: ink,
      neutralContent: paper,
      viewerBg: token('--viewer'),
      viewerContent: ink,
      toolbarBg: paper,
      toolbarContent: ink,
      panelBg: paper,
      panelContent: ink,
      galleryBg: paper,
      galleryContent: ink,
      inputBg: paper,
      content: ink,
      surfaceBorder: token('--edge'),
      radiusBox: '3px',
      radiusButtons: '3px',
      radiusSelector: '3px',
      radiusToolbar: '4px',
      radiusPanels: '3px',
      radiusControls: '4px',
      radiusControlsButtons: '3px',
      depth: 0 as const
    };
  });

  const view = $derived(folioView(sample, label));
</script>

{#await view}
  <p class="state">Loading the image…</p>
{:then v}
  {#key v.id}
    <TriiiceratopsViewer
      manifestId={v.id}
      manifestJson={v.manifest}
      {config}
      theme={theme.current}
      {themeConfig}
      initialCanvasRegion={v.region}
    />
  {/key}
{:catch}
  <p class="state">Image failed to load from CSNTM. Reload to retry.</p>
{/await}

<style>
  .state {
    margin: 0;
    padding: 1.2rem;
    color: var(--pencil);
  }
</style>
