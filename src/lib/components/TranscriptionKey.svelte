<script lang="ts">
  import { parseGroundTruth } from '#lib/align.js';
  import { paperName, type Folio, type Sample } from '#lib/bench.js';

  let { sample, folio }: { sample: Sample; folio: Folio | null } = $props();

  const key = $derived.by(() => {
    if (!folio) return null;
    const gt = parseGroundTruth(folio.gt);
    const lines = gt.lines.filter((l) => l.kind !== 'blank');
    return {
      lines,
      count: lines.filter((l) => l.kind === 'text').length,
      words: gt.tokens.filter((t) => gt.lines[t.line].kind === 'text').length
    };
  });
</script>

<article class="sheet script" aria-live="polite">
  <div class="ruled">
    <div class="hl"><span>Folio:</span> <span class="val">{paperName(sample)}</span></div>
    {#if key}
      <div class="hl">
        <span>Human committee transcription:</span>
        <span class="val">
          {key.count} lines, {key.words} words, {sample.chars?.toLocaleString('en')} characters
        </span>
      </div>
      {#each key.lines as l (l.index)}
        <div class="l" class:col={l.kind === 'column'}>
          <span class="mm num">{l.n ?? ''}</span>{l.text}
        </div>
      {/each}
    {:else}
      <p class="l col">Loading the human committee transcription…</p>
    {/if}
  </div>
</article>

<style>
  .num {
    color: var(--pencil);
    font-family: var(--f-ui);
    font-style: normal;
    font-size: 0.8rem;
  }
</style>
