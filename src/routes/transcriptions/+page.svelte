<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { MediaQuery } from 'svelte/reactivity';
  import CaretLeftIcon from 'phosphor-svelte/lib/CaretLeftIcon';
  import CaretRightIcon from 'phosphor-svelte/lib/CaretRightIcon';
  import MarkedScript from '#lib/components/MarkedScript.svelte';
  import TranscriptionKey from '#lib/components/TranscriptionKey.svelte';
  import Viewer from '#lib/components/Viewer.svelte';
  import {
    PROVIDERS,
    buildRows,
    fmt1,
    loadFolio,
    fmtCost,
    fmtTime,
    paperName,
    pct,
    scriptHash,
    store,
    type Folio
  } from '#lib/bench.js';

  let { data } = $props();

  const KEY = 'paleo-bench:transcriptions';
  const S = $derived(data.summary.samples);
  const rows = $derived(buildRows(data.summary));
  const order = $derived(
    [...rows].sort(
      (a, b) => (b.std.mark ?? -1) - (a.std.mark ?? -1) || a.m.label.localeCompare(b.m.label)
    )
  );
  const bySlug = $derived(new Map(rows.map((r) => [r.m.slug, r])));

  let c = $state(0);
  let p = $state(0);
  let view = $state<'script' | 'paper'>('script');
  let showKey = $state(false);
  let ready = $state(false);
  const desktop = new MediaQuery('min-width: 1024px');

  const row = $derived(rows[c]);
  const sample = $derived(S[p]);
  const cell = $derived(row.cells[p]);
  const result = $derived(row.res[p]);
  const k = $derived(order.indexOf(row));

  const current = $derived(ready && (showKey || cell.kind === 'ok') ? loadFolio(sample.id) : null);

  function fromHash(): boolean {
    const m = /^#(.+)\.(\d+)$/.exec(location.hash);
    const r = m && bySlug.get(m[1]);
    const n = m ? Number(m[2]) - 1 : -1;
    if (!r || n < 0 || n >= S.length) return false;
    c = r.i;
    p = n;
    return true;
  }

  function select(nc: number, np: number) {
    c = nc;
    p = np;
    store.set(KEY, { slug: rows[c].m.slug, p });
    goto(scriptHash(rows[c], p), { shallow: true, replace: true });
  }

  onMount(() => {
    if (!fromHash()) {
      const saved = store.get<{ slug: string; p: number }>(KEY);
      const r =
        bySlug.get(saved?.slug ?? '') ??
        rows.find((x) => x.m.label === 'Sonnet 5.5 (low)') ??
        order[0];
      const n = saved && saved.p >= 0 && saved.p < S.length ? saved.p : Math.min(3, S.length - 1);
      select(r.i, n);
    }
    ready = true;
  });

  function onTabKey(e: KeyboardEvent) {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    const next = (p + (e.key === 'ArrowRight' ? 1 : S.length - 1)) % S.length;
    select(c, next);
    document.getElementById(`paper-${next}`)?.focus();
  }
</script>

<svelte:head><title>Image & transcription, Paleo Bench</title></svelte:head>

<svelte:window onhashchange={fromHash} />

<h1 class="vh">Image & transcription</h1>

{#snippet sheet(folio: Folio | null)}
  {#if showKey}
    <TranscriptionKey {sample} {folio} />
  {:else}
    <MarkedScript label={row.m.label} {sample} {cell} {folio} />
  {/if}
{/snippet}

<div class="tools">
  <div class="pick">
    <label for="cand">Model</label>
    <select
      class="sel"
      id="cand"
      value={c}
      onchange={(e) => select(Number(e.currentTarget.value), p)}
    >
      {#each PROVIDERS as prov (prov)}
        {@const list = order.filter((r) => r.m.provider === prov)}
        {#if list.length}
          <optgroup label={prov}>
            {#each list as r (r.i)}
              <option value={r.i}>
                {r.m.label}, {r.std.mark == null ? 'no folios run' : `mean ${fmt1(r.std.mark)}`}
              </option>
            {/each}
          </optgroup>
        {/if}
      {/each}
    </select>

    <button type="button" class="btn" disabled={k <= 0} onclick={() => select(order[k - 1].i, p)}
      ><CaretLeftIcon aria-hidden="true" />Previous model</button
    >

    <button
      type="button"
      class="btn"
      disabled={k >= order.length - 1}
      onclick={() => select(order[k + 1].i, p)}
    >
      Next model<CaretRightIcon aria-hidden="true" />
    </button>
    <span class="pos">{k + 1} of {order.length} by mean score</span>
    <button
      type="button"
      class="btn key"
      aria-pressed={showKey}
      onclick={() => (showKey = !showKey)}>Human committee transcription</button
    >
  </div>
  <div class="papers" role="tablist" aria-label="Folios" tabindex="-1" onkeydown={onTabKey}>
    {#each S as s, n (s.id)}
      {@const pc = row.cells[n]}
      <button
        type="button"
        role="tab"
        id="paper-{n}"
        class="ptab"
        aria-selected={n === p}
        tabindex={n === p ? 0 : -1}
        aria-label="{paperName(s)}{s.microfilm ? ', microfilm' : ''}: {pc.kind === 'ok'
          ? `score ${pc.v}`
          : pc.kind === 'abs'
            ? `failed, ${pc.why}`
            : 'not run'}"
        onclick={() => select(c, n)}
      >
        <span class="pn">{s.ms} {s.folio}</span>
        {#if pc.kind === 'ok'}
          <span class="pm mk" class:lo={pc.v < 50}>{pc.v}</span>
        {:else if pc.kind === 'abs'}
          <span class="pm ab">failed</span>
        {:else}
          <span class="pm mk na">–</span>
        {/if}
        <span class="mf">{s.microfilm ? 'Microfilm' : ''}</span>
      </button>
    {/each}
  </div>
</div>

<div class="seg" role="group" aria-label="View">
  <button type="button" aria-pressed={view === 'script'} onclick={() => (view = 'script')}
    >Transcription</button
  >

  <button type="button" aria-pressed={view === 'paper'} onclick={() => (view = 'paper')}
    >Image</button
  >
</div>

<div class="grid" data-view={view}>
  <section class="qp-pane" aria-label="Question paper">
    <div class="viewer-box">
      {#if ready && (desktop.current || view === 'paper')}
        <Viewer {sample} label={paperName(sample)} />
      {/if}
    </div>
  </section>
  <section
    class="script-pane"
    aria-label={showKey ? 'Human committee transcription' : 'Annotated transcription'}
  >
    <dl class="strip">
      {#if cell.kind === 'ok' && result}
        <div>
          <dt>Character error</dt>
          <dd>{pct(result.cer)}</dd>
        </div>
        <div>
          <dt>Word error</dt>
          <dd>{pct(result.wer)}</dd>
        </div>
        <div>
          <dt>Cost</dt>
          <dd>{fmtCost(result.cost)}</dd>
        </div>

        <div>
          <dt>Time</dt>
          <dd>{fmtTime(result.latency, true)}</dd>
        </div>
        {#if result.outTokens != null}
          <div>
            <dt>Output tokens</dt>
            <dd>{result.outTokens.toLocaleString('en')}</dd>
          </div>
        {/if}
      {:else if cell.kind === 'abs'}
        <div>
          <dt>Failed</dt>
          <dd>{cell.why}</dd>
        </div>
        {#if result?.latency != null}
          <div>
            <dt>Time spent</dt>
            <dd>{fmtTime(result.latency, true)}</dd>
          </div>
        {/if}
      {:else}
        <div>
          <dt>Not run</dt>
          <dd>no result for this folio</dd>
        </div>
      {/if}
    </dl>
    {#await current}
      {@render sheet(null)}
    {:then f}
      {@render sheet(f)}
    {:catch}
      <p class="sheet empty">Transcription failed to load. Reload to retry.</p>
    {/await}
    <ul class="points aside">
      {#if showKey}
        <li>Reference transcription for scoring, without accents or punctuation</li>
      {:else}
        <li>
          Red pen and margin deductions: word alignment against the human committee transcription,
          approximate
        </li>
        <li>Circled score: 100 minus character error rate</li>
      {/if}
    </ul>
  </section>
</div>

<style>
  .tools {
    display: grid;
    gap: 12px;
    margin-bottom: 14px;
  }

  .pick {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 10px;
  }

  .pick label,
  .pos {
    color: var(--pencil);
  }

  .pos {
    font-size: 0.9rem;
  }

  .key {
    margin-left: auto;
  }

  .pick select {
    font-weight: 500;
    max-width: min(28rem, 100%);
  }

  .papers {
    display: flex;
    gap: 6px;
    overflow-x: auto;
    padding: 2px 2px 4px;
  }

  .ptab {
    flex: 1 0 6.5rem;
    display: grid;
    justify-items: center;
    padding: 0.4rem 0.6rem 0.35rem;
    background: var(--paper);
    border: 1px solid var(--edge);
    border-radius: 3px;
    cursor: pointer;
  }

  .ptab:hover {
    border-color: var(--pencil);
  }

  .ptab[aria-selected='true'] {
    border-color: var(--ink);
    box-shadow: inset 0 -2.5px 0 var(--ink);
  }

  .pn {
    font-size: 0.86rem;
    color: var(--pencil);
    white-space: nowrap;
  }

  .ptab[aria-selected='true'] .pn {
    color: var(--ink);
    font-weight: 500;
  }

  .pm {
    font-family: var(--f-script);
    font-size: 1.2rem;
    line-height: 1.2;
    margin-top: 2px;
  }

  .pm.mk {
    height: 1.75rem;
  }

  .mf {
    font-size: 0.72rem;
    color: var(--faint);
    min-height: 1em;
    line-height: 1.1;
  }

  .seg {
    display: none;
    margin-bottom: 12px;
    border: 1px solid var(--edge);
    border-radius: 4px;
    overflow: hidden;
    background: var(--paper);
  }

  .seg button {
    flex: 1;
    padding: 0.55rem 0.4rem;
    border: 0;
    border-left: 1px solid var(--edge);
    background: none;
    font-weight: 500;
    cursor: pointer;
  }

  .seg button:first-child {
    border-left: 0;
  }

  .seg button[aria-pressed='true'] {
    background: var(--ink);
    color: var(--paper);
  }

  .grid {
    display: grid;
    gap: 22px;
    align-items: start;
  }

  .qp-pane,
  .script-pane {
    min-width: 0;
  }

  .viewer-box {
    height: 70vh;
    min-height: 420px;
    background: var(--viewer);
    border: 1px solid var(--edge);
  }

  .aside {
    margin: 8px 2px 0;
    color: var(--pencil);
    font-size: 0.85rem;
    max-width: 70ch;
  }

  .aside {
    margin-top: 10px;
  }

  .strip {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 22px;
    margin: 0 0 10px;
    padding: 0 2px;
    font-variant-numeric: tabular-nums;
  }

  .strip div {
    display: flex;
    gap: 6px;
    align-items: baseline;
  }

  .strip dt {
    color: var(--pencil);
    font-size: 0.9rem;
  }

  .strip dd {
    margin: 0;
    font-weight: 500;
  }

  @media (min-width: 1024px) {
    .grid {
      grid-template-columns: minmax(0, 0.92fr) minmax(0, 1.08fr);
    }

    .qp-pane {
      position: sticky;
      top: max(12px, env(safe-area-inset-top, 0px));
    }

    .viewer-box {
      height: calc(100vh - 70px);
      min-height: 520px;
    }
  }

  @media (max-width: 1023.98px) {
    .seg {
      display: flex;
    }

    .grid[data-view='script'] .qp-pane,
    .grid[data-view='paper'] .script-pane {
      display: none;
    }

    .viewer-box {
      height: 72vh;
      min-height: 380px;
    }
  }
</style>
